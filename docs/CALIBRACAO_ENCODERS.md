# Sistema de Calibração de Encoders ESP32

Documento sobre o sistema de calibração dos encoders rotativos do cockpit.

## Status Atual

- **Data**: 2025-12-18
- **Status**: Produção

---

## Visão Geral

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FLUXO DE CALIBRAÇÃO                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Cliente PC                           ESP32 Cockpit                 │
│  ──────────                           ─────────────                 │
│                                                                     │
│  1. Usuário clica                                                   │
│     "Calibrar Acelerador"                                           │
│          │                                                          │
│          ▼                                                          │
│     CAL_START:THROTTLE ────────────► Inicia modo calibração        │
│                                       (remove limites encoder)      │
│          │                                                          │
│          │ ◄─── CAL_THROTTLE:1523 ─── Envia valor bruto (100Hz)    │
│          │ ◄─── CAL_THROTTLE:1524 ───                              │
│          │ ◄─── CAL_THROTTLE:1520 ───                              │
│          ▼                                                          │
│     Interface mostra                                                │
│     valor bruto ao vivo                                             │
│          │                                                          │
│  2. Usuário move encoder                                            │
│     de min a max                                                    │
│          │                                                          │
│          ▼                                                          │
│     Cliente detecta                                                 │
│     min=0, max=2400                                                 │
│          │                                                          │
│  3. Usuário clica "Salvar"                                          │
│          │                                                          │
│          ▼                                                          │
│     CAL_SAVE:THROTTLE:0:2400 ──────► Salva em EEPROM               │
│                                              │                      │
│          │ ◄─── CAL_COMPLETE:THROTTLE ─────  │                      │
│          ▼                                                          │
│     Calibração concluída                                            │
│     (mapeamento ativo)                                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Por que Calibração é Necessária?

### Problema

Encoders rotativos não têm posição absoluta. Ao ligar o ESP32:
- Posição inicial = 0 (arbitrário)
- Não sabe onde está min/max
- Valores variam entre sessões

### Solução

Calibração define:
- **Throttle/Brake**: min e max (unipolar 0-100%)
- **Steering**: esquerda, centro e direita (bipolar -100% a +100%)

---

## Encoders LPD3806-600BM-G5-24C

### Especificações

| Parâmetro | Valor |
|-----------|-------|
| Pulsos/revolução | 600 PPR |
| Resolução angular | 0.6° por pulso |
| Tensão | 5-24V |
| Saída | A/B quadratura |
| Frequência máxima | 20kHz |

### Por que 600 PPR?

```
Alternativas:
- 100 PPR: 3.6° por pulso → grosseiro, impreciso
- 360 PPR: 1.0° por pulso → OK, mas existe 600
- 600 PPR: 0.6° por pulso → precisão ideal
- 1000+ PPR: overkill, mais caro
```

**Trade-off**: Maior PPR = mais interrupções por segundo (CPU).

```
100 RPM @ 600 PPR = 60000 pulsos/minuto = 1000 Hz
→ ESP32 a 240MHz: trivial
```

---

## Leitura por Interrupção

### Por que ISR e não Polling?

| Método | Taxa Máxima | CPU | Decisão |
|--------|-------------|-----|---------|
| Polling (loop) | ~1kHz | 100% | Rejeitado |
| Timer interrupt | ~10kHz | ~50% | Possível |
| **GPIO ISR** | ~100kHz | ~5% | **Escolhido** |

### Implementação

```cpp
volatile long encoder_position = 0;

void IRAM_ATTR encoder_isr() {
    bool clk = digitalRead(PIN_CLK);
    bool dt = digitalRead(PIN_DT);

    if (clk != last_clk) {
        if (dt != clk) {
            encoder_position++;  // Horário
        } else {
            encoder_position--;  // Anti-horário
        }
        last_clk = clk;
    }
}

void setup() {
    attachInterrupt(digitalPinToInterrupt(PIN_CLK), encoder_isr, CHANGE);
}
```

### Por que só CLK e não DT também?

