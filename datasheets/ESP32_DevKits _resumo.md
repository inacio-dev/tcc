# ESP32 Development Kits - Resumo Técnico

**Documento**: ESP32 esp-dev-kits Documentation
**Fabricante**: Espressif Systems
**Versão**: Release master (Dec 2025)

---

## 1. Visão Geral

Este documento fornece guias detalhados para as placas de desenvolvimento da série ESP32 fabricadas pela Espressif Systems. O ESP32 é um microcontrolador dual-core Xtensa de 32 bits operando a 240 MHz, com Wi-Fi 802.11 b/g/n 2.4 GHz e Bluetooth 4.2 BR/EDR e BLE integrados.

### Especificações Gerais do ESP32

| Parâmetro | Valor |
|-----------|-------|
| Processador | 32-bit Xtensa dual-core @ 240 MHz |
| Wi-Fi | IEEE 802.11 b/g/n 2.4 GHz |
| Bluetooth | 4.2 BR/EDR e BLE |
| SRAM | 520 KB (16 KB para cache) |
| ROM | 448 KB |
| GPIOs | 34 |
| Interfaces | 4x SPI, 3x UART, 2x I2C, 2x I2S, RMT, LED PWM, 1 host SD/eMMC/SDIO, 1 slave SDIO/SPI, TWAI, 12-bit ADC, Ethernet |

---

## 2. ESP32-DevKitC

### 2.1 ESP32-DevKitC V4

Placa de desenvolvimento compacta baseada em ESP32, com a maioria dos pinos I/O expostos para fácil conexão.

#### Módulos Compatíveis
- ESP32-WROOM-32E
- ESP32-WROOM-32UE
- ESP32-WROVER-E
- ESP32-WROVER-IE
- ESP32-WROOM-32D
- ESP32-WROOM-32U
- ESP32-WROOM-DA (End of Life)
- ESP32-SOLO-1
- ESP32-WROOM-32

#### Componentes Principais

| Componente | Descrição |
|------------|-----------|
| ESP32-WROOM-32E | Módulo com ESP32 no núcleo |
| USB-to-UART Bridge | Taxa de transferência até 3 Mbps |
| Boot Button | Modo de download de firmware (Boot + EN) |
| EN Button | Reset do sistema |
| USB-to-UART Port | Micro-USB para alimentação e comunicação |
| 5V Power On LED | Indicador de alimentação |

#### Opções de Alimentação
1. Porta Micro USB (padrão)
2. Pinos 5V e GND
3. Pinos 3V3 e GND

**AVISO**: Usar apenas UMA opção de alimentação por vez.

#### Pinout J2 (Principais)

| Pino | Nome | Tipo | Função |
|------|------|------|--------|
| 1 | 3V3 | P | Alimentação 3.3V |
| 2 | EN | I | CHIP_PU, Reset |
| 3 | VP | I | GPIO36, ADC1_CH0, S_VP |
| 4 | VN | I | GPIO39, ADC1_CH3, S_VN |
| 5 | IO34 | I | GPIO34, ADC1_CH6, VDET_1 |
| 6 | IO35 | I | GPIO35, ADC1_CH7, VDET_2 |
| 7 | IO32 | I/O | GPIO32, ADC1_CH4, TOUCH_CH9, XTAL_32K_P |
| 8 | IO33 | I/O | GPIO33, ADC1_CH5, TOUCH_CH8, XTAL_32K_N |
| 9 | IO25 | I/O | GPIO25, ADC2_CH8, DAC_1 |
| 10 | IO26 | I/O | GPIO26, ADC2_CH9, DAC_2 |
| 11 | IO27 | I/O | GPIO27, ADC2_CH7, TOUCH_CH7 |
| 12 | IO14 | I/O | GPIO14, ADC2_CH6, TOUCH_CH6, MTMS |
| 13 | IO12 | I/O | GPIO12, ADC2_CH5, TOUCH_CH5, MTDI |

#### Pinout J3 (Principais)

| Pino | Nome | Tipo | Função |
|------|------|------|--------|
| 1 | GND | G | Terra |
| 2 | IO23 | I/O | GPIO23 |
| 3 | IO22 | I/O | GPIO22 |
| 4 | TX | I/O | GPIO1, U0TXD |
| 5 | RX | I/O | GPIO3, U0RXD |
| 6 | IO21 | I/O | GPIO21 |
| 8 | IO19 | I/O | GPIO19 |
| 9 | IO18 | I/O | GPIO18 |
| 10 | IO5 | I/O | GPIO5 |

