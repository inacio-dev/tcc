#!/usr/bin/env python3
"""
steering_manager.py - Sistema de Direção do Carrinho F1
Controla direção com servo MG996R via PCA9685

PINOUT PCA9685 + SERVO MG996R (DIREÇÃO):
=========================================
Pinos do módulo PCA9685: GND ; OE ; SCL ; SDA ; VCC ; V+

PCA9685 -> Raspberry Pi 4 (I2C) [COMPARTILHADO COM FREIOS]
  - GND    -> Pin 6 (GND)                [Terra comum]
  - OE     -> Pin 6 (GND)                [Output Enable - LOW = habilitado]
  - SCL    -> Pin 5 (GPIO3/SCL)          [I2C Clock]
  - SDA    -> Pin 3 (GPIO2/SDA)          [I2C Data]
  - VCC    -> Pin 1 (3.3V)               [Alimentação lógica do chip]
  - V+     -> UBEC OUT+ (5.25V)          [Alimentação dos servos]

Diagrama de conexão PCA9685:
                    PCA9685
                  ┌─────────┐
    GND (Pin 6) ──┤ GND     │
    GND (Pin 6) ──┤ OE      │  ← LOW = saídas habilitadas
    GPIO3 (Pin 5)─┤ SCL     │
    GPIO2 (Pin 3)─┤ SDA     │
    3.3V (Pin 1) ─┤ VCC     │
    UBEC OUT+  ───┤ V+      │  ← 5.25V para servos
                  └─────────┘

Servo Direção -> PCA9685
  - VCC (Vermelho)  -> V+ do PCA9685 (alimentado pelo UBEC)
  - GND (Marrom)    -> GND
  - Signal (Laranja)-> Canal 0 do PCA9685

ALIMENTAÇÃO DOS SERVOS - UBEC 15A:
==================================
O UBEC alimenta TODOS os servos (direção + freios) via V+ do PCA9685.

UBEC 15A (Pinos: IN+ ; IN- ; OUT+ ; OUT-)
  - IN+   -> Bateria 3S (+) via XT90     [9V-12.6V da bateria]
  - IN-   -> Bateria 3S (-) via XT90     [GND bateria]
  - OUT+  -> V+ do PCA9685               [5.25V para servos]
  - OUT-  -> GND comum do sistema        [Terra]

Diagrama de alimentação:
    Bateria 3S (11.1V)
         │
    ┌────┴────┐
    │  UBEC   │
    │  15A    │
    └────┬────┘
         │ 5.25V
    ┌────┴────┐
    │ PCA9685 │──── Servo Direção (Canal 2)
    │   V+    │──── Servo Freio Frontal (Canal 0)
    └─────────┘──── Servo Freio Traseiro (Canal 1)

CARACTERÍSTICAS UBEC 15A:
=========================
  - Tensão de Entrada: 6-12S (23V a 45V) [Usando 3S: 9V-12.6V]
  - Tensão de Saída: 5.25V ±0.5V
  - Corrente Contínua: 15A (suficiente para 3 servos ~4.5A)
  - Corrente de Pico: 30A (10 segundos)
  - Dimensões: 55 x 28 x 5 mm

MAPEAMENTO COMPLETO DOS CANAIS PCA9685:
======================================
Canal 0: Direção (steering_manager.py) <-- ESTE ARQUIVO
Canal 4: Freio frontal (brake_manager.py)
Canal 8: Freio traseiro (brake_manager.py)
Demais canais: Disponíveis para expansão

CARACTERÍSTICAS MG996R (DIREÇÃO):
=================================
- Tensão: 4.8V - 7.2V (recomendado 6V)
- Torque: 11kg.cm @ 6V (suficiente para direção)
- Velocidade: 0.14s/60° @ 6V
- Ângulo útil: 0° - 180° (90° = centro)
- PWM: 50Hz, pulso 1.0ms-2.0ms
- Corrente: ~1.5A sob carga

CONFIGURAÇÃO MECÂNICA:
=====================
- 0° = Máximo à esquerda
- 90° = Centro (frente)
- 180° = Máximo à direita
- Range útil: 0° a 180° (±90° do centro)
- Ackermann: Geometria de direção correta para F1

CONFIGURAÇÃO NECESSÁRIA:
=======================
sudo raspi-config -> Interface Options -> I2C -> Enable
sudo pip3 install adafruit-circuitpython-pca9685
"""

