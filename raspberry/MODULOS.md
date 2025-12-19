# Especificações dos Módulos de Hardware

Este arquivo contém as especificações técnicas de todos os módulos utilizados no projeto.

---

## Raspberry Pi 4 Modelo B

| Especificação | Valor |
|---------------|-------|
| Processador | Broadcom BCM2711, SoC quad-core Cortex-A72 (ARM v8) 64-bit @ 1.8 GHz |
| Memória | 1GB / 2GB / 4GB / 8GB LPDDR4-3200 |
| Wi-Fi | IEEE 802.11ac 2.4 GHz e 5.0 GHz |
| Bluetooth | 5.0, BLE |
| Ethernet | Gigabit |
| USB | 2x USB 3.0, 2x USB 2.0 |
| GPIO | 40 pinos (compatível com versões anteriores) |
| Vídeo | 2x micro-HDMI (até 4Kp60) |
| Display | Porta MIPI DSI 2 pistas |
| Câmera | Porta MIPI CSI 2 pistas |
| Áudio | Porta estéreo 4 polos + vídeo composto |
| Decodificação | H.265 (4Kp60), H.264 (1080p60 decode, 1080p30 encode) |
| Gráficos | OpenGL ES 3.1, Vulkan 1.0 |
| Armazenamento | Slot micro-SD |
| Alimentação | 5V DC via USB-C ou GPIO (mínimo 3A) |
| PoE | Compatível (requer HAT separado) |
| Temperatura | 0°C a 50°C (ambiente) |

---

## Câmera OV5647

