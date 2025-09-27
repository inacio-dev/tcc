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
        max_steering_angle: float = 45.0,
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

        # Controle de movimento suave
        self.smooth_movement = False  # DESABILITADO - movimento direto igual aos testes
        self.movement_thread = None
        self.should_stop = False

        # Sistema Ackermann (geometria de direção)
        self.ackermann_enabled = True
        self.wheelbase = 0.25  # Distância entre eixos (metros, escala 1:10)
        self.track_width = 0.15  # Largura da bitola (metros)

        # Compensação baseada na velocidade
        self.speed_compensation = True
        self.current_speed = 0.0  # km/h (recebido externamente)
        self.speed_compensation_factor = 0.7

        # Estatísticas
        self.total_steering_movements = 0
        self.total_steering_angle = 0.0
        self.max_angle_reached = 0.0
        self.start_time = time.time()
        self.last_movement_time = 0.0

        # Calibração
        self.center_calibrated = False
        self.calibration_offset = 0.0

        # Limites de segurança
        self.steering_limit_enabled = True
        self.emergency_center = False

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
        print(
            f"Geometria Ackermann: {'Ativada' if self.ackermann_enabled else 'Desativada'}"
        )

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

            # Inicia thread de movimento suave
            if self.smooth_movement:
                self._start_movement_thread()

            self.is_initialized = True

            print("✅ Sistema de direção inicializado com sucesso!")
            print(f"  - Frequência PWM: {self.PWM_FREQUENCY}Hz")
            print(f"  - Posição inicial: {self.STEERING_CENTER}° (centro)")
            print(f"  - Range: {self.STEERING_MIN_ANGLE}° a {self.STEERING_MAX_ANGLE}° (COMPLETO)")
            print(
                f"  - Movimento suave: {'Ativado' if self.smooth_movement else 'Desativado'}"
            )
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

    def _start_movement_thread(self):
        """Inicia thread para movimento suave da direção"""
        if self.movement_thread is None or not self.movement_thread.is_alive():
            self.should_stop = False
            self.movement_thread = threading.Thread(target=self._smooth_movement_loop)
            self.movement_thread.daemon = True
            self.movement_thread.start()

    def _smooth_movement_loop(self):
        """Loop principal para movimento suave da direção"""
        while not self.should_stop and self.is_initialized:
            try:
                # Velocidade de movimento baseada no tempo de resposta
                max_speed = 90.0 / self.response_time  # graus/segundo
                move_speed = max_speed * 0.02  # graus por iteração (50Hz)

                # Movimento suave em direção ao ângulo alvo
                angle_diff = self.target_angle - self.current_angle

                if abs(angle_diff) > 0.5:  # Threshold de movimento
                    if angle_diff > 0:
                        self.current_angle = min(
                            self.current_angle + move_speed, self.target_angle
                        )
                    else:
                        self.current_angle = max(
                            self.current_angle - move_speed, self.target_angle
                        )

                    # Converte ângulo de direção (-90° a +90°) para ângulo do servo (0° a 180°)
                    self.servo_angle = self.STEERING_CENTER + self.current_angle

                    # Aplica calibração
                    calibrated_angle = self.servo_angle + self.calibration_offset

                    # Aplica movimento ao servo (apenas se PCA9685 disponível)
                    if self.steering_servo:
                        # Limita ângulo ao range válido do servo
                        final_angle = max(
                            self.STEERING_MIN_ANGLE,
                            min(self.STEERING_MAX_ANGLE, calibrated_angle),
                        )

                        self.steering_servo.angle = final_angle

                time.sleep(0.02)  # 50Hz de atualização

            except Exception as e:
                print(f"⚠ Erro no movimento da direção: {e}")
                time.sleep(0.1)

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

        # Verifica parada de emergência
        if self.emergency_center:
            steering_input = 0.0

        # Garante range válido
        steering_input = max(-100.0, min(100.0, steering_input))
        self.steering_input = steering_input
        self.current_speed = speed_kmh

        # Aplica sensibilidade baseada no modo
        effective_sensitivity = self._get_mode_sensitivity() * self.steering_sensitivity

        # Aplica compensação de velocidade
        if self.speed_compensation and speed_kmh > 0:
            speed_factor = 1.0 - (speed_kmh / 50.0) * self.speed_compensation_factor
            speed_factor = max(0.3, min(1.0, speed_factor))  # Limita compensação
            effective_sensitivity *= speed_factor

        # Converte entrada (-100% a +100%) para ângulo (-90° a +90°)
        target_angle = (
            (steering_input / 100.0) * self.max_steering_angle * effective_sensitivity
        )

        # Aplica limites de segurança
        if self.steering_limit_enabled:
            target_angle = max(
                self.MAX_STEERING_LEFT, min(self.MAX_STEERING_RIGHT, target_angle)
            )

        # Geometria Ackermann (opcional)
        if self.ackermann_enabled:
            target_angle = self._apply_ackermann_geometry(target_angle)

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

    def _get_mode_sensitivity(self) -> float:
        """Obtém fator de sensibilidade baseado no modo"""
        sensitivity_map = {
            SteeringMode.COMFORT: 0.7,  # Menos sensível
            SteeringMode.NORMAL: 1.0,  # Sensibilidade normal
            SteeringMode.SPORT: 1.3,  # Mais sensível
            SteeringMode.PARKING: 1.5,  # Máxima sensibilidade
        }
        return sensitivity_map.get(self.steering_mode, 1.0)

    def _apply_ackermann_geometry(self, target_angle: float) -> float:
        """
        Aplica correção de geometria Ackermann

        Args:
            target_angle (float): Ângulo alvo em graus

        Returns:
            float: Ângulo corrigido
        """
        if abs(target_angle) < 5.0:  # Não aplica para ângulos pequenos
            return target_angle

        # Conversão para radianos
        target_rad = math.radians(target_angle)

        # Cálculo do raio de curvatura
        try:
            # R = wheelbase / tan(steering_angle)
            turn_radius = self.wheelbase / math.tan(abs(target_rad))

            # Correção Ackermann para roda interna
            # Ângulo corrigido considera diferença entre rodas interna e externa
            ackermann_correction = math.atan(
                self.wheelbase / (turn_radius - self.track_width / 2)
            )

            # Aplica correção (pequena para modelos em escala)
            corrected_angle = math.degrees(ackermann_correction)
            correction_factor = 0.1  # Correção sutil

            if target_angle >= 0:
                return (
                    target_angle
                    + (corrected_angle - abs(target_angle)) * correction_factor
                )
            else:
                return (
                    target_angle
                    - (corrected_angle - abs(target_angle)) * correction_factor
                )

        except (ZeroDivisionError, ValueError):
            return target_angle

    def center_steering(self):
        """Centraliza a direção"""
        self.set_steering_input(0.0)
        print("🔧 Direção centralizada")

    def emergency_center(self):
        """Centraliza direção em emergência"""
        self.emergency_center = True
        self.center_steering()
        print("🚨 CENTRALIZAÇÃO DE EMERGÊNCIA DA DIREÇÃO!")

    def release_emergency(self):
        """Libera modo de emergência"""
        self.emergency_center = False
        print("✓ Modo de emergência da direção liberado")

    def set_steering_mode(self, mode: SteeringMode):
        """
        Altera modo de direção

        Args:
            mode (SteeringMode): Novo modo de direção
        """
        old_mode = self.steering_mode
        self.steering_mode = mode
        print(f"🔧 Modo de direção alterado: {old_mode.value} → {mode.value}")

    def set_sensitivity(self, sensitivity: float):
        """
        Altera sensibilidade da direção

        Args:
            sensitivity (float): Nova sensibilidade (0.5-2.0)
        """
        old_sensitivity = self.steering_sensitivity
        self.steering_sensitivity = max(0.5, min(2.0, sensitivity))

        if abs(self.steering_sensitivity - old_sensitivity) > 0.1:
            print(
                f"🔧 Sensibilidade alterada: {old_sensitivity:.1f}x → {self.steering_sensitivity:.1f}x"
            )

    def _test_steering(self):
        """Executa teste rápido da direção"""
        print("Executando teste da direção...")

        original_smooth = self.smooth_movement
        self.smooth_movement = False  # Movimento direto para teste

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

        finally:
            self.smooth_movement = original_smooth

    def calibrate_center(self):
        """
        Calibra posição central da direção
        """
        print("=== CALIBRAÇÃO DA DIREÇÃO ===")
        print("Centralizando servo...")

        # Move para posição teórica do centro
        self.target_angle = 0.0
        self.current_angle = 0.0
        self.servo_angle = self.STEERING_CENTER

        time.sleep(1.0)

        print("Calibração concluída.")
        print("Ajuste manual se necessário:")
        print("- Rodas devem estar alinhadas para frente")
        print("- Volante deve estar centralizado")

        self.center_calibrated = True

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
            # === COMPENSAÇÕES ===
            "speed_compensation": self.speed_compensation,
            "current_speed": round(self.current_speed, 1),
            "ackermann_enabled": self.ackermann_enabled,
            # === STATUS TÉCNICO ===
            "is_initialized": self.is_initialized,
            "center_calibrated": self.center_calibrated,
            "smooth_movement": self.smooth_movement,
            "emergency_center": self.emergency_center,
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
        if not self.ackermann_enabled or abs(self.current_angle) < 1.0:
            return {
                "left_wheel": round(self.current_angle, 1),
                "right_wheel": round(self.current_angle, 1),
                "turn_radius": float("inf"),
            }

        try:
            # Cálculo do raio de curvatura
            angle_rad = math.radians(abs(self.current_angle))
            turn_radius = self.wheelbase / math.tan(angle_rad)

            # Ângulos das rodas interna e externa
            inner_radius = turn_radius - self.track_width / 2
            outer_radius = turn_radius + self.track_width / 2

            inner_angle = math.degrees(math.atan(self.wheelbase / inner_radius))
            outer_angle = math.degrees(math.atan(self.wheelbase / outer_radius))

            # Determina qual roda é interna
            if self.current_angle > 0:  # Direita
                left_wheel = outer_angle
                right_wheel = inner_angle
            else:  # Esquerda
                left_wheel = -inner_angle
                right_wheel = -outer_angle

            return {
                "left_wheel": round(left_wheel, 1),
                "right_wheel": round(right_wheel, 1),
                "turn_radius": round(turn_radius, 2),
            }

        except (ZeroDivisionError, ValueError):
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
            "center_calibrated": self.center_calibrated,
            "steering_mode": self.steering_mode.value,
        }

    def cleanup(self):
        """Libera recursos da direção"""
        try:
            print("Finalizando sistema de direção...")

            # Para thread de movimento
            self.should_stop = True
            if self.movement_thread and self.movement_thread.is_alive():
                self.movement_thread.join(timeout=1.0)

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
