# Logitech G923 - Setup e Troubleshooting (Linux)

## Modelo

- **Versão**: G923 Racing Wheel for Xbox One and PC
- **USB ID original**: `046d:c26d` (modo Xbox GIP, USB class 0xFF)
- **USB ID após modeswitch**: `046d:c26e` (modo HID, USB class 0x03)
- **Driver kernel**: `logitech-hidpp-device` (módulo `hid_logitech_hidpp`)
- **Kernel testado**: 6.12.73-1-lts (Arch Linux)

## Setup Inicial

### 1. Instalar usb_modeswitch

O G923 versão Xbox usa protocolo GIP (Xbox Game Input Protocol) por padrão, que NÃO é reconhecido como dispositivo de input padrão no Linux. É necessário trocar para modo HID.

```bash
# Arch Linux
sudo pacman -S usb_modeswitch

# Ubuntu/Debian
sudo apt install usb-modeswitch
```

### 2. Trocar modo Xbox GIP → HID

Rodar **após plugar** o volante (necessário toda vez que plugar):

```bash
sudo usb_modeswitch -v 046d -p c26d -M 0f00010142 -C 0x03 -m 01 -r 81
```

Após o comando, o PID muda de `c26d` para `c26e` e o dispositivo aparece em `/dev/input/event*`.

### 3. Permissão de acesso ao evdev

O usuário precisa estar no grupo `input` para acessar `/dev/input/event*`:

```bash
sudo usermod -a -G input $USER
# Requer logout/login para aplicar
```

### 4. Verificar detecção

```bash
python3 -c "import evdev; [print(evdev.InputDevice(d).name) for d in evdev.list_devices()]"
# Deve aparecer: "Logitech G923 Racing Wheel for Xbox One and PC"
```

### 5. Instalar ferramentas de teste (opcional)

```bash
# Arch Linux
sudo pacman -S linuxconsole

# Testar FF nativo
fftest /dev/input/event27
```

## Mapeamento de Eixos e Botões

Descoberto via `evdev.InputDevice.capabilities()`:

### Eixos (EV_ABS)

| Eixo | Code | Range | Função |
|------|-------|-------|--------|
| ABS_X | 0 | 0-65535 | Steering (volante) |
| ABS_Y | 1 | 0-255 | Throttle (acelerador, invertido) |
| ABS_Z | 2 | 0-255 | Brake (freio, invertido) |
| ABS_RZ | 5 | 0-255 | Não usado (sem pedal físico na versão Xbox) |
| ABS_HAT0X | 16 | -1 a 1 | D-pad horizontal |
| ABS_HAT0Y | 17 | -1 a 1 | D-pad vertical |

**ATENÇÃO**: Na versão Xbox do G923, o acelerador é ABS_Y (code=1), NÃO ABS_RZ (code=5). O evdev rotula ABS_Y como "clutch" mas fisicamente é o pedal do acelerador. Confirmado via test_g923.py — ABS_Y fez range completo 0-255 ao pisar no acelerador, ABS_RZ nunca disparou evento.

### Botões (EV_KEY) - Paddle Shifters

| Botão | Code | Função |
|-------|------|--------|
| BTN_TOP2 | 292 | Paddle direito → GEAR_UP |
| BTN_PINKIE | 293 | Paddle esquerdo → GEAR_DOWN |

**ATENÇÃO**: Os codes 710/711 (BTN_GEAR_DOWN/UP) NÃO são usados na versão Xbox do G923. Os paddles reais são 292 e 293.

### Outros Botões (23 no total)

Codes 288-303 e 704-710 (BTN_TRIGGER, BTN_THUMB, etc.)

## Force Feedback (evdev)

### Efeitos suportados (15)

FF_RUMBLE, FF_PERIODIC, FF_CONSTANT, FF_SPRING, FF_FRICTION, FF_DAMPER, FF_INERTIA, FF_RAMP, FF_SQUARE, FF_TRIANGLE, FF_SINE, FF_SAW_UP, FF_SAW_DOWN, FF_GAIN, FF_AUTOCENTER

