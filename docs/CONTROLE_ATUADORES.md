# Controle de Atuadores - Motor, Freios e Direção

Documento sobre as decisões técnicas do sistema de controle do veículo.

## Status Atual

- **Data**: 2025-12-18
- **Status**: Produção

---

## Visão Geral do Sistema

```
Comando Cliente → UDP 9998 → Raspberry Pi → Atuadores
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
               Motor RC 775    Servos MG996R    Servo MG996R
               (BTS7960)      (Freio F+R)       (Direção)
                    │               │               │
                    ▼               ▼               ▼
               GPIO 18/27      PCA9685 CH0/1   PCA9685 CH2
```

---

## Motor RC 775 + Transmissão Manual

### Por que RC 775?

| Motor | Potência | Tensão | RPM | Decisão |
|-------|----------|--------|-----|---------|
| RS550 | ~200W | 12V | 19000 | RPM alto demais |
| RS380 | ~30W | 7.2V | 15000 | Fraco para o chassi |
| **RC 775** | ~300W | 12-18V | 6000-10000 | **Escolhido** - alto torque + melhor controle |

**Motivo da escolha:**
- **Alto torque**: Essencial para arranque e subidas
- **Melhor controle**: RPM moderado (6000-10000) permite controle mais preciso via PWM
- **Potência adequada**: 300W suficiente para o chassi sem exagero

**Nota**: Ver `docs/CAIXA_REDUCAO.md` para discussão sobre caixa de redução.

### Por que Ponte H BTS7960?

| Driver | Corrente | Proteção | Decisão |
|--------|----------|----------|---------|
| L298N | 2A | Básica | Insuficiente para RC 775 |
| **BTS7960** | 43A | Térmica + curto | **Escolhido** |
| IBT-2 | 43A | Similar BTS7960 | Mesma performance |

### Conexão BTS7960

```
BTS7960          Raspberry Pi
────────         ────────────
RPWM     ◄────── GPIO 18 (PWM frente)
LPWM     ◄────── GPIO 27 (PWM ré)
R_EN     ◄────── GPIO 22 (enable, HIGH)
L_EN     ◄────── GPIO 23 (enable, HIGH)
VCC      ◄────── 5V
GND      ◄────── GND
B+/B-    ◄────── Bateria 12V
M+/M-    ────►── Motor RC 775
```

### Frequência PWM

```python
PWM_FREQUENCY = 2000  # 2kHz
```

**Por que 2kHz?**
- <1kHz: Ruído audível (zumbido)
- 2kHz: Silencioso, eficiente
- >10kHz: Perdas por switching, aquecimento

---

## Transmissão Manual de 5 Marchas

### Por que 5 marchas manuais?

**Alternativas consideradas:**

| Sistema | Complexidade | Realismo | Decisão |
|---------|--------------|----------|---------|
| Direto (sem marcha) | Simples | Baixo | Rejeitado |
| CVT automático | Médio | Médio | Rejeitado |
| **5 marchas manual** | Médio | Alto | **Escolhido** |
| 8 marchas (F1 real) | Alto | Máximo | Overkill |

### Relações de Transmissão

```python
GEAR_RATIOS = {
    1: 3.5,   # Arranque - 28% velocidade, torque máximo
    2: 2.2,   # Aceleração - 45% velocidade
    3: 1.4,   # Velocidade média - 71% velocidade
    4: 0.9,   # Alta velocidade - 111% velocidade
    5: 0.7,   # Máxima - 143% velocidade, torque mínimo
}
```

### Zonas de Eficiência Estilo F1

```python
EFFICIENCY_ZONES = {
    1: {"ideal": (0, 20),   "suboptimal": (20, 30), "poor": (30, 100)},
    2: {"ideal": (20, 40),  "suboptimal": (10, 20), "poor": (0, 10)},
    3: {"ideal": (40, 60),  "suboptimal": (30, 40), "poor": (0, 30)},
    4: {"ideal": (60, 80),  "suboptimal": (50, 60), "poor": (0, 50)},
    5: {"ideal": (80, 100), "suboptimal": (70, 80), "poor": (0, 70)},
}
```

### Penalidade de Aceleração

| Zona | Tempo 0→100% | Multiplicador |
|------|--------------|---------------|
| Ideal | 5s | 1x |
| Subótima | 50s | 10x mais lento |
| Ruim | 125s | 25x mais lento |

**Simulação**: Motor "engasga" fora da zona ideal, como carro real.

---

## Sistema de Freios Dual-Servo

### Por que 2 servos independentes?

**Alternativa**: 1 servo com distribuidor mecânico
- Mais simples, mas sem ajuste de balanço

**Escolhido**: 2 servos (frente + traseiro)
- Balanço ajustável via software
- Simula bias de freio de F1

### Balanço de Freio

```python
DEFAULT_BRAKE_BALANCE = 60  # 60% frente, 40% traseiro
```

