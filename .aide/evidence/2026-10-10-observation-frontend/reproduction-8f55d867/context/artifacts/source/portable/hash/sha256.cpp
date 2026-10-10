#include "sha256.h"
#include <cstring>

namespace disked {
namespace {
// FIPS 180-4 sections 4.1.2, 4.2.2, 5.1.1, 5.3.3 and 6.2.
const std::uint32_t constants[64]={
  0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
  0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
  0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
  0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
  0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
  0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
  0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
std::uint32_t rotate(std::uint32_t v,unsigned n) {return (v>>n)|(v<<(32-n));}
void block(std::uint32_t state[8],const unsigned char* bytes) {
    std::uint32_t w[64];
    for(unsigned i=0;i<16;++i)w[i]=(std::uint32_t(bytes[4*i])<<24)|(std::uint32_t(bytes[4*i+1])<<16)|
        (std::uint32_t(bytes[4*i+2])<<8)|bytes[4*i+3];
    for(unsigned i=16;i<64;++i) {
        const auto x=w[i-15],y=w[i-2];
        w[i]=w[i-16]+(rotate(x,7)^rotate(x,18)^(x>>3))+w[i-7]+(rotate(y,17)^rotate(y,19)^(y>>10));
    }
    auto a=state[0],b=state[1],c=state[2],d=state[3],e=state[4],f=state[5],g=state[6],h=state[7];
    for(unsigned i=0;i<64;++i) {
        const auto t1=h+(rotate(e,6)^rotate(e,11)^rotate(e,25))+((e&f)^(~e&g))+constants[i]+w[i];
        const auto t2=(rotate(a,2)^rotate(a,13)^rotate(a,22))+((a&b)^(a&c)^(b&c));
        h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
    }
    state[0]+=a;state[1]+=b;state[2]+=c;state[3]+=d;state[4]+=e;state[5]+=f;state[6]+=g;state[7]+=h;
}
}
void sha256(const unsigned char* data,std::size_t size,unsigned char digest[32]) {
    std::uint32_t state[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    const auto bits=static_cast<std::uint64_t>(size)*8;
    while(size>=64) {block(state,data);data+=64;size-=64;}
    unsigned char tail[128]={};if(size)std::memcpy(tail,data,size);tail[size]=0x80;
    const std::size_t padded=size<56?64:128;
    for(unsigned i=0;i<8;++i)tail[padded-1-i]=static_cast<unsigned char>(bits>>(8*i));
    block(state,tail);if(padded==128)block(state,tail+64);
    for(unsigned i=0;i<32;++i)digest[i]=static_cast<unsigned char>(state[i/4]>>(24-8*(i%4)));
}
}
