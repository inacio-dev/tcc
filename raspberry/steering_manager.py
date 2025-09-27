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

import math
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

    # Limites mecânicos da direção (em graus) - RANGE COMPLETO MG996R
    STEERING_MIN_ANGLE = 0   # 0° = máximo à esquerda
    STEERING_MAX_ANGLE = 180 # 180° = máximo à direita
    STEERING_CENTER = 90     # 90° = posição central

    # Range de direção útil (COMPLETO 0°-180°)
    MAX_STEERING_LEFT = -90  # -90° (esquerda máxima: 90°-90°=0°)
    MAX_STEERING_RIGHT = 90  # +90° (direita máxima: 90°+90°=180°)

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

        # Configurações
        self.steering_sensitivity = max(0.5, min(2.0, steering_sensitivity))
        self.max_steering_angle = max(10.0, min(90.0, max_steering_angle))  # Máximo 90° (range completo)
        self.steering_mode = steering_mode
        self.response_time = max(0.05, response_time)

        # Estado da direção
        self.is_initialized = False
        self.current_angle = 0.0  # Ângulo atual (-90° a +90°)
        self.target_angle = 0.0  # Ângulo alvo
        self.servo_angle = self.STEERING_CENTER  # Ângulo do servo (0° a 180°)
        self.steering_input = 0.0  # Input de direção (-100% a +100%)

        # Controle PCA9685
        self.pca9685 = None
        self.i2c = None
        self.steering_servo = None

        # REMOVIDO: movimento suave - usando movimento direto

        # REMOVIDO: Sistema Ackermann - usando movimento direto
        # REMOVIDO: Compensação de velocidade - usando movimento direto

        # Estatísticas
        self.total_steering_movements = 0
        self.total_steering_angle = 0.0
        self.max_angle_reached = 0.0
        self.start_time = time.time()
        self.last_movement_time = 0.0

        # REMOVIDO: Calibração - usando movimento direto
        # REMOVIDO: Limites de segurança - usando movimento direto
        # REMOVIDO: Emergency center - usando movimento direto

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

            # REMOVIDO: thread de movimento suave - usando movimento direto

            self.is_initialized = True

            print("✅ Sistema de direção inicializado com sucesso!")
            print(f"  - Frequência PWM: {self.PWM_FREQUENCY}Hz")
            print(f"  - Posição inicial: {self.STEERING_CENTER}° (centro)")
            print(f"  - Range: {self.STEERING_MIN_ANGLE}° a {self.STEERING_MAX_ANGLE}° (COMPLETO)")
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

    # REMOVIDO: funções de movimento suave - usando movimento direto

    def set_steering_input(self, steering_input: float, speed_kmh: float = 0.0):
        """
        Define entrada de direção

        Args:
            steering_input (float): Entrada de direção -100% a +100%
                                  (-100% = máximo esquerda, +100% = máximo direita)
            speed_kmh (float): Velocidade atual em km/h para compensação
        """
        if not self.is_initialized:
            print("⚠ Sistema de direção não inicializado")
            return

        print(f"🏎️ DIREÇÃO: {steering_input:.1f}% recebido")

        # REMOVIDO: parada de emergência - movimento direto

        # Garante range válido
        steering_input = max(-100.0, min(100.0, steering_input))
        self.steering_input = steering_input

        # MOVIMENTO DIRETO - converte entrada (-100% a +100%) para ângulo (-90° a +90°)
        target_angle = (steering_input / 100.0) * self.max_steering_angle

        # REMOVIDO: Limites de segurança - usar range completo
        # REMOVIDO: Geometria Ackermann - movimento direto sem correções

        self.target_angle = target_angle

        # MOVIMENTO DIRETO - igual aos testes funcionais
        self.current_angle = target_angle
        self.servo_angle = self.STEERING_CENTER + self.current_angle

        # Aplica movimento DIRETO ao servo
        if self.steering_servo:
            # Limita ângulo ao range válido do servo (0° a 180°)
            final_angle = max(
                self.STEERING_MIN_ANGLE,
                min(self.STEERING_MAX_ANGLE, self.servo_angle),
            )

            # COMANDO DIRETO - igual ao test_steering_direto_simples.py
            self.steering_servo.angle = final_angle

            print(f"🎯 Target: {target_angle:.1f}° → Servo: {final_angle:.1f}° (input: {steering_input:.1f}%)")
        else:
            print(f"⚠️ Servo não inicializado!")

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
            print(
                f"🔧 Direção: {steering_input:+.0f}% → {target_angle:+.1f}° "
                f"(Velocidade: {speed_kmh:.1f} km/h)"
            )

    # REMOVIDO: funções auxiliares não usadas - movimento direto

    def center_steering(self):
        """Centraliza a direção"""
        self.set_steering_input(0.0)
        print("🔧 Direção centralizada")

    # REMOVIDO: funções não usadas - movimento direto

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

    # REMOVIDO: calibração - movimento direto

    def get_steering_status(self) -> Dict[str, Any]:
        """
        Obtém status completo da direção

        Returns:
            dict: Status atual da direção
        """
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
            # === MOVIMENTO DIRETO (sem compensações) ===
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
        # REMOVIDO: ackermann sempre desabilitado - retorna ângulos simples
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
            # REMOVIDO: calibração não usada
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


