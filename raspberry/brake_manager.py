#!/usr/bin/env python3
"""
brake_manager.py - Sistema de Freios do Carrinho F1
Controla freios dianteiros e traseiros com servo MG996R

PINOUT SERVOS MG996R:
====================
Servo Freio Dianteiro -> Raspberry Pi 4 (GPIO)
- VCC (Vermelho)  -> Pin 2 (5V) ou fonte externa 6V
- GND (Marrom)    -> Pin 6 (GND)
- Signal (Laranja)-> Pin 7 (GPIO4) - PWM

Servo Freio Traseiro -> Raspberry Pi 4 (GPIO)
- VCC (Vermelho)  -> Pin 2 (5V) ou fonte externa 6V
- GND (Marrom)    -> Pin 9 (GND)
- Signal (Laranja)-> Pin 11 (GPIO17) - PWM

CARACTERÍSTICAS MG996R:
======================
- Tensão: 4.8V - 7.2V (recomendado 6V para torque máximo)
- Torque: 11kg.cm @ 6V
- Velocidade: 0.14s/60° @ 6V
- Ângulo: 0° - 180° (180° = freio máximo)
- PWM: 50Hz, pulso 1.0ms-2.0ms
- Corrente: ~1.5A sob carga máxima

CONFIGURAÇÃO NECESSÁRIA:
=======================
sudo raspi-config -> Interface Options -> SPI -> Enable
sudo apt-get install python3-rpi.gpio python3-pigpio
sudo pigpiod  # Para PWM de alta precisão (opcional)
"""

import time
import math
import threading
from typing import Optional

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    print("❌ RPi.GPIO não disponível - hardware GPIO obrigatório")
    GPIO_AVAILABLE = False
    exit(1)  # Para execução se GPIO não disponível


