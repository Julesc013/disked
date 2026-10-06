cmake_minimum_required(VERSION 3.27)
project(DiskEdBootstrap VERSION 0.1.0 LANGUAGES CXX)

# This lane is deliberately narrow. Other targets need their own evidence.
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/spec/catalog/native-bootstrap.json" bootstrap)
foreach(key compiler_version sdk toolset)
  string(JSON expected_${key} GET "${bootstrap}" ${key})
endforeach()
set(toolset_path "${CMAKE_CXX_COMPILER}")
foreach(level RANGE 1 4)
  get_filename_component(toolset_path "${toolset_path}" DIRECTORY)
endforeach()
get_filename_component(actual_toolset "${toolset_path}" NAME)
if(NOT WIN32 OR NOT CMAKE_CXX_COMPILER_ID STREQUAL "MSVC" OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8
   OR NOT CMAKE_VS_PLATFORM_NAME STREQUAL "x64"
   OR NOT CMAKE_CXX_COMPILER_VERSION VERSION_EQUAL expected_compiler_version
   OR NOT CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION STREQUAL expected_sdk
   OR NOT actual_toolset STREQUAL expected_toolset)
  message(FATAL_ERROR "Use the pinned windows-bootstrap preset/toolchain. Observed: Windows=${WIN32}; MSVC=${MSVC}; pointer=${CMAKE_SIZEOF_VOID_P}; platform=${CMAKE_VS_PLATFORM_NAME}; compiler=${CMAKE_CXX_COMPILER_VERSION}; SDK=${CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION}; toolset=${actual_toolset}")
endif()
set(CMAKE_CONFIGURATION_TYPES "Release" CACHE STRING "Bootstrap qualification configuration" FORCE)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded")
find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)
find_package(Git REQUIRED)
add_library(disked_json STATIC source/runtime/command/json.cpp source/runtime/command/command.cpp source/runtime/command/protocol.cpp source/runtime/invocation/policy.cpp)
target_include_directories(disked_json PUBLIC source/runtime/command source/runtime/invocation)
set_target_properties(disked_json PROPERTIES CXX_STANDARD 14 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)
target_compile_options(disked_json PRIVATE /W4 /WX /permissive- /utf-8 /GS /sdl /guard:cf)

set(generated "${CMAKE_CURRENT_BINARY_DIR}/generated")
add_custom_target(bootstrap_registry ALL
  COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/build-bootstrap.py"
    --root "${CMAKE_CURRENT_SOURCE_DIR}" --output "${generated}"
    --git "${GIT_EXECUTABLE}" --compiler "${CMAKE_CXX_COMPILER}"
    --compiler-version "${CMAKE_CXX_COMPILER_VERSION}"
    --sdk "${CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION}" --configuration "$<CONFIG>"
    --compile-flags "${CMAKE_CXX_FLAGS} ${CMAKE_CXX_FLAGS_RELEASE}"
    --link-flags "${CMAKE_EXE_LINKER_FLAGS} ${CMAKE_EXE_LINKER_FLAGS_RELEASE}"
    --cmake-version "${CMAKE_VERSION}" --generator "${CMAKE_GENERATOR}"
  BYPRODUCTS "${generated}/bootstrap_registry.h" "${generated}/build-identity.json"
  COMMENT "Bind current Git revision and native input bytes" VERBATIM)

function(bootstrap_executable target)
  add_executable(${target} source/apps/disked/main.cpp source/apps/disked/cli.cpp source/apps/disked/command_registry.cpp
    source/apps/disked/disked.manifest source/providers/fake/bootstrap.cpp
    source/platform/windows/entry.cpp source/platform/windows/invocation.cpp)
  add_dependencies(${target} bootstrap_registry)
  target_include_directories(${target} PRIVATE "${generated}" source/providers/fake source/platform/windows source/apps/disked)
  target_link_libraries(${target} PRIVATE disked_json)
  set_target_properties(${target} PROPERTIES CXX_STANDARD 14 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)
  target_compile_options(${target} PRIVATE /W4 /WX /permissive- /utf-8 /GS /sdl /guard:cf)
  target_link_options(${target} PRIVATE /SUBSYSTEM:CONSOLE,10.00 /DYNAMICBASE /NXCOMPAT /HIGHENTROPYVA /guard:cf)