| Especificação | Valor |
|---------------|-------|
| Resolução | 5 MP (2592 x 1944 pixels) |
| Tamanho do Pixel | 1.4 x 1.4 µm |
| Tipo de Sensor | OmniVision OV5647 Color CMOS QSXGA |
| Tamanho do Sensor | 3.67 x 2.74 mm (formato 1/4") |
| Abertura | f/2.9 |
| Distância Focal | 3.29 mm (equiv. 35mm full-frame) |
| Lente | f = 3.6 mm, f/2.9 |
| FOV | 65° (54° x 41°) |
| Foco | Fixo (1m ao infinito) |
| Vídeo | 1080p @ 30fps (H.264), VGA @ 90fps |
| Campo de Visão | 2.0 x 1.33 m @ 2m |
| Cabo | 16 cm |
| Dimensões | 25 x 24 x 7 mm |
| Peso | 20g |

---

## Sensor de Temperatura DS18B20

| Especificação | Valor |
|---------------|-------|
| Tensão de Operação | 3V a 5.5V DC |
| Faixa de Medição | -55°C a +125°C (recomendado até 100°C) |
| Precisão | ±0.5°C |
| Resolução | 9 ou 12 bits (configurável) |
| Tempo de Atualização | < 750 ms |

---

## IMU GY-BMI160 (6 eixos)

| Especificação | Valor |
|---------------|-------|
| Tensão de Operação | 3V a 5V DC |
| Interface | I2C ou SPI |
| Resolução AD | 16 bits |
| Faixa do Giroscópio | ±125, ±250, ±500, ±1000, ±2000 °/s |
| Faixa do Acelerômetro | ±2, ±4, ±8, ±16 g |
| Dimensões | 13 x 18 mm |

---

## Conversor ADC ADS1115

| Especificação | Valor |
|---------------|-------|
| Chip | ADS1115 |
| Resolução | 16 bits |
| Tensão de Operação | 2V a 5.5V DC |
| Interface | I2C (4 endereços de 7 bits) |
| Canais | 4 simples ou 2 diferenciais |
| Taxa de Amostragem | 8 a 860 SPS (programável) |
| Consumo | 150 µA (modo contínuo) |
| Recursos | Oscilador interno, PGA, comparador programável |
| Dimensões | 28 x 17 x 2.5 mm |

---

## Regulador Step-Down XL4015 5A

| Especificação | Valor |
|---------------|-------|
| Tensão de Entrada | 4V a 38V DC |
| Tensão de Saída | 1.25V a 36V DC |
| Corrente de Saída | Máx 5A (recomendado 4.5A) |
| Potência de Saída | Até 75W |
| Eficiência | Até 96% |
| Frequência | 180 KHz |
| Voltímetro | 4-40V (erro ±0.1V) |
| Dimensões | 66 x 39 x 18 mm |

---

## Breakout USB-C

| Especificação | Valor |
|---------------|-------|
| Pinos Disponíveis | VBUS, GND, CC1, CC2, D+, D- |
| Conectores | 6 pinos (passo 0.1") |

---

## UBEC 15A

| Especificação | Valor |
|---------------|-------|
| Tensão de Entrada | 6-12S (23V a 45V) |
| Tensão de Saída | 5.25V ±0.5V |
| Corrente Contínua | 15A |
| Corrente de Pico | 30A (10 segundos) |
| Dimensões | 55 x 28 x 5 mm |
| Peso | 36g |

---

## Driver PWM PCA9685 (16 canais)

| Especificação | Valor |
|---------------|-------|
| Controlador | PCA9685 |
| Canais | 16 |
| Resolução | 12 bits |
| Tensão de Operação | 5V a 10V DC |
| Compatibilidade | 3.3V e 5V |
| Frequência PWM | 40 Hz a 1 KHz |
| Interface | I2C (endereço selecionável) |
| Alimentação Externa | Bloco de terminais |
| Dimensões | 62 x 20 x 25 mm |
| Peso | 11g |

---

## Motor DC RC 775

| Especificação | Valor |
|---------------|-------|
| Tipo | Alto torque |
| Tensão | 12V a 18V |
| RPM | 6000 - 10000 (típico 9000 sob carga) |
| Potência | ~300W |
| Corrente | ~5A normal, 30A pico |

**Nota**: Motor conecta ao diferencial. Ver `docs/CAIXA_REDUCAO.md` para análise de velocidades.

---

## Servo Motor MG996R

| Especificação | Valor |
|---------------|-------|
| Modelo | TowerPro MG996R Metálico |
| Faixa de Rotação | 180° |
| Tipo de Engrenagem | Metálica |
| Tensão de Operação | 4.8V a 7.2V |
| Velocidade (4.8V) | 0.17 s/60° (sem carga) |
| Velocidade (6.0V) | 0.13 s/60° (sem carga) |
| Torque (4.8V) | 9.4 kgf·cm |
| Torque (6.0V) | 11.0 kgf·cm |
| Corrente de Pico | 2.5A |
| Corrente de Operação | 500 mA a 900 mA |
| Tamanho do Cabo | 28 cm |
| Conector | Dupont 3 vias |
| Dimensões | 47 x 54 x 20 mm |
| Peso (servo) | 56g |
| Peso (componentes) | 8g |

---

## Ponte H BTS7960B

| Especificação | Valor |
|---------------|-------|
| CI | BTS7960B |
| Tensão de Alimentação | 5V a 45V DC |
| Corrente Máxima | 43A (contínua) |
| Corrente de Pico | 60A |
| Dimensões | 50 x 50 x 42 mm (com dissipador) |
| Peso | 67g |

---

## Sensor de Corrente INA219 I2C

| Especificação | Valor |
|---------------|-------|
| Modelo | CJMCU-219 |
| Tensão de Operação | 3V a 5.5V |
| Interface | I2C (16 endereços) |
| Faixa de Corrente | 0 a ±3.2A (resolução 0.8 mA) |
| Faixa de Tensão | 0 a 26V |
| Faixa de Potência | 0 a 83.2W |
| Precisão | ±0.5% (corrente) |
| Resolução | 12 bits |
| Resistor Shunt | 0.1Ω (1% precisão) |
| Offset Máximo | 100 µV |
| Dimensões | 22.3 x 25.2 mm |

---

## Sensor de Corrente ACS758 100A

| Especificação | Valor |
|---------------|-------|
| Chip | ACS758LCB-100B-PFF-T |
| Tensão de Operação | 3V a 5.5V |
| Faixa de Medição | ±100A |
| Sensibilidade | 20 mV/A |
| Largura de Banda | 120 KHz |
| Corrente de Operação | 13.5 mA (máx) |
| Resistência Interna | 100 µΩ |
| Temperatura | -40°C a +150°C |
| Dimensões | 37 x 18 mm |
| Peso | 8.8g |

---

## Sensor de Corrente ACS758 50A

| Especificação | Valor |
|---------------|-------|
| Modelo | CJMCU-758 |
| Chip | ACS758LCB-050B-PFF-T |
| Tensão de Operação | 3V a 5.5V |
| Faixa de Medição | ±50A |
| Sensibilidade | 40 mV/A |
| Largura de Banda | 120 KHz |
| Corrente de Operação | 13.5 mA (máx) |
| Resistência Interna | 100 µΩ |
| Temperatura | -40°C a +150°C |
| Dimensões | 37 x 18 mm |
| Peso | 8.8g |

---

## Bateria Turnigy Graphene 6000mAh 3S

| Especificação | Valor |
|---------------|-------|
| Capacidade | 6000 mAh |
| Células | 3S |
| Tensão | 11.1V |
| Descarga Contínua | 75C |
| Descarga de Pico | 150C (3s) |
| Resistência do Pack | 7 mΩ |
| Conector de Carga | JST-XH |
| Conector de Descarga | XT90 |
| Dimensões | 168 x 69 x 23 mm |
| Peso | 507g |
