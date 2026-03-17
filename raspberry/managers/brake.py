#!/usr/bin/env python3
"""
brake_manager.py - Sistema de Freios do Carrinho F1
Controla freios dianteiros e traseiros com servo MG996R via PCA9685

PINOUT PCA9685 + SERVOS MG996R:
===============================
Pinos do módulo PCA9685: GND ; OE ; SCL ; SDA ; VCC ; V+

PCA9685 -> Raspberry Pi 4 (I2C) [COMPARTILHADO COM DIREÇÃO]
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

Servo Freio Dianteiro -> PCA9685
  - VCC (Vermelho)  -> V+ do PCA9685 (alimentado pelo UBEC)
  - GND (Marrom)    -> GND
  - Signal (Laranja)-> Canal 4 do PCA9685

Servo Freio Traseiro -> PCA9685
  - VCC (Vermelho)  -> V+ do PCA9685 (alimentado pelo UBEC)
  - GND (Marrom)    -> GND
  - Signal (Laranja)-> Canal 8 do PCA9685

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
    │ PCA9685 │──── Servo Freio Frontal (Canal 0) ← ESTE ARQUIVO
    │   V+    │──── Servo Freio Traseiro (Canal 1) ← ESTE ARQUIVO
    └─────────┘──── Servo Direção (Canal 2)

CARACTERÍSTICAS UBEC 15A:
=========================
  - Tensão de Entrada: 6-12S (23V a 45V) [Usando 3S: 9V-12.6V]
  - Tensão de Saída: 5.25V ±0.5V
  - Corrente Contínua: 15A (suficiente para 3 servos ~4.5A)
  - Corrente de Pico: 30A (10 segundos)
  - Dimensões: 55 x 28 x 5 mm

MAPEAMENTO DE PINOS OCUPADOS NO PROJETO:
========================================
PINOS I2C (PCA9685 + BMI160):
- GPIO2/Pin 3  -> SDA (I2C Data) - OCUPADO
- GPIO3/Pin 5  -> SCL (I2C Clock) - OCUPADO

PINOS GPIO LIBERADOS (agora usando PCA9685):
- GPIO4/Pin 7   -> LIBERADO (era freio frontal)
- GPIO17/Pin 11 -> LIBERADO (era freio traseiro)
- GPIO24/Pin 18 -> LIBERADO (era direção - agora no PCA9685)

PINOS OCUPADOS POR OUTROS COMPONENTES:
- GPIO18/Pin 12 -> Motor BTS7960 RPWM (OCUPADO)
- GPIO27/Pin 13 -> Motor BTS7960 LPWM (OCUPADO)
- GPIO22/Pin 15 -> Motor BTS7960 R_EN (OCUPADO)
- GPIO23/Pin 16 -> Motor BTS7960 L_EN (OCUPADO)
- GPIO25/Pin 22 -> Sensor temperatura DS18B20 (OCUPADO)

CARACTERÍSTICAS MG996R:
======================
- Tensão: 4.8V - 7.2V (recomendado 6V para torque máximo)
- Torque: 11kg.cm @ 6V
- Velocidade: 0.14s/60° @ 6V
- Ângulo: 0° - 180° (0°=solto, 90°=neutro, 180°=máximo)
- PWM: 50Hz, pulso 1.0ms-2.0ms
- Corrente: ~1.5A sob carga máxima

CONFIGURAÇÃO NECESSÁRIA:
=======================
sudo raspi-config -> Interface Options -> I2C -> Enable
sudo apt-get install python3-pip
sudo pip3 install adafruit-circuitpython-pca9685
"""

import threading
import time

import board
import busio
from adafruit_motor import servo
from adafruit_pca9685 import PCA9685

from managers.logger import debug, error, info, warn