class BrakeManager:
    """Gerencia sistema de freios dianteiro e traseiro"""

    # ================== CONFIGURAÇÕES FÍSICAS ==================

    # Pinos GPIO dos servos
    FRONT_BRAKE_PIN = 4  # GPIO4 - Pin 7
    REAR_BRAKE_PIN = 17  # GPIO17 - Pin 11

    # Características do servo MG996R
    PWM_FREQUENCY = 50  # 50Hz para servos
    PULSE_MIN = 1.0  # 1.0ms = 0° (freio solto)
    PULSE_MAX = 2.0  # 2.0ms = 180° (freio máximo)
    PULSE_NEUTRAL = 1.5  # 1.5ms = 90° (posição neutra)

    # Limites físicos do freio (em graus)
    BRAKE_MIN_ANGLE = 0  # 0° = freio completamente solto
    BRAKE_MAX_ANGLE = 180  # 180° = freio máximo
    BRAKE_NEUTRAL = 90  # 90° = posição neutra

    def __init__(
        self,
        front_pin: int = None,
        rear_pin: int = None,
        brake_balance: float = 50.0,  # 50% = balanceado
        max_brake_force: float = 100.0,
        response_time: float = 0.1,
    ):
        """
        Inicializa o sistema de freios

        Args:
            front_pin (int): Pino GPIO do servo freio dianteiro
            rear_pin (int): Pino GPIO do servo freio traseiro
            brake_balance (float): Balanço de freio 0-100% (0=mais dianteiro, 100=mais traseiro)
            max_brake_force (float): Força máxima de freio 0-100%
            response_time (float): Tempo de resposta do servo em segundos
        """
        self.front_pin = front_pin or self.FRONT_BRAKE_PIN
        self.rear_pin = rear_pin or self.REAR_BRAKE_PIN

        # Configurações de freio
        self.brake_balance = max(0.0, min(100.0, brake_balance))  # 0-100%
        self.max_brake_force = max(0.0, min(100.0, max_brake_force))  # 0-100%
        self.response_time = max(0.05, response_time)  # Mínimo 50ms

        # Estado atual dos freios
        self.front_brake_angle = self.BRAKE_NEUTRAL  # Ângulo atual do servo dianteiro
        self.rear_brake_angle = self.BRAKE_NEUTRAL  # Ângulo atual do servo traseiro
        self.front_brake_force = 0.0  # Força atual 0-100%
        self.rear_brake_force = 0.0  # Força atual 0-100%
        self.total_brake_input = 0.0  # Input total 0-100%

        # Estado dos servos
        self.is_initialized = False
        self.front_pwm = None
        self.rear_pwm = None

        # Controle de movimento suave
        self.target_front_angle = self.BRAKE_NEUTRAL
        self.target_rear_angle = self.BRAKE_NEUTRAL
        self.smooth_movement = True
        self.movement_thread = None
        self.should_stop = False

        # Estatísticas
        self.brake_applications = 0
        self.total_brake_time = 0.0
        self.last_brake_time = 0.0
        self.start_time = time.time()

        # Calibração
        self.front_calibrated = False
        self.rear_calibrated = False
        self.calibration_offset_front = 0.0
        self.calibration_offset_rear = 0.0

    def initialize(self) -> bool:
        """
        Inicializa o sistema de freios

        Returns:
            bool: True se inicializado com sucesso
        """
        print("Inicializando sistema de freios...")
        print(
            f"Freio dianteiro: GPIO{self.front_pin} (Pin {self._gpio_to_pin(self.front_pin)})"
        )
        print(
            f"Freio traseiro: GPIO{self.rear_pin} (Pin {self._gpio_to_pin(self.rear_pin)})"
        )
        print(
            f"Balanço de freio: {self.brake_balance:.1f}% (0=dianteiro, 100=traseiro)"
        )

        # GPIO sempre disponível - sem modo simulação

        try:
            # Configura GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Configura pinos como saída
            GPIO.setup(self.front_pin, GPIO.OUT)
            GPIO.setup(self.rear_pin, GPIO.OUT)

            # Cria objetos PWM
            self.front_pwm = GPIO.PWM(self.front_pin, self.PWM_FREQUENCY)
            self.rear_pwm = GPIO.PWM(self.rear_pin, self.PWM_FREQUENCY)

            # Inicia PWM na posição neutra
            front_duty = self._angle_to_duty_cycle(self.BRAKE_NEUTRAL)
            rear_duty = self._angle_to_duty_cycle(self.BRAKE_NEUTRAL)

            self.front_pwm.start(front_duty)
            self.rear_pwm.start(rear_duty)

            # Aguarda servos se posicionarem
            time.sleep(0.5)

            # Inicia thread de movimento suave
            if self.smooth_movement:
                self._start_movement_thread()

            self.is_initialized = True

            print("✓ Sistema de freios inicializado com sucesso")
            print(f"  - Frequência PWM: {self.PWM_FREQUENCY}Hz")
            print(f"  - Posição inicial: {self.BRAKE_NEUTRAL}° (neutro)")
            print(
                f"  - Movimento suave: {'Ativado' if self.smooth_movement else 'Desativado'}"
            )

            # Teste rápido dos servos
            self._test_servos()

            return True

        except Exception as e:
            print(f"✗ Erro ao inicializar sistema de freios: {e}")
            print("\nVerifique:")
            print("1. Conexões dos servos (VCC, GND, Signal)")
            print("2. Alimentação dos servos (5V-6V, corrente suficiente)")
            print("3. Pinos GPIO configurados corretamente")
            print("4. sudo apt-get install python3-rpi.gpio")

            self.is_initialized = False
            return False

    def _gpio_to_pin(self, gpio_num: int) -> int:
        """Converte número GPIO para número do pino físico"""
        gpio_to_pin_map = {
            4: 7,
            17: 11,
            18: 12,
            27: 13,
            22: 15,
            23: 16,
            24: 18,
            25: 22,
            5: 29,
            6: 31,
            12: 32,
            13: 33,
            19: 35,
            16: 36,
            26: 37,
            20: 38,
            21: 40,
        }
        return gpio_to_pin_map.get(gpio_num, 0)

    def _angle_to_duty_cycle(self, angle: float) -> float:
        """
        Converte ângulo do servo para duty cycle PWM

        Args:
            angle (float): Ângulo em graus (0-180)

        Returns:
            float: Duty cycle em porcentagem (0-100)
        """
        # Garante que o ângulo está no range válido
        angle = max(self.BRAKE_MIN_ANGLE, min(self.BRAKE_MAX_ANGLE, angle))

        # Converte ângulo para duração de pulso (1.0ms - 2.0ms)
        pulse_width = self.PULSE_MIN + (angle / 180.0) * (
            self.PULSE_MAX - self.PULSE_MIN
        )

        # Converte duração de pulso para duty cycle
        # Período = 1/50Hz = 20ms
        # Duty cycle = (pulse_width / 20ms) * 100
        duty_cycle = (pulse_width / 20.0) * 100.0

        return duty_cycle

    def _start_movement_thread(self):
        """Inicia thread para movimento suave dos servos"""
        if self.movement_thread is None or not self.movement_thread.is_alive():
            self.should_stop = False
            self.movement_thread = threading.Thread(target=self._smooth_movement_loop)
            self.movement_thread.daemon = True
            self.movement_thread.start()

    def _smooth_movement_loop(self):
        """Loop principal para movimento suave dos servos"""
        while not self.should_stop and self.is_initialized:
            try:
                # Velocidade de movimento (graus por iteração)
                move_speed = 2.0  # Ajuste para mais/menos suavidade

                # Movimento suave para posição alvo
                front_diff = self.target_front_angle - self.front_brake_angle
                rear_diff = self.target_rear_angle - self.rear_brake_angle

                # Move gradualmente em direção ao alvo
                if abs(front_diff) > 0.5:
                    if front_diff > 0:
                        self.front_brake_angle = min(
                            self.front_brake_angle + move_speed, self.target_front_angle
                        )
                    else:
                        self.front_brake_angle = max(
                            self.front_brake_angle - move_speed, self.target_front_angle
                        )

                if abs(rear_diff) > 0.5:
                    if rear_diff > 0:
                        self.rear_brake_angle = min(
                            self.rear_brake_angle + move_speed, self.target_rear_angle
                        )
                    else:
                        self.rear_brake_angle = max(
                            self.rear_brake_angle - move_speed, self.target_rear_angle
                        )

                # Aplica movimento aos servos (apenas se GPIO disponível)
                if self.front_pwm and self.rear_pwm:
                    front_duty = self._angle_to_duty_cycle(self.front_brake_angle)
                    rear_duty = self._angle_to_duty_cycle(self.rear_brake_angle)

                    self.front_pwm.ChangeDutyCycle(front_duty)
                    self.rear_pwm.ChangeDutyCycle(rear_duty)

                time.sleep(0.02)  # 50Hz de atualização

            except Exception as e:
                print(f"⚠ Erro no movimento suave: {e}")
                time.sleep(0.1)

    def set_brake_balance(self, balance: float):
        """
        Define o balanço de freio entre dianteiro e traseiro

        Args:
            balance (float): Balanço 0-100% (0=mais dianteiro, 100=mais traseiro)
        """
        old_balance = self.brake_balance
        self.brake_balance = max(0.0, min(100.0, balance))

        if abs(self.brake_balance - old_balance) > 0.1:
            print(f"Balanço de freio alterado: {self.brake_balance:.1f}%")

            # Recalcula distribuição se freios estão aplicados
            if self.total_brake_input > 0:
                self._calculate_brake_distribution(self.total_brake_input)

    def apply_brake(self, brake_input: float):
        """
        Aplica freio com a intensidade especificada

        Args:
            brake_input (float): Intensidade do freio 0-100%
        """
        if not self.is_initialized:
            print("⚠ Sistema de freios não inicializado")
            return

        print(f"🛑 FREIO: {brake_input:.1f}% recebido")

        # Garante que o input está no range válido
        brake_input = max(0.0, min(100.0, brake_input))
        self.total_brake_input = brake_input

        # Calcula distribuição entre dianteiro e traseiro
        self._calculate_brake_distribution(brake_input)

        # Atualiza estatísticas
        if brake_input > 0:
            current_time = time.time()
            if self.last_brake_time == 0:
                self.brake_applications += 1
            self.last_brake_time = current_time

        # Debug
        if brake_input > 10:  # Log apenas freadas significativas
            print(
                f"🔧 Freio aplicado: {brake_input:.1f}% "
                f"(Diant: {self.front_brake_force:.1f}%, "
                f"Tras: {self.rear_brake_force:.1f}%)"
            )

    def _calculate_brake_distribution(self, total_input: float):
        """
        Calcula a distribuição de freio entre dianteiro e traseiro

        Args:
            total_input (float): Input total de freio 0-100%
        """
        # Calcula distribuição baseada no balanço
        # balance = 0%   -> 100% dianteiro, 0% traseiro
        # balance = 50%  -> distribuição igual
        # balance = 100% -> 0% dianteiro, 100% traseiro

        front_ratio = (100.0 - self.brake_balance) / 100.0
        rear_ratio = self.brake_balance / 100.0

        # Aplica limitação de força máxima
        max_input = self.max_brake_force
        limited_input = min(total_input, max_input)

        # Calcula forças finais
        self.front_brake_force = limited_input * front_ratio
        self.rear_brake_force = limited_input * rear_ratio

        # Converte força para ângulo do servo
        # 0% força = BRAKE_NEUTRAL (90°)
        # 100% força = BRAKE_MAX_ANGLE (180°)

        front_range = self.BRAKE_MAX_ANGLE - self.BRAKE_NEUTRAL
        rear_range = self.BRAKE_MAX_ANGLE - self.BRAKE_NEUTRAL

        front_angle = (
            self.BRAKE_NEUTRAL + (self.front_brake_force / 100.0) * front_range
        )
        rear_angle = self.BRAKE_NEUTRAL + (self.rear_brake_force / 100.0) * rear_range

        # Aplica calibração se disponível
        front_angle += self.calibration_offset_front
        rear_angle += self.calibration_offset_rear

        # Define novos ângulos alvo
        self.target_front_angle = max(
            self.BRAKE_MIN_ANGLE, min(self.BRAKE_MAX_ANGLE, front_angle)
        )
        self.target_rear_angle = max(
            self.BRAKE_MIN_ANGLE, min(self.BRAKE_MAX_ANGLE, rear_angle)
        )

        # Se movimento suave estiver desabilitado, move imediatamente
        if not self.smooth_movement:
            self.front_brake_angle = self.target_front_angle
            self.rear_brake_angle = self.target_rear_angle

            if GPIO_AVAILABLE and self.front_pwm and self.rear_pwm:
                front_duty = self._angle_to_duty_cycle(self.front_brake_angle)
                rear_duty = self._angle_to_duty_cycle(self.rear_brake_angle)

                self.front_pwm.ChangeDutyCycle(front_duty)
                self.rear_pwm.ChangeDutyCycle(rear_duty)

    def release_brakes(self):
        """Libera completamente os freios"""
        self.apply_brake(0.0)
        print("🔧 Freios liberados")

    def emergency_brake(self):
        """Aplica freio de emergência (força máxima)"""
        self.apply_brake(100.0)
        print("🚨 FREIO DE EMERGÊNCIA ATIVADO!")

    def _test_servos(self):
        """Executa teste rápido dos servos"""
        print("Executando teste dos servos...")

        original_smooth = self.smooth_movement
        self.smooth_movement = False  # Desabilita movimento suave para teste

        try:
            # Teste freio dianteiro
            print("  - Testando freio dianteiro...")
            self.apply_brake(30.0)  # 30% só no dianteiro (balance = 0)
            old_balance = self.brake_balance
            self.set_brake_balance(0.0)
            time.sleep(0.5)

            # Teste freio traseiro
            print("  - Testando freio traseiro...")
            self.set_brake_balance(100.0)  # 30% só no traseiro
            time.sleep(0.5)

            # Volta ao estado inicial
            self.set_brake_balance(old_balance)
            self.release_brakes()
            time.sleep(0.5)

            print("✓ Teste dos servos concluído")

        except Exception as e:
            print(f"⚠ Erro durante teste: {e}")

        finally:
            self.smooth_movement = original_smooth

    def calibrate_brakes(self):
        """
        Calibra os servos de freio para posição correta
        """
        print("=== CALIBRAÇÃO DOS FREIOS ===")
        print("Posicionando servos na posição neutra...")

        # Move para posição neutra
        self.target_front_angle = self.BRAKE_NEUTRAL
        self.target_rear_angle = self.BRAKE_NEUTRAL

        time.sleep(1.0)  # Aguarda posicionamento

        print("Calibração concluída.")
        print("Ajuste manual se necessário:")
        print(f"- Freio dianteiro deve estar na posição neutra (sem contato)")
        print(f"- Freio traseiro deve estar na posição neutra (sem contato)")

        self.front_calibrated = True
        self.rear_calibrated = True

    def get_brake_status(self) -> dict:
        """
        Obtém status completo do sistema de freios

        Returns:
            dict: Status atual dos freios
        """
        return {
            # === CONFIGURAÇÃO ===
            "brake_balance": round(self.brake_balance, 1),
            "max_brake_force": round(self.max_brake_force, 1),
            "response_time": round(self.response_time, 3),
            # === ESTADO ATUAL ===
            "total_brake_input": round(self.total_brake_input, 1),
            "front_brake_force": round(self.front_brake_force, 1),
            "rear_brake_force": round(self.rear_brake_force, 1),
            # === ÂNGULOS DOS SERVOS ===
            "front_brake_angle": round(self.front_brake_angle, 1),
            "rear_brake_angle": round(self.rear_brake_angle, 1),
            "target_front_angle": round(self.target_front_angle, 1),
            "target_rear_angle": round(self.target_rear_angle, 1),
            # === STATUS TÉCNICO ===
            "is_initialized": self.is_initialized,
            "front_calibrated": self.front_calibrated,
            "rear_calibrated": self.rear_calibrated,
            "smooth_movement": self.smooth_movement,
            # === ESTATÍSTICAS ===
            "brake_applications": self.brake_applications,
            "total_brake_time": round(self.total_brake_time, 2),
            "is_braking": self.total_brake_input > 0,
            # === HARDWARE ===
            "front_pin": self.front_pin,
            "rear_pin": self.rear_pin,
            "pwm_frequency": self.PWM_FREQUENCY,
            "gpio_available": True,
            # === TIMESTAMP ===
            "timestamp": round(time.time(), 3),
        }

    def get_statistics(self) -> dict:
        """
        Obtém estatísticas de uso dos freios

        Returns:
            dict: Estatísticas de operação
        """
        elapsed = time.time() - self.start_time

        return {
            "brake_applications": self.brake_applications,
            "total_runtime": round(elapsed, 2),
            "average_brake_per_minute": (
                round(self.brake_applications / (elapsed / 60.0), 2)
                if elapsed > 0
                else 0
            ),
            "last_brake_time": self.last_brake_time,
            "system_uptime": round(elapsed, 2),
            "front_calibrated": self.front_calibrated,
            "rear_calibrated": self.rear_calibrated,
        }

    def cleanup(self):
        """Libera recursos do sistema de freios"""
        try:
            print("Finalizando sistema de freios...")

            # Para thread de movimento
            self.should_stop = True
            if self.movement_thread and self.movement_thread.is_alive():
                self.movement_thread.join(timeout=1.0)

            # Libera freios antes de desligar
            self.release_brakes()
            time.sleep(0.2)

            # Para PWM
            # Sempre limpa GPIO
                if self.front_pwm:
                    self.front_pwm.stop()
                if self.rear_pwm:
                    self.rear_pwm.stop()

                # Cleanup GPIO
                GPIO.cleanup([self.front_pin, self.rear_pin])

            self.is_initialized = False
            print("✓ Sistema de freios finalizado")

        except Exception as e:
            print(f"⚠ Erro ao finalizar sistema de freios: {e}")

    def __del__(self):
        """Destrutor - garante limpeza dos recursos"""
        self.cleanup()


