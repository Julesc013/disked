#pragma once
#include "model.h"
#include <memory>
namespace disked {
int run_windows_tui(const std::string& presentation,const std::function<std::unique_ptr<TuiModel>()>& create);
}
