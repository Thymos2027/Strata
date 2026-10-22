// A small independent kernel for checking actual hardware-counter access.
#include <cuda_runtime.h>
#include <cmath>
#include <cstdio>

__global__ void counter_probe(float* data, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    float v = float(i) * 0.0001f + 1.0f;
    for (int j = 0; j < 128; ++j) v = fmaf(v, 1.000001f, 0.000001f);
    data[i] = v;
}

int main() {
    constexpr int n = 65536;
    float* data = nullptr;
    cudaError_t status = cudaMalloc(&data, n * sizeof(float));
    if (status != cudaSuccess) { std::fprintf(stderr,"cudaMalloc: %s\n",cudaGetErrorString(status)); return 1; }
    counter_probe<<<n/128,128>>>(data,n);
    status = cudaDeviceSynchronize();
    float result = 0;
    if (status == cudaSuccess) status = cudaMemcpy(&result,data,sizeof(float),cudaMemcpyDeviceToHost);
    cudaFree(data);
    if (status != cudaSuccess || !std::isfinite(result) || result < 1.0f) {
        std::fprintf(stderr,"CUDA probe failed: %s; result=%f\n",cudaGetErrorString(status),result); return 1;
    }
    std::printf("CUDA probe passed: %f\n",result);
    return 0;
}
