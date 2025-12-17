#!/usr/bin/env python3
"""
image_filters.py - Filtros de Processamento Digital de Imagens (PDI)

Implementa máscaras e filtros para aprimoramento de qualidade de vídeo:
- Aguçamento (Sharpening): Laplaciano, Unsharp Mask, High-boost
- Suavização: Bilateral, Denoise
- Realce: CLAHE (Contrast Limited Adaptive Histogram Equalization)
- Super-resolução: Upscale com Lanczos

Suporte a GPU NVIDIA via CuPy (opcional):
- Se CuPy estiver instalado, usa GPU para operações de convolução
- Fallback automático para CPU se GPU não disponível

Referências teóricas:
- Gonzalez & Woods, "Digital Image Processing"
- Máscaras de convolução para realce espacial
"""

import cv2
import numpy as np
from typing import Optional, Callable, Dict, List

# Tenta importar CuPy para aceleração GPU
GPU_AVAILABLE = False
cp = None
cp_ndimage = None

try:
    import cupy as cp
    # Testa se CUDA realmente funciona
    cp.cuda.runtime.getDeviceCount()
    from cupyx.scipy import ndimage as cp_ndimage
    GPU_AVAILABLE = True
    print("[FILTERS] GPU NVIDIA detectada - usando CuPy para aceleração")
except ImportError:
    print("[FILTERS] CuPy não instalado - usando CPU")
except Exception as e:
    # CUDA não disponível ou erro de runtime
    cp = None
    cp_ndimage = None
    print(f"[FILTERS] GPU não disponível ({type(e).__name__}) - usando CPU")


