#include "kernel_internal.hpp"

#include "robust_execution/model/validation.hpp"

#include <sstream>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>

namespace robust_execution::simulation {
model::Event SimulationKernel::Impl::make_response_event(
    model::EventPayload payload,
    const model::ActionTiming& timing,
    const model::SourceChannelId& channel,
    bool execution_time
) {
  const auto event_time = execution_time ? timing.exchange_process : timing.acknowledgement_send;
  return model::Event{
      generated_header(
          event_time,
          timing.acknowledgement_receive,
          timing.acknowledgement_available,
          model::EventOrigin::SyntheticExchange,
          channel
      ),
      std::move(payload),
  };
}

void SimulationKernel::Impl::emit_event(
    model::Event event,
    const model::ActionTiming& timing,
    std::string detail
) {
  if (!event.header.available_time.has_value()) {
    throw std::logic_error("emitted exchange event lacks available_time");
  }
  if (event.header.available_time->domain() != timing.acknowledgement_available.domain() ||
      event.header.available_time->value() != timing.acknowledgement_available.value()) {
    throw std::logic_error("emitted exchange event uses inconsistent acknowledgement timing");
  }
  const auto issues = model::validate_event(event);
  if (model::has_errors(issues)) {
    throw std::logic_error("matching engine produced an invalid event-model response");
  }
  const auto sequence = event.header.ordering.canonical_sequence;
  const auto available = *event.header.available_time;
  KernelTask task{KernelTaskKind::ObserverDelivery, std::move(event), std::nullopt};
  const auto snapshot = task;
  const auto task_id = scheduler_.schedule(
      available,
      KernelStage::ObserverAvailable,
      sequence,
      std::move(task)
  );
  record_trace(
      KernelTraceAction::Scheduled,
      ScheduledTask{
          task_id,
          available,
          KernelStage::ObserverAvailable,
          sequence,
          snapshot,
      },
      std::move(detail)
  );
}

void SimulationKernel::Impl::record_failure(
    const ScheduledTask& scheduled,
    const exchange::EngineFailure& failure
) {
  failures_.push_back(KernelFailureRecord{
      scheduled.task.event.header.event_id,
      scheduled.scheduled_time,
      failure,
  });
  std::ostringstream detail;
  detail << exchange::to_string(failure.code) << '|' << failure.client_order_id.value() << '|';
  if (failure.exchange_order_id.has_value()) {
    detail << failure.exchange_order_id->value();
  }
  detail << '|';
  if (failure.current_state.has_value()) {
    detail << static_cast<unsigned>(*failure.current_state);
  }
  detail << '|' << failure.detail;
  record_trace(KernelTraceAction::EngineFailure, scheduled, detail.str());
}

void SimulationKernel::Impl::emit_matches(
    const std::vector<exchange::MatchExecution>& matches,
    const model::ActionTiming& timing
) {
  for (const auto& match : matches) {
    emit_event(
        make_response_event(
            match.trade,
            timing,
            config_.exchange_trade_channel,
            true
        ),
        timing,
        "trade"
    );
    emit_event(
        make_response_event(
            match.maker_fill,
            timing,
            config_.exchange_fill_channel,
            true
        ),
        timing,
        "maker_fill"
    );
    emit_event(
        make_response_event(
            match.taker_fill,
            timing,
            config_.exchange_fill_channel,
            true
        ),
        timing,
        "taker_fill"
    );
  }
}

void SimulationKernel::Impl::emit_submit_result(
    const ScheduledTask& scheduled,
    const exchange::SubmitResult& result,
    const model::ActionTiming& timing
) {
  if (result.acknowledgement.has_value()) {
    emit_event(
        make_response_event(
            *result.acknowledgement,
            timing,
            config_.exchange_order_channel,
            false
        ),
        timing,
        "order_acknowledged"
    );
  }
  if (result.rejection.has_value()) {
    emit_event(
        make_response_event(
            *result.rejection,
            timing,
            config_.exchange_order_channel,
            false
        ),
        timing,
        "order_rejected"
    );
  }
  if (result.failure.has_value()) {
    record_failure(scheduled, *result.failure);
  }
  emit_matches(result.matches, timing);
  if (result.automatic_cancellation.has_value()) {
    emit_event(
        make_response_event(
            *result.automatic_cancellation,
            timing,
            config_.exchange_order_channel,
            false
        ),
        timing,
        "automatic_cancel"
    );
  }
}

void SimulationKernel::Impl::emit_cancel_result(
    const ScheduledTask& scheduled,
    const exchange::CancelResult& result,
    const model::ActionTiming& timing
) {
  if (result.acknowledgement.has_value()) {
    emit_event(
        make_response_event(
            *result.acknowledgement,
            timing,
            config_.exchange_order_channel,
            false
        ),
        timing,
        "cancel_acknowledged"
    );
  }
  if (result.failure.has_value()) {
    record_failure(scheduled, *result.failure);
  }
}

void SimulationKernel::Impl::emit_replace_result(
    const ScheduledTask& scheduled,
    const exchange::ReplaceResult& result,
    const model::ActionTiming& timing
) {
  if (result.acknowledgement.has_value()) {
    emit_event(
        make_response_event(
            *result.acknowledgement,
            timing,
            config_.exchange_order_channel,
            false
        ),
        timing,
        "replace_acknowledged"
    );
  }
  if (result.failure.has_value()) {
    record_failure(scheduled, *result.failure);
  }
  emit_matches(result.matches, timing);
}

void SimulationKernel::Impl::process_exchange(const ScheduledTask& scheduled) {
  if (!scheduled.task.action_timing.has_value()) {
    throw std::logic_error("exchange-process task lacks action timing");
  }
  const auto& timing = *scheduled.task.action_timing;
  if (scheduled.scheduled_time.domain() != timing.exchange_process.domain() ||
      scheduled.scheduled_time.value() != timing.exchange_process.value()) {
    throw std::logic_error("exchange-process task time differs from action timing");
  }

  std::visit(
      [this, &scheduled, &timing](const auto& payload) {
        using Payload = std::decay_t<decltype(payload)>;
        if constexpr (std::is_same_v<Payload, model::OrderSubmit>) {
          emit_submit_result(scheduled, matching_engine_.submit(payload), timing);
        } else if constexpr (std::is_same_v<Payload, model::CancelRequest>) {
          emit_cancel_result(scheduled, matching_engine_.cancel(payload), timing);
        } else if constexpr (std::is_same_v<Payload, model::ReplaceRequest>) {
          emit_replace_result(scheduled, matching_engine_.replace(payload), timing);
        } else {
          throw std::logic_error("exchange-process task contains a non-command event");
        }
      },
      scheduled.task.event.payload
  );

  const auto violations = matching_engine_.validate_invariants();
  if (!violations.empty()) {
    throw std::logic_error("matching-engine invariant failed during simulation dispatch");
  }
}

}  // namespace robust_execution::simulation
