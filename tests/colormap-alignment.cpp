// Board regression: exercise the engine's actual SIMD blur functions against
// an independent byte-wise oracle, including every 16-byte alignment and tail.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
using Fn = void (*)(unsigned char*, const unsigned char*, int, int);
void TVPChBlurAddMulCopy65_sse2_c(unsigned char*, const unsigned char*, int, int);
void TVPChBlurAddMulCopy_sse2_c(unsigned char*, const unsigned char*, int, int);
void TVPChBlurMulCopy65_sse2_c(unsigned char*, const unsigned char*, int, int);
void TVPChBlurMulCopy_sse2_c(unsigned char*, const unsigned char*, int, int);
int main(int argc, char**) {
    Fn funcs[] = {TVPChBlurAddMulCopy65_sse2_c, TVPChBlurAddMulCopy_sse2_c,
                  TVPChBlurMulCopy65_sse2_c, TVPChBlurMulCopy_sse2_c};
    alignas(16) unsigned char dst[128], src[128], expected[128], saved[128];
    if (argc > 1) {
        std::memset(dst, 11, sizeof(dst)); std::memset(src, 19, sizeof(src));
        funcs[1](dst + 17, src + 19, 4, 262144);
        std::puts("single unaligned call passed"); return 0;
    }
    const int levels[] = {0,1,65535,65536,131071,131072,262143,262144,524288,1048576};
    unsigned cases = 0;
    for (int f=0; f<4; ++f) for (int d=0; d<16; ++d) for (int s=0; s<16; ++s)
    for (int n=0; n<=65; ++n) for (int level: levels) {
        for (int i=0; i<128; ++i) {
            dst[i] = static_cast<unsigned char>(i*79+n*23+d*11);
            src[i] = static_cast<unsigned char>(i*53+n*17+s*31);
        }
        std::memcpy(expected, dst, sizeof(dst)); std::memcpy(saved, src, sizeof(src));
        for (int i=0; i<n; ++i) {
            int v = (static_cast<uint32_t>(src[16+s+i])*level) >> 18;
            if (f<2) v += dst[16+d+i];
            expected[16+d+i] = std::min(v, (f%2==0) ? 64 : 255);
        }
        funcs[f](dst+16+d, src+16+s, n, level);
        if (std::memcmp(dst, expected, sizeof(dst)) || std::memcmp(src, saved, sizeof(src))) {
            std::printf("FAIL f=%d dst=%d src=%d n=%d level=%d\n", f,d,s,n,level);
            return 1;
        }
        ++cases;
    }
    std::printf("PASS cases=%u; all offsets 0..15, lengths 0..65; guards and source intact\n", cases);
}
