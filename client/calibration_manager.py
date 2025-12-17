#!/usr/bin/env python3
"""
calibration_manager.py - Gerenciador de Calibração de Encoders
Gerencia calibração de encoders incrementais (acelerador, freio, direção)

Este módulo trata o processo de calibração para encoders incrementais do ESP32,
permitindo ajuste dinâmico das faixas de encoder sem limites de pulsos fixos no código.

Fluxo de Calibração:
1. Usuário clica no botão "Calibrar" para um controle específico
2. Sistema entra em modo de calibração e exibe instruções
3. Usuário move fisicamente o encoder através de sua faixa completa
4. Sistema registra valores brutos mín/máx/centro do encoder
5. Usuário clica em "Salvar" para salvar calibração
6. Sistema calcula mapeamento de pulsos brutos para 0-100% (ou -100 a +100%)

@author F1 RC Car Project
@date 2025-10-14
"""

import json
import os
from typing import Dict, Optional, Callable
from datetime import datetime


class CalibrationManager:
    """Gerencia calibração de encoders para acelerador, freio e direção"""

    def __init__(
        self,
        serial_sender: Optional[Callable[[str], bool]] = None,
        log_callback: Optional[Callable[[str, str], None]] = None,
        config_file: str = "encoder_calibration.json",
    ):
        """
        Inicializa gerenciador de calibração

        Args:
            serial_sender: Função para enviar comandos ao ESP32 (comando: str) -> bool
            log_callback: Função para registrar mensagens (nível: str, mensagem: str)
            config_file: Arquivo JSON para salvar/carregar dados de calibração
        """
        self.serial_sender = serial_sender
        self.log_callback = log_callback
        self.config_file = config_file

        # Estado de calibração
        self.is_calibrating = False
        self.current_component = None  # "THROTTLE", "BRAKE", "STEERING"
        self.calibration_step = 0

        # Valores brutos do encoder durante calibração
        self.raw_min = None
        self.raw_max = None
        self.raw_center = None
        self.raw_current = 0

        # Dados de calibração para todos os componentes
        self.calibration_data = {
            "THROTTLE": {"min": 0, "max": 600},  # Valores padrão
            "BRAKE": {"min": 0, "max": 600},
            "STEERING": {"left": 0, "center": 300, "right": 600},
        }

        # Carrega calibração existente se disponível
        self.load_calibration()

    def _log(self, level: str, message: str):
        """Envia mensagem de log"""
        if self.log_callback:
            self.log_callback(level, message)
        else:
            print(f"[{level}] {message}")

    def start_calibration(self, component: str) -> bool:
        """
        Inicia processo de calibração para um componente

        Args:
            component: "THROTTLE", "BRAKE", ou "STEERING"

        Returns:
            bool: True se calibração iniciada com sucesso
        """
        if self.is_calibrating:
            self._log("WARN", "Calibração já em andamento!")
            return False

        if component not in ["THROTTLE", "BRAKE", "STEERING"]:
            self._log("ERROR", f"Componente inválido: {component}")
            return False

        # Reseta estado de calibração
        self.is_calibrating = True
        self.current_component = component
        self.calibration_step = 0
        self.raw_min = None
        self.raw_max = None
        # Para direção, registra posição inicial como centro
        self.raw_center = 0 if component == "STEERING" else None
        self.raw_current = 0

        # Envia comando de início de calibração ao ESP32
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
        Atualiza valor bruto do encoder durante calibração

        Args:
            component: Componente sendo calibrado
            raw_value: Posição bruta atual do encoder
        """
        if not self.is_calibrating or component != self.current_component:
            return

        self.raw_current = raw_value

        # Auto-detecta mín/máx conforme usuário move encoder
        if self.raw_min is None or raw_value < self.raw_min:
            self.raw_min = raw_value
        if self.raw_max is None or raw_value > self.raw_max:
            self.raw_max = raw_value

    def save_calibration(self) -> bool:
        """
        Salva dados de calibração atuais

        Returns:
            bool: True se calibração salva com sucesso
        """
        if not self.is_calibrating:
            self._log("WARN", "Nenhuma calibração em andamento!")
            return False

        component = self.current_component

        # Valida dados de calibração
        if component in ["THROTTLE", "BRAKE"]:
            if self.raw_min is None or self.raw_max is None:
                self._log("ERROR", "Dados de calibração incompletos! Mova o encoder pelo range completo.")
                return False

            if self.raw_min >= self.raw_max:
                self._log("ERROR", f"Calibração inválida! Min ({self.raw_min}) >= Max ({self.raw_max})")
                return False

            # Salva calibração de acelerador/freio
            self.calibration_data[component] = {
                "min": self.raw_min,
                "max": self.raw_max,
            }

            # Envia calibração ao ESP32
            if self.serial_sender:
                command = f"CAL_SAVE:{component}:{self.raw_min}:{self.raw_max}"
                self.serial_sender(command)

            self._log("INFO", f"✅ Calibração salva: {component} = [{self.raw_min}, {self.raw_max}]")

        elif component == "STEERING":
            # Para direção, precisamos das posições esquerda, centro, direita
            if self.raw_min is None or self.raw_max is None:
                self._log("ERROR", "Dados de calibração incompletos! Gire o volante completamente.")
                return False

            if self.raw_min >= self.raw_max:
                self._log("ERROR", f"Calibração inválida! Esquerda ({self.raw_min}) >= Direita ({self.raw_max})")
                return False

            # Calcula centro como ponto médio entre esquerda e direita
            raw_center = (self.raw_min + self.raw_max) // 2

            # Salva calibração de direção
            self.calibration_data[component] = {
                "left": self.raw_min,
                "center": raw_center,
                "right": self.raw_max,
            }

            # Envia calibração ao ESP32
            if self.serial_sender:
                command = f"CAL_SAVE:{component}:{self.raw_min}:{raw_center}:{self.raw_max}"
                self.serial_sender(command)

            self._log("INFO", f"✅ Calibração salva: {component} = [Esq:{self.raw_min}, Centro:{raw_center}, Dir:{self.raw_max}]")

        # Salva em arquivo
        self.save_to_file()

        # Finaliza modo de calibração
        self.is_calibrating = False
        self.current_component = None

        return True

    def cancel_calibration(self):
        """Cancela calibração atual"""
        if self.is_calibrating:
            self._log("INFO", f"Calibração cancelada: {self.current_component}")
        self.is_calibrating = False
        self.current_component = None
        self.raw_min = None
        self.raw_max = None
        self.raw_center = None

    def get_calibration_instructions(self) -> str:
        """
        Obtém instruções de calibração para componente atual

        Returns:
            str: Texto de instruções
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
        Obtém status atual de calibração

        Returns:
            dict: Informações de status
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
        Obtém dados de calibração para um componente

        Args:
            component: "THROTTLE", "BRAKE", ou "STEERING"

        Returns:
            dict: Dados de calibração ou None se não disponível
        """
        return self.calibration_data.get(component)

    def map_raw_to_percent(self, component: str, raw_value: int) -> int:
        """
        Mapeia valor bruto do encoder para porcentagem baseado na calibração

        Args:
            component: "THROTTLE", "BRAKE", ou "STEERING"
            raw_value: Posição bruta do encoder

        Returns:
            int: Valor mapeado (0-100% para acelerador/freio, -100 a +100% para direção)
        """
        cal_data = self.calibration_data.get(component)
        if not cal_data:
            return 0

        if component in ["THROTTLE", "BRAKE"]:
            min_val = cal_data["min"]
            max_val = cal_data["max"]

            # Garante min < max para mapeamento correto
            if min_val > max_val:
                min_val, max_val = max_val, min_val

            # Restringe valor bruto
            raw_value = max(min_val, min(max_val, raw_value))

            # Mapeia para 0-100%
            if max_val == min_val:
                return 0
            percent = int(((raw_value - min_val) / (max_val - min_val)) * 100)

            return max(0, min(100, percent))

        elif component == "STEERING":
            left_val = cal_data["left"]
            center_val = cal_data["center"]
            right_val = cal_data["right"]

            # Restringe valor bruto
            raw_value = max(left_val, min(right_val, raw_value))

            # Mapeia para -100 a +100%
            if raw_value < center_val:
                # Lado esquerdo: left_val até center_val mapeia para -100% a 0%
                if center_val == left_val:
                    return 0
                percent = int(((raw_value - center_val) / (center_val - left_val)) * 100)
            else:
                # Lado direito: center_val até right_val mapeia para 0% a +100%
                if right_val == center_val:
                    return 0
                percent = int(((raw_value - center_val) / (right_val - center_val)) * 100)

            return max(-100, min(100, percent))

        return 0

    def save_to_file(self) -> bool:
        """
        Salva dados de calibração em arquivo JSON

        Returns:
            bool: True se salvo com sucesso
        """
        try:
            # Adiciona metadados
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
        Carrega dados de calibração de arquivo JSON

        Returns:
            bool: True se carregado com sucesso
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

