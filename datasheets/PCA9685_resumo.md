# PCA9685 - Resumo Técnico para TCC

## Visão Geral

| Parâmetro | Valor |
|-----------|-------|
| **Descrição** | Controlador PWM de 16 canais via I2C |
| **Fabricante** | NXP Semiconductors |
| **Resolução PWM** | 12 bits (4096 passos) |
| **Interface** | I2C-bus (Fast-mode Plus, até 1 MHz) |
| **Canais** | 16 saídas LED/PWM independentes |
| **Frequência PWM** | 24 Hz a 1526 Hz (ajustável) |
| **Tensão de Operação** | 2.3V a 5.5V |
| **Endereços I2C** | Até 62 dispositivos (6 pinos de endereço) |

## Aplicações no TCC

- **Controle de Servos**: 3 canais (freio dianteiro, freio traseiro, direção)
- **Frequência para Servos**: 50 Hz (padrão para servos RC)
- **Endereço I2C**: 0x40 (todos pinos de endereço em GND)

---

## Pinagem (TSSOP28)

| Pino | Nome | Função |
|------|------|--------|
| 1 | A0 | Bit de endereço I2C |
| 2 | A1 | Bit de endereço I2C |
| 3 | A2 | Bit de endereço I2C |
| 4 | A3 | Bit de endereço I2C |
| 5 | A4 | Bit de endereço I2C |
| 6 | A5 | Bit de endereço I2C |
| 7 | LED0 | Saída PWM canal 0 |
| 8 | LED1 | Saída PWM canal 1 |
| 9 | LED2 | Saída PWM canal 2 |
| 10 | LED3 | Saída PWM canal 3 |
| 11 | LED4 | Saída PWM canal 4 |
| 12 | LED5 | Saída PWM canal 5 |
| 13 | LED6 | Saída PWM canal 6 |
| 14 | LED7 | Saída PWM canal 7 |
| 15 | VSS (GND) | Terra |
| 16 | LED8 | Saída PWM canal 8 |
| 17 | LED9 | Saída PWM canal 9 |
| 18 | LED10 | Saída PWM canal 10 |
| 19 | LED11 | Saída PWM canal 11 |
| 20 | LED12 | Saída PWM canal 12 |
| 21 | LED13 | Saída PWM canal 13 |
| 22 | LED14 | Saída PWM canal 14 |
| 23 | LED15 | Saída PWM canal 15 |
| 24 | OE | Output Enable (ativo LOW) |
| 25 | EXTCLK | Clock externo (opcional) |
| 26 | SCL | Clock I2C |
| 27 | SDA | Dados I2C |
| 28 | VDD | Alimentação (2.3V-5.5V) |

---

## Endereçamento I2C

### Endereço do Dispositivo

O endereço I2C é formado por:
- **Bits fixos**: `1` (MSB)
- **Bits de hardware**: A5, A4, A3, A2, A1, A0
- **Bit R/W**: 0 (escrita) ou 1 (leitura)

| A5 | A4 | A3 | A2 | A1 | A0 | Endereço (7-bit) |
|----|----|----|----|----|----| ----------------|
| 0 | 0 | 0 | 0 | 0 | 0 | **0x40** |
| 0 | 0 | 0 | 0 | 0 | 1 | 0x41 |
| 0 | 0 | 0 | 0 | 1 | 0 | 0x42 |
| ... | ... | ... | ... | ... | ... | ... |
| 1 | 1 | 1 | 1 | 1 | 1 | 0x7F |

### Endereços Especiais

| Endereço | Nome | Função |
|----------|------|--------|
| **0x00** | General Call | Software Reset (SWRST) |
| **0x70** | LED All Call | Controla todos os dispositivos simultaneamente |
| **0x71** | Sub-address 1 | Grupo de dispositivos 1 |
| **0x72** | Sub-address 2 | Grupo de dispositivos 2 |
| **0x74** | Sub-address 3 | Grupo de dispositivos 3 |

---

## Registradores

### Mapa de Registradores