**Slots simultâneos**: 63

### Bug crítico: nomes de campo ctypes no python-evdev

O `evdev.ff.EffectType` é um `ctypes.Union`. Os nomes dos campos DEVEM corresponder exatamente aos definidos na struct. O ctypes aceita silenciosamente nomes errados como atributos Python, mas o buffer C fica zerado — resultando em level=0 (nenhuma força).

```python
# ERRADO - ctypes aceita mas buffer fica zerado!
ff.EffectType(ff_constant_ef=ff.Constant(9830, ...))

# CORRETO - dados vão para o buffer C
ff.EffectType(ff_constant_effect=ff.Constant(9830, ...))
```

Nomes corretos dos campos:
- `ff_constant_effect` (não `ff_constant_ef`)
- `ff_ramp_effect`
- `ff_periodic_effect` (não `ff_periodic_ef`)
- `ff_condition_effect` (não `ff_condition_ef`) — requer `Condition * 2` (array de 2)
- `ff_rumble_effect` (não `ff_rumble_ef`)

### upload_effect retorna o ID

```python
# ERRADO - effect.id permanece -1
dev.upload_effect(effect)
effect_id = effect.id  # -1!

# CORRETO - upload_effect retorna o ID atribuído pelo kernel
effect_id = dev.upload_effect(effect)  # 0, 1, 2...
```

### Exemplo funcional: FF_CONSTANT

```python
from evdev import InputDevice, ecodes, ff

dev = InputDevice('/dev/input/event27')

# 1. Definir ganho global
dev.write(ecodes.EV_FF, ecodes.FF_GAIN, 0xFFFF)

# 2. Criar efeito
effect = ff.Effect(
    ecodes.FF_CONSTANT,
    -1,          # id = -1 para novo efeito
    0xC000,      # direction (0x4000=esq, 0xC000=dir)
    ff.Trigger(0, 0),
    ff.Replay(0xFFFF, 0),  # duração longa
    ff.EffectType(
        ff_constant_effect=ff.Constant(
            9830,  # level: signed, -32767 a +32767
            ff.Envelope(0, 0, 0, 0)
        )
    ),
)

# 3. Upload e play
effect_id = dev.upload_effect(effect)
dev.write(ecodes.EV_FF, effect_id, 1)  # play

# 4. Atualizar força (reusar mesmo effect_id)
new_effect = ff.Effect(
    ecodes.FF_CONSTANT, effect_id, 0x4000,
    ff.Trigger(0, 0), ff.Replay(0xFFFF, 0),
    ff.EffectType(
        ff_constant_effect=ff.Constant(-9830, ff.Envelope(0, 0, 0, 0))
    ),
)
dev.upload_effect(new_effect)

# 5. Parar e remover
dev.write(ecodes.EV_FF, effect_id, 0)
dev.erase_effect(effect_id)
```

## Informações do sysfs

```
Driver: logitech-hidpp-device
HID_ID: 0003:0000046D:0000C26E
Modalias: hid:b0003g0001v0000046Dp0000C26E
Range: 900 (graus de rotação)
Range sysfs: /sys/devices/.../0003:046D:C26E.*/range
```

## Diagnóstico

### Verificar driver vinculado

```bash
ls -la /sys/class/input/event27/device/device/driver
# Deve apontar para: logitech-hidpp-device
```

### Verificar módulos carregados

```bash
lsmod | grep -i logi
# Deve mostrar: hid_logitech_hidpp
```

### Testar FF com fftest

```bash
fftest /dev/input/event27
# Testar efeitos 0-5 digitando o número
```

### Script de teste Python

```bash
cd client && python3 tests/test_g923.py
```

## Histórico de Troubleshooting

Registro cronológico dos problemas encontrados e soluções durante a integração do G923 no projeto.

### Problema 1: G923 não detectado como dispositivo de input

**Sintoma**: `evdev.list_devices()` não listava o G923. `lsusb` mostrava `046d:c26d` mas nenhum `/dev/input/event*` era criado.

