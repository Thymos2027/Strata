// Operator feasibility probe, NOT a segmented full-model prefill implementation.
#include "strata/prefill/gemm.hpp"
#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <random>
#include <string>
#include <vector>

void ck(cudaError_t code, const char* label) {
    if (code != cudaSuccess) { std::fprintf(stderr, "%s: %s\n",label,cudaGetErrorString(code)); std::exit(2); }
}
int main(int argc,char** argv) {
    if (argc != 7) return 3;
    const std::string path=argv[1]; const int type=std::atoi(argv[2]);
    const int N=std::atoi(argv[3]),K=std::atoi(argv[4]),L=std::atoi(argv[5]),B=std::atoi(argv[6]);
    const int T=L*B;
    if (N<=0 || K<=0 || L<=0 || B<2 || T>4096) return 3;
    std::ifstream file(path,std::ios::binary|std::ios::ate);
    if (!file) return 3;
    const size_t bytes=(size_t)file.tellg(); file.seekg(0);
    void *hw=nullptr,*dw=nullptr; uint16_t* dx=nullptr; float *da=nullptr,*db=nullptr;
    ck(cudaMallocHost(&hw,bytes),"pinned weight"); file.read((char*)hw,bytes);
    if (!file) return 3;
    cudaStream_t stream; ck(cudaStreamCreate(&stream),"stream");
    ck(cudaMalloc(&dw,bytes),"weight"); ck(cudaMemcpy(dw,hw,bytes,cudaMemcpyHostToDevice),"weight init");
    ck(cudaMalloc(&dx,(size_t)T*K*2),"input");
    ck(cudaMalloc(&da,(size_t)T*N*4),"output A"); ck(cudaMalloc(&db,(size_t)T*N*4),"output B");
    std::mt19937 rng(20261104); std::uniform_real_distribution<float> dist(-.5f,.5f);
    std::vector<uint16_t> x((size_t)T*K);
    for (auto& v:x) { __half h=__float2half(dist(rng)); std::memcpy(&v,&h,2); }
    ck(cudaMemcpy(dx,x.data(),x.size()*2,cudaMemcpyHostToDevice),"input init");
    strata::prefill::Gemm gemm; std::string error;
    if (!gemm.init(stream,(int64_t)N*K,error)) { std::fprintf(stderr,"%s\n",error.c_str()); return 2; }
    auto run=[&](bool packed,bool transfer) {
        const int calls=packed?1:B, rows=packed?T:L; float* dst=packed?db:da;
        for (int i=0;i<calls;++i) {
            if (transfer) ck(cudaMemcpyAsync(dw,hw,bytes,cudaMemcpyHostToDevice,stream),"weight transfer");
            gemm.native(dx+(size_t)i*rows*K,type,dw,dst+(size_t)i*rows*N,rows,N,K);
        }
    };
    // Same weight and activation rows: compare individual products with packed rows.
    run(false,false); run(true,false); ck(cudaStreamSynchronize(stream),"correctness");
    std::vector<float> a((size_t)T*N),b(a.size());
    ck(cudaMemcpy(a.data(),da,a.size()*4,cudaMemcpyDeviceToHost),"read A");
    ck(cudaMemcpy(b.data(),db,b.size()*4,cudaMemcpyDeviceToHost),"read B");
    double sq=0,ref=0,maxerr=0,maxref=0; bool finite=true;
    for (size_t i=0;i<a.size();++i) {
        if (!std::isfinite(a[i]) || !std::isfinite(b[i])) { finite=false; break; }
        double e=std::abs((double)a[i]-b[i]); sq+=e*e; ref+=(double)a[i]*a[i];
        maxerr=std::max(maxerr,e); maxref=std::max(maxref,std::abs((double)a[i]));
    }
    const double nrmse=std::sqrt(sq/std::max(ref,1e-30));
    if (!finite || nrmse>0.002 || maxerr>0.01+0.002*maxref) {
        std::fprintf(stderr,"FAIL parity finite=%d nrmse=%g max=%g ref=%g\n",finite,nrmse,maxerr,maxref); return 4;
    }
    std::printf("CHECK,%d,%d,%d,%d,%.12g,%.12g,%.12g\n",N,K,L,B,nrmse,maxerr,maxref);
    cudaEvent_t begin,end; ck(cudaEventCreate(&begin),"event"); ck(cudaEventCreate(&end),"event");
    constexpr int REPEAT=10;
    auto time_run=[&](bool packed,bool transfer) {
        ck(cudaEventRecord(begin,stream),"begin");
        for(int i=0;i<REPEAT;++i) run(packed,transfer);
        ck(cudaEventRecord(end,stream),"end"); ck(cudaEventSynchronize(end),"timing");
        float ms; ck(cudaEventElapsedTime(&ms,begin,end),"elapsed"); return ms/REPEAT;
    };
    for(int transfer=0;transfer<=1;++transfer) {
        for(int i=0;i<3;++i) { run(false,transfer); run(true,transfer); }
        ck(cudaStreamSynchronize(stream),"warmup");
        for(int pair=0;pair<5;++pair) {
            float ta,tb;
            if(pair%2==0) { ta=time_run(false,transfer); tb=time_run(true,transfer); }
            else { tb=time_run(true,transfer); ta=time_run(false,transfer); }
            std::printf("PAIR,%s,%d,%.9g,%.9g,%.9g,%zu,%zu\n",transfer?"streamed":"resident",pair+1,ta,tb,ta/tb,
                        transfer?bytes*B:0,transfer?bytes:0); std::fflush(stdout);
        }
    }
    ck(cudaStreamSynchronize(stream),"finish");
    cudaEventDestroy(begin); cudaEventDestroy(end); cudaFree(dw); cudaFree(dx); cudaFree(da); cudaFree(db);
    cudaFreeHost(hw); cudaStreamDestroy(stream);
    return 0;
}
