cmake_minimum_required(VERSION 3.27)
project(NamespaceWordBounds LANGUAGES C CXX)
set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)
if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL EXPECTED_POINTER_BYTES
   OR NOT CMAKE_CXX_COMPILER_VERSION VERSION_EQUAL "19.44.35228.0"
   OR NOT CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION STREQUAL "10.0.19041.0")
  message(FATAL_ERROR "Pinned compiler/SDK required")
endif()
add_executable(exfat_namespace_probe
  "D:/Projects/DiskEd/disked/.aide-local/namespace-word-bounds-corrected/source/source/portable/exfat/allocation.c"
  "D:/Projects/DiskEd/disked/.aide-local/namespace-word-bounds-corrected/source/source/portable/exfat/boot.c"
  "D:/Projects/DiskEd/disked/.aide-local/namespace-word-bounds-corrected/source/source/portable/exfat/directory.c"
  "D:/Projects/DiskEd/disked/.aide-local/namespace-word-bounds-corrected/source/source/portable/exfat/upcase.c"
  "D:/Projects/DiskEd/disked/.aide-local/namespace-word-bounds-corrected/source/source/portable/hash/sha256.cpp"
  "D:/Projects/DiskEd/disked/.aide-local/namespace-word-bounds-corrected/source/source/portable/primitives/checked.c"
  "D:/Projects/DiskEd/disked/.aide-local/namespace-word-bounds-corrected/source/source/portable/primitives/extent.c"
  "D:/Projects/DiskEd/disked/.aide-local/namespace-word-bounds-corrected/source/source/portable/primitives/view.c"
  "D:/Projects/DiskEd/disked/.aide-local/namespace-word-bounds-corrected/source/source/runtime/capture/exfat_namespace.cpp"
  "D:/Projects/DiskEd/disked/.aide-local/namespace-word-bounds-corrected/source/source/runtime/capture/exfat_upcase.cpp"
  "D:/Projects/DiskEd/disked/.aide-local/namespace-word-bounds-corrected/source/source/runtime/command/json.cpp"
  "D:/Projects/DiskEd/disked/.aide-local/namespace-word-bounds-corrected/source/tests/unit/exfat_namespace_probe.cpp"
  exfat_upcase.cpp
  exfat_namespace.cpp)
target_include_directories(exfat_namespace_probe PRIVATE "D:/Projects/DiskEd/disked/.aide-local/namespace-word-bounds-corrected/source/source")
set_target_properties(exfat_namespace_probe PROPERTIES C_STANDARD 90 C_STANDARD_REQUIRED YES C_EXTENSIONS NO
  CXX_STANDARD 14 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)
target_compile_options(exfat_namespace_probe PRIVATE /W4 /WX /GS /sdl /guard:cf
  "$<$<COMPILE_LANGUAGE:CXX>:/permissive-;/utf-8>")
target_link_options(exfat_namespace_probe PRIVATE /guard:cf /DYNAMICBASE /NXCOMPAT)
