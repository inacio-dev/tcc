"""
constants.py - Constantes compartilhadas do console
"""

from pathlib import Path

# Limites do console de log
MAX_LOG_LINES = 5000

# Diretório de auto-export (relativo ao diretório do projeto client/)
AUTO_EXPORT_DIR = str(Path(__file__).resolve().parents[3] / "exports" / "auto")

# Intervalos de atualização (ms)
UPDATE_INTERVAL = 100  # Taxa de atualização da GUI
AUTO_SAVE_INTERVAL = 20000  # Auto-save periódico (20 segundos)

# Thresholds de cálculo
ACCEL_THRESHOLD = 0.3  # Threshold para filtrar ruído de aceleração (m/s²)
VELOCITY_DECAY_FACTOR = 0.98  # Fator de decay para simular atrito
MIN_VELOCITY_THRESHOLD = 0.1  # Velocidade mínima antes de zerar (m/s)

# Limites mínimos para auto-save
MIN_LOGS_FOR_SAVE = 100
MIN_SENSORS_FOR_SAVE = 1000
MIN_TELEMETRY_FOR_SAVE = 100  # Pontos mínimos de telemetria para salvar

# Valores padrão de Force Feedback
FF_DAMPING_DEFAULT = 50.0
FF_FRICTION_DEFAULT = 30.0
FF_FILTER_DEFAULT = 40.0
FF_SENSITIVITY_DEFAULT = 75.0
FF_MAX_FORCE_DEFAULT = 15.0  # Limite máximo de força no motor (% do max do G923)

# Valores padrão de controle
BRAKE_BALANCE_DEFAULT = 60.0  # 60% dianteiro
