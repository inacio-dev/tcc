# Sistema de Force Feedback

Documento sobre a implementação do force feedback no volante ESP32.

## Status Atual

- **Data**: 2025-12-18
- **Status**: Produção

---

## Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────────────┐
│                     FLUXO DE FORCE FEEDBACK                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Raspberry Pi              Cliente PC              ESP32 Cockpit   │
│  ────────────              ──────────              ─────────────   │
│                                                                     │
│  BMI160 (100Hz)                                                     │
│      │                                                              │
│      ▼                                                              │
│  UDP 9997 ──────────────► Recepção                                 │
│                               │                                     │
│                               ▼                                     │
│                          Cálculo FF                                 │
│                          (g_lateral,                                │
│                           gyro_z,                                   │
│                           steering)                                 │
│                               │                                     │
│                               ▼                                     │
│                          Parâmetros                                 │
│                          (sensitivity,                              │
│                           friction,                                 │
│                           filter,                                   │
│                           damping)                                  │
│                               │                                     │
│                               ▼                                     │
│                          Serial USB ──────────► FF Motor Manager   │
│                          "FF_MOTOR:                    │            │
│                           LEFT:45"                     ▼            │
│                                                   BTS7960 PWM      │
│                                                        │            │
│                                                        ▼            │
│                                                   Motor DC 12V     │
│                                                        │            │
│                                                        ▼            │
│                                                   Torque no        │
│                                                   Volante          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Por que Calcular no Cliente?

### Alternativas Consideradas

| Local | Prós | Contras | Decisão |
|-------|------|---------|---------|
| Raspberry Pi | Menor latência | CPU limitada, 4 núcleos ocupados | Rejeitado |
| ESP32 | Ultra-baixa latência | Não tem dados do BMI160 | Impossível |
| **Cliente PC** | CPU sobrando, ajustes em tempo real | +10ms latência | **Escolhido** |

### Justificativa

1. **CPU disponível**: PC tem núcleos livres, RPi está saturado com vídeo + sensores
2. **Parâmetros ajustáveis**: Interface Tkinter permite ajustar sensitivity/friction em tempo real
3. **Latência aceitável**: 10ms adicional imperceptível para tato humano (limiar ~50ms)

---

## Componentes da Força

### Fórmula Base

```python
def calculate_force(self, sensor_data, steering_value):
    g_lateral = sensor_data.get('bmi160_g_force_lateral', 0)
    gyro_z = sensor_data.get('bmi160_gyro_z', 0)

    # Componente 1: Forças laterais em curva (0-100%)
    lateral = min(abs(g_lateral) * 50, 100)

    # Componente 2: Rotação yaw (0-50%)
    yaw = min(abs(gyro_z) / 60.0 * 50, 50)

    # Componente 3: Centralização (0-40%)
    centering = abs(steering_value) / 100.0 * 40

    # Força base combinada
    base_ff = min(lateral + yaw + centering, 100)

    return base_ff
```

### Componente Lateral (Curvas)

**Física**: Em curva, força centrípeta empurra lateralmente.

```
Curva leve:  0.3g → 0.3 × 50 = 15% força
Curva média: 0.8g → 0.8 × 50 = 40% força
Curva forte: 1.5g → 1.5 × 50 = 75% força (clamp em 100%)
```

### Componente Yaw (Rotação)

**Física**: Rotação do chassi causa torque reativo no volante.

```
Rotação leve:  20°/s → 20/60 × 50 = 16% força
Rotação média: 40°/s → 40/60 × 50 = 33% força
Rotação forte: 60°/s → 60/60 × 50 = 50% força (máximo)
```

### Componente Centralização

**Física**: Caster e KPI das rodas tendem a centralizar volante.

```
Volante centro: 0% → 0/100 × 40 = 0% força
Volante 50%:   50% → 50/100 × 40 = 20% força
Volante 100%: 100% → 100/100 × 40 = 40% força (máximo)
```

---

## Parâmetros Ajustáveis

### Sensitivity (Sensibilidade)

```python
ff_adjusted = base_ff * (sensitivity / 100.0)
```

| Valor | Efeito |
|-------|--------|
| 25% | Força muito leve |
| 50% | Força moderada |
| **75%** | **Padrão** - força realista |
| 100% | Força máxima |

### Friction (Atrito)

Simula resistência mecânica da direção.

```python
friction_force = (gyro_z / 100.0) * (friction / 100.0) * 30
ff_adjusted += friction_force
```

| Valor | Efeito |
|-------|--------|
| 0% | Volante livre |
| **30%** | **Padrão** - atrito leve |
| 60% | Atrito médio |
| 100% | Volante pesado |

### Filter (Filtro EMA)

Remove ruído de alta frequência do sensor.

```python
# Exponential Moving Average
ff_filtered = ff_adjusted * (1 - filter/100) + previous_ff * (filter/100)
```

| Valor | Efeito |
|-------|--------|
| 0% | Sem filtro (ruidoso) |
| **40%** | **Padrão** - suave |
| 70% | Muito suave (lento) |
| 100% | Sem mudança (travado) |

### Damping (Amortecimento)

Simula inércia do sistema mecânico.

```python
ff_damped = ff_filtered * (1 - damping/100) + last_ff * (damping/100)
```

| Valor | Efeito |
|-------|--------|
| 0% | Resposta instantânea |
| **50%** | **Padrão** - amortecido |
| 80% | Muito lento |
| 100% | Sem movimento |

---

## Determinação de Direção

### Algoritmo