class ImageFilters:
    """Gerencia filtros PDI para processamento de frames de vídeo"""

    # Máscaras de convolução clássicas
    KERNELS = {
        # Laplaciano 3x3 - detecta bordas em todas as direções
        "laplacian": np.array([
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0]
        ], dtype=np.float32),

        # Laplaciano 8-conectado (mais agressivo)
        "laplacian_8": np.array([
            [-1, -1, -1],
            [-1, 9, -1],
            [-1, -1, -1]
        ], dtype=np.float32),

        # High-boost (aguçamento com preservação de baixas frequências)
        # A > 1 para boost, A = 1 é unsharp mask
        "high_boost": np.array([
            [-1, -1, -1],
            [-1, 10, -1],
            [-1, -1, -1]
        ], dtype=np.float32) / 2,
    }

    # Definição dos filtros disponíveis
    FILTERS = {
        "original": {
            "name": "Original",
            "description": "Sem filtro aplicado",
        },
        "sharpen": {
            "name": "Sharpen (Laplaciano)",
            "description": "Aguça bordas usando máscara Laplaciana 3x3",
        },
        "unsharp": {
            "name": "Unsharp Mask",
            "description": "Aguçamento suave - subtrai versão borrada",
        },
        "high_boost": {
            "name": "High-Boost",
            "description": "Aguçamento com preservação de detalhes",
        },
        "clahe": {
            "name": "CLAHE",
            "description": "Equalização adaptativa de histograma",
        },
        "bilateral": {
            "name": "Bilateral",
            "description": "Suaviza ruído preservando bordas",
        },
        "denoise": {
            "name": "Denoise",
            "description": "Remoção de ruído (Non-local Means)",
        },
        "super_res": {
            "name": "Super-Res 2x",
            "description": "Upscale 2x com interpolação Lanczos",
        },
    }

    def __init__(self, use_gpu=True):
        """
        Inicializa o gerenciador de filtros

        Args:
            use_gpu: Se True, usa GPU quando disponível
        """
        self.current_filter = "original"
        self.use_gpu = use_gpu and GPU_AVAILABLE
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        # Cache para super-resolução (evita recriar toda vez)
        self._super_res_size = None

        # Kernels para GPU (CuPy)
        if self.use_gpu:
            self._gpu_kernels = {
                "laplacian": cp.array([
                    [0, -1, 0],
                    [-1, 5, -1],
                    [0, -1, 0]
                ], dtype=cp.float32),
                "high_boost": cp.array([
                    [-1, -1, -1],
                    [-1, 10, -1],
                    [-1, -1, -1]
                ], dtype=cp.float32) / 2,
            }

    @classmethod
    def get_filter_names(cls) -> List[str]:
        """Retorna lista de nomes dos filtros para exibição"""
        return [f["name"] for f in cls.FILTERS.values()]

    @classmethod
    def get_filter_keys(cls) -> List[str]:
        """Retorna lista de chaves dos filtros"""
        return list(cls.FILTERS.keys())

    @classmethod
    def get_filter_by_name(cls, name: str) -> Optional[str]:
        """Retorna a chave do filtro pelo nome de exibição"""
        for key, data in cls.FILTERS.items():
            if data["name"] == name:
                return key
        return None

    def set_filter(self, filter_key: str) -> bool:
        """
        Define o filtro atual

        Args:
            filter_key: Chave do filtro (ex: 'sharpen', 'clahe')

        Returns:
            bool: True se filtro válido
        """
        if filter_key in self.FILTERS:
            self.current_filter = filter_key
            return True
        return False

    def apply(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica o filtro atual ao frame

        Args:
            frame: Frame BGR (numpy array)

        Returns:
            Frame processado
        """
        if frame is None or self.current_filter == "original":
            return frame

        try:
            method = getattr(self, f"_apply_{self.current_filter}", None)
            if method:
                return method(frame)
            return frame
        except Exception as e:
            print(f"[FILTER] Erro ao aplicar filtro: {e}")
            return frame

    def _apply_sharpen(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica aguçamento com máscara Laplaciana

        Teoria: O Laplaciano é um operador de segunda derivada que
        destaca regiões de mudança rápida de intensidade (bordas).
        A máscara 3x3 com centro 5 preserva a imagem original
        enquanto realça as bordas.
        """
        if self.use_gpu:
            return self._gpu_convolve(frame, "laplacian")
        return cv2.filter2D(frame, -1, self.KERNELS["laplacian"])

    def _apply_unsharp(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica Unsharp Masking

        Teoria: Unsharp Mask = Original + k * (Original - Blur)
        Subtrai uma versão borrada da imagem e adiciona ao original,
        realçando detalhes de alta frequência.
        """
        # Blur gaussiano
        blurred = cv2.GaussianBlur(frame, (0, 0), 3)

        # Unsharp mask: original + k * (original - blur)
        # cv2.addWeighted faz: src1*alpha + src2*beta + gamma
        sharpened = cv2.addWeighted(frame, 1.5, blurred, -0.5, 0)

        return sharpened

    def _apply_high_boost(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica filtro High-Boost

        Teoria: High-boost = (A-1) * Original + Laplaciano
        Onde A > 1 para aumentar a contribuição do original.
        Mais suave que Laplaciano puro, preserva mais detalhes.
        """
        if self.use_gpu:
            return self._gpu_convolve(frame, "high_boost")
        return cv2.filter2D(frame, -1, self.KERNELS["high_boost"])

    def _apply_clahe(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica CLAHE (Contrast Limited Adaptive Histogram Equalization)

        Teoria: Divide a imagem em tiles e aplica equalização de
        histograma em cada um, com limite de contraste para evitar
        amplificação de ruído. Melhora contraste local.
        """
        # Converte para LAB para aplicar CLAHE apenas na luminância
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # Aplica CLAHE no canal L
        l = self.clahe.apply(l)

        # Reconstrói a imagem
        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def _apply_bilateral(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica filtro Bilateral

        Teoria: Suaviza a imagem preservando bordas usando duas
        gaussianas: uma para distância espacial e outra para
        diferença de intensidade. Pixels similares em cor são
        mais afetados que pixels diferentes.
        """
        return cv2.bilateralFilter(frame, d=9, sigmaColor=75, sigmaSpace=75)

    def _apply_denoise(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica remoção de ruído Non-Local Means

        Teoria: NLM busca patches similares em toda a imagem e
        faz média ponderada pela similaridade. Muito eficaz para
        ruído gaussiano, preserva texturas e bordas.
        """
        # fastNlMeansDenoisingColored para imagens coloridas
        # h=10: força do filtro (maior = mais suavização)
        # hForColorComponents=10: força para canais de cor
        # templateWindowSize=7: tamanho do patch
        # searchWindowSize=21: área de busca
        return cv2.fastNlMeansDenoisingColored(frame, None, 10, 10, 7, 21)

    def _apply_super_res(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica Super-resolução 2x com Lanczos

        Teoria: Interpolação Lanczos usa função sinc truncada
        para estimar valores de pixels intermediários.
        Melhor qualidade que bilinear/bicúbica para upscaling.
        """
        h, w = frame.shape[:2]
        new_size = (w * 2, h * 2)

        # Upscale com Lanczos
        upscaled = cv2.resize(frame, new_size, interpolation=cv2.INTER_LANCZOS4)

        # Aplica leve aguçamento após upscale para compensar blur
        kernel = np.array([
            [0, -0.5, 0],
            [-0.5, 3, -0.5],
            [0, -0.5, 0]
        ], dtype=np.float32)
        upscaled = cv2.filter2D(upscaled, -1, kernel)

        return upscaled

    def get_current_filter_info(self) -> Dict:
        """Retorna informações do filtro atual"""
        info = {
            "key": self.current_filter,
            **self.FILTERS.get(self.current_filter, {})
        }
        if self.use_gpu:
            info["gpu"] = True
        return info

    def _gpu_convolve(self, frame: np.ndarray, kernel_name: str) -> np.ndarray:
        """
        Aplica convolução usando GPU (CuPy)

        Args:
            frame: Frame BGR (numpy array)
            kernel_name: Nome do kernel em _gpu_kernels

        Returns:
            Frame processado (numpy array)
        """
        try:
            kernel = self._gpu_kernels.get(kernel_name)
            if kernel is None:
                return frame

            # Transfere para GPU
            gpu_frame = cp.asarray(frame, dtype=cp.float32)

            # Aplica convolução em cada canal separadamente
            result = cp.zeros_like(gpu_frame)
            for i in range(3):  # BGR
                result[:, :, i] = cp_ndimage.convolve(gpu_frame[:, :, i], kernel)

            # Clipa valores e converte de volta
            result = cp.clip(result, 0, 255).astype(cp.uint8)

            # Transfere de volta para CPU
            return cp.asnumpy(result)

        except Exception as e:
            print(f"[FILTER-GPU] Erro, usando CPU: {e}")
            # Fallback para CPU
            cpu_kernel = self.KERNELS.get(kernel_name)
            if cpu_kernel is not None:
                return cv2.filter2D(frame, -1, cpu_kernel)
            return frame

    def is_gpu_enabled(self) -> bool:
        """Retorna se GPU está sendo usada"""
        return self.use_gpu


# Instância global para uso fácil
_filters = None


def get_filters() -> ImageFilters:
    """Retorna instância global dos filtros"""
    global _filters
    if _filters is None:
        _filters = ImageFilters()
    return _filters
