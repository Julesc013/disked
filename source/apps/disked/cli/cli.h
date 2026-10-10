#pragma once
#include "command.h"
#include "policy.h"
#include "protocol.h"
namespace disked {
// Human CLI presentation only. Channel availability is observed by the host;
// this module neither writes handles nor selects providers or another frontend.
struct CliText {bool available=false,diagnostic=false;std::string bytes;};
CliText cli_text(const Outcome&,const ParseResult&,const InvocationHost&,const Registry&,bool background,bool acquisition_watch);
}
