# Processamento de Imagem com GPU (CuPy + CUDA)

Documento sobre a habilitação de GPU NVIDIA para acelerar os filtros PDI no cliente.

## Status Atual

- **Data**: 2025-12-17
- **Status**: Opcional - CPU funciona perfeitamente para 640x480

---

## Requisitos

### Hardware
- GPU NVIDIA com suporte CUDA (ex: RTX 3050, GTX 1060+)
- Driver NVIDIA instalado

### Software
- CUDA Toolkit (versão compatível com o driver)
- CuPy (biblioteca Python para GPU)

---

## Instalação

### 1. Verificar GPU e Driver

```bash
nvidia-smi
```

Saída esperada:
```
NVIDIA GeForce RTX 3050 6GB Laptop GPU, 6144 MiB, 580.x.x
```

### 2. Instalar CUDA Toolkit

**Arch Linux:**
```bash
sudo pacman -S cuda
```

**Ubuntu/Debian:**
```bash
sudo apt install nvidia-cuda-toolkit
```

### 3. Configurar PATH

**Bash/Zsh:**
```bash
echo 'export PATH=/opt/cuda/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/opt/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

**Fish:**
```bash
fish_add_path /opt/cuda/bin
set -Ux LD_LIBRARY_PATH /opt/cuda/lib64 $LD_LIBRARY_PATH
```

### 4. Verificar Instalação

```bash
nvcc --version
```

### 5. Instalar CuPy

```bash
# Para CUDA 12.x
pip install cupy-cuda12x

# Para CUDA 11.x
pip install cupy-cuda11x
```

### 6. Testar

```bash
python -c "import cupy; print('GPU:', cupy.cuda.runtime.getDeviceCount(), 'dispositivos')"
```

---

## Problemas Conhecidos

### Erro: `forward compatibility was attempted on non supported HW`

**Causa:** Incompatibilidade entre versão do CUDA Toolkit e driver NVIDIA.

**Solução:**
1. Verificar versão suportada: `nvidia-smi` (mostra "CUDA Version" no canto superior direito)
2. Instalar CUDA Toolkit compatível
3. **Reiniciar o PC** após instalar CUDA

### Erro: `Driver/library version mismatch`

**Causa:** Driver foi atualizado mas sistema não reiniciou.

**Solução:** Reiniciar o PC.

### Erro: `libnvrtc.so.12: cannot open shared object file`

**Causa:** CUDA Toolkit não instalado ou PATH não configurado.

**Solução:**
1. Instalar CUDA Toolkit
2. Configurar PATH (ver seção acima)
3. Reiniciar terminal

---

## Compatibilidade Driver x CUDA

| Driver NVIDIA | CUDA Suportado |
|---------------|----------------|
| 550.x+        | CUDA 12.4+     |
| 535.x+        | CUDA 12.2+     |
| 525.x+        | CUDA 12.0+     |
| 515.x+        | CUDA 11.7+     |
| 470.x+        | CUDA 11.4+     |

Fonte: [NVIDIA CUDA Compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/)

---

## Filtros com Suporte GPU

| Filtro | GPU (CuPy) | CPU (OpenCV) | Recomendado |
|--------|------------|--------------|-------------|
| Sharpen (Laplaciano) | ✅ | ✅ | |
| High-Boost | ✅ | ✅ | |
| Unsharp Mask | ❌ | ✅ | |
| CLAHE | ❌ | ✅ | |
| CLAHE + High-Boost | ✅* | ✅ | ⭐ |
| Bilateral | ❌ | ✅ | |
| Super-Res 2x | ❌ | ✅ | |

*CLAHE + High-Boost: CLAHE roda na CPU, High-Boost usa GPU se disponível.

---

## Funcionamento no Código

### Detecção Automática (`image_filters.py`)

```python
# Tenta importar CuPy para aceleração GPU
try:
    import cupy as cp
    cp.cuda.runtime.getDeviceCount()  # Testa se CUDA funciona
    GPU_AVAILABLE = True
except:
    GPU_AVAILABLE = False
```

### Fallback Automático

Se GPU não disponível, o sistema usa CPU automaticamente:

```python
def _apply_sharpen(self, frame):
    if self.use_gpu:
        return self._gpu_convolve(frame, "laplacian")
    return cv2.filter2D(frame, -1, self.KERNELS["laplacian"])
```

### Indicação na Interface

Quando GPU está ativa, o overlay do vídeo mostra:
```
Filtro: Sharpen (Laplaciano) [GPU]
```

---

## Performance

Para resolução 640x480 @ 30 FPS:

| Processamento | Tempo/Frame | Observação |
|---------------|-------------|------------|
| CPU (OpenCV)  | ~2-5ms      | Suficiente para 30 FPS |
| GPU (CuPy)    | ~1-2ms      | Overhead de transferência |

**Conclusão:** Para 640x480, a diferença é mínima. GPU faz mais diferença em resoluções maiores (1080p+).

---

## Desabilitar GPU

Se preferir usar apenas CPU:

```bash
pip uninstall cupy-cuda12x cupy-cuda13x -y
```

O sistema funciona normalmente sem GPU.

---

## Arquivos Relacionados

- `client/image_filters.py` - Implementação dos filtros com suporte GPU
- `client/requirements.txt` - Dependências (CuPy opcional)
- `client/console/frames/video.py` - Dropdown de seleção de filtros
- `client/video_display.py` - Aplicação dos filtros no pipeline de vídeo
