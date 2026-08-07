#include "robust_execution/model/events.hpp"

#include <array>
#include <cstdlib>

int main() {
  namespace model = robust_execution::model;
  const std::array<model::EventPayload, 17U> payloads{
      model::BookSnapshot{},
      model::DepthUpdate{},
      model::Trade{},
      model::Decision{},
      model::OrderSubmit{},
      model::OrderAcknowledged{},
      model::OrderRejected{},
      model::CancelRequest{},
      model::CancelAcknowledged{},
      model::CancelRejected{},
      model::ReplaceRequest{},
      model::ReplaceAcknowledged{},
      model::ReplaceRejected{},
      model::Fill{},
      model::Fee{},
      model::TerminalCompletion{},
      model::Timer{},
  };
  const std::array<model::EventKind, 17U> expected{
      model::EventKind::BookSnapshot,
      model::EventKind::DepthUpdate,
      model::EventKind::Trade,
      model::EventKind::Decision,
      model::EventKind::OrderSubmit,
      model::EventKind::OrderAcknowledged,
      model::EventKind::OrderRejected,
      model::EventKind::CancelRequest,
      model::EventKind::CancelAcknowledged,
      model::EventKind::CancelRejected,
      model::EventKind::ReplaceRequest,
      model::EventKind::ReplaceAcknowledged,
      model::EventKind::ReplaceRejected,
      model::EventKind::Fill,
      model::EventKind::Fee,
      model::EventKind::TerminalCompletion,
      model::EventKind::Timer,
  };
  for (std::size_t index = 0U; index < payloads.size(); ++index) {
    if (model::event_kind(payloads[index]) != expected[index] ||
        model::to_string(expected[index]) == "unknown") {
      return EXIT_FAILURE;
    }
  }
  return EXIT_SUCCESS;
}
