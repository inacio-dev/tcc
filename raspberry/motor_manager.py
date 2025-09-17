#!/usr/bin/env python3
"""
motor_manager.py - Sistema de Motor DC e Transmissão com 8 Marchas
Controla motor RS550 via ponte H BTS7960 (HW-039)

PINOUT PONTE H BTS7960 (HW-039):
================================
Ponte H HW-039 -> Raspberry Pi 4 (GPIO)
- VCC          -> Pin 2 (5V) - Alimentação lógica
- GND          -> Pin 6 (GND) - Terra comum
- RPWM         -> Pin 12 (GPIO18) - PWM direção direita
- LPWM         -> Pin 13 (GPIO27) - PWM direção esquerda
- R_EN         -> Pin 15 (GPIO22) - Enable direita (HIGH)
- L_EN         -> Pin 16 (GPIO23) - Enable esquerda (HIGH)
- R_IS         -> Não conectar (current sense direita)
- L_IS         -> Não conectar (current sense esquerda)

Motor RS550 -> Ponte H BTS7960:
- Motor+ -> B+
- Motor- -> B-

Alimentação Motor -> Ponte H:
- V+ (12V) -> B+VCC (Positivo bateria)
- V- (GND) -> B-VCC (Negativo bateria)

CARACTERÍSTICAS RS550:
=====================
- Tensão: 12V nominal (9V-15V)
- RPM: 19.550 @ 12V sem carga
- Corrente: ~3A @ 12V carga normal, pico 15A
- Torque: Alto torque de partida
- Potência: ~200W

CARACTERÍSTICAS BTS7960:
=======================
- Tensão: 5.5V-27V (motor), 5V (lógica)
- Corrente: 40A contínua, 60A pico
- Frequência PWM: até 25kHz (recomendado 1-10kHz)
- Proteção térmica e sobrecorrente integrada
- Controle independente para frente/ré

CONFIGURAÇÃO NECESSÁRIA:
=======================
sudo raspi-config -> Interface Options -> SPI -> Enable
sudo apt-get install python3-rpi.gpio
"""

import time
import math
import threading
from typing import Optional, Dict, Any
from enum import Enum

try:
    import RPi.GPIO as GPIO

    GPIO_AVAILABLE = True
except ImportError:
    print("⚠ RPi.GPIO não disponível - usando simulação")
    GPIO_AVAILABLE = False


class MotorDirection(Enum):
    """Direções do motor"""

    FORWARD = "forward"
    REVERSE = "reverse"
    STOP = "stop"


class TransmissionMode(Enum):
    """Modos de transmissão"""

    MANUAL = "manual"
    AUTOMATIC = "automatic"
    SPORT = "sport"


