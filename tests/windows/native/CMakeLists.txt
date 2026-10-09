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
  "${CMAKE_CURRENT_LIST_DIR}/volume_namespace_probe.cpp")
target_include_directories(nt_volume_namespace_probe PRIVATE
  "${DISKED_ROOT}/source/platform/windows/storage"
  "${DISKED_ROOT}/source/providers/windows"
  "${DISKED_ROOT}/source/runtime/command")
target_compile_definitions(nt_volume_namespace_probe PRIVATE _WIN32_WINNT=0x0501 WINVER=0x0501)
target_compile_options(nt_volume_namespace_probe PRIVATE /W4 /WX /utf-8 /permissive- /GS /sdl /guard:cf)
target_link_options(nt_volume_namespace_probe PRIVATE /guard:cf /DYNAMICBASE /NXCOMPAT)
# A modern static CRT build is not an XP qualification. No shipped product link.
