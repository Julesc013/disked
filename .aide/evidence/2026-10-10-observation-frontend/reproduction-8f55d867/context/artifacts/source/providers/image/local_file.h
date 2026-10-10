#pragma once
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include "json.h"
#include <cstdint>
#include <string>
#include <vector>

namespace disked { namespace local_file {
struct Error : std::runtime_error {
    DWORD platform_code;
    Error(const char* code,DWORD platform=0):std::runtime_error(code),platform_code(platform) {}
};
class Handle {
public:
    HANDLE value=INVALID_HANDLE_VALUE;
    explicit Handle(HANDLE h=INVALID_HANDLE_VALUE):value(h) {}
    ~Handle() {if(value!=INVALID_HANDLE_VALUE)CloseHandle(value);}
    Handle(const Handle&)=delete;Handle& operator=(const Handle&)=delete;
    Handle(Handle&& h) noexcept:value(h.value) {h.value=INVALID_HANDLE_VALUE;}
    Handle& operator=(Handle&& h) noexcept {
        if(this!=&h) {if(value!=INVALID_HANDLE_VALUE)CloseHandle(value);value=h.value;h.value=INVALID_HANDLE_VALUE;}return *this;
    }
};
struct Metadata {json::Value value;std::uint64_t size=0;};
std::wstring path_for(const std::string& input);
std::string utf8(const std::wstring& input);
BY_HANDLE_FILE_INFORMATION ordinary(HANDLE,bool directory);
void bind_path(HANDLE,const std::wstring& expected);
std::vector<Handle> pin_parents(const std::wstring& path);
json::Value parent_generations(const std::vector<Handle>&);
void check_parents(const std::wstring& path,const std::vector<Handle>&,const json::Value& expected);
Metadata metadata(HANDLE);
json::Value generation(HANDLE,bool directory);
}}
