"""
auto_save.py - Sistema de auto-save de logs e dados de sensores
"""

import os
import tkinter as tk
from datetime import datetime

from ..utils.constants import (
    AUTO_EXPORT_DIR,
    MAX_LOG_LINES,
    MIN_LOGS_FOR_SAVE,
    MIN_SENSORS_FOR_SAVE,
)


class AutoSaveManager:
    """Gerencia auto-save periódico de logs e dados de sensores"""

    def __init__(self, console):
        """
        Args:
            console: Instância de ConsoleInterface
        """
        self.console = console
        self.last_log_count = 0
        self.last_sensor_count = 0

    def auto_export_on_limit(self):
        """Exporta automaticamente logs e dados quando o limite é atingido"""
        try:
            # Cria diretório de export automático se não existir
            os.makedirs(AUTO_EXPORT_DIR, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 1. Exporta logs do console
            log_filename = os.path.join(AUTO_EXPORT_DIR, f"logs_{timestamp}.txt")
            try:
                log_content = self.console.log_text.get("1.0", tk.END)
                with open(log_filename, "w", encoding="utf-8") as f:
                    f.write("# F1 Client - Auto Export (Limite atingido)\n")
                    f.write(
                        f"# Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
                    f.write(f"# Linhas: {MAX_LOG_LINES}\n")
                    f.write("#" + "=" * 60 + "\n\n")
                    f.write(log_content)
            except Exception as e:
                print(f"Erro ao exportar logs: {e}")

            # 2. Exporta dados de sensores (Pickle - mais rápido que CSV)
            if self.console.sensor_display:
                sensor_filename = os.path.join(
                    AUTO_EXPORT_DIR, f"sensors_{timestamp}.pkl"
                )
                try:
                    self.console.sensor_display.export_history_fast(sensor_filename)
                except Exception:
                    pass

            # Log discreto
            print(f"[AUTO-EXPORT] Dados salvos em: {AUTO_EXPORT_DIR}/")

        except Exception as e:
            print(f"[AUTO-EXPORT] Erro: {e}")

    def periodic_auto_save(self):
        """Auto-save periódico a cada 20 segundos (apenas se houver dados novos)"""
        if not self.console.is_running:
            return

        try:
            has_new_data = False

            # Verifica se há novos logs
            current_log_count = 0
            if hasattr(self.console, "log_text") and self.console.log_text:
                try:
                    current_log_count = int(
                        self.console.log_text.index("end-1c").split(".")[0]
                    )
                except Exception:
                    pass

            # Verifica se há novos dados de sensores
            current_sensor_count = 0
            if self.console.sensor_display and hasattr(
                self.console.sensor_display, "history"
            ):
                try:
                    current_sensor_count = len(
                        self.console.sensor_display.history.get("timestamp", [])
                    )
                except Exception:
                    pass

            # Só salva se houver dados significativos
            if (
                current_log_count >= MIN_LOGS_FOR_SAVE
                or current_sensor_count >= MIN_SENSORS_FOR_SAVE
            ) and (
                current_log_count > self.last_log_count
                or current_sensor_count > self.last_sensor_count
            ):
                has_new_data = True
                self.last_log_count = current_log_count
                self.last_sensor_count = current_sensor_count

            if has_new_data:
                os.makedirs(AUTO_EXPORT_DIR, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                saved_logs = False
                saved_sensors = False

                # Salva logs apenas se tiver quantidade mínima
                if current_log_count >= MIN_LOGS_FOR_SAVE:
                    log_filename = os.path.join(
                        AUTO_EXPORT_DIR, f"logs_{timestamp}.txt"
                    )
                    try:
                        log_content = self.console.log_text.get("1.0", tk.END)
                        with open(log_filename, "w", encoding="utf-8") as f:
                            f.write("# F1 Client - Auto Save (20s)\n")
                            f.write(
                                f"# Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            )
                            f.write(f"# Linhas: {current_log_count}\n")
                            f.write("#" + "=" * 60 + "\n\n")
                            f.write(log_content)
                        saved_logs = True
                    except Exception:
                        pass

                # Salva sensores apenas se tiver quantidade mínima
                if current_sensor_count >= MIN_SENSORS_FOR_SAVE and self.console.sensor_display:
                    sensor_filename = os.path.join(
                        AUTO_EXPORT_DIR, f"sensors_{timestamp}.pkl"
                    )
                    try:
                        self.console.sensor_display.export_history_fast(sensor_filename)
                        saved_sensors = True
                    except Exception:
                        pass

                # Log apenas do que foi salvo
                saved_items = []
                if saved_logs:
                    saved_items.append(f"{current_log_count} logs")
                if saved_sensors:
                    saved_items.append(f"{current_sensor_count} sensores")

                if saved_items:
                    print(f"[AUTO-SAVE] {', '.join(saved_items)} -> {AUTO_EXPORT_DIR}/")

                # Reset apenas do que foi salvo
                try:
                    if saved_logs and self.console.log_text:
                        self.console.log_text.delete("1.0", tk.END)
                        self.last_log_count = 0
                    if saved_sensors and self.console.sensor_display:
                        self.console.sensor_display.reset_statistics()
                        self.last_sensor_count = 0
                except Exception:
                    pass

        except Exception as e:
            print(f"[AUTO-SAVE] Erro: {e}")

        # Reagenda próximo auto-save
        if self.console.is_running and self.console.root:
            try:
                from ..utils.constants import AUTO_SAVE_INTERVAL

                self.console.root.after(AUTO_SAVE_INTERVAL, self.periodic_auto_save)
            except Exception:
                pass
