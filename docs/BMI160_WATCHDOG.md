# BMI160 Brown-Out Watchdog + Otimizações de Performance

## Problema 1: BMI160 zera durante aceleração do motor

### Sintoma

Quando o throttle sobe (motor RC 775 puxa alta corrente):
- BMI160 retorna `accel_data=[0, 0, 0, 0, 0, 0], gyro_data=[0, 0, 0, 0, 0, 0]`
- Os zeros persistem **indefinidamente** — o sensor nunca recupera
- Telemetria de acelerômetro e giroscópio fica completamente inoperante

### Causas raiz (eram 3 problemas simultâneos)

**1. Brown-out elétrico (hardware)**

O motor RC 775 causa queda momentânea de tensão no barramento 3.3V do RPi.
O BMI160 faz power-on reset e volta ao suspend mode (PMU = 0x00).
Em suspend, os registradores de dados retornam zero, mas I2C continua funcionando.

**2. Starvation no I2C (software)**

O PriorityI2CLock original usava prioridade estrita: steering/brake (prioridade 0)
bloqueavam completamente o BMI160 (prioridade 1) durante aceleração contínua.
Sem conseguir ler o sensor, o watchdog detectava zeros e fazia rewake desnecessário.

**3. Delays excessivos no driver (software)**

Cada `_write_register()` tinha 5ms de delay (vs 2µs do datasheet).
O `_rewake_sensor()` levava ~183ms. A combinação com starvation fazia
o BMI160 ficar offline por centenas de milissegundos.

### Diferença entre as 3 causas

| Causa | Zeros? | errno 5? | Lock resolve? | Recupera? |
|-------|--------|----------|---------------|-----------|
| Brown-out | Sim (persistente) | Não | Não | Precisa rewake PMU |
| I2C collision | Não (None) | Sim | Sim | Automático |
| I2C starvation | Sim (timeout) | Não | Parcial* | Precisa fair queuing |

*O lock antigo com prioridade estrita era a própria causa do starvation.

### Timeline do problema (antes das correções)

```
t=0:     Motor idle, BMI160 lê normalmente
t=1:     Throttle sobe → steering envia comandos contínuos ao PCA9685
t=2:     PriorityI2CLock (strict) → BMI160 bloqueado (starvation)
t=3:     Motor puxa ~30A → tensão cai → BMI160 brown-out reset
t=4:     BMI160 em suspend mode + bloqueado no I2C → zeros permanentes
t=5-50:  _rewake_sensor() com delays de 5ms/registro → recovery lento (~183ms)
t=50+:   BMI160 volta, mas starvation continua → novos zeros → loop infinito
```

## Solução: 4 correções combinadas

### 1. Watchdog de zeros (detecção)

```python
self._consecutive_zeros = 0
self._ZERO_THRESHOLD = 3  # Reduzido de 5 → 3 (detecção mais rápida, ~30ms a 100Hz)

# Em read_sensor_data():
all_zero = all(b == 0 for b in accel_data) and all(b == 0 for b in gyro_data)
if all_zero:
    self._consecutive_zeros += 1
    if self._consecutive_zeros >= self._ZERO_THRESHOLD:
        self._rewake_sensor()
        return True  # Usa dados anteriores neste ciclo
else:
    self._consecutive_zeros = 0
```

Threshold reduzido de 5 para 3: a 100Hz, 3 zeros = 30ms. O brown-out é instantâneo,
então 3 leituras consecutivas zeradas são suficientes para confirmar reset do sensor
sem risco de falso positivo.

### 2. Rewake otimizado (~100ms vs ~183ms)

Delays ajustados conforme datasheet BST-BMI160-DS000-09:

```python
# _write_register(): 5ms → 1ms (datasheet: 2µs settling, 1ms margem)
# _read_register(): 5ms → 0ms (leitura não precisa delay)

# _rewake_sensor() Estágio 1: PMU re-activation (~100ms)
self._write_register(REG_CMD, CMD_ACC_SET_PMU_MODE)  # Accel normal
time.sleep(0.004)   # 10ms → 4ms (datasheet: 3.8ms startup accel)
self._write_register(REG_CMD, CMD_GYR_SET_PMU_MODE)  # Gyro normal
time.sleep(0.080)   # 80ms mantido (datasheet: 80ms startup gyro)
time.sleep(0.010)   # 50ms → 10ms (settling final)

# _rewake_sensor() Estágio 2: Soft reset (se estágio 1 falhar, ~200ms)
self._write_register(REG_CMD, CMD_SOFT_RESET)
time.sleep(0.100)   # 200ms → 100ms
# Re-ativa e re-configura tudo
time.sleep(0.010)   # 50ms → 10ms (settling final)
```

### 3. Fair Queuing no I2C (anti-starvation)

PriorityI2CLock reescrito de strict priority para weighted fair queuing:

```
Antes (strict): steering sempre passa → BMI160 bloqueado indefinidamente
Depois (fair):  3x steering → 2x BMI160 → 3x steering → 2x BMI160 → ...
```

