# Camera e Video - Issues e Soluções

Documento para rastrear problemas e soluções relacionados ao sistema de vídeo H.264.

## Status Atual

- **Data**: 2025-12-17
- **Status**: Em investigação - distorção visual ocasional

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

## Problema Atual: Distorção Visual

### Descrição
A imagem às vezes aparece com bandas horizontais distorcidas/corrompidas.

### Possíveis Causas

1. **Perda de pacotes UDP**
   - Frames H.264 podem ter 4-30KB
   - UDP não garante entrega
   - Fragmentação de pacotes grandes

2. **Decoder sem keyframe inicial**
   - H.264 precisa de SPS/PPS para inicializar
   - P-frames dependem de frames anteriores
   - Se perder um frame, os seguintes ficam corrompidos

3. **Memória não-contígua**
   - PyAV pode retornar arrays com stride incorreto
   - Corrigido com `np.ascontiguousarray()`

4. **Processamento em lote**
   - Decodificar múltiplos frames mas exibir só o último
   - Pode causar dessincronização do decoder

### Correções Aplicadas

1. **Keyframe mais frequente** (`raspberry/camera_manager.py`):
   ```python
   iperiod=15  # Keyframe a cada 0.5s (era 30 = 1s)
   ```

2. **Memória contígua** (`client/video_display.py`):
   ```python
   if not img.flags['C_CONTIGUOUS']:
       img = np.ascontiguousarray(img)
   ```

3. **Loop baseado em eventos** (`client/video_display.py`):
   ```python
   # Bloqueia esperando frame (não polling)
   frame_data = self.video_queue.get(timeout=0.1)
   ```

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
