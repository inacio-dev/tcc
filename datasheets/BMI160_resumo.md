# BMI160 - Resumo do Datasheet

## Informações Gerais

- **Fabricante**: Bosch Sensortec
- **Tipo**: IMU (Inertial Measurement Unit) de 6 eixos
- **Componentes**: Acelerômetro 3 eixos + Giroscópio 3 eixos
- **Chip ID**: 0xD1
- **Revisão**: 0x00

## Características Principais

### Acelerômetro
- **Ranges**: ±2g, ±4g, ±8g, ±16g (selecionável)
- **Resolução**: 16 bits
- **Sensibilidade**:
  - ±2g: 16384 LSB/g
  - ±4g: 8192 LSB/g
  - ±8g: 4096 LSB/g
  - ±16g: 2048 LSB/g
- **Ruído**: 180 µg/√Hz (modo normal)
- **Bandwidth**: 5Hz a 1600Hz (configurável via ODR)

### Giroscópio
- **Ranges**: ±125°/s, ±250°/s, ±500°/s, ±1000°/s, ±2000°/s
- **Resolução**: 16 bits
- **Sensibilidade**:
  - ±125°/s: 262.4 LSB/°/s
  - ±250°/s: 131.2 LSB/°/s
  - ±500°/s: 65.6 LSB/°/s
  - ±1000°/s: 32.8 LSB/°/s
  - ±2000°/s: 16.4 LSB/°/s
- **Ruído**: 0.007 °/s/√Hz (modo normal)

## Especificações Elétricas

### Alimentação
- **VDD**: 1.71V a 3.6V (tensão digital)
- **VDDIO**: 1.2V a 3.6V (tensão I/O)
- **Corrente (Normal)**: ~925 µA (accel + gyro ativos)
- **Corrente (Low Power)**: ~3.5 µA (apenas accel a 25Hz)
- **Corrente (Suspend)**: ~3 µA

### Temperatura de Operação
- **Range**: -40°C a +85°C

## Interface de Comunicação

### I2C
- **Velocidades**: Standard (100kHz), Fast (400kHz), Fast+ (1MHz)
- **Endereços**:
  - 0x68 (SAO/SDO = GND) ← **Usado no projeto**
  - 0x69 (SAO/SDO = VDD)

### SPI
- **Modo**: SPI 4-wire
- **Velocidade máxima**: 10MHz
- **Modos suportados**: Mode 0 e Mode 3

## Pinout do Módulo

```
╔═══════════════════════════════════════╗
║         MÓDULO BMI160 GY-BMI160       ║
║                                       ║
║   VIN ─── Alimentação (3.3V-5V)       ║
║   3V3 ─── Saída 3.3V (regulador)      ║
║   GND ─── Terra                       ║
║   SCL ─── I2C Clock                   ║
║   SDA ─── I2C Data                    ║
║   CS  ─── Chip Select (SPI)           ║
║   SAO ─── Seleção de endereço I2C     ║
║                                       ║
╚═══════════════════════════════════════╝
```

## Modos de Energia

| Modo | Accel | Gyro | Consumo |
|------|-------|------|---------|
| Normal | ON | ON | ~925 µA |
| Low Power | ON (LP) | OFF | ~3.5 µA |
| Suspend | OFF | OFF | ~3 µA |
| Fast Startup | OFF | Standby | ~50 µA |

### Tempos de Inicialização
- **Power-on Reset**: 55ms (soft-reset) / 10ms (POR)
- **Accel Suspend → Normal**: 3.8ms
- **Gyro Suspend → Normal**: 80ms
- **Gyro Fast Startup → Normal**: 10ms

## Registradores Principais

### Registradores de Status
| Endereço | Nome | Descrição |
|----------|------|-----------|
| 0x00 | CHIP_ID | ID do chip (0xD1) |
| 0x02-0x03 | ERR_REG | Registro de erros |
| 0x1B | STATUS | Status de dados prontos |

