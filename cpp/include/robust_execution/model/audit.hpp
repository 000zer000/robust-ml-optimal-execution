#pragma once

#include <cstdint>
#include <string>
#include <string_view>

#include "robust_execution/model/events.hpp"
#include "robust_execution/model/validation.hpp"

namespace robust_execution::model {

inline constexpr std::string_view kAuditSchemaId =
    "https://robust-execution.local/schemas/event-model/audit-record-v1.schema.json";

class AuditRecord {
 public:
  AuditRecord(
      SchemaVersion schema,
      RunId run_id,
      std::uint64_t append_index,
      std::string previous_record_sha256,
      std::string record_sha256,
      Event event
  );

  [[nodiscard]] const SchemaVersion& schema() const noexcept { return schema_; }
  [[nodiscard]] const RunId& run_id() const noexcept { return run_id_; }
  [[nodiscard]] std::uint64_t append_index() const noexcept { return append_index_; }
  [[nodiscard]] const std::string& previous_record_sha256() const noexcept {
    return previous_record_sha256_;
  }
  [[nodiscard]] const std::string& record_sha256() const noexcept { return record_sha256_; }
  [[nodiscard]] const Event& event() const noexcept { return event_; }

 private:
  SchemaVersion schema_;
  RunId run_id_;
  std::uint64_t append_index_;
  std::string previous_record_sha256_;
  std::string record_sha256_;
  Event event_;
};

[[nodiscard]] bool is_lowercase_sha256(const std::string& value) noexcept;
[[nodiscard]] ValidationIssues validate_audit_record(const AuditRecord& record);

}  // namespace robust_execution::model
