# Encoder de Velocidade nas Rodas - Discussão

Documento para discutir a implementação de sensor de velocidade real no veículo.

## Status Atual

- **Data**: 2025-12-18
- **Status**: Proposta - não implementado

---

## Problema Atual

O sistema atual **não tem velocidade real**. O que existe:

```python
# motor_manager.py - velocidade SIMULADA
"rpm_display": round(self._calculate_efficiency_zone_percentage(self.current_pwm), 0)
```

Isso é apenas uma estimativa baseada no PWM, não na velocidade real das rodas.

**Limitações**:
- Não detecta derrapagem
- Não sabe se o carro está realmente se movendo
- Não considera carga/inclinação
- Telemetria imprecisa

---

## Solução Proposta

Adicionar encoder/sensor de velocidade em pelo menos uma roda (traseira motriz).

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SENSOR DE VELOCIDADE                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Roda Traseira                                                      │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────┐      ┌─────────────┐      ┌─────────────┐             │
│  │  Ímã    │ ───► │ Sensor Hall │ ───► │ GPIO RPi    │             │
│  │ (na roda)│      │  (A3144)    │      │ (interrupt) │             │
│  └─────────┘      └─────────────┘      └─────────────┘             │
│                                               │                     │
│                                               ▼                     │
│                                        Conta pulsos                 │
│                                        Calcula RPM                  │
│                                        Calcula km/h                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Opções de Hardware

### Opção 1: Sensor Hall + Ímã (Recomendada)

| Componente | Modelo | Preço | Quantidade |
|------------|--------|-------|------------|
| Sensor Hall | A3144 / 44E | ~R$3 | 1 |
| Ímã neodímio | 5x3mm cilíndrico | ~R$2 | 1-4 |
| Resistor pull-up | 10kΩ | ~R$0.10 | 1 |

**Total: ~R$6**

**Funcionamento**:
- Ímã colado na roda/eixo
- Sensor Hall detecta passagem do ímã
- 1 pulso por rotação (com 1 ímã)
- 4 pulsos por rotação (com 4 ímãs = mais precisão)

**Prós**:
- Barato e simples
- Robusto (sem contato físico)
- Funciona em qualquer velocidade

**Contras**:
- Baixa resolução com 1 ímã
- Precisa posicionar ímã com cuidado

### Opção 2: Encoder Óptico de Slot

| Componente | Modelo | Preço |
|------------|--------|-------|
| Encoder óptico | HC-020K / LM393 | ~R$12 |
| Disco encoder | 20 slots | Incluso |

**Funcionamento**:
- Disco com furos gira com a roda
- Sensor óptico conta passagens
- 20 pulsos por rotação típico

**Prós**:
- Maior resolução que Hall simples
- Módulo pronto

**Contras**:
- Mais frágil (poeira, sujeira)
- Precisa adaptar disco na roda

### Opção 3: Encoder Magnético de Precisão

**ATENÇÃO**: O motor RC 775 conecta direto ao diferencial (sem redução), então RPM do motor ≈ RPM das rodas.

| Encoder | RPM Máx | Interface | Resolução | Preço | Serve? |
|---------|---------|-----------|-----------|-------|--------|
| AS5600 | 1000 RPM | I2C | 12-bit | ~R$25 | ❌ Não (limite baixo) |
| **AS5047P** | 28000 RPM | SPI | 14-bit | ~R$45 | ✅ Sim |
| AS5048A | 10000 RPM | SPI | 14-bit | ~R$50 | ✅ Sim |
| TLE5012B | 30000 RPM | SPI | 15-bit | ~R$40 | ✅ Sim |

**Para ~6000 RPM do motor sob carga**: AS5047P ou TLE5012B são ideais.

**AS5600 NÃO serve** - limite de 1000 RPM é muito baixo para o motor RC 775.

**Funcionamento**:
- Ímã diametral no eixo
- Sensor lê ângulo absoluto (0-360°)
- Saída SPI (mais rápido que I2C para alta velocidade)

**Prós**:
- Altíssima resolução (14-16 bit)
- Posição absoluta (não só contagem)
- Aguenta alta velocidade

**Contras**:
- Mais caro (~R$45)
- Precisa alinhar bem o ímã
- Interface SPI (não I2C)

---

## Comparativo