| Endereço | Nome | Função |
|----------|------|--------|
| 0x00 | MODE1 | Configuração modo 1 |
| 0x01 | MODE2 | Configuração modo 2 |
| 0x02 | SUBADR1 | Sub-endereço I2C 1 |
| 0x03 | SUBADR2 | Sub-endereço I2C 2 |
| 0x04 | SUBADR3 | Sub-endereço I2C 3 |
| 0x05 | ALLCALLADR | Endereço LED All Call |
| 0x06-0x09 | LED0_ON_L/H, LED0_OFF_L/H | Controle PWM canal 0 |
| 0x0A-0x0D | LED1_ON_L/H, LED1_OFF_L/H | Controle PWM canal 1 |
| ... | ... | ... |
| 0x42-0x45 | LED15_ON_L/H, LED15_OFF_L/H | Controle PWM canal 15 |
| 0xFA-0xFD | ALL_LED_ON_L/H, ALL_LED_OFF_L/H | Controle todos os LEDs |
| 0xFE | PRE_SCALE | Prescaler da frequência PWM |
| 0xFF | TestMode | Modo de teste (não usar) |

### Registrador MODE1 (0x00)

| Bit | Nome | Função | Padrão |
|-----|------|--------|--------|
| 7 | RESTART | Reiniciar PWM | 0 |
| 6 | EXTCLK | Usar clock externo | 0 |
| 5 | AI | Auto-incremento de endereço | 0 |
| 4 | SLEEP | Modo sleep (oscilador desligado) | 1 |
| 3 | SUB1 | Responder a sub-endereço 1 | 0 |
| 2 | SUB2 | Responder a sub-endereço 2 | 0 |
| 1 | SUB3 | Responder a sub-endereço 3 | 0 |
| 0 | ALLCALL | Responder a LED All Call | 1 |

**Valor padrão após reset**: 0x11 (SLEEP=1, ALLCALL=1)

### Registrador MODE2 (0x01)

| Bit | Nome | Função | Padrão |
|-----|------|--------|--------|
| 7-5 | - | Reservado | 0 |
| 4 | INVRT | Inverter saída | 0 |
| 3 | OCH | Atualização de saída | 0 |
| 2 | OUTDRV | Tipo de saída (0=open-drain, 1=totem-pole) | 1 |
| 1-0 | OUTNE | Comportamento quando OE=HIGH | 00 |

**Valor padrão após reset**: 0x04 (OUTDRV=1)

---

## Controle PWM

### Registradores de Canal (LEDn)

Cada canal possui 4 registradores de 8 bits:

| Registrador | Função |
|-------------|--------|
| LEDn_ON_L | Byte baixo do contador ON (bits 0-7) |
| LEDn_ON_H | Byte alto do contador ON (bits 8-11) + bit 4 = full ON |
| LEDn_OFF_L | Byte baixo do contador OFF (bits 0-7) |
| LEDn_OFF_H | Byte alto do contador OFF (bits 8-11) + bit 4 = full OFF |

### Cálculo de Duty Cycle

- **Contador**: 0 a 4095 (12 bits)
- **ON_COUNT**: Quando a saída vai para HIGH
- **OFF_COUNT**: Quando a saída vai para LOW

```
Duty Cycle = (OFF_COUNT - ON_COUNT) / 4096 × 100%
```

### Exemplos de Configuração

| Duty Cycle | ON_COUNT | OFF_COUNT |
|------------|----------|-----------|
| 0% | - | Full OFF (bit 4 = 1) |
| 25% | 0 | 1024 |
| 50% | 0 | 2048 |
| 75% | 0 | 3072 |
| 100% | Full ON (bit 4 = 1) | - |

### Controle Full ON/OFF

| LEDn_ON_H[4] | LEDn_OFF_H[4] | Estado |
|--------------|---------------|--------|
| 0 | 0 | PWM normal |
| 1 | 0 | Full ON (100%) |
| 0 | 1 | Full OFF (0%) |
| 1 | 1 | Full OFF (0%) |

---

## Frequência PWM

### Registrador PRE_SCALE (0xFE)

**Fórmula**:
```
prescale = round(osc_clock / (4096 × update_rate)) - 1
```

Onde:
- `osc_clock` = 25 MHz (oscilador interno)
- `update_rate` = frequência PWM desejada em Hz
- `prescale` = valor do registrador PRE_SCALE (3 a 255)