Pesos: Alta=3 turnos, Média=2 turnos, Baixa=1 turno. Após gastar os turnos,
a thread cede para outras prioridades. Ver detalhes em `I2C_BUS_LOCK.md`.

### 4. I2C baudrate 400kHz (velocidade)

Barramento I2C-1 configurado de 100kHz para 400kHz (Fast mode).
Cada transação I2C leva 4x menos tempo, reduzindo a janela de contenção.
Todos os 3 dispositivos (BMI160, PCA9685, INA219) suportam 400kHz.

Configuração em `/boot/firmware/config.txt`. Ver detalhes em `I2C_CONFIG.md`.

### Por que as 4 correções juntas resolveram

| Correção | O que resolve | Sozinha bastaria? |
|----------|---------------|-------------------|
| Watchdog (threshold 3) | Detecta brown-out rápido | Não — starvation impede o rewake |
| Rewake otimizado | Recupera sensor em ~100ms | Não — starvation bloqueia o I2C |
| Fair queuing | Garante acesso do BMI160 | Não — brown-out ainda zera o sensor |
| I2C 400kHz | Reduz tempo de cada transação | Não — não resolve brown-out nem starvation |

Nenhuma correção isolada resolvia. O brown-out zerava o sensor, o starvation
impedia a leitura (e o rewake), e os delays lentos prolongavam a recuperação.
As 4 juntas eliminam o ciclo: detecção rápida (3 zeros) + acesso garantido
(fair queuing) + recovery rápido (100ms) + transações curtas (400kHz).

### Hardware recomendado (complementar)

Capacitores no VDD/GND do BMI160 para filtrar brown-out na fonte:
- **100µF eletrolítico**: reserva de energia para quedas momentâneas
- **100nF cerâmico**: filtra ruído de alta frequência

Colocar os dois em paralelo, o mais próximo possível dos pinos VDD/GND do BMI160.

## Problema 2: UI do client congela periodicamente

### Sintoma

A UI do client (Tkinter) congela por ~1-2s a cada poucos segundos, causando:
- Vídeo desaparece ("Sem Sinal" após 2s sem frame)
- Telemetria para de atualizar
- Sliders não respondem

### Causa raiz

O `process_queues()` (chamado a cada 100ms via `root.after()`) executava `update_hardware_effects()` que fazia **5 `upload_effect` ioctls** para o G923 a cada chamada, mesmo quando os valores não mudavam:

```
A cada 100ms (10x por segundo):
  → update_spring(75%)      → ioctl EVIOCSFF (bloqueante)
  → update_damper(50%)      → ioctl EVIOCSFF (bloqueante)
  → update_friction(30%)    → ioctl EVIOCSFF (bloqueante)
  → update_inertia(5%)      → ioctl EVIOCSFF (bloqueante)
  → update_periodic(40, 3%) → ioctl EVIOCSFF (bloqueante)
```

Cada ioctl pode levar 1-5ms no driver hid-logitech-hidpp. Com 5 chamadas, são 5-25ms de bloqueio da thread UI, 10x por segundo. Se o kernel ou o USB têm latência variável, isso pode acumular e causar frame drops.

### Solução: Deduplicação de uploads FF

Cache do último coeficiente enviado para cada efeito. Só faz ioctl quando o valor realmente muda:

```python
# Cache
self._last_spring_coeff = -1
self._last_damper_coeff = -1
self._last_friction_coeff = -1
self._last_inertia_coeff = -1
self._last_periodic_key = None
self._last_rumble_key = None

def update_spring(self, coefficient_pct):
    coeff = int(pct / 100.0 * 32767)
    if coeff == self._last_spring_coeff:
        return  # Nenhum ioctl!
    with self._ff_lock:
        self._update_condition_effect(...)
        self._last_spring_coeff = coeff
```

**Resultado**: quando sliders estão parados (99% do tempo), zero ioctls por ciclo. Redução de ~50 ioctls/s → 0.

## Problema 3: Auto-save bloqueia thread UI

### Sintoma

A cada 20s, o auto-save serializava 70+ deques × 10k elementos com `pickle.dump()` na thread principal do Tkinter, bloqueando processamento de pacotes UDP.

### Solução

1. **Snapshot rápido** sob lock (~5ms): `{k: list(v) for k, v in history.items()}`
2. **pickle.dump em thread background** (daemon): não bloqueia a UI
3. **Reset via `root.after(0, ...)`** de volta na thread UI (Tkinter não é thread-safe)
4. **sensor_display.export_history_fast()**: snapshot sob lock, I/O fora do lock

## Arquivos modificados

- `raspberry/bmi160_manager.py`: Watchdog de zeros + `_rewake_sensor()` (PMU recovery)
- `client/g923_manager.py`: Cache de coeficientes FF, dedup de uploads
- `client/console/logic/auto_save.py`: I/O em thread background
- `client/sensor_display.py`: Snapshot sob lock, pickle fora do lock
