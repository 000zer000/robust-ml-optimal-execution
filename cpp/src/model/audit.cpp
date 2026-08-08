#include "robust_execution/model/audit.hpp"

#include <algorithm>
#include <cctype>
#include <utility>

namespace robust_execution::model {

AuditRecord::AuditRecord(
    SchemaVersion schema,
    RunId run_id,
    std::uint64_t append_index,
    std::string previous_record_sha256,
    std::string record_sha256,
    Event event
)
    : schema_(schema),
      run_id_(std::move(run_id)),
      append_index_(append_index),
      previous_record_sha256_(std::move(previous_record_sha256)),
      record_sha256_(std::move(record_sha256)),
      event_(std::move(event)) {}

bool is_lowercase_sha256(const std::string& value) noexcept {
  return value.size() == 64U &&
         std::all_of(value.begin(), value.end(), [](char character) {
           const auto unsigned_character = static_cast<unsigned char>(character);
           return std::isdigit(unsigned_character) != 0 ||
                  (character >= 'a' && character <= 'f');
         });
}

ValidationIssues validate_audit_record(const AuditRecord& record) {
  ValidationIssues issues = validate_event(record.event());
  if (record.schema().major != kEventSchemaVersion.major) {
    issues.push_back(
        ValidationIssue{Severity::Error, "audit.schema.major", "unsupported audit schema major"}
    );
  }
  if (!record.run_id().valid()) {
    issues.push_back(ValidationIssue{Severity::Error, "audit.run_id", "run_id is empty"});
  }
  if (record.run_id() != record.event().header.run_id) {
    issues.push_back(
        ValidationIssue{Severity::Error, "audit.run_mismatch", "audit and event run_id differ"}
    );
  }
  if (!is_lowercase_sha256(record.previous_record_sha256())) {
    issues.push_back(ValidationIssue{
        Severity::Error,
        "audit.previous_hash",
        "previous_record_sha256 must be 64 lowercase hexadecimal characters"
    });
  }
  if (!is_lowercase_sha256(record.record_sha256())) {
    issues.push_back(ValidationIssue{
        Severity::Error,
        "audit.record_hash",
        "record_sha256 must be 64 lowercase hexadecimal characters"
    });
  }
  if (record.append_index() == 0U &&
      record.previous_record_sha256() != std::string(64U, '0')) {
    issues.push_back(ValidationIssue{
        Severity::Error,
        "audit.genesis_hash",
        "first audit record must use the all-zero previous hash"
    });
  }
  return issues;
}

}  // namespace robust_execution::model
