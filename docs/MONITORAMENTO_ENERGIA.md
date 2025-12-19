# Monitoramento de Energia

Documento sobre o sistema de monitoramento de corrente e tensão do veículo.

## Status Atual

- **Data**: 2025-12-18
- **Status**: Produção - 10Hz de amostragem

---

## Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MONITORAMENTO DE ENERGIA                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Bateria LiPo 3S (11.1V)                                           │
│         │                                                           │
│         ├──► XL4015 (Buck 5V) ──► Raspberry Pi 4                   │
│         │         │                                                 │
│         │         └──► ACS758-50A ──► ADS1115 CH0                  │
│         │                                                           │
│         ├──► UBEC (5.25V) ──────► Servos MG996R (3x)               │
│         │         │                                                 │
│         │         └──► ACS758-50A ──► ADS1115 CH1                  │
│         │                                                           │
│         └──► Direto 11.1V ──────► Motor RC 775 (via BTS7960)        │
│                   │                                                 │
│                   └──► ACS758-100A ──► ADS1115 CH2                 │
│                                                                     │
│  Raspberry Pi 5V Rail                                               │
│         │                                                           │
│         └──► INA219 (0x41) ──► Tensão + Corrente do RPi            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Por que Monitorar Energia?

### Benefícios

1. **Segurança**: Detectar sobrecarga antes de dano
2. **Autonomia**: Estimar bateria restante
3. **Diagnóstico**: Identificar componentes com consumo anormal
4. **Telemetria**: Dados para análise pós-corrida

### Dados Coletados

| Canal | Sensor | Faixa | Precisão |
|-------|--------|-------|----------|
| CH0 | ACS758-50A | 0-50A | ±40mV/A |
| CH1 | ACS758-50A | 0-50A | ±40mV/A |
| CH2 | ACS758-100A | 0-100A | ±20mV/A |
| INA219 | Integrado | 0-3.2A | ±0.1% |

---

## Sensores de Corrente ACS758

### Por que ACS758?

| Sensor | Corrente Max | Isolação | Decisão |
|--------|--------------|----------|---------|
| Shunt resistivo | Ilimitado | Não | Dissipa calor |
| ACS712 | 30A | 2.1kV | Limite baixo |
| **ACS758** | 50A/100A | 3kV | **Escolhido** |
| INA219 | 3.2A | Não | Só para RPi |

### Princípio de Funcionamento

```
                    ┌──────────────┐
  Corrente ─────────┤  Efeito Hall  ├─────── Saída analógica
                    │   (interno)   │        (0.5V a 4.5V)
                    └──────────────┘
                           │
                        ┌──┴──┐
                        │ VCC │ = 5V
                        └─────┘
```

**Vantagem**: Sem contato galvânico = sem perdas = sem aquecimento.

### Conversão Tensão → Corrente

```python
# ACS758-50A: 40mV/A, offset 2.5V
def voltage_to_current_50A(voltage):
    V_REF = 2.5  # Zero-current = 2.5V
    SENSITIVITY = 0.040  # 40mV/A
    return (voltage - V_REF) / SENSITIVITY

# ACS758-100A: 20mV/A, offset 2.5V
def voltage_to_current_100A(voltage):
    V_REF = 2.5
    SENSITIVITY = 0.020  # 20mV/A
    return (voltage - V_REF) / SENSITIVITY
```

**Exemplo**:
```
Tensão medida: 2.9V
Corrente = (2.9 - 2.5) / 0.040 = 10A
```

---

## ADC ADS1115

### Por que ADS1115?

| ADC | Resolução | Canais | Decisão |
|-----|-----------|--------|---------|
| MCP3008 | 10-bit | 8 | Resolução baixa |
| ADS1015 | 12-bit | 4 | OK |
| **ADS1115** | 16-bit | 4 | **Escolhido** - precisão |
| ADS1015 | 12-bit | 4 | Mais rápido, menos preciso |

### Configuração

```python
# Registros do ADS1115
CONFIG_REG = 0x01

# Bits de configuração
OS = 1          # Start single-shot
MUX = 4         # AIN0 vs GND (canal 0)
PGA = 1         # ±4.096V range
MODE = 1        # Single-shot
DR = 4          # 128 SPS
COMP_QUE = 3    # Disable comparator

config = (OS << 15) | (MUX << 12) | (PGA << 9) | (MODE << 8) | (DR << 5) | COMP_QUE
```

### Tempo de Conversão

```
128 SPS = 7.8ms por amostra
3 canais × 7.8ms = 23.4ms por ciclo
→ Taxa máxima: ~42Hz

Usado: 10Hz (100ms) = confortável
```

---

## Sensor INA219

### Por que INA219 para o Raspberry Pi?

| Método | Vantagem | Desvantagem |
|--------|----------|-------------|
| ACS758 | Fácil | Só corrente, não tensão |
| Shunt manual | Barato | Requer cálculo manual |
| **INA219** | Tensão + corrente + potência | Limite 3.2A |

O RPi 4 consome ~1.5A típico, bem dentro do limite.

### Endereço I2C

