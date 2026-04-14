# Network ports
VIDEO_PORT = 9999
SENSOR_PORT = 9997
COMMAND_PORT = 9998

# Socket configuration
UDP_SOCKET_TIMEOUT = 1.0
# VIDEO_SOCKET_RCVBUF: dimensionado para 1080p @ 60fps.
#   Um frame 1080p MJPEG Q=85 tem ~200-400 KB, fragmentado em 4-7 pacotes UDP
#   de 60 KB. A 60 fps isso gera rajadas de ~300 pacotes/s. Buffer de 4 MB
#   absorve ~10-20 frames de folga antes do kernel dropar.
#   Requer: sudo sysctl -w net.core.rmem_max=4194304 (ou o kernel clampa)
VIDEO_SOCKET_RCVBUF = 4_194_304
SENSOR_SOCKET_RCVBUF = 65536
MAX_FRAME_SIZE = 1_000_000
MAX_SENSOR_SIZE = 50_000

# Connection
CONNECTION_TIMEOUT = 10.0

# Buffer & data limits
DEFAULT_SENSOR_HISTORY_SIZE = 10_000
MAX_VIDEO_QUEUE_FRAMES = 10

# Input rates
G923_SEND_RATE_HZ = 60
