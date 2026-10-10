#pragma once
#include <string>

namespace disked {
// Private, host-neutral input shared by text frontends. Host adapters decode
// native events; each frontend decides their meaning. This is not a command,
// an OS key code, or a public SDK/protocol contract.
enum class TextKey {Text,Up,Down,PageUp,PageDown,Enter,Tab,BackTab,Backspace,Escape,F2,F3,F4,F5,F6,F9,F10,Left,Right,Home,End,Delete};
struct TextInput {TextKey key;std::string text;bool repeat=false;};
}
