# Sistema de Force Feedback — Logitech G923 via evdev

## Status Atual

- **Data**: 2026-03-10
- **Status**: Produção (G923 nativo via evdev, sem ESP32)

---

## Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────────────┐
│                     FLUXO DE FORCE FEEDBACK                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Raspberry Pi                    Cliente PC                         │
│  ────────────                    ──────────                         │
│                                                                     │
│  BMI160 (100Hz)                                                     │
│      │                                                              │
│      ▼                                                              │
│  UDP 9997 (60Hz) ──────────────► network_client.py                 │
│                                       │                             │
│                                       ▼                             │
│                                  sensor_display queue               │
│                                       │                             │
│                                       ▼                             │
│                         _sensor_processing_loop (100Hz thread)      │
│                                       │                             │
│                          ┌────────────┴────────────┐                │
│                          ▼                         ▼                │
│                  calculate_g_forces_and_ff()  velocity_calc()       │
│                          │                                          │
│                          ▼                                          │
│                  ┌───────┴───────┐                                  │
│                  ▼               ▼                                  │
│           send_ff_command()  send_dynamic_effects()                 │
│           (FF_CONSTANT)      (RUMBLE + PERIODIC + INERTIA)          │
│                  │               │                                  │
│                  └───────┬───────┘                                  │
│                          ▼                                          │
│                  g923_manager.py (upload_effect ioctl)              │
│                          │                                          │
│                          ▼                                          │
│                  Logitech G923 hardware (kernel ~1kHz)              │
│                                                                     │
│  Paralelamente (GUI thread, 10Hz):                                 │
│  process_queues() → _apply_local_ff()                              │
│       → update_spring/damper/friction (sliders)                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 8 Efeitos Simultâneos

### Condition effects (kernel ~1kHz, baseados em sliders)

| Efeito | Controle | Mínimo | Função |
|--------|----------|--------|--------|
| FF_SPRING | Slider Sensitivity (75%) | 5% | Centering — kernel calcula pela posição do volante |
| FF_DAMPER | Slider Damping (50%) | 0% | Resistência proporcional à velocidade do volante |
| FF_FRICTION | Slider Friction (30%) | 3% | Grip do pneu — resistência constante ao movimento |
| FF_INERTIA | Calculado (velocidade + throttle) | 5% | Peso do volante — aumenta com velocidade |

### Force effects (software, a cada pacote BMI160)

| Efeito | Fonte | Função |
|--------|-------|--------|
| FF_CONSTANT (dinâmico) | G lateral + yaw do BMI160 | Puxão lateral em curvas |
| FF_CONSTANT (endstop) | Posição do volante (~1kHz) | Batente virtual nos limites calibrados |

### Vibration effects

| Efeito | Fonte | Função |
|--------|-------|--------|
| FF_RUMBLE | 8 componentes combinados | Vibração de impactos/estrada (strong + weak motor) |
| FF_PERIODIC | Throttle → frequência | Vibração senoidal do motor (5Hz idle → 12Hz full) |

### Controle global

FF_GAIN limita todos os 8 efeitos simultaneamente. Default 15% (25%+ pode travar o G923).

---

## Otimização de Latência (2026-03-10)

### Problema: delay perceptível no force feedback

A cada pacote BMI160 (60Hz), 3 efeitos dinâmicos eram atualizados via `_recreate_effect()`,
que fazia 4 ioctls bloqueantes por efeito (stop → erase → upload → start):

```
Antes: 3 efeitos × 4 ioctls = 12 ioctls/pacote × 1-5ms cada = 12-60ms bloqueio
```

A sensor thread (100Hz, ciclo de 10ms) ficava bloqueada por mais tempo que o ciclo,
perdendo pacotes e introduzindo delay perceptível no feedback.

### Correção 1: Cache no FF_CONSTANT

`apply_constant_force()` não tinha cache — recriava o efeito mesmo com mesma
intensidade e direção. Adicionado `_last_constant_key = (level, direction)`:

```python
key = (level, ff_direction)
if key == self._last_constant_key:
    return  # Nenhum ioctl
```

### Correção 2: Quantização dos EMA outputs

Os valores de rumble, periodic e inertia passam por EMA (Exponential Moving Average),
que gera floats ligeiramente diferentes a cada ciclo (ex: 42.31 → 42.29), invalidando
o cache mesmo com input estável.

```python
# Antes: float → cache nunca acerta
sensor_data["rumble_strong"] = self._filtered_rumble_strong  # 42.3147...

# Depois: inteiro → cache funciona quando input é estável
sensor_data["rumble_strong"] = round(self._filtered_rumble_strong)  # 42
```

Aplicado em: rumble_strong/weak, periodic_magnitude, periodic_period_ms,
steering_feedback_intensity, inertia.

### Correção 3: Upload in-place ao invés de recreate

Para FF_CONSTANT, FF_RUMBLE e FF_PERIODIC, o efeito agora é atualizado via
`upload_effect(id_existente)` (1 ioctl) ao invés de erase+create (4 ioctls).
Se o driver hid-lg4ff não aplicar, faz fallback automático para recreate.

