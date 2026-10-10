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
  "${DISKED_ROOT}/source/platform/windows/storage/observation_worker.cpp"
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
  "${DISKED_ROOT}/source/platform/windows/storage/observation_worker.cpp"
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
  "${DISKED_ROOT}/source/platform/windows/storage/observation_worker.cpp"
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
  "${DISKED_ROOT}/source/platform/windows/storage/identity_queries.cpp"
  "${DISKED_ROOT}/source/platform/windows/storage/storage_queries.cpp"
  "${DISKED_ROOT}/source/providers/windows/storage_inventory.cpp"
  "${DISKED_ROOT}/source/providers/windows/volume_inventory.cpp"
  "${DISKED_ROOT}/source/platform/windows/storage/volume_namespace.cpp"
  "${DISKED_ROOT}/source/runtime/command/json.cpp"
  "${DISKED_ROOT}/source/runtime/graph/snapshot.cpp"
  "${DISKED_ROOT}/source/portable/hash/sha256.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/storage_fixture.cpp"
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

get_target_property(identity_query_sources nt_storage_query_probe SOURCES)
list(FILTER identity_query_sources EXCLUDE REGEX "storage_query_probe\\.cpp$")
add_executable(nt_identity_query_probe ${identity_query_sources}
  "${CMAKE_CURRENT_LIST_DIR}/identity_query_probe.cpp")
get_target_property(identity_query_includes nt_storage_query_probe INCLUDE_DIRECTORIES)
target_include_directories(nt_identity_query_probe PRIVATE ${identity_query_includes})
target_compile_definitions(nt_identity_query_probe PRIVATE _WIN32_WINNT=0x0501 WINVER=0x0501)
target_compile_options(nt_identity_query_probe PRIVATE /W4 /WX /utf-8 /permissive- /GS /sdl /guard:cf)
target_link_options(nt_identity_query_probe PRIVATE /guard:cf /DYNAMICBASE /NXCOMPAT)

add_executable(nt_storage_worker_probe
  "${DISKED_ROOT}/source/platform/windows/storage/identity_queries.cpp"
  "${DISKED_ROOT}/source/platform/windows/storage/observation_worker.cpp"
  "${DISKED_ROOT}/source/platform/windows/storage/namespace_worker.cpp"
  "${DISKED_ROOT}/source/platform/windows/storage/storage_worker.cpp"
  "${DISKED_ROOT}/source/platform/windows/storage/storage_queries.cpp"
  "${DISKED_ROOT}/source/platform/windows/storage/volume_namespace.cpp"
  "${DISKED_ROOT}/source/providers/windows/storage_inventory.cpp"
  "${DISKED_ROOT}/source/providers/windows/storage_frame_reader.cpp"
  "${DISKED_ROOT}/source/providers/windows/storage_graph.cpp"
  "${DISKED_ROOT}/source/providers/windows/volume_inventory.cpp"
  "${DISKED_ROOT}/source/providers/windows/namespace_graph.cpp"
  "${DISKED_ROOT}/source/providers/image/local_file.cpp"
  "${DISKED_ROOT}/source/runtime/command/json.cpp"
  "${DISKED_ROOT}/source/runtime/graph/snapshot.cpp"
  "${DISKED_ROOT}/source/runtime/graph/capture.cpp"
  "${DISKED_ROOT}/source/portable/hash/sha256.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/storage_fixture.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/volume_fixture.cpp"
  "${CMAKE_CURRENT_LIST_DIR}/storage_worker_probe.cpp")
target_include_directories(nt_storage_worker_probe PRIVATE
  "${DISKED_ROOT}/source/platform/windows/storage"
  "${DISKED_ROOT}/source/platform/windows"
  "${DISKED_ROOT}/source/providers/windows"
  "${DISKED_ROOT}/source/providers/image"
  "${DISKED_ROOT}/source/runtime/command"
  "${DISKED_ROOT}/source/runtime/graph"
  "${DISKED_ROOT}/source/portable/hash")
target_compile_definitions(nt_storage_worker_probe PRIVATE _WIN32_WINNT=0x0A00 WINVER=0x0A00 DISKED_NT_OBSERVATION_WORKER_TESTING=1)
target_compile_options(nt_storage_worker_probe PRIVATE /W4 /WX /utf-8 /permissive- /GS /sdl /guard:cf)
target_link_options(nt_storage_worker_probe PRIVATE /guard:cf /DYNAMICBASE /NXCOMPAT)

get_target_property(identity_frame_sources nt_storage_worker_probe SOURCES)
add_executable(nt_identity_frame_probe ${identity_frame_sources})
get_target_property(identity_frame_includes nt_storage_worker_probe INCLUDE_DIRECTORIES)
target_include_directories(nt_identity_frame_probe PRIVATE ${identity_frame_includes})
target_compile_definitions(nt_identity_frame_probe PRIVATE _WIN32_WINNT=0x0A00 WINVER=0x0A00 DISKED_NT_OBSERVATION_WORKER_TESTING=1 DISKED_NT_IDENTITY_FRAME_TESTING=1)
target_compile_options(nt_identity_frame_probe PRIVATE /W4 /WX /utf-8 /permissive- /GS /sdl /guard:cf)
target_link_options(nt_identity_frame_probe PRIVATE /guard:cf /DYNAMICBASE /NXCOMPAT)

add_executable(nt_observation_frontend_probe
  "${CMAKE_CURRENT_LIST_DIR}/observation_frontend_probe.cpp"
  "${DISKED_ROOT}/source/platform/windows/memory_budget.cpp"
  "${DISKED_ROOT}/source/runtime/presentation/session.cpp"
  "${DISKED_ROOT}/source/runtime/presentation/requests.cpp"
  "${DISKED_ROOT}/source/runtime/command/command.cpp"
  "${DISKED_ROOT}/source/runtime/command/protocol.cpp"
  "${DISKED_ROOT}/source/runtime/command/shell_lexer.cpp"
  "${DISKED_ROOT}/source/apps/disked/tui/tui_model.cpp"
  "${DISKED_ROOT}/source/apps/disked/gui/gui_model.cpp"
  "${DISKED_ROOT}/source/apps/disked/shell/shell_model.cpp")
get_target_property(observation_shared_sources nt_storage_worker_probe SOURCES)
list(FILTER observation_shared_sources EXCLUDE REGEX "storage_worker_probe[.]cpp$")
target_sources(nt_observation_frontend_probe PRIVATE ${observation_shared_sources})
get_target_property(observation_shared_includes nt_storage_worker_probe INCLUDE_DIRECTORIES)
target_include_directories(nt_observation_frontend_probe PRIVATE ${observation_shared_includes}
  "${DISKED_ROOT}/source/runtime/presentation"
  "${DISKED_ROOT}/source/apps/disked/tui"
  "${DISKED_ROOT}/source/apps/disked/gui"
  "${DISKED_ROOT}/source/apps/disked/shell")
target_compile_definitions(nt_observation_frontend_probe PRIVATE _WIN32_WINNT=0x0A00 WINVER=0x0A00 DISKED_NT_OBSERVATION_WORKER_TESTING=1)
target_compile_options(nt_observation_frontend_probe PRIVATE /W4 /WX /utf-8 /permissive- /GS /sdl /guard:cf)
target_link_options(nt_observation_frontend_probe PRIVATE /guard:cf /DYNAMICBASE /NXCOMPAT)
