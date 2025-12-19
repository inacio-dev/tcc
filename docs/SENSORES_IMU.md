# Sensor IMU BMI160 - Decisões Técnicas

Documento sobre as escolhas de configuração e implementação do sensor inercial BMI160.

## Status Atual

- **Data**: 2025-12-18
- **Status**: Produção - 100Hz de amostragem

---

## Por que BMI160?

### Alternativas Consideradas

| Sensor | Eixos | Preço | Interface | Decisão |
|--------|-------|-------|-----------|---------|
| MPU6050 | 6 | ~R$15 | I2C | Descontinuado, drift alto |
| MPU9250 | 9 | ~R$40 | I2C/SPI | Magnetômetro desnecessário |
| **BMI160** | 6 | ~R$25 | I2C | **Escolhido** - moderno, baixo ruído |
| ICM-20948 | 9 | ~R$60 | I2C/SPI | Overkill para o projeto |
| LSM6DS3 | 6 | ~R$30 | I2C/SPI | Boa alternativa, menos documentação |

### Vantagens do BMI160

1. **Baixo ruído**: 180 µg/√Hz (acelerômetro), 0.008 °/s/√Hz (giroscópio)
2. **Baixo consumo**: 925 µA em modo normal
3. **Taxa alta**: Até 1600Hz ODR
4. **Temperatura interna**: Sensor de temperatura integrado
5. **Documentação**: Bosch fornece datasheet completo e exemplos

### Por que NÃO usar magnetômetro (9 eixos)?

Sensores 9 eixos (MPU9250, ICM-20948) incluem magnetômetro para heading absoluto.
**Não recomendado para este projeto** pelos seguintes motivos:

| Problema | Causa | Impacto |
|----------|-------|---------|
| Interferência do motor RC 775 | Campo magnético do motor DC | Leituras erráticas |
| Interferência da ponte H | BTS7960 gera EMI forte | Spikes nos dados |
| Interferência dos servos | PWM 50Hz dos MG996R | Ruído periódico |
| Calibração complexa | Hard/soft iron compensation | Difícil em ambiente metálico |
| Proximidade da bateria LiPo | Correntes altas geram campo | Offset variável |

**Conclusão**: Em veículos elétricos RC, magnetômetro é mais problema que solução.
Para heading, usar integração do giroscópio (com drift aceito) ou GPS externo.

---

## Configuração Escolhida

### Ranges de Medição

| Parâmetro | Valor | Resolução | Justificativa |
|-----------|-------|-----------|---------------|
| Aceleração | ±2g | 61 µg/LSB | Carro RC não ultrapassa 2g em curvas |
| Giroscópio | ±250°/s | 7.6 m°/s/LSB | Rotações lentas em veículo terrestre |
| ODR | 100Hz | 10ms | Suficiente para telemetria, economiza CPU |

### Por que ±2g e não ±4g ou ±8g?

```
Resolução ±2g:  61 µg/LSB  = 0.0006 m/s² precisão
Resolução ±4g:  122 µg/LSB = 0.0012 m/s² precisão
Resolução ±8g:  244 µg/LSB = 0.0024 m/s² precisão
```

**Trade-off**: Maior range = menor precisão.

Para um carro RC:
- Aceleração máxima em curva: ~1.5g
- Frenagem máxima: ~1.0g
- Impacto leve: ~2.0g

**Conclusão**: ±2g cobre todos os cenários com máxima precisão.

### Por que ±250°/s e não ±500°/s?

```
Rotação ±250°/s  = ~0.7 rotações/segundo = carro girando
Rotação ±500°/s  = ~1.4 rotações/segundo = capotamento
Rotação ±2000°/s = ~5.5 rotações/segundo = drone/heli
```

**Cenário real**: Carro fazendo curva de 90° em 1 segundo = 90°/s (bem abaixo de 250°/s)

---

## Sequência de Inicialização

### Por que a ordem importa?

O BMI160 requer sequência específica ou falha silenciosamente:

```python
# CORRETO: Ativar ANTES de configurar
bus.write_byte_data(ADDR, CMD_REG, CMD_ACC_NORMAL)  # 1. Ativa accel
time.sleep(0.01)                                      # 2. Aguarda 10ms
bus.write_byte_data(ADDR, ACC_CONF, ODR_100HZ)       # 3. Configura ODR
bus.write_byte_data(ADDR, ACC_RANGE, RANGE_2G)       # 4. Configura range

# INCORRETO: Configurar antes de ativar
bus.write_byte_data(ADDR, ACC_CONF, ODR_100HZ)       # Ignorado!
bus.write_byte_data(ADDR, CMD_REG, CMD_ACC_NORMAL)   # Ativa com config padrão
```

### Tempo de Startup

| Componente | Tempo Mínimo | Usado |
|------------|--------------|-------|
| Acelerômetro | 3.8ms | 10ms |
| Giroscópio | 55ms | 60ms |
| Ambos | ~60ms | 80ms total |

---

## Conversão de Dados

### Aceleração (Raw → m/s²)

```python
# 16-bit signed, range ±2g
raw = (high_byte << 8) | low_byte
if raw > 32767:
    raw -= 65536  # Conversão signed

# Escala: ±2g / 32768 = 61 µg/LSB
accel_g = raw * (2.0 / 32768.0)
accel_ms2 = accel_g * 9.81
```

### Giroscópio (Raw → °/s)

```python
# 16-bit signed, range ±250°/s
raw = (high_byte << 8) | low_byte
if raw > 32767:
    raw -= 65536

# Escala: ±250°/s / 32768 = 7.63 m°/s/LSB
gyro_dps = raw * (250.0 / 32768.0)
```

