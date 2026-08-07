#include "robust_execution/model/enums.hpp"

#include <cstdlib>

int main() {
  using robust_execution::model::OrderState;
  using robust_execution::model::is_terminal;
  using robust_execution::model::to_string;
  using robust_execution::model::valid_order_state_transition;

  if (!valid_order_state_transition(OrderState::PendingNew, OrderState::Live) ||
      !valid_order_state_transition(OrderState::Live, OrderState::PendingCancel) ||
      !valid_order_state_transition(OrderState::PendingCancel, OrderState::PartiallyFilled) ||
      !valid_order_state_transition(OrderState::PartiallyFilled, OrderState::Filled)) {
    return EXIT_FAILURE;
  }
  if (valid_order_state_transition(OrderState::Filled, OrderState::Live) ||
      valid_order_state_transition(OrderState::Live, OrderState::Live)) {
    return EXIT_FAILURE;
  }
  if (!is_terminal(OrderState::Cancelled) || is_terminal(OrderState::PendingCancel)) {
    return EXIT_FAILURE;
  }
  if (to_string(OrderState::PartiallyFilled) != "partially_filled") {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
