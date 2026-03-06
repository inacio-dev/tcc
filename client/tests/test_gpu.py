#!/usr/bin/env python3
"""
test_gpu.py - Testa compatibilidade da GPU com CuPy
Roda: python test_gpu.py
"""

import subprocess
import sys


def test_nvidia_smi():
    print("=== nvidia-smi ===")
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,compute_cap,driver_version,memory.total",
         "--format=csv,noheader"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        name, cc, driver, mem = result.stdout.strip().split(", ")
        print(f"  GPU:                {name}")
        print(f"  Compute Capability: {cc}")
        print(f"  Driver:             {driver}")
        print(f"  VRAM:               {mem}")
    else:
        print("  nvidia-smi nao encontrado")
    print()


def test_cupy_import():
    print("=== Import CuPy ===")
    try:
        import cupy as cp
        print(f"  CuPy versao:   {cp.__version__}")
        cuda_ver = cp.cuda.runtime.runtimeGetVersion()
        major = cuda_ver // 1000
        patch = (cuda_ver % 1000) // 10
        print(f"  CUDA runtime:  {major}.{patch}")
        return cp
    except ImportError as e:
        print(f"  ERRO: CuPy nao instalado -- {e}")
        return None
    except Exception as e:
        print(f"  ERRO: {e}")
        return None
    finally:
        print()


def test_device_info(cp):
    print("=== Device Info ===")
    try:
        n = cp.cuda.runtime.getDeviceCount()
        print(f"  Dispositivos CUDA: {n}")
        for i in range(n):
            with cp.cuda.Device(i):
                dev = cp.cuda.Device(i)
                cc = dev.compute_capability
                free, total = dev.mem_info
                print(f"  Device {i}:")
                print(f"    Compute Capability: {cc}")
                print(f"    VRAM livre:  {free / 1024**2:.0f} MB")
                print(f"    VRAM total:  {total / 1024**2:.0f} MB")
    except Exception as e:
        print(f"  ERRO: {e}")
    print()


def test_basic_ops(cp):
    print("=== Operacoes Basicas ===")
    ops = [
        ("Alocacao array",  lambda: cp.zeros((1000, 1000), dtype=cp.float32)),
        ("Soma",            lambda: float(cp.sum(cp.ones((1000, 1000), dtype=cp.float32)))),
        ("Multiplicacao",   lambda: cp.ones((512, 512), dtype=cp.float32) * 2.0),
        ("Indexacao",       lambda: cp.arange(1000)[::2]),
    ]
    for name, fn in ops:
        try:
            fn()
            cp.cuda.Stream.null.synchronize()
            print(f"  [OK]   {name}")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
    print()


def test_convolution(cp):
    print("=== Convolucao (usada nos filtros de video) ===")
    try:
        from cupyx.scipy import ndimage as cp_ndimage
        kernel = cp.ones((3, 3), dtype=cp.float32) / 9
        img = cp.ones((480, 640), dtype=cp.float32)
        cp_ndimage.convolve(img, kernel)
        cp.cuda.Stream.null.synchronize()
        print("  [OK]   cupyx.scipy.ndimage.convolve")
    except Exception as e:
        print(f"  [FAIL] convolve: {e}")

    try:
        import numpy as np
        from cupyx.scipy import ndimage as cp_ndimage
        img_np = (255 * np.random.rand(480, 640, 3)).astype(np.float32)
        img_gpu = cp.asarray(img_np)
        kernel = cp.ones((3, 3), dtype=cp.float32) / 9
        for c in range(3):
            cp_ndimage.convolve(img_gpu[:, :, c], kernel)
        cp.cuda.Stream.null.synchronize()
        print("  [OK]   Convolucao RGB 480x640 (cenario real dos filtros)")
    except Exception as e:
        print(f"  [FAIL] Convolucao RGB: {e}")
    print()


def test_transfer(cp):
    print("=== Transferencia CPU <-> GPU ===")
    try:
        import numpy as np
        import time

        for h, w in [(100, 100), (480, 640), (1080, 1920)]:
            arr_cpu = (255 * np.random.rand(h, w, 3)).astype(np.uint8)
            size_mb = arr_cpu.nbytes / 1024**2

            t0 = time.perf_counter()
            arr_gpu = cp.asarray(arr_cpu)
            cp.cuda.Stream.null.synchronize()
            t_up = (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            cp.asnumpy(arr_gpu)
            t_down = (time.perf_counter() - t0) * 1000

            print(f"  {h}x{w} ({size_mb:.1f}MB): CPU->GPU {t_up:.1f}ms | GPU->CPU {t_down:.1f}ms")
    except Exception as e:
        print(f"  ERRO: {e}")
    print()


def conclusion(cp):
    print("=== Conclusao ===")
    if cp is None:
        print("  CuPy nao esta instalado. GPU nao disponivel.")
        return

    try:
        from cupyx.scipy import ndimage as cp_ndimage
        k = cp.ones((3, 3), dtype=cp.float32) / 9
        img = cp.ones((8, 8), dtype=cp.float32)
        cp_ndimage.convolve(img, k)
        cp.cuda.Stream.null.synchronize()
        print("  GPU COMPATIVEL com os filtros de video do projeto!")
        print("  image_filters.py usara GPU automaticamente.")
    except Exception as e:
        cc = cp.cuda.Device(0).compute_capability
        cuda_ver = cp.cuda.runtime.runtimeGetVersion()
        major = cuda_ver // 1000
        patch = (cuda_ver % 1000) // 10
        print(f"  GPU NAO COMPATIVEL com CuPy pre-compilado.")
        print(f"  Compute Capability {cc} (GPU serie 50xx / Blackwell)")
        print(f"  CUDA runtime disponivel: {major}.{patch}")
        print()
        print("  Causa: os wheels pre-compilados do CuPy foram gerados com CUDA < 12.8,")
        print("  que nao inclui suporte a sm_120. E necessario compilar do source")
        print("  usando CUDA 12.8+ para gerar kernels para Blackwell.")
        print()
        print("  Para compilar do source (requer ~30min e CUDA toolkit >= 12.8):")
        print("     pip uninstall cupy-cuda12x cupy-cuda13x")
        print("     CUPY_NVCC_GENERATE_CODE=arch=compute_120,code=sm_120 pip install cupy --no-binary cupy")
        print()
        print("  Alternativas:")
        print("  1. Aguardar wheel oficial com suporte a sm_120 em versoes futuras do CuPy")
        print("  2. Usar CPU (automatico -- a aplicacao funciona normalmente sem GPU)")
    print()


if __name__ == "__main__":
    print()
    test_nvidia_smi()
    cp = test_cupy_import()
    if cp:
        test_device_info(cp)
        test_basic_ops(cp)
        test_convolution(cp)
        test_transfer(cp)
    conclusion(cp)
