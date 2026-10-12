#pragma once
#include "apps/disked/tui/tui_model.h"
#include "apps/disked/shell/shell_model.h"
#include <memory>
namespace disked {
int run_windows_tui(const std::string& presentation,const std::function<std::unique_ptr<TuiModel>()>& create,
    const std::function<void()>& advance_observations={},const std::function<void()>& before_model_release={});
int run_windows_shell(const std::string& presentation,const std::function<std::unique_ptr<ShellModel>()>& create,
    const std::function<void()>& advance_observations={},const std::function<void()>& before_model_release={});
}