### Registradores de Dados
| Endereço | Nome | Descrição |
|----------|------|-----------|
| 0x04-0x09 | DATA_MAG | Dados do magnetômetro (se conectado) |
| 0x0C-0x0D | DATA_GYR_X | Giroscópio eixo X |
| 0x0E-0x0F | DATA_GYR_Y | Giroscópio eixo Y |
| 0x10-0x11 | DATA_GYR_Z | Giroscópio eixo Z |
| 0x12-0x13 | DATA_ACC_X | Acelerômetro eixo X |
| 0x14-0x15 | DATA_ACC_Y | Acelerômetro eixo Y |
| 0x16-0x17 | DATA_ACC_Z | Acelerômetro eixo Z |

### Registradores de Configuração
| Endereço | Nome | Descrição |
|----------|------|-----------|
| 0x40 | ACC_CONF | Config ODR/BW acelerômetro |
| 0x41 | ACC_RANGE | Range do acelerômetro |
| 0x42 | GYR_CONF | Config ODR/BW giroscópio |
| 0x43 | GYR_RANGE | Range do giroscópio |

## FIFO (First-In-First-Out Buffer)

### Características
- **Tamanho**: 1024 bytes
- **Tipos de Frame**:
  - Header frame (1 byte)
  - Data frame (6 bytes por sensor)
  - Control frame (skip/time)

### Configuração
- Suporta armazenamento de: Accel, Gyro, Mag (externo)
- Modos: Headerless ou Header mode
- Watermark configurável (0-1023 bytes)

### Estrutura do Header Frame
```
Bit 7-6: Frame type (00=ctrl, 01=data, 10=ctrl, 11=reserved)
Bit 5-4: Parameter
Bit 3-0: Data specific
```

## Processamento de Dados

### Pipeline de Dados
1. **Sensor** → ADC (16-bit)
2. **ADC** → Filtro Digital (LP/HP configurável)
3. **Filtro** → Registrador de Dados / FIFO

### Output Data Rate (ODR)
- **Acelerômetro**: 12.5Hz a 1600Hz
- **Giroscópio**: 25Hz a 3200Hz

### Filtros Digitais
- **Acelerômetro**:
  - Normal mode: OSR4, OSR2, Normal
  - Undersampling mode: Average
- **Giroscópio**:
  - Normal mode: OSR4, OSR2, Normal

## Interrupções

### Pinos de Interrupção
- **INT1** e **INT2**: Configuráveis independentemente
- **Polaridade**: Active high ou Active low
- **Tipo**: Push-pull ou Open-drain

### Fontes de Interrupção
- Data ready (drdy)
- FIFO full / watermark
- Any-motion / No-motion
- Tap (single/double)
- Orientation
- Flat detection
- Free-fall
- Shock/High-g

## Sistema de Interrupções (Detalhado)

### Any-Motion Detection (Slope)
- Detecta mudanças de movimento usando slope entre amostras consecutivas
- Parâmetros configuráveis:
  - `int_anym_th`: Threshold de slope
  - `int_anym_dur`: Número de amostras consecutivas
- Registrador: 0x5F-0x62 (INT_MOTION)

### Significant Motion
- Implementa detecção de movimento Android 4.3+
- Detecta: caminhada, bicicleta, carro em movimento
- Ignora: vibração de mesa, telefone no bolso parado
- Algoritmo: detecta movimento → espera 3s → verifica novamente

### Step Detector / Counter
- **Step Detector**: Detecta evento de passo único
- **Step Counter**: Acumula passos (Android 4.4+)
- **Modos**:
  - Normal (padrão, recomendado)
  - Sensitive (pessoas leves)
  - Robust (menos falsos positivos)
- Registradores: 0x7A-0x7B (STEP_CONF), 0x78-0x79 (STEP_CNT)

### Tap Sensing
- **Single Tap**: Um toque detectado
- **Double Tap**: Dois toques em período definido
- Parâmetros:
  - `int_tap_th`: Threshold (0.7g a 1.5g típico)
  - `int_tap_dur`: Tempo entre toques (12.5ms a 500ms)
  - `int_tap_quiet`: Período de silêncio (20/30ms)
  - `int_tap_shock`: Duração do choque (50/75ms)

