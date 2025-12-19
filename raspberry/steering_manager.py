#!/usr/bin/env python3
"""
steering_manager.py - Sistema de Direção do Carrinho F1
Controla direção com servo MG996R via PCA9685

PINOUT PCA9685 + SERVO MG996R (DIREÇÃO):
=========================================
PCA9685 -> Raspberry Pi 4 (I2C) [COMPARTILHADO COM FREIOS]
- VCC    -> Pin 2 (5V) ou fonte externa 6V
- GND    -> Pin 6 (GND)
- SCL    -> Pin 5 (GPIO3/SCL)
- SDA    -> Pin 3 (GPIO2/SDA)

Servo Direção -> PCA9685
- VCC (Vermelho)  -> V+ (fonte externa 6V recomendada)
- GND (Marrom)    -> GND
- Signal (Laranja)-> Canal 2 do PCA9685

MAPEAMENTO COMPLETO DOS CANAIS PCA9685:
======================================
Canal 0: Freio frontal (brake_manager.py)
Canal 1: Freio traseiro (brake_manager.py)
Canal 2: Direção (steering_manager.py) <-- ESTE ARQUIVO
Canais 3-15: Disponíveis para expansão

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

try:
    import board
    import busio
    from adafruit_motor import servo
    from adafruit_pca9685 import PCA9685

    PCA9685_AVAILABLE = True
    print("✓ PCA9685 disponível")
except ImportError:
    print(
        "❌ PCA9685 não disponível - instale: sudo pip3 install adafruit-circuitpython-pca9685"
    )
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
    STEERING_CHANNEL = 2  # Canal 2 do PCA9685

    # Endereço I2C do PCA9685 (compartilhado com brake_manager)
    PCA9685_I2C_ADDRESS = 0x40  # Endereço padrão do PCA9685

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
        """
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

    def initialize(self) -> bool:
        """
        Inicializa o sistema de direção via PCA9685

        Returns:
            bool: True se inicializado com sucesso
        """
        print("Inicializando sistema de direção via PCA9685...")
        print(f"Servo direção: Canal {self.steering_channel} do PCA9685")
        print(f"Endereço I2C: 0x{self.pca9685_address:02X}")
        print(f"Modo: {self.steering_mode.value.upper()}")
        print(f"Sensibilidade: {self.steering_sensitivity:.1f}x")
        print(f"Ângulo máximo: ±{self.max_steering_angle}°")
        print("Geometria Ackermann: DESABILITADA (movimento direto)")

        try:
            # Inicializa barramento I2C (pode ser compartilhado com brake_manager)
            self.i2c = busio.I2C(board.SCL, board.SDA)
            print("✓ Barramento I2C inicializado")

            # Inicializa PCA9685
            self.pca9685 = PCA9685(self.i2c, address=self.pca9685_address)
            self.pca9685.frequency = self.PWM_FREQUENCY
            print(f"✓ PCA9685 inicializado @ {self.PWM_FREQUENCY}Hz")

            # Configura servo no canal especificado
            self.steering_servo = servo.Servo(
                self.pca9685.channels[self.steering_channel],
                min_pulse=int(self.PULSE_MIN * 1000),  # converte para microssegundos
                max_pulse=int(self.PULSE_MAX * 1000),
            )
            print(f"✓ Servo direção configurado (canal {self.steering_channel})")

            # Posiciona servo na posição central
            self.steering_servo.angle = self.STEERING_CENTER
            print(f"✓ Servo posicionado na posição central ({self.STEERING_CENTER}°)")

            # Aguarda servo se posicionar
            time.sleep(0.5)

            self.is_initialized = True

            print("✅ Sistema de direção inicializado com sucesso!")
            print(f"  - Frequência PWM: {self.PWM_FREQUENCY}Hz")
            print(f"  - Posição inicial: {self.STEERING_CENTER}° (centro)")
            print(
                f"  - Range: {self.STEERING_MIN_ANGLE}° a {self.STEERING_MAX_ANGLE}° (LIMITADO 0-113.4°)"
            )
            print("  - Movimento: DIRETO (sem suavização)")
            print(f"  - Canal direção: {self.steering_channel}")

            # Teste rápido da direção
            self._test_steering()

            return True

        except Exception as e:
            print(f"❌ Erro ao inicializar direção: {e}")
            print("\nVerifique:")
            print("1. Conexões do PCA9685 (VCC, GND, SDA, SCL)")
            print("2. Conexão do servo no PCA9685 (canal correto)")
            print("3. Alimentação do servo (fonte externa 6V recomendada)")
            print("4. sudo raspi-config -> Interface Options -> I2C -> Enable")
            print("5. sudo pip3 install adafruit-circuitpython-pca9685")

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
            print("⚠ Sistema de direção não inicializado")
            return

        print(f"🏎️ DIREÇÃO: {steering_input:.1f}% recebido")

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

                # COMANDO DIRETO - igual ao test_steering_direto_simples.py
                self.steering_servo.angle = final_angle

                print(
                    f"🎯 Target: {target_angle:.1f}° → Servo: {final_angle:.1f}° (input: {steering_input:.1f}%)"
                )
            else:
                print("⚠️ Servo não inicializado!")

            print(
                f"🎯 Target angle definido: {target_angle:.1f}° (input: {steering_input:.1f}%)"
            )

            # Atualiza estatísticas
            if abs(steering_input) > 5:  # Movimento significativo
                self.total_steering_movements += 1
                self.total_steering_angle += abs(target_angle)
                self.max_angle_reached = max(self.max_angle_reached, abs(target_angle))
                self.last_movement_time = time.time()

        # Debug para movimentos grandes
        if abs(steering_input) > 20:
            print(f"🔧 Direção: {steering_input:+.0f}% → {target_angle:+.1f}°")

    # REMOVIDO: funções auxiliares não usadas - movimento direto

    def center_steering(self):
        """Centraliza a direção"""
        self.set_steering_input(0.0)
        print("🔧 Direção centralizada")

    def _test_steering(self):
        """Executa teste rápido da direção - MOVIMENTO DIRETO"""
        print("Executando teste da direção...")

        try:
            # Teste esquerda
            print("  - Testando direção esquerda...")
            self.set_steering_input(-50.0)  # 50% esquerda
            time.sleep(0.8)

            # Centro
            print("  - Retornando ao centro...")
            self.center_steering()
            time.sleep(0.8)

            # Teste direita
            print("  - Testando direção direita...")
            self.set_steering_input(50.0)  # 50% direita
            time.sleep(0.8)

            # Centro final
            self.center_steering()
            time.sleep(0.5)

            print("✓ Teste da direção concluído")

        except Exception as e:
            print(f"⚠ Erro durante teste: {e}")

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
            print("Finalizando sistema de direção...")

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
            print("✓ Sistema de direção finalizado")

        except Exception as e:
            print(f"⚠ Erro ao finalizar direção: {e}")

    def __del__(self):
        """Destrutor - garante limpeza dos recursos"""
        self.cleanup()