**Nota**: GPIO16 e GPIO17 disponíveis apenas em módulos ESP32-WROOM e ESP32-SOLO-1 (não em ESP32-WROVER com PSRAM).

---

## 3. ESP32-DevKitM-1

### Características
- Módulo: ESP32-MINI-1 ou ESP32-MINI-1U
- Flash: 4 MB integrado no chip
- Antena: PCB on-board (MINI-1) ou conector externo (MINI-1U)
- USB-to-UART: Taxa até 3 Mbps
- Regulador: LDO 5V para 3.3V

#### Componentes

| Componente | Descrição |
|------------|-----------|
| ESP32-MINI-1 | Módulo com 4 MB flash in-package |
| 5V to 3.3V LDO | Regulador de tensão |
| Boot Button | Boot + Reset = modo download |
| Reset Button | Reset do sistema |
| Micro-USB Port | Alimentação e comunicação |
| USB-to-UART Bridge | Até 3 Mbps |
| 3.3V Power On LED | Indicador de alimentação |

#### Pinout Completo (32 pinos)

| Pino | Nome | Tipo | Função |
|------|------|------|--------|
| 1 | GND | P | Terra |
| 2 | 3V3 | P | Alimentação 3.3V |
| 3 | I36 | I | GPIO36, ADC1_CH0, RTC_GPIO0 |
| 4 | I37 | I | GPIO37, ADC1_CH1, RTC_GPIO1 |
| 5 | I38 | I | GPIO38, ADC1_CH2, RTC_GPIO2 |
| 6 | I39 | I | GPIO39, ADC1_CH3, RTC_GPIO3 |
| 7 | RST | I | Reset (High: enable, Low: off) |
| 8 | I34 | I | GPIO34, ADC1_CH6, RTC_GPIO4 |
| 9 | I35 | I | GPIO35, ADC1_CH7, RTC_GPIO5 |
| 10 | IO32 | I/O | GPIO32, XTAL_32K_P, ADC1_CH4, TOUCH9 |
| 11 | IO33 | I/O | GPIO33, XTAL_32K_N, ADC1_CH5, TOUCH8 |
| 12 | IO25 | I/O | GPIO25, DAC_1, ADC2_CH8, EMAC_RXD0 |
| 13 | IO26 | I/O | GPIO26, DAC_2, ADC2_CH9, EMAC_RXD1 |
| 14 | IO27 | I/O | GPIO27, ADC2_CH7, TOUCH7, EMAC_RX_DV |
| 15 | IO14 | I/O | GPIO14, ADC2_CH6, TOUCH6, HSPICLK |
| 16 | 5V | P | Alimentação 5V |
| 17 | IO12 | I/O | GPIO12, ADC2_CH5, TOUCH5, HSPIQ |
| 18 | IO13 | I/O | GPIO13, ADC2_CH4, TOUCH4, HSPID |
| 19 | IO15 | I/O | GPIO15, ADC2_CH3, TOUCH3, HSPICS0 |
| 20 | IO2 | I/O | GPIO2, ADC2_CH2, TOUCH2, HSPIWP |
| 21 | IO0 | I/O | GPIO0, ADC2_CH1, TOUCH1, CLK_OUT1 |
| 22 | IO4 | I/O | GPIO4, ADC2_CH0, TOUCH0, HSPIHD |
| 23 | IO9 | I/O | GPIO9, U1RXD, SD_DATA2 |
| 24 | IO10 | I/O | GPIO10, U1TXD, SD_DATA3 |
| 25 | IO5 | I/O | GPIO5, VSPICS0, EMAC_RX_CLK |
| 26 | IO18 | I/O | GPIO18, VSPICLK |
| 27 | IO23 | I/O | GPIO23, VSPID |
| 28 | IO19 | I/O | GPIO19, VSPIQ, EMAC_TXD0 |
| 29 | IO22 | I/O | GPIO22, VSPIWP, EMAC_TXD1 |
| 30 | IO21 | I/O | GPIO21, VSPIHD, EMAC_TX_EN |
| 31 | TXD0 | I/O | GPIO1, U0TXD, CLK_OUT3 |
| 32 | RXD0 | I/O | GPIO3, U0RXD, CLK_OUT2 |

