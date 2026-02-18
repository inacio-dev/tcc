# Monitoramento de Energia

Documento sobre o sistema de monitoramento de corrente e tensão do veículo.

## Status Atual

- **Data**: 2026-02-14
- **Status**: Produção - 10Hz de amostragem
- **Arquitetura**: Arduino Pro Micro (USB Serial) + INA219 (I2C)

---

## Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MONITORAMENTO DE ENERGIA                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Bateria LiPo 3S (11.1V)                                               │
│         │                                                               │
│         ├── ACS758-100A ──► Ponte H BTS7960 ──► Motor DC 775           │
│         │   (high-side)        Pro Micro A2                             │
│         │                                                               │
│         ├── ACS758-50A  ──► UBEC (5.25V) ──► Servos MG996R (3x)       │
│         │   (high-side)        Pro Micro A1                             │
│         │                                                               │
│         ├── Divisor R ──────► Pro Micro A0 (tensão bateria)            │
│         │   (20k/10k)                                                   │
│         │                                                               │
│         └── XL4015 (Buck 5V) ──► INA219 ──► USB-C ──► Raspberry Pi 4  │
│                                  (I2C 0x41)                             │
│                                                                         │
│  Arduino Pro Micro (ATmega32U4)                                         │
│         │                                                               │
│         └── USB Serial (115200 baud) ──► Raspberry Pi 4                │
│              Protocolo: PWR:<v_bat>,<i_servos>,<i_motor>               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Migração: ADS1115 para Arduino Pro Micro

### Arquitetura Anterior (ADS1115)

Na versão anterior, o sistema utilizava um ADC externo ADS1115 (16-bit, I2C) conectado
diretamente ao Raspberry Pi para ler as saídas analógicas dos sensores ACS758:

```
ACS758 (analógico) ──► ADS1115 (I2C, 0x48) ──► Raspberry Pi 4
                         │
                    Barramento I2C compartilhado com:
                    BMI160 (0x68), PCA9685 (0x40), INA219 (0x41)
```

### Problemas Identificados

#### 1. Incompatibilidade de Referência de Tensão

O problema mais grave era a incompatibilidade entre a referência de tensão do ADS1115 e
a saída dos sensores ACS758.

Os ACS758 são alimentados a 5V e possuem saída ratiométrica: o ponto zero (sem corrente)
é exatamente VCC/2 = 2.5V. Porém, o ADS1115 opera com referência interna própria
(PGA configurável: ±6.144V, ±4.096V, etc.), que não acompanha variações na alimentação
dos sensores.

Na prática isso significa que se o VCC dos ACS758 sofrer uma queda de 5.00V para 4.90V
(algo comum com carga variável na bateria), o offset zero muda de 2.500V para 2.450V,
mas o ADS1115 não percebe essa mudança, introduzindo um erro de 50mV. Em um sensor de
20mV/A (ACS758-100A), 50mV representam 2.5A de erro fantasma.

```
Problema:
  ACS758 alimentado a 5V → offset zero = 2.500V
  ACS758 alimentado a 4.9V → offset zero = 2.450V
  ADS1115 não acompanha a variação → erro de 50mV = 2.5A falso (no 100A)

Solução (Pro Micro):
  ACS758 e Pro Micro alimentados pelo MESMO 5V (AVCC)
  Se VCC cai para 4.9V:
    - Offset zero do ACS758 = 4.9V / 2 = 2.450V
    - Referência do ADC (AVCC) = 4.9V
    - ADC lê: 2.450V / 4.9V × 1024 = 512 (exatamente o zero!)
  → Erro cancela automaticamente (medição ratiométrica)
```

#### 2. Congestionamento do Barramento I2C

O ADS1115 compartilhava o barramento I2C (GPIO2/3) do Raspberry Pi com outros 3 dispositivos:

| Dispositivo | Endereço | Taxa de Acesso |
|-------------|----------|----------------|
| BMI160 IMU | 0x68 | 100Hz |
| PCA9685 PWM | 0x40 | Sob demanda |
| INA219 | 0x41 | 10Hz |
| ADS1115 | 0x48 | 10Hz (3 canais) |