```python
# Antes: _recreate_effect() — 4 ioctls
self.device.write(EV_FF, old_id, 0)      # para
self.device.erase_effect(old_id)           # apaga
new_id = self.device.upload_effect(...)    # cria
self.device.write(EV_FF, new_id, 1)       # inicia

# Depois: upload in-place — 1 ioctl
effect = ff.Effect(FF_CONSTANT, existing_id, ...)
self.device.upload_effect(effect)          # atualiza direto
```

### Resultado

```
Antes:  12 ioctls/pacote (4 por efeito × 3 efeitos) = 12-60ms bloqueio
Depois:  0-3 ioctls/pacote (1 por efeito, só quando valor muda) = 0-15ms bloqueio
```

Quando inputs são estáveis (volante parado, throttle constante), o cache acerta e
zero ioctls são feitos. Quando há mudança real, 1 ioctl por efeito ao invés de 4.

---

## Componentes da Força (FF_CONSTANT dinâmico)

### Fórmula

```python
# Componente lateral (curvas): 0-100%
lateral_component = min(abs(g_force_lateral) * 50, 100)

# Componente yaw (rotação): 0-50%
yaw_component = min(abs(gyro_z) / 60.0 * 50, 50)

# Soma limitada
base_ff = min(lateral_component + yaw_component, 100)

# Aplicar sensitivity e EMA filter
adjusted_ff = base_ff * sensitivity
final_ff = adjusted_ff * (1 - filter) + previous_ff * filter
```

### Direção do puxão

```python
lateral_dir = g_force_lateral * 10
yaw_dir = gyro_z
total_dir = lateral_dir + yaw_dir

if total_dir > 1.5:   direction = "right"
elif total_dir < -1.5: direction = "left"
else:                   direction = "neutral"
```

---

## Componentes do Rumble (FF_RUMBLE)

8 componentes combinados em strong motor (impactos) e weak motor (contínuo):

| Componente | Strong | Weak | Fonte |
|------------|--------|------|-------|
| Engine vibration | 0.5× | 0.7× | throttle/100 × 60% |
| Bump vertical | 0.3× | 0.3× | desvio de accel_z da gravidade |
| Impacto frontal | 0.3× | — | g_force_frontal |
| Jerk BMI160 | 0.2× | — | derivada temporal de accel |
| Jerk controles | 1× | — | mudança brusca de throttle/brake/steering |
| Rugosidade | — | 1× | desvio padrão de accel_z (histórico) |
| Stress lateral | 0.3× | 0.4× | g_force_lateral em curva |
| Frenagem | 0.5× | 0.3× | brake/100 × 70% |

---

## Parâmetros Ajustáveis (Sliders)

| Parâmetro | Default | Efeito no hardware |
|-----------|---------|-------------------|
| Sensitivity | 75% | FF_SPRING coefficient + multiplicador do FF_CONSTANT |
| Friction | 30% | FF_FRICTION coefficient (mín 3%) |
| Damping | 50% | FF_DAMPER coefficient |
| Filter | 40% | EMA no FF_CONSTANT (software only) |
| Max Force | 15% | FF_GAIN global (limita todos os 8 efeitos) |

---

## Latência do Sistema

### Breakdown

| Etapa | Latência |
|-------|----------|
| BMI160 → Buffer RPi | ~1ms |
| Buffer → UDP 9997 | ~1ms |
| UDP transmissão WiFi | ~1-5ms |
| Recepção + queue | ~1ms |
| Cálculo FF (CPU) | <1ms |
| upload_effect ioctl (USB) | ~1-5ms |
| Kernel → Motor G923 | <1ms |
| **Total** | **~6-15ms** |

### Percepção Humana

- Limiar tátil: ~50ms
- Sistema: ~6-15ms
- Margem: 3-8x mais rápido que percepção

---

## Detecção de Veículo Parado

Quando o veículo está parado (sem throttle, sem brake, sem movimento significativo):
- FF_CONSTANT decai rapidamente (EMA × 0.5)
- FF_RUMBLE decai (EMA × 0.3)
- FF_PERIODIC vai para 0%
- FF_INERTIA vai para mínimo (5%)
- Histórico do BMI160 é limpo (evita dados velhos ao retomar)

---

## Arquivos

- `client/g923_manager.py` — Driver evdev, 8 efeitos FF, cache de uploads
- `client/console/logic/force_feedback_calc.py` — Cálculo dos 7 efeitos dinâmicos
- `client/console/main.py` — `_sensor_processing_loop` (100Hz) e `_apply_local_ff` (10Hz)

---

## Histórico de Mudanças

| Data | Mudança |
|------|---------|
| 2025-12-17 | Implementação inicial (ESP32 + BTS7960 via serial) |
| 2026-02-18 | Migração para G923 nativo via evdev (8 efeitos simultâneos) |
| 2026-03-10 | Otimização de latência: cache FF_CONSTANT, quantização EMA, upload in-place |
