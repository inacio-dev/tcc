# Camera e Video - Issues e Soluções

Documento para rastrear problemas e soluções relacionados ao sistema de vídeo H.264.

## Status Atual

- **Data**: 2025-12-17
- **Status**: RESOLVIDO - Migração para MJPEG

---

## Problemas Identificados e Corrigidos

### 1. Encoder H.264 não produzia frames

**Sintoma**: Nenhum frame era capturado, `capture_frame()` retornava `None`.

**Causa**: Faltava o parâmetro `encode="main"` na configuração do picamera2.

**Correção** (`raspberry/camera_manager.py`):
```python
# ANTES (não funcionava)
config = self.camera.create_video_configuration(
    main={"size": self.resolution},
    buffer_count=4,
)

# DEPOIS (funciona)
config = self.camera.create_video_configuration(
    main={"size": self.resolution, "format": "XBGR8888"},
    encode="main",  # IMPORTANTE: indica qual stream usar para o encoder
    buffer_count=4,
)
```

### 2. Cliente filtrava pacotes por hostname ao invés de IP

**Sintoma**: Pacotes chegavam mas eram ignorados. Log mostrava:
```
Pacote de 192.168.5.33, filtro=f1car.local
```

**Causa**: O filtro comparava IP numérico com hostname mDNS.

**Correção** (`client/network_client.py`):
```python
# Resolve hostname para IP na inicialização
if rpi_ip:
    try:
        resolved_ip = socket.gethostbyname(rpi_ip)
        self.rpi_ip = resolved_ip
    except socket.gaierror:
        self.rpi_ip = rpi_ip
```

### 3. Spam de warnings quando BMI160 não conectado

**Sintoma**: Console inundado com "Campo obrigatório ausente: bmi160_accel_x".

**Causa**: Validação muito rígida - BMI160 era obrigatório.

**Correção** (`client/sensor_display.py`):
- BMI160 agora é opcional
- Log apenas 1x a cada 30 segundos

---

### 4. Distorção Visual com H.264 (RESOLVIDO)

**Sintoma**: Bandas horizontais distorcidas/corrompidas na imagem.

**Causa**: H.264 usa P-frames que dependem de frames anteriores. Perda de pacote UDP corrompe múltiplos frames.

**Solução**: Migração de H.264 para MJPEG.

```python
# ANTES (H.264 - com distorção)
from picamera2.encoders import H264Encoder
encoder = H264Encoder(bitrate=1500000, repeat=True, iperiod=15)

# DEPOIS (MJPEG - sem distorção)
from picamera2.encoders import MJPEGEncoder
encoder = MJPEGEncoder()
```

**Por que MJPEG resolve:**

| Característica | H.264 | MJPEG |
|----------------|-------|-------|
| Dependência entre frames | P-frames dependem dos anteriores | Cada frame é independente |
| Efeito de perda de pacote | Corrompe múltiplos frames | Perde só 1 frame |
| Uso de banda | ~1.5-2.5 Mbps | ~6-8 Mbps |
| Qualidade | Boa | Excelente |

**Trade-off aceito**: Mais banda (~4x) em troca de imagem perfeita.

---

## Configurações Atuais

### Raspberry Pi (camera_manager.py)

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| Resolução | 640x480 | Tamanho do frame |
| FPS | 30 | Taxa de captura |
| Bitrate | 1.5 Mbps | Taxa de compressão |
| Keyframe (iperiod) | 15 frames | ~2 keyframes/segundo |
| repeat | True | Repete SPS/PPS |
| Buffer circular | 10 frames | Armazena últimos frames |

### Cliente (video_display.py)

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| Queue timeout | 100ms | Tempo de espera por frame |
| Frames extras | até 5 | Processa acúmulo na fila |
| No signal timeout | 2s | Tempo para mostrar "sem sinal" |
| Codec | H.264 (PyAV) | Decoder de vídeo |

---

## Próximos Passos para Investigar

### Se distorção persistir:

1. **Reduzir bitrate**
   ```python
   # camera_manager.py
   bitrate=1000000  # 1.0 Mbps (era 1.5)
   ```

2. **Usar TCP ao invés de UDP**
   - Mais confiável, maior latência
   - Requer refatoração do network_manager

3. **Implementar fragmentação própria**
   - Dividir frames grandes em chunks < 1400 bytes
   - Reassembly no cliente com sequence numbers

4. **Adicionar detecção de corrupção**
   - Checksum por pacote
   - Solicitar retransmissão de keyframe se corrompido

5. **Flush do decoder em erro**
   ```python
   # Resetar decoder quando detectar corrupção
   self.codec = av.CodecContext.create('h264', 'r')
   ```

---

## Arquivos Relacionados

### Raspberry Pi
- `raspberry/camera_manager.py` - Captura e encoding H.264
- `raspberry/network_manager.py` - Transmissão UDP
- `raspberry/main.py` - Loop principal

### Cliente
- `client/video_display.py` - Decoder e exibição
- `client/network_client.py` - Recepção UDP
- `client/main.py` - Orquestração

### Testes
- `test/test_camera_h264.py` - Teste isolado do encoder

---

## Comandos Úteis para Debug

```bash
# Testar encoder H.264 isoladamente
python test/test_camera_h264.py

# Ver pacotes UDP chegando
sudo tcpdump -i any udp port 9999 -c 10

# Verificar resolução mDNS
ping f1car.local -c 1
ping f1client.local -c 1

# Monitorar uso de CPU no Raspberry
htop

# Ver estatísticas de rede
netstat -u -n
```

---

## Histórico de Mudanças

| Data | Mudança |
|------|---------|
| 2025-12-17 | Corrigido `encode="main"` no picamera2 |
| 2025-12-17 | Corrigido filtro IP vs hostname |
| 2025-12-17 | BMI160 tornado opcional |
| 2025-12-17 | Keyframe interval: 30 → 15 |
| 2025-12-17 | Adicionado `np.ascontiguousarray()` |
| 2025-12-17 | Loop de vídeo baseado em eventos |
