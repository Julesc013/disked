cmake_minimum_required(VERSION 3.27)
project(DiskEdNtVolumeNamespace LANGUAGES CXX)
if(NOT WIN32 OR NOT MSVC)
  message(FATAL_ERROR "Selected Windows MSVC adapter fixture only")
endif()
set(CMAKE_CONFIGURATION_TYPES Release CACHE STRING "" FORCE)
set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
get_filename_component(DISKED_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
add_executable(nt_volume_namespace_probe
  "${DISKED_ROOT}/source/platform/windows/storage/volume_namespace.cpp"
  "${DISKED_ROOT}/source/providers/windows/volume_inventory.cpp"
  "${DISKED_ROOT}/source/runtime/command/json.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/volume_fixture.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/volume_namespace_probe.cpp")
target_include_directories(nt_volume_namespace_probe PRIVATE
  "${DISKED_ROOT}/source/platform/windows/storage"
  "${DISKED_ROOT}/source/providers/windows"
  "${DISKED_ROOT}/source/runtime/command")
target_compile_definitions(nt_volume_namespace_probe PRIVATE _WIN32_WINNT=0x0501 WINVER=0x0501)
target_compile_options(nt_volume_namespace_probe PRIVATE /W4 /WX /utf-8 /permissive- /GS /sdl /guard:cf)
target_link_options(nt_volume_namespace_probe PRIVATE /guard:cf /DYNAMICBASE /NXCOMPAT)
# A modern static CRT build is not an XP qualification. No shipped product link.
add_executable(nt_namespace_worker_probe
  "${DISKED_ROOT}/source/platform/windows/storage/namespace_worker.cpp"
  "${DISKED_ROOT}/source/platform/windows/storage/volume_namespace.cpp"
  "${DISKED_ROOT}/source/providers/windows/volume_inventory.cpp"
  "${DISKED_ROOT}/source/providers/image/local_file.cpp"
  "${DISKED_ROOT}/source/portable/hash/sha256.cpp"
  "${DISKED_ROOT}/source/runtime/command/json.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/volume_fixture.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/namespace_worker_probe.cpp")
target_include_directories(nt_namespace_worker_probe PRIVATE
  "${DISKED_ROOT}/source/platform/windows/storage"
  "${DISKED_ROOT}/source/platform/windows"
  "${DISKED_ROOT}/source/providers/windows"
  "${DISKED_ROOT}/source/providers/image"
  "${DISKED_ROOT}/source/portable/hash"
  "${DISKED_ROOT}/source/runtime/command")
target_compile_definitions(nt_namespace_worker_probe PRIVATE _WIN32_WINNT=0x0A00 WINVER=0x0A00 DISKED_NT_NAMESPACE_WORKER_TESTING=1)
target_compile_options(nt_namespace_worker_probe PRIVATE /W4 /WX /utf-8 /permissive- /GS /sdl /guard:cf)
target_link_options(nt_namespace_worker_probe PRIVATE /guard:cf /DYNAMICBASE /NXCOMPAT)

# Private capture publication/retirement qualification with the owned injected
# reader. Empty graph projection only; no native product/provider admission.
add_executable(nt_capture_lifecycle_probe
  "${DISKED_ROOT}/source/platform/windows/storage/namespace_worker.cpp"
  "${DISKED_ROOT}/source/platform/windows/storage/volume_namespace.cpp"
  "${DISKED_ROOT}/source/providers/windows/volume_inventory.cpp"
  "${DISKED_ROOT}/source/providers/image/local_file.cpp"
  "${DISKED_ROOT}/source/portable/hash/sha256.cpp"
  "${DISKED_ROOT}/source/runtime/command/json.cpp"
  "${DISKED_ROOT}/source/runtime/graph/snapshot.cpp"
  "${DISKED_ROOT}/source/runtime/graph/capture.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/volume_fixture.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/capture_lifecycle_probe.cpp")
target_include_directories(nt_capture_lifecycle_probe PRIVATE
  "${DISKED_ROOT}/source/platform/windows/storage"
  "${DISKED_ROOT}/source/platform/windows"
  "${DISKED_ROOT}/source/providers/windows"
  "${DISKED_ROOT}/source/providers/image"
  "${DISKED_ROOT}/source/portable/hash"
  "${DISKED_ROOT}/source/runtime/command"
  "${DISKED_ROOT}/source/runtime/graph")
target_compile_definitions(nt_capture_lifecycle_probe PRIVATE _WIN32_WINNT=0x0A00 WINVER=0x0A00 DISKED_NT_NAMESPACE_WORKER_TESTING=1)
target_compile_options(nt_capture_lifecycle_probe PRIVATE /W4 /WX /utf-8 /permissive- /GS /sdl /guard:cf)
target_link_options(nt_capture_lifecycle_probe PRIVATE /guard:cf /DYNAMICBASE /NXCOMPAT)

# Same common graph, with a private observation profile and owned injected reader.
add_executable(nt_namespace_graph_probe
  "${DISKED_ROOT}/source/platform/windows/storage/namespace_worker.cpp"
  "${DISKED_ROOT}/source/platform/windows/storage/volume_namespace.cpp"
  "${DISKED_ROOT}/source/providers/windows/volume_inventory.cpp"
  "${DISKED_ROOT}/source/providers/windows/namespace_graph.cpp"
  "${DISKED_ROOT}/source/providers/image/local_file.cpp"
  "${DISKED_ROOT}/source/portable/hash/sha256.cpp"
  "${DISKED_ROOT}/source/runtime/command/json.cpp"
  "${DISKED_ROOT}/source/runtime/graph/snapshot.cpp"
  "${DISKED_ROOT}/source/runtime/graph/capture.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/volume_fixture.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/namespace_graph_probe.cpp")
target_include_directories(nt_namespace_graph_probe PRIVATE
  "${DISKED_ROOT}/source/platform/windows/storage"
  "${DISKED_ROOT}/source/platform/windows"
  "${DISKED_ROOT}/source/providers/windows"
  "${DISKED_ROOT}/source/providers/image"
  "${DISKED_ROOT}/source/portable/hash"
  "${DISKED_ROOT}/source/runtime/command"
  "${DISKED_ROOT}/source/runtime/graph")
target_compile_definitions(nt_namespace_graph_probe PRIVATE _WIN32_WINNT=0x0A00 WINVER=0x0A00 DISKED_NT_NAMESPACE_WORKER_TESTING=1)
target_compile_options(nt_namespace_graph_probe PRIVATE /W4 /WX /utf-8 /permissive- /GS /sdl /guard:cf)
target_link_options(nt_namespace_graph_probe PRIVATE /guard:cf /DYNAMICBASE /NXCOMPAT)

add_executable(nt_storage_query_probe
  "${DISKED_ROOT}/source/platform/windows/storage/storage_queries.cpp"
  "${DISKED_ROOT}/source/providers/windows/storage_inventory.cpp"
  "${DISKED_ROOT}/source/providers/windows/volume_inventory.cpp"
  "${DISKED_ROOT}/source/platform/windows/storage/volume_namespace.cpp"
  "${DISKED_ROOT}/source/runtime/command/json.cpp"
  "${DISKED_ROOT}/source/runtime/graph/snapshot.cpp"
  "${DISKED_ROOT}/source/portable/hash/sha256.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/storage_query_probe.cpp")
target_include_directories(nt_storage_query_probe PRIVATE
  "${DISKED_ROOT}/source/platform/windows/storage"
  "${DISKED_ROOT}/source/providers/windows"
  "${DISKED_ROOT}/source/runtime/command"
  "${DISKED_ROOT}/source/runtime/graph"
  "${DISKED_ROOT}/source/portable/hash")
target_compile_definitions(nt_storage_query_probe PRIVATE _WIN32_WINNT=0x0501 WINVER=0x0501)
target_compile_options(nt_storage_query_probe PRIVATE /W4 /WX /utf-8 /permissive- /GS /sdl /guard:cf)
target_link_options(nt_storage_query_probe PRIVATE /guard:cf /DYNAMICBASE /NXCOMPAT)
