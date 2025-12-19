# Interface Gráfica e Sistema de Telemetria

Documento sobre as decisões técnicas da interface Tkinter e sistema de auto-save.

## Status Atual

- **Data**: 2025-12-18
- **Status**: Produção

---

## Arquitetura da Interface

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CONSOLE INTERFACE (Tkinter)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────┐  ┌─────────────────────────┐          │
│  │    COLUNA ESQUERDA      │  │    COLUNA DIREITA       │          │
│  ├─────────────────────────┤  ├─────────────────────────┤          │
│  │ ┌─────────────────────┐ │  │ ┌─────────────────────┐ │          │
│  │ │  Connection Status  │ │  │ │    Video Frame      │ │          │
│  │ │  (UDP, FPS, pkts)   │ │  │ │  (H.264 + filtros)  │ │          │
│  │ └─────────────────────┘ │  │ └─────────────────────┘ │          │
│  │ ┌─────────────────────┐ │  │ ┌─────────────────────┐ │          │
│  │ │  Instrument Panel   │ │  │ │  Slider Controls    │ │          │
│  │ │  (RPM, gear, speed) │ │  │ │  (throttle, brake,  │ │          │
│  │ └─────────────────────┘ │  │ │   steering)         │ │          │
│  │ ┌─────────────────────┐ │  │ └─────────────────────┘ │          │
│  │ │  BMI160 Telemetry   │ │  │ ┌─────────────────────┐ │          │
│  │ │  (accel, gyro, g)   │ │  │ │  Force Feedback     │ │          │
│  │ └─────────────────────┘ │  │ │  (sliders ajuste)   │ │          │
│  │ ┌─────────────────────┐ │  │ └─────────────────────┘ │          │
│  │ │  Telemetry Plotter  │ │  │ ┌─────────────────────┐ │          │
│  │ │  (gráficos F1)      │ │  │ │  Keyboard Controls  │ │          │
│  │ └─────────────────────┘ │  │ │  (M/N gear shift)   │ │          │
│  │ ┌─────────────────────┐ │  │ └─────────────────────┘ │          │
│  │ │    Log Console      │ │  │                         │          │
│  │ │  (5000 linhas max)  │ │  │                         │          │
│  │ └─────────────────────┘ │  │                         │          │
│  └─────────────────────────┘  └─────────────────────────┘          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Por que Tkinter?

### Alternativas Consideradas

| Framework | Prós | Contras | Decisão |
|-----------|------|---------|---------|
| **Tkinter** | Nativo Python, simples | UI datada | **Escolhido** |
| PyQt | Moderno, poderoso | Licença, complexo | Rejeitado |
| Dear ImGui | Rápido, gamer | Requer OpenGL | Rejeitado |
| Web (Flask) | Moderno | Latência, complexo | Rejeitado |

### Justificativa

1. **Zero dependências**: Já vem com Python
2. **Cross-platform**: Linux, Windows, Mac
3. **Suficiente**: Não é app comercial, é TCC
4. **Integração fácil**: Canvas para vídeo, widgets nativos

---

## Thread Safety com Tkinter

### Problema

Tkinter **não é thread-safe**. Apenas a thread principal pode modificar widgets.

### Solução: Filas + root.after()

```python
class ConsoleInterface:
    def __init__(self):
        self.log_queue = queue.Queue()
        self.sensor_queue = queue.Queue()
        self.video_queue = queue.Queue()

        # Processa filas a cada 100ms
        self.root.after(100, self._process_queues)

    def _process_queues(self):
        # Processa logs
        while not self.log_queue.empty():
            level, message = self.log_queue.get_nowait()
            self._append_log(level, message)

        # Processa sensores
        while not self.sensor_queue.empty():
            data = self.sensor_queue.get_nowait()
            self._update_sensor_display(data)

        # Agenda próxima execução
        self.root.after(100, self._process_queues)
```

### Por que 100ms?

```
Taxa de atualização UI: 10Hz
Taxa de sensores: 100Hz
→ Buffer 10 leituras por update = suave
```

---

## Painel de Instrumentos

### Widgets Simulados

```python
# RPM (canvas arc)
def draw_rpm_gauge(self, rpm_percent):
    # Arco de 0° a 270° (escala de RPM)
    angle = rpm_percent * 270 / 100
    self.canvas.create_arc(
        10, 10, 150, 150,
        start=135, extent=-angle,
        fill="green" if rpm_percent < 80 else "red"
    )

# Gear indicator (label)
self.gear_label = ttk.Label(frame, text="N", font=("Consolas", 48))

# Speed (label + progress bar)
self.speed_label = ttk.Label(frame, text="0 km/h")
self.speed_bar = ttk.Progressbar(frame, maximum=200)
```

