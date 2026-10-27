cmake_minimum_required(VERSION 3.18)
include(${CMAKE_CURRENT_LIST_DIR}/cmake/Compatibility.cmake)
project(vmweave_shm LANGUAGES C)
add_subdirectory(shm-queue queue)
add_library(vmweave_mapping STATIC src/mapping.c)
target_compile_features(vmweave_mapping PUBLIC c_std_11)
target_include_directories(vmweave_mapping PUBLIC include)
target_link_libraries(vmweave_mapping PUBLIC vmweave_shm_queue)
set_target_properties(vmweave_mapping PROPERTIES POSITION_INDEPENDENT_CODE ON)
set(VMWEAVE_BUILD_CUDA_RUNTIME ON CACHE BOOL "Worker requires CUDA runtime backend")
add_subdirectory(cuda-dispatch exec)
find_package(CUDAToolkit 12.8 REQUIRED)
add_library(vmweave_dispatch STATIC src/dispatch.c)
target_include_directories(vmweave_dispatch PUBLIC include)
target_link_libraries(vmweave_dispatch PUBLIC vmweave_cuda_exec vmweave_mapping CUDA::cudart)
add_executable(vmweave-shm-worker src/worker.c)
add_library(vmweave_async STATIC src/async.c src/torch.c)
target_link_libraries(vmweave_async PUBLIC vmweave_dispatch CUDA::cudart CUDA::cuda_driver)
find_library(VMWEAVE_CUDNN cudnn REQUIRED)
add_library(vmweave_compat STATIC src/compat.c)
target_link_libraries(vmweave_compat PUBLIC vmweave_async CUDA::cublas ${VMWEAVE_CUDNN})
target_link_libraries(vmweave-shm-worker PRIVATE vmweave_dispatch vmweave_cuda_runtime vmweave_async vmweave_compat)
add_library(vmweave_guest SHARED src/owner.c src/broker_client.c src/guest.c src/guest_async.c src/guest_compat.c src/guest_torch.c)
target_include_directories(vmweave_guest PRIVATE ${CUDAToolkit_INCLUDE_DIRS} cuda-dispatch/include)
target_link_libraries(vmweave_guest PRIVATE vmweave_mapping)
install(TARGETS vmweave-shm-worker vmweave_guest RUNTIME DESTINATION bin LIBRARY DESTINATION lib)

add_executable(vmweave-shm-session-worker src/worker_sessions.c src/session_ipc.c)
target_link_libraries(vmweave-shm-session-worker PRIVATE vmweave_dispatch vmweave_cuda_runtime vmweave_async vmweave_compat)
install(TARGETS vmweave-shm-session-worker RUNTIME DESTINATION bin)

vmweave_legacy_target(vmweave_mapping flyt_mapping)

vmweave_legacy_target(vmweave_dispatch flyt_dispatch)

vmweave_legacy_target(vmweave-shm-worker flyt-shm-worker)

vmweave_legacy_target(vmweave_async flyt_async)

vmweave_legacy_target(vmweave_compat flyt_compat)

vmweave_legacy_target(vmweave_guest flyt_guest)

vmweave_legacy_target(vmweave-shm-session-worker flyt-shm-session-worker)