# Exemplo de uso
if __name__ == "__main__":
    print("=== TESTE DO SISTEMA DE DIREÇÃO ===")

    # Cria instância da direção com PCA9685
    steering_mgr = SteeringManager(
        steering_channel=2,  # Canal 2 do PCA9685 para direção
        pca9685_address=0x40,  # Endereço I2C padrão do PCA9685 (compartilhado)
        steering_sensitivity=1.2,
        max_steering_angle=40.0,
        steering_mode=SteeringMode.SPORT,
        response_time=0.12,
    )

    # Inicializa
    if steering_mgr.initialize():
        print("\n=== TESTE DE DIREÇÃO ===")

        # Teste 1: Movimento progressivo
        print("1. Teste de movimento progressivo...")
        for angle in [-100, -50, -25, 0, 25, 50, 100, 50, 0]:
            print(f"   Direção: {angle:+3.0f}%")
            steering_mgr.set_steering_input(angle, speed_kmh=20.0)
            time.sleep(1.0)

            status = steering_mgr.get_steering_status()
            wheels = steering_mgr.get_wheel_angles()

            print(
                f"   Ângulo: {status['current_angle']:+.1f}°, "
                f"Rodas: E={wheels['left_wheel']:+.1f}° D={wheels['right_wheel']:+.1f}°"
            )

        # Teste 2: Diferentes modos
        print("\n2. Teste de modos de direção...")
        steering_mgr.set_steering_input(50.0, speed_kmh=30.0)  # 50% direita

        for mode in [SteeringMode.COMFORT, SteeringMode.NORMAL, SteeringMode.SPORT]:
            print(f"   Modo: {mode.value.upper()}")
            steering_mgr.set_steering_mode(mode)
            steering_mgr.set_steering_input(50.0, speed_kmh=30.0)
            time.sleep(0.8)

            status = steering_mgr.get_steering_status()
            print(f"   Ângulo resultante: {status['current_angle']:+.1f}°")

        # Teste 3: Compensação de velocidade
        print("\n3. Teste de compensação de velocidade...")
        steering_mgr.set_steering_mode(SteeringMode.NORMAL)

        for speed in [0, 10, 20, 40, 60]:
            print(f"   Velocidade: {speed} km/h")
            steering_mgr.set_steering_input(75.0, speed_kmh=speed)
            time.sleep(0.5)

            status = steering_mgr.get_steering_status()
            print(f"   Ângulo com compensação: {status['current_angle']:+.1f}°")

        # Teste 4: Geometria Ackermann
        print("\n4. Teste de geometria Ackermann...")
        steering_mgr.set_steering_input(60.0, speed_kmh=25.0)
        time.sleep(1.0)

        wheels = steering_mgr.get_wheel_angles()
        print("   Entrada: 60% direita")
        print(f"   Roda esquerda (externa): {wheels['left_wheel']:+.1f}°")
        print(f"   Roda direita (interna): {wheels['right_wheel']:+.1f}°")
        print(f"   Raio de curvatura: {wheels['turn_radius']:.2f}m")

        # Centraliza
        steering_mgr.center_steering()
        time.sleep(1.0)

        # Estatísticas finais
        stats = steering_mgr.get_statistics()
        print("\n=== ESTATÍSTICAS FINAIS ===")
        print(f"Movimentos de direção: {stats['total_movements']}")
        print(f"Ângulo total percorrido: {stats['total_steering_angle']:.1f}°")
        print(f"Ângulo máximo atingido: {stats['max_angle_reached']:.1f}°")
        print(f"Ângulo médio: {stats['average_angle']:.1f}°")
        print(f"Movimentos/minuto: {stats['movements_per_minute']:.1f}")

        # Finaliza
        steering_mgr.cleanup()

    else:
        print("✗ Falha ao inicializar direção")
        print("\nPara usar com hardware real:")
        print("1. Conecte servo conforme pinout no cabeçalho")
        print("2. Fonte de alimentação adequada (5V-6V)")
        print("3. sudo apt-get install python3-rpi.gpio")
        print("4. Verifique conexões e calibração mecânica")
