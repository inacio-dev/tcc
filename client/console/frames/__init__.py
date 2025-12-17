"""
frames - Componentes de UI do console
"""

from .connection_status import create_connection_status_frame
from .instrument_panel import create_instrument_panel
from .bmi160 import create_bmi160_frame
from .force_feedback import create_force_feedback_frame
from .controls import create_controls_frame
from .video import create_video_frame
from .serial_port import create_serial_port_selector_frame
from .log import create_log_frame

__all__ = [
    "create_connection_status_frame",
    "create_instrument_panel",
    "create_bmi160_frame",
    "create_force_feedback_frame",
    "create_controls_frame",
    "create_video_frame",
    "create_serial_port_selector_frame",
    "create_log_frame",
]