| Aspecto | Hall + Ímã | Encoder Óptico | AS5600 |
|---------|------------|----------------|--------|
| Preço | ~R$6 | ~R$12 | ~R$28 |
| Resolução | 1-4 pulsos/rot | 20 pulsos/rot | 4096 pos/rot |
| Robustez | Alta | Média | Alta |
| Complexidade | Baixa | Média | Média |
| Interface | GPIO interrupt | GPIO interrupt | I2C |

**Recomendação**: Começar com **Hall + Ímã** pela simplicidade e custo. Se precisar mais precisão, migrar para AS5600.

---

## Implementação Proposta

### Conexão no Raspberry Pi

```
Sensor Hall A3144:
├── VCC ──────► 3.3V ou 5V
├── GND ──────► GND
└── OUT ──────► GPIO 17 (com pull-up 10kΩ para VCC)
```

### Código: speed_sensor_manager.py

```python
import RPi.GPIO as GPIO
import time
import threading

class SpeedSensorManager:
    def __init__(self, gpio_pin=17, pulses_per_rev=1, wheel_circumference=0.25):
        """
        Args:
            gpio_pin: Pino GPIO do sensor
            pulses_per_rev: Pulsos por rotação da roda (1 ímã = 1, 4 ímãs = 4)
            wheel_circumference: Circunferência da roda em metros
        """
        self.gpio_pin = gpio_pin
        self.pulses_per_rev = pulses_per_rev
        self.wheel_circumference = wheel_circumference  # metros

        self.pulse_count = 0
        self.last_pulse_time = time.time()
        self.current_speed_ms = 0.0
        self.current_rpm = 0.0
        self.total_distance = 0.0

        self.lock = threading.Lock()
        self.running = False

    def start(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(
            self.gpio_pin,
            GPIO.FALLING,
            callback=self._pulse_callback,
            bouncetime=5  # 5ms debounce
        )

        self.running = True
        self.calc_thread = threading.Thread(target=self._calculation_loop)
        self.calc_thread.daemon = True
        self.calc_thread.start()

    def _pulse_callback(self, channel):
        """Chamado a cada pulso do sensor"""
        current_time = time.time()

        with self.lock:
            self.pulse_count += 1

            # Calcula velocidade instantânea
            dt = current_time - self.last_pulse_time
            if dt > 0.001:  # Evita divisão por zero
                # RPM = (pulsos/seg) / pulsos_por_rot * 60
                instant_rpm = (1.0 / dt) / self.pulses_per_rev * 60
                self.current_rpm = instant_rpm

                # Velocidade = RPM * circunferência / 60
                self.current_speed_ms = (instant_rpm * self.wheel_circumference) / 60

                # Distância acumulada
                self.total_distance += self.wheel_circumference / self.pulses_per_rev

            self.last_pulse_time = current_time

    def _calculation_loop(self):
        """Loop para detectar parada (sem pulsos)"""
        while self.running:
            time.sleep(0.1)  # 10Hz

            with self.lock:
                # Se não teve pulso em 500ms, velocidade = 0
                if time.time() - self.last_pulse_time > 0.5:
                    self.current_speed_ms = 0.0
                    self.current_rpm = 0.0

    def get_speed_kmh(self):
        with self.lock:
            return self.current_speed_ms * 3.6

    def get_speed_ms(self):
        with self.lock:
            return self.current_speed_ms

    def get_rpm(self):
        with self.lock:
            return self.current_rpm

    def get_distance_meters(self):
        with self.lock:
            return self.total_distance

    def reset_distance(self):
        with self.lock:
            self.total_distance = 0.0

    def get_sensor_data(self):
        with self.lock:
            return {
                "wheel_speed_kmh": round(self.current_speed_ms * 3.6, 1),
                "wheel_speed_ms": round(self.current_speed_ms, 2),
                "wheel_rpm": round(self.current_rpm, 0),
                "total_distance_m": round(self.total_distance, 2),
                "pulse_count": self.pulse_count,
            }

    def stop(self):
        self.running = False
        GPIO.remove_event_detect(self.gpio_pin)
        GPIO.cleanup(self.gpio_pin)
```

---

## Cálculos

### Fórmulas

```
RPM = (pulsos_por_segundo / pulsos_por_rotação) × 60

Velocidade (m/s) = (RPM × circunferência_roda) / 60

Velocidade (km/h) = Velocidade (m/s) × 3.6

Distância (m) = pulsos_total × (circunferência / pulsos_por_rotação)
```

### Exemplo com Valores Reais

