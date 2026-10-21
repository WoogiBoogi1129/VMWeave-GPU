cmake_minimum_required(VERSION 3.18)
include(${CMAKE_CURRENT_LIST_DIR}/../cmake/Compatibility.cmake)
project(vmweave_cuda_dispatch LANGUAGES C)

# Explicit opt-in only. No generated RPC files, rpcgen, XDR, or libtirpc.
# The execution core can be built without the optional CUDA backend.
find_package(Threads REQUIRED)
add_library(vmweave_cuda_exec STATIC src/exec.c)
target_compile_features(vmweave_cuda_exec PUBLIC c_std_11)
target_include_directories(vmweave_cuda_exec PUBLIC
    "${CMAKE_CURRENT_SOURCE_DIR}/include"
    "${CMAKE_CURRENT_SOURCE_DIR}/../shm-contract/include")
target_link_libraries(vmweave_cuda_exec PUBLIC Threads::Threads)
set_target_properties(vmweave_cuda_exec PROPERTIES POSITION_INDEPENDENT_CODE ON)

option(VMWEAVE_BUILD_CUDA_RUNTIME "Build the real CUDA backend (no GPU execution)" OFF)
if(VMWEAVE_BUILD_CUDA_RUNTIME)
    find_package(CUDAToolkit 12.8 REQUIRED)
    add_library(vmweave_cuda_runtime STATIC src/runtime.c)
    target_compile_features(vmweave_cuda_runtime PUBLIC c_std_11)
    # Shared cudart is intentional: future Worker must preserve HAMi interception.
    target_link_libraries(vmweave_cuda_runtime PUBLIC vmweave_cuda_exec CUDA::cudart)
    set_target_properties(vmweave_cuda_runtime PROPERTIES POSITION_INDEPENDENT_CODE ON)
vmweave_legacy_target(vmweave_cuda_runtime flyt_cuda_runtime)
endif()

vmweave_legacy_target(vmweave_cuda_exec flyt_cuda_exec)