### Orientation Recognition
- Detecta orientação em relação à gravidade
- **Orientações**: Portrait (up/down), Landscape (left/right), Face up/down
- **Modos**:
  - Symmetrical (padrão)
  - High Asymmetrical
  - Low Asymmetrical
- **Blocking**: Pode bloquear detecção em condições específicas

### Flat Detection
- Detecta quando dispositivo está horizontal (em mesa)
- `int_flat_hold_time`: Tempo mínimo para confirmar (ex: 1s)
- Registrador: 0x67-0x68 (INT_FLAT)

### Low-g / Free-Fall Detection
- Detecta queda livre (aceleração muito baixa)
- Usa soma: |acc_x| + |acc_y| + |acc_z| < threshold
- Parâmetros: `int_low_th`, `int_low_hy`, `int_low_dur`

### High-g Detection (Shock)
- Detecta impactos/choques (aceleração muito alta)
- Threshold configurável por eixo
- Parâmetros: `int_high_th`, `int_high_hy`, `int_high_dur`

### No-Motion / Slow-Motion
- **No-Motion**: Interrupção quando não há movimento por tempo X
- **Slow-Motion**: Similar ao any-motion mas com parâmetros diferentes
- Tempo configurável: 1s a 430s

## Self-Test (Auto-Teste)

### Acelerômetro
1. Configurar range para 8g
2. ACC_CONF = 0x2C (1600Hz, bwp=2, us=0)
3. Ativar self-test em 0x6D SELF_TEST
4. Aguardar 50ms
5. Testar direção positiva e negativa
6. **Mínimo esperado**: 2g de diferença em cada eixo

### Giroscópio
- Verifica amplitude de drive, frequência e estabilidade
- Ativar: `gyr_self_test_enable` em 0x6D
- Resultado: `gyr_self_test_ok` em 0x1B STATUS

## Compensação de Offset

### Fast Offset Compensation (FOC)
- Processo one-shot para calibração
- Configurar em 0x69 FOC_CONF
- Disparar via 0x7E CMD (`start_foc`)
- Tempo máximo: 250ms
- Precisão acelerômetro: 3.9mg

### Manual Offset
- Escrever diretamente nos registradores 0x71-0x77 OFFSET
- Habilitar: `gyr_off_en` e `acc_off_en`

### Inline Calibration
- Salvar valores de compensação na NVM
- Carregados automaticamente no reset

## Memória Não-Volátil (NVM)

- **Máximo de ciclos de escrita**: 14
- **Registradores com backup NVM**: 0x70 NV_CONF, 0x71-0x77 OFFSET
- **Processo de escrita**:
  1. Escrever nos registradores de imagem
  2. Setar `nvm_prog_en` = 1 em 0x6A CONF
  3. Enviar `prog_nvm` (0xA0) via 0x7E CMD

## Mapa de Registradores

### Registradores de Identificação e Status
| Endereço | Nome | Default | Descrição |
|----------|------|---------|-----------|
| 0x00 | CHIP_ID | 0xD1 | ID do chip |
| 0x02 | ERR_REG | 0x00 | Flags de erro |
| 0x03 | PMU_STATUS | 0x00 | Status do modo de energia |
| 0x1B | STATUS | 0x01 | Status geral |

### Registradores de Dados
| Endereço | Nome | Descrição |
|----------|------|-----------|
| 0x04-0x0B | DATA_MAG | Magnetômetro + RHALL |
| 0x0C-0x11 | DATA_GYR | Giroscópio X, Y, Z |
| 0x12-0x17 | DATA_ACC | Acelerômetro X, Y, Z |
| 0x18-0x1A | SENSORTIME | Contador 24-bit (39µs) |
| 0x20-0x21 | TEMPERATURE | Temperatura (½⁹ K/LSB) |