```
Dados do carro:
- Diâmetro roda: 80mm = 0.08m
- Circunferência: π × 0.08 = 0.251m
- Ímãs na roda: 4 (4 pulsos/rotação)

Cenário: 20 pulsos em 1 segundo
- RPM = (20 / 4) × 60 = 300 RPM
- Velocidade = (300 × 0.251) / 60 = 1.26 m/s = 4.5 km/h
```

### Velocidade Máxima Esperada

```
Motor RC 775: 6000-10000 RPM (típico 9000 sob carga)
Roda: 63mm diâmetro → circunferência 0.198m

Velocidade máxima (sem redução):
= (9000 × 0.198) / 60 = 29.7 m/s = 107 km/h

MUITO RÁPIDO! Recomendado usar caixa de redução.
Ver docs/CAIXA_REDUCAO.md para análise completa.
```

---

## Integração com Sistema Existente

### Dados para Telemetria

```json
{
    "wheel_speed_kmh": 25.3,
    "wheel_speed_ms": 7.03,
    "wheel_rpm": 1680,
    "total_distance_m": 152.4,
    "bmi160_accel_x": 0.5,
    "motor_pwm": 65
}
```

### Detecção de Derrapagem

```python
def detect_wheelspin(self, wheel_speed, accel_x):
    """
    Compara velocidade da roda com aceleração do chassi.
    Se roda gira muito mais rápido que aceleração indica = derrapagem
    """
    # Velocidade esperada pela aceleração
    expected_speed = self.last_speed + (accel_x * dt)

    # Diferença entre roda e esperado
    slip_ratio = (wheel_speed - expected_speed) / max(wheel_speed, 0.1)

    if slip_ratio > 0.2:  # 20% de diferença
        return "WHEELSPIN"  # Roda girando mais que deveria
    elif slip_ratio < -0.2:
        return "LOCKUP"  # Roda travada (frenagem)
    else:
        return "NORMAL"
```

### Velocímetro no Console

```python
# No console, exibir velocidade real
speed_label = ttk.Label(frame, text="0 km/h", font=("Consolas", 24))

def update_speed(self, sensor_data):
    speed = sensor_data.get("wheel_speed_kmh", 0)
    self.speed_label.config(text=f"{speed:.0f} km/h")
```

---

## Montagem Física

### Posicionamento Recomendado

```
Vista Traseira do Carro:

    ┌─────────────────────┐
    │      Chassi         │
    └─────────────────────┘
           │     │
    ┌──────┴─────┴──────┐
    │     Eixo Traseiro  │
    └───┬───────────┬───┘
        │           │
   ┌────┴────┐ ┌────┴────┐
   │  Roda   │ │  Roda   │
   │ Esquerda│ │ Direita │
   └────┬────┘ └─────────┘
        │
   ┌────┴────┐
   │  Ímã    │ ◄── Colado na face interna da roda
   └─────────┘
        ▲
   ┌────┴────┐
   │ Sensor  │ ◄── Fixado no chassi, ~3mm de distância
   │  Hall   │
   └─────────┘
```

### Dicas de Montagem

1. **Distância ímã-sensor**: 1-5mm (quanto menor, melhor sinal)
2. **Polaridade do ímã**: Testar qual lado ativa o sensor
3. **Fixação do sensor**: Cola quente ou suporte impresso 3D
4. **Proteção**: Evitar que sujeira bloqueie o sensor
5. **Fios**: Usar fio blindado se possível (evita interferência do motor)

---

## Próximos Passos

1. [ ] Comprar componentes (Hall A3144 + ímãs)
2. [ ] Definir GPIO disponível no RPi
3. [ ] Testar sensor na bancada
4. [ ] Montar na roda traseira
5. [ ] Implementar `speed_sensor_manager.py`
6. [ ] Integrar com `main.py`
7. [ ] Adicionar dados ao pacote UDP
8. [ ] Exibir velocímetro no console
9. [ ] Implementar detecção de derrapagem

---

## Arquivos a Criar/Modificar

### Novos
- `raspberry/speed_sensor_manager.py` - Gerenciador do sensor

### Modificar
- `raspberry/main.py` - Adicionar thread do sensor
- `raspberry/network_manager.py` - Incluir dados no pacote
- `client/sensor_display.py` - Processar novos campos
- `client/console/frames/bmi160.py` - Exibir velocímetro

---

## Histórico

| Data | Mudança |
|------|---------|
| 2025-12-18 | Documento inicial de discussão |