```
Com interrupção em CLK apenas:
  600 pulsos × 2 edges = 1200 ISR/revolução

Com interrupção em CLK e DT:
  600 × 2 × 2 = 2400 ISR/revolução (dobro, desnecessário)
```

**Leitura de DT dentro da ISR** é suficiente para determinar direção.

---

## Estrutura EEPROM

### Layout

```
Endereço 0x00: Throttle Calibration (16 bytes)
Endereço 0x10: Brake Calibration (16 bytes)
Endereço 0x20: Steering Calibration (16 bytes)
```

### Estrutura de Dados

```cpp
struct CalibrationData {
    uint16_t magic;        // 0xCAFE = dados válidos
    int32_t min_value;     // Posição mínima
    int32_t max_value;     // Posição máxima
    int32_t center_value;  // Centro (steering only)
    uint16_t checksum;     // XOR de todos os bytes
};
// Total: 16 bytes
```

### Por que Magic Number?

**Problema**: EEPROM virgem contém 0xFF em todos os bytes.

**Solução**:
```cpp
if (data.magic != 0xCAFE) {
    // EEPROM não calibrada, usar defaults
    return false;
}
```

### Checksum XOR

```cpp
uint16_t calculate_checksum(CalibrationData* data) {
    uint8_t* bytes = (uint8_t*)data;
    uint16_t checksum = 0;

    // XOR de todos os bytes exceto o próprio checksum
    for (int i = 0; i < sizeof(CalibrationData) - 2; i++) {
        checksum ^= bytes[i];
    }
    return checksum;
}
```

**Proteção**: Detecta corrupção por falha de energia ou bug.

---

## Mapeamento Unipolar vs Bipolar

### Unipolar (Throttle/Brake)

```
Input:  raw_value (qualquer int32)
Output: 0-100%

Fórmula:
  percent = (raw - min) / (max - min) × 100
  percent = constrain(percent, 0, 100)
```

**Exemplo**:
```
Calibrado: min=100, max=2500
Raw=100  → (100-100)/(2500-100) × 100 = 0%
Raw=1300 → (1300-100)/(2500-100) × 100 = 50%
Raw=2500 → (2500-100)/(2500-100) × 100 = 100%
```

### Bipolar (Steering)

```
Input:  raw_value (qualquer int32)
Output: -100% a +100%

Fórmula:
  Se raw < center:
    percent = (raw - center) / (center - left) × 100
  Se raw >= center:
    percent = (raw - center) / (right - center) × 100
  percent = constrain(percent, -100, 100)
```

**Exemplo**:
```
Calibrado: left=0, center=1200, right=2400
Raw=0    → (0-1200)/(1200-0) × 100 = -100% (esquerda)
Raw=1200 → (1200-1200)/X × 100 = 0% (centro)
Raw=2400 → (2400-1200)/(2400-1200) × 100 = +100% (direita)
```

---

## Protocolo Serial

### Comandos do Cliente → ESP32

| Comando | Descrição |
|---------|-----------|
| `CAL_START:THROTTLE` | Inicia calibração do acelerador |
| `CAL_START:BRAKE` | Inicia calibração do freio |
| `CAL_START:STEERING` | Inicia calibração da direção |
| `CAL_SAVE:THROTTLE:min:max` | Salva calibração unipolar |
| `CAL_SAVE:STEERING:left:center:right` | Salva calibração bipolar |

### Respostas ESP32 → Cliente

| Resposta | Descrição |
|----------|-----------|
| `CAL_THROTTLE:1523` | Valor bruto atual (100Hz) |
| `CAL_BRAKE:820` | Valor bruto atual |
| `CAL_STEERING:-450` | Valor bruto atual |
| `CAL_COMPLETE:THROTTLE` | Calibração salva com sucesso |
| `CAL_ERROR:THROTTLE` | Erro ao salvar (min >= max) |

---

## Interface de Calibração

### Fluxo de UI (Tkinter)