**Nota**: Placas fabricadas antes de 02/12/2021 possuem módulo single-core. Habilitar CONFIG_FREERTOS_UNICORE no menuconfig.

---

## 4. ESP32-PICO-KIT-1

### Características
- Módulo: ESP32-PICO-V3 (System-in-Package)
- Integra: cristal 40 MHz, flash 4 MB, capacitores de filtro, rede de matching RF
- USB-to-UART: CP2102N (até 3 Mbps)
- Headers: 2x 18 pinos (0.1")

#### Componentes

| Componente | Descrição |
|------------|-----------|
| ESP32-PICO-V3 | SiP com ESP32 completo |
| LDO | Conversão 5V para 3.3V |
| USB-to-UART (CP2102N) | Até 3 Mbps |
| Boot Button | Modo download |
| EN Button | Reset |
| 5V Power On LED | Indicador vermelho |

#### Pinout Header J2

| Pino | Nome | Tipo | Função |
|------|------|------|--------|
| 1 | IO20 | I/O | GPIO20 |
| 2 | IO21 | I/O | GPIO21, VSPIHD, EMAC_TX_EN |
| 3 | IO22 | I/O | GPIO22, VSPIWP, U0RTS |
| 4 | IO19 | I/O | GPIO19, VSPIQ, U0CTS |
| 5 | IO8 | I/O | GPIO8, SD_DATA1, U2CTS |
| 6 | IO7 | I/O | GPIO7, SD_DATA0, U2RTS |
| 7 | IO5 | I/O | GPIO5, VSPICS0, EMAC_RX_CLK |
| 8 | IO10 | I/O | GPIO10, SD_DATA3, SPIWP |
| 9 | IO9 | I/O | GPIO9, SD_DATA2, SPIHD |
| 10 | RXD0 | I/O | GPIO3, U0RXD, CLK_OUT2 |
| 11 | TXD0 | I/O | GPIO1, U0TXD, CLK_OUT3 |
| 12 | IO35 | I | ADC1_CH7, RTC_GPIO5 |
| 13 | IO34 | I | ADC1_CH6, RTC_GPIO4 |
| 14 | IO38 | I | GPIO38, ADC1_CH2 |
| 15 | IO37 | I | GPIO37, ADC1_CH1 |
| 16 | EN | I | CHIP_PU |
| 17 | GND | P | Terra |
| 18 | VDD33 | P | Alimentação 3.3V |

#### Pinout Header J3

| Pino | Nome | Tipo | Função |
|------|------|------|--------|
| 1 | GND | P | Terra |
| 2 | SENSOR_VP | I | GPIO36, ADC1_CH0 |
| 3 | SENSOR_VN | I | GPIO39, ADC1_CH3 |
| 4 | IO25 | I/O | GPIO25, DAC_1, ADC2_CH8 |
| 5 | IO26 | I/O | GPIO26, DAC_2, ADC2_CH9 |
| 6 | IO32 | I/O | 32K_XP, ADC1_CH4, TOUCH9 |
| 7 | IO33 | I/O | 32K_XN, ADC1_CH5, TOUCH8 |
| 8 | IO27 | I/O | GPIO27, ADC2_CH7, TOUCH7 |
| 9 | IO14 | I/O | ADC2_CH6, TOUCH6, HSPICLK |
| 10 | IO12 | I/O | ADC2_CH5, TOUCH5, MTDI |
| 11 | IO13 | I/O | ADC2_CH4, TOUCH4, HSPID |
| 12 | IO15 | I/O | ADC2_CH3, TOUCH3, HSPICS0 |
| 13 | IO2 | I/O | ADC2_CH2, TOUCH2, HSPIWP |
| 14 | IO4 | I/O | ADC2_CH0, TOUCH0, HSPIHD |
| 15 | IO0 | I/O | ADC2_CH1, TOUCH1, CLK_OUT1 |
| 16 | VDD33 | P | Alimentação 3.3V |
| 17 | GND | P | Terra |
| 18 | EXT_5V | P | Alimentação 5V |

**Nota**: MTDI (GPIO12) deve ser mantido LOW no reset para flash de 3.3V.

---

## 5. ESP32-PICO-DevKitM-2

### Características
- Módulo: ESP32-PICO-MINI-02 ou ESP32-PICO-MINI-02U
- USB-to-UART: CP2102N (até 3 Mbps)
- Headers: 2x 18 pinos

Pinout similar ao ESP32-PICO-KIT-1, com IO8 e IO9 marcados como NC (não conectados).

---

## 6. ESP32-LCDKit

### Visão Geral
Placa de desenvolvimento HMI (Human Machine Interface) para uso com ESP32-DevKitC.

### Características
- Suporte para displays: SPI serial, 8-bit paralelo, 16-bit paralelo
- Slot para SD Card
- Módulo DAC-Audio com amplificador MIX3006
- 2 portas de saída para alto-falantes

#### Módulos Funcionais

| Módulo | Descrição |
|--------|-----------|
| Display Connection | Interface serial/paralela LCD |
| ESP32 DevKitC Connector | Conexão com placa DevKitC |
| SD-Card | Expansão de memória |
| DAC-Audio | Amplificador + 2 saídas de áudio |

---

## 7. ESP32-Ethernet-Kit v1.2

### Visão Geral
Placa de desenvolvimento Ethernet-to-Wi-Fi com suporte a Power over Ethernet (PoE).

### Componentes

#### Ethernet Board (A)
| Componente | Descrição |
|------------|-----------|
| ESP32-WROVER-E | Módulo com 64-Mbit PSRAM |
| IP101GRI | PHY Ethernet 10/100 Mbps |
| FT2232H | USB-to-UART e USB-to-JTAG |
| RJ45 Port | Porta de rede |
| Magnetics Module | Isolação galvânica |
| Link/Activity LEDs | Status da conexão |

#### PoE Board (B)
- Suporte: IEEE 802.3at
- Saída: 5V, 1.4A
- Terminais externos: 26.6 ~ 54V

### Interface RMII (PHY)

| ESP32 (MAC) | IP101GRI (PHY) |
|-------------|----------------|
| GPIO21 | TX_EN |
| GPIO19 | TXD[0] |
| GPIO22 | TXD[1] |
| GPIO25 | RXD[0] |
| GPIO26 | RXD[1] |
| GPIO27 | CRS_DV |
| GPIO0 | REF_CLK |
| GPIO23 | MDC |
| GPIO18 | MDIO |
| GPIO5 | Reset_N |

### Function Switch (DIP)

| DIP | GPIO |
|-----|------|
| 1 | GPIO13 (JTAG TCK) |
| 2 | GPIO12 (JTAG TDI) |
| 3 | GPIO15 (JTAG TDO) |
| 4 | GPIO14 (JTAG TMS) |

### Seleção de Clock RMII

**Opção 1 - Clock Externo do PHY (Padrão)**:
- PHY gera clock de 50 MHz a partir de cristal 25 MHz
- Saída: 50M_CLKO do IP101GRI
- GPIO5 controla RESET_N do PHY

**Opção 2 - Clock Interno do ESP32 APLL** (não recomendado):
- ESP32 gera clock via APLL
- Sinal invertido no GPIO0
- **Limitações**: Não usar se Wi-Fi e Ethernet simultâneos ou APLL em uso por I2S

---

## 8. Placas End of Life (EOL)

### ESP32-Sense-Kit

Kit de desenvolvimento para sensores touch capacitivos com sistema modular motherboard/daughterboard.

#### Componentes da Motherboard

| Componente | Descrição |
|------------|-----------|
| ESP32 Module | Unidade de controle principal |
| Mini USB | Alimentação (5V) |
| ESP-Prog Connector | Interface para download e debug |
| 7-Segment Displays (3x) | Exibem posição e duração do toque |
| CH455G | Driver I2C para displays |
| RGB LED | Feedback visual de eventos touch |
| LDO (AMS1117) | Regulador 5V → 3.3V |
| Power Switch | Liga/desliga |

#### Diagrama de Blocos

```
Mini USB ─► LDO ─► ESP32 ─┬─► Touch Sensor I/O ─► Daughterboard
    │                     ├─► I2C ─► Segment Driver ─► Displays
ESP-Prog ───────────────►├─► UART
                          └─► I/O ─► RGB LED
```

#### Sistema de Alimentação
- Duas fontes: Mini USB ou ESP-Prog (diodos de proteção impedem interferência)
- Mini USB: apenas alimentação
- ESP-Prog: alimentação + download automático de firmware
- Regulador: AMS1117 (5V → 3.3V)

#### Identificação de Daughterboards via ADC

O sistema identifica automaticamente cada daughterboard através de divisor de tensão lido pelo ADC (GPIO35/I/O35).

| Daughterboard | Resistência (kΩ) | ADC Min | ADC Max |
|---------------|------------------|---------|---------|
| Spring Button | 0 | 0 | 250 |
| Linear Slider | 4.7 | 805 | 1305 |
| Matrix Button | 10 | 1400 | 1900 |
| Duplex Slider | 19.1 | 1916 | 2416 |
| Wheel Slider | 47 | 2471 | 2971 |

**Nota**: Resistência da motherboard = 10 kΩ

#### Tipos de Daughterboards

| Tipo | Descrição | Canais Touch |
|------|-----------|--------------|
| Spring Button | Botões com mola (feedback mecânico) | Touch individuais |
| Linear Slider | Slider horizontal para controle linear | T6/IO33, T8/IO33, T7/IO27, T9/IO14, T5/IO12, T4/IO13 |
| Matrix Button | Matriz 3x3 de botões (9 botões) | T9/IO27, T9/IO27, T7/IO27 + T4/T4, T5/T5, T6/T6 |
| Duplex Slider | Slider duplo (controle de 2 eixos) | 8 segmentos + 3 botões |
| Wheel Slider | Slider circular tipo jog wheel | Segmentos radiais |

#### Cálculo de Sensibilidade Touch

Fórmula para calibrar sensibilidade com diferentes overlays:

```
Sensibilidade = (Valor_Sem_Toque - Valor_Com_Toque) / Valor_Sem_Toque
```

Onde:
- **Valor_Sem_Toque**: Contagem de pulsos sem evento touch
- **Valor_Com_Toque**: Contagem de pulsos durante evento touch
- O threshold é calculado automaticamente na inicialização

#### Estrutura do Software (ESP-IoT-Solution)

```
esp32-sense-project/
├── main/
│   ├── evb_adc.c          // Identificação de daughterboards via ADC
│   ├── evb.h              // Config: threshold, ADC I/O, I2C I/O
│   ├── evb_led.cpp        // Driver RGB LED
│   ├── evb_seg_led.c      // Driver 7-segment (CH455G)
│   ├── evb_touch_button.cpp   // Driver touch button
│   ├── evb_touch_wheel.cpp    // Driver wheel slider
│   ├── evb_touch_matrix.cpp   // Driver matrix button
│   ├── evb_touch_seq_slide.cpp // Driver duplex slider
│   ├── evb_touch_slide.cpp    // Driver linear slider
│   ├── evb_touch_spring.cpp   // Driver spring button
│   └── main.cpp           // Entry point
├── Makefile
└── sdkconfig.defaults
```

#### Configuração ESP-Prog

| Jumper | Configuração |
|--------|--------------|
| Power Supply | 5V |
| IO0 | Desconectar se usar como pino touch |

**Conexão**: Usar interface "Program" (não JTAG) entre ESP-Prog e motherboard

---

### ESP32-MeshKit-Sense

Placa de desenvolvimento para medição de consumo de corrente do ESP32 em diferentes modos de operação.

#### Componentes Principais

| Componente | Descrição |
|------------|-----------|
| ESP32 Module | Módulo ESP32 principal |
| AP5056 | Carregador de bateria Li-ion (4.2V, 1A) |
| ETA3425 | DC-DC 3.3V, 600mA máx. |
| HTS221 | Sensor de temperatura e umidade (I2C) |
| BH1750FVI | Sensor de luz ambiente digital (I2C) |
| APDS-9960 | Sensor de proximidade, gestos e cor RGB (I2C) |
| Screen Connector | Interface para displays externos (SPI) |
| Wake-up Button | Botão conectado a GPIO34 (RTC domain) |

#### Diagrama de Blocos

```
USB Port ─► Charge Chip (AP5056) ─► Battery
                    │
                    ├─► DC-DC ─► 3.3V_ESP (ESP32 Module)
                    │           │
                    │           └─► 3.3V_Perip ─┬─► 3.3V_Perip_Sensor (HTS221, BH1750, APDS-9960)
                    │                           └─► 3.3V_Perip_Screen (External)
                    │
                    └─► PROG Header (3.3V, GND, TX, RX, EN, IO0)
```

#### Ramificações de Alimentação

| Rail | Função | Controle |
|------|--------|----------|
| ESP32_VDD33 | Alimentação do módulo ESP32 | Jumper J9 |
| VDD33_PeriP | Alimentação de periféricos | GPIO + MOS |
| VDD33_PeriP_Screen | Display externo | GPIO controlável |
| VDD33_PeriP_Sensor | 3 sensores onboard | GPIO controlável |

#### Sensores I2C

| Sensor | Endereço I2C | Função |
|--------|--------------|--------|
| HTS221 | 0x5F | Temperatura e umidade (CS=HIGH para I2C) |
| BH1750FVI | 0x5C (H) / 0x23 (L) | Luz ambiente digital |
| APDS-9960 | 0x39 | Proximidade, gestos, cor RGBC, IR LED driver |

**Nota**: APDS-9960 não é soldado por padrão.

---

### ESP-WROVER-KIT (v2, v3, v4.1)

Placa de desenvolvimento avançada com JTAG integrado, LCD e slot microSD.

#### Componentes Principais

| Componente | Descrição |
|------------|-----------|
| ESP32-WROVER-E | Módulo com 64-Mbit PSRAM |
| FT2232HL | USB-to-UART (Ch B) e USB-to-JTAG (Ch A) |
| 32.768 kHz Crystal | Oscilador externo para Deep-sleep |
| 0R Resistor | Placeholder para shunt de medição de corrente |
| LCD 3.2" | Display SPI (4-wire) |
| microSD Slot | Armazenamento de dados |
| RGB LED | GPIO0 (Red), GPIO2 (Green), GPIO4 (Blue) |
| Camera Connector | Interface OV7670 (JP4) |

#### Pinagem JTAG (JP2/JP8)

| Pino | ESP32 GPIO | Sinal JTAG |
|------|------------|------------|
| 1 | EN | TRST_N |
| 2 | GPIO14 (MTMS) | TMS |
| 3 | GPIO15 (MTDO) | TDO |
| 4 | GPIO12 (MTDI) | TDI |
| 5 | GPIO13 (MTCK) | TCK |

#### Interface LCD (U5)

| Pino | ESP32 GPIO | Sinal LCD |
|------|------------|-----------|
| 1 | GPIO18 | RESET |
| 2 | GPIO19 | SCL |
| 3 | GPIO21 | D/C |
| 4 | GPIO22 | CS |
| 5 | GPIO23 | SDA |
| 6 | GPIO25 | SDO |
| 7 | GPIO5 | Backlight |

#### Interface microSD Card

| Pino | ESP32 GPIO | Sinal SD |
|------|------------|----------|
| 1 | GPIO12 (MTDI) | DATA2 |
| 2 | GPIO13 (MTCK) | CD/DATA3 |
| 3 | GPIO15 (MTDO) | CMD |
| 4 | GPIO14 (MTMS) | CLK |
| 5 | GPIO2 | DATA0 |
| 6 | GPIO4 | DATA1 |
| 7 | GPIO21 | Card Detect |

#### Configuração de Jumpers

| Header | Configuração | Função |
|--------|--------------|--------|
| JP7 | USB_5V | Alimentação via USB (padrão) |
| JP7 | EXT_5V | Alimentação externa 5V |
| JP2/JP8 | TMS/TDO/TDI/TCK | Habilitar JTAG |
| JP2/JP11 | RXD/TXD | Habilitar UART |
| JP14 | CTS/RTS | Flow control (desabilitado por padrão) |

**Nota**: GPIO16/GPIO17 reservados para PSRAM no ESP32-WROVER.

---

### ESP32-PICO-KIT (v3, v4, v4.1)

Placa de desenvolvimento compacta baseada no ESP32-PICO-D4 SiP.

#### Características do ESP32-PICO-D4 (SiP)

O módulo integra em um único pacote:
- ESP32 SoC completo
- Cristal 40 MHz
- Flash 4 MB
- Capacitores de filtro
- Rede de matching RF

#### Componentes

| Componente | Descrição |
|------------|-----------|
| ESP32-PICO-D4 | System-in-Package (SiP) |
| LDO | 5V → 3.3V |
| USB-UART | CP2102 (v4, 1 Mbps) ou CP2102N (v4.1, 3 Mbps) |
| EN Button | Reset |
| BOOT Button | Download mode |
| 5V Power LED | Indicador vermelho |

#### Pinout Header J2

| Pino | Nome | Função |
|------|------|--------|
| 1 | FSD1 | GPIO8, SD_DATA1, SPID |
| 2 | FSD3 | GPIO7, SD_DATA0, SPIQ |
| 3 | FCLK | GPIO6, SD_CLK, SPICLK |
| 4 | IO21 | GPIO21, VSPIHD |
| 5 | IO22 | GPIO22, VSPIWP |
| 6 | IO19 | GPIO19, VSPIQ |
| 7 | IO23 | GPIO23, VSPID |
| 8 | IO18 | GPIO18, VSPICLK |
| 9 | IO5 | GPIO5, VSPICS0 |
| 10 | IO10 | GPIO10, SD_DATA3, SPIWP |
| 11 | IO9 | GPIO9, SD_DATA2, SPIHD |
| 12 | RXD0 | GPIO3, U0RXD |
| 13 | TXD0 | GPIO1, U0TXD |
| 14 | IO35 | GPIO35, ADC1_CH7 |
| 15 | IO34 | GPIO34, ADC1_CH6 |
| 16 | IO38 | GPIO38, ADC1_CH2 |
| 17 | IO37 | GPIO37, ADC1_CH1 |

#### Pinout Header J3

| Pino | Nome | Função |
|------|------|--------|
| 1 | FCS | GPIO16, Flash CS |
| 2 | FSD0 | GPIO17, Flash SD0 |
| 3 | FSD2 | GPIO11, SD_CMD |
| 4 | FSVP | GPIO36, ADC1_CH0 |
| 5 | FSVN | GPIO39, ADC1_CH3 |
| 6 | IO25 | GPIO25, DAC_1 |
| 7 | IO26 | GPIO26, DAC_2 |
| 8 | IO32 | GPIO32, 32K_XP, ADC1_CH4, TOUCH9 |
| 9 | IO33 | GPIO33, 32K_XN, ADC1_CH5, TOUCH8 |
| 10 | IO27 | GPIO27, ADC2_CH7, TOUCH7 |
| 11 | IO14 | GPIO14, ADC2_CH6, TOUCH6 |
| 12 | IO12 | GPIO12, ADC2_CH5, TOUCH5 (strapping!) |
| 13 | IO13 | GPIO13, ADC2_CH4, TOUCH4 |
| 14 | IO15 | GPIO15, ADC2_CH3, TOUCH3 |
| 15 | IO2 | GPIO2, ADC2_CH2, TOUCH2 |
| 16 | IO4 | GPIO4, ADC2_CH0, TOUCH0 |
| 17 | IO0 | GPIO0, ADC2_CH1, TOUCH1 (strapping!) |

#### Dimensões

- **Tamanho**: 52 x 20.3 x 10 mm (2.1" x 0.8" x 0.4")

**Nota**: GPIO12 (MTDI) deve ser LOW no reset para flash 3.3V.

---

## 9. Strapping Pins (Pinos de Configuração)

| GPIO | Função no Boot |
|------|----------------|
| GPIO0 | Boot mode (HIGH=Flash Boot, LOW=Download) |
| GPIO2 | Boot mode |
| GPIO5 | Timing SDIO Slave |
| GPIO12 (MTDI) | Voltagem do flash (LOW=3.3V, HIGH=1.8V) |
| GPIO15 (MTDO) | Timing SDIO Slave, silencia boot log |

---

## 10. Referências e Documentação

- ESP32 Datasheet
- ESP32-WROOM-32E Datasheet
- ESP32-WROVER-E Datasheet
- ESP32-PICO-V3 Datasheet
- ESP32-MINI-1 & ESP32-MINI-1U Datasheet
- ESP-IDF Programming Guide
- JTAG Debugging Guide

---

*Documento gerado a partir de: ESP32 esp-dev-kits Documentation - Espressif Systems*