endfunction()
bootstrap_executable(disked)

include(CTest)
if(BUILD_TESTING)
  add_executable(invocation_policy_probe tests/invocation/policy_probe.cpp)
  target_link_libraries(invocation_policy_probe PRIVATE disked_json)
  add_test(NAME invocation.policy COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/invocation/test_policy.py" --exe "$<TARGET_FILE:invocation_policy_probe>" --root "${CMAKE_CURRENT_SOURCE_DIR}")
  set_tests_properties(invocation.policy PROPERTIES TIMEOUT 120)
  add_executable(protocol_reader_probe tests/contracts/reader_probe.cpp)
  target_link_libraries(protocol_reader_probe PRIVATE disked_json)
  add_test(NAME protocol.compatible_reader COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/contracts/test_reader.py" --exe "$<TARGET_FILE:protocol_reader_probe>")
  set_tests_properties(protocol.compatible_reader PROPERTIES TIMEOUT 120)
  add_executable(command_parser_probe tests/contracts/parser_probe.cpp source/apps/disked/command_registry.cpp)
  add_dependencies(command_parser_probe bootstrap_registry)
  target_include_directories(command_parser_probe PRIVATE "${generated}" source/apps/disked)
  target_link_libraries(command_parser_probe PRIVATE disked_json)
  add_test(NAME command.syntax COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/contracts/test_parser.py" --exe "$<TARGET_FILE:command_parser_probe>" --root "${CMAKE_CURRENT_SOURCE_DIR}")
  set_tests_properties(command.syntax PROPERTIES TIMEOUT 120)
  add_executable(json_codec_probe tests/contracts/codec_probe.cpp)
  target_link_libraries(json_codec_probe PRIVATE disked_json)
  add_test(NAME protocol.json_codec COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/contracts/test_json.py" --exe "$<TARGET_FILE:json_codec_probe>")
  set_tests_properties(protocol.json_codec PROPERTIES TIMEOUT 120)
  bootstrap_executable(disked_provider_guard)
  target_compile_definitions(disked_provider_guard PRIVATE DISKED_POISON_PROVIDER=1)
  foreach(target disked disked_provider_guard)
    add_test(NAME ${target}.invocation COMMAND "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/tests/invocation/test_windows.py" --exe "$<TARGET_FILE:${target}>" --root "${CMAKE_CURRENT_SOURCE_DIR}")
    set_tests_properties(${target}.invocation PROPERTIES TIMEOUT 120)
    add_test(NAME ${target}.acceptance
      COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/native/test_protocol.py"
        --exe "$<TARGET_FILE:${target}>" --root "${CMAKE_CURRENT_SOURCE_DIR}"
        --identity "${generated}/build-identity.json")
    set_tests_properties(${target}.acceptance PROPERTIES TIMEOUT 120)
  endforeach()
  add_executable(provider_guard_probe tests/native/provider_guard_probe.cpp source/providers/fake/bootstrap.cpp)
  add_dependencies(provider_guard_probe bootstrap_registry)
  target_include_directories(provider_guard_probe PRIVATE "${generated}" source/providers/fake)
  target_compile_definitions(provider_guard_probe PRIVATE DISKED_POISON_PROVIDER=1)
  add_test(NAME provider_guard.positive_control COMMAND "${Python3_EXECUTABLE}"
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/native/test_provider_guard.py" "$<TARGET_FILE:provider_guard_probe>")
  set_tests_properties(provider_guard.positive_control PROPERTIES TIMEOUT 15)
endif()