# Exemplo de uso
if __name__ == "__main__":
    print("=== TESTE DO SISTEMA DE FREIOS ===")

    # Cria instância do sistema de freios
    brake_mgr = BrakeManager(
        brake_balance=60.0,  # 60% mais traseiro para F1
        max_brake_force=90.0,  # 90% força máxima
        response_time=0.1,  # 100ms de resposta
    )

    # Inicializa
    if brake_mgr.initialize():
        print("\n=== TESTE DE FREIOS ===")

        # Teste 1: Freio progressivo
        print("1. Teste de freio progressivo...")
        for brake_level in [0, 25, 50, 75, 100, 50, 0]:
            print(f"   Aplicando freio: {brake_level}%")
            brake_mgr.apply_brake(brake_level)
            time.sleep(1.0)

            status = brake_mgr.get_brake_status()
            print(
                f"   Status: Diant={status['front_brake_force']:.1f}% "
                f"Tras={status['rear_brake_force']:.1f}%"
            )

        # Teste 2: Diferentes balanços
        print("\n2. Teste de balanço de freio...")
        brake_mgr.apply_brake(50.0)  # 50% de freio

        for balance in [0, 25, 50, 75, 100]:
            print(f"   Balanço: {balance}%")
            brake_mgr.set_brake_balance(balance)
            time.sleep(0.5)

            status = brake_mgr.get_brake_status()
            print(
                f"   Distribuição: Diant={status['front_brake_force']:.1f}% "
                f"Tras={status['rear_brake_force']:.1f}%"
            )

        # Teste 3: Freio de emergência
        print("\n3. Teste de freio de emergência...")
        brake_mgr.emergency_brake()
        time.sleep(1.0)

        status = brake_mgr.get_brake_status()
        print(f"   Freio emergência: {status['total_brake_input']:.1f}%")

        # Libera freios
        brake_mgr.release_brakes()
        time.sleep(1.0)

        # Estatísticas finais
        stats = brake_mgr.get_statistics()
        print(f"\n=== ESTATÍSTICAS FINAIS ===")
        print(f"Aplicações de freio: {stats['brake_applications']}")
        print(f"Tempo de operação: {stats['total_runtime']:.1f}s")
        print(
            f"Freios calibrados: Diant={stats['front_calibrated']}, Tras={stats['rear_calibrated']}"
        )

        # Finaliza
        brake_mgr.cleanup()

    else:
        print("✗ Falha ao inicializar sistema de freios")
        print("\nPara usar com hardware real:")
        print("1. Conecte servos conforme pinout no cabeçalho")
        print("2. Fonte de alimentação adequada (5V-6V, 3A+)")
        print("3. sudo apt-get install python3-rpi.gpio")
        print("4. Verifique conexões e alimentação")