class BrakeManager:
    """Gerencia sistema de freios dianteiro e traseiro via PCA9685"""

    # ================== CONFIGURAÇÕES FÍSICAS ==================

    # Canais PCA9685 dos servos (mapeamento completo do projeto)
    FRONT_BRAKE_CHANNEL = 4  # Canal 4 do PCA9685 - Freio frontal
    REAR_BRAKE_CHANNEL = 8  # Canal 8 do PCA9685 - Freio traseiro
    # STEERING_CHANNEL = 0     # Canal 0 do PCA9685 - Direção (usado pelo steering_manager)

    # Endereço I2C do PCA9685
    PCA9685_I2C_ADDRESS = 0x41  # PCA9685 com A0 soldado (evita conflito com INA219 em 0x40)

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
        front_channel: int = None,
        rear_channel: int = None,
        pca9685_address: int = None,
        brake_balance: float = 50.0,  # 50% = balanceado
        max_brake_force: float = 100.0,
        response_time: float = 0.1,
        i2c_lock=None,  # Lock compartilhado do bus I2C
    ):
        """
        Inicializa o sistema de freios

        Args:
            front_channel (int): Canal PCA9685 do servo freio dianteiro
            rear_channel (int): Canal PCA9685 do servo freio traseiro
            pca9685_address (int): Endereço I2C do PCA9685
            brake_balance (float): Balanço de freio 0-100% (0=mais dianteiro, 100=mais traseiro)
            max_brake_force (float): Força máxima de freio 0-100%
            response_time (float): Tempo de resposta do servo em segundos
            i2c_lock: threading.Lock compartilhado entre dispositivos I2C
        """
        self.i2c_lock = i2c_lock
        self.front_channel = front_channel or self.FRONT_BRAKE_CHANNEL
        self.rear_channel = rear_channel or self.REAR_BRAKE_CHANNEL
        self.pca9685_address = pca9685_address or self.PCA9685_I2C_ADDRESS

        # Lock para thread-safety (acesso concorrente por threads de comando e TX)
        self.state_lock = threading.Lock()

        # Configurações de freio
        self.brake_balance = max(0.0, min(100.0, brake_balance))  # 0-100%
        self.max_brake_force = max(0.0, min(100.0, max_brake_force))  # 0-100%
        self.response_time = max(0.05, response_time)  # Mínimo 50ms

        # Estado atual dos freios
        self.front_brake_angle = (
            self.BRAKE_MIN_ANGLE
        )  # Ângulo atual do servo dianteiro (0° = solto)
        self.rear_brake_angle = (
            self.BRAKE_MIN_ANGLE
        )  # Ângulo atual do servo traseiro (0° = solto)
        self.front_brake_force = 0.0  # Força atual 0-100%
        self.rear_brake_force = 0.0  # Força atual 0-100%
        self.total_brake_input = 0.0  # Input total 0-100%

        # Estado dos servos e PCA9685
        self.is_initialized = False
        self.pca9685 = None
        self.i2c = None
        self.front_servo = None
        self.rear_servo = None
        self._last_front_angle = None  # Dedup I2C writes
        self._last_rear_angle = None

        # Estatísticas
        self.brake_applications = 0
        self.total_brake_time = 0.0
        self.last_brake_time = 0.0
        self.start_time = time.time()
        self._last_log_time = 0.0

    def initialize(self) -> bool:
        """
        Inicializa o sistema de freios via PCA9685

        Returns:
            bool: True se inicializado com sucesso
        """
        info(f"Inicializando freios | Canais: front={self.front_channel} rear={self.rear_channel} | I2C: 0x{self.pca9685_address:02X} | Balanço: {self.brake_balance:.1f}%", "BRAKE")

        try:
            # Inicializa barramento I2C
            self.i2c = busio.I2C(board.SCL, board.SDA)
            debug("I2C inicializado", "BRAKE")

            # Inicializa PCA9685
            self.pca9685 = PCA9685(self.i2c, address=self.pca9685_address)
            self.pca9685.frequency = self.PWM_FREQUENCY
            debug(f"PCA9685 inicializado @ {self.PWM_FREQUENCY}Hz", "BRAKE")

            # Configura servos nos canais especificados
            self.front_servo = servo.Servo(
                self.pca9685.channels[self.front_channel],
                min_pulse=int(self.PULSE_MIN * 1000),  # converte para microssegundos
                max_pulse=int(self.PULSE_MAX * 1000),
            )

            self.rear_servo = servo.Servo(
                self.pca9685.channels[self.rear_channel],
                min_pulse=int(self.PULSE_MIN * 1000),  # converte para microssegundos
                max_pulse=int(self.PULSE_MAX * 1000),
            )
            debug(f"Servos configurados (canais {self.front_channel} e {self.rear_channel})", "BRAKE")

            # Posiciona servos na posição solta (freios liberados)
            if self.i2c_lock:
                self.i2c_lock.acquire(priority=0)  # Alta
                try:
                    self.front_servo.angle = self.BRAKE_MIN_ANGLE
                    self.rear_servo.angle = self.BRAKE_MIN_ANGLE
                finally:
                    self.i2c_lock.release()
            else:
                self.front_servo.angle = self.BRAKE_MIN_ANGLE
                self.rear_servo.angle = self.BRAKE_MIN_ANGLE
            # Aguarda servos se posicionarem
            time.sleep(0.5)

            self.is_initialized = True
            info(f"Freios inicializados | PWM: {self.PWM_FREQUENCY}Hz | Canais: {self.front_channel}/{self.rear_channel}", "BRAKE")

            # Teste rápido dos servos
            self._test_servos()

            return True

        except Exception as e:
            error(f"Erro ao inicializar freios: {e} | Verifique: PCA9685 I2C, canais, alimentação servos 6V", "BRAKE")

            self.is_initialized = False
            return False

    def set_brake_balance(self, balance: float):
        """
        Define o balanço de freio entre dianteiro e traseiro

        Args:
            balance (float): Balanço 0-100% (0=mais dianteiro, 100=mais traseiro)
        """
        with self.state_lock:
            old_balance = self.brake_balance
            self.brake_balance = max(0.0, min(100.0, balance))

            if abs(self.brake_balance - old_balance) > 0.1:
                info(f"Balanço de freio alterado: {self.brake_balance:.1f}%", "BRAKE")

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
            return

        # Garante que o input está no range válido
        brake_input = max(0.0, min(100.0, brake_input))

        with self.state_lock:
            self.total_brake_input = brake_input

            # Calcula distribuição entre dianteiro e traseiro
            self._calculate_brake_distribution(brake_input)

            # Atualiza estatísticas
            if brake_input > 0:
                current_time = time.time()
                if self.last_brake_time == 0:
                    self.brake_applications += 1
                self.last_brake_time = current_time

            # Log rate limited a cada 1s
            now = time.time()
            if now - self._last_log_time >= 1.0 and brake_input > 0:
                self._last_log_time = now
                debug(f"Freio: {brake_input:.1f}% (Diant: {self.front_brake_force:.1f}%, Tras: {self.rear_brake_force:.1f}%)", "BRAKE")

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
        # 0% força = BRAKE_MIN_ANGLE (0° = freio solto)
        # 100% força = BRAKE_MAX_ANGLE (180° = freio máximo)

        front_range = self.BRAKE_MAX_ANGLE - self.BRAKE_MIN_ANGLE
        rear_range = self.BRAKE_MAX_ANGLE - self.BRAKE_MIN_ANGLE

        front_angle = (
            self.BRAKE_MIN_ANGLE + (self.front_brake_force / 100.0) * front_range
        )
        rear_angle = self.BRAKE_MIN_ANGLE + (self.rear_brake_force / 100.0) * rear_range

        # MOVIMENTO DIRETO - igual aos testes funcionais
        self.front_brake_angle = front_angle
        self.rear_brake_angle = rear_angle

        if self.front_servo and self.rear_servo:
            # Limita ângulos ao range válido (0° a 180°)
            front_angle = max(
                self.BRAKE_MIN_ANGLE,
                min(self.BRAKE_MAX_ANGLE, self.front_brake_angle),
            )
            rear_angle = max(
                self.BRAKE_MIN_ANGLE,
                min(self.BRAKE_MAX_ANGLE, self.rear_brake_angle),
            )

            # Só escreve no I2C se o ângulo mudou (dedup)
            front_changed = self._last_front_angle is None or abs(front_angle - self._last_front_angle) >= 0.1
            rear_changed = self._last_rear_angle is None or abs(rear_angle - self._last_rear_angle) >= 0.1
            if front_changed or rear_changed:
                if self.i2c_lock:
                    self.i2c_lock.acquire(priority=0)  # Alta
                    try:
                        if front_changed:
                            self.front_servo.angle = front_angle
                        if rear_changed:
                            self.rear_servo.angle = rear_angle
                    finally:
                        self.i2c_lock.release()
                else:
                    if front_changed:
                        self.front_servo.angle = front_angle
                    if rear_changed:
                        self.rear_servo.angle = rear_angle
                if front_changed:
                    self._last_front_angle = front_angle
                if rear_changed:
                    self._last_rear_angle = rear_angle
        else:
            warn("Servos de freio não inicializados!", "BRAKE")

    def release_brakes(self):
        """Libera completamente os freios"""
        self.apply_brake(0.0)
        debug("Freios liberados", "BRAKE")

    def emergency_brake(self):
        """Aplica freio de emergência (força máxima)"""
        self.apply_brake(100.0)
        warn("FREIO DE EMERGÊNCIA ATIVADO!", "BRAKE")

    def _test_servos(self):
        """Executa teste rápido dos servos - MOVIMENTO DIRETO"""
        debug("Executando teste dos servos...", "BRAKE")

        try:
            old_balance = self.brake_balance
            self.set_brake_balance(0.0)
            self.apply_brake(30.0)
            time.sleep(0.5)
            self.set_brake_balance(100.0)
            time.sleep(0.5)
            self.set_brake_balance(old_balance)
            self.release_brakes()
            time.sleep(0.5)
            debug("Teste dos servos concluído", "BRAKE")

        except Exception as e:
            warn(f"Erro durante teste: {e}", "BRAKE")

    def get_brake_status(self) -> dict:
        """
        Obtém status completo do sistema de freios

        Returns:
            dict: Status atual dos freios
        """
        with self.state_lock:
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
                # === STATUS TÉCNICO ===
                "is_initialized": self.is_initialized,
                # === ESTATÍSTICAS ===
                "brake_applications": self.brake_applications,
                "total_brake_time": round(self.total_brake_time, 2),
                "is_braking": self.total_brake_input > 0,
                # === HARDWARE ===
                "front_channel": self.front_channel,
                "rear_channel": self.rear_channel,
                "pca9685_address": f"0x{self.pca9685_address:02X}",
                "pwm_frequency": self.PWM_FREQUENCY,
                "pca9685_available": True,
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
        }

    def cleanup(self):
        """Libera recursos do sistema de freios"""
        try:
            debug("Finalizando sistema de freios...", "BRAKE")

            # Libera freios antes de desligar
            self.release_brakes()
            time.sleep(0.2)

            # Libera recursos do PCA9685
            if self.front_servo:
                self.front_servo = None
            if self.rear_servo:
                self.rear_servo = None
            if self.pca9685:
                self.pca9685.deinit()
                self.pca9685 = None
            if self.i2c:
                self.i2c.deinit()
                self.i2c = None

            self.is_initialized = False
            info("Sistema de freios finalizado", "BRAKE")

        except Exception as e:
            warn(f"Erro ao finalizar sistema de freios: {e}", "BRAKE")

    def __del__(self):
        """Destrutor - garante limpeza dos recursos"""
        self.cleanup()
