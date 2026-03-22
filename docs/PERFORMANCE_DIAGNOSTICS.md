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

### Fase 6 — Raw Buffer (todos os pacotes, com limite)

O `process_queue` do client faz drain (descarta pacotes intermediários, usa só o último) para manter a GUI em tempo real. Para não perder dados no pickle, adicionamos um `raw_buffer` que armazena **100% dos pacotes recebidos** sem perda. O auto-save exporta o raw_buffer.

O raw_buffer é limitado a **12.000 rows** (~2 minutos a 100Hz) para evitar memory leak
em sessões longas. Quando excede o limite, as primeiras 2.000 entries são descartadas.
O `inject_client_timings` que insere timings do client no raw_buffer é protegido por
`data_lock` para thread-safety.

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

Sessão de 20 segundos, 1779 pacotes raw (sem perda por drain), ~84Hz efetivo.

### Timing RPi

| Métrica | Média | P50 | P95 | P99 | Máx |
|---------|-------|-----|-----|-----|-----|
| BMI160 I2C read | 1.20ms | 1.08ms | 1.79ms | 2.32ms | 3.21ms |
| Power USB read | 1.68ms | 1.25ms | 3.47ms | 5.52ms | 5.78ms |
| Lock (entre threads) | 0.03ms | 0.03ms | 0.04ms | 0.05ms | 0.29ms |
| Status collect | 0.18ms | 0.17ms | 0.21ms | 0.43ms | 1.03ms |
| STATE cmd (I2C servos) | 0.22ms | 0.08ms | 0.83ms | 1.21ms | 2.57ms |
| **Total pre-send** | **0.26ms** | 0.25ms | 0.32ms | 0.53ms | 1.13ms |

**Zero pacotes > 50ms.** O RPi processa e envia em menos de 1.2ms em 99% dos casos.

### Timing Client

| Métrica | Média | P50 | P95 | P99 | Máx |
|---------|-------|-----|-----|-----|-----|
| JSON decode | 0.08ms | 0.09ms | 0.11ms | 0.12ms | 0.14ms |
| Queue drain | 0.16ms | 0.16ms | 0.16ms | 0.16ms | 0.16ms |
| Cálculos (vel+G+FF) | 0.03ms | 0.03ms | 0.03ms | 0.03ms | 0.03ms |
| Force feedback evdev | 0.01ms | 0.01ms | 0.02ms | 0.03ms | 0.03ms |
| Writeback | 0.02ms | 0.01ms | 0.03ms | 0.06ms | 0.07ms |
| **Total loop 100Hz** | **0.20ms** | 0.20ms | 0.20ms | 0.20ms | 0.20ms |
| GUI update (10Hz) | 1.68ms | 1.60ms | 2.43ms | 3.21ms | 4.46ms |

**Zero loops > 10ms.** O loop de 100Hz usa apenas 2% do budget de 10ms.

### Latência de Rede (WiFi 2.4GHz, NTP sync)

| Métrica | Valor |
|---------|-------|
| Média | 45.37ms |
| P50 | 45.44ms |
| P95 | 91.38ms |
| P99 | 95.54ms |
| Máx | 188.17ms |
| Mín | -6.56ms |
| Jitter (std) | 29.91ms |
| Taxa efetiva | ~84Hz |

Nota: valores negativos mínimos indicam pequeno residual de clock skew entre RPi e Client (~6ms).

### Resumo End-to-End

| Etapa | Latência | % do Total |
|-------|----------|-----------|
| RPi (sensores + consolidação + envio) | 0.26ms | 0.6% |
| Rede WiFi 2.4GHz | ~45ms | **97.8%** |
| Client (decode + cálculos + FF) | 0.20ms | 0.4% |
| Client GUI (10Hz) | 1.68ms | 3.7% |
| **Total end-to-end** | **~46ms** | 100% |

### Conclusão

O software (RPi + Client) contribui com apenas **~2ms** da latência total de ~46ms. O gargalo absoluto é a **rede WiFi 2.4GHz** que representa ~98% da latência. Migrar para WiFi 5GHz deve reduzir a latência de rede para ~5-15ms, resultando em latência total de ~7-17ms.

O sistema captura **100% dos pacotes** (1779 em 20s, ~84Hz) sem perda graças ao raw_buffer que armazena todos os pacotes antes do drain (limitado a 12.000 rows para evitar memory leak). O loop de processamento de 100Hz usa apenas 2% do budget disponível (0.20ms de 10ms).

Os loops TX do RPi e client usam timing compensado (`next_tick` pattern) para manter a taxa real precisa. Sem compensação, o `time.sleep(interval)` simples causava drift de ~15-20% (ex: 85Hz em vez de 100Hz).

## Raw Buffer vs Drain

O client implementa duas estratégias complementares:

- **Drain (tempo real)**: o `process_queue()` descarta pacotes intermediários e processa apenas o mais recente. Garante que a GUI e o force feedback sempre usem o dado mais atual, sem atraso por acumulação.

- **Raw buffer (análise)**: o `raw_buffer` armazena 100% dos pacotes recebidos antes do drain. É exportado no auto-save (pickle) para análise offline completa com resolução máxima (~84Hz).

Antes do raw_buffer, o pickle salvava apenas ~1400 amostras (pós-drain, ~61Hz). Agora salva ~1779 amostras (~84Hz) — 27% mais dados sem impacto na performance em tempo real.

## Logger com Timestamps

Ambos os loggers (RPi e Client) incluem timestamps automáticos `[HH:MM:SS]` em todas as mensagens para correlação temporal entre os dispositivos.

## Arquivos Relevantes

| Arquivo | Função |
|---------|--------|
| `raspberry/main.py` | Instrumentação do RPi (threads de sensores, comandos, TX) |
| `raspberry/managers/logger.py` | Logger do RPi com timestamp automático |
| `client/network_client.py` | Medição de latência de rede + JSON decode |
| `client/console/main.py` | Timings do sensor loop (100Hz) e GUI (10Hz) |
| `client/sensor_display.py` | update_history dinâmico + raw_buffer + inject_client_timings |
| `client/console/logic/auto_save.py` | Auto-save periódico (20s) exporta raw_buffer |
| `client/simple_logger.py` | Logger do client com timestamp automático |
| `scripts/analyze_session.py` | Análise offline com tabelas + gráficos de timing |
