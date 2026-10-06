#pragma once
#include "model.h"
#include "shell_model.h"
#include <memory>
namespace disked {
int run_windows_tui(const std::string& presentation,const std::function<std::unique_ptr<TuiModel>()>& create);
int run_windows_shell(const std::string& presentation,const std::function<std::unique_ptr<ShellModel>()>& create);
}