**Investigação**:
1. `lsusb -v` revelou que o G923 Xbox usa USB class `0xFF` (vendor-specific) — protocolo Xbox GIP
2. O kernel espera USB class `0x03` (HID) para criar dispositivos de input
3. O módulo `hid_logitech_hidpp` tem alias para PID `c26e` mas NÃO para `c26d` (modo Xbox)

**Solução**: Instalar `usb_modeswitch` e trocar o protocolo:
```bash
sudo usb_modeswitch -v 046d -p c26d -M 0f00010142 -C 0x03 -m 01 -r 81
```
Após o comando, PID muda para `c26e`, USB class muda para `0x03`, e o dispositivo aparece em `/dev/input/event*`.

### Problema 2: evdev.list_devices() retorna lista vazia

**Sintoma**: Mesmo após modeswitch, `evdev.list_devices()` retornava 0 dispositivos.

**Causa**: Arquivos em `/dev/input/event*` são `root:input` com permissão `660`. Usuário não estava no grupo `input`.

**Solução**:
```bash
sudo usermod -a -G input $USER
# Requer logout/login completo para aplicar
```

### Problema 3: Paddles mapeados nos codes errados

**Sintoma**: Código assumia BTN_GEAR_UP (711) e BTN_GEAR_DOWN (710) para os paddles, baseado na documentação genérica do G923. Mas o G923 versão Xbox usa codes diferentes.

**Investigação**: Script de teste `test_g923.py` revelou os codes reais pressionando cada paddle:
- Paddle esquerdo → BTN_PINKIE (code=293), NÃO 710
- Paddle direito → BTN_TOP2 (code=292), NÃO 711

**Solução**: Atualizar `g923_manager.py`:
```python
BTN_PADDLE_DOWN = 293  # BTN_PINKIE - paddle esquerdo
BTN_PADDLE_UP = 292    # BTN_TOP2 - paddle direito
```

### Problema 4: upload_effect retorna -1

**Sintoma**: `effect.id` permanecia `-1` após `upload_effect()`. Force feedback nunca era ativado pois `write(EV_FF, -1, 1)` é inválido.

**Causa**: `upload_effect()` retorna o ID como **valor de retorno**, não modifica `effect.id` in-place (o `ff.Effect` é uma struct ctypes).

**Solução**:
```python
# ERRADO
dev.upload_effect(effect)
effect_id = effect.id  # permanece -1!

# CORRETO
effect_id = dev.upload_effect(effect)  # retorna 0, 1, 2...
```

### Problema 5: FF uploads bem-sucedidos mas nenhuma força sentida

**Sintoma**: Todos os uploads de efeitos FF retornavam sucesso (id=0), play não dava erro, mas absolutamente nenhuma força era sentida no volante. Testado com FF_CONSTANT, FF_AUTOCENTER, FF_SPRING, FF_DAMPER, FF_RUMBLE — nenhum funcionou.

**Investigação**:
1. Verificado driver (`logitech-hidpp-device`), permissões (`660`, grupo `input`), FF capabilities (15 efeitos) — tudo correto
2. Testado 8 abordagens diferentes (FF_AUTOCENTER, FF_CONSTANT com direction, FF_CONSTANT com signed level, FF_SPRING, FF_DAMPER, FF_PERIODIC, FF_RUMBLE) — nenhuma funcionou
3. Instalado `fftest` (`sudo pacman -S linuxconsole`) para testar FF no nível do kernel → **todos os 6 efeitos do fftest funcionaram perfeitamente**
4. Conclusão: problema no código Python, não no driver

**Causa raiz**: Bug sutil nos nomes de campo do `ctypes.Union`. O `ff.EffectType` é um `ctypes.Union` e aceita silenciosamente keyword arguments que não correspondem a nenhum campo. O argumento errado é armazenado como atributo Python, mas o buffer C subjacente permanece zerado.

```python
# Verificação que provou o bug:
eff_wrong = ff.EffectType(ff_constant_ef=ff.Constant(9830, ...))
bytes(eff_wrong)  # → 00000000... (tudo zero!)

eff_right = ff.EffectType(ff_constant_effect=ff.Constant(9830, ...))
bytes(eff_right)  # → 6626... (9830 em little-endian!)
```