class MotorManager:
    """Gerencia motor DC RS550 com transmissão simulada de 4 marchas"""

    # ================== CONFIGURAÇÕES FÍSICAS ==================

    # Pinos GPIO da ponte H BTS7960
    RPWM_PIN = 18  # GPIO18 - Pin 12 - PWM direção frente
    LPWM_PIN = 27  # GPIO27 - Pin 13 - PWM direção ré
    R_EN_PIN = 22  # GPIO22 - Pin 15 - Enable frente
    L_EN_PIN = 23  # GPIO23 - Pin 16 - Enable esquerda

    # Configurações PWM
    PWM_FREQUENCY = 2000  # 2kHz - boa para motores DC
    PWM_MAX = 100  # Duty cycle máximo

    # Características do motor RS550
    MOTOR_MAX_RPM = 19550  # RPM máximo @ 12V
    MOTOR_MIN_RPM = 800  # RPM mínimo estável
    MOTOR_IDLE_RPM = 1200  # RPM marcha lenta

    # Sistema de transmissão (5 marchas)
    GEAR_RATIOS = {
        1: 3.5,  # 1ª marcha - maior torque, arranque
        2: 2.2,  # 2ª marcha - aceleração
        3: 1.4,  # 3ª marcha - velocidade média
        4: 0.9,  # 4ª marcha - velocidade alta
        5: 0.7,  # 5ª marcha - velocidade máxima (100% potência)
    }

    # RPM de troca automática (5 marchas)
    SHIFT_UP_RPM = {
        1: 4500,  # 1ª→2ª: arranque completo
        2: 6000,  # 2ª→3ª: aceleração
        3: 7500,  # 3ª→4ª: velocidade alta
        4: 9000,  # 4ª→5ª: velocidade máxima
        5: 999999,  # 5ª: sem limite superior
    }

    SHIFT_DOWN_RPM = {
        1: 0,     # 1ª: sem limite inferior
        2: 2500,  # 2ª→1ª: baixa rotação
        3: 4000,  # 3ª→2ª: rotação média
        4: 6000,  # 4ª→3ª: rotação alta
        5: 7500,  # 5ª→4ª: rotação muito alta
    }

    def __init__(
        self,
        rpwm_pin: int = None,
        lpwm_pin: int = None,
        r_en_pin: int = None,
        l_en_pin: int = None,
    ):
        """
        Inicializa o gerenciador do motor

        Args:
            rpwm_pin (int): Pino PWM frente
            lpwm_pin (int): Pino PWM ré
            r_en_pin (int): Pino enable frente
            l_en_pin (int): Pino enable ré
        """
        self.rpwm_pin = rpwm_pin or self.RPWM_PIN
        self.lpwm_pin = lpwm_pin or self.LPWM_PIN
        self.r_en_pin = r_en_pin or self.R_EN_PIN
        self.l_en_pin = l_en_pin or self.L_EN_PIN


        # Estado do motor
        self.is_initialized = False
        self.motor_direction = MotorDirection.STOP
        self.current_pwm = 0.0  # PWM atual 0-100%
        self.target_pwm = 0.0  # PWM alvo 0-100%
        self.current_rpm = 0.0  # RPM atual calculado
        self.target_rpm = 0.0  # RPM alvo


        # Sistema de transmissão
        self.current_gear = 1  # Marcha atual (1-8)
        self.gear_ratio = self.GEAR_RATIOS[1]
        self.clutch_engaged = True  # Embreagem
        self.is_shifting = False  # Em processo de troca
        self.shift_time = 0.3  # Tempo de troca em segundos
        self.last_throttle_percent = 0.0  # CORREÇÃO: Armazena último throttle para reaplicar após troca

        # SISTEMA F1 DE ZONAS DE EFICIÊNCIA
        self.efficiency_zone = "IDEAL"  # IDEAL, SUBOPTIMAL, POOR
        self.zone_acceleration_rate = 1.0  # Multiplicador de aceleração baseado na zona
        self.base_acceleration_time = 2.0  # Tempo base para atingir zona ideal (2s)
        self.last_zone_check = time.time()

        # Conta-giros
        self.engine_rpm = 0.0  # RPM do motor
        self.wheel_rpm = 0.0  # RPM das rodas
        self.calculated_speed_kmh = 0.0  # Velocidade calculada

        # Controle PWM
        self.rpwm = None
        self.lpwm = None

        # Controle de aceleração suave
        self.acceleration_thread = None
        self.should_stop = False

        # Estatísticas
        self.total_runtime = 0.0
        self.total_distance = 0.0
        self.gear_changes = 0
        self.engine_starts = 0
        self.last_update_time = time.time()
        self.start_time = time.time()

        # Limitadores de segurança
        self.temperature_limit = 85.0  # °C simulado
        self.current_limit = 12.0  # A simulado
        self.overheat_protection = True
        self.current_protection = True

    def initialize(self) -> bool:
        """
        Inicializa o sistema de motor

        Returns:
            bool: True se inicializado com sucesso
        """
        print("Inicializando sistema de motor...")
        print(f"Motor: RS550 12V via ponte H BTS7960")
        print(
            f"RPWM (Frente): GPIO{self.rpwm_pin} (Pin {self._gpio_to_pin(self.rpwm_pin)})"
        )
        print(
            f"LPWM (Ré): GPIO{self.lpwm_pin} (Pin {self._gpio_to_pin(self.lpwm_pin)})"
        )
        print(f"R_EN: GPIO{self.r_en_pin} (Pin {self._gpio_to_pin(self.r_en_pin)})")
        print(f"L_EN: GPIO{self.l_en_pin} (Pin {self._gpio_to_pin(self.l_en_pin)})")
        print(f"Transmissão: MANUAL - 5 marchas")

        if not GPIO_AVAILABLE:
            print("⚠ MODO SIMULAÇÃO - Motor não conectado")
            self.is_initialized = True
            self._start_acceleration_thread()
            self._start_engine()
            return True

        try:
            # Configura GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Configura pinos como saída
            GPIO.setup(self.rpwm_pin, GPIO.OUT)
            GPIO.setup(self.lpwm_pin, GPIO.OUT)
            GPIO.setup(self.r_en_pin, GPIO.OUT)
            GPIO.setup(self.l_en_pin, GPIO.OUT)

            # Cria objetos PWM
            self.rpwm = GPIO.PWM(self.rpwm_pin, self.PWM_FREQUENCY)
            self.lpwm = GPIO.PWM(self.lpwm_pin, self.PWM_FREQUENCY)

            # Habilita ponte H (enables em HIGH)
            GPIO.output(self.r_en_pin, GPIO.HIGH)
            GPIO.output(self.l_en_pin, GPIO.HIGH)

            # Inicia PWM com duty cycle zero
            self.rpwm.start(0)
            self.lpwm.start(0)

            # Inicia motor em marcha lenta
            self._start_engine()

            self.is_initialized = True

            # Correção emergencial: garantir marcha válida no sistema de 5 marchas
            if self.current_gear > 5:
                print(f"⚠ Marcha {self.current_gear}ª inválida - redefinindo para 1ª")
                self.current_gear = 1

            # Inicia thread de controle APÓS is_initialized=True
            self._start_acceleration_thread()

            print("✓ Sistema de motor inicializado com sucesso")
            print(f"  - Frequência PWM: {self.PWM_FREQUENCY}Hz")
            print(f"  - Marcha inicial: {self.current_gear}ª")
            print(f"  - Modo transmissão: manual")
            print(f"  - Resposta instantânea: motor responde imediatamente")

            return True

        except Exception as e:
            print(f"✗ Erro ao inicializar motor: {e}")
            print("\nVerifique:")
            print("1. Conexões da ponte H BTS7960")
            print("2. Alimentação 12V do motor (V+/V-)")
            print("3. Alimentação 5V da lógica (VCC/GND)")
            print("4. Enables conectados e em HIGH")
            print("5. sudo apt-get install python3-rpi.gpio")

            self.is_initialized = False
            return False

    def _gpio_to_pin(self, gpio_num: int) -> int:
        """Converte número GPIO para número do pino físico"""
        gpio_to_pin_map = {
            18: 12,
            27: 13,
            22: 15,
            23: 16,
            4: 7,
            17: 11,
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

    def _start_acceleration_thread(self):
        """Inicia thread para controle de aceleração suave"""
        if self.acceleration_thread is None or not self.acceleration_thread.is_alive():
            self.should_stop = False
            self.acceleration_thread = threading.Thread(target=self._acceleration_loop)
            self.acceleration_thread.daemon = True
            self.acceleration_thread.start()
            print("🧵 Thread de aceleração iniciada")

    def _acceleration_loop(self):
        """Loop principal de controle de aceleração e RPM"""
        print(f"🧵 Thread loop iniciado (should_stop={self.should_stop}, is_initialized={self.is_initialized})")
        while not self.should_stop and self.is_initialized:
            try:
                current_time = time.time()
                dt = current_time - self.last_update_time

                # SISTEMA F1: Aceleração baseada em zonas de eficiência
                self._apply_f1_zone_acceleration(dt)

                # Calcula RPM do motor baseado no PWM
                self._calculate_engine_rpm()

                # Sistema de transmissão automática DESABILITADO
                # Apenas controle manual via teclas M/N
                # if self.transmission_mode == TransmissionMode.AUTOMATIC:
                #     self._automatic_transmission()

                # Calcula velocidade das rodas
                self._calculate_wheel_speed()

                # Aplica PWM ao motor
                self._apply_motor_pwm()

                # Atualiza estatísticas
                self._update_statistics(dt)

                self.last_update_time = current_time
                time.sleep(0.02)  # 50Hz de atualização

            except Exception as e:
                print(f"⚠ Erro no controle do motor: {e}")
                time.sleep(0.1)

    def _calculate_engine_rpm(self):
        """Calcula RPM do motor baseado no PWM - simulação realista de carro"""

        # Obter marcha lenta correspondente à marcha atual
        gear_idle_rpm = {
            1: 1200,   # 1ª marcha: marcha lenta baixa
            2: 1500,   # 2ª marcha: marcha lenta média
            3: 1800,   # 3ª marcha: marcha lenta alta
            4: 2100,   # 4ª marcha: marcha lenta alta
            5: 2400,   # 5ª marcha: marcha lenta máxima
        }

        idle_rpm_for_gear = gear_idle_rpm.get(self.current_gear, 1200)

        if self.current_pwm < 30.0:
            # Motor parado - não tem torque suficiente para girar (< 30%)
            self.engine_rpm = 0
        else:
            # Faixas de PWM por marcha para calcular RPM (mínimo 30% para girar)
            gear_ranges = {
                1: (30, 40),   # 1ª marcha: 30% a 40%
                2: (40, 55),   # 2ª marcha: 40% a 55%
                3: (55, 70),   # 3ª marcha: 55% a 70%
                4: (70, 85),   # 4ª marcha: 70% a 85%
                5: (85, 100),  # 5ª marcha: 85% a 100%
            }

            min_pwm, max_pwm = gear_ranges.get(self.current_gear, (30, 40))

            # Se estiver na marcha lenta da marcha (min_pwm)
            if abs(self.current_pwm - min_pwm) < 1.0:
                self.engine_rpm = idle_rpm_for_gear
            else:
                # RPM baseado no PWM dentro da faixa da marcha
                # min_pwm = idle_rpm, max_pwm = MAX_RPM
                rpm_range = self.MOTOR_MAX_RPM - idle_rpm_for_gear

                # Normalizar PWM dentro da faixa da marcha
                if max_pwm > min_pwm:
                    normalized_pwm = (self.current_pwm - min_pwm) / (max_pwm - min_pwm)
                    normalized_pwm = max(0.0, min(1.0, normalized_pwm))
                else:
                    normalized_pwm = 0.0

                # Curva não-linear para simular característica do motor
                rpm_curve = math.pow(normalized_pwm, 0.7)  # Curva realista

                self.engine_rpm = idle_rpm_for_gear + (rpm_range * rpm_curve)

        # Simula variação natural do motor (menor variação)
        variation = math.sin(time.time() * 10) * 30  # ±30 RPM
        self.engine_rpm += variation

        # Garante limites
        self.engine_rpm = max(0, min(self.MOTOR_MAX_RPM, self.engine_rpm))

    def _calculate_wheel_speed(self):
        """Calcula velocidade das rodas baseada na transmissão"""
        if self.clutch_engaged and not self.is_shifting:
            self.wheel_rpm = self.engine_rpm / self.gear_ratio
        else:
            # Embreagem desacoplada - rodas desaceleram
            self.wheel_rpm *= 0.98  # Desaceleração gradual

        # Converte RPM das rodas para km/h
        # Assumindo roda de 65mm de diâmetro (modelo 1:10)
        wheel_diameter_m = 0.065
        wheel_circumference = math.pi * wheel_diameter_m

        # RPM para m/s
        speed_ms = (self.wheel_rpm * wheel_circumference) / 60.0

        # m/s para km/h
        self.calculated_speed_kmh = speed_ms * 3.6

    def _automatic_transmission(self):
        """Controla transmissão automática baseada no RPM"""
        if self.is_shifting:
            return

        current_gear = self.current_gear

        # Verifica necessidade de subir marcha
        if current_gear < 8:
            shift_up_rpm = self.SHIFT_UP_RPM[current_gear]
            if self.engine_rpm > shift_up_rpm and self.current_pwm > 30:
                self._shift_gear(current_gear + 1)
                return

        # Verifica necessidade de descer marcha
        if current_gear > 1:
            shift_down_rpm = self.SHIFT_DOWN_RPM[current_gear]
            if self.engine_rpm < shift_down_rpm and self.current_pwm > 10:
                self._shift_gear(current_gear - 1)
                return

    def _shift_gear(self, new_gear: int):
        """
        Executa troca de marcha

        Args:
            new_gear (int): Nova marcha (1-4)
        """
        # Valida marcha no sistema de 5 marchas
        if new_gear < 1 or new_gear > 5 or new_gear == self.current_gear:
            return

        if self.is_shifting:
            return

        print(
            f"🔧 Trocando marcha: {self.current_gear}ª → {new_gear}ª "
            f"(RPM: {self.engine_rpm:.0f})"
        )

        self.is_shifting = True

        # Thread para simular tempo de troca
        def shift_process():
            # Desengate embreagem
            self.clutch_engaged = False

            # Aguarda tempo de troca
            time.sleep(self.shift_time)

            # Troca marcha
            old_gear = self.current_gear
            self.current_gear = new_gear
            self.gear_ratio = self.GEAR_RATIOS[new_gear]

            # Reengata embreagem
            self.clutch_engaged = True
            self.is_shifting = False

            # Atualiza estatísticas
            self.gear_changes += 1

            print(
                f"✓ Marcha trocada para {new_gear}ª "
                f"(Relação: {self.gear_ratio:.1f}:1) - Instantâneo!"
            )

            # CORREÇÃO: Reaplica último throttle com novo limite da marcha
            if self.last_throttle_percent > 0:
                self._reapply_throttle_after_shift()

        shift_thread = threading.Thread(target=shift_process)
        shift_thread.daemon = True
        shift_thread.start()

    def _reapply_throttle_after_shift(self):
        """
        CORREÇÃO: Reaplica último throttle após troca de marcha
        Recalcula PWM com novo limite da marcha atual
        """
        # Recalcula PWM com nova marcha
        intelligent_pwm = self._calculate_intelligent_pwm(self.last_throttle_percent)
        self.target_pwm = intelligent_pwm

        print(f"🔄 THROTTLE reaplicado: {self.last_throttle_percent}% → PWM: {intelligent_pwm:.1f}% (nova marcha: {self.current_gear}ª)")

        # Log removido daqui - será feito no main.py com todos os dados

    def _apply_motor_pwm(self):
        """Aplica PWM ao motor via ponte H"""
        if not self.is_initialized or not GPIO_AVAILABLE:
            return

        try:
            # Determina direção e PWM
            if self.motor_direction == MotorDirection.FORWARD:
                # Frente: RPWM ativo, LPWM zero
                self.rpwm.ChangeDutyCycle(self.current_pwm)
                self.lpwm.ChangeDutyCycle(0)

            elif self.motor_direction == MotorDirection.REVERSE:
                # Ré: LPWM ativo, RPWM zero
                self.rpwm.ChangeDutyCycle(0)
                self.lpwm.ChangeDutyCycle(self.current_pwm)

            else:  # STOP
                # Parado: ambos PWM zero (freio elétrico)
                self.rpwm.ChangeDutyCycle(0)
                self.lpwm.ChangeDutyCycle(0)

        except Exception as e:
            print(f"⚠ Erro ao aplicar PWM: {e}")

    def _start_engine(self):
        """Inicia o motor em marcha lenta"""
        self.motor_direction = MotorDirection.STOP
        self.target_pwm = 0.0
        self.current_pwm = 0.0
        self.engine_starts += 1
        print("🔧 Motor iniciado em marcha lenta")

    def _update_statistics(self, dt: float):
        """Atualiza estatísticas do motor"""
        self.total_runtime += dt

        # Calcula distância percorrida
        if self.calculated_speed_kmh > 0:
            distance_km = (self.calculated_speed_kmh / 3600.0) * dt
            self.total_distance += distance_km

    def set_throttle(self, throttle_percent: float):
        """
        Define posição do acelerador

        Args:
            throttle_percent (float): Posição do acelerador 0-100%
        """
        if not self.is_initialized:
            print("⚠ Motor não inicializado")
            return

        # Garante range válido
        throttle_percent = max(0.0, min(100.0, throttle_percent))

        # CORREÇÃO: Salva último throttle para reaplicar após troca de marcha
        self.last_throttle_percent = throttle_percent

        # Define direção baseada no throttle
        if throttle_percent > 0:
            if self.motor_direction == MotorDirection.STOP:
                self.motor_direction = MotorDirection.FORWARD

            # PWM mínimo para motor se mexer (baseado nos testes)
            min_motor_pwm = 15.0
            if throttle_percent > 0 and throttle_percent < min_motor_pwm:
                # Mapeia 1-100% para 15-100% (PWM útil)
                self.target_pwm = min_motor_pwm + (throttle_percent / 100.0) * (100.0 - min_motor_pwm)
            else:
                self.target_pwm = throttle_percent
        else:
            self.target_pwm = throttle_percent

        # Calcula PWM inteligente baseado na marcha e velocidade
        intelligent_pwm = self._calculate_intelligent_pwm(throttle_percent)

        # Define target PWM para a thread aplicar gradualmente
        self.target_pwm = intelligent_pwm

        # Debug temporário para verificar comandos
        print(f"🚗 THROTTLE: {throttle_percent}% → PWM target: {intelligent_pwm:.1f}% (marcha: {self.current_gear}ª)")

        # Log removido daqui - será feito no main.py com todos os dados

    def _calculate_intelligent_pwm(self, throttle_percent: float) -> float:
        """
        Calcula PWM do motor F1 - SEM LIMITADORES

        Sistema F1 Real:
        - TODAS as marchas podem ir de 0-100% PWM
        - Zonas de eficiência determinam velocidade de aceleração
        - Marcha ideal = aceleração rápida
        - Fora da zona ideal = aceleração muito lenta

        Args:
            throttle_percent (float): Posição do acelerador (0-100%)

        Returns:
            float: PWM motor real a ser aplicado (0-100%)
        """
        # SEM LIMITADORES - throttle mapeia diretamente para PWM
        # As zonas de eficiência controlam a velocidade de aceleração
        final_pwm = throttle_percent

        return final_pwm

    def _calculate_efficiency_zone(self, current_pwm: float) -> tuple:
        """
        Calcula zona de eficiência F1 CORRIGIDA baseada no PWM atual e marcha

        Sistema F1 Real por marcha:

        1ª MARCHA:
        - IDEAL: 0-20% (alta eficiência)
        - SUBOPTIMAL: 20-30% (média eficiência)
        - POOR: 30-100% (baixa eficiência)

        2ª MARCHA:
        - IDEAL: 20-40% (alta eficiência)
        - SUBOPTIMAL: 10-20% e 40-50% (média eficiência)
        - POOR: 0-10% e 50-100% (baixa eficiência)

        3ª MARCHA:
        - IDEAL: 40-60% (alta eficiência)
        - SUBOPTIMAL: 30-40% e 60-70% (média eficiência)
        - POOR: 0-30% e 70-100% (baixa eficiência)

        5ª MARCHA:
        - IDEAL: 80-100% (alta eficiência)
        - SUBOPTIMAL: 70-80% (média eficiência)
        - POOR: 0-70% (baixa eficiência)

        Args:
            current_pwm (float): PWM atual do motor

        Returns:
            tuple: (zona_eficiencia, multiplicador_aceleracao)
        """
        # Zonas F1 CORRETAS por marcha
        if self.current_gear == 1:
            # 1ª MARCHA
            if 0 <= current_pwm <= 20:
                return "IDEAL", 1.0     # 0-20%: Alta eficiência
            elif 20 < current_pwm <= 30:
                return "SUBOPTIMAL", 0.25  # 20-30%: Média eficiência
            else:
                return "POOR", 0.05     # 30-100%: Baixa eficiência

        elif self.current_gear == 2:
            # 2ª MARCHA
            if 20 <= current_pwm <= 40:
                return "IDEAL", 1.0     # 20-40%: Alta eficiência
            elif (10 <= current_pwm < 20) or (40 < current_pwm <= 50):
                return "SUBOPTIMAL", 0.25  # 10-20% e 40-50%: Média eficiência
            else:
                return "POOR", 0.05     # 0-10% e 50-100%: Baixa eficiência

        elif self.current_gear == 3:
            # 3ª MARCHA
            if 40 <= current_pwm <= 60:
                return "IDEAL", 1.0     # 40-60%: Alta eficiência
            elif (30 <= current_pwm < 40) or (60 < current_pwm <= 70):
                return "SUBOPTIMAL", 0.25  # 30-40% e 60-70%: Média eficiência
            else:
                return "POOR", 0.05     # 0-30% e 70-100%: Baixa eficiência

        elif self.current_gear == 4:
            # 4ª MARCHA (interpolação entre 3ª e 5ª)
            if 60 <= current_pwm <= 80:
                return "IDEAL", 1.0     # 60-80%: Alta eficiência
            elif (50 <= current_pwm < 60) or (80 < current_pwm <= 90):
                return "SUBOPTIMAL", 0.25  # 50-60% e 80-90%: Média eficiência
            else:
                return "POOR", 0.05     # 0-50% e 90-100%: Baixa eficiência

        elif self.current_gear == 5:
            # 5ª MARCHA
            if 80 <= current_pwm <= 100:
                return "IDEAL", 1.0     # 80-100%: Alta eficiência
            elif 70 <= current_pwm < 80:
                return "SUBOPTIMAL", 0.25  # 70-80%: Média eficiência
            else:
                return "POOR", 0.05     # 0-70%: Baixa eficiência

        # Fallback para marchas não definidas
        return "POOR", 0.05

    def _apply_f1_zone_acceleration(self, dt: float):
        """
        Aplica aceleração F1 baseada em zonas de eficiência

        Sistema F1:
        - Zona IDEAL: 2s para atingir target (aceleração normal)
        - Zona SUBOPTIMAL: 8s para atingir target (4x mais lento)
        - Zona POOR: 40s para atingir target (20x mais lento)

        Args:
            dt (float): Delta time desde última atualização
        """
        # Calcula zona de eficiência atual
        zone, rate_multiplier = self._calculate_efficiency_zone(self.current_pwm)

        # Atualiza zona apenas se mudou (para logs)
        if zone != self.efficiency_zone:
            self.efficiency_zone = zone
            self.zone_acceleration_rate = rate_multiplier
            print(f"🏁 Zona F1: {zone} (aceleração: {rate_multiplier:.2f}x)")

        # Calcula diferença entre target e atual
        pwm_diff = self.target_pwm - self.current_pwm

        if abs(pwm_diff) < 0.1:  # Já está próximo do target
            self.current_pwm = self.target_pwm
            return

        # Velocidade de aceleração baseada na zona
        # Tempo base: 2s para zona ideal (50% PWM = 1%/frame a 50Hz)
        base_acceleration_per_frame = 50.0 / (self.base_acceleration_time * 50)  # %PWM por frame
        zone_acceleration = base_acceleration_per_frame * rate_multiplier

        # Aplica aceleração gradual baseada na zona
        if pwm_diff > 0:  # Acelerando
            acceleration_step = min(zone_acceleration * dt * 50, pwm_diff)  # 50Hz
            self.current_pwm += acceleration_step
        else:  # Desacelerando (sempre rápido para segurança)
            deceleration_step = min(base_acceleration_per_frame * dt * 50, abs(pwm_diff))
            self.current_pwm -= deceleration_step

        # Debug zona a cada 1s
        current_time = time.time()
        if current_time - self.last_zone_check >= 1.0:
            self.last_zone_check = current_time
            if abs(pwm_diff) > 0.5:  # Só mostra se ainda está acelerando
                print(f"🏁 F1 Zone: {zone} | PWM: {self.current_pwm:.1f}%→{self.target_pwm:.1f}% | Rate: {rate_multiplier:.2f}x")

    def set_reverse(self, enable: bool = True):
        """
        Ativa/desativa ré

        Args:
            enable (bool): True para ré, False para frente
        """
        if not self.is_initialized:
            return

        if enable:
            self.motor_direction = MotorDirection.REVERSE
            print("🔧 Ré engrenada")
        else:
            self.motor_direction = MotorDirection.FORWARD
            print("🔧 Modo frente")

    def emergency_stop(self):
        """Para motor imediatamente"""
        self.motor_direction = MotorDirection.STOP
        self.target_pwm = 0.0
        self.current_pwm = 0.0
        print("🚨 PARADA DE EMERGÊNCIA DO MOTOR!")

    def manual_shift(self, gear: int):
        """
        Troca marcha manualmente

        Args:
            gear (int): Marcha desejada (1-8)
        """
        if gear < 1 or gear > 5:
            print(f"⚠ Marcha inválida: {gear} (válido: 1-5)")
            return

        # Modo sempre manual - permite troca a qualquer momento

        self._shift_gear(gear)

    def shift_gear_up(self) -> bool:
        """
        Sobe uma marcha (controle manual via teclado)
        
        Returns:
            bool: True se a troca foi bem-sucedida
        """
        if self.current_gear >= 5:
            return False  # Já está na marcha máxima
            
        new_gear = self.current_gear + 1
        # Troca manual - sem alterar modo de transmissão
        self._shift_gear(new_gear)
        return True
        
    def shift_gear_down(self) -> bool:
        """
        Desce uma marcha (controle manual via teclado)
        
        Returns:
            bool: True se a troca foi bem-sucedida
        """
        if self.current_gear <= 1:
            return False  # Já está na marcha mínima
            
        new_gear = self.current_gear - 1
        # Troca manual - sem alterar modo de transmissão
        self._shift_gear(new_gear)
        return True

    # Função removida - transmissão sempre manual

    def get_motor_status(self) -> Dict[str, Any]:
        """
        Obtém status completo do motor

        Returns:
            dict: Status atual do motor e transmissão
        """
        return {
            # === MOTOR ===
            "motor_direction": self.motor_direction.value,
            "current_pwm": round(self.current_pwm, 1),
            "target_pwm": round(self.target_pwm, 1),
            "engine_rpm": round(self.engine_rpm, 0),
            "wheel_rpm": round(self.wheel_rpm, 0),
            "speed_kmh": round(self.calculated_speed_kmh, 1),
            # === TRANSMISSÃO ===
            "current_gear": self.current_gear,
            "gear_ratio": self.gear_ratio,
            "transmission_mode": "manual",
            "clutch_engaged": self.clutch_engaged,
            "is_shifting": self.is_shifting,
            # === CONTA-GIROS ===
            "rpm_display": round(self.engine_rpm, 0),
            "max_rpm": self.MOTOR_MAX_RPM,
            "idle_rpm": self.MOTOR_IDLE_RPM,
            "rpm_percent": round((self.engine_rpm / self.MOTOR_MAX_RPM) * 100, 1),
            # === STATUS TÉCNICO ===
            "is_initialized": self.is_initialized,
            "motor_temperature": round(25 + (self.current_pwm * 0.6), 1),  # Simulado
            "motor_current": round(0.5 + (self.current_pwm * 0.1), 2),  # Simulado
            # === HARDWARE ===
            "rpwm_pin": self.rpwm_pin,
            "lpwm_pin": self.lpwm_pin,
            "pwm_frequency": self.PWM_FREQUENCY,
            "gpio_available": GPIO_AVAILABLE,
            # === ESTATÍSTICAS ===
            "gear_changes": self.gear_changes,
            "total_runtime": round(self.total_runtime, 1),
            "total_distance": round(self.total_distance, 3),
            "engine_starts": self.engine_starts,
            # === TIMESTAMP ===
            "timestamp": round(time.time(), 3),
        }

    def get_tachometer_data(self) -> Dict[str, Any]:
        """
        Dados específicos para conta-giros

        Returns:
            dict: Dados do conta-giros
        """
        # SISTEMA F1: Calcula eficiência usando nova lógica de zonas
        zone, rate_multiplier = self._calculate_efficiency_zone(self.current_pwm)

        # Converte multiplicador para porcentagem de eficiência
        if rate_multiplier >= 1.0:
            gear_efficiency = 100.0  # Zona IDEAL
        elif rate_multiplier >= 0.25:
            gear_efficiency = 75.0   # Zona SUBOPTIMAL
        else:
            gear_efficiency = 25.0   # Zona POOR

        # Define faixas ideais para display
        gear_ideal_ranges = {
            1: "0-20%",    # 1ª marcha
            2: "20-40%",   # 2ª marcha
            3: "40-60%",   # 3ª marcha
            4: "60-80%",   # 4ª marcha
            5: "80-100%",  # 5ª marcha
        }
        ideal_range = gear_ideal_ranges.get(self.current_gear, "0-20%")

        # Zona de eficiência F1 por cor (baseada na zona atual)
        if zone == "IDEAL":
            efficiency_zone = "GREEN"    # Zona ideal
        elif zone == "SUBOPTIMAL":
            efficiency_zone = "YELLOW"   # Zona subótima
        else:
            efficiency_zone = "RED"      # Zona ruim

        # RPM tradicional para compatibilidade
        rpm_percent = (self.engine_rpm / self.MOTOR_MAX_RPM) * 100

        return {
            "rpm": round(self.engine_rpm, 0),
            "rpm_percent": round(rpm_percent, 1),
            "rpm_zone": efficiency_zone,  # Agora baseado na eficiência F1
            "gear": self.current_gear,
            "speed_kmh": round(self.calculated_speed_kmh, 1),
            "shift_light": gear_efficiency < 70,  # Luz acende se eficiência baixa
            "max_rpm": self.MOTOR_MAX_RPM,
            # NOVOS DADOS F1
            "gear_efficiency": round(gear_efficiency, 1),
            "efficiency_zone": self.efficiency_zone,
            "zone_acceleration_rate": self.zone_acceleration_rate,
            "ideal_pwm_range": ideal_range,
            "current_pwm": round(self.current_pwm, 1),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Obtém estatísticas de operação

        Returns:
            dict: Estatísticas completas
        """
        elapsed = time.time() - self.start_time

        return {
            "total_runtime": round(self.total_runtime, 2),
            "system_uptime": round(elapsed, 2),
            "total_distance": round(self.total_distance, 4),
            "gear_changes": self.gear_changes,
            "engine_starts": self.engine_starts,
            "average_speed": (
                round(self.total_distance / (self.total_runtime / 3600), 1)
                if self.total_runtime > 0
                else 0
            ),
            "gear_changes_per_minute": (
                round(self.gear_changes / (elapsed / 60), 2) if elapsed > 0 else 0
            ),
            "current_gear": self.current_gear,
            "transmission_mode": "manual",
        }

    def cleanup(self):
        """Libera recursos do motor"""
        try:
            print("Finalizando sistema de motor...")

            # Para motor
            self.emergency_stop()
            time.sleep(0.1)

            # Para thread de controle
            self.should_stop = True
            if self.acceleration_thread and self.acceleration_thread.is_alive():
                self.acceleration_thread.join(timeout=1.0)

            # Para PWM
            if GPIO_AVAILABLE:
                if self.rpwm:
                    self.rpwm.stop()
                if self.lpwm:
                    self.lpwm.stop()

                # Desabilita ponte H
                GPIO.output(self.r_en_pin, GPIO.LOW)
                GPIO.output(self.l_en_pin, GPIO.LOW)

                # Cleanup GPIO
                GPIO.cleanup(
                    [self.rpwm_pin, self.lpwm_pin, self.r_en_pin, self.l_en_pin]
                )

            self.is_initialized = False
            print("✓ Sistema de motor finalizado")

        except Exception as e:
            print(f"⚠ Erro ao finalizar motor: {e}")

    def __del__(self):
        """Destrutor - garante limpeza dos recursos"""
        self.cleanup()


# Exemplo de uso
if __name__ == "__main__":
    print("=== TESTE DO SISTEMA DE MOTOR ===")

    # Cria instância do motor
    motor_mgr = MotorManager()

    # Inicializa
    if motor_mgr.initialize():
        print("\n=== TESTE DE ACELERAÇÃO ===")

        # Teste 1: Aceleração gradual
        print("1. Aceleração gradual...")
        for throttle in [0, 20, 40, 60, 80, 100, 80, 40, 0]:
            print(f"   Acelerador: {throttle}%")
            motor_mgr.set_throttle(throttle)

            # Aguarda e mostra dados
            time.sleep(2.0)
            status = motor_mgr.get_motor_status()
            tacho = motor_mgr.get_tachometer_data()

            print(
                f"   Status: {status['current_pwm']:.1f}% PWM, "
                f"{tacho['rpm']:.0f} RPM, "
                f"Marcha {status['current_gear']}ª, "
                f"{status['speed_kmh']:.1f} km/h"
            )

        # Teste 2: Transmissão manual
        print("\n2. Teste transmissão manual...")
        # Transmissão já é manual por padrão
        motor_mgr.set_throttle(40.0)  # 40% acelerador

        for gear in [1, 2, 3, 4, 3, 2, 1]:
            print(f"   Trocando para marcha {gear}ª...")
            motor_mgr.manual_shift(gear)
            time.sleep(1.5)

            status = motor_mgr.get_motor_status()
            print(
                f"   Marcha {status['current_gear']}ª, "
                f"Relação {status['gear_ratio']:.1f}:1, "
                f"{status['speed_kmh']:.1f} km/h"
            )

        # Teste 3: Ré
        print("\n3. Teste de ré...")
        motor_mgr.set_throttle(0.0)
        time.sleep(1.0)

        motor_mgr.set_reverse(True)
        motor_mgr.set_throttle(30.0)
        time.sleep(2.0)

        status = motor_mgr.get_motor_status()
        print(f"   Ré: {status['motor_direction']}, " f"{status['speed_kmh']:.1f} km/h")

        # Para motor
        motor_mgr.set_throttle(0.0)
        motor_mgr.set_reverse(False)
        time.sleep(1.0)

        # Estatísticas finais
        stats = motor_mgr.get_statistics()
        print(f"\n=== ESTATÍSTICAS FINAIS ===")
        print(f"Tempo de operação: {stats['total_runtime']:.1f}s")
        print(f"Distância percorrida: {stats['total_distance']:.3f} km")
        print(f"Trocas de marcha: {stats['gear_changes']}")
        print(f"Partidas do motor: {stats['engine_starts']}")
        print(f"Velocidade média: {stats['average_speed']:.1f} km/h")

        # Finaliza
        motor_mgr.cleanup()

    else:
        print("✗ Falha ao inicializar motor")
        print("\nPara usar com hardware real:")
        print("1. Conecte ponte H BTS7960 conforme pinout")
        print("2. Alimentação 12V para motor (V+/V-)")
        print("3. Alimentação 5V para lógica (VCC/GND)")
        print("4. Enables em HIGH para operação")
        print("5. sudo apt-get install python3-rpi.gpio")
