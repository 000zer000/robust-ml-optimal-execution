cmake_minimum_required(VERSION 3.24)

project(
  robust_execution
  VERSION 0.14.0
  DESCRIPTION "Research platform for robust execution policies in limit order books"
  LANGUAGES CXX
)

include(CTest)
include(GNUInstallDirs)
include(CheckIPOSupported)
include(CMakePackageConfigHelpers)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(ProjectOptions)
include(Sanitizers)

option(RE_BUILD_TESTING "Build C++ tests" ${BUILD_TESTING})
option(RE_BUILD_PYTHON_BINDINGS "Build pybind11 extension" OFF)
option(RE_WARNINGS_AS_ERRORS "Treat compiler warnings as errors" ON)
option(RE_ENABLE_IPO "Enable interprocedural optimisation in Release builds" OFF)
option(RE_ENABLE_CLANG_TIDY "Run clang-tidy during compilation" OFF)
option(RE_ENABLE_ASAN "Enable AddressSanitizer" OFF)
option(RE_ENABLE_UBSAN "Enable UndefinedBehaviorSanitizer" OFF)
option(RE_ENABLE_TSAN "Enable ThreadSanitizer" OFF)

if(RE_ENABLE_IPO)
  check_ipo_supported(RESULT re_ipo_supported OUTPUT re_ipo_error)
  if(NOT re_ipo_supported)
    message(FATAL_ERROR "IPO requested but unsupported: ${re_ipo_error}")
  endif()
endif()

add_library(robust_execution_core
  cpp/src/build_info.cpp
  cpp/src/diagnostic_sequence.cpp
  cpp/src/model/events.cpp
  cpp/src/model/validation.cpp
  cpp/src/model/audit.cpp
  cpp/src/exchange/matching_engine.cpp
  cpp/src/exchange/matching_engine_commands.cpp
  cpp/src/exchange/matching_engine_book.cpp
  cpp/src/util/sha256.cpp
  cpp/src/simulation/logical_rng.cpp
  cpp/src/simulation/latency.cpp
  cpp/src/simulation/scheduler.cpp
  cpp/src/simulation/canonical_event.cpp
  cpp/src/simulation/kernel.cpp
  cpp/src/simulation/kernel_exchange.cpp
  cpp/src/policy/accounting.cpp
  cpp/src/policy/action.cpp
  cpp/src/policy/state.cpp
  cpp/src/policy/observation.cpp
  cpp/src/policy/terminal.cpp
  cpp/src/policy/dispatch.cpp
  cpp/src/synthetic/config.cpp
  cpp/src/synthetic/canonical.cpp
  cpp/src/synthetic/generator.cpp
  cpp/src/validation/hand_checks.cpp
  cpp/src/validation/statistical_checks.cpp
  cpp/src/validation/differential_check.cpp
  cpp/src/validation/report.cpp
  cpp/src/historical/replay.cpp
  cpp/src/historical/queue_model.cpp
  cpp/src/metrics/calculator.cpp
  cpp/src/metrics/aggregate.cpp
  cpp/src/metrics/audit.cpp
  cpp/src/metrics/validation.cpp
  cpp/src/strategies/baselines.cpp
  cpp/src/strategies/almgren_chriss.cpp
  cpp/src/strategies/adaptive.cpp
)
add_library(robust_execution::core ALIAS robust_execution_core)

target_compile_features(robust_execution_core PUBLIC cxx_std_20)
target_include_directories(
  robust_execution_core
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/cpp/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)
target_compile_definitions(
  robust_execution_core
  PUBLIC
    ROBUST_EXECUTION_VERSION="${PROJECT_VERSION}"
)
re_set_project_warnings(robust_execution_core ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_core)
set_target_properties(
  robust_execution_core
  PROPERTIES
    EXPORT_NAME core
    CXX_EXTENSIONS OFF
    POSITION_INDEPENDENT_CODE ON
    INTERPROCEDURAL_OPTIMIZATION_RELEASE ${RE_ENABLE_IPO}
)

if(RE_ENABLE_CLANG_TIDY)
  find_program(RE_CLANG_TIDY_EXE NAMES clang-tidy REQUIRED)
  set_target_properties(robust_execution_core PROPERTIES CXX_CLANG_TIDY "${RE_CLANG_TIDY_EXE}")
endif()

add_executable(robust_execution_info cpp/apps/re_info.cpp)
target_link_libraries(robust_execution_info PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_info ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_info)

add_executable(robust_execution_matching_demo cpp/apps/re_matching_demo.cpp)
target_link_libraries(robust_execution_matching_demo PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_matching_demo ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_matching_demo)