### Registradores de Interrupção
| Endereço | Nome | Descrição |
|----------|------|-----------|
| 0x1C-0x1F | INT_STATUS | Status das interrupções |
| 0x50-0x52 | INT_EN | Habilitação de interrupções |
| 0x53 | INT_OUT_CTRL | Controle dos pinos INT |
| 0x54 | INT_LATCH | Configuração de latch |
| 0x55-0x57 | INT_MAP | Mapeamento INT1/INT2 |

### Registradores de Configuração de Sensores
| Endereço | Nome | Default | Descrição |
|----------|------|---------|-----------|
| 0x40 | ACC_CONF | 0x28 | ODR/BW acelerômetro |
| 0x41 | ACC_RANGE | 0x03 | Range acelerômetro |
| 0x42 | GYR_CONF | 0x28 | ODR/BW giroscópio |
| 0x43 | GYR_RANGE | 0x00 | Range giroscópio |

### Registradores de FIFO
| Endereço | Nome | Descrição |
|----------|------|-----------|
| 0x22-0x23 | FIFO_LENGTH | Nível atual do FIFO |
| 0x24 | FIFO_DATA | Dados do FIFO |
| 0x45 | FIFO_DOWNS | Downsampling |
| 0x46-0x47 | FIFO_CONFIG | Configuração |

### Registradores de Offset e NVM
| Endereço | Nome | Descrição |
|----------|------|-----------|
| 0x69 | FOC_CONF | Configuração FOC |
| 0x6D | SELF_TEST | Auto-teste |
| 0x70 | NV_CONF | Configuração NVM |
| 0x71-0x77 | OFFSET | Valores de offset |

### Registradores de Comando
| Endereço | Nome | Descrição |
|----------|------|-----------|
| 0x7E | CMD | Comandos |
| 0x7A-0x7B | STEP_CONF | Config step detector |
| 0x78-0x79 | STEP_CNT | Contador de passos |

## Sensor Time

- **Resolução**: 39 µs por incremento
- **Tamanho**: 24 bits (3 bytes)
- **Período único**: ~10 min 54 segundos (0x000000 → 0xFFFFFF)
- **Registrador**: 0x18-0x1A SENSORTIME

## Sensor de Temperatura

- **Resolução**: ½⁹ K/LSB (~0.002°C)
- **Range**: -41°C a +87°C
- **Valor 0x0000**: 23°C
- **Atualização**: 10ms (gyro normal) ou 1.28s (gyro suspend)

## Timings de Comunicação I2C

### Especificações de Timing (Tabela 28)
| Parâmetro | Símbolo | Condição | Min | Max | Unidade |
|-----------|---------|----------|-----|-----|---------|
| Clock Frequency | fSCL | - | - | 1000 | kHz |
| SCL Low Period | tLOW | - | 1.3 | - | µs |
| SCL High Period | tHIGH | - | 0.6 | - | µs |
| SDA Setup Time | tSUDAT | - | 0.1 | - | µs |
| SDA Hold Time | tHDDAT | - | 0.0 | - | µs |
| Setup Time Start | tSUSTA | - | 0.6 | - | µs |
| Hold Time Start | tHDSTA | - | 0.6 | - | µs |
| Setup Time Stop | tSUSTO | - | 0.6 | - | µs |
| Time Before New TX | tBUF | Low Power | 400 | - | µs |
| | | Normal | 1.3 | - | µs |

### Restrições de Acesso
- **Normal mode**: 2 µs de espera após escrita
- **Suspend mode**: 450 µs de espera após escrita
- **Watchdog Timer (WDT)**: Previne travamento do barramento I2C
  - `i2c_wdt_en`: Ativa/desativa WDT
  - `i2c_wdt_sel`: Período 1ms ou 50ms

## Interface Secundária

### Tipos de Uso
1. **Magnetometer Interface (I2C)**: Conexão com sensor MAG (ex: BMM150)
2. **OIS Interface (SPI)**: Conexão com controlador OIS (estabilização óptica)

