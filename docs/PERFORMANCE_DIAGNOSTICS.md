# Diagnóstico de Performance — Sistema F1 Teleoperado

## Visão Geral

Este documento descreve o sistema de instrumentação de performance implementado para medir latências, jitter e gargalos em todo o pipeline de dados do sistema F1 teleoperado.

## Pipeline End-to-End

```
[RPi] BMI160 lê I2C (1.2ms)
  ↓
[RPi] Consolida JSON + envia UDP (0.3ms)
  ↓
[Rede] WiFi 2.4GHz RPi→Client (~35ms)  ← gargalo principal
  ↓
[Client] Recebe UDP + JSON decode (0.1ms)
  ↓
[Client] Queue drain + cálculos + FF (0.2ms)
  ↓
[Client] GUI update Tkinter (1.7ms)
─────────────────────────────────────────
TOTAL end-to-end: ~38ms
```

## Evolução da Instrumentação

### Fase 1 — Diagnóstico Inicial (warn > 50ms)

O `_sensor_tx_thread_loop` do RPi já media tempos internos, mas apenas emitia warnings no terminal quando ultrapassava 50ms. Nenhum dado era salvo ou enviado ao client.

### Fase 2 — Timings no Pacote de Sensores (RPi)

Adicionamos campos `timing_*` ao pacote JSON consolidado enviado ao client:

| Campo | O que mede |
|-------|-----------|
| `timing_bmi160_read_ms` | Leitura I2C do sensor BMI160 |
| `timing_power_ms` | Leitura USB do monitor de energia (Pro Micro + INA219) |
| `timing_lock_ms` | Lock para copiar dados entre threads |
| `timing_status_ms` | Coleta de status dos atuadores (motor, freio, direção) |
| `timing_state_cmd_ms` | Tempo para aplicar último comando STATE (I2C servos) |
| `timing_total_pre_send_ms` | Tempo total antes do envio UDP |

### Fase 3 — Timings do Client

Instrumentamos o loop de processamento de sensores (100Hz) e a GUI (10Hz):

| Campo | O que mede |
|-------|-----------|
| `client_timing_json_decode_ms` | Tempo de parse do JSON recebido via UDP |
| `client_timing_queue_ms` | Drain da fila de sensores |
| `client_timing_calc_ms` | Cálculos de velocidade + forças G + force feedback |
| `client_timing_ff_ms` | Envio de comandos force feedback via evdev |
| `client_timing_writeback_ms` | Writeback dos dados calculados ao sensor_display |
| `client_timing_total_ms` | Tempo total do loop de 100Hz |
| `client_timing_gui_ms` | Tempo do `update_sensor_data` (widgets Tkinter) |
| `client_timing_gui_total_ms` | Tempo total do `process_queues` (10Hz) |

### Fase 4 — Latência de Rede

Adicionamos medição de latência one-way RPi→Client usando timestamps sincronizados via NTP:

| Campo | O que mede |
|-------|-----------|
| `net_latency_ms` | `client_recv_time - rpi_send_timestamp` (latência real com NTP) |
| `client_recv_timestamp` | Momento exato de recepção no client (para análise offline) |

**Requisito**: ambos os dispositivos devem estar sincronizados via NTP:
```bash
# Verificar sincronização
timedatectl status  # "System clock synchronized: yes"

# Forçar sincronização
sudo timedatectl set-ntp true
```

### Fase 5 — Auto-Save Dinâmico

O `sensor_display.update_history()` foi alterado de uma lista fixa de ~100 campos para salvar **tudo** que chega dinamicamente. Qualquer campo novo do RPi (ex: novos `timing_*`) é incluído automaticamente no pickle sem alteração de código.

### Fase 6 — Raw Buffer (todos os pacotes)

O `process_queue` do client faz drain (descarta pacotes intermediários, usa só o último) para manter a GUI em tempo real. Para não perder dados no pickle, adicionamos um `raw_buffer` que armazena **100% dos pacotes recebidos** sem perda. O auto-save exporta o raw_buffer.

## Como Coletar Dados

### 1. Executar sessão

```bash
# RPi
cd raspberry && python3 main.py

# Client
cd client && python3 main.py
```

O auto-save exporta a cada 20 segundos para `client/exports/auto/`:
- `sensors_YYYYMMDD_HHMMSS.pkl` — dados de sensores + timings
- `telemetry_YYYYMMDD_HHMMSS.pkl` — dados dos gráficos
- `logs_YYYYMMDD_HHMMSS.txt` — logs do console