Com `level=0` no buffer, o kernel recebia um efeito de força zero — por isso uploads tinham sucesso mas nada acontecia.

**Solução**: Usar os nomes EXATOS dos campos definidos em `evdev.ff`:
- `ff_constant_effect` (não `ff_constant_ef`)
- `ff_periodic_effect` (não `ff_periodic_ef`)
- `ff_condition_effect` (não `ff_condition_ef`)
- `ff_rumble_effect` (não `ff_rumble_ef`)

### Resumo das correções em g923_manager.py

1. `upload_effect()` → capturar retorno: `self._ff_effect_id = self.device.upload_effect(effect)`
2. `ff_constant_ef` → `ff_constant_effect` (nome correto do campo ctypes)
3. Adicionar `FF_GAIN = 0xFFFF` na inicialização do FF
4. Paddle codes: `710/711` → `293/292` (versão Xbox)

## Arquitetura do Client com G923

### Fluxo de dados

```
G923 (USB HID, ~1000Hz poll)
    │
    ├─ ABS_X  (steering)  ──► command_callback("STEERING", "-30")
    ├─ ABS_Y  (throttle)  ──► command_callback("THROTTLE", "75")
    ├─ ABS_Z  (brake)     ──► command_callback("BRAKE", "50")
    ├─ BTN_TOP2 (292)     ──► command_callback("GEAR_UP", "")
    └─ BTN_PINKIE (293)   ──► command_callback("GEAR_DOWN", "")
            │
            ▼
    main.py handle_g923_command()
            │
            ├─ Atualiza sliders visuais (slider_controller.update_from_g923)
            └─ Envia via rede SOMENTE se RPi confirmado (packets_received > 0)
                    │
                    ▼
            network_client.send_control_command() ──► RPi UDP:9998

RPi BMI160 ──► UDP:9999 ──► client ──► ff_calculator.calculate_g_forces_and_ff()
                                            │
                                            ├─► g923_manager.apply_constant_force()  → FF_CONSTANT
                                            ├─► g923_manager.update_rumble()          → FF_RUMBLE
                                            ├─► g923_manager.update_periodic()        → FF_PERIODIC
                                            └─► g923_manager.update_inertia()         → FF_INERTIA
```

### Proteção contra envio de rede sem RPi conectado

**Problema**: Quando o RPi está desligado, `sendto("f1car.local")` tenta resolver o nome via mDNS, o que bloqueia por ~5 segundos por chamada. Como o G923 gera ~1000 eventos/segundo, isso travava completamente a thread de input.

**Solução**: Três camadas de proteção:

1. **`handle_g923_command()` em `main.py`**: Verifica `network_client.packets_received > 0` antes de enviar. Só conta como "conectado" quando pelo menos um pacote UDP foi recebido do RPi.

2. **`send_command_to_rpi()` em `network_client.py`**: Verifica `self.is_connected_to_rpi` (flag setada quando primeiro pacote chega). Retorna `False` silenciosamente se RPi não confirmado — sem log para não poluir.

3. **`run_receiver()` em `network_client.py`**: Removida a atribuição prematura de `is_connected_to_rpi = True` durante o setup de configuração. Agora a flag só é setada quando o primeiro pacote real é recebido.

```python
# network_client.py - guard em send_command_to_rpi
def send_command_to_rpi(self, command: str) -> bool:
    if not self.raspberry_pi_ip or not self.is_connected_to_rpi:
        return False  # Silencioso — sem bloqueio mDNS
    # ... sendto() seguro
```

### Slider Controller: modo visual com G923

Quando o G923 está conectado, o `SliderController` opera em modo somente-visual:

- **`update_from_g923()`**: O G923Manager chama este método para atualizar os sliders na UI. Flag `_updating_from_g923` previne callbacks circulares.

- **Callbacks de slider** (`_on_throttle_change`, `_on_brake_change`, `_on_steering_change`): Verificam `_updating_from_g923 or _g923_connected()` — se verdadeiro, retornam sem enviar pela rede (evita envio duplicado).