add_executable(robust_execution_kernel_demo cpp/apps/re_kernel_demo.cpp)
target_link_libraries(robust_execution_kernel_demo PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_kernel_demo ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_kernel_demo)

add_executable(robust_execution_policy_demo cpp/apps/re_policy_demo.cpp)
target_link_libraries(robust_execution_policy_demo PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_policy_demo ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_policy_demo)

add_executable(robust_execution_synthetic_demo cpp/apps/re_synthetic_demo.cpp)
target_link_libraries(robust_execution_synthetic_demo PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_synthetic_demo ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_synthetic_demo)

add_executable(robust_execution_validation_demo cpp/apps/re_validation_demo.cpp)
target_link_libraries(robust_execution_validation_demo PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_validation_demo ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_validation_demo)

add_executable(robust_execution_historical_demo cpp/apps/re_historical_demo.cpp)
target_link_libraries(robust_execution_historical_demo PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_historical_demo ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_historical_demo)

add_executable(robust_execution_queue_demo cpp/apps/re_queue_demo.cpp)
target_link_libraries(robust_execution_queue_demo PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_queue_demo ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_queue_demo)

add_executable(robust_execution_metrics_demo cpp/apps/re_metrics_demo.cpp)
target_link_libraries(robust_execution_metrics_demo PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_metrics_demo ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_metrics_demo)

add_executable(robust_execution_baseline_demo cpp/apps/re_baseline_demo.cpp)
target_link_libraries(robust_execution_baseline_demo PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_baseline_demo ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_baseline_demo)

add_executable(robust_execution_almgren_chriss_demo cpp/apps/re_almgren_chriss_demo.cpp)
target_link_libraries(robust_execution_almgren_chriss_demo PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_almgren_chriss_demo ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_almgren_chriss_demo)

add_executable(robust_execution_adaptive_demo cpp/apps/re_adaptive_demo.cpp)
target_link_libraries(robust_execution_adaptive_demo PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_adaptive_demo ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_adaptive_demo)

add_executable(robust_execution_ml_mpc_demo cpp/apps/re_ml_mpc_demo.cpp)
target_link_libraries(robust_execution_ml_mpc_demo PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_ml_mpc_demo ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_ml_mpc_demo)

add_executable(robust_execution_imitation_oracle cpp/apps/re_imitation_oracle.cpp)
target_link_libraries(robust_execution_imitation_oracle PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_imitation_oracle ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_imitation_oracle)

add_executable(robust_execution_performance_benchmark cpp/apps/re_performance_benchmark.cpp)
target_link_libraries(robust_execution_performance_benchmark PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_performance_benchmark ${RE_WARNINGS_AS_ERRORS})
re_enable_sanitizers(robust_execution_performance_benchmark)

if(RE_BUILD_PYTHON_BINDINGS)
  find_package(Python 3.11 COMPONENTS Interpreter Development.Module REQUIRED)
  find_package(pybind11 3.0 CONFIG REQUIRED)
  pybind11_add_module(_core MODULE cpp/bindings/module.cpp)
  target_link_libraries(_core PRIVATE robust_execution::core)
  target_compile_features(_core PRIVATE cxx_std_20)
  re_set_project_warnings(_core ${RE_WARNINGS_AS_ERRORS})
  re_enable_sanitizers(_core)
  install(TARGETS _core LIBRARY DESTINATION robust_execution)
endif()

if(RE_BUILD_TESTING)
  add_subdirectory(cpp/tests)
endif()

install(
  TARGETS robust_execution_core robust_execution_info robust_execution_matching_demo robust_execution_kernel_demo robust_execution_policy_demo robust_execution_synthetic_demo robust_execution_validation_demo robust_execution_historical_demo robust_execution_queue_demo robust_execution_metrics_demo robust_execution_baseline_demo robust_execution_almgren_chriss_demo robust_execution_adaptive_demo robust_execution_ml_mpc_demo robust_execution_imitation_oracle robust_execution_performance_benchmark
  EXPORT robust_executionTargets
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(DIRECTORY cpp/include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
configure_package_config_file(
  cmake/robust_executionConfig.cmake.in
  ${CMAKE_CURRENT_BINARY_DIR}/robust_executionConfig.cmake
  INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/robust_execution
)
write_basic_package_version_file(
  ${CMAKE_CURRENT_BINARY_DIR}/robust_executionConfigVersion.cmake
  VERSION ${PROJECT_VERSION}
  COMPATIBILITY SameMajorVersion
)

install(
  EXPORT robust_executionTargets
  FILE robust_executionTargets.cmake
  NAMESPACE robust_execution::
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/robust_execution
)
install(
  FILES
    ${CMAKE_CURRENT_BINARY_DIR}/robust_executionConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/robust_executionConfigVersion.cmake
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/robust_execution
)
