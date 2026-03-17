# Testes dos Sistemas do Veículo F1

Testes independentes para verificar o funcionamento de cada componente de hardware do veículo.

## Arquivos

### `bmi160_direct.py`

Teste do sensor BMI160 (IMU 6 eixos) via I2C.

**Hardware:** BMI160 no barramento I2C bus 1, endereço `0x68`

**Fluxo do teste:**
1. Otimização de delay I2C: testa delays de 0-100ms em passos de 5ms, lê CHIP_ID (`0x00`, esperado `0xD1`), escolhe o mínimo + 5ms de margem com validação de 10 leituras consecutivas (threshold 80%)
2. Verifica CHIP_ID e lê PMU Status (`0x03`)
3. Ativa acelerômetro (`0x7E = 0x11`) e giroscópio (`0x7E = 0x15`), aguarda 55ms para startup do gyro
4. Configura range: ±2g (reg `0x41 = 0x03`) e ±250°/s (reg `0x43 = 0x03`)
5. Configura ODR 200Hz (reg `0x40` e `0x42`)
6. Lê 5 amostras com intervalo de 200ms, converte raw 16-bit para unidades físicas (accel: `2.0/32768 g/LSB`, gyro: `250.0/32768 °/s/LSB`)
7. Valida magnitude da aceleração total (~1.0g em repouso)

```bash
cd /home/inacio-rasp/tcc/raspberry
python test/bmi160_direct.py
```

---

### `motor_direct.py`

Teste do motor RC 775 via ponte H BTS7960.

**Hardware:** BTS7960 com PWM a 2kHz

| Pino     | GPIO | Função         |
|----------|------|----------------|
| RPWM     | 18   | PWM frente     |
| LPWM     | 27   | PWM ré         |
| R_EN     | 22   | Enable frente  |
| L_EN     | 23   | Enable ré      |

**Fluxo do teste automático:**
1. Inicializa GPIO (BCM) e cria objetos PWM a 2kHz
2. Desabilita ponte H (enables LOW) como segurança
3. Inicia PWM em 0% e habilita ponte H (enables HIGH)
4. Testa frente (RPWM) com intensidades progressivas: 10%, 25%, 50%, 75%, 100% (3s cada)
5. Testa ré (LPWM) com: 10%, 25%, 50% (3s cada)
6. Testa frenagem elétrica (ambos PWM = 0%)
7. Para PWM e desabilita ponte H

**Modo interativo:** `f [PWM]` frente, `r [PWM]` ré, `s` parar, `q` sair

```bash
cd /home/inacio-rasp/tcc/raspberry
python test/motor_direct.py
```

---

### `steering_direto_simples.py`

Teste direto do servo de direção MG996R via PCA9685.

**Hardware:** PCA9685 I2C `0x41` (A0 soldado), Canal 0, frequência 50Hz, pulso 1000-2000μs

**Fluxo do teste:**
1. Inicializa PCA9685 e cria servo no canal 0
2. Testa 11 posições em padrão F1: Centro (90°) → Esquerda leve (70°) → média (45°) → forte (20°) → MAX (0°) → Centro → Direita leve (110°) → média (135°) → forte (160°) → MAX (180°) → Centro (2s por posição, confirmação por ENTER)
3. Teste de velocidade: oscilação rápida 3 ciclos (0° → 90° → 180° → 90°, 0.4s por step)
4. Varredura completa: 0° a 180° em passos de 20° (0.3s por step)
5. Retorna ao centro (90°)

```bash
cd /home/inacio-rasp/tcc/raspberry
python test/steering_direto_simples.py
```

---

### `brake_direto_simples.py`

Teste direto dos servos de freio dianteiro e traseiro via PCA9685.

**Hardware:** PCA9685 I2C `0x41`, Canal 4 (freio frontal), Canal 8 (freio traseiro), 50Hz, pulso 1000-2000μs

**Fluxo do teste:**
1. Inicializa PCA9685 e cria dois servos (canais 4 e 8)
2. Teste do freio frontal: 8 posições progressivas (0° → 30° → 60° → 90° → 120° → 150° → 180° → 90°, 1.5s cada)
3. Teste do freio traseiro: mesma sequência
4. Teste combinado: 8 combinações incluindo balanço estilo F1 (ex: frontal 180° / traseiro 170°), frenagem de emergência (180°/180°)
5. Teste de velocidade: frenagem de emergência 3 ciclos (90° → 180° → 90°, 0.6s)
6. Modulação gradual: frontal 0°-180° em passos de 30°, traseiro com offset -20°
7. Retorna ambos ao neutro (90°)

```bash
cd /home/inacio-rasp/tcc/raspberry
python test/brake_direto_simples.py
```

---

### `camera_h264.py`

Teste de captura H.264 da câmera OV5647 via picamera2.

**Hardware:** OV5647 no slot CSI, resolução 640x480, formato XBGR8888

**Fluxo do teste:**
1. Teste simples: inicia câmera, captura 1 frame como array NumPy, exibe shape
2. Teste completo H.264:
   - Verifica câmeras disponíveis via `Picamera2.global_camera_info()`
   - Configura encoder H.264: bitrate 1.5 Mbps, I-period 30 frames
   - Captura por 5s usando `TestBuffer` (buffer circular de 30 frames)
   - O buffer detecta NAL start codes (`0x000001`/`0x00000001`) e extrai tipos (1=Non-IDR, 5=IDR/keyframe, 7=SPS, 8=PPS)
   - Exibe estatísticas: tempo, writes, bytes, FPS médio, bitrate, detalhes do último frame

```bash
cd /home/inacio-rasp/tcc/raspberry
python test/camera_h264.py
```

---

### `quick_temp.py`

Teste rápido do sensor DS18B20 via 1-Wire (sem dependências do projeto).

**Hardware:** DS18B20 no GPIO4 (Pin 7), pull-up 4.7kΩ, requer `dtoverlay=w1-gpio,gpiopin=4` em `/boot/firmware/config.txt`

**Fluxo do teste:**
1. Verifica diretório `/sys/bus/w1/devices/` e busca dispositivos com prefixo `28-`
2. Loop contínuo de leitura (1 leitura/s):
   - Lê arquivo `/w1_slave` do dispositivo, valida CRC (linha termina com "YES")
   - Extrai temperatura do formato `t=XXXXX` (milidegrees / 1000 = °C)
   - Retry: até 3 tentativas com 200ms entre cada
3. Exibe: timestamp, temperatura em °C/°F/K, status térmico (NORMAL <40°C, WARNING <60°C, CRITICAL <80°C, DANGER ≥80°C)
4. A cada 10 leituras: min, max e média
5. No Ctrl+C: estatísticas finais (total leituras, min, max, média, variação total)

```bash
cd /home/inacio-rasp/tcc/raspberry
python test/quick_temp.py
```

## Pré-requisitos

- Python 3.7+
- RPi.GPIO, smbus2, adafruit-circuitpython-pca9685, picamera2
- Raspberry Pi OS com GPIO, I2C, Camera e 1-Wire habilitados