Cada leitura do ADS1115 envolve: escrever configuração (selecionar canal + iniciar
conversão) + aguardar conversão (7.8ms @ 128 SPS) + ler resultado. Com 3 canais, isso
ocupava ~23.4ms do barramento I2C a cada ciclo de 100ms. Em combinação com o BMI160
a 100Hz, o barramento ficava congestionado, gerando timeouts esporádicos e leituras
corrompidas.

#### 3. Latência de Conversão

O ADS1115 é um ADC sigma-delta, otimizado para precisão e não para velocidade. Cada
conversão leva 7.8ms (128 SPS). Para 3 canais multiplexados, o ciclo completo demora
~25ms, limitando a taxa efetiva e adicionando latência ao sistema de monitoramento.

#### 4. Sem Canal para Tensão da Bateria

Os 4 canais do ADS1115 estavam alocados (3 para ACS758 + 1 reserva). Com a remoção do
ACS758 dedicado ao RPi (substituído pelo INA219), sobrou um canal. Porém, para medir a
tensão da bateria diretamente, seria necessário um divisor de tensão compatível com o
range do ADS1115 (±4.096V). O divisor antigo (2x 10kOhm, ratio 1:2) gerava 6.3V com
bateria cheia, que excedia a faixa segura do ADS1115 no modo single-ended.

### Por que Arduino Pro Micro?

| Critério | ADS1115 | Pro Micro | Vantagem |
|----------|---------|-----------|----------|
| Referência ADC | Interna (independente) | AVCC (ratiométrica) | Pro Micro cancela drift |
| Barramento | I2C compartilhado | USB dedicado | Pro Micro libera I2C |
| Latência | 25ms (3 canais) | <5ms (3 canais) | Pro Micro 5x mais rápido |
| Calibração | Software (RPi) | EEPROM persistente | Pro Micro sobrevive reboot |
| Oversampling | 1 amostra/canal | 50 amostras/canal | Pro Micro reduz ruido |
| Custo | ~R$15 | ~R$20 | Similar |
| Complexidade | 1 chip I2C | MCU dedicado | Pro Micro mais flexível |

A vantagem decisiva é a **medição ratiométrica**: como o Pro Micro e os ACS758 compartilham
a mesma alimentação 5V, qualquer variação de tensão afeta ambos igualmente, cancelando o
erro. Isso é impossível com o ADS1115, que possui referência interna própria.

### Resumo da Migração

| Item | Antes | Depois |
|------|-------|--------|
| ADC | ADS1115 (I2C, 16-bit) | Pro Micro ATmega32U4 (USB, 10-bit) |
| Comunicação | I2C compartilhado | USB Serial dedicado (115200 baud) |
| Referência | Interna ADS1115 (PGA) | AVCC ratiométrica (5V) |
| Tensão bateria | Não medida | Divisor R1=20k/R2=10k → A0 |
| Corrente RPi | ACS758 no ADS1115 | INA219 I2C (muito mais preciso) |
| Corrente servos | ACS758 → ADS1115 CH1 | ACS758 → Pro Micro A1 |
| Corrente motor | ACS758 → ADS1115 CH2 | ACS758 → Pro Micro A2 |
| Calibração | Arquivo no RPi | EEPROM do Pro Micro (0xCAFE + checksum) |
| Oversampling | 1 amostra | 50 amostras por leitura |

---

## Sensores de Corrente ACS758

### Por que ACS758?

| Sensor | Corrente Max | Isolacao | Decisao |
|--------|--------------|----------|---------|
| Shunt resistivo | Ilimitado | Nao | Dissipa calor |
| ACS712 | 30A | 2.1kV | Limite baixo |
| **ACS758** | 50A/100A | 3kV | **Escolhido** |
| INA219 | 3.2A | Nao | So para RPi |

### Principio de Funcionamento

O ACS758 utiliza o efeito Hall para medir corrente. Internamente, possui dois circuitos
fisicamente separados e galvanicamente isolados:

1. **Caminho de corrente (IP+ e IP-)**: Barra de cobre interna com resistencia de apenas
   100 uOhm. A corrente da carga flui por esta barra sem contato com o circuito eletronico.