---

## I2C Compartilhado

### Dispositivos no mesmo barramento

```
I2C Bus 1 (GPIO2/3):
├── BMI160      @ 0x68 (SAO=GND)
├── PCA9685     @ 0x40 (PWM servos)
├── ADS1115     @ 0x48 (ADC energia)
└── INA219      @ 0x41 (monitor RPi)
```

### Por que compartilhar?

**Prós:**
- Menos GPIOs usados
- Fiação simplificada
- I2C suporta múltiplos dispositivos nativamente

**Contras aceitos:**
- Clock máximo limitado pelo dispositivo mais lento
- Conflito se dois acessos simultâneos (resolvido com lock)

### Solução de Conflito

```python
class BMI160Manager:
    def __init__(self):
        self.state_lock = threading.Lock()

    def read_sensor_data(self):
        with self.state_lock:  # Protege acesso I2C
            return self._read_raw_data()
```

---

## Tratamento de Erros I2C

### Erros Comuns

| Erro | Causa | Solução |
|------|-------|---------|
| errno 5 | Timeout I2C | Retry até 3x |
| errno 121 | NACK (sem resposta) | Verificar conexão |
| errno 110 | Timeout conexão | Reduzir clock I2C |

### Estratégia de Retry

```python
def _read_with_retry(self, register, length):
    for attempt in range(3):
        try:
            return self.bus.read_i2c_block_data(self.addr, register, length)
        except IOError as e:
            if e.errno == 5:  # Remote I/O error
                time.sleep(0.005)  # Aguarda 5ms
                continue
            raise
    return None  # Falha após 3 tentativas
```

### Degradação Graceful

```python
def get_sensor_data(self):
    data = self._read_with_retry(DATA_REG, 12)
    if data is None:
        self.error_count += 1
        if self.error_count < 50:
            warn("BMI160: Erro de leitura", rate_limit=5.0)
        return self.last_valid_data  # Retorna último dado válido

    self.error_count = 0
    self.last_valid_data = self._parse_data(data)
    return self.last_valid_data
```

---

## Calibração de Offset

### Por que calibrar?

Sensores MEMS têm bias de fábrica:
- Acelerômetro: ±40 mg típico
- Giroscópio: ±3°/s típico

### Procedimento de Calibração

```python
def calibrate_offsets(self, samples=100):
    """Calibra com sensor em repouso em superfície plana."""
    accel_sum = [0, 0, 0]
    gyro_sum = [0, 0, 0]

    for _ in range(samples):
        data = self.read_raw()
        accel_sum[0] += data['accel_x']
        accel_sum[1] += data['accel_y']
        accel_sum[2] += data['accel_z'] - 1.0  # Gravidade = 1g
        gyro_sum[0] += data['gyro_x']
        gyro_sum[1] += data['gyro_y']
        gyro_sum[2] += data['gyro_z']
        time.sleep(0.01)

    self.accel_offset = [s / samples for s in accel_sum]
    self.gyro_offset = [s / samples for s in gyro_sum]
```

---

## Dados Enviados ao Cliente

### Campos do BMI160 (39 campos)

```json
{
    "bmi160_accel_x": -0.12,
    "bmi160_accel_y": 0.05,
    "bmi160_accel_z": 9.78,
    "bmi160_accel_x_raw": -20,
    "bmi160_accel_y_raw": 8,
    "bmi160_accel_z_raw": 16234,
    "bmi160_gyro_x": 0.5,
    "bmi160_gyro_y": -0.2,
    "bmi160_gyro_z": 1.1,
    "bmi160_g_force_x": -0.012,
    "bmi160_g_force_y": 0.005,
    "bmi160_g_force_z": 0.997,
    "bmi160_g_force_lateral": 0.013,
    "bmi160_g_force_longitudinal": -0.012,
    "bmi160_temperature": 28.5,
    "bmi160_timestamp": 1702847123.456
}
```

### Por que enviar raw E físico?

- **Raw**: Debug, verificar se sensor funciona
- **Físico**: Cálculos no cliente (force feedback, velocidade)
- **Timestamp**: Sincronização temporal, detecção de pacotes perdidos

---

## Integração com Force Feedback

### Dados usados para FF

```python
# No cliente (force_feedback_calc.py)
g_lateral = sensor_data.get('bmi160_g_force_lateral', 0)
gyro_z = sensor_data.get('bmi160_gyro_z', 0)

# Componente lateral: curvas
lateral_ff = min(abs(g_lateral) * 50, 100)

# Componente yaw: rotação
yaw_ff = min(abs(gyro_z) / 60.0 * 50, 50)
```

### Por que 100Hz para FF?

- Resposta tátil perceptível: <50ms
- 100Hz = 10ms entre amostras
- Filtro EMA suaviza ruído sem adicionar latência perceptível

---

## Arquivos Relacionados

### Raspberry Pi
- `raspberry/bmi160_manager.py` - Driver do sensor

### Cliente
- `client/sensor_display.py` - Processamento e validação
- `client/console/logic/force_feedback_calc.py` - Uso para FF
- `client/console/logic/velocity_calc.py` - Integração de velocidade

---

## Histórico de Mudanças

| Data | Mudança |
|------|---------|
| 2025-12-17 | Implementação inicial |
| 2025-12-17 | Adicionado retry para erros I2C |
| 2025-12-17 | Separação em porta UDP 9997 (100Hz dedicado) |
| 2025-12-18 | Documentação de decisões técnicas |