### Mapeamento de Pinos Secundários (Tabela 29)
| Pin# | Nome | I/O Type | SPI4W | SPI3W | I2C |
|------|------|----------|-------|-------|-----|
| 2 | ASDx | Digital I/O | MOSI | SISO | SDA |
| 3 | ASCx | Digital I/O | SCK | SCK | SCL |
| 10 | OCSB | Digital in | CSB | CSB | DNC |
| 11 | OSDO | Digital out | MISO | DNC | DNC |

### Modos do Magnetometer Interface
1. **Setup Mode (Manual)**:
   - Acesso a todos registradores do sensor externo
   - Habilitado por: `MAG_IF[1]<7> = 1`
   - Usado para configuração inicial após POR

2. **Data Mode**:
   - Leitura autônoma dos dados do magnetômetro
   - Habilitado por: `MAG_IF[1]<7> = 0`
   - ODR configurável via `mag_odr` em MAG_CONF

### Interface OIS
- **ODR**: 6.4 kHz (dados pré-filtrados do giroscópio)
- **Velocidade**: Até 10 MHz (SPI fast mode)
- **Modos**: SPI 3-wire e 4-wire

## Pinout do Chip BMI160

### Tabela Completa de Pinos (14 pinos)
| Pin# | Nome | I/O Type | Interface | Descrição |
|------|------|----------|-----------|-----------|
| 1 | SDO | Digital I/O | Primary | SPI data out / I2C address select |
| 2 | ASDx | Digital I/O | Secondary | Magnetometer interface |
| 3 | ASCx | Digital I/O | Secondary | Magnetometer interface |
| 4 | INT1 | Digital I/O | Primary | Interrupt pin 1 |
| 5 | VDDIO | Supply | - | I/O supply (1.2-3.6V) |
| 6 | GNDIO | Ground | - | Ground for I/O |
| 7 | GND | Ground | - | Ground digital & analog |
| 8 | VDD | Supply | - | Power supply (1.71-3.6V) |
| 9 | INT2 | Digital I/O | Primary | Interrupt pin 2 |
| 10 | OCSB | Digital in | Secondary | OIS interface |
| 11 | OSDO | Digital out | Secondary | OIS interface |
| 12 | CSB | Digital in | Primary | Chip select SPI / Protocol select |
| 13 | SCx | Digital in | Primary | SCK (SPI) / SCL (I2C) |
| 14 | SDx | Digital I/O | Primary | SDA/MOSI/SISO |

**Notas**:
- INT1/INT2 não usados: deixar desconectados (DNC)
- ASDx, ASCx, OCSB, OSDO não usados: alta impedância

## Diagramas de Conexão

### I2C como Interface Primária
```
BMI160 Conexões:
├── VDD ────── 1.71-3.6V + 100nF
├── VDDIO ──── 1.2-3.6V + 100nF
├── GND, GNDIO ── GND
├── SCx ────── SCL (com pull-up R)
├── SDx ────── SDA (com pull-up R)
├── SDO ────── SA0 (GND=0x68, VDD=0x69)
├── CSB ────── VDD (seleciona I2C)
├── INT1 ───── Opcional (interrupção)
└── INT2 ───── Opcional (interrupção)
```

### SPI 4-Wire como Interface Primária
```
BMI160 Conexões:
├── VDD ────── 1.71-3.6V + 100nF
├── VDDIO ──── 1.2-3.6V + 100nF
├── GND, GNDIO ── GND
├── SCx ────── SCK
├── SDx ────── MOSI
├── SDO ────── MISO
├── CSB ────── CS (chip select)
├── INT1 ───── Opcional
└── INT2 ───── Opcional
```

## Especificações do Encapsulamento

### Dimensões
- **Tipo**: LGA (Land Grid Array)
- **Tamanho**: 2.5mm × 3.0mm × 0.83mm
- **Tolerância**: ±0.05mm