2. **Circuito de medicao (VCC, GND, OUT)**: Sensor Hall que detecta o campo magnetico
   gerado pela corrente na barra de cobre e produz uma tensao proporcional no pino OUT.

Essa isolacao galvanica significa que a corrente flui pelo IP+ e IP- **independentemente**
de VCC/GND estarem conectados. Com VCC desconectado, a corrente ainda passa, mas o sensor
nao produz sinal no OUT.

### Configuracao High-Side

Os ACS758 sao instalados no fio **positivo** (high-side), em serie entre a bateria e
cada carga. O GND comum do sistema nao e interrompido.

```
                         ACS758 100A                  ACS758 50A
Bateria (+) ─────┬────[IP+ ──► IP-]──── Ponte H ──── Motor DC 775
                 │
                 ├────[IP+ ──► IP-]──── UBEC ──────── Servos PCA9685
                 │
                 ├──── R1(20k) ──┬───── Pro Micro A0 (tensao)
                 │               R2(10k)
                 │               │
Bateria (-) ─────┴───────────────┴───── GND comum
```

Por que high-side em vez de low-side:

| Criterio | High-Side | Low-Side |
|----------|-----------|----------|
| GND | Intacto, compartilhado | Interrompido por sensor |
| Ground loops | Sem risco | Pode causar offset no GND |
| Protecao | Detecta curto para GND | Nao detecta curto para GND |
| Complexidade | Igual (ACS758 e bidirecional) | Igual |

### Conversao Tensao para Corrente

O ACS758 tem saida ratiometrica: sem corrente, OUT = VCC/2. A corrente e calculada pela
diferenca entre a leitura e o offset zero:

```
ACS758-50A:  Sensibilidade = 40 mV/A, Offset = VCC/2
ACS758-100A: Sensibilidade = 20 mV/A, Offset = VCC/2

Corrente = (V_adc - V_offset) / Sensibilidade
```

No Pro Micro (ADC ratiometrico):
```c
// ADC le: valor = (V_out / VCC) * 1024
// Offset zero = VCC/2, que no ADC = 1024/2 = 512
int offset = 512;  // Teorico (calibrado na EEPROM)
float voltage_diff = (adc_avg - offset) * (VCC / 1024.0);
float current = voltage_diff / sensitivity;
```

---

## Divisor de Tensao da Bateria

### Circuito

```
Bateria (+) ─── R1 (20kOhm) ───┬─── Filtro RC ─── Pro Micro A0
                                │
                           R2 (10kOhm)
                                │
                               GND
```

### Calculos

```
Razao: R2 / (R1 + R2) = 10k / 30k = 1/3
V_adc = V_bateria x (1/3)
V_bateria = V_adc x 3

Bat. cheia  (12.6V) → ADC = 4.2V  (seguro, < 5V)
Bat. nominal (11.1V) → ADC = 3.7V
Bat. minima  (9.0V)  → ADC = 3.0V

Corrente no divisor: 12.6V / 30kOhm = 0.42mA (desprezivel)
```

### Percentual da Bateria (3S LiPo)

```python
# 3S LiPo: 9.0V (vazia) a 12.6V (cheia)
pct = (voltage - 9.0) / (12.6 - 9.0) * 100.0
pct = max(0.0, min(100.0, pct))
```

| Tensao | Percentual | Estado |
|--------|-----------|--------|
| 12.6V | 100% | Cheia |
| 11.1V | 58% | Nominal |
| 10.5V | 42% | Uso normal |
| 9.9V | 25% | Baixa |
| 9.0V | 0% | Vazia (cutoff) |

---

## Sensor INA219 (Raspberry Pi)

### Por que INA219 para o RPi?

O Raspberry Pi consome ~1.5A tipico, muito abaixo da faixa util dos ACS758 (minimo
pratico ~0.5A para o 50A). O INA219 oferece resolucao de 0.8mA com shunt de 0.1 Ohm,
ideal para medir correntes baixas com alta precisao.

### Circuito de Medicao

```
XL4015 OUT+ ─── VIN+ ───[Shunt 0.1 Ohm]─── VIN- ─── USB-C Breakout ─── RPi 4
                            (interno)
```

### Endereco I2C

```
Padrao: 0x40 (conflita com PCA9685)
Com A0=VCC: 0x41 (usado no projeto)
```

