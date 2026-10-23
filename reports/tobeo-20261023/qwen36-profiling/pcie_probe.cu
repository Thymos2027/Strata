// Bounded pinned-memory HtoD throughput diagnostic. Does not change clocks or link settings.
#include <cuda_runtime.h>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#define CK(x) do { auto e=(x); if(e!=cudaSuccess){std::fprintf(stderr,"%s: %s\n",#x,cudaGetErrorString(e));std::exit(1);} } while(0)
int main(){
    constexpr size_t bytes=64ull*1024*1024;
    size_t free=0,total=0;CK(cudaMemGetInfo(&free,&total));
    if(free<bytes*2){std::fprintf(stderr,"Insufficient free VRAM for bounded diagnostic\n");return 2;}
    void *host=nullptr,*device=nullptr;CK(cudaMallocHost(&host,bytes));CK(cudaMalloc(&device,bytes));
    std::memset(host,0x5a,bytes);
    cudaStream_t stream;CK(cudaStreamCreate(&stream));
    auto warm=std::chrono::steady_clock::now();
    do{for(int i=0;i<16;i++)CK(cudaMemcpyAsync(device,host,bytes,cudaMemcpyHostToDevice,stream));CK(cudaStreamSynchronize(stream));}
    while(std::chrono::duration<double>(std::chrono::steady_clock::now()-warm).count()<2.0);
    std::puts("Warm-up complete; measuring 512 pinned 64-MiB copies");std::fflush(stdout);
    cudaEvent_t begin,end;CK(cudaEventCreate(&begin));CK(cudaEventCreate(&end));CK(cudaEventRecord(begin,stream));
    for(int i=0;i<512;i++)CK(cudaMemcpyAsync(device,host,bytes,cudaMemcpyHostToDevice,stream));
    CK(cudaEventRecord(end,stream));CK(cudaEventSynchronize(end));float ms=0;CK(cudaEventElapsedTime(&ms,begin,end));
    unsigned value=0;CK(cudaMemcpy(&value,device,sizeof(value),cudaMemcpyDeviceToHost));
    if(value!=0x5a5a5a5a){std::fprintf(stderr,"Copy verification failed\n");return 3;}
    std::printf("{\"copies\":512,\"bytes_per_copy\":%llu,\"elapsed_ms\":%.6f,\"gb_per_s_decimal\":%.9f,\"verification_passed\":true}\n",
                (unsigned long long)bytes,ms,(double)bytes*512/(ms*1.e6));
    CK(cudaEventDestroy(begin));CK(cudaEventDestroy(end));CK(cudaStreamDestroy(stream));CK(cudaFree(device));CK(cudaFreeHost(host));
}
