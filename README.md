# Sistema de Teleoperação com Force Feedback para Veículo RC

Trabalho de Conclusão de Curso (TCC) - Engenharia da Computação
Universidade Federal do Ceará (UFC)

## Sobre o Projeto

Sistema completo de controle remoto para veículo RC estilo Fórmula 1 com interface háptica (force feedback), comunicação UDP de baixa latência e telemetria em tempo real. O projeto integra:

- **Veículo RC** controlado por Raspberry Pi 4 com câmera e sensores IMU
- **Cockpit físico** com volante, pedais e force feedback via ESP32
- **Aplicação cliente** em Python para visualização e controle

### Principais Resultados

| Métrica | Obtido | Benchmark |
|---------|--------|-----------|
| Latência UDP | 1.94ms | < 5ms |
| FPS Vídeo | 29.9 | 10 (literatura) |
| Resolução | 640×480 | 320×240 (literatura) |
| Precisão Force Feedback | 97.2% | - |
| Custo Total | R$ 1.300 | R$ 50.000+ (comercial) |

## Arquitetura do Sistema

```
┌─────────────────┐     UDP      ┌─────────────────┐    Serial    ┌─────────────────┐
│  Raspberry Pi 4 │◄────────────►│   Cliente PC    │◄────────────►│  ESP32 Cockpit  │
│                 │   9999/9998  │                 │   115200     │                 │
│  - Câmera       │              │  - Interface    │              │  - Encoders     │
│  - BMI160 IMU   │              │  - Vídeo        │              │  - Botões       │
│  - Motores      │              │  - Telemetria   │              │  - Force FB     │
│  - Servos       │              │  - Controle     │              │  - BTS7960      │
└─────────────────┘              └─────────────────┘              └─────────────────┘
```

## Estrutura do Projeto

```
tcc/
├── raspberry/          # Código do Raspberry Pi 4
│   ├── main.py         # Orquestrador principal
│   ├── camera_manager.py
│   ├── bmi160_manager.py
│   ├── motor_manager.py
│   ├── steering_manager.py
│   ├── brake_manager.py
│   └── network_manager.py
│
├── client/             # Aplicação cliente (PC)
│   ├── main.py         # Aplicação principal
│   ├── console_interface.py
│   ├── video_display.py
│   ├── sensor_display.py
│   └── serial_receiver_manager.py
│
├── esp32/              # Firmware do cockpit
│   ├── esp32.ino       # Orquestrador dual-core
│   ├── throttle_manager.h/cpp
│   ├── brake_manager.h/cpp
│   ├── steering_manager.h/cpp
│   └── ff_motor_manager.h/cpp
│
├── monografia/         # Documentação acadêmica (LaTeX)
│   ├── documento.tex   # Arquivo principal
│   ├── 2-textuais/     # Capítulos
│   └── lib/            # Template UFCTeX
│
├── datasheets/         # Datasheets dos componentes
└── exports/            # Dados exportados (telemetria)
```

## Hardware Necessário

### Veículo RC
- Raspberry Pi 4 Model B (4GB+ RAM)
- Câmera OV5647 (5MP, interface CSI)
- Sensor IMU BMI160 (I2C)
- Motor DC RS550 12V + Ponte H BTS7960
- 3x Servo MG996R (direção + freios)
- Driver PWM PCA9685

### Cockpit
- ESP32 DevKit V1
- 3x Encoder rotativo LPD3806-600BM (600 PPR)
- 2x Push buttons (marchas)
- Motor DC 775 24V + Ponte H BTS7960 (force feedback)

### Rede
- Roteador WiFi 2.4GHz
- Suporte a mDNS (Avahi)

## Instalação

### Raspberry Pi

```bash
# Habilitar interfaces
sudo raspi-config  # Ativar Camera, I2C, SPI

# Instalar dependências
sudo apt update
sudo apt install python3-opencv python3-numpy python3-picamera2 python3-libcamera

# Instalar pacotes Python
pip install smbus2 adafruit-circuitpython-pca9685 adafruit-circuitpython-servokit

# Configurar hostname
sudo hostnamectl set-hostname f1car
echo "127.0.1.1 f1car" | sudo tee -a /etc/hosts
sudo systemctl restart avahi-daemon
```

### Cliente (Linux)

```bash
# Instalar dependências
pip install opencv-python numpy pyserial Pillow av

# Configurar mDNS (Arch Linux)
sudo pacman -S avahi nss-mdns
sudo systemctl enable --now avahi-daemon
```

### ESP32

1. Instalar Arduino IDE ou PlatformIO
2. Adicionar suporte à placa ESP32
3. Fazer upload do código em `esp32/esp32.ino`

### Monografia (LaTeX)

```bash
# Arch Linux
sudo pacman -S texlive-latex texlive-latexrecommended texlive-latexextra texlive-fontsrecommended texlive-science texlive-plaingeneric
yay -S abntex2

# Compilar
cd monografia
make compile
```

## Uso

### Iniciar o Sistema

```bash
# 1. Raspberry Pi
cd raspberry && python3 main.py

# 2. Cliente PC
cd client && python3 main.py --port 9999

# 3. ESP32 conectado via USB será detectado automaticamente
```

### Controles

| Entrada | Ação |
|---------|------|
| W / ↑ | Acelerar |
| S / ↓ | Frear |
| A / ← | Virar esquerda |
| D / → | Virar direita |
| M | Marcha acima |
| N | Marcha abaixo |

O cockpit físico (ESP32) tem prioridade sobre o teclado quando conectado.

## Protocolo de Comunicação

### UDP (Raspberry Pi ↔ Cliente)

- **Porta 9999**: Dados (vídeo H.264 + telemetria JSON)
- **Porta 9998**: Comandos de controle

### Serial (ESP32 → Cliente)

```
THROTTLE:<0-100>      # Posição do acelerador
BRAKE:<0-100>         # Posição do freio
STEERING:<-100 a 100> # Posição do volante
GEAR_UP / GEAR_DOWN   # Troca de marchas
```

### Force Feedback (Cliente → ESP32)

```
FF_MOTOR:LEFT:<0-100>    # Força anti-horária
FF_MOTOR:RIGHT:<0-100>   # Força horária
FF_MOTOR:NEUTRAL:0       # Liberar volante
```

## Documentação

- `CLAUDE.md` - Guia técnico completo para desenvolvimento
- `raspberry/MODULOS.md` - Especificações dos módulos de hardware
- `raspberry/DIAGRAMA.drawio.pdf` - Diagrama elétrico completo
- `datasheets/` - Datasheets dos componentes
- `monografia/` - Monografia completa do TCC (LaTeX)

## Métricas de Validação

O sistema foi validado através de sessão de 15 minutos com:
- 90.000+ pontos de telemetria
- 26.925 frames de vídeo
- Análise estatística completa (ANOVA, teste t, correlação de Pearson)

Detalhes completos disponíveis em `monografia/2-textuais/4-resultados.tex`.

## Licença

Este projeto foi desenvolvido como Trabalho de Conclusão de Curso.
Template LaTeX baseado no UFCTeX/abnTeX2 (LPPL License).

## Autor

Inácio Medeiros
Engenharia da Computação - UFC
2025