- **`_send_loop` (thread 100Hz)**: Quando `_g923_connected()` retorna `True`, a thread entra em sleep em vez de enviar comandos. A taxa de envio real vem do próprio G923 (~1000Hz USB HID).

```python
# slider_controller.py
def _g923_connected(self) -> bool:
    return self.g923_manager is not None and self.g923_manager.is_connected()

def _on_throttle_change(self, value):
    # ...
    if self._updating_from_g923 or self._g923_connected():
        return  # G923 é o dono do envio

def _send_loop(self):
    while self.is_active:
        if self._g923_connected():
            time.sleep(0.1)
            continue
        # ... envio normal (teclado/fallback)
```

### Logging throttled de eixos do G923

O G923 gera ~1000 eventos/segundo. Para não poluir o console de logs, os valores de eixo (steering, throttle, brake) são logados no máximo 1x/segundo:

```python
# main.py - handle_g923_command()
if now - self._g923_last_log_time >= self._g923_log_interval:
    self._g923_last_log_time = now
    log_queue.put(("DEBUG", f"G923: DIR={g923._steering:+4d}° "
                            f"ACEL={g923._throttle:3d}% "
                            f"FREIO={g923._brake:3d}%"))
```

Botões (GEAR_UP, GEAR_DOWN) são logados imediatamente pois são eventos discretos.

### Troca de marchas

As marchas vêm exclusivamente do RPi via campo `current_gear` nos dados de sensor UDP. Os paddles do G923 enviam `GEAR_UP`/`GEAR_DOWN` para o RPi, que gerencia o estado da marcha e retorna o valor atualizado no próximo pacote de telemetria.

## Force Feedback Local (sem RPi)

### Comportamento com multi-efeito

Com a arquitetura multi-efeito, o FF local funciona automaticamente via efeitos de hardware:

- **FF_SPRING**: Centering baseado na posição do volante — mínimo 5% sempre ativo (peso mecânico)
- **FF_DAMPER**: Resistência baseado na velocidade — funciona sem nenhum dado externo
- **FF_FRICTION**: Resistência constante — mínimo 3% sempre ativo (atrito mecânico)
- **FF_INERTIA**: Peso base do volante (5% idle) — aumenta com velocidade quando RPi conectado
- **FF_PERIODIC**: Vibração idle do motor (25Hz, 3%) — sempre ligada, aumenta com throttle
- **FF_RUMBLE**: Desligado sem RPi (sem dados de accel_z para detectar bumps)
- **FF_CONSTANT**: Zerado sem RPi (sem dados de G lateral + yaw)

O método `_apply_local_ff()` em `console/main.py` chama `ff_calculator.update_hardware_effects()` periodicamente para manter os coeficientes sincronizados com os sliders.

### Transição local → RPi

Quando dados do RPi chegam, `calculate_g_forces_and_ff()` atualiza o FF_CONSTANT com forças dinâmicas (G lateral + yaw). Os efeitos de hardware (spring/damper/friction) continuam rodando independentemente.

## Arquitetura Multi-Efeito (Force Feedback)

### Motivação

A versão anterior usava apenas FF_CONSTANT e calculava spring, damping e friction em software Python a ~10Hz. O G923 suporta 15 tipos de efeito com 63 slots simultâneos. Efeitos condicionais (FF_SPRING, FF_DAMPER, FF_FRICTION) rodam no firmware do volante a ~1kHz — muito mais suaves e realistas.

### 7 efeitos simultâneos

```
Condition effects (kernel ~1kHz):
  Slot 0: FF_SPRING    ← centering spring (posição do volante), mínimo 5%
  Slot 1: FF_DAMPER    ← amortecimento (velocidade do volante)
  Slot 2: FF_FRICTION  ← atrito constante (grip do pneu), mínimo 3%
  Slot 3: FF_INERTIA   ← peso do volante (aumenta com velocidade)

Force effects (software, a cada pacote):
  Slot 4: FF_CONSTANT  ← forças dinâmicas do BMI160 (G lateral + yaw)

Vibration effects (hardware):
  Slot 5: FF_RUMBLE    ← vibração de impactos/estrada (strong + weak motor)
  Slot 6: FF_PERIODIC  ← vibração senoidal do motor (freq = RPM via throttle)
```

