#!/usr/bin/env python3
"""
motor.py - Motor DC RC 775 + Transmissão 5 Marchas via BTS7960

GPIO:
  RPWM → GPIO18 (Pin 12) - PWM motor
  R_EN → GPIO22 (Pin 15) - Enable ponte H

Zonas de eficiência via sistema de 1ª ordem: τ_eff · dPWM/dt = target - PWM
"""

import threading
import time
from typing import Any, Dict

import RPi.GPIO as GPIO

from managers.logger import debug, error, info, warn


class MotorManager:
    """Gerencia motor DC RC 775 com transmissão simulada de 5 marchas"""

    # ================== CONFIGURAÇÕES FÍSICAS ==================

    # Pinos GPIO da ponte H BTS7960 (apenas frente)
    RPWM_PIN = 18  # GPIO18 - Pin 12 - PWM motor
    R_EN_PIN = 22  # GPIO22 - Pin 15 - Enable frente
    L_EN_PIN = 23  # GPIO23 - Pin 16 - Enable ré (ambos HIGH = ponte H ativa)

    # Configurações PWM
    PWM_FREQUENCY = 2000  # 2kHz - boa para motores DC
    PWM_MAX = 100  # Duty cycle máximo

    # Características do motor RC 775
    MOTOR_MAX_RPM = 9000  # RPM máximo @ 12V sob carga (spec: 6000-10000)
    MOTOR_MIN_RPM = 600  # RPM mínimo estável
    MOTOR_IDLE_RPM = 800  # RPM marcha lenta


    def __init__(
        self,
        rpwm_pin: int = None,
        r_en_pin: int = None,
        l_en_pin: int = None,
    ):
        self.rpwm_pin = rpwm_pin or self.RPWM_PIN
        self.r_en_pin = r_en_pin or self.R_EN_PIN
        self.l_en_pin = l_en_pin or self.L_EN_PIN

        # Lock para thread-safety (acesso concorrente por threads de comando e TX)
        self.state_lock = threading.Lock()

        # Estado do motor
        self.is_initialized = False
        self.is_running = False  # Motor ligado (PWM > 0)
        self.current_pwm = 0.0  # PWM atual 0-100%
        self.target_pwm = 0.0  # PWM alvo 0-100%
        self.brake_input = 0.0  # Freio atual 0-100% (multiplica desaceleração)

        # Sistema de transmissão
        self.current_gear = 1
        self.last_throttle_percent = 0.0

        # Sistema de zonas de eficiência
        self.efficiency_zone = "IDEAL"
        self.last_zone_check = time.time()

        # Motor não tem sensor de RPM - apenas controle PWM

        # Controle PWM
        self.rpwm = None

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
        self._last_throttle_log = 0.0

    def initialize(self) -> bool:
        """
        Inicializa o sistema de motor

        Returns:
            bool: True se inicializado com sucesso
        """
        info(f"Inicializando motor BTS7960 | PWM=GPIO{self.rpwm_pin} R_EN=GPIO{self.r_en_pin} L_EN=GPIO{self.l_en_pin} | 5 marchas", "MOTOR")

        try:
            # Configura GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Configura pinos como saída
            GPIO.setup(self.rpwm_pin, GPIO.OUT)
            GPIO.setup(self.r_en_pin, GPIO.OUT)
            GPIO.setup(self.l_en_pin, GPIO.OUT)

            # Cria objeto PWM
            self.rpwm = GPIO.PWM(self.rpwm_pin, self.PWM_FREQUENCY)

            # Habilita ponte H (AMBOS enables em HIGH — obrigatório no BTS7960)
            GPIO.output(self.r_en_pin, GPIO.HIGH)
            GPIO.output(self.l_en_pin, GPIO.HIGH)

            # Inicia PWM com duty cycle zero
            self.rpwm.start(0)

            # Inicia motor em marcha lenta
            self._start_engine()

            self.is_initialized = True

            if self.current_gear > 5:
                warn(f"Marcha {self.current_gear}ª inválida - redefinindo para 1ª", "MOTOR")
                self.current_gear = 1

            self._start_acceleration_thread()
            info(f"Motor inicializado | PWM: {self.PWM_FREQUENCY}Hz | Marcha: {self.current_gear}ª", "MOTOR")

            return True

        except Exception as e:
            error(f"Erro ao inicializar motor: {e} | Verifique: BTS7960, alimentação 12V, GPIO", "MOTOR")

            self.is_initialized = False
            return False

    def _start_acceleration_thread(self):
        """Inicia thread para controle de aceleração suave"""
        if self.acceleration_thread is None or not self.acceleration_thread.is_alive():
            self.should_stop = False
            self.acceleration_thread = threading.Thread(target=self._acceleration_loop)
            self.acceleration_thread.daemon = True
            self.acceleration_thread.start()
            debug("Thread de aceleração iniciada", "MOTOR")

    def _acceleration_loop(self):
        """Loop principal de controle de aceleração e RPM"""
        debug(f"Thread loop iniciado (should_stop={self.should_stop}, is_initialized={self.is_initialized})", "MOTOR")
        while not self.should_stop and self.is_initialized:
            try:
                current_time = time.time()
                dt = current_time - self.last_update_time

                with self.state_lock:
                    # SISTEMA F1: Aceleração baseada em zonas de eficiência
                    self._apply_f1_acceleration(dt)

                    # Aplica PWM ao motor
                    self._apply_motor_pwm()

                    # Atualiza estatísticas
                    self._update_statistics(dt)

                self.last_update_time = current_time
                time.sleep(0.01)  # 100Hz de atualização

            except Exception as e:
                warn(f"Erro no controle do motor: {e}", "MOTOR")
                time.sleep(0.1)

    def _shift_gear(self, new_gear: int):
        """Executa troca de marcha instantânea e recalcula target PWM."""
        if new_gear < 1 or new_gear > 5 or new_gear == self.current_gear:
            return

        old_gear = self.current_gear
        self.current_gear = new_gear
        self.gear_changes += 1

        # Recalcula target PWM com novo limitador da marcha
        if self.last_throttle_percent > 0:
            self.target_pwm = self._calculate_intelligent_pwm(self.last_throttle_percent)

        info(f"Marcha: {old_gear}ª → {new_gear}ª (PWM target: {self.target_pwm:.1f}%)", "MOTOR")

    def _apply_motor_pwm(self):
        """Aplica PWM ao motor via ponte H"""
        if not self.is_initialized:
            return

        try:
            self.rpwm.ChangeDutyCycle(self.current_pwm)
        except Exception as e:
            warn(f"Erro ao aplicar PWM: {e}", "MOTOR")

    def _start_engine(self):
        """Inicia o motor parado"""
        self.is_running = False
        self.target_pwm = 0.0
        self.current_pwm = 0.0
        self.engine_starts += 1
        debug("Motor iniciado", "MOTOR")

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
            warn("Motor não inicializado", "MOTOR")
            return

        # Garante range válido
        throttle_percent = max(0.0, min(100.0, throttle_percent))

        with self.state_lock:
            # CORREÇÃO: Salva último throttle para reaplicar após troca de marcha
            self.last_throttle_percent = throttle_percent

            self.is_running = throttle_percent > 0

            # Calcula PWM inteligente baseado na marcha (já limita por marcha)
            intelligent_pwm = self._calculate_intelligent_pwm(throttle_percent)

            # Define target PWM para a thread aplicar gradualmente
            self.target_pwm = intelligent_pwm

        # Debug — rate limited a cada 1s para não spammar
        now = time.time()
        if now - self._last_throttle_log >= 1.0 and throttle_percent > 0:
            self._last_throttle_log = now
            debug(f"Throttle: {throttle_percent}% → PWM: {intelligent_pwm:.1f}% (marcha: {self.current_gear}ª)", "MOTOR")

        # Log removido daqui - será feito no main.py com todos os dados

    # ================== SISTEMA DE TRANSMISSÃO F1 ==================
    #
    # Modelo: Sistema de 1ª ordem por marcha com zonas de eficiência
    #
    #   τ_eff(g) · dPWM/dt = target_PWM - current_PWM
    #
    # Onde τ_eff depende da zona em que o PWM se encontra:
    #   - IDEAL:      τ = τ_base(g)       → resposta rápida
    #   - SUBOPTIMAL: τ = τ_base(g) × 10  → resposta lenta
    #   - POOR:       τ = τ_base(g) × 25  → resposta muito lenta
    #
    # Resposta ao degrau: PWM(t) = target × (1 - e^(-t/τ_eff))
    #
    # Parâmetros por marcha: (limiter, ideal_low, ideal_high, τ_base)
    #   - limiter:    PWM máximo da marcha (throttle 100% → limiter%)
    #   - ideal_low:  início da zona ideal
    #   - ideal_high: fim da zona ideal
    #   - τ_base:     constante de tempo na zona ideal (segundos)
    #
    # Zonas ideais se sobrepõem: ideal_low(g+1) < ideal_high(g)
    # No ponto de troca, o PWM já está na zona ideal da próxima marcha.
    # 1ª marcha começa em 0% (sem zona morta).
    #
    # Teto absoluto do motor limitado a 50% de duty cycle para proteger o
    # diferencial do veículo. Mesmo com throttle 100% na 5ª marcha, o PWM
    # real enviado ao BTS7960 nunca passa de 50%.

    GEAR_PARAMS = {
        # gear: (limiter, ideal_low, ideal_high, τ_base)
        1: (10,   0,   7,  2.0),  # 1ª: ideal 0-7%
        2: (20,   6,  15,  4.0),  # 2ª: ideal 6-15% (sobrepõe 1ª em 6-7%)
        3: (30,  12,  25,  6.0),  # 3ª: ideal 12-25% (sobrepõe 2ª em 12-15%)
        4: (40,  22,  35,  8.0),  # 4ª: ideal 22-35% (sobrepõe 3ª em 22-25%)
        5: (50,  32,  48, 10.0),  # 5ª: ideal 32-48% (sobrepõe 4ª em 32-35%)
    }

    # Multiplicadores de τ por zona (quanto maior, mais lento)
    TAU_MULTIPLIER = {"IDEAL": 1.0, "SUBOPTIMAL": 10.0, "POOR": 25.0}

    def _calculate_intelligent_pwm(self, throttle_percent: float) -> float:
        """Mapeia throttle (0-100%) para PWM real limitado pela marcha atual."""
        limiter = self.GEAR_PARAMS[self.current_gear][0]
        return (throttle_percent / 100.0) * limiter

    def _classify_zone(self, current_pwm: float) -> str:
        """
        Classifica a zona de eficiência com base no PWM atual e marcha.

        Zonas por marcha (exemplo 3ª, limiter=30%, ideal 12-25%):
          POOR:       0% — 8.75%  (muito abaixo do ideal)
          SUBOPTIMAL: 8.75% — 12% (abaixo do ideal, transição)
          IDEAL:      12% — 25%   (faixa eficiente)
          SUBOPTIMAL: 25% — 28.25% (acima do ideal, deveria subir marcha)
          POOR:       > 28.25%    (acima do limiter)
        """
        _, ideal_low, ideal_high, _ = self.GEAR_PARAMS[self.current_gear]
        limiter = self.GEAR_PARAMS[self.current_gear][0]

        # Margem subótima: ~25% da largura ideal em cada borda
        ideal_width = ideal_high - ideal_low
        sub_margin = max(ideal_width * 0.25, 2.0)

        sub_low = ideal_low - sub_margin
        sub_high = min(ideal_high + sub_margin, limiter)

        if ideal_low <= current_pwm <= ideal_high:
            return "IDEAL"
        elif sub_low <= current_pwm <= sub_high:
            return "SUBOPTIMAL"
        return "POOR"

    def _get_tau(self, current_pwm: float) -> float:
        """
        Retorna τ efetivo (constante de tempo) para o PWM e marcha atuais.

            τ_eff = τ_base(g) × multiplicador_zona

        Zona IDEAL → τ_base (rápido), SUBOPTIMAL → 10×τ_base, POOR → 25×τ_base.
        """
        tau_base = self.GEAR_PARAMS[self.current_gear][3]
        zone = self._classify_zone(current_pwm)
        return tau_base * self.TAU_MULTIPLIER[zone]

    def _tachometer_percent(self, current_pwm: float) -> float:
        """
        Conta-giros: mapeia PWM para 0-100% dentro da zona ideal da marcha.

        0% = ideal_low, 100% = ideal_high.
        Abaixo de ideal_low → 0%, acima de ideal_high → 100%.
        """
        _, ideal_low, ideal_high, _ = self.GEAR_PARAMS[self.current_gear]

        if current_pwm <= ideal_low:
            return 0.0
        if current_pwm >= ideal_high:
            return 100.0

        return ((current_pwm - ideal_low) / (ideal_high - ideal_low)) * 100.0

    def _apply_f1_acceleration(self, dt: float):
        """
        Aplica aceleração/desaceleração via ODE de 1ª ordem com τ por zona.

        Equação de estado:
            dPWM/dt = (target - PWM) / τ_eff(g, zona)

        Onde τ_eff = τ_base(g) × multiplicador_zona.
        Na zona IDEAL a resposta é rápida (τ_base).
        Fora dela, τ cresce e a resposta fica lenta (penaliza marcha errada).

        Para desaceleração, τ é reduzido (mais responsivo ao soltar acelerador).
        """
        zone = self._classify_zone(self.current_pwm)

        if zone != self.efficiency_zone:
            self.efficiency_zone = zone
            tau = self._get_tau(self.current_pwm)
            debug(f"Zona F1: {zone} (τ={tau:.1f}s)", "MOTOR")

        pwm_diff = self.target_pwm - self.current_pwm

        if abs(pwm_diff) < 0.1:
            self.current_pwm = self.target_pwm
            return

        tau = self._get_tau(self.current_pwm)

        if pwm_diff > 0:  # ACELERANDO
            # dPWM/dt = (target - PWM) / τ
            step = (pwm_diff / tau) * dt
            self.current_pwm += step

        else:  # DESACELERANDO
            # Desaceleração: τ dividido por 3 (mais responsivo ao soltar)
            tau_decel = tau / 3.0

            # Freio multiplica a responsividade (0%=1x, 100%=10x)
            brake_boost = 1.0 + (self.brake_input / 100.0) * 9.0
            tau_decel /= brake_boost

            step = (abs(pwm_diff) / tau_decel) * dt
            self.current_pwm -= min(step, abs(pwm_diff))

        # Debug a cada 1s
        now = time.time()
        if now - self.last_zone_check >= 1.0:
            self.last_zone_check = now
            if abs(pwm_diff) > 0.5:
                action = "ACCEL" if pwm_diff > 0 else "DECEL"
                debug(f"F1: {zone} τ={tau:.1f}s | PWM {self.current_pwm:.1f}%→{self.target_pwm:.1f}% | {action}", "MOTOR")

    def emergency_stop(self):
        """Para motor imediatamente"""
        with self.state_lock:
            self.is_running = False
            self.target_pwm = 0.0
            self.current_pwm = 0.0
        warn("PARADA DE EMERGÊNCIA DO MOTOR!", "MOTOR")

    def shift_gear_up(self) -> bool:
        """
        Sobe uma marcha (controle manual via teclado)

        Returns:
            bool: True se a troca foi bem-sucedida
        """
        with self.state_lock:
            if self.current_gear >= 5:
                return False  # Já está na marcha máxima
            self._shift_gear(self.current_gear + 1)
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
            self._shift_gear(self.current_gear - 1)
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
                "is_running": self.is_running,
                "current_pwm": round(self.current_pwm, 1),
                "target_pwm": round(self.target_pwm, 1),
                # === TRANSMISSÃO ===
                "current_gear": self.current_gear,
                "efficiency_zone": self.efficiency_zone,
                # === CONTA-GIROS ===
                "rpm_display": round(
                    self._tachometer_percent(self.current_pwm), 0
                ),
                "max_rpm": self.MOTOR_MAX_RPM,
                "idle_rpm": self.MOTOR_IDLE_RPM,
                "rpm_percent": round(
                    self._tachometer_percent(self.current_pwm), 1
                ),
                # === STATUS TÉCNICO ===
                "is_initialized": self.is_initialized,
                # === HARDWARE ===
                "rpwm_pin": self.rpwm_pin,
                "pwm_frequency": self.PWM_FREQUENCY,
                # === ESTATÍSTICAS ===
                "gear_changes": self.gear_changes,
                "total_runtime": round(self.total_runtime, 1),
                "total_distance": round(self.total_distance, 3),
                "engine_starts": self.engine_starts,
                # === TIMESTAMP ===
                "timestamp": round(time.time(), 3),
            }

    def cleanup(self):
        """Libera recursos do motor"""
        try:
            debug("Finalizando sistema de motor...", "MOTOR")

            # Para motor
            self.emergency_stop()
            time.sleep(0.1)

            # Para thread de controle
            self.should_stop = True
            if self.acceleration_thread and self.acceleration_thread.is_alive():
                self.acceleration_thread.join(timeout=1.0)

            # Para PWM
            if self.rpwm:
                self.rpwm.stop()

            # Desabilita ponte H (ambos enables)
            GPIO.output(self.r_en_pin, GPIO.LOW)
            GPIO.output(self.l_en_pin, GPIO.LOW)

            # Cleanup GPIO
            GPIO.cleanup([self.rpwm_pin, self.r_en_pin, self.l_en_pin])

            self.is_initialized = False
            info("Sistema de motor finalizado", "MOTOR")

        except Exception as e:
            warn(f"Erro ao finalizar motor: {e}", "MOTOR")

    def __del__(self):
        """Destrutor - garante limpeza dos recursos"""
        self.cleanup()