```
Padrão: 0x40
Com A0=VCC: 0x41 (usado para evitar conflito com PCA9685)
```

### Leitura de Dados

```python
# Registro de tensão do barramento
BUS_VOLTAGE_REG = 0x02

def read_bus_voltage():
    raw = bus.read_word_data(INA219_ADDR, BUS_VOLTAGE_REG)
    raw = ((raw & 0xFF) << 8) | (raw >> 8)  # Swap bytes
    voltage = (raw >> 3) * 0.004  # 4mV por LSB
    return voltage
```

---

## Filtros de Ruído

### Problema

Sensores analógicos têm ruído:
- ACS758: ~1% de ruído
- ADS1115: Quantização de 16-bit
- Interferência elétrica do motor

### Solução: 3 Estágios de Filtro

```python
def filter_reading(self, raw_value):
    # 1. Filtro mediana (remove spikes)
    self.buffer.append(raw_value)
    median_value = statistics.median(self.buffer[-5:])

    # 2. EMA (suaviza)
    alpha = 0.2
    ema_value = alpha * median_value + (1 - alpha) * self.last_ema
    self.last_ema = ema_value

    # 3. Média móvel (estabiliza)
    self.history.append(ema_value)
    avg_value = sum(self.history[-20:]) / len(self.history[-20:])

    return avg_value
```

### Por que 3 filtros?

| Filtro | Remove | Adiciona |
|--------|--------|----------|
| Mediana | Spikes | Nenhum |
| EMA | Ruído HF | Lag mínimo |
| Média móvel | Flutuações | Lag médio |

**Resultado**: Leitura estável sem lag perceptível.

---

## Calibração Zero-Current

### Problema

ACS758 tem offset de fábrica:
- Nominal: 2.5V em zero
- Real: 2.48V a 2.52V

### Solução

```python
def calibrate_zero_current(self, samples=100):
    """Chamar com circuito sem carga."""
    readings = []
    for _ in range(samples):
        readings.append(self.read_raw_voltage())
        time.sleep(0.01)

    self.zero_offset = statistics.mean(readings)
    # Salvar em arquivo de calibração
```

### Aplicação

```python
def read_current(self):
    voltage = self.read_raw_voltage()
    corrected = voltage - self.zero_offset + 2.5  # Normaliza para 2.5V
    return self.voltage_to_current(corrected)
```

---

## Dados Enviados ao Cliente

### Formato JSON

```json
{
    "power_rpi_voltage": 5.12,
    "power_rpi_current": 1.45,
    "power_rpi_power": 7.42,
    "power_servo_current": 2.3,
    "power_motor_current": 15.8,
    "power_total_current": 19.55,
    "power_timestamp": 1702847123.456
}
```

### Cálculos Derivados

```python
# Potência do RPi
power_rpi = voltage_rpi * current_rpi

# Corrente total do sistema
total_current = current_rpi + current_servo + current_motor

# Estimativa de autonomia (bateria 5000mAh)
remaining_minutes = (5000 / total_current) * 60 / 1000
```

---

## Limites e Alertas

### Thresholds de Segurança

| Componente | Normal | Warning | Critical |
|------------|--------|---------|----------|
| RPi | <2A | 2-2.5A | >2.5A |
| Servos | <5A | 5-8A | >8A |
| Motor | <30A | 30-40A | >40A |

### Implementação

```python
def check_limits(self, data):
    if data['power_motor_current'] > 40:
        warn("Motor: Corrente crítica!", rate_limit=5.0)
        self.emergency_stop()
    elif data['power_motor_current'] > 30:
        warn("Motor: Corrente alta", rate_limit=10.0)
```

---

## Consumo Típico

### Medições Reais

| Estado | RPi | Servos | Motor | Total |
|--------|-----|--------|-------|-------|
| Idle | 0.6A | 0.1A | 0A | 0.7A |
| Vídeo streaming | 1.2A | 0.1A | 0A | 1.3A |
| Vídeo + sensores | 1.5A | 0.1A | 0A | 1.6A |
| Curva lenta | 1.5A | 2A | 5A | 8.5A |
| Aceleração máxima | 1.5A | 0.5A | 25A | 27A |
| Frenagem máxima | 1.5A | 4A | 0A | 5.5A |

### Autonomia Estimada

```
Bateria: 5000mAh @ 11.1V

Uso misto (média 10A):
  Tempo = 5000mAh / 10A = 0.5h = 30 minutos

Uso agressivo (média 20A):
  Tempo = 5000mAh / 20A = 0.25h = 15 minutos
```

---

## Arquivos Relacionados

### Raspberry Pi
- `raspberry/power_monitor_manager.py` - Driver ADS1115 + INA219

### Cliente
- `client/sensor_display.py` - Exibição de dados de energia

### Hardware
- `raspberry/MODULOS.md` - Especificações ACS758, ADS1115, INA219

---

## Histórico de Mudanças

| Data | Mudança |
|------|---------|
| 2025-12-17 | Implementação inicial |
| 2025-12-17 | Adicionado filtro de 3 estágios |
| 2025-12-17 | Calibração zero-current |
| 2025-12-18 | Documentação completa |
