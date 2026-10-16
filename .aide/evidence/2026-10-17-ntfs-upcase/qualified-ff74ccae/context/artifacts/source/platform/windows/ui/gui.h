#pragma once
#include "apps/disked/gui/gui_model.h"
#include <functional>

namespace disked {
// Explicit serialized application source control, separate from model tick and
// cached observation getters. The ordinary product supplies no callback.
int run_windows_gui(const std::function<std::unique_ptr<GuiModel>(const json::Value&)>& create,
    const std::function<void()>& advance_observations={},const std::function<void()>& before_model_release={});
}
