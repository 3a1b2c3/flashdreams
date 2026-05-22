/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "native_primitives.h"

#ifndef OMNIDREAMS_SINGLEVIEW_WITH_CUDA
#error "OmniDreams native primitives require CUDA"
#endif

#include <c10/core/ScalarType.h>

#include <cstdint>
#include <string>

namespace omnidreams_singleview {
namespace {

pybind11::tuple int_array_ref_to_tuple(c10::IntArrayRef values) {
  pybind11::tuple result(values.size());
  for (std::size_t i = 0; i < values.size(); ++i) {
    result[i] = values[i];
  }
  return result;
}

void check_defined(const torch::Tensor& tensor, const char* name) {
  TORCH_CHECK(tensor.defined(), name, " must be defined");
}

void check_cuda_tensor(const torch::Tensor& tensor, const char* name) {
  TORCH_CHECK(tensor.is_cuda(), name, " must be a CUDA tensor");
}

}  // namespace

pybind11::dict native_tensor_descriptor(const torch::Tensor& tensor) {
  check_defined(tensor, "tensor");
  check_cuda_tensor(tensor, "tensor");

  pybind11::dict descriptor;
  descriptor["shape"] = int_array_ref_to_tuple(tensor.sizes());
  descriptor["stride"] = int_array_ref_to_tuple(tensor.strides());
  descriptor["dtype"] = std::string(c10::toString(tensor.scalar_type()));
  descriptor["device"] = tensor.device().str();
  descriptor["is_cuda"] = tensor.is_cuda();
  descriptor["is_contiguous"] = tensor.is_contiguous();
  descriptor["nbytes"] =
      static_cast<int64_t>(tensor.numel()) * static_cast<int64_t>(tensor.element_size());
  return descriptor;
}

torch::Tensor prepare_contiguous(const torch::Tensor& input) {
  check_defined(input, "input");
  check_cuda_tensor(input, "input");

  if (input.is_contiguous()) {
    return input;
  }
  return prepare_contiguous_cuda(input);
}

torch::Tensor zero_workspace_(torch::Tensor workspace) {
  check_defined(workspace, "workspace");
  check_cuda_tensor(workspace, "workspace");
  TORCH_CHECK(
      workspace.is_contiguous(),
      "zero_workspace_ expects a contiguous workspace tensor");

  zero_workspace_cuda(workspace);
  return workspace;
}

void bind_native_primitives(pybind11::module_& module) {
  module.def("native_tensor_descriptor", &native_tensor_descriptor);
  module.def("prepare_contiguous", &prepare_contiguous);
  module.def("zero_workspace_", &zero_workspace_);
}

}  // namespace omnidreams_singleview