### Por que não gauges reais (matplotlib, etc)?

**Overhead**: Matplotlib é pesado para 10Hz de update.

**Solução**: Canvas Tkinter com formas simples (arcos, retângulos).

---

## Telemetria BMI160

### Campos Exibidos

```
┌─────────────────────────────────────────┐
│           BMI160 TELEMETRY              │
├─────────────────────────────────────────┤
│ Accel X:  -0.12 m/s² (raw: -20)        │
│ Accel Y:   0.05 m/s² (raw: 8)          │
│ Accel Z:   9.78 m/s² (raw: 16234)      │
├─────────────────────────────────────────┤
│ Gyro X:    0.50 °/s                     │
│ Gyro Y:   -0.20 °/s                     │
│ Gyro Z:    1.10 °/s                     │
├─────────────────────────────────────────┤
│ G-Force Lateral:      0.013 g          │
│ G-Force Longitudinal: -0.012 g         │
│ G-Force Total:        1.003 g          │
├─────────────────────────────────────────┤
│ Temperature:  28.5 °C                   │
│ Quality:      98%                       │
└─────────────────────────────────────────┘
```

### Atualização via StringVar

```python
# Variáveis vinculadas
self.accel_x_var = tk.StringVar(value="0.00")
self.gyro_z_var = tk.StringVar(value="0.00")

# Labels auto-atualizáveis
ttk.Label(frame, textvariable=self.accel_x_var)

# Update (thread-safe via queue)
def update_telemetry(self, data):
    self.accel_x_var.set(f"{data['accel_x']:.2f}")
    self.gyro_z_var.set(f"{data['gyro_z']:.2f}")
```

---

## Log Console

### Implementação

```python
class LogConsole:
    MAX_LINES = 5000  # Limite de memória

    def __init__(self, parent):
        self.text = tk.Text(parent, height=20, state="disabled")
        self.text.tag_configure("ERROR", foreground="red")
        self.text.tag_configure("WARN", foreground="orange")
        self.text.tag_configure("INFO", foreground="white")
        self.text.tag_configure("DEBUG", foreground="gray")

    def append(self, level, message):
        self.text.config(state="normal")
        self.text.insert("end", f"[{level}] {message}\n", level)
        self.text.config(state="disabled")
        self.text.see("end")  # Auto-scroll

        # Limita linhas
        lines = int(self.text.index("end-1c").split(".")[0])
        if lines > self.MAX_LINES:
            self.text.config(state="normal")
            self.text.delete("1.0", f"{lines - self.MAX_LINES}.0")
            self.text.config(state="disabled")
```

### Por que 5000 linhas?

```
100Hz × 60s = 6000 mensagens/minuto (se todas logadas)
5000 linhas ≈ 50 segundos de buffer
→ Suficiente para debug, não estoura memória
```

---

## Sistema de Auto-Save

### Fluxo

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AUTO-SAVE (a cada 20s)                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Timer 20s ──► Verifica dados novos                                │
│                     │                                               │
│                     ├── Logs >= 100 linhas?                         │
│                     │       └── Sim ──► logs_YYYYMMDD_HHMMSS.txt   │
│                     │                                               │
│                     ├── Sensores >= 1000 leituras?                  │
│                     │       └── Sim ──► sensors_YYYYMMDD_HHMMSS.pkl│
│                     │                                               │
│                     └── Telemetria >= 100 pontos?                   │
│                             └── Sim ──► telemetry_YYYYMMDD_HHMMSS.pkl│
│                     │                                               │
│                     └── Limpa buffers após salvar                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Por que 20 segundos?

| Intervalo | Arquivos/hora | Tamanho/hora | Decisão |
|-----------|---------------|--------------|---------|
| 5s | 720 | ~100MB | Muito |
| 10s | 360 | ~50MB | Razoável |
| **20s** | 180 | ~25MB | **Escolhido** |
| 60s | 60 | ~8MB | Perda se crash |

### Por que Pickle?

| Formato | Velocidade | Tamanho | Legível | Decisão |
|---------|------------|---------|---------|---------|
| CSV | Lento | Grande | Sim | Rejeitado |
| JSON | Médio | Médio | Sim | Alternativa |
| **Pickle** | Rápido (5-10x) | Pequeno | Não | **Escolhido** |

### Leitura de Arquivos Pickle