### Valores Comuns

| Frequência | PRE_SCALE | Aplicação |
|------------|-----------|-----------|
| **50 Hz** | **121 (0x79)** | **Servos RC** |
| 60 Hz | 100 (0x64) | Servos |
| 100 Hz | 60 (0x3C) | LEDs |
| 200 Hz | 30 (0x1E) | LEDs (padrão) |
| 1000 Hz | 5 (0x05) | LEDs alta frequência |
| 1526 Hz | 3 (0x03) | Máxima frequência |
| 24 Hz | 255 (0xFF) | Mínima frequência |

### Configuração para Servos (50 Hz)

```python
# Fórmula: prescale = round(25MHz / (4096 × 50Hz)) - 1
prescale = round(25000000 / (4096 * 50)) - 1
prescale = round(122.07) - 1
prescale = 121  # 0x79
```

**Importante**: PRE_SCALE só pode ser alterado quando SLEEP=1 (MODE1 bit 4)

---

## Controle de Servos

### Pulsos de Servo

Servos RC padrão esperam pulsos de 1ms a 2ms em período de 20ms (50Hz):

| Posição | Pulso | Duty Cycle | Valor 12-bit |
|---------|-------|------------|--------------|
| 0° (mín) | 1.0 ms | 5% | ~205 |
| 90° (centro) | 1.5 ms | 7.5% | ~307 |
| 180° (máx) | 2.0 ms | 10% | ~410 |

### Fórmula de Conversão

```python
# Para 50Hz (período = 20ms, 4096 steps)
# 1ms = 4096 / 20 = 204.8 steps
# 2ms = 4096 / 20 × 2 = 409.6 steps

def angulo_para_pwm(angulo):
    """Converte ângulo (0-180) para valor PWM (0-4095)"""
    min_pulse = 205   # ~1ms
    max_pulse = 410   # ~2ms
    return int(min_pulse + (angulo / 180.0) * (max_pulse - min_pulse))

# Exemplo: 90° = 205 + (90/180) × (410-205) = 307
```

### Configuração no TCC

| Canal | Servo | Função |
|-------|-------|--------|
| 0 | MG996R | Freio dianteiro |
| 1 | MG996R | Freio traseiro |
| 2 | MG996R | Direção |

---

## Sequência de Inicialização

### 1. Reset e Configuração Inicial

```python
import smbus2

bus = smbus2.SMBus(1)
PCA9685_ADDR = 0x40

# Registradores
MODE1 = 0x00
MODE2 = 0x01
PRE_SCALE = 0xFE

# 1. Entrar em modo SLEEP
bus.write_byte_data(PCA9685_ADDR, MODE1, 0x10)  # SLEEP=1

# 2. Configurar prescaler para 50Hz (servos)
bus.write_byte_data(PCA9685_ADDR, PRE_SCALE, 121)  # 0x79

# 3. Sair do modo SLEEP
bus.write_byte_data(PCA9685_ADDR, MODE1, 0x00)

# 4. Aguardar oscilador estabilizar
import time
time.sleep(0.005)  # 5ms

# 5. Habilitar auto-incremento (opcional, facilita escrita)
bus.write_byte_data(PCA9685_ADDR, MODE1, 0x20)  # AI=1
```

### 2. Configurar Canal PWM

```python
def set_pwm(channel, on, off):
    """Define PWM para um canal específico"""
    base_reg = 0x06 + 4 * channel
    bus.write_byte_data(PCA9685_ADDR, base_reg, on & 0xFF)      # ON_L
    bus.write_byte_data(PCA9685_ADDR, base_reg + 1, on >> 8)    # ON_H
    bus.write_byte_data(PCA9685_ADDR, base_reg + 2, off & 0xFF) # OFF_L
    bus.write_byte_data(PCA9685_ADDR, base_reg + 3, off >> 8)   # OFF_H

def set_servo_angle(channel, angle):
    """Define ângulo do servo (0-180)"""
    min_pulse = 205
    max_pulse = 410
    pulse = int(min_pulse + (angle / 180.0) * (max_pulse - min_pulse))
    set_pwm(channel, 0, pulse)

# Exemplo: Direção no centro (90°)
set_servo_angle(2, 90)
```

