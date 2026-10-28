// Bounded diagnostic. No link, driver or clock settings are changed.
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#define CK(x) do {auto e=(x); if(e!=cudaSuccess){fprintf(stderr,"%s: %s\n",#x,cudaGetErrorString(e));exit(1);}}while(0)
using Clock=std::chrono::steady_clock;
constexpr size_t N=64ull<<20;
__global__ void read_mapped(const unsigned *p, unsigned *out, size_t n){
 unsigned s=0;for(size_t i=blockIdx.x*blockDim.x+threadIdx.x;i<n;i+=gridDim.x*blockDim.x)s+=p[i];
 out[blockIdx.x*blockDim.x+threadIdx.x]=s;
}
void measure(const char *name,void *dst,void *src,cudaMemcpyKind kind,int count){
 for(int i=0;i<8;++i) CK(cudaMemcpy(dst,src,N,kind));
 cudaEvent_t a,b;CK(cudaEventCreate(&a));CK(cudaEventCreate(&b));
 auto t=Clock::now();CK(cudaEventRecord(a));
 for(int i=0;i<count;++i)CK(cudaMemcpyAsync(dst,src,N,kind));
 CK(cudaEventRecord(b));CK(cudaEventSynchronize(b));float ms;CK(cudaEventElapsedTime(&ms,a,b));
 double wall=std::chrono::duration<double>(Clock::now()-t).count();
 printf("{\"test\":\"%s\",\"bytes_per_copy\":%llu,\"count\":%d,\"event_GBps\":%.6f,\"wall_GBps\":%.6f}\n",name,(unsigned long long)N,count,double(N)*count/(ms*1e6),double(N)*count/wall/1e9);fflush(stdout);
 CK(cudaEventDestroy(a));CK(cudaEventDestroy(b));
}
int main(){
 void *h,*d,*d2;CK(cudaMallocHost(&h,N));CK(cudaMalloc(&d,N));CK(cudaMalloc(&d2,N));memset(h,0x5a,N);
 measure("pinned_H2D",d,h,cudaMemcpyHostToDevice,128);
 unsigned v;CK(cudaMemcpy(&v,d,4,cudaMemcpyDeviceToHost));if(v!=0x5a5a5a5a)return 2;
 measure("pinned_D2H",h,d,cudaMemcpyDeviceToHost,128);
 if(*(unsigned*)h!=0x5a5a5a5a)return 3;
 measure("D2D_oneway_bytes",d2,d,cudaMemcpyDeviceToDevice,256);
 CK(cudaMemcpy(&v,d2,4,cudaMemcpyDeviceToHost));if(v!=0x5a5a5a5a)return 4;
 void *h2=malloc(N);if(!h2)return 5;
 auto t=Clock::now();for(int i=0;i<128;++i){memcpy(h2,h,N);*(volatile unsigned*)h2=i;}
 printf("{\"test\":\"CPU_memcpy\",\"GBps\":%.6f}\n",double(N)*128/std::chrono::duration<double>(Clock::now()-t).count()/1e9);
 void *mapped;CK(cudaHostGetDevicePointer(&mapped,h,0));
 read_mapped<<<256,256>>>((unsigned*)mapped,(unsigned*)d2,N/4);CK(cudaGetLastError());CK(cudaDeviceSynchronize());
 cudaEvent_t a,b;CK(cudaEventCreate(&a));CK(cudaEventCreate(&b));CK(cudaEventRecord(a));
 for(int i=0;i<32;++i)read_mapped<<<256,256>>>((unsigned*)mapped,(unsigned*)d2,N/4);
 CK(cudaGetLastError());CK(cudaEventRecord(b));CK(cudaEventSynchronize(b));float ms;CK(cudaEventElapsedTime(&ms,a,b));
 CK(cudaMemcpy(&v,d2,4,cudaMemcpyDeviceToHost));unsigned expected=0;for(size_t i=0;i<N/4;i+=65536)expected+=0x5a5a5a5au;
 if(v!=expected){fprintf(stderr,"mapped verification failed\n");return 6;}
 printf("{\"test\":\"mapped_GPU_read\",\"GBps\":%.6f,\"spot_checks_passed\":true}\n",double(N)*32/(ms*1e6));
 CK(cudaFree(d));CK(cudaFree(d2));CK(cudaFreeHost(h));free(h2);
}
