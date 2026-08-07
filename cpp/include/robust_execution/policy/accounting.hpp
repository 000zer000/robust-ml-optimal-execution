#pragma once

#include <optional>
#include <string>

#include "robust_execution/policy/types.hpp"

namespace robust_execution::policy {

struct AccountingError {
  std::string detail;
};

[[nodiscard]] std::optional<model::QuoteAtoms> exact_quote_notional(
    const model::InstrumentDefinition& instrument,
    model::PriceTicks price,
    model::QuantityLots quantity,
    AccountingError* error = nullptr
) noexcept;

[[nodiscard]] std::optional<model::QuoteAtoms> signed_cash_effect(
    const model::InstrumentDefinition& instrument,
    model::Side side,
    model::PriceTicks price,
    model::QuantityLots quantity,
    AccountingError* error = nullptr
) noexcept;

}  // namespace robust_execution::policy