### Orientação dos Eixos
- **Eixo X**: Horizontal (comprimento)
- **Eixo Y**: Horizontal (largura)
- **Eixo Z**: Vertical (perpendicular ao chip)
- **Em repouso com Z para cima**: X=0g, Y=0g, Z=+1g

### Marcação do Chip
**Produção em Massa**:
- Linha 1: CCC (Counter ID - 3 dígitos)
- Linha 2: VL (V=T denota BMI160)
- Marcador Pin 1: ponto

**Amostras de Engenharia**:
- Linha 1: VLE (E = engineering)
- Linha 2: CC (revision ID)

## Diretrizes de Soldagem

### Perfil de Reflow (Lead-Free)
| Parâmetro | Valor |
|-----------|-------|
| Ramp-Up Rate | 3°C/s máx |
| Preheat Temp | 150-200°C |
| Preheat Time | 60-180s |
| Time Above 217°C | 60-150s |
| Peak Temperature | 260°C |
| Time at Peak (±5°C) | 20-40s |
| Ramp-Down Rate | 6°C/s máx |
| 25°C to Peak Time | 8 min máx |

### Nível de Sensibilidade à Umidade
- **MSL**: JEDEC Level 1 (sem restrições de tempo de exposição)
- **Padrões**: IPC/JEDEC J-STD-020E, J-STD-033D

## Instruções de Manuseio

### Proteção contra Choques
- Tolerância: Vários milhares de g's
- Evitar: Golpes de martelo, quedas em superfícies duras
- Recomendação: Processo de instalação qualificado

### Proteção ESD
- Proteção integrada: 2kV HBM
- Recomendação: Precauções antiestáticas padrão CMOS
- Entradas não usadas: Amarrar a nível lógico definido

## Especificações de Embalagem

### Tape and Reel
- **Quantidade**: 5.000 peças por reel
- **Caixa**: 35cm × 35cm × 6cm
- **Pocket dimensions**: A0=3.30mm, B0=2.80mm, K0=1.10mm

### Conformidade Ambiental
- **RoHS**: Diretiva 2011/65/EU (incluindo 2015/863/EU)
- **Halogênio**: Livre de halogênio

## Resumo de Configuração Recomendada (Projeto TCC)

### Configuração Usada no Projeto
```
Interface: I2C
Endereço: 0x68 (SDO = GND)
Velocidade: Fast Mode (400kHz)

Acelerômetro:
├── Range: ±4g (8192 LSB/g)
├── ODR: 100Hz
└── Modo: Normal

Giroscópio:
├── Range: ±500°/s (65.6 LSB/°/s)
├── ODR: 100Hz
└── Modo: Normal

Conversão de Dados:
├── Accel: valor_g = raw_data / 8192.0
└── Gyro: valor_dps = raw_data / 65.6
```

### Sequência de Inicialização
```python
# 1. Soft Reset
write(0x7E, 0xB6)
delay(55ms)

# 2. Verificar Chip ID
chip_id = read(0x00)  # Deve ser 0xD1

# 3. Configurar Acelerômetro
write(0x40, 0x28)  # ODR=100Hz, bwp=normal
write(0x41, 0x05)  # Range ±4g

# 4. Configurar Giroscópio
write(0x42, 0x28)  # ODR=100Hz, bwp=normal
write(0x43, 0x01)  # Range ±500°/s

# 5. Ativar Sensores (Normal Mode)
write(0x7E, 0x11)  # Accel normal mode
delay(4ms)
write(0x7E, 0x15)  # Gyro normal mode
delay(80ms)

# 6. Leitura de Dados (0x0C-0x17)
gyro_x = read16(0x0C)
gyro_y = read16(0x0E)
gyro_z = read16(0x10)
accel_x = read16(0x12)
accel_y = read16(0x14)
accel_z = read16(0x16)
```

---

*Resumo baseado no datasheet BMI160 BST-BMI160-DS000-09 Revision 1.0 (November 2020)*
*Bosch Sensortec GmbH - www.bosch-sensortec.com*