```python
class CalibrationFrame:
    def start_calibration(self, component):
        # 1. Desabilita botões
        self.disable_buttons()

        # 2. Mostra instruções
        self.show_instructions(f"Mova o {component} de min a max")

        # 3. Envia comando
        self.serial.send(f"CAL_START:{component}")

        # 4. Ativa display de valor bruto
        self.raw_display.config(state="normal")

    def on_raw_value(self, component, value):
        # Atualiza display
        self.raw_value_label.config(text=f"Valor: {value}")

        # Auto-detecta min/max
        self.min_value = min(self.min_value, value)
        self.max_value = max(self.max_value, value)

    def save_calibration(self):
        # Valida
        if self.max_value <= self.min_value:
            self.show_error("Range inválido")
            return

        # Envia
        if self.component == "STEERING":
            cmd = f"CAL_SAVE:STEERING:{self.left}:{self.center}:{self.right}"
        else:
            cmd = f"CAL_SAVE:{self.component}:{self.min_value}:{self.max_value}"

        self.serial.send(cmd)
```

### Persistência Local

```python
# calibration_manager.py
def save_to_file(self):
    data = {
        "throttle": {"min": self.throttle_min, "max": self.throttle_max},
        "brake": {"min": self.brake_min, "max": self.brake_max},
        "steering": {"left": self.steer_left, "center": self.steer_center, "right": self.steer_right},
        "timestamp": datetime.now().isoformat()
    }
    with open("encoder_calibration.json", "w") as f:
        json.dump(data, f, indent=2)
```

---

## Pinagem ESP32

### Conexões dos Encoders

| Encoder | CLK GPIO | DT GPIO | Notas |
|---------|----------|---------|-------|
| Throttle | 25 | 26 | **Pinos invertidos** |
| Brake | 27 | 14 | Ordem original |
| Steering | 12 | 13 | **Pinos invertidos** |

### Por que pinos invertidos?

**Descoberto durante debug**: Direção do encoder era oposta ao esperado.

**Solução simples**: Inverter CLK↔DT na configuração (software) em vez de refazer fiação.

```cpp
// throttle_manager.cpp
#define PIN_CLK 25  // Fio branco (originalmente DT)
#define PIN_DT  26  // Fio verde (originalmente CLK)
```

---

## Tratamento de Erros

### Validações no ESP32

```cpp
bool save_calibration(int32_t min_val, int32_t max_val) {
    // 1. Range válido
    if (min_val >= max_val) {
        Serial.println("CAL_ERROR:RANGE");
        return false;
    }

    // 2. Range razoável (não muito pequeno)
    if ((max_val - min_val) < 100) {
        Serial.println("CAL_ERROR:RANGE_TOO_SMALL");
        return false;
    }

    // 3. Salva com checksum
    CalibrationData data;
    data.magic = 0xCAFE;
    data.min_value = min_val;
    data.max_value = max_val;
    data.checksum = calculate_checksum(&data);

    EEPROM.put(address, data);
    EEPROM.commit();

    Serial.println("CAL_COMPLETE:OK");
    return true;
}
```

### Recuperação de Corrupção

```cpp
bool load_calibration() {
    CalibrationData data;
    EEPROM.get(address, data);

    // Verifica magic
    if (data.magic != 0xCAFE) {
        return use_defaults();
    }

    // Verifica checksum
    if (data.checksum != calculate_checksum(&data)) {
        return use_defaults();
    }

    // Dados válidos
    min_value = data.min_value;
    max_value = data.max_value;
    return true;
}
```

---

## Arquivos Relacionados

### ESP32
- `esp32/encoder_calibration.h/cpp` - Classe genérica de calibração
- `esp32/throttle_manager.h/cpp` - Gerenciador do acelerador
- `esp32/brake_manager.h/cpp` - Gerenciador do freio
- `esp32/steering_manager.h/cpp` - Gerenciador da direção
- `esp32/esp32.ino` - Processamento de comandos CAL_*

### Cliente
- `client/calibration_manager.py` - Lógica de calibração
- `client/slider_controller.py` - UI de calibração
- `client/serial_receiver_manager.py` - Comunicação serial

---

## Histórico de Mudanças

| Data | Mudança |
|------|---------|
| 2025-12-17 | Implementação inicial |
| 2025-12-17 | Adicionado checksum EEPROM |
| 2025-12-17 | Suporte bipolar para steering |
| 2025-12-18 | Documentação completa |
