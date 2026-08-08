#include "robust_execution/exchange/exchange.hpp"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace exchange = robust_execution::exchange;
namespace model = robust_execution::model;

namespace {

model::TimestampNs time_ns(std::int64_t value) {
  return model::TimestampNs{model::ClockDomain::Simulation, value};
}

model::InstrumentDefinition instrument() {
  return {
      model::kEventSchemaVersion,
      model::VenueId{"performance"},
      model::InstrumentId{"PERF-USD"},
      "PERF",
      "USD",
      model::RationalIncrement{1U, 100U},
      model::RationalIncrement{1U, 1U},
      model::RationalIncrement{1U, 100U},
      model::QuantityLots{1U},
      model::QuantityLots{1'000'000U},
      "step30-performance-v1",
  };
}

model::OrderSubmit limit_order(
    std::uint64_t client,
    model::Side side,
    model::TimeInForce tif
) {
  const auto base = static_cast<std::int64_t>(client * 4U);
  return {
      model::ParentOrderId{1U},
      model::ClientOrderId{client},
      model::DecisionId{client},
      side,
      model::OrderType::Limit,
      tif,
      model::QuantityLots{1U},
      model::PriceTicks{101},
      false,
      time_ns(base),
      time_ns(base + 1),
      time_ns(base + 2),
  };
}

struct WorkResult {
  std::uint64_t checksum{0U};
  std::uint64_t matches{0U};
};

WorkResult matching_pairs(exchange::MatchingEngine& engine, std::uint64_t pairs) {
  WorkResult result;
  for (std::uint64_t i = 0U; i < pairs; ++i) {
    const auto maker_id = 2U * i + 1U;
    const auto taker_id = maker_id + 1U;
    auto maker = engine.submit(
        limit_order(maker_id, model::Side::Sell, model::TimeInForce::GoodTilCancelled)
    );
    auto taker = engine.submit(
        limit_order(taker_id, model::Side::Buy, model::TimeInForce::ImmediateOrCancel)
    );
    if (!maker.accepted() || !taker.accepted() || taker.matches.size() != 1U) {
      throw std::runtime_error("performance workload matching invariant failed");
    }
    result.matches += taker.matches.size();
    result.checksum += taker.matches.front().match_sequence;
  }
  if (engine.active_order_count() != 0U || !engine.validate_invariants().empty()) {
    throw std::runtime_error("performance workload final engine invariant failed");
  }
  return result;
}

struct TimedResult {
  WorkResult work;
  std::uint64_t elapsed_ns{0U};
};

TimedResult timed_parallel_matching(std::uint64_t total_pairs, std::uint32_t threads) {
  if (threads == 0U || total_pairs < threads) {
    throw std::invalid_argument("threads must be positive and no greater than total pairs");
  }
  std::vector<std::thread> workers;
  std::vector<WorkResult> results(threads);
  std::atomic<std::uint32_t> ready{0U};
  std::atomic<std::uint32_t> done{0U};
  std::atomic<bool> start{false};
  std::atomic<bool> release{false};
  workers.reserve(threads);
  const auto base = total_pairs / threads;
  const auto remainder = total_pairs % threads;
  for (std::uint32_t index = 0U; index < threads; ++index) {
    const auto count = base + (index < remainder ? 1U : 0U);
    workers.emplace_back([&, index, count] {
      auto engine_config = exchange::MatchingEngineConfig{instrument()};
      engine_config.expected_order_count = count * 2U;
      exchange::MatchingEngine engine{std::move(engine_config)};
      ready.fetch_add(1U, std::memory_order_release);
      while (!start.load(std::memory_order_acquire)) std::this_thread::yield();
      results[index] = matching_pairs(engine, count);
      done.fetch_add(1U, std::memory_order_release);
      while (!release.load(std::memory_order_acquire)) std::this_thread::yield();
    });
  }
  while (ready.load(std::memory_order_acquire) != threads) std::this_thread::yield();
  const auto begin = std::chrono::steady_clock::now();
  start.store(true, std::memory_order_release);
  while (done.load(std::memory_order_acquire) != threads) std::this_thread::yield();
  const auto end = std::chrono::steady_clock::now();
  release.store(true, std::memory_order_release);
  for (auto& worker : workers) worker.join();

  TimedResult aggregate;
  aggregate.elapsed_ns = static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(end - begin).count()
  );
  for (const auto& row : results) {
    aggregate.work.matches += row.matches;
    aggregate.work.checksum += row.checksum;
  }
  return aggregate;
}

std::uint64_t parse_u64(const char* text, const char* name) {
  try {
    const auto value = std::stoull(text);
    if (value == 0U) throw std::invalid_argument("zero");
    return value;
  } catch (const std::exception&) {
    throw std::invalid_argument(std::string{name} + " must be a positive integer");
  }
}

}  // namespace

int main(int argc, char** argv) {
  try {
    std::uint64_t pairs = 20'000U;
    std::uint32_t threads = 1U;
    std::uint32_t warmups = 2U;
    std::uint32_t repetitions = 7U;
    for (int i = 1; i < argc; i += 2) {
      if (i + 1 >= argc) throw std::invalid_argument("missing command-line value");
      const std::string key{argv[i]};
      if (key == "--pairs") {
        pairs = parse_u64(argv[i + 1], "pairs");
      } else if (key == "--threads") {
        threads = static_cast<std::uint32_t>(parse_u64(argv[i + 1], "threads"));
      } else if (key == "--warmups") {
        warmups = static_cast<std::uint32_t>(parse_u64(argv[i + 1], "warmups"));
      } else if (key == "--repetitions") {
        repetitions = static_cast<std::uint32_t>(parse_u64(argv[i + 1], "repetitions"));
      } else {
        throw std::invalid_argument("unknown command-line option: " + key);
      }
    }

    for (std::uint32_t i = 0U; i < warmups; ++i) {
      static_cast<void>(timed_parallel_matching(pairs, threads));
    }
    std::cout << "repetition,threads,pairs,operations,elapsed_ns,matches,checksum\n";
    for (std::uint32_t repetition = 0U; repetition < repetitions; ++repetition) {
      const auto result = timed_parallel_matching(pairs, threads);
      std::cout << repetition << ',' << threads << ',' << pairs << ',' << (pairs * 2U) << ','
                << result.elapsed_ns << ',' << result.work.matches << ',' << result.work.checksum
                << '\n';
    }
    return EXIT_SUCCESS;
  } catch (const std::exception& error) {
    std::cerr << "performance benchmark error: " << error.what() << '\n';
    return EXIT_FAILURE;
  }
}