### Controle global: FF_GAIN

O slider "Max Force" controla o `FF_GAIN` do evdev, que é um multiplicador global que limita TODOS os efeitos simultaneamente:

```python
# g923_manager.set_ff_max_percent(percent)
gain = int(percent / 100.0 * 0xFFFF)
device.write(ecodes.EV_FF, ecodes.FF_GAIN, gain)
# Default: 15% — valores acima de 25% travam o volante
```

### Mapeamento dos sliders para efeitos hardware

| Slider | Default | Efeito evdev | Função |
|--------|---------|-------------|--------|
| Sensitivity | 75% | FF_SPRING coeff + FF_CONSTANT multiplier | Centering + intensidade geral |
| Friction | 30% | FF_FRICTION coeff (mín 3%) | Resistência constante (grip do pneu) |
| Damping | 50% | FF_DAMPER coeff | Resistência proporcional à velocidade |
| Filter | 40% | Software EMA no FF_CONSTANT | Suaviza ruído dos sensores BMI160 |
| Max Force | 15% | FF_GAIN global | Limite de TODOS os 7 efeitos |

Efeitos automáticos (sem slider — calculados pelo contexto):

| Efeito | Fonte | Cálculo |
|--------|-------|---------|
| FF_INERTIA | Velocidade + throttle | 5% idle → 80% em alta velocidade |
| FF_RUMBLE (strong) | accel_z + accel_x | Impactos bruscos + frenagem forte |
| FF_RUMBLE (weak) | accel_z | Textura contínua da estrada |
| FF_PERIODIC | Throttle | 25Hz/3% idle → 50Hz/30% em full throttle |

### Efeitos condicionais (FF_SPRING, FF_DAMPER, FF_FRICTION)

Estrutura evdev para efeitos condicionais:

```python
from evdev import ff, ecodes

# ff.Condition(right_sat, left_sat, right_coeff, left_coeff, deadband, center)
# Valores: 0-32767

# Array de 2 condições: [eixo X, eixo Y]. Para volante, só X importa.
cond = (ff.Condition * 2)(
    ff.Condition(16384, 16384, 16384, 16384, 0, 0),  # eixo X (steering)
    ff.Condition(0, 0, 0, 0, 0, 0),                   # eixo Y (ignorado)
)

effect = ff.Effect(
    ecodes.FF_SPRING,  # ou FF_DAMPER, FF_FRICTION
    -1,  # id=-1 para novo efeito
    0,   # direction (não usado em condicionais)
    ff.Trigger(0, 0),
    ff.Replay(0xFFFF, 0),  # duração infinita
    ff.EffectType(ff_condition_effect=cond),
)

# IMPORTANTE: nome do campo deve ser ff_condition_effect (não ff_condition_ef)
eid = device.upload_effect(effect)
device.write(ecodes.EV_FF, eid, 1)  # Ativa

# Atualizar coeficiente em tempo real (mesmo eid):
new_cond = (ff.Condition * 2)(
    ff.Condition(new_sat, new_sat, new_coeff, new_coeff, 0, 0),
    ff.Condition(0, 0, 0, 0, 0, 0),
)
new_effect = ff.Effect(
    ecodes.FF_SPRING, eid, 0,  # reutiliza eid
    ff.Trigger(0, 0), ff.Replay(0xFFFF, 0),
    ff.EffectType(ff_condition_effect=new_cond),
)
device.upload_effect(new_effect)  # Atualiza sem parar
```

### FF_CONSTANT (forças dinâmicas)

Usado apenas para forças calculadas a partir de sensores do RPi:

