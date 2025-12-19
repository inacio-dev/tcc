#!/usr/bin/env python3
"""
motor_manager.py - Sistema de Motor DC e Transmissão com 5 Marchas
Controla motor RC 775 via ponte H BTS7960 (HW-039)

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

Motor RC 775 -> Ponte H BTS7960:
- Motor+ -> B+
- Motor- -> B-

Alimentação Motor -> Ponte H:
- V+ (12V) -> B+VCC (Positivo bateria)
- V- (GND) -> B-VCC (Negativo bateria)

CARACTERÍSTICAS RC 775:
======================
- Tensão: 12V nominal (12V-18V)
- RPM: 6000-10000 @ 12V (típico 9000 sob carga)
- Corrente: ~5A @ 12V carga normal, pico 30A
- Torque: Alto torque de partida
- Potência: ~300W

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

import threading
import time
from enum import Enum
from typing import Any, Dict

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


class MotorManager:
    """Gerencia motor DC RC 775 com transmissão simulada de 5 marchas"""

    # ================== CONFIGURAÇÕES FÍSICAS ==================

    # Pinos GPIO da ponte H BTS7960
    RPWM_PIN = 18  # GPIO18 - Pin 12 - PWM direção frente
    LPWM_PIN = 27  # GPIO27 - Pin 13 - PWM direção ré
    R_EN_PIN = 22  # GPIO22 - Pin 15 - Enable frente
    L_EN_PIN = 23  # GPIO23 - Pin 16 - Enable esquerda

    # Configurações PWM
    PWM_FREQUENCY = 2000  # 2kHz - boa para motores DC
    PWM_MAX = 100  # Duty cycle máximo

    # Características do motor RC 775
    MOTOR_MAX_RPM = 9000  # RPM máximo @ 12V sob carga (spec: 6000-10000)
    MOTOR_MIN_RPM = 600  # RPM mínimo estável
    MOTOR_IDLE_RPM = 800  # RPM marcha lenta

    # Sistema de transmissão (5 marchas)
    GEAR_RATIOS = {
        1: 3.5,  # 1ª marcha - maior torque, arranque
        2: 2.2,  # 2ª marcha - aceleração
        3: 1.4,  # 3ª marcha - velocidade média
        4: 0.9,  # 4ª marcha - velocidade alta
        5: 0.7,  # 5ª marcha - velocidade máxima (100% potência)
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

        # Lock para thread-safety (acesso concorrente por threads de comando e TX)
        self.state_lock = threading.Lock()

        # Estado do motor
        self.is_initialized = False
        self.motor_direction = MotorDirection.STOP
        self.current_pwm = 0.0  # PWM atual 0-100%
        self.target_pwm = 0.0  # PWM alvo 0-100%

        # Sistema de transmissão
        self.current_gear = 1  # Marcha atual (1-8)
        self.gear_ratio = self.GEAR_RATIOS[1]
        self.clutch_engaged = True  # Embreagem
        self.is_shifting = False  # Em processo de troca
        self.shift_time = 0.3  # Tempo de troca em segundos
        self.last_throttle_percent = (
            0.0  # CORREÇÃO: Armazena último throttle para reaplicar após troca
        )

        # SISTEMA F1 DE ZONAS DE EFICIÊNCIA
        self.efficiency_zone = "IDEAL"  # IDEAL, SUBOPTIMAL, POOR
        self.zone_acceleration_rate = 1.0  # Multiplicador de aceleração baseado na zona
        self.base_acceleration_time = (
            5.0  # Tempo base para atingir zona ideal (5s - mais lento)
        )
        self.last_zone_check = time.time()

        # Motor não tem sensor de RPM - apenas controle PWM

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
        print("Motor: RC 775 12V via ponte H BTS7960")
        print(
            f"RPWM (Frente): GPIO{self.rpwm_pin} (Pin {self._gpio_to_pin(self.rpwm_pin)})"
        )
        print(
            f"LPWM (Ré): GPIO{self.lpwm_pin} (Pin {self._gpio_to_pin(self.lpwm_pin)})"
        )
        print(f"R_EN: GPIO{self.r_en_pin} (Pin {self._gpio_to_pin(self.r_en_pin)})")
        print(f"L_EN: GPIO{self.l_en_pin} (Pin {self._gpio_to_pin(self.l_en_pin)})")
        print("Transmissão: MANUAL - 5 marchas")

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
            print("  - Modo transmissão: manual")
            print("  - Resposta instantânea: motor responde imediatamente")

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
        print(
            f"🧵 Thread loop iniciado (should_stop={self.should_stop}, is_initialized={self.is_initialized})"
        )
        while not self.should_stop and self.is_initialized:
            try:
                current_time = time.time()
                dt = current_time - self.last_update_time

                # SISTEMA F1: Aceleração baseada em zonas de eficiência
                self._apply_f1_zone_acceleration(dt)

                # Aplica PWM ao motor
                self._apply_motor_pwm()

                # Atualiza estatísticas
                self._update_statistics(dt)

                self.last_update_time = current_time
                time.sleep(0.02)  # 50Hz de atualização

            except Exception as e:
                print(f"⚠ Erro no controle do motor: {e}")
                time.sleep(0.1)

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
            f"(PWM: {self.current_pwm:.1f}%)"
        )

        self.is_shifting = True

        # Thread para simular tempo de troca
        def shift_process():
            # Desengate embreagem
            self.clutch_engaged = False

            # Aguarda tempo de troca
            time.sleep(self.shift_time)

            # Troca marcha
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
            # Isso também força recálculo do conta-giros (zona de eficiência)
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

        print(
            f"🔄 THROTTLE reaplicado: {self.last_throttle_percent}% → PWM: {intelligent_pwm:.1f}% (nova marcha: {self.current_gear}ª)"
        )

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

        # Distância percorrida será calculada pelos dados do BMI160

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

        with self.state_lock:
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
                    self.target_pwm = min_motor_pwm + (throttle_percent / 100.0) * (
                        100.0 - min_motor_pwm
                    )
                else:
                    self.target_pwm = throttle_percent
            else:
                self.target_pwm = throttle_percent

            # Calcula PWM inteligente baseado na marcha e velocidade
            intelligent_pwm = self._calculate_intelligent_pwm(throttle_percent)

            # Define target PWM para a thread aplicar gradualmente
            self.target_pwm = intelligent_pwm

        # Debug temporário para verificar comandos
        print(
            f"🚗 THROTTLE: {throttle_percent}% → PWM target: {intelligent_pwm:.1f}% (marcha: {self.current_gear}ª)"
        )

        # Log removido daqui - será feito no main.py com todos os dados

    def _calculate_intelligent_pwm(self, throttle_percent: float) -> float:
        """
        Calcula PWM do motor F1 com limitadores dinâmicos por marcha

        Sistema F1 com limitadores:
        - 1ª marcha: limitador 40% (zona ruim até 30+10%)
        - 2ª marcha: limitador 60% (zona ruim até 50+10%)
        - 3ª marcha: limitador 80% (zona ruim até 70+10%)
        - 4ª marcha: limitador 100% (zona ruim até 90+10%, cap 100%)
        - 5ª marcha: limitador 100% (sem limite real)

        Args:
            throttle_percent (float): Posição do acelerador (0-100%)

        Returns:
            float: PWM motor real a ser aplicado (0-limitador%)
        """
        # Limitadores dinâmicos por marcha
        gear_limiters = {
            1: 40,  # 1ª marcha: máximo 40% (30+10)
            2: 60,  # 2ª marcha: máximo 60% (50+10)
            3: 80,  # 3ª marcha: máximo 80% (70+10)
            4: 100,  # 4ª marcha: máximo 100% (90+10, cap)
            5: 100,  # 5ª marcha: máximo 100% (sem limite)
        }

        # Obter limitador da marcha atual
        max_pwm = gear_limiters.get(self.current_gear, 40)

        # Mapeia throttle (0-100%) para (0-limitador%)
        final_pwm = (throttle_percent / 100.0) * max_pwm

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
        # Zonas F1 com limitadores por marcha
        if self.current_gear == 1:
            # 1ª MARCHA (limitador: 40%)
            if 0 <= current_pwm <= 20:
                return "IDEAL", 1.0  # 0-20%: Alta eficiência
            elif 20 < current_pwm <= 30:
                return "SUBOPTIMAL", 0.1  # 20-30%: Média eficiência (10x mais lento)
            else:  # 30-40%
                return "POOR", 0.04  # 30-40%: Baixa eficiência (25x mais lento)

        elif self.current_gear == 2:
            # 2ª MARCHA (limitador: 60%)
            if 20 <= current_pwm <= 40:
                return "IDEAL", 1.0  # 20-40%: Alta eficiência
            elif (10 <= current_pwm < 20) or (40 < current_pwm <= 50):
                return (
                    "SUBOPTIMAL",
                    0.1,
                )  # 10-20% e 40-50%: Média eficiência (10x mais lento)
            else:  # 0-10% e 50-60%
                return "POOR", 0.04  # Baixa eficiência (25x mais lento)

        elif self.current_gear == 3:
            # 3ª MARCHA (limitador: 80%)
            if 40 <= current_pwm <= 60:
                return "IDEAL", 1.0  # 40-60%: Alta eficiência
            elif (30 <= current_pwm < 40) or (60 < current_pwm <= 70):
                return (
                    "SUBOPTIMAL",
                    0.1,
                )  # 30-40% e 60-70%: Média eficiência (10x mais lento)
            else:  # 0-30% e 70-80%
                return "POOR", 0.04  # Baixa eficiência (25x mais lento)

        elif self.current_gear == 4:
            # 4ª MARCHA (limitador: 100%)
            if 60 <= current_pwm <= 80:
                return "IDEAL", 1.0  # 60-80%: Alta eficiência
            elif (50 <= current_pwm < 60) or (80 < current_pwm <= 90):
                return (
                    "SUBOPTIMAL",
                    0.1,
                )  # 50-60% e 80-90%: Média eficiência (10x mais lento)
            else:  # 0-50% e 90-100%
                return "POOR", 0.04  # Baixa eficiência (25x mais lento)

        elif self.current_gear == 5:
            # 5ª MARCHA (limitador: 100% - sem limite real)
            if 80 <= current_pwm <= 100:
                return "IDEAL", 1.0  # 80-100%: Alta eficiência
            elif 70 <= current_pwm < 80:
                return "SUBOPTIMAL", 0.1  # 70-80%: Média eficiência (10x mais lento)
            else:  # 0-70%
                return "POOR", 0.04  # Baixa eficiência (25x mais lento)

        # Fallback para marchas não definidas
        return "POOR", 0.04

    def _calculate_efficiency_zone_percentage(self, current_pwm: float) -> float:
        """
        Calcula porcentagem dentro da zona IDEAL de eficiência da marcha atual

        Para cada marcha, mapeia a zona IDEAL para 0-100%:
        - 1ª marcha (0-20%): PWM de 0-20% → 0-100% no conta-giros
        - 2ª marcha (20-40%): PWM de 20-40% → 0-100% no conta-giros
        - 3ª marcha (40-60%): PWM de 40-60% → 0-100% no conta-giros
        - 4ª marcha (60-80%): PWM de 60-80% → 0-100% no conta-giros
        - 5ª marcha (80-100%): PWM de 80-100% → 0-100% no conta-giros

        Fora da zona ideal permanece 0% (abaixo) ou 100% (acima)

        Args:
            current_pwm (float): PWM atual do motor

        Returns:
            float: Porcentagem 0-100% dentro da zona ideal
        """
        # Define zonas ideais por marcha
        ideal_zones = {
            1: (0, 20),  # 1ª marcha: 0-20%
            2: (20, 40),  # 2ª marcha: 20-40%
            3: (40, 60),  # 3ª marcha: 40-60%
            4: (60, 80),  # 4ª marcha: 60-80%
            5: (80, 100),  # 5ª marcha: 80-100%
        }

        if self.current_gear not in ideal_zones:
            return 0.0

        zone_min, zone_max = ideal_zones[self.current_gear]

        # Se está abaixo da zona ideal
        if current_pwm < zone_min:
            return 0.0

        # Se está acima da zona ideal
        if current_pwm > zone_max:
            return 100.0

        # Se está dentro da zona ideal, mapeia para 0-100%
        zone_range = zone_max - zone_min
        pwm_position = current_pwm - zone_min
        percentage = (pwm_position / zone_range) * 100.0

        return min(100.0, max(0.0, percentage))

    def _apply_f1_zone_acceleration(self, dt: float):
        """
        Aplica aceleração/desaceleração F1 baseada em zonas de eficiência

        Sistema F1 (MUITO EXIGENTE):

        ACELERAÇÃO:
        - Zona IDEAL: 5s para atingir target (aceleração normal)
        - Zona SUBÓTIMA: 50s para atingir target (10x mais lento)
        - Zona RUIM: 125s para atingir target (25x mais lento)

        DESACELERAÇÃO (sempre mais rápida):
        - Zona IDEAL: 2.5s para desacelerar (2x mais rápido)
        - Zona SUBÓTIMA: 10s para desacelerar (5x mais rápido que aceleração)
        - Zona RUIM: 12.5s para desacelerar (10x mais rápido que aceleração)

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
        base_acceleration_per_frame = 50.0 / (
            self.base_acceleration_time * 50
        )  # %PWM por frame
        zone_acceleration = base_acceleration_per_frame * rate_multiplier

        # Sistema diferenciado para aceleração vs desaceleração
        if pwm_diff > 0:  # ACELERANDO - usa zona de eficiência
            acceleration_step = min(zone_acceleration * dt * 50, pwm_diff)  # 50Hz
            self.current_pwm += acceleration_step

        else:  # DESACELERANDO - mais rápido e inteligente
            # Desaceleração baseada na zona atual, mas sempre mais rápida
            if rate_multiplier >= 1.0:  # Zona IDEAL
                decel_multiplier = 2.0  # 2x mais rápido que aceleração
            elif rate_multiplier >= 0.1:  # Zona SUBÓTIMA
                decel_multiplier = 5.0  # 5x mais rápido que aceleração
            else:  # Zona RUIM
                decel_multiplier = 10.0  # 10x mais rápido que aceleração

            # Aplica desaceleração melhorada
            deceleration_rate = base_acceleration_per_frame * decel_multiplier
            deceleration_step = min(deceleration_rate * dt * 50, abs(pwm_diff))
            self.current_pwm -= deceleration_step

        # Debug zona a cada 1s
        current_time = time.time()
        if current_time - self.last_zone_check >= 1.0:
            self.last_zone_check = current_time
            if abs(pwm_diff) > 0.5:  # Só mostra se ainda está mudando
                action = "⬆️ ACELERANDO" if pwm_diff > 0 else "⬇️ DESACELERANDO"
                if pwm_diff > 0:
                    rate_info = f"Rate: {rate_multiplier:.2f}x"
                else:
                    decel_mult = (
                        2.0
                        if rate_multiplier >= 1.0
                        else (5.0 if rate_multiplier >= 0.1 else 10.0)
                    )
                    rate_info = f"Decel: {decel_mult:.1f}x mais rápido"
                print(
                    f"🏁 F1 Zone: {zone} | PWM: {self.current_pwm:.1f}%→{self.target_pwm:.1f}% | {action} | {rate_info}"
                )

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
        with self.state_lock:
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
        with self.state_lock:
            if self.current_gear <= 1:
                return False  # Já está na marcha mínima
            new_gear = self.current_gear - 1

        # Troca manual - sem alterar modo de transmissão
        self._shift_gear(new_gear)
        return True

    def get_motor_status(self) -> Dict[str, Any]:
        """
        Obtém status completo do motor

        Returns:
            dict: Status atual do motor e transmissão
        """
        with self.state_lock:
            return {
                # === MOTOR ===
                "motor_direction": self.motor_direction.value,
                "current_pwm": round(self.current_pwm, 1),
                "target_pwm": round(self.target_pwm, 1),
                # === TRANSMISSÃO ===
                "current_gear": self.current_gear,
                "gear_ratio": self.gear_ratio,
                "transmission_mode": "manual",
                "clutch_engaged": self.clutch_engaged,
                "is_shifting": self.is_shifting,
                # === CONTA-GIROS ===
                "rpm_display": round(
                    self._calculate_efficiency_zone_percentage(self.current_pwm), 0
                ),
                "max_rpm": self.MOTOR_MAX_RPM,
                "idle_rpm": self.MOTOR_IDLE_RPM,
                "rpm_percent": round(
                    self._calculate_efficiency_zone_percentage(self.current_pwm), 1
                ),
                # === STATUS TÉCNICO ===
                "is_initialized": self.is_initialized,
                "motor_temperature": round(
                    25 + (self.current_pwm * 0.6), 1
                ),  # Simulado
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
            gear_efficiency = 75.0  # Zona SUBOPTIMAL
        else:
            gear_efficiency = 25.0  # Zona POOR

        # Define faixas ideais para display
        gear_ideal_ranges = {
            1: "0-20%",  # 1ª marcha
            2: "20-40%",  # 2ª marcha
            3: "40-60%",  # 3ª marcha
            4: "60-80%",  # 4ª marcha
            5: "80-100%",  # 5ª marcha
        }
        ideal_range = gear_ideal_ranges.get(self.current_gear, "0-20%")

        # Zona de eficiência F1 por cor (baseada na zona atual)
        if zone == "IDEAL":
            efficiency_zone = "GREEN"  # Zona ideal
        elif zone == "SUBOPTIMAL":
            efficiency_zone = "YELLOW"  # Zona subótima
        else:
            efficiency_zone = "RED"  # Zona ruim

        return {
            "rpm": round(
                self._calculate_efficiency_zone_percentage(self.current_pwm), 0
            ),
            "rpm_zone": efficiency_zone,  # Baseado na eficiência F1
            "gear": self.current_gear,
            "shift_light": gear_efficiency < 70,  # Luz acende se eficiência baixa
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
