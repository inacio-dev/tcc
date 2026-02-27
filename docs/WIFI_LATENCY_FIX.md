# WiFi Latency Fix — Diagnóstico e Correção de Stalls de 5 Segundos

## Problema: Vídeo e sensores cortam simultaneamente por ~5 segundos

### Sintoma

A cada 20-60 segundos, o client perde vídeo e sensores ao mesmo tempo:
- Tela mostra "Sem Sinal" (timeout de 2s sem frame)
- Telemetria congela
- Após ~5 segundos, tudo volta ao normal

### Investigação com logs de timing

Adicionamos instrumentação `[DIAG]` em todas as threads do RPi para medir o tempo de cada operação:

```
[DIAG] VIDEO TX LENTO: total=Xms (lock=Xms, send=Xms)
[DIAG] SENSOR TX LENTO: total=Xms (lock=Xms, status=Xms, send=Xms, ping=Xms)
[DIAG] BMI160 LENTO: total=Xms (i2c_read=Xms, lock=Xms)
[DIAG] CAMERA LENTA: total=Xms (capture=Xms, lock=Xms)
[DIAG] STATE CMD LENTO: total=Xms (steering+motor+brake com I2C lock)
[DIAG] SENSOR SEND: serial=Xms, sendto=Xms, size=XB
[DIAG] VIDEO SEND: Xms, size=XB
```

### Resultados do diagnóstico

| Operação | Tempo normal | Durante stall | Causa? |
|----------|-------------|---------------|--------|
| `current_data_lock` | 0ms | 0ms | Não |
| `stats_lock` | 0ms | 0ms | Não |
| I2C BMI160 read | 2-5ms | 2-5ms | Não |
| `_convert_numpy_types` + `json.dumps` | 1-2ms | 1-2ms | Não |
| `get_motor/brake/steering_status` | 0ms | 0ms | Não |
| **`sendto()` vídeo** | 20-25ms | **5015ms** | **SIM** |
| **`sendto()` sensores** | 10-13ms | **5012ms** | **SIM** |

O `sendto()` UDP bloqueou por **exatamente ~5 segundos** em ambos os sockets simultaneamente. Locks, I2C, serialização — tudo OK. O problema era exclusivamente na camada de rede.

## Causa raiz 1: WiFi Power Save

O Raspberry Pi 4 vem com **WiFi power management ativado** por padrão. O driver `brcmfmac` desativa periodicamente a antena WiFi para economizar energia, bloqueando todas as chamadas `sendto()` até a antena ser reativada.

```bash
$ iw wlan0 get power_save
Power save: on  # ← PROBLEMA
```

### Correção

```bash
# Desativa imediatamente
sudo iw wlan0 set power_save off

# Torna permanente via NetworkManager (Raspberry Pi OS Bookworm)
echo -e '[connection]\nwifi.powersave = 2' | sudo tee /etc/NetworkManager/conf.d/wifi-powersave.conf
sudo systemctl restart NetworkManager

# Verificar após reboot
iw wlan0 get power_save
# Deve retornar: Power save: off
```

Nota: o método `/etc/network/interfaces` (wireless-power off) **não funciona** quando o NetworkManager gerencia o WiFi.

## Causa raiz 2: Resolução mDNS em cada sendto()

Mesmo com power save desligado, os stalls de 5s persistiam. O diagnóstico revelou a causa:

### O fluxo problemático

```
1. main.py: set_fixed_client("f1client.local", 9999)
   → armazena "f1client.local" como chave em connected_clients

2. _send_single_packet(): sendto(data, ("f1client.local", 9999))
   → kernel resolve mDNS a CADA pacote (60x/s sensores + 30x/s vídeo)

3. Quando Avahi (mDNS daemon) demora para responder:
   → sendto() bloqueia por 5 segundos (timeout padrão mDNS)
   → AMBOS os sockets bloqueiam (resolução DNS é global)
```

### Por que 5 segundos?

O timeout padrão do Avahi/mDNS é 5 segundos. Quando o daemon está ocupado ou o cache expira, a resolução de `"f1client.local"` trava por esse período. Como **todos os `sendto()`** passavam o hostname em vez de IP, tanto o socket de vídeo quanto o de sensores bloqueavam simultaneamente.

### Timeline do problema

```
t=0:    sendto("f1client.local", ...) → cache mDNS válido → 0ms → OK
t=0.01: sendto("f1client.local", ...) → cache mDNS válido → 0ms → OK
...
t=30:   sendto("f1client.local", ...) → cache mDNS expirou → Avahi query
        → timeout 5000ms → vídeo e sensores bloqueados
t=35:   Avahi responde ou timeout → sendto() retorna → transmissão retomada
```

### Correção: resolver uma vez, enviar por IP

```python
# ANTES: hostname em connected_clients
set_fixed_client("f1client.local", 9999)
# → connected_clients = {"f1client.local": {"port": 9999}}
# → sendto(data, ("f1client.local", 9999))  # resolve mDNS 90x/s!

# DEPOIS: IP numérico em connected_clients
def _resolve_hostname(self, hostname):
    """Resolve hostname para IP numérico (evita mDNS em cada sendto)"""
    try:
        resolved = socket.gethostbyname(hostname)
        return resolved
    except socket.gaierror:
        return hostname

def set_fixed_client(self, client_ip, client_port):
    resolved_ip = self._resolve_hostname(client_ip)  # "192.168.1.x"
    self.connected_clients[resolved_ip] = {"port": client_port, ...}
    # → sendto(data, ("192.168.1.x", 9999))  # sem resolução DNS!
```

O `send_connect_to_client()` (chamado a cada 10s) re-resolve o hostname para atualizar o IP caso o DHCP mude, mas essa resolução é feita **uma vez a cada 10 segundos** em vez de 90 vezes por segundo.

## Latência normal do WiFi do RPi 4

Após as correções, os logs mostram:

| Operação | Latência típica | Status |
|----------|----------------|--------|
| `sendto()` sensores (4KB) | 10-13ms | Normal para WiFi |
| `sendto()` vídeo (17KB) | 20-25ms | Normal para WiFi |
| `json.dumps()` | 1-2ms | Normal |
| `current_data_lock` | 0ms | Sem contention |

O WiFi interno do RPi 4 (brcmfmac, 802.11ac) tem latência base de ~10ms para pacotes UDP. Isso é inerente ao hardware e não causa problemas visíveis (frame rate e sensor rate se mantêm estáveis).

## Arquivos modificados

- `raspberry/network_manager.py`:
  - `_resolve_hostname()`: resolve hostname → IP numérico
  - `set_fixed_client()`: armazena IP resolvido em connected_clients
  - `send_connect_to_client()`: re-resolve a cada 10s, atualiza IP se mudou
  - `send_sensor_data()`: threshold de diagnóstico ajustado (10ms → 50ms)
  - `send_video_frame()`: log de diagnóstico para sendto lento
- `raspberry/main.py`:
  - Logs `[DIAG]` em todas as threads (câmera, BMI160, video TX, sensor TX, STATE cmd)
- `/etc/NetworkManager/conf.d/wifi-powersave.conf`: desativa power save permanentemente
