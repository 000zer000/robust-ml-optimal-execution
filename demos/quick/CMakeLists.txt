cmake_minimum_required(VERSION 3.24)
project(ExecutionQuickTour LANGUAGES CXX)

# Keep the original research build and its frozen evidence unchanged.
set(RE_BUILD_TESTING OFF CACHE BOOL "Build original research tests" FORCE)
set(RE_BUILD_PYTHON_BINDINGS OFF CACHE BOOL "Build Python bindings" FORCE)
add_subdirectory(../.. core EXCLUDE_FROM_ALL)
add_executable(robust_execution_quick_demo ../../cpp/apps/re_quick_demo.cpp)
target_compile_features(robust_execution_quick_demo PRIVATE cxx_std_20)
target_link_libraries(robust_execution_quick_demo PRIVATE robust_execution::core)
re_set_project_warnings(robust_execution_quick_demo ON)
enable_testing()
add_test(NAME quick_demo.hand_tape_accounting COMMAND robust_execution_quick_demo)