```python
# intensity: 0-100% (G lateral + yaw do BMI160)
# FF_GAIN já limita globalmente, então level vai direto
level = int(intensity / 100.0 * 32767)

# direction: 0x4000 (esquerda), 0xC000 (direita), 0 (neutro)
effect = ff.Effect(
    ecodes.FF_CONSTANT, constant_eid, ff_direction,
    ff.Trigger(0, 0), ff.Replay(0xFFFF, 0),
    ff.EffectType(ff_constant_effect=ff.Constant(level, ff.Envelope(0, 0, 0, 0))),
)
device.upload_effect(effect)
```

### Ciclo de vida dos efeitos

1. **Inicialização** (`_init_force_feedback()`):
   - Define FF_GAIN baseado no slider Max Force
   - Upload 7 efeitos (spring, damper, friction, inertia, constant, rumble, periodic) com `id=-1`
   - Ativa todos: `write(EV_FF, eid, 1)`
2. **Atualização de sliders**: Re-upload condition effects com mesmo `eid`
3. **Atualização de sensor data**: Re-upload FF_CONSTANT + FF_RUMBLE + FF_PERIODIC + FF_INERTIA
4. **Idle (sem RPi)**: Spring/friction com mínimos, periodic idle (25Hz/3%), inertia base (5%)
5. **Cleanup** (`_stop_force_feedback()`): `write(EV_FF, eid, 0)` + `erase_effect(eid)` para cada um

### Fluxo de dados completo

```
G923 (firmware ~1kHz) — condition effects:
  ├─ FF_SPRING:   kernel lê posição → centering (Sensitivity slider, mín 5%)
  ├─ FF_DAMPER:   kernel lê velocidade → resistência (Damping slider)
  ├─ FF_FRICTION: kernel aplica resistência constante (Friction slider, mín 3%)
  ├─ FF_INERTIA:  kernel lê aceleração angular → peso (auto: velocidade/throttle)
  └─ FF_GAIN:     multiplica todos os 7 efeitos (Max Force slider, default 15%)

BMI160 (RPi, 100Hz) → UDP → Client → ff_calculator.calculate_g_forces_and_ff():
  ├─ FF_CONSTANT: G lateral + yaw → empurra volante (sensitivity × filter EMA)
  ├─ FF_RUMBLE:   |accel_z - 9.81| → strong (impactos) + weak (estrada)
  ├─ FF_PERIODIC: throttle → freq 25-50Hz, magnitude 3-30% (engine RPM)
  └─ FF_INERTIA:  velocidade + throttle → 5-80% (peso dinâmico do volante)

Idle (sem RPi, sem dados):
  ├─ FF_SPRING:   mínimo 5% (peso mecânico do eixo de direção)
  ├─ FF_FRICTION: mínimo 3% (atrito mecânico)
  ├─ FF_INERTIA:  base 5% (peso do volante parado)
  ├─ FF_PERIODIC: 25Hz / 3% (motor em idle)
  └─ FF_CONSTANT/RUMBLE: desligados (sem dados de sensor)

Slider callbacks (imediato):
  ├─ Sensitivity → g923_manager.update_spring(value)
  ├─ Friction    → g923_manager.update_friction(value)
  ├─ Damping     → g923_manager.update_damper(value)
  ├─ Filter      → apenas software (EMA no FF_CONSTANT)
  └─ Max Force   → g923_manager.set_ff_max_percent(value) → FF_GAIN
```

### Seleção inteligente de efeitos por contexto

O calculador (`force_feedback_calc.py`) seleciona automaticamente quais efeitos ativar e com qual intensidade baseado no estado atual do veículo:

| Contexto | FF_CONSTANT | FF_RUMBLE | FF_PERIODIC | FF_INERTIA |
|----------|-------------|-----------|-------------|------------|
| Idle (motor ligado) | 0% | 0% | 25Hz/3% | 5% |
| Acelerando | G lateral | estrada | ↑ freq/mag | ↑ com velocidade |
| Curva | G lat + yaw | estrada | throttle | velocidade |
| Frenagem forte | G frontal | strong ↑ | throttle | mantém |
| Bump/impacto | — | strong ↑↑ | — | — |
| Alta velocidade | normal | estrada | throttle | 50-80% |
