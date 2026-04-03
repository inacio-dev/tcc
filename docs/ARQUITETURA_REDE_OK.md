# Arquitetura de Rede - Decisões Técnicas

Documento sobre as escolhas de comunicação UDP entre Raspberry Pi e Cliente.

## Status Atual

- **Data**: 2025-12-18
- **Status**: Produção - 3 portas UDP

---

## Visão Geral da Comunicação

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ARQUITETURA DE REDE                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  RASPBERRY PI                         CLIENTE PC                    │
│  ────────────                         ──────────                    │
│                                                                     │
│  Camera Thread ──► Vídeo MJPEG ─────────────────────┐               │
│  Power Thread ───► Energia     ──┐                  │               │
│  Temp Thread ────► Temperatura ──┼──► UDP 9999 ─────┼──► Recepção   │
│                                  │    (~60Hz)       │    Principal  │
│                                  │                  │               │
│  BMI160 Thread ──► Accel/Gyro ──────► UDP 9997 ─────┼──► Thread     │
│                                       (100Hz)       │    Sensores   │
│                                                     │               │
│  Command Handler ◄───────────────── UDP 9998 ◄──────┴── Controles   │
│                                     (100Hz STATE + on-demand gear)  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Por que 3 Portas Separadas?

### Porta 9999 - Vídeo + Dados Consolidados

| Característica | Valor |
|----------------|-------|
| Direção | RPi → Cliente |
| Taxa | ~60Hz (sync com câmera) |
| Tamanho pacote | 10-50 KB (frame MJPEG) |
| Conteúdo | Frame + energia + temperatura |

**Por que consolidar vídeo com dados lentos?**
- Energia (10Hz) e temperatura (1Hz) são lentos
- Aproveita o pacote do frame sem overhead adicional
- Sincronização temporal automática

### Porta 9997 - Sensores Rápidos (BMI160)

| Característica | Valor |
|----------------|-------|
| Direção | RPi → Cliente |
| Taxa | 100Hz fixo |
| Tamanho pacote | ~200 bytes (JSON) |
| Conteúdo | Accel X/Y/Z, Gyro X/Y/Z, G-forces |

**Por que porta dedicada?**
- Force feedback precisa de 100Hz consistente
- Vídeo grande (50KB) bloquearia sensores pequenos (200B)
- Latência crítica: <10ms para resposta tátil

### Porta 9998 - Comandos Bidirecionais

| Característica | Valor |
|----------------|-------|
| Direção | Cliente ↔ RPi |
| Taxa | 100Hz (STATE contínuo) + on-demand (gear shifts) |
| Tamanho pacote | ~50 bytes (texto) |
| Conteúdo | CONTROL:STATE:s,t,b (100Hz), GEAR_UP/DOWN, PING |

**Arquitetura de comandos:**
- G923/sliders atualizam `_control_state` (string "steering,throttle,brake")
- Thread TX dedicada envia `CONTROL:STATE:s,t,b` a 100Hz com timing compensado
- Gear shifts (G923 paddles e teclas M/N) são enviados imediatamente
- Teclado verifica `packets_received > 0` antes de enviar (mesma regra do G923)

---

## Por que UDP e não TCP?

### Comparação

| Aspecto | UDP | TCP |
|---------|-----|-----|
| Latência | Mínima (1,94ms medido) | Alta (handshake + ACK) |
| Overhead | 8 bytes header | 20+ bytes header |
| Perda de pacote | Aceita (próximo frame resolve) | Retransmite (atrasa tudo) |
| Conexão | Stateless | Stateful |
| Broadcast | Nativo | Não suporta |

### Cenário: Perda de 1 pacote

**Com UDP:**
```
Frame 1 → OK
Frame 2 → PERDIDO
Frame 3 → OK (exibe normalmente)
Resultado: 1 frame perdido, vídeo continua fluido
```

**Com TCP:**
```
Frame 1 → OK
Frame 2 → PERDIDO → Retransmite → Aguarda ACK
Frame 3 → AGUARDANDO Frame 2
Resultado: Vídeo trava até retransmissão completar
```

**Conclusão**: Para telemetria em tempo real, perder dados antigos é melhor que atrasar dados novos.

---

## Formato dos Pacotes

### Porta 9999 (Vídeo)

```
┌──────────────┬─────────────────┐
│ frame_size   │ frame_data      │
│ (4 bytes)    │ (N bytes)       │
│ little-end   │ MJPEG raw       │
└──────────────┴─────────────────┘
```

**Exemplo:**
```python
# Criação do pacote (send_video_frame)
frame_data = camera.capture()  # bytes MJPEG
packet = struct.pack("<I", len(frame_data)) + frame_data
```

**Nota:** Dados de energia e temperatura são incluídos como campos extras
no JSON de sensores quando disponíveis, não embutidos no pacote de vídeo.

### Porta 9997 (Sensores Rápidos)

```
┌─────────────────┐
│ sensor_json     │
│ (N bytes)       │
│ UTF-8 JSON      │
└─────────────────┘
```