import threading
import time
from enum import Enum
from typing import Any, Dict

from logger import debug, error, info, warn

try:
    import board
    import busio
    from adafruit_motor import servo
    from adafruit_pca9685 import PCA9685

    PCA9685_AVAILABLE = True
    info("PCA9685 disponível", "STEERING")
except ImportError:
    error("PCA9685 não disponível - instale: sudo pip3 install adafruit-circuitpython-pca9685", "STEERING")
    PCA9685_AVAILABLE = False
    exit(1)  # Para execução se PCA9685 não disponível


class SteeringMode(Enum):
    """Modos de direção"""

    NORMAL = "normal"  # Direção normal
    SPORT = "sport"  # Direção esportiva (mais sensível)
    COMFORT = "comfort"  # Direção confortável (menos sensível)
    PARKING = "parking"  # Assistência para estacionamento


class SteeringManager:
    """Gerencia sistema de direção do carrinho F1 via PCA9685"""

    # ================== CONFIGURAÇÕES FÍSICAS ==================

    # Canal PCA9685 do servo de direção
    STEERING_CHANNEL = 0  # Canal 0 do PCA9685

    # Endereço I2C do PCA9685 (compartilhado com brake_manager)
    PCA9685_I2C_ADDRESS = 0x41  # PCA9685 com A0 soldado (evita conflito com INA219 em 0x40)

    # Características do servo MG996R
    PWM_FREQUENCY = 50  # 50Hz para servos
    PULSE_MIN = 1.0  # 1.0ms = 0° (máximo esquerda)
    PULSE_MAX = 2.0  # 2.0ms = 180° (máximo direita)
    PULSE_CENTER = 1.5  # 1.5ms = 90° (centro)

    # Limites mecânicos da direção (em graus) - RANGE LIMITADO 0° a 113.4°
    STEERING_MIN_ANGLE = 0  # 0° = máximo à esquerda
    STEERING_MAX_ANGLE = 113.4  # 113.4° = máximo à direita
    STEERING_CENTER = 56.7  # 56.7° = posição central (meio do range 0-113.4°)

    # Range de direção útil (LIMITADO 0°-113.4°)
    MAX_STEERING_LEFT = -56.7  # -56.7° (esquerda máxima: 56.7°-56.7°=0°)
    MAX_STEERING_RIGHT = 56.7  # +56.7° (direita máxima: 56.7°+56.7°=113.4°)

    def __init__(
        self,
        steering_channel: int = None,
        pca9685_address: int = None,
        steering_sensitivity: float = 1.0,
        max_steering_angle: float = 90.0,  # RANGE COMPLETO
        steering_mode: SteeringMode = SteeringMode.NORMAL,
        response_time: float = 0.15,
        i2c_lock=None,  # Lock compartilhado do bus I2C
    ):
        """
        Inicializa o gerenciador de direção

        Args:
            steering_channel (int): Canal PCA9685 do servo de direção
            pca9685_address (int): Endereço I2C do PCA9685
            steering_sensitivity (float): Sensibilidade da direção (0.5-2.0)
            max_steering_angle (float): Ângulo máximo de esterçamento
            steering_mode (SteeringMode): Modo de direção
            response_time (float): Tempo de resposta da direção
            i2c_lock: threading.Lock compartilhado entre dispositivos I2C
        """
        self.i2c_lock = i2c_lock
        self.steering_channel = steering_channel or self.STEERING_CHANNEL
        self.pca9685_address = pca9685_address or self.PCA9685_I2C_ADDRESS

        # Lock para thread-safety (acesso concorrente por threads de comando e TX)
        self.state_lock = threading.Lock()

        # Configurações
        self.steering_sensitivity = max(0.5, min(2.0, steering_sensitivity))
        self.max_steering_angle = max(
            10.0, min(56.7, max_steering_angle)
        )  # Máximo 56.7° (range 0-113.4°)
        self.steering_mode = steering_mode
        self.response_time = max(0.05, response_time)

        # Estado da direção
        self.is_initialized = False
        self.current_angle = 0.0  # Ângulo atual (-56.7° a +56.7°)
        self.target_angle = 0.0  # Ângulo alvo
        self.servo_angle = self.STEERING_CENTER  # Ângulo do servo (0° a 113.4°)
        self.steering_input = 0.0  # Input de direção (-100% a +100%)

        # Controle PCA9685
        self.pca9685 = None
        self.i2c = None
        self.steering_servo = None

        # Estado da direção

        # Estatísticas
        self.total_steering_movements = 0
        self.total_steering_angle = 0.0
        self.max_angle_reached = 0.0
        self.start_time = time.time()
        self.last_movement_time = 0.0
        self._last_log_time = 0.0
        self._last_servo_angle = None  # Dedup I2C writes

    def initialize(self) -> bool:
        """
        Inicializa o sistema de direção via PCA9685

        Returns:
            bool: True se inicializado com sucesso
        """
        info(f"Inicializando direção | Canal: {self.steering_channel} | I2C: 0x{self.pca9685_address:02X} | Modo: {self.steering_mode.value.upper()} | Sens: {self.steering_sensitivity:.1f}x | ±{self.max_steering_angle}°", "STEERING")

        try:
            # Inicializa barramento I2C (pode ser compartilhado com brake_manager)
            self.i2c = busio.I2C(board.SCL, board.SDA)
            self.pca9685 = PCA9685(self.i2c, address=self.pca9685_address)
            self.pca9685.frequency = self.PWM_FREQUENCY
            self.steering_servo = servo.Servo(
                self.pca9685.channels[self.steering_channel],
                min_pulse=int(self.PULSE_MIN * 1000),  # converte para microssegundos
                max_pulse=int(self.PULSE_MAX * 1000),
            )

            # Posiciona servo na posição central
            if self.i2c_lock:
                self.i2c_lock.acquire(priority=0)
                try:
                    self.steering_servo.angle = self.STEERING_CENTER
                finally:
                    self.i2c_lock.release()
            else:
                self.steering_servo.angle = self.STEERING_CENTER

            # Aguarda servo se posicionar
            time.sleep(0.5)

            self.is_initialized = True
            info(f"Direção inicializada | PWM: {self.PWM_FREQUENCY}Hz | Canal: {self.steering_channel}", "STEERING")

            # Teste rápido da direção
            self._test_steering()

            return True

        except Exception as e:
            error(f"Erro ao inicializar direção: {e} | Verifique: PCA9685 I2C, canal servo, alimentação 6V", "STEERING")

            self.is_initialized = False
            return False

    def set_steering_input(self, steering_input: float):
        """
        Define entrada de direção

        Args:
            steering_input (float): Entrada de direção -100% a +100%
                                  (-100% = máximo esquerda, +100% = máximo direita)
        """
        if not self.is_initialized:
            return

        # Garante range válido
        steering_input = max(-100.0, min(100.0, steering_input))

        with self.state_lock:
            self.steering_input = steering_input

            # MOVIMENTO DIRETO - converte entrada (-100% a +100%) para ângulo (-56.7° a +56.7°)
            target_angle = (steering_input / 100.0) * self.max_steering_angle

            self.target_angle = target_angle

            # MOVIMENTO DIRETO - igual aos testes funcionais
            self.current_angle = target_angle
            self.servo_angle = self.STEERING_CENTER + self.current_angle

            # Aplica movimento DIRETO ao servo
            if self.steering_servo:
                # Limita ângulo ao range válido do servo (0° a 113.4°)
                final_angle = max(
                    self.STEERING_MIN_ANGLE,
                    min(self.STEERING_MAX_ANGLE, self.servo_angle),
                )

                # Só escreve no I2C se o ângulo mudou (dedup)
                if self._last_servo_angle is None or abs(final_angle - self._last_servo_angle) >= 0.1:
                    if self.i2c_lock:
                        self.i2c_lock.acquire(priority=0)  # Alta
                        try:
                            self.steering_servo.angle = final_angle
                        finally:
                            self.i2c_lock.release()
                    else:
                        self.steering_servo.angle = final_angle
                    self._last_servo_angle = final_angle

                # Log rate limited a cada 1s
                now = time.time()
                if now - self._last_log_time >= 1.0 and abs(steering_input) > 0:
                    self._last_log_time = now
                    debug(f"Direção: {steering_input:.1f}% → {final_angle:.1f}°", "STEERING")
            else:
                warn("Servo não inicializado!", "STEERING")

            # Atualiza estatísticas
            if abs(steering_input) > 5:  # Movimento significativo
                self.total_steering_movements += 1
                self.total_steering_angle += abs(target_angle)
                self.max_angle_reached = max(self.max_angle_reached, abs(target_angle))
                self.last_movement_time = time.time()


    # REMOVIDO: funções auxiliares não usadas - movimento direto

    def center_steering(self):
        """Centraliza a direção"""
        self.set_steering_input(0.0)
        debug("Direção centralizada", "STEERING")

    def _test_steering(self):
        """Executa teste rápido da direção - MOVIMENTO DIRETO"""
        debug("Executando teste da direção...", "STEERING")

        try:
            self.set_steering_input(-50.0)
            time.sleep(0.8)
            self.center_steering()
            time.sleep(0.8)
            self.set_steering_input(50.0)
            time.sleep(0.8)
            self.center_steering()
            time.sleep(0.5)
            debug("Teste da direção concluído", "STEERING")

        except Exception as e:
            warn(f"Erro durante teste: {e}", "STEERING")

    def get_steering_status(self) -> Dict[str, Any]:
        """
        Obtém status completo da direção

        Returns:
            dict: Status atual da direção
        """
        with self.state_lock:
            return {
                # === CONFIGURAÇÃO ===
                "steering_mode": self.steering_mode.value,
                "steering_sensitivity": round(self.steering_sensitivity, 2),
                "max_steering_angle": round(self.max_steering_angle, 1),
                "response_time": round(self.response_time, 3),
                # === ESTADO ATUAL ===
                "steering_input": round(self.steering_input, 1),
                "current_angle": round(self.current_angle, 1),
                "target_angle": round(self.target_angle, 1),
                "servo_angle": round(self.servo_angle, 1),
                # === ÂNGULOS EM DIFERENTES FORMATOS ===
                "angle_degrees": round(self.current_angle, 1),
                "angle_percent": round(
                    (self.current_angle / self.max_steering_angle) * 100, 1
                ),
                "steering_left": self.current_angle < -2.0,
                "steering_right": self.current_angle > 2.0,
                "steering_center": abs(self.current_angle) <= 2.0,
                # === STATUS TÉCNICO ===
                "is_initialized": self.is_initialized,
                # === ESTATÍSTICAS ===
                "total_movements": self.total_steering_movements,
                "max_angle_reached": round(self.max_angle_reached, 1),
                "last_movement_time": self.last_movement_time,
                # === HARDWARE ===
                "steering_channel": self.steering_channel,
                "pca9685_address": f"0x{self.pca9685_address:02X}",
                "pwm_frequency": self.PWM_FREQUENCY,
                "pca9685_available": PCA9685_AVAILABLE,
                # === TIMESTAMP ===
                "timestamp": round(time.time(), 3),
            }

    def get_wheel_angles(self) -> Dict[str, float]:
        """
        Calcula ângulos individuais das rodas (Ackermann)

        Returns:
            dict: Ângulos das rodas esquerda e direita
        """
        # Retorna ângulos simples (Ackermann desabilitado)
        return {
            "left_wheel": round(self.current_angle, 1),
            "right_wheel": round(self.current_angle, 1),
            "turn_radius": float("inf"),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Obtém estatísticas de uso da direção

        Returns:
            dict: Estatísticas de operação
        """
        elapsed = time.time() - self.start_time

        return {
            "total_movements": self.total_steering_movements,
            "total_steering_angle": round(self.total_steering_angle, 1),
            "max_angle_reached": round(self.max_angle_reached, 1),
            "average_angle": round(
                self.total_steering_angle / max(1, self.total_steering_movements), 1
            ),
            "movements_per_minute": (
                round(self.total_steering_movements / (elapsed / 60), 1)
                if elapsed > 0
                else 0
            ),
            "system_uptime": round(elapsed, 2),
            "steering_mode": self.steering_mode.value,
        }

    def cleanup(self):
        """Libera recursos da direção"""
        try:
            debug("Finalizando sistema de direção...", "STEERING")

            # Centraliza direção antes de desligar
            self.center_steering()
            time.sleep(0.2)

            # Libera recursos do PCA9685
            if self.steering_servo:
                self.steering_servo = None
            if self.pca9685:
                self.pca9685.deinit()
                self.pca9685 = None
            if self.i2c:
                self.i2c.deinit()
                self.i2c = None

            self.is_initialized = False
            info("Sistema de direção finalizado", "STEERING")

        except Exception as e:
            warn(f"Erro ao finalizar direção: {e}", "STEERING")

    def __del__(self):
        """Destrutor - garante limpeza dos recursos"""
        self.cleanup()