O jumper A0 do INA219 e soldado para VCC, deslocando o endereco para 0x41 e evitando
conflito com o PCA9685 (0x40) no mesmo barramento I2C.

---

## Filtros de Ruido

### Filtro de Hardware (RC)

Cada sensor ACS758 possui um filtro RC na saida antes de conectar ao Pro Micro:

```
ACS758 OUT ─── 1kOhm ───┬─── Pro Micro (Ax)
                         │
                      100nF
                         │
                        GND

Frequencia de corte: fc = 1/(2*pi*1k*100n) = 1.6 kHz
```

O filtro RC remove ruido de alta frequencia (EMI do motor, chaveamento do BTS7960)
antes do sinal chegar ao ADC.

### Filtro de Software (Pro Micro)

O Pro Micro faz oversampling de 50 amostras por leitura, reduzindo o ruido por
um fator de raiz(50) = 7x:

```c
long sum = 0;
for (int i = 0; i < 50; i++) {
    sum += analogRead(pin);
}
int avg = sum / 50;
```

### Filtro de Software (Raspberry Pi)

O power_monitor_manager.py aplica 2 estagios adicionais de filtragem digital:

```
Dado bruto (Pro Micro) → Mediana (5 amostras) → EMA (alpha=0.2) → Buffer medio (20)
```

| Filtro | Funcao | Efeito |
|--------|--------|--------|
| Mediana | Remove spikes isolados | Sem lag, robusto |
| EMA | Suaviza ruido HF | Lag minimo (alpha=0.2) |
| Media movel | Estabiliza display | Lag medio, leitura limpa |

---

## Protocolo Serial (Pro Micro para RPi)

### Formato de Dados

```
Pro Micro → RPi:
  PWR:<v_bat>,<i_servos>,<i_motor>\n     (10Hz)
  STATUS:READY\n                          (apos boot)
  STATUS:CALIBRATING\n                    (durante calibracao)
  STATUS:NO_CAL\n                         (sem EEPROM valida)
  CAL_DONE:<offset_servos>,<offset_motor>\n  (apos calibracao)

RPi → Pro Micro:
  CAL\n                                   (solicitar recalibracao)
```

### Deteccao USB

O Pro Micro (ATmega32U4) aparece como `/dev/ttyACM*` no Linux. A deteccao automatica
segue a ordem de prioridade:

1. `/dev/serial/by-id/` (link simbolico estavel baseado em VID/PID)
2. USB VID/PID (0x2341 Arduino, 0x1B4F SparkFun)
3. Fallback `/dev/ttyACM0`

### Configuracao Serial

| Parametro | Valor |
|-----------|-------|
| Baudrate | 115200 |
| Data bits | 8 |
| Parity | None |
| Stop bits | 1 |
| Timeout | 0.1s |
| Taxa de envio | 10Hz |

---

## Calibracao dos ACS758

### Problema

O offset de fabrica dos ACS758 nao e exatamente VCC/2. Pode variar de 2.48V a 2.52V,
o que representa 1A de erro no sensor 50A (40mV/A) ou 2.5A no sensor 100A (20mV/A).

### Solucao: Calibracao com Persistencia em EEPROM

O Pro Micro mede o offset real de cada ACS758 (com cargas desligadas) e salva na EEPROM:

```
EEPROM Layout (7 bytes):
  Addr 0-1: Magic number (0xCAFE)
  Addr 2-3: Offset A1 - Servos  (int16_t, unidades ADC)
  Addr 4-5: Offset A2 - Motor   (int16_t, unidades ADC)
  Addr 6:   Checksum (XOR dos bytes 2-5)
```

### Processo de Calibracao

1. Operador desliga motor e servos (corrente zero)
2. RPi envia comando `CAL\n` via serial
3. Pro Micro le 200 amostras de cada canal ACS758 (com delay de 5ms entre amostras)
4. Calcula media das amostras como novo offset
5. Valida range (400-624, proximo de 512 teorico)
6. Salva na EEPROM com magic number e checksum
7. Responde `CAL_DONE:<offset_servos>,<offset_motor>\n`

