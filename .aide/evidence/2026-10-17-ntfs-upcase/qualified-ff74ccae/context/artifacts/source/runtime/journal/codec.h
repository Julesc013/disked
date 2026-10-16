#pragma once
#include <array>
#include <cstdint>
#include <functional>
#include <stdexcept>
#include <string>
#include <vector>

namespace disked { namespace journal { namespace proposal {
using Bytes=std::vector<unsigned char>;
using Digest=std::array<unsigned char,32>;
using Identity=std::array<unsigned char,16>;
constexpr std::size_t header_bytes=192,prefix_bytes=112,trailer_bytes=32,max_payload=65536;
constexpr std::uint64_t max_source=16777216,max_records=4096;
// Experimental framing only. No effect, repair, authority or file-writing port.
struct Error:std::runtime_error {using std::runtime_error::runtime_error;};
struct Bindings {Identity journal{};Digest plan{},targets{},providers{};};
struct Record {
    std::uint16_t kind=0,flags=0;
    std::uint64_t sequence=0,publisher_epoch=0;
    Identity publisher{};Digest previous{},digest{};
    Bytes payload;bool known=false;
};
class Source {
public:
    virtual ~Source()=default;
    virtual std::uint64_t size()=0;
    // Exactly count bytes or a failure. Never more than max_payload.
    virtual Bytes read_at(std::uint64_t offset,std::size_t count)=0;
};
struct Scan {
    std::string disposition="invalid",diagnostic;
    std::uint64_t records=0,verified_bytes=0,error_offset=0;
    Digest last{};
    bool terminal_record_observed=false;
};
Digest hash(const Bytes&);
Bytes encode_header(const Bindings&);
Bindings decode_header(const Bytes&);
// Strict producer. Known mutation-critical kinds cannot drop their critical bit.
Bytes encode_record(const Digest& header_digest,const Record&);
// Format validation and optional semantic acceptance, no recovery decisions.
Scan scan(Source&,const Bindings&,const std::function<bool(const Record&)>& visitor={});
}}}
