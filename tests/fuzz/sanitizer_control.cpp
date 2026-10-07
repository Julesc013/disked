// Deliberately invalid test-only positive controls. Never linked into DiskEd.
#include <climits>
#include <cstdlib>
#include <string>
int main(int argc,char** argv) {
    if(argc!=2)return 2;
    if(std::string(argv[1])=="overflow") { volatile int value=INT_MAX; return value+1; }
    if(std::string(argv[1])=="bounds") {
        volatile int offset=8; auto* p=static_cast<unsigned char*>(std::malloc(8));
        if(!p)return 2;
        p[offset]=1; volatile int value=p[offset]; std::free(p); return value;
    }
    return 2;
}
