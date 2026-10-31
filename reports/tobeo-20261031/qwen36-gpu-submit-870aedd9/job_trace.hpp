#pragma once
// Local diagnostic only. No arithmetic, scheduling or synchronization policy changes.
#include <nvtx3/nvToolsExt.h>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
namespace strata_job_trace {
inline bool enabled() {
    static const bool value = [] { const char* p = std::getenv("STRATA_Q36_JOB_TRACE"); return p && p[0]=='1' && p[1]=='\0'; }();
    return value;
}
inline thread_local uint64_t forward_id=0, moe_id=0;
inline uint64_t next_forward() { if (enabled()) ++forward_id; return forward_id; }
inline uint64_t next_moe() { if (enabled()) ++moe_id; return moe_id; }
class Span {
    bool active_=false;
    char text_[256];
public:
    explicit Span(const char* format, ...) {
        if (!enabled()) return;
        va_list args; va_start(args,format); std::vsnprintf(text_,sizeof(text_),format,args); va_end(args);
        nvtxRangePushA(text_); active_=true;
    }
    void finish() { if (active_) { nvtxRangePop(); active_=false; } }
    ~Span() { finish(); }
    Span(const Span&)=delete;
    Span& operator=(const Span&)=delete;
};
inline void mark(const char* format, ...) {
    if (!enabled()) return;
    char text[256]; va_list args; va_start(args,format); std::vsnprintf(text,sizeof(text),format,args); va_end(args);
    nvtxMarkA(text);
}
}