O canal A0 (divisor de tensao da bateria) **nao** precisa de calibracao, pois nao
possui offset variavel.

---

## Calculos de Potencia

### Formulas

```python
# Motor DC 775 (alimentado diretamente pela bateria via BTS7960)
power_motor = abs(current_motor) * voltage_battery

# Servos (alimentados pelo UBEC a 5.25V fixo)
power_servos = abs(current_servos) * 5.25

# Raspberry Pi (medido diretamente pelo INA219)
power_rpi = voltage_rpi * current_rpi  # calculado pelo proprio INA219

# Total do sistema
power_total = power_motor + power_servos + power_rpi
```

Nota: a potencia do motor usa a tensao real da bateria (medida pelo divisor), nao a
tensao nominal de 11.1V. Isso garante precisao mesmo com bateria descarregando.

---

## Dados Enviados ao Cliente

### Campos de Telemetria

| Campo | Fonte | Unidade |
|-------|-------|---------|
| voltage_battery | Pro Micro A0 | V |
| battery_percentage | Calculado | % |
| current_motor | Pro Micro A2 (ACS758-100A) | A |
| current_servos | Pro Micro A1 (ACS758-50A) | A |
| voltage_rpi | INA219 | V |
| current_rpi | INA219 | A |
| power_motor | Calculado | W |
| power_servos | Calculado | W |
| power_rpi | INA219 | W |
| power_total | Calculado | W |

---

## Limites e Alertas

### Thresholds de Seguranca

| Componente | Normal | Warning | Critical |
|------------|--------|---------|----------|
| RPi | <2A | 2-2.5A | >2.5A |
| Servos | <5A | 5-8A | >8A |
| Motor | <30A | 30-40A | >40A |
| Bateria | >10.5V | 9.9-10.5V | <9.9V |

### Cores na Interface (Bateria)

| Percentual | Cor | Estado |
|-----------|-----|--------|
| >50% | Verde (#00ff88) | OK |
| 30-50% | Amarelo (#ffaa00) | Atencao |
| 15-30% | Laranja (#ff6600) | Baixa |
| <15% | Vermelho (#ff4444) | Critico |

---

## Consumo Tipico

| Estado | RPi | Servos | Motor | Total |
|--------|-----|--------|-------|-------|
| Idle | 0.6A | 0.1A | 0A | 0.7A |
| Video streaming | 1.2A | 0.1A | 0A | 1.3A |
| Video + sensores | 1.5A | 0.1A | 0A | 1.6A |
| Curva lenta | 1.5A | 2A | 5A | 8.5A |
| Aceleracao maxima | 1.5A | 0.5A | 25A | 27A |
| Frenagem maxima | 1.5A | 4A | 0A | 5.5A |

### Autonomia Estimada

```
Bateria: 6000mAh @ 11.1V (Turnigy Graphene 3S)

Uso misto (media 10A):
  Tempo = 6000mAh / 10000mA = 0.6h = 36 minutos

Uso agressivo (media 20A):
  Tempo = 6000mAh / 20000mA = 0.3h = 18 minutos
```

---

## Arquivos Relacionados

### Arduino Pro Micro
- `pro_micro/pro_micro.ino` - Firmware de aquisicao (ADC + calibracao + serial)

### Raspberry Pi
- `raspberry/power_monitor_manager.py` - Recebe dados serial + INA219
- `raspberry/MODULOS.md` - Especificacoes dos sensores

### Cliente
- `client/sensor_display.py` - Historico e exportacao de dados
- `client/console/frames/energy_panel.py` - Painel de energia na interface
- `client/console/main.py` - Formatacao e cores dos displays

---

## Historico de Mudancas

| Data | Mudanca |
|------|---------|
| 2025-12-17 | Implementacao inicial com ADS1115 |
| 2025-12-17 | Filtro de 3 estagios + calibracao zero-current |
| 2025-12-18 | Documentacao completa (ADS1115) |
| 2026-02-14 | Migracao ADS1115 → Arduino Pro Micro (ratiometrico) |
| 2026-02-14 | Adicionado divisor de tensao para bateria (A0) |
| 2026-02-14 | Configuracao high-side para ACS758 |
| 2026-02-14 | Painel de energia dedicado na interface |
