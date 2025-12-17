#!/usr/bin/env python3
"""
image_filters.py - Filtros de Processamento Digital de Imagens (PDI)

Implementa máscaras e filtros para aprimoramento de qualidade de vídeo:
- Aguçamento (Sharpening): Laplaciano, Unsharp Mask, High-boost
- Suavização: Bilateral
- Realce: CLAHE (Contrast Limited Adaptive Histogram Equalization)
- Super-Res: Supersampling 2x (anti-aliasing, suaviza pixels)

Filtros são combináveis via checkboxes na interface.

Suporte a GPU NVIDIA via CuPy (opcional):
- Sharpen, High-Boost: convolução GPU
- Unsharp Mask: blur gaussiano + operações aritméticas GPU
- Brilho +/-: operações aritméticas GPU
- Super-Res: zoom/reshape GPU
- CLAHE, Bilateral: CPU apenas (algoritmos complexos)
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


def _create_gaussian_kernel(size=5, sigma=1.0):
    """Cria kernel Gaussiano para GPU"""
    x = np.arange(size) - size // 2
    kernel_1d = np.exp(-x**2 / (2 * sigma**2))
    kernel_2d = np.outer(kernel_1d, kernel_1d)
    return (kernel_2d / kernel_2d.sum()).astype(np.float32)


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
        "super_res": {
            "name": "Super-Res 2x",
            "description": "Supersampling 2x para anti-aliasing (suaviza pixels)",
        },
        "brightness_up": {
            "name": "Brilho +",
            "description": "Aumenta brilho (para ambientes escuros)",
        },
        "brightness_down": {
            "name": "Brilho -",
            "description": "Diminui brilho (para ambientes claros)",
        },
    }

    def __init__(self, use_gpu=True):
        """
        Inicializa o gerenciador de filtros

        Args:
            use_gpu: Se True, usa GPU quando disponível
        """
        self.current_filter = "original"
        self.active_filters = set()  # Filtros ativos (para modo checkbox)
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
                "gaussian": cp.array(_create_gaussian_kernel(7, 3.0), dtype=cp.float32),
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
        Define o filtro atual (modo dropdown - legado)

        Args:
            filter_key: Chave do filtro (ex: 'sharpen', 'clahe')

        Returns:
            bool: True se filtro válido
        """
        if filter_key in self.FILTERS:
            self.current_filter = filter_key
            return True
        return False

    def toggle_filter(self, filter_key: str) -> bool:
        """
        Ativa/desativa um filtro (modo checkbox)

        Args:
            filter_key: Chave do filtro

        Returns:
            bool: True se filtro está ativo após toggle
        """
        if filter_key not in self.FILTERS or filter_key == "original":
            return False

        if filter_key in self.active_filters:
            self.active_filters.discard(filter_key)
            return False
        else:
            self.active_filters.add(filter_key)
            return True

    def set_filter_active(self, filter_key: str, active: bool):
        """
        Define estado de um filtro diretamente

        Args:
            filter_key: Chave do filtro
            active: True para ativar, False para desativar
        """
        if filter_key not in self.FILTERS or filter_key == "original":
            return

        if active:
            self.active_filters.add(filter_key)
        else:
            self.active_filters.discard(filter_key)

    def is_filter_active(self, filter_key: str) -> bool:
        """Verifica se um filtro está ativo"""
        return filter_key in self.active_filters

    def get_active_filters(self) -> List[str]:
        """Retorna lista de filtros ativos"""
        return list(self.active_filters)

    def clear_filters(self):
        """Remove todos os filtros ativos"""
        self.active_filters.clear()

    def apply(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica os filtros ativos ao frame

        Args:
            frame: Frame BGR (numpy array)

        Returns:
            Frame processado
        """
        if frame is None:
            return frame

        # Modo checkbox: aplica filtros ativos em ordem
        if self.active_filters:
            # Ordem de aplicação otimizada
            order = ["brightness_up", "brightness_down", "bilateral", "clahe",
                     "super_res", "sharpen", "unsharp", "high_boost"]

            for filter_key in order:
                if filter_key in self.active_filters:
                    try:
                        method = getattr(self, f"_apply_{filter_key}", None)
                        if method:
                            frame = method(frame)
                    except Exception as e:
                        print(f"[FILTER] Erro ao aplicar {filter_key}: {e}")

            return frame

        # Modo dropdown (legado): aplica filtro único
        if self.current_filter == "original":
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
        if self.use_gpu:
            return self._gpu_unsharp(frame)

        # CPU: Blur gaussiano
        blurred = cv2.GaussianBlur(frame, (0, 0), 3)
        # Unsharp mask: original + k * (original - blur)
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

    def _apply_brightness_up(self, frame: np.ndarray) -> np.ndarray:
        """
        Aumenta o brilho da imagem (para ambientes escuros)

        Teoria: Ajusta o canal V (Value/Brightness) no espaço HSV
        para aumentar a luminosidade sem distorcer as cores.
        """
        if self.use_gpu:
            return self._gpu_brightness(frame, 30)

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        v = cv2.add(v, 30)
        hsv = cv2.merge([h, s, v])
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    def _apply_brightness_down(self, frame: np.ndarray) -> np.ndarray:
        """
        Diminui o brilho da imagem (para ambientes claros)

        Teoria: Ajusta o canal V (Value/Brightness) no espaço HSV
        para diminuir a luminosidade sem distorcer as cores.
        """
        if self.use_gpu:
            return self._gpu_brightness(frame, -30)

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        v = cv2.subtract(v, 30)
        hsv = cv2.merge([h, s, v])
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    def _apply_super_res(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica Supersampling 2x (Anti-Aliasing)

        Teoria: Upscale 2x com Lanczos cria pixels intermediários
        suaves, depois downscale com AREA averaging combina 4 pixels
        em 1, criando transições mais suaves entre cores.
        Resultado: mesma resolução, mas com aparência menos pixelada.
        """
        if self.use_gpu:
            return self._gpu_super_res(frame)

        h, w = frame.shape[:2]
        double_size = (w * 2, h * 2)
        original_size = (w, h)

        # Passo 1: Upscale 2x com Lanczos (cria pixels interpolados)
        upscaled = cv2.resize(frame, double_size, interpolation=cv2.INTER_LANCZOS4)

        # Passo 2: Downscale de volta com AREA (averaging de 4 pixels)
        downscaled = cv2.resize(upscaled, original_size, interpolation=cv2.INTER_AREA)

        return downscaled

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

    def _gpu_unsharp(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica Unsharp Mask usando GPU

        Unsharp = Original * 1.5 - Blurred * 0.5
        """
        try:
            kernel = self._gpu_kernels.get("gaussian")
            gpu_frame = cp.asarray(frame, dtype=cp.float32)

            # Aplica blur gaussiano em cada canal
            blurred = cp.zeros_like(gpu_frame)
            for i in range(3):
                blurred[:, :, i] = cp_ndimage.convolve(gpu_frame[:, :, i], kernel)

            # Unsharp: original * 1.5 - blur * 0.5
            result = gpu_frame * 1.5 - blurred * 0.5
            result = cp.clip(result, 0, 255).astype(cp.uint8)

            return cp.asnumpy(result)

        except Exception as e:
            print(f"[FILTER-GPU] Unsharp fallback CPU: {e}")
            blurred = cv2.GaussianBlur(frame, (0, 0), 3)
            return cv2.addWeighted(frame, 1.5, blurred, -0.5, 0)

    def _gpu_brightness(self, frame: np.ndarray, delta: int) -> np.ndarray:
        """
        Ajusta brilho usando GPU

        Args:
            frame: Frame BGR
            delta: Valor a adicionar (+30 ou -30)
        """
        try:
            gpu_frame = cp.asarray(frame, dtype=cp.int16)

            # Adiciona delta e clipa
            result = gpu_frame + delta
            result = cp.clip(result, 0, 255).astype(cp.uint8)

            return cp.asnumpy(result)

        except Exception as e:
            print(f"[FILTER-GPU] Brightness fallback CPU: {e}")
            if delta > 0:
                return cv2.add(frame, delta)
            else:
                return cv2.subtract(frame, abs(delta))

    def _gpu_super_res(self, frame: np.ndarray) -> np.ndarray:
        """
        Aplica Supersampling usando GPU

        Usa zoom do CuPy para upscale/downscale
        """
        try:
            gpu_frame = cp.asarray(frame, dtype=cp.float32)

            # Upscale 2x usando zoom (order=1 = linear, mais rápido)
            upscaled = cp_ndimage.zoom(gpu_frame, (2, 2, 1), order=1)

            # Downscale de volta (averaging)
            # Reshape para agrupar pixels 2x2 e fazer média
            h, w = frame.shape[:2]
            downscaled = upscaled.reshape(h, 2, w, 2, 3).mean(axis=(1, 3))
            downscaled = downscaled.astype(cp.uint8)

            return cp.asnumpy(downscaled)

        except Exception as e:
            print(f"[FILTER-GPU] SuperRes fallback CPU: {e}")
            h, w = frame.shape[:2]
            upscaled = cv2.resize(frame, (w * 2, h * 2), interpolation=cv2.INTER_LANCZOS4)
            return cv2.resize(upscaled, (w, h), interpolation=cv2.INTER_AREA)

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