### 2. Analisar sessão

```bash
# Combina TODOS os arquivos e exibe estatísticas + gráficos
python scripts/analyze_session.py

# Apenas os mais recentes
python scripts/analyze_session.py --latest

# Salva gráficos como PNG
python scripts/analyze_session.py --save-plots

# Exporta relatório HTML
python scripts/analyze_session.py --export report.html
```

### 3. Análise manual com Python

```python
import pickle
import numpy as np

with open("client/exports/auto/sensors_XXXXXXXX_XXXXXX.pkl", "rb") as f:
    data = pickle.load(f)

# Listar todas as chaves disponíveis
print(sorted(data.keys()))

# Latência de rede
lat = np.array(data["net_latency_ms"])
print(f"Latência média: {np.mean(lat):.1f}ms")
print(f"P95: {np.percentile(lat, 95):.1f}ms")
print(f"Jitter: {np.std(lat):.1f}ms")

# Timing do RPi
total = np.array(data["timing_total_pre_send_ms"])
print(f"RPi total médio: {np.mean(total):.2f}ms")

# Timing do Client
client = np.array([v for v in data["client_timing_total_ms"] if v is not None and v > 0])
print(f"Client total médio: {np.mean(client):.2f}ms")
```

## Resultados de Referência (WiFi 2.4GHz)

Sessão de 20 segundos, ~1400 pacotes:

### Timing RPi

| Métrica | Média | P50 | P95 | Máx |
|---------|-------|-----|-----|-----|
| BMI160 I2C read | 1.19ms | 1.07ms | 1.74ms | 3.57ms |
| Power USB read | 1.59ms | 1.22ms | 3.32ms | 4.74ms |
| Lock | 0.03ms | 0.03ms | 0.04ms | 0.36ms |
| Status collect | 0.17ms | 0.17ms | 0.21ms | 1.38ms |
| STATE cmd (I2C) | 0.12ms | 0.08ms | 0.51ms | 2.09ms |
| **Total pre-send** | **0.26ms** | 0.25ms | 0.32ms | 1.47ms |

**Zero pacotes > 50ms.**

### Timing Client

| Métrica | Média | P50 | P95 | Máx |
|---------|-------|-----|-----|-----|
| JSON decode | 0.10ms | 0.10ms | 0.12ms | 0.17ms |
| Queue drain | 0.15ms | 0.14ms | 0.19ms | 0.85ms |
| Cálculos (vel+G+FF) | 0.04ms | 0.04ms | 0.06ms | 0.61ms |
| Force feedback evdev | 0.01ms | 0.01ms | 0.02ms | 0.03ms |
| Writeback | 0.02ms | 0.01ms | 0.03ms | 0.07ms |
| **Total loop 100Hz** | **0.20ms** | 0.19ms | 0.25ms | 0.94ms |
| GUI update (10Hz) | 1.68ms | 1.60ms | 2.43ms | 4.46ms |

**Zero loops > 10ms.** O loop de 100Hz usa apenas 2% do budget de 10ms.

### Latência de Rede (WiFi 2.4GHz, NTP sync)

| Métrica | Valor |
|---------|-------|
| Média | 35.52ms |
| P50 | 34.39ms |
| P95 | 82.66ms |
| P99 | 90.01ms |
| Máx | 104.28ms |
| Jitter (std) | 30.17ms |
| Taxa efetiva | ~61Hz |

### Conclusão

O software (RPi + Client) contribui com apenas **~3ms** da latência total. O gargalo é a rede WiFi 2.4GHz (~35ms). Migrar para WiFi 5GHz deve reduzir a latência total para ~10-15ms.

## Logger com Timestamps

Ambos os loggers (RPi e Client) incluem timestamps automáticos `[HH:MM:SS]` em todas as mensagens para correlação temporal entre os dispositivos.

## Arquivos Relevantes

- `raspberry/main.py` — instrumentação do RPi (threads de sensores, comandos, TX)
- `raspberry/managers/logger.py` — logger do RPi com timestamp
- `client/network_client.py` — medição de latência de rede + JSON decode
- `client/console/main.py` — timings do sensor loop (100Hz) e GUI (10Hz)
- `client/sensor_display.py` — update_history dinâmico + raw_buffer
- `client/console/logic/auto_save.py` — auto-save periódico (20s)
- `client/simple_logger.py` — logger do client com timestamp
- `scripts/analyze_session.py` — análise offline com tabelas + gráficos
