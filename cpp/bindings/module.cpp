#include "robust_execution/build_info.hpp"
#include "robust_execution/diagnostic_sequence.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

PYBIND11_MODULE(_core, module) {
  module.doc() = "C++ core bindings for the robust-execution research platform";
  module.def("build_info_json", &robust_execution::build_info_json);
  module.def("diagnostic_sequence", &robust_execution::diagnostic_sequence);
}