**Por que 60/40?**
- Transferência de peso na frenagem: frente recebe mais carga
- F1 real: 55-60% frente típico
- Ajustável via comando `CONTROL:BRAKE_BALANCE:value`

### Servos MG996R

| Parâmetro | Valor |
|-----------|-------|
| Ângulo | 0° (solto) a 180° (máximo) |
| Torque | 11 kg·cm @ 6V |
| PWM | 50Hz, pulse 1-2ms |
| Alimentação | 6V externo (não do RPi) |

### Por que PCA9685?

| Método | Canais PWM | Precisão | Decisão |
|--------|------------|----------|---------|
| GPIO direto | 2 (hardware) | 8-bit | Insuficiente |
| **PCA9685** | 16 | 12-bit (4096 steps) | **Escolhido** |
| Adafruit PWM Hat | 16 | 12-bit | Mesmo chip, mais caro |

---

## Direção Servo

### Range Mecânico

```python
STEERING_MIN_ANGLE = 0      # Máximo esquerda
STEERING_CENTER = 56.7      # Centro
STEERING_MAX_ANGLE = 113.4  # Máximo direita
```

**Por que não 0-180°?**
- Geometria do chassi limita movimento
- Forçar além do limite danifica servo e linkagem

### Mapeamento de Input

```python
def set_steering(self, value):
    """value: -100 (esquerda) a +100 (direita)"""
    # Mapeia -100..+100 para 0..113.4°
    angle = self.STEERING_CENTER + (value / 100.0) * self.STEERING_CENTER
    angle = max(0, min(113.4, angle))
    self.servo.angle = angle
```

### Modos de Direção

| Modo | Sensibilidade | Uso |
|------|---------------|-----|
| NORMAL | 1.0x | Padrão |
| **SPORT** | 1.2x | **Ativo** - mais responsivo |
| COMFORT | 0.8x | Suavizado |
| PARKING | Assistido | Manobras lentas |

---

## Movimento Direto vs Suavizado

### Decisão: Movimento DIRETO

```python
# ESCOLHIDO: Direto
def set_throttle(self, value):
    self.current_pwm = value
    self._apply_pwm(value)

# REJEITADO: Suavizado
def set_throttle_smooth(self, value):
    while self.current_pwm != value:
        self.current_pwm += 1 if value > self.current_pwm else -1
        self._apply_pwm(self.current_pwm)
        time.sleep(0.01)
```

**Por que direto?**
1. Latência mínima: ~10ms vs ~500ms
2. Controle preciso: Usuário determina velocidade de mudança
3. Force feedback: Resposta instantânea ao volante
4. Menos CPU: Sem threads de interpolação

**Trade-off aceito**: Mudanças bruscas podem causar stress mecânico (aceitável para RC).

---

## Thread Safety

### Lock por Componente

```python
class MotorManager:
    def __init__(self):
        self.state_lock = threading.Lock()

    def set_throttle(self, value):
        with self.state_lock:
            self._apply_throttle(value)

    def get_status(self):
        with self.state_lock:
            return self.current_status.copy()
```

**Por que lock separado por componente?**
- Permite operações paralelas (ex: freio e direção simultâneos)
- Evita deadlock (cada lock é independente)
- Granularidade fina: só bloqueia o necessário

---

## Comandos UDP

### Protocolo

```
CONTROL:THROTTLE:50      → Motor 50%
CONTROL:BRAKE:100        → Freio máximo
CONTROL:STEERING:-30     → 30% esquerda
CONTROL:BRAKE_BALANCE:55 → 55% frente
CONTROL:GEAR_UP          → Subir marcha
CONTROL:GEAR_DOWN        → Descer marcha
```

### Callback de Processamento

```python
def handle_command(self, command):
    parts = command.split(":")
    if parts[0] != "CONTROL":
        return

    action = parts[1]
    value = int(parts[2]) if len(parts) > 2 else None

    with self.motor_lock:
        if action == "THROTTLE":
            self.motor_mgr.set_throttle(value)
        elif action == "GEAR_UP":
            self.motor_mgr.shift_gear_up()

    with self.brake_lock:
        if action == "BRAKE":
            self.brake_mgr.apply_brake(value)

    with self.steering_lock:
        if action == "STEERING":
            self.steering_mgr.set_steering(value)
```

---

## Arquivos Relacionados

### Raspberry Pi
- `raspberry/motor_manager.py` - Controle do motor RC 775
- `raspberry/brake_manager.py` - Sistema de freios dual
- `raspberry/steering_manager.py` - Controle de direção
- `raspberry/main.py` - Callback de comandos

### Cliente
- `client/slider_controller.py` - Controles de interface
- `client/keyboard_controller.py` - Teclado WASD/MN

### Documentação
- `raspberry/MODULOS.md` - Especificações de hardware

---

## Histórico de Mudanças

| Data | Mudança |
|------|---------|
| 2025-12-17 | Implementação inicial |
| 2025-12-17 | Adicionado sistema de marchas |
| 2025-12-17 | Zonas de eficiência F1 |
| 2025-12-18 | Documentação de decisões |
