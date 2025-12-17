"""
constants.py - Constantes compartilhadas do console
"""

# Limites do console de log
MAX_LOG_LINES = 5000

# Diretório de auto-export
AUTO_EXPORT_DIR = "exports/auto"

# Intervalos de atualização (ms)
UPDATE_INTERVAL = 100  # Taxa de atualização da GUI
AUTO_SAVE_INTERVAL = 20000  # Auto-save periódico (20 segundos)

# Thresholds de cálculo
ACCEL_THRESHOLD = 0.3  # Threshold para filtrar ruído de aceleração (m/s²)
VELOCITY_DECAY_FACTOR = 0.98  # Fator de decay para simular atrito
MIN_VELOCITY_THRESHOLD = 0.1  # Velocidade mínima antes de zerar (m/s)

# Limites mínimos para auto-save
MIN_LOGS_FOR_SAVE = 200
MIN_SENSORS_FOR_SAVE = 100

# Valores padrão de Force Feedback
FF_DAMPING_DEFAULT = 50.0
FF_FRICTION_DEFAULT = 30.0
FF_FILTER_DEFAULT = 40.0
FF_SENSITIVITY_DEFAULT = 75.0

# Valores padrão de controle
BRAKE_BALANCE_DEFAULT = 60.0  # 60% dianteiro

# Cores do tema escuro
COLORS = {
    "bg_dark": "#2b2b2b",
    "bg_medium": "#3c3c3c",
    "bg_light": "#4c4c4c",
    "bg_panel": "#2c2c2c",
    "bg_log": "#1e1e1e",
    "fg_white": "#ffffff",
    "fg_gray": "#cccccc",
    "fg_dark_gray": "#808080",
    "fg_green": "#00ff00",
    "fg_red": "#ff0000",
    "fg_yellow": "#ffff00",
    "fg_orange": "#ffaa00",
    "fg_blue": "#0078d4",
    "fg_cyan": "#00aaff",
    "fg_temp_normal": "#00ff88",
    "fg_temp_warning": "#ffaa00",
    "fg_temp_critical": "#ff4444",
}