**Nota:** Sem header binário — o pacote é JSON puro codificado em UTF-8,
enviado diretamente via `sendto()` sem `struct.pack`.

**Exemplo de JSON:**
```json
{
    "bmi160_accel_x": -0.12,
    "bmi160_accel_y": 0.05,
    "bmi160_accel_z": 9.78,
    "bmi160_gyro_x": 0.5,
    "bmi160_gyro_y": -0.2,
    "bmi160_gyro_z": 1.1,
    "bmi160_g_force_lateral": 0.013,
    "bmi160_timestamp": 1702847123.456
}
```

### Porta 9998 (Comandos)

```
Texto plano UTF-8, terminado em newline

Exemplos:
  CONNECT\n
  PING\n
  CONTROL:THROTTLE:50\n
  CONTROL:STEERING:-30\n
  CONTROL:GEAR_UP\n
```

---

## mDNS - Zero Configuration

### Por que mDNS?

| Método | Configuração | Flexibilidade |
|--------|--------------|---------------|
| IP fixo | Manual em cada rede | Nenhuma |
| DHCP + hostname | Depende do roteador | Média |
| **mDNS** | Zero-config | Total |

### Configuração

**Raspberry Pi:**
```bash
sudo hostnamectl set-hostname f1car
# Acessível como f1car.local
```

**Cliente:**
```bash
sudo hostnamectl set-hostname f1client
# Acessível como f1client.local
```

### Resolução no Código

```python
import socket

def resolve_rpi():
    try:
        ip = socket.gethostbyname("f1car.local")
        return ip  # Ex: "192.168.1.47"
    except socket.gaierror:
        return "192.168.1.100"  # Fallback
```

---

## Filtragem de IP

### Por que filtrar pacotes?

```python
def _receive_loop(self):
    while self.running:
        data, addr = self.socket.recvfrom(65535)

        # Ignora pacotes de outros dispositivos
        if addr[0] != self.rpi_ip:
            continue

        self._process_packet(data)
```

**Motivos:**
1. Segurança: Evita dados de fontes desconhecidas
2. Debug: Simplifica troubleshooting
3. Performance: Não processa lixo

---

## Buffers de Socket

### Configuração Atual

```python
# Porta 9999 (vídeo) - buffer grande
# RPi (send): SO_SNDBUF = 65536 (64 KB)
# Client (recv): SO_RCVBUF = 65536 (64 KB)

# Porta 9997 (sensores) - buffer intermediário
# RPi (send): SO_SNDBUF = 32768 (32 KB)
# Client (recv): SO_RCVBUF = 32768 (32 KB)

# Porta 9998 (comandos) - buffer grande para recepção no RPi
# RPi (recv): SO_RCVBUF = 131072 (128 KB)
```

### Trade-off

| Porta | Buffer | Justificativa |
|-------|--------|---------------|
| 9999 (vídeo) | 64 KB | Frames grandes (10-50 KB), menor perda |
| 9997 (sensores) | 32 KB | Balanceia latência e confiabilidade para FF |
| 9998 (comandos) | 128 KB | Acomoda picos de comandos simultâneos |

---

## Heartbeat / Keep-Alive

### Mecanismo PING/PONG

```python
# Cliente envia PING (com timestamp opcional)
# Formato: "PING" ou "PING:<timestamp>"

# RPi responde PONG ao receber PING do cliente
def _handle_client_ping(self, client_ip, client_port, ping_data):
    parts = ping_data.split(":")
    if len(parts) > 1:
        timestamp = parts[1]
        pong_response = f"PONG:{timestamp}".encode("utf-8")
    else:
        pong_response = b"PONG"
    self._send_to_client(client_ip, pong_response)
```

**Nota:** O RPi **não** inicia PINGs — apenas responde ao cliente. O cliente é responsável por iniciar o heartbeat.

---

## Alternativas ao UDP Analisadas

### Comparação de Protocolos

| Protocolo | Latência | Confiabilidade | Overhead | Uso Ideal |
|-----------|----------|----------------|----------|-----------|
| **UDP puro** | 1,94ms (medido) | Nenhuma | 8 bytes | ✅ Escolhido |
| TCP | ~10-50ms | 100% | 20+ bytes | Arquivos, HTTP |
| MQTT | ~5-20ms | QoS 0/1/2 | Broker + header | IoT com broker |
| WebSocket | ~5-15ms | TCP underneath | Handshake grande | Web apps |
| ZeroMQ | ~1-2ms | Opcional | Mínimo | Pub/sub rápido |
| nanomsg/nng | ~1-2ms | Opcional | Mínimo | Alternativa ZeroMQ |
| UDP Multicast | ~1ms | Nenhuma | 8 bytes | Múltiplos clientes |
| QUIC | ~2-5ms | Parcial | Médio | HTTP/3, streams |

### Análise por Caso de Uso

**Para Vídeo (60Hz, pacotes grandes):**