```python
import pickle

with open("sensors_20241216_143000.pkl", "rb") as f:
    data = pickle.load(f)

# data é dict com listas
print(data.keys())
# ['accel_x', 'accel_y', 'accel_z', 'gyro_x', 'gyro_y', 'gyro_z', ...]

print(len(data['accel_x']))
# 2000 (20s × 100Hz)
```

---

## Telemetry Plotter

### Gráficos Estilo F1

```python
class TelemetryPlotter:
    def __init__(self, parent):
        self.fig, self.axes = plt.subplots(3, 1, figsize=(6, 4))
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)

        # Gráfico 1: G-forces lateral/longitudinal
        self.axes[0].set_ylabel("G-Force")
        self.axes[0].set_ylim(-2, 2)

        # Gráfico 2: Throttle/Brake
        self.axes[1].set_ylabel("Pedal %")
        self.axes[1].set_ylim(0, 100)

        # Gráfico 3: Steering
        self.axes[2].set_ylabel("Steering")
        self.axes[2].set_ylim(-100, 100)

    def update(self, data_history):
        # Últimos 10 segundos (1000 pontos @ 100Hz)
        x = range(len(data_history['g_lateral'][-1000:]))

        self.lines['g_lateral'].set_data(x, data_history['g_lateral'][-1000:])
        self.lines['g_long'].set_data(x, data_history['g_long'][-1000:])

        self.canvas.draw_idle()
```

### Por que Matplotlib Embedding?

**Alternativa**: Gráficos com Canvas Tkinter.
- Simples, mas limitado
- Sem zoom, pan, export

**Escolhido**: Matplotlib em FigureCanvasTkAgg.
- Gráficos profissionais
- Interatividade (zoom, pan)
- Export PNG/SVG

---

## Controles de Slider

### Implementação

```python
class SliderControls:
    def __init__(self, parent, send_callback):
        self.send = send_callback

        # Throttle (vertical, 0-100)
        self.throttle = ttk.Scale(
            parent, from_=100, to=0,  # Invertido para visual
            orient="vertical",
            command=self._on_throttle
        )

        # Brake (vertical, 0-100)
        self.brake = ttk.Scale(
            parent, from_=100, to=0,
            orient="vertical",
            command=self._on_brake
        )

        # Steering (horizontal, -100 a +100)
        self.steering = ttk.Scale(
            parent, from_=-100, to=100,
            orient="horizontal",
            command=self._on_steering
        )

    def _on_throttle(self, value):
        value = int(float(value))
        if abs(value - self.last_throttle) >= 1:  # Threshold
            self.send(f"CONTROL:THROTTLE:{value}")
            self.last_throttle = value
```

### Sincronização com ESP32

Quando ESP32 envia valor, slider atualiza:

```python
def on_serial_value(self, component, value):
    if component == "THROTTLE":
        self.throttle.set(value)  # Atualiza visual
    elif component == "STEERING":
        self.steering.set(value)
```

---

## Shutdown Limpo

### Problema: Tcl_AsyncDelete

```
Tcl_AsyncDelete: async handler deleted by the wrong thread
```

**Causa**: Tkinter destruído enquanto threads ainda acessam widgets.

### Solução

```python
def shutdown(self):
    # 1. Sinaliza threads para parar
    self.running = False

    # 2. Aguarda threads
    for thread in self.threads:
        thread.join(timeout=2.0)

    # 3. Limpa referências Tkinter
    self.video_label = None
    self.log_text = None

    # 4. Força garbage collection
    gc.collect()
    gc.collect()
    gc.collect()

    # 5. Destrói root
    self.root.destroy()

    # 6. Exit forçado
    os._exit(0)
```

### Por que os._exit(0)?

`sys.exit()` pode travar se threads ainda rodando.
`os._exit(0)` termina imediatamente (bypass cleanup Python).

**Trade-off aceito**: Pode deixar recursos não liberados, mas evita hang.

---

## Arquivos Relacionados

### Cliente
- `client/console/main.py` - Interface principal
- `client/console/frames/*.py` - Widgets modulares
- `client/console/logic/auto_save.py` - Sistema auto-save
- `client/console/utils/simple_logger.py` - Logger para UI

### Exports
- `exports/auto/` - Diretório de auto-save
- `exports/manual/` - Exports manuais do usuário

---

## Histórico de Mudanças

| Data | Mudança |
|------|---------|
| 2025-12-17 | Implementação inicial |
| 2025-12-17 | Adicionado auto-save 20s |
| 2025-12-17 | Fix Tcl_AsyncDelete |
| 2025-12-17 | Telemetry plotter integrado |
| 2025-12-18 | Documentação completa |