```python
def determine_direction(self, g_lateral, gyro_z, steering):
    # Peso de cada componente na direção
    centering_dir = -steering  # Oposto ao volante
    lateral_dir = g_lateral * 10  # Amplificado
    yaw_dir = gyro_z  # Direto

    # Soma ponderada
    total_dir = centering_dir + lateral_dir + yaw_dir

    if abs(total_dir) < 5:  # Zona morta
        return "NEUTRAL"
    elif total_dir < 0:
        return "LEFT"
    else:
        return "RIGHT"
```

### Cenários

| Situação | Centering | Lateral | Yaw | Resultado |
|----------|-----------|---------|-----|-----------|
| Reto, centro | 0 | 0 | 0 | NEUTRAL |
| Reto, volante esquerda | +50 | 0 | 0 | RIGHT (centraliza) |
| Curva direita | 0 | +30 | +20 | RIGHT (resiste) |
| Curva esquerda, volante esquerda | +50 | -30 | -20 | Depende do peso |

---

## Hardware ESP32

### BTS7960 H-Bridge

```
ESP32 GPIO        BTS7960
──────────        ───────
GPIO 16  ───────► RPWM (horário)
GPIO 17  ───────► LPWM (anti-horário)
GPIO 18  ───────► R_EN (enable)
GPIO 19  ───────► L_EN (enable)
```

### Configuração PWM

```cpp
#define PWM_FREQUENCY 1000   // 1kHz
#define PWM_RESOLUTION 8     // 0-255

void setup() {
    ledcSetup(0, PWM_FREQUENCY, PWM_RESOLUTION);  // Canal RPWM
    ledcSetup(1, PWM_FREQUENCY, PWM_RESOLUTION);  // Canal LPWM
    ledcAttachPin(PIN_RPWM, 0);
    ledcAttachPin(PIN_LPWM, 1);
}
```

### Conversão Intensidade→PWM

```cpp
int intensity_to_pwm(int intensity) {
    return map(intensity, 0, 100, 0, 255);
}

// 50% força → PWM 127
// 75% força → PWM 191
// 100% força → PWM 255
```

---

## Protocolo Serial

### Formato

```
FF_MOTOR:<DIRECTION>:<INTENSITY>

Exemplos:
  FF_MOTOR:LEFT:45     → 45% força anti-horária
  FF_MOTOR:RIGHT:80    → 80% força horária
  FF_MOTOR:NEUTRAL:0   → Para motor
```

### Parsing no ESP32

```cpp
void process_ff_command(String cmd) {
    // cmd = "FF_MOTOR:LEFT:45"
    int colon1 = cmd.indexOf(':');
    int colon2 = cmd.indexOf(':', colon1 + 1);

    String direction = cmd.substring(colon1 + 1, colon2);
    int intensity = cmd.substring(colon2 + 1).toInt();

    ff_motor.set_force(direction, intensity);
}
```

---

## Startup Check

### Por que verificar na inicialização?

1. **Segurança**: Detecta BTS7960 desconectado
2. **Calibração**: Centraliza volante antes de operar
3. **Feedback**: Usuário sente que sistema funciona

### Sequência (1.5 segundos)

```cpp
void perform_startup_check() {
    // Fase 0 (0-500ms): Gira esquerda
    set_force("LEFT", 20);
    delay(500);

    // Fase 1 (500-1000ms): Gira direita
    set_force("RIGHT", 20);
    delay(500);

    // Fase 2 (1000-1500ms): Para
    set_force("NEUTRAL", 0);
    delay(500);

    startup_complete = true;
}
```

---

## Latência do Sistema

### Breakdown

| Etapa | Latência |
|-------|----------|
| BMI160 → Buffer | ~1ms |
| Buffer → UDP | ~1ms |
| UDP 9997 transmissão | ~1-2ms |
| Recepção cliente | ~1ms |
| Cálculo FF | <1ms |
| Serial USB | ~1ms |
| ESP32 parsing | <1ms |
| PWM → Motor | ~1ms |
| **Total** | **~8-10ms** |

### Percepção Humana

- Limiar tátil: ~50ms
- Sistema: ~10ms
- **Margem**: 5x mais rápido que percepção

---

## Interface de Ajuste

### Sliders Tkinter

```python
# console/frames/controls.py
ttk.Label(frame, text="Force Feedback")

ttk.Scale(frame, from_=0, to=100, variable=self.sensitivity_var,
          command=self._on_sensitivity_change)
ttk.Label(frame, text="Sensitivity")

ttk.Scale(frame, from_=0, to=100, variable=self.friction_var,
          command=self._on_friction_change)
ttk.Label(frame, text="Friction")

# ... filter, damping
```

### Valores Padrão

```python
DEFAULT_FF_PARAMS = {
    "sensitivity": 75,
    "friction": 30,
    "filter": 40,
    "damping": 50,
}
```

---

## Arquivos Relacionados

### Cliente
- `client/console/logic/force_feedback_calc.py` - Cálculo de força
- `client/console/frames/controls.py` - Interface de ajuste
- `client/serial_receiver_manager.py` - Envio serial

### ESP32
- `esp32/ff_motor_manager.h/cpp` - Controle do motor
- `esp32/esp32.ino` - Recepção de comandos

### Raspberry Pi
- `raspberry/bmi160_manager.py` - Fonte de dados de sensores

---

## Histórico de Mudanças

| Data | Mudança |
|------|---------|
| 2025-12-17 | Implementação inicial |
| 2025-12-17 | Adicionado startup check |
| 2025-12-17 | Parâmetros ajustáveis na UI |
| 2025-12-18 | Documentação completa |