---

## Pino OE (Output Enable)

### Comportamento

| OE | OUTNE[1:0] | LEDn quando OE=HIGH |
|----|------------|---------------------|
| LOW | XX | Saídas normais (PWM) |
| HIGH | 00 | LEDn = LOW |
| HIGH | 01 | LEDn = HIGH (OUTDRV=1) ou Hi-Z (OUTDRV=0) |
| HIGH | 1X | Hi-Z (alta impedância) |

**Uso típico**: Conectar OE ao GND para manter saídas sempre ativas.

---

## Reset por Software (SWRST)

### Sequência

1. Enviar START
2. Endereço General Call: 0x00 (escrita)
3. Dado: 0x06
4. Enviar STOP

```python
# Software Reset
bus.write_byte(0x00, 0x06)
```

**Nota**: Todos os dispositivos PCA9685 no barramento serão resetados.

---

## Características Elétricas

### Limites Absolutos

| Parâmetro | Mín | Máx | Unidade |
|-----------|-----|-----|---------|
| VDD | -0.5 | 6.0 | V |
| Tensão em pinos | -0.5 | VDD + 0.5 | V |
| Corrente por LEDn | - | 25 | mA |
| Corrente total (VSS) | - | 400 | mA |

### Características DC (VDD = 5V, 25°C)

| Parâmetro | Típico | Máx | Unidade |
|-----------|--------|-----|---------|
| IDD (operando) | 6 | 10 | mA |
| Istb (standby) | 2.2 | 15.5 | µA |
| VOL (LOW) | - | 0.4 | V |
| VOH (HIGH) | VDD - 0.5 | - | V |
| IOL (sink) | 25 | - | mA |
| IOH (source) | 10 | - | mA |

### Características I2C

| Modo | Velocidade Máxima |
|------|-------------------|
| Standard-mode | 100 kHz |
| Fast-mode | 400 kHz |
| Fast-mode Plus | 1 MHz |

---

## Configuração Recomendada para TCC

### Hardware

```
Raspberry Pi 4B
    │
    ├── GPIO2 (SDA) ──┬── PCA9685 SDA (pino 27)
    │                 └── (pull-up 4.7kΩ para 3.3V)
    │
    ├── GPIO3 (SCL) ──┬── PCA9685 SCL (pino 26)
    │                 └── (pull-up 4.7kΩ para 3.3V)
    │
    └── GND ──────────── PCA9685 VSS (pino 15)
                         PCA9685 OE (pino 24) → GND
                         PCA9685 A0-A5 (pinos 1-6) → GND

VDD (5V) ────────────── PCA9685 VDD (pino 28)
```

### Software (Python com Adafruit)

```python
from adafruit_servokit import ServoKit

# Inicializar com 16 canais
kit = ServoKit(channels=16)

# Configurar ângulos dos servos
kit.servo[0].angle = 90  # Freio dianteiro
kit.servo[1].angle = 90  # Freio traseiro
kit.servo[2].angle = 90  # Direção (centro)

# Configurar range de pulso (1ms a 2ms)
kit.servo[0].set_pulse_width_range(1000, 2000)
kit.servo[1].set_pulse_width_range(1000, 2000)
kit.servo[2].set_pulse_width_range(1000, 2000)
```

---

## Troubleshooting

### Problema: Servo não responde

1. Verificar conexão I2C: `i2cdetect -y 1` (deve mostrar 0x40)
2. Verificar alimentação: VDD entre 2.3V e 5.5V
3. Verificar OE: deve estar em GND
4. Verificar frequência: deve ser 50Hz para servos

### Problema: Servo treme

1. Verificar alimentação: capacitor de 100µF no VDD
2. Verificar range de pulso: ajustar min/max
3. Verificar interferência: cabos blindados

### Problema: I2C não detecta

1. Verificar pull-ups: 4.7kΩ para 3.3V
2. Verificar endereço: pinos A0-A5
3. Verificar I2C habilitado: `sudo raspi-config`

---

## Referências

- **Datasheet**: PCA9685 - NXP Semiconductors
- **Biblioteca**: adafruit-circuitpython-pca9685
- **Biblioteca Servo**: adafruit-circuitpython-servokit
