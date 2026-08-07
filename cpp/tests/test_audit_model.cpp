#include "robust_execution/model/model.hpp"

#include <cstdlib>
#include <string>

int main() {
  namespace model = robust_execution::model;
  const model::RunId run_id{"run-1"};
  const model::Event event{
      model::EventHeader{
          model::kEventSchemaVersion,
          model::EventId{1U},
          run_id,
          model::VenueId{"synthetic"},
          model::InstrumentId{"TEST-USD"},
          model::SourceChannelId{"timer"},
          model::EventOrigin::System,
          model::TimestampNs{model::ClockDomain::Simulation, 0},
          model::TimestampNs{model::ClockDomain::Simulation, 0},
          model::TimestampNs{model::ClockDomain::Simulation, 0},
          model::EventOrdering{false, 0U, 0U, 1U, 2U},
          std::nullopt,
      },
      model::Timer{"decision-grid", 0U},
  };
  const std::string zero_hash(64U, '0');
  const std::string one_hash(64U, 'a');
  const model::AuditRecord record{
      model::kEventSchemaVersion,
      run_id,
      0U,
      zero_hash,
      one_hash,
      event,
  };
  if (model::has_errors(model::validate_audit_record(record)) ||
      !model::is_lowercase_sha256(one_hash) || model::is_lowercase_sha256("ABC")) {
    return EXIT_FAILURE;
  }
  const model::AuditRecord bad_record{
      model::kEventSchemaVersion,
      model::RunId{"other-run"},
      0U,
      one_hash,
      "invalid",
      event,
  };
  if (!model::has_errors(model::validate_audit_record(bad_record))) {
    return EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
