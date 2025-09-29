#!/usr/bin/env python3
"""
brake_manager.py - Sistema de Freios do Carrinho F1
Controla freios dianteiros e traseiros com servo MG996R via PCA9685

PINOUT PCA9685 + SERVOS MG996R:
===============================
PCA9685 -> Raspberry Pi 4 (I2C)
- VCC    -> Pin 2 (5V) ou fonte externa 6V
- GND    -> Pin 6 (GND)
- SCL    -> Pin 5 (GPIO3/SCL)
- SDA    -> Pin 3 (GPIO2/SDA)

Servo Freio Dianteiro -> PCA9685
- VCC (Vermelho)  -> V+ (fonte externa 6V recomendada)
- GND (Marrom)    -> GND
- Signal (Laranja)-> Canal 0 do PCA9685

Servo Freio Traseiro -> PCA9685
- VCC (Vermelho)  -> V+ (fonte externa 6V recomendada)
- GND (Marrom)    -> GND
- Signal (Laranja)-> Canal 1 do PCA9685

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

import time

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


class BrakeManager:
    """Gerencia sistema de freios dianteiro e traseiro via PCA9685"""

    # ================== CONFIGURAÇÕES FÍSICAS ==================

    # Canais PCA9685 dos servos (mapeamento completo do projeto)
    FRONT_BRAKE_CHANNEL = 0  # Canal 0 do PCA9685 - Freio frontal
    REAR_BRAKE_CHANNEL = 1  # Canal 1 do PCA9685 - Freio traseiro
    # STEERING_CHANNEL = 2     # Canal 2 do PCA9685 - Direção (usado pelo steering_manager)

    # Endereço I2C do PCA9685
    PCA9685_I2C_ADDRESS = 0x40  # Endereço padrão do PCA9685

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
        """
        self.front_channel = front_channel or self.FRONT_BRAKE_CHANNEL
        self.rear_channel = rear_channel or self.REAR_BRAKE_CHANNEL
        self.pca9685_address = pca9685_address or self.PCA9685_I2C_ADDRESS

        # Configurações de freio
        self.brake_balance = max(0.0, min(100.0, brake_balance))  # 0-100%
        self.max_brake_force = max(0.0, min(100.0, max_brake_force))  # 0-100%
        self.response_time = max(0.05, response_time)  # Mínimo 50ms

        # Estado atual dos freios
        self.front_brake_angle = self.BRAKE_MIN_ANGLE  # Ângulo atual do servo dianteiro (0° = solto)
        self.rear_brake_angle = self.BRAKE_MIN_ANGLE  # Ângulo atual do servo traseiro (0° = solto)
        self.front_brake_force = 0.0  # Força atual 0-100%
        self.rear_brake_force = 0.0  # Força atual 0-100%
        self.total_brake_input = 0.0  # Input total 0-100%

        # Estado dos servos e PCA9685
        self.is_initialized = False
        self.pca9685 = None
        self.i2c = None
        self.front_servo = None
        self.rear_servo = None


        # Estatísticas
        self.brake_applications = 0
        self.total_brake_time = 0.0
        self.last_brake_time = 0.0
        self.start_time = time.time()


    def initialize(self) -> bool:
        """
        Inicializa o sistema de freios via PCA9685

        Returns:
            bool: True se inicializado com sucesso
        """
        print("Inicializando sistema de freios via PCA9685...")
        print(f"Freio dianteiro: Canal {self.front_channel} do PCA9685")
        print(f"Freio traseiro: Canal {self.rear_channel} do PCA9685")
        print(f"Endereço I2C: 0x{self.pca9685_address:02X}")
        print(
            f"Balanço de freio: {self.brake_balance:.1f}% (0=dianteiro, 100=traseiro)"
        )

        try:
            # Inicializa barramento I2C
            self.i2c = busio.I2C(board.SCL, board.SDA)
            print("✓ Barramento I2C inicializado")

            # Inicializa PCA9685
            self.pca9685 = PCA9685(self.i2c, address=self.pca9685_address)
            self.pca9685.frequency = self.PWM_FREQUENCY
            print(f"✓ PCA9685 inicializado @ {self.PWM_FREQUENCY}Hz")

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
            print(
                f"✓ Servos configurados (canais {self.front_channel} e {self.rear_channel})"
            )

            # Posiciona servos na posição solta (freios liberados)
            self.front_servo.angle = self.BRAKE_MIN_ANGLE
            self.rear_servo.angle = self.BRAKE_MIN_ANGLE
            print(f"✓ Servos posicionados na posição solta ({self.BRAKE_MIN_ANGLE}° = freios liberados)")

            # Aguarda servos se posicionarem
            time.sleep(0.5)


            self.is_initialized = True

            print("✅ Sistema de freios inicializado com sucesso!")
            print(f"  - Frequência PWM: {self.PWM_FREQUENCY}Hz")
            print(f"  - Posição inicial: {self.BRAKE_MIN_ANGLE}° (freios soltos)")
            print("  - Movimento: DIRETO (sem suavização)")
            print(f"  - Canal frontal: {self.front_channel}")
            print(f"  - Canal traseiro: {self.rear_channel}")

            # Teste rápido dos servos
            self._test_servos()

            return True

        except Exception as e:
            print(f"❌ Erro ao inicializar sistema de freios: {e}")
            print("\nVerifique:")
            print("1. Conexões do PCA9685 (VCC, GND, SDA, SCL)")
            print("2. Conexões dos servos no PCA9685 (canais corretos)")
            print("3. Alimentação dos servos (fonte externa 6V recomendada)")
            print("4. sudo raspi-config -> Interface Options -> I2C -> Enable")
            print("5. sudo pip3 install adafruit-circuitpython-pca9685")

            self.is_initialized = False
            return False


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

            # COMANDO DIRETO - igual ao test_brake_direto_simples.py
            self.front_servo.angle = front_angle
            self.rear_servo.angle = rear_angle

            print(f"🛑 Freio aplicado → Frontal: {front_angle:.1f}° | Traseiro: {rear_angle:.1f}°")
        else:
            print(f"⚠️ Servos de freio não inicializados!")

    def release_brakes(self):
        """Libera completamente os freios"""
        self.apply_brake(0.0)
        print("🔧 Freios liberados")

    def emergency_brake(self):
        """Aplica freio de emergência (força máxima)"""
        self.apply_brake(100.0)
        print("🚨 FREIO DE EMERGÊNCIA ATIVADO!")

    def _test_servos(self):
        """Executa teste rápido dos servos - MOVIMENTO DIRETO"""
        print("Executando teste dos servos...")

        try:
            # Teste freio dianteiro
            print("  - Testando freio dianteiro...")
            old_balance = self.brake_balance
            self.set_brake_balance(0.0)
            self.apply_brake(30.0)  # 30% só no dianteiro
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
            "pca9685_available": PCA9685_AVAILABLE,
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
            print("Finalizando sistema de freios...")

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
            print("✓ Sistema de freios finalizado")

        except Exception as e:
            print(f"⚠ Erro ao finalizar sistema de freios: {e}")

    def __del__(self):
        """Destrutor - garante limpeza dos recursos"""
        self.cleanup()


# Exemplo de uso
if __name__ == "__main__":
    print("=== TESTE DO SISTEMA DE FREIOS ===")

    # Cria instância do sistema de freios com PCA9685
    brake_mgr = BrakeManager(
        front_channel=0,  # Canal 0 do PCA9685 para freio frontal
        rear_channel=1,  # Canal 1 do PCA9685 para freio traseiro
        pca9685_address=0x40,  # Endereço I2C padrão do PCA9685
        brake_balance=60.0,  # 60% frontal para F1 (ajustado)
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
        print("\n=== ESTATÍSTICAS FINAIS ===")
        print(f"Aplicações de freio: {stats['brake_applications']}")
        print(f"Tempo de operação: {stats['total_runtime']:.1f}s")
        print(
            "Freios: MOVIMENTO DIRETO (sem calibração)"
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
