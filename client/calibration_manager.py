#!/usr/bin/env python3
"""
calibration_manager.py - Encoder Calibration Manager
Manages calibration of incremental encoders (throttle, brake, steering)

This module handles the calibration process for ESP32 incremental encoders,
allowing dynamic adjustment of encoder ranges without hardcoded pulse limits.

Calibration Flow:
1. User clicks "Calibrar" button for a specific control
2. System enters calibration mode and displays instructions
3. User physically moves the encoder through its full range
4. System records min/max/center raw encoder values
5. User clicks "Salvar" to save calibration
6. System calculates mapping from raw pulses to 0-100% (or -100 to +100%)

@author F1 RC Car Project
@date 2025-10-14
"""

import json
import os
from typing import Dict, Optional, Callable
from datetime import datetime


class CalibrationManager:
    """Manages encoder calibration for throttle, brake, and steering"""

    def __init__(
        self,
        serial_sender: Optional[Callable[[str], bool]] = None,
        log_callback: Optional[Callable[[str, str], None]] = None,
        config_file: str = "encoder_calibration.json",
    ):
        """
        Initialize calibration manager

        Args:
            serial_sender: Function to send commands to ESP32 (command: str) -> bool
            log_callback: Function to log messages (level: str, message: str)
            config_file: JSON file to save/load calibration data
        """
        self.serial_sender = serial_sender
        self.log_callback = log_callback
        self.config_file = config_file

        # Calibration state
        self.is_calibrating = False
        self.current_component = None  # "THROTTLE", "BRAKE", "STEERING"
        self.calibration_step = 0

        # Raw encoder values during calibration
        self.raw_min = None
        self.raw_max = None
        self.raw_center = None
        self.raw_current = 0

        # Calibration data for all components
        self.calibration_data = {
            "THROTTLE": {"min": 0, "max": 600},  # Default values
            "BRAKE": {"min": 0, "max": 600},
            "STEERING": {"left": 0, "center": 300, "right": 600},
        }

        # Load existing calibration if available
        self.load_calibration()

    def _log(self, level: str, message: str):
        """Send log message"""
        if self.log_callback:
            self.log_callback(level, message)
        else:
            print(f"[{level}] {message}")

    def start_calibration(self, component: str) -> bool:
        """
        Start calibration process for a component

        Args:
            component: "THROTTLE", "BRAKE", or "STEERING"

        Returns:
            bool: True if calibration started successfully
        """
        if self.is_calibrating:
            self._log("WARN", "Calibração já em andamento!")
            return False

        if component not in ["THROTTLE", "BRAKE", "STEERING"]:
            self._log("ERROR", f"Componente inválido: {component}")
            return False

        # Reset calibration state
        self.is_calibrating = True
        self.current_component = component
        self.calibration_step = 0
        self.raw_min = None
        self.raw_max = None
        # For steering, record initial position as center
        self.raw_center = 0 if component == "STEERING" else None
        self.raw_current = 0

        # Send calibration start command to ESP32
        if self.serial_sender:
            command = f"CAL_START:{component}"
            success = self.serial_sender(command)
            if not success:
                self._log("ERROR", f"Falha ao enviar comando de calibração: {command}")
                self.is_calibrating = False
                return False

        self._log("INFO", f"🎯 Calibração iniciada: {component}")
        return True

    def update_raw_value(self, component: str, raw_value: int):
        """
        Update raw encoder value during calibration

        Args:
            component: Component being calibrated
            raw_value: Current raw encoder position
        """
        if not self.is_calibrating or component != self.current_component:
            return

        self.raw_current = raw_value

        # Auto-detect min/max as user moves encoder
        if self.raw_min is None or raw_value < self.raw_min:
            self.raw_min = raw_value
        if self.raw_max is None or raw_value > self.raw_max:
            self.raw_max = raw_value

    def save_calibration(self) -> bool:
        """
        Save current calibration data

        Returns:
            bool: True if calibration saved successfully
        """
        if not self.is_calibrating:
            self._log("WARN", "Nenhuma calibração em andamento!")
            return False

        component = self.current_component

        # Validate calibration data
        if component in ["THROTTLE", "BRAKE"]:
            if self.raw_min is None or self.raw_max is None:
                self._log("ERROR", "Dados de calibração incompletos! Mova o encoder pelo range completo.")
                return False

            if self.raw_min >= self.raw_max:
                self._log("ERROR", f"Calibração inválida! Min ({self.raw_min}) >= Max ({self.raw_max})")
                return False

            # Save throttle/brake calibration
            self.calibration_data[component] = {
                "min": self.raw_min,
                "max": self.raw_max,
            }

            # Send calibration to ESP32
            if self.serial_sender:
                command = f"CAL_SAVE:{component}:{self.raw_min}:{self.raw_max}"
                self.serial_sender(command)

            self._log("INFO", f"✅ Calibração salva: {component} = [{self.raw_min}, {self.raw_max}]")

        elif component == "STEERING":
            # For steering, we need left, center, right positions
            if self.raw_min is None or self.raw_max is None:
                self._log("ERROR", "Dados de calibração incompletos! Gire o volante completamente.")
                return False

            if self.raw_min >= self.raw_max:
                self._log("ERROR", f"Calibração inválida! Esquerda ({self.raw_min}) >= Direita ({self.raw_max})")
                return False

            # Calculate center as midpoint between left and right
            raw_center = (self.raw_min + self.raw_max) // 2

            # Save steering calibration
            self.calibration_data[component] = {
                "left": self.raw_min,
                "center": raw_center,
                "right": self.raw_max,
            }

            # Send calibration to ESP32
            if self.serial_sender:
                command = f"CAL_SAVE:{component}:{self.raw_min}:{raw_center}:{self.raw_max}"
                self.serial_sender(command)

            self._log("INFO", f"✅ Calibração salva: {component} = [Esq:{self.raw_min}, Centro:{raw_center}, Dir:{self.raw_max}]")

        # Save to file
        self.save_to_file()

        # End calibration mode
        self.is_calibrating = False
        self.current_component = None

        return True

    def cancel_calibration(self):
        """Cancel current calibration"""
        if self.is_calibrating:
            self._log("INFO", f"Calibração cancelada: {self.current_component}")
        self.is_calibrating = False
        self.current_component = None
        self.raw_min = None
        self.raw_max = None
        self.raw_center = None

    def get_calibration_instructions(self) -> str:
        """
        Get calibration instructions for current component

        Returns:
            str: Instruction text
        """
        if not self.is_calibrating:
            return ""

        if self.current_component == "THROTTLE":
            return ("🎯 Calibração do Acelerador:\n"
                    "1. SOLTE completamente o pedal (posição 0%)\n"
                    "2. PRESSIONE totalmente o pedal (posição 100%)\n"
                    "3. Clique em 'Salvar' quando terminar")

        elif self.current_component == "BRAKE":
            return ("🎯 Calibração do Freio:\n"
                    "1. SOLTE completamente o pedal (posição 0%)\n"
                    "2. PRESSIONE totalmente o pedal (posição 100%)\n"
                    "3. Clique em 'Salvar' quando terminar")

        elif self.current_component == "STEERING":
            return ("🎯 Calibração da Direção:\n"
                    "1. Gire TOTALMENTE para a ESQUERDA (-100%)\n"
                    "2. Gire TOTALMENTE para a DIREITA (+100%)\n"
                    "3. PARE NO CENTRO (o sistema calculará automaticamente)\n"
                    "4. Clique em 'Salvar' quando terminar")

        return ""

    def get_calibration_status(self) -> Dict:
        """
        Get current calibration status

        Returns:
            dict: Status information
        """
        return {
            "is_calibrating": self.is_calibrating,
            "component": self.current_component,
            "raw_current": self.raw_current,
            "raw_min": self.raw_min,
            "raw_max": self.raw_max,
            "raw_center": self.raw_center,
            "instructions": self.get_calibration_instructions(),
        }

    def get_calibration_data(self, component: str) -> Optional[Dict]:
        """
        Get calibration data for a component

        Args:
            component: "THROTTLE", "BRAKE", or "STEERING"

        Returns:
            dict: Calibration data or None if not available
        """
        return self.calibration_data.get(component)

    def map_raw_to_percent(self, component: str, raw_value: int) -> int:
        """
        Map raw encoder value to percentage based on calibration

        Args:
            component: "THROTTLE", "BRAKE", or "STEERING"
            raw_value: Raw encoder position

        Returns:
            int: Mapped value (0-100% for throttle/brake, -100 to +100% for steering)
        """
        cal_data = self.calibration_data.get(component)
        if not cal_data:
            return 0

        if component in ["THROTTLE", "BRAKE"]:
            min_val = cal_data["min"]
            max_val = cal_data["max"]

            # Ensure min < max for correct mapping
            if min_val > max_val:
                min_val, max_val = max_val, min_val

            # Constrain raw value
            raw_value = max(min_val, min(max_val, raw_value))

            # Map to 0-100%
            if max_val == min_val:
                return 0
            percent = int(((raw_value - min_val) / (max_val - min_val)) * 100)

            return max(0, min(100, percent))

        elif component == "STEERING":
            left_val = cal_data["left"]
            center_val = cal_data["center"]
            right_val = cal_data["right"]

            # Constrain raw value
            raw_value = max(left_val, min(right_val, raw_value))

            # Map to -100 to +100%
            if raw_value < center_val:
                # Left side: left_val to center_val maps to -100% to 0%
                if center_val == left_val:
                    return 0
                percent = int(((raw_value - center_val) / (center_val - left_val)) * 100)
            else:
                # Right side: center_val to right_val maps to 0% to +100%
                if right_val == center_val:
                    return 0
                percent = int(((raw_value - center_val) / (right_val - center_val)) * 100)

            return max(-100, min(100, percent))

        return 0

    def save_to_file(self) -> bool:
        """
        Save calibration data to JSON file

        Returns:
            bool: True if saved successfully
        """
        try:
            # Add metadata
            data = {
                "calibration_data": self.calibration_data,
                "last_updated": datetime.now().isoformat(),
                "version": "1.0",
            }

            with open(self.config_file, "w") as f:
                json.dump(data, f, indent=4)

            self._log("INFO", f"Calibração salva em: {self.config_file}")
            return True

        except Exception as e:
            self._log("ERROR", f"Erro ao salvar calibração: {e}")
            return False

    def load_calibration(self) -> bool:
        """
        Load calibration data from JSON file

        Returns:
            bool: True if loaded successfully
        """
        try:
            if not os.path.exists(self.config_file):
                self._log("INFO", "Nenhum arquivo de calibração encontrado. Usando valores padrão.")
                return False

            with open(self.config_file, "r") as f:
                data = json.load(f)

            self.calibration_data = data.get("calibration_data", self.calibration_data)
            last_updated = data.get("last_updated", "unknown")

            self._log("INFO", f"Calibração carregada de: {self.config_file} (atualizada em: {last_updated})")
            return True

        except Exception as e:
            self._log("ERROR", f"Erro ao carregar calibração: {e}")
            return False

    def reset_to_defaults(self):
        """Reset all calibrations to default values"""
        self.calibration_data = {
            "THROTTLE": {"min": 0, "max": 600},
            "BRAKE": {"min": 0, "max": 600},
            "STEERING": {"left": 0, "center": 300, "right": 600},
        }

        # Send reset command to ESP32
        if self.serial_sender:
            self.serial_sender("CAL_RESET")

        self.save_to_file()
        self._log("INFO", "✅ Calibração resetada para valores padrão")