| Protocolo | Veredicto | Motivo |
|-----------|-----------|--------|
| **UDP** | ✅ Ideal | Perder 1 frame é OK, próximo resolve |
| TCP | ❌ Ruim | Retransmissão trava o stream |
| MQTT | ❌ Ruim | Não foi feito para blobs grandes |
| WebRTC | ⚠️ Alternativa | Bom, mas complexo demais para LAN |

**Para Sensores (100Hz, latência crítica):**

| Protocolo | Veredicto | Motivo |
|-----------|-----------|--------|
| **UDP** | ✅ Ideal | 1ms latência, dado antigo é inútil |
| ZeroMQ | ✅ Alternativa | Pub/sub eficiente, ~1-2ms |
| MQTT QoS 0 | ⚠️ OK | Funciona, mas precisa de broker |
| TCP | ❌ Ruim | Latência variável, buffering |

**Para Comandos (on-demand, precisa chegar):**

| Protocolo | Veredicto | Motivo |
|-----------|-----------|--------|
| **UDP** | ⚠️ OK | Funciona, mas pode perder |
| UDP + ACK manual | ✅ Melhor | Confirma recebimento |
| TCP | ✅ Alternativa | Garante entrega |
| MQTT QoS 1 | ✅ Alternativa | Garante pelo menos 1 entrega |

### Por que NÃO usar MQTT?

| Aspecto | Problema |
|---------|----------|
| Broker | Precisa rodar Mosquitto em algum lugar |
| Latência | +5-20ms comparado com UDP |
| Vídeo | Não é ideal para blobs grandes |
| Complexidade | Overhead de conexão e tópicos |

**Veredicto**: Latência extra não compensa para telemetria em tempo real.

### ZeroMQ - Alternativa Considerada

```python
# Exemplo de como seria com ZeroMQ
# RPi (Publisher)
import zmq
context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://*:9999")
socket.send_multipart([b"sensor", sensor_data])

# Cliente (Subscriber)
socket = context.socket(zmq.SUB)
socket.connect("tcp://f1car.local:9999")
socket.subscribe(b"sensor")
topic, data = socket.recv_multipart()
```

| Prós | Contras |
|------|---------|
| Latência similar UDP (~1-2ms) | Dependência extra (pyzmq) |
| Pub/sub nativo | Curva de aprendizado |
| Filtro por tópico | Menos controle que UDP puro |
| Reconnect automático | Overhead de abstração |

**Veredicto**: Boa alternativa, mas UDP puro é mais simples e funciona bem.

### Conclusão: Manter UDP

1. **Funciona bem** - Não há problema real a resolver
2. **Latência mínima** - 1ms é imbatível
3. **Simplicidade** - Sem dependências extras
4. **Controle total** - Sabemos exatamente o que acontece

---

## Discussão: Possíveis Melhorias

### 1. Compressão de Sensores

```python
# Atual: JSON (~200 bytes)
{"bmi160_accel_x": -0.12, "bmi160_accel_y": 0.05, ...}

# Alternativa: MessagePack (~80 bytes)
import msgpack
data = msgpack.packb(sensor_dict)

# Alternativa: Struct binário (~48 bytes)
data = struct.pack("<6f", ax, ay, az, gx, gy, gz)
```

**Trade-off**: Menor tamanho vs. menor legibilidade para debug.

### 2. Frame ID Counter (Implementado)

O RPi inclui um `frame_id_counter` nos pacotes de vídeo para detecção de perda:

```python
self.frame_id_counter = (self.frame_id_counter + 1) & 0xFFFFFFFF
```

Nota: usa `& 0xFFFFFFFF` (bitwise AND) em vez de `% 0xFFFFFFFF` (módulo) para
incluir o valor máximo no range.

### 3. Redundância de Comandos Críticos

```python
# Enviar comandos importantes 2-3 vezes
def send_critical_command(self, cmd):
    for _ in range(3):
        self.send_command(cmd)
        time.sleep(0.005)  # 5ms entre envios
```

### 4. QoS no Roteador

Priorizar porta 9998 (comandos) sobre 9999 (vídeo) nas configurações do roteador.

---

## Arquivos Relacionados

### Raspberry Pi
- `raspberry/managers/network.py` - Transmissão UDP
- `raspberry/main.py` - Orquestração de threads

### Cliente
- `client/managers/network.py` - Recepção UDP + `_stats_lock` para contadores thread-safe
- `client/main.py` - Threads de recepção + TX 100Hz com timing compensado

---

## Histórico de Mudanças

| Data | Mudança |
|------|---------|
| 2025-12-17 | Implementação inicial com porta única |
| 2025-12-17 | Separação: porta 9997 para sensores 100Hz |
| 2025-12-17 | Adicionado filtro de IP |
| 2025-12-18 | Documentação de decisões técnicas |
| 2026-03-22 | Timing compensado nos TX loops, _stats_lock, frame_id fix, protocolo STATE 100Hz |
