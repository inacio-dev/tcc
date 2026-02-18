# Sistema de Teleoperação com Force Feedback para Veículo RC

Trabalho de Conclusão de Curso (TCC) - Engenharia da Computação
Universidade Federal do Ceará (UFC)

## Sobre o Projeto

Sistema completo de controle remoto para veículo RC estilo Fórmula 1 com interface háptica (force feedback), comunicação UDP de baixa latência e telemetria em tempo real. O projeto integra:

- **Veículo RC** controlado por Raspberry Pi 4 com câmera e sensores IMU
- **Simulador** com volante Logitech G923 (steering 900°, pedais progressivos, force feedback nativo)
- **Aplicação cliente** em Python para visualização e controle
- **Monitoramento de energia** via Arduino Pro Micro (tensão + corrente) e INA219

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
┌─────────────────┐     UDP      ┌─────────────────┐     USB      ┌─────────────────┐
│  Raspberry Pi 4 │◄────────────►│   Cliente PC    │◄────────────►│  Logitech G923  │
│                 │   9999/9998  │                 │    evdev     │                 │
│  - Câmera       │              │  - Interface    │              │  - Volante 900° │
│  - BMI160 IMU   │              │  - Vídeo        │              │  - Pedais       │
│  - Motor DC 775 │              │  - Telemetria   │              │  - Paddle shift │
│  - 3x Servos    │              │  - Controle     │              │  - Force FB     │
│  - Pro Micro    │              │  - G923 Manager │              │                 │
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
│   ├── network_manager.py
│   └── power_monitor_manager.py
│
├── client/             # Aplicação cliente (PC)
│   ├── main.py         # Aplicação principal
│   ├── g923_manager.py # Logitech G923 (evdev + force feedback)
│   ├── console/        # Interface gráfica (Tkinter)
│   ├── video_display.py
│   ├── sensor_display.py
│   └── slider_controller.py
│
├── pro_micro/          # Arduino Pro Micro (monitoramento de energia)
│   └── pro_micro.ino   # ADC: bateria + 2x ACS758 → USB Serial
│
├── monografia/         # Documentação acadêmica (LaTeX)
│   ├── documento.tex   # Arquivo principal
│   ├── 2-textuais/     # Capítulos
│   └── lib/            # Template UFCTeX
│
├── docs/               # Documentação técnica
├── datasheets/         # Datasheets dos componentes
└── exports/            # Dados exportados (telemetria)
```

## Hardware Necessário

### Veículo RC
- Raspberry Pi 4 Model B (4GB+ RAM)
- Câmera OV5647 (5MP, interface CSI)
- Sensor IMU BMI160 (I2C)
- Motor DC RC 775 + Ponte H BTS7960
- 3x Servo MG996R (direção + freios)
- Driver PWM PCA9685

### Monitoramento de Energia
- Arduino Pro Micro (ATmega32U4, USB nativo)
- 2x ACS758 Hall-effect current sensor (50A + 100A, high-side)
- Divisor de tensão 20kΩ/10kΩ (bateria 3S LiPo)
- INA219 (corrente do Raspberry Pi, I2C direto)

### Simulador
- Logitech G923 Racing Wheel (USB)
- Volante 900°, pedais progressivos, paddle shifters
- Force feedback nativo via Linux evdev

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
cd client
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Permissão para leitura do G923 via evdev
sudo usermod -a -G input $USER
# (logout/login necessário para aplicar)

# Configurar mDNS (Arch Linux)
sudo pacman -S avahi nss-mdns
sudo systemctl enable --now avahi-daemon
```

### Arduino Pro Micro

1. Arduino IDE: Board → Arduino Micro
2. Upload `pro_micro/pro_micro.ino`
3. Conectar via USB ao Raspberry Pi (detectado automaticamente)

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
# 1. Raspberry Pi (+ Pro Micro conectado via USB)
cd raspberry && python3 main.py

# 2. Cliente PC (+ G923 conectado via USB)
cd client && source venv/bin/activate && python3 main.py --port 9999

# G923 e Pro Micro são detectados automaticamente
```

### Controles

| Entrada | Ação |
|---------|------|
| G923 Volante | Direção (-100 a +100) |
| G923 Acelerador | Throttle (0-100%) |
| G923 Freio | Brake (0-100%) |
| G923 Paddle R | Marcha acima |
| G923 Paddle L | Marcha abaixo |
| W / ↑ | Acelerar (teclado) |
| S / ↓ | Frear (teclado) |
| A / ← | Virar esquerda (teclado) |
| D / → | Virar direita (teclado) |
| M | Marcha acima (teclado) |
| N | Marcha abaixo (teclado) |

O G923 tem prioridade sobre o teclado quando conectado.

## Protocolo de Comunicação

### UDP (Raspberry Pi ↔ Cliente)

- **Porta 9999**: Dados (vídeo MJPEG + telemetria JSON)
- **Porta 9998**: Comandos de controle

### G923 → Cliente (evdev)

```
ABS_X     → STEERING (-100 a +100)
ABS_RZ    → THROTTLE (0-100%)
ABS_Z     → BRAKE (0-100%)
BTN_GEAR_UP   → GEAR_UP
BTN_GEAR_DOWN → GEAR_DOWN
```

### Force Feedback (Cliente → G923)

```python
g923_manager.apply_force_feedback(intensity, direction)
# intensity: 0-100% | direction: "left", "right", "neutral"
# Usa FF_CONSTANT via evdev (efeito contínuo atualizado em tempo real)
```

### Serial (Pro Micro → Raspberry Pi)

```
PWR:<v_bat>,<i_servos>,<i_motor>   # Tensão (V) e correntes (A) a 10Hz
CAL                                 # Solicitar recalibração dos ACS758
```

## Documentação

- `CLAUDE.md` - Guia técnico completo para desenvolvimento
- `docs/MONITORAMENTO_ENERGIA.md` - Arquitetura do sistema de energia (Pro Micro + INA219)
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
2026
