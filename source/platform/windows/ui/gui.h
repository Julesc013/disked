#pragma once
#include "gui_model.h"
#include <functional>

namespace disked {
int run_windows_gui(const std::function<std::unique_ptr<GuiModel>(const json::Value&)>& create);
}
