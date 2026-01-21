# Testes dos Componentes ESP32

Este diretorio contem testes independentes para verificar o funcionamento de cada componente do ESP32.

**IMPORTANTE**: Cada teste e um sketch .ino completamente independente, sem dependencias do projeto principal.

## Arquivos de Teste

### test_throttle_encoder/

Teste do encoder de aceleracao (LPD3806-600BM-G5-24C).

**Pinagem:**
| Pino | GPIO | Cor do Fio |
|------|------|------------|
| CLK (A) | 25 | Branco |
| DT (B) | 26 | Verde |
| VCC | 5V | Vermelho |
| GND | GND | Preto |

**O que testa:**
- Leitura do encoder via interrupcao
- Contagem de pulsos
- Conversao para porcentagem (0-100%)
- Exibicao visual no Serial Monitor

---

### test_brake_encoder/

Teste do encoder de freio (LPD3806-600BM-G5-24C).

**Pinagem:**
| Pino | GPIO | Cor do Fio |
|------|------|------------|
| CLK (A) | 27 | Verde |
| DT (B) | 14 | Branco |
| VCC | 5V | Vermelho |
| GND | GND | Preto |

**O que testa:**
- Leitura do encoder via interrupcao
- Contagem de pulsos
- Conversao para porcentagem (0-100%)
- Exibicao visual no Serial Monitor

---

### test_steering_encoder/

Teste do encoder de direcao (LPD3806-600BM-G5-24C).

**Pinagem:**
| Pino | GPIO | Cor do Fio |
|------|------|------------|
| CLK (A) | 12 | Branco |
| DT (B) | 13 | Verde |
| VCC | 5V | Vermelho |
| GND | GND | Preto |

**O que testa:**
- Leitura do encoder via interrupcao
- Contagem de pulsos com posicao central
- Conversao para porcentagem (-100% a +100%)
- Indicador de direcao (esquerda/centro/direita)

---

### test_gear_buttons/

Teste dos botoes de troca de marcha.

**Pinagem:**
| Componente | GPIO |
|------------|------|
| Botao Marcha Cima | 32 |
| Botao Marcha Baixo | 33 |

**Conexao:** Botao entre GPIO e GND (usa pull-up interno)

**O que testa:**
- Leitura dos botoes com debounce
- Deteccao de pressao (ativo LOW)
- Simulacao de troca de marchas (1-5)
- Contador de pressionamentos

---

### test_ff_motor/

Teste do motor de force feedback via driver BTS7960.

**Pinagem BTS7960 -> ESP32:**
| Pino BTS7960 | GPIO |
|--------------|------|
| RPWM | 16 |
| LPWM | 17 |
| R_EN | 18 |
| L_EN | 19 |
| VCC | 5V |
| GND | GND |

**Alimentacao Motor:** 6V-27V DC em B+/B-

**O que testa:**
- Controle PWM bidirecional
- Rotacao horaria e anti-horaria
- Diferentes intensidades (30%, 60%)
- Simulacao do algoritmo de force feedback real:
  - Componente de forcas G laterais
  - Componente de rotacao yaw
  - Componente de centragem do volante
  - Calculo combinado

---

## Como Usar

### 1. Abrir no Arduino IDE

1. Abra a pasta do teste desejado (ex: `test_throttle_encoder/`)
2. Abra o arquivo `.ino`
3. Selecione a placa: **ESP32 Dev Module**
4. Selecione a porta serial
5. Faca o upload

### 2. Usando PlatformIO

```bash
cd esp32/test/test_throttle_encoder
pio run --target upload
pio device monitor -b 115200
```

### 3. Monitor Serial

Todos os testes usam **115200 baud**.

```bash
# Arduino IDE: Tools -> Serial Monitor -> 115200 baud
# PlatformIO: pio device monitor -b 115200
# Linux: screen /dev/ttyUSB0 115200
```

---

## Troubleshooting

### Encoder nao responde

1. Verifique alimentacao (5V no VCC)
2. Confirme conexao dos fios (cores podem variar)
3. Teste continuidade dos cabos
4. Verifique se capacitores de filtro estao instalados (100nF)

### Encoder conta na direcao errada

Os pinos CLK e DT podem estar invertidos. Troque as conexoes ou inverta a logica no codigo.

### Botoes nao detectam pressao

1. Confirme conexao: GPIO -> Botao -> GND
2. Verifique se o botao esta funcionando (use multimetro)
3. Aumente o DEBOUNCE_DELAY se houver leituras falsas

### Motor nao gira

1. Verifique alimentacao do motor (B+/B- no BTS7960)
2. Confirme que R_EN e L_EN estao em HIGH
3. Teste o motor diretamente na fonte
4. Verifique conexoes M+/M- no BTS7960

### Motor gira na direcao errada

Inverta as conexoes M+ e M- no BTS7960.

---

## Especificacoes dos Componentes

### Encoder LPD3806-600BM-G5-24C

- Resolucao: 600 PPR (pulsos por revolucao)
- Saida: Quadratura AB
- Tensao: 5-24V DC
- Tipo: Coletor aberto NPN

### Driver BTS7960

- Corrente maxima: 43A
- Tensao: 6-27V
- PWM: Ate 25kHz
- Protecoes: Sobrecorrente, sobretemperatura
