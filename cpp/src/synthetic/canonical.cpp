#include "robust_execution/synthetic/types.hpp"

#include <sstream>
#include <string>

namespace robust_execution::synthetic {
namespace {

std::string json_escape(std::string_view input) {
  std::ostringstream output;
  for (const char character : input) {
    switch (character) {
      case '\\': output << "\\\\"; break;
      case '"': output << "\\\""; break;
      case '\n': output << "\\n"; break;
      case '\r': output << "\\r"; break;
      case '\t': output << "\\t"; break;
      default: output << character; break;
    }
  }
  return output.str();
}

std::string aggressor_text(model::AggressorSide side) {
  switch (side) {
    case model::AggressorSide::Buy: return "buy";
    case model::AggressorSide::Sell: return "sell";
    case model::AggressorSide::Unknown: return "unknown";
  }
  return "unknown";
}

std::string side_text(const std::optional<model::Side>& side) {
  if (!side.has_value()) {
    return "";
  }
  return std::string{model::to_string(*side)};
}

}  // namespace

std::string canonical_tape(const SyntheticTape& tape) {
  std::ostringstream output;
  output << canonical_config(tape.config);
  for (const auto& action : tape.actions) {
    output << "action|" << action.sequence << '|' << action.global_step << '|'
           << action.time.value() << '|' << action.regime_id << '|'
           << to_string(action.kind) << '|' << side_text(action.side) << '|'
           << action.quantity.value() << '|';
    if (action.price.has_value()) {
      output << action.price->value();
    }
    output << '|';
    if (action.client_order_id.has_value()) {
      output << action.client_order_id->value();
    }
    output << '|';
    if (action.exchange_order_id.has_value()) {
      output << action.exchange_order_id->value();
    }
    output << '|';
    if (action.shock_id.has_value()) {
      output << *action.shock_id;
    }
    output << '|' << action.detail << '\n';
  }
  for (const auto& trade : tape.trades) {
    output << "trade|" << trade.sequence << '|' << trade.global_step << '|'
           << trade.time.value() << '|' << trade.regime_id << '|'
           << trade.trade.trade_id.value() << '|' << trade.trade.price.value() << '|'
           << trade.trade.quantity.value() << '|'
           << aggressor_text(trade.trade.aggressor_side) << '|'
           << trade.maker_fee.value() << '|' << trade.taker_fee.value() << '\n';
  }
  for (const auto& step : tape.steps) {
    output << "step|" << step.global_step << '|' << step.time.value() << '|'
           << step.regime_id << '|' << step.reference_price.value() << '|';
    if (step.best_bid.has_value()) {
      output << step.best_bid->value();
    }
    output << '|';
    if (step.best_ask.has_value()) {
      output << step.best_ask->value();
    }
    output << '|' << step.visible_bid_lots.value() << '|'
           << step.visible_ask_lots.value() << '|' << step.active_orders << '|'
           << step.impact_microticks << '|' << step.limit_excitation_ppm << '|'
           << step.market_excitation_ppm << '|' << step.cancel_excitation_ppm << '\n';
  }
  output << "summary|" << tape.summary.total_steps << '|'
         << tape.summary.limit_submissions << '|'
         << tape.summary.market_submissions << '|'
         << tape.summary.cancellations << '|'
         << tape.summary.reference_moves << '|'
         << tape.summary.shocks_applied << '|'
         << tape.summary.trades << '|'
         << tape.summary.rejected_commands << '|'
         << tape.summary.executed_lots.value() << '|'
         << tape.summary.maker_fees.value() << '|'
         << tape.summary.taker_fees.value() << '|'
         << tape.summary.final_reference_price.value() << '|';
  if (tape.summary.final_best_bid.has_value()) {
    output << tape.summary.final_best_bid->value();
  }
  output << '|';
  if (tape.summary.final_best_ask.has_value()) {
    output << tape.summary.final_best_ask->value();
  }
  output << '\n';
  return output.str();
}

std::string manifest_json(const SyntheticTape& tape) {
  const auto& summary = tape.summary;
  std::ostringstream output;
  output << '{'
         << "\"schema_id\":\"synthetic-market-manifest-v1\","
         << "\"scenario_id\":\"" << json_escape(tape.config.scenario_id) << "\","
         << "\"scenario_class\":\"" << to_string(tape.config.scenario_class) << "\","
         << "\"calibration_status\":\"not_calibrated_step9\","
         << "\"run_id\":\"" << json_escape(tape.config.run_id.value()) << "\","
         << "\"seed\":" << tape.config.random_seed << ','
         << "\"config_sha256\":\"" << tape.config_sha256 << "\","
         << "\"instrument\":\""
         << json_escape(tape.config.instrument.instrument.value()) << "\","
         << "\"grid_step_ns\":" << tape.config.grid_step_ns << ','
         << "\"fee_schedule_id\":\""
         << json_escape(tape.config.fees.fee_schedule_id.value()) << "\","
         << "\"regime_count\":" << tape.config.regimes.size() << ','
         << "\"regime_ids\":[";
  for (std::size_t index = 0U; index < tape.config.regimes.size(); ++index) {
    if (index != 0U) output << ',';
    output << "\"" << json_escape(tape.config.regimes[index].regime_id) << "\"";
  }
  output << "],"
         << "\"shock_count\":" << tape.config.shocks.size() << ','
         << "\"shock_ids\":[";
  for (std::size_t index = 0U; index < tape.config.shocks.size(); ++index) {
    if (index != 0U) output << ',';
    output << "\"" << json_escape(tape.config.shocks[index].shock_id) << "\"";
  }
  output << "],"
         << "\"total_steps\":" << summary.total_steps << ','
         << "\"actions\":" << tape.actions.size() << ','
         << "\"trades\":" << summary.trades << ','
         << "\"executed_lots\":" << summary.executed_lots.value() << ','
         << "\"maker_fee_atoms\":" << summary.maker_fees.value() << ','
         << "\"taker_fee_atoms\":" << summary.taker_fees.value() << ','
         << "\"rejected_commands\":" << summary.rejected_commands << ','
         << "\"tape_sha256\":\"" << tape.tape_sha256 << "\","
         << "\"limitations\":["
         << "\"designed synthetic process; not historical evidence\","
         << "\"Step 9 parameters are not calibrated to a venue\","
         << "\"visible-book mechanics omit hidden liquidity\","
         << "\"impact is an explicit synthetic assumption\""
         << "]}";
  return output.str();
}

}  // namespace robust_execution::synthetic
