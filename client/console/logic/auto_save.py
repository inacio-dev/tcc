"""
auto_save.py - Sistema de auto-save de logs, dados de sensores e telemetria

Arquivos salvos em exports/auto/:
- logs_YYYYMMDD_HHMMSS.txt - Logs do console
- sensors_YYYYMMDD_HHMMSS.pkl - Dados brutos dos sensores
- telemetry_YYYYMMDD_HHMMSS.pkl - Dados dos gráficos de telemetria
"""

import os
import threading
import tkinter as tk
from datetime import datetime

from ..utils.constants import (
    AUTO_EXPORT_DIR,
    MAX_LOG_LINES,
    MIN_LOGS_FOR_SAVE,
    MIN_SENSORS_FOR_SAVE,
    MIN_TELEMETRY_FOR_SAVE,
)


class AutoSaveManager:
    """Gerencia auto-save periódico de logs, dados de sensores e telemetria"""

    def __init__(self, console):
        """
        Args:
            console: Instância de ConsoleInterface
        """
        self.console = console
        self.last_log_count = 0
        self.last_sensor_count = 0
        self.last_telemetry_count = 0

    def auto_export_on_limit(self):
        """Exporta automaticamente logs e dados quando o limite é atingido.
        Snapshot rápido na thread UI, I/O em thread background."""
        try:
            os.makedirs(AUTO_EXPORT_DIR, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Snapshot rápido na thread UI
            log_snapshot = None
            try:
                log_snapshot = self.console.log_text.get("1.0", tk.END)
            except Exception:
                pass

            sensor_snapshot = None
            if self.console.sensor_display:
                try:
                    sd = self.console.sensor_display
                    with sd.data_lock:
                        if len(sd.history.get("timestamp", [])) > 0:
                            sensor_snapshot = {
                                k: list(v) for k, v in sd.history.items()
                            }
                except Exception:
                    pass

            telemetry_snapshot = None
            if (
                hasattr(self.console, "telemetry_plotter")
                and self.console.telemetry_plotter
            ):
                try:
                    telemetry_snapshot = self.console.telemetry_plotter.get_data_dict()
                except Exception:
                    pass

            # I/O em thread background
            def _write_files():
                try:
                    if log_snapshot is not None:
                        log_filename = os.path.join(
                            AUTO_EXPORT_DIR, f"logs_{timestamp}.txt"
                        )
                        with open(log_filename, "w", encoding="utf-8") as f:
                            f.write("# F1 Client - Auto Export (Limite atingido)\n")
                            f.write(
                                f"# Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            )
                            f.write(f"# Linhas: {MAX_LOG_LINES}\n")
                            f.write("#" + "=" * 60 + "\n\n")
                            f.write(log_snapshot)

                    if sensor_snapshot is not None:
                        import pickle

                        sensor_filename = os.path.join(
                            AUTO_EXPORT_DIR, f"sensors_{timestamp}.pkl"
                        )
                        with open(sensor_filename, "wb") as f:
                            pickle.dump(
                                sensor_snapshot,
                                f,
                                protocol=pickle.HIGHEST_PROTOCOL,
                            )

                    if telemetry_snapshot is not None:
                        import pickle

                        telemetry_filename = os.path.join(
                            AUTO_EXPORT_DIR, f"telemetry_{timestamp}.pkl"
                        )
                        with open(telemetry_filename, "wb") as f:
                            pickle.dump(telemetry_snapshot, f)

                    print(f"[AUTO-EXPORT] Dados salvos em: {AUTO_EXPORT_DIR}/")
                except Exception as e:
                    print(f"[AUTO-EXPORT] Erro I/O: {e}")

            thread = threading.Thread(target=_write_files, daemon=True)
            thread.start()

        except Exception as e:
            print(f"[AUTO-EXPORT] Erro: {e}")

    def periodic_auto_save(self):
        """Auto-save periódico a cada 20 segundos (apenas se houver dados novos).
        Coleta snapshots rápidos na thread UI, faz I/O em thread background."""
        if not self.console.is_running:
            return

        try:
            # --- Fase 1: Contagem rápida (thread UI) ---
            current_log_count = 0
            if hasattr(self.console, "log_text") and self.console.log_text:
                try:
                    current_log_count = int(
                        self.console.log_text.index("end-1c").split(".")[0]
                    )
                except Exception:
                    pass

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

            current_telemetry_count = 0
            if (
                hasattr(self.console, "telemetry_plotter")
                and self.console.telemetry_plotter
            ):
                try:
                    current_telemetry_count = (
                        self.console.telemetry_plotter.get_data_count()
                    )
                except Exception:
                    pass

            # Só salva se houver dados significativos e novos
            has_new_data = (
                current_log_count >= MIN_LOGS_FOR_SAVE
                or current_sensor_count >= MIN_SENSORS_FOR_SAVE
                or current_telemetry_count >= MIN_TELEMETRY_FOR_SAVE
            ) and (
                current_log_count > self.last_log_count
                or current_sensor_count > self.last_sensor_count
                or current_telemetry_count > self.last_telemetry_count
            )

            if not has_new_data:
                self._schedule_next()
                return

            self.last_log_count = current_log_count
            self.last_sensor_count = current_sensor_count
            self.last_telemetry_count = current_telemetry_count

            # --- Fase 2: Snapshot rápido dos dados (thread UI, sem I/O) ---
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs(AUTO_EXPORT_DIR, exist_ok=True)

            # Snapshot de logs (leitura do widget Tk — rápida, ~1ms)
            log_snapshot = None
            if current_log_count >= MIN_LOGS_FOR_SAVE:
                try:
                    log_snapshot = self.console.log_text.get("1.0", tk.END)
                except Exception:
                    pass

            # Snapshot de sensores (cópia sob lock — rápida, ~5ms)
            sensor_snapshot = None
            if (
                current_sensor_count >= MIN_SENSORS_FOR_SAVE
                and self.console.sensor_display
            ):
                try:
                    sd = self.console.sensor_display
                    with sd.data_lock:
                        if len(sd.history.get("timestamp", [])) > 0:
                            sensor_snapshot = {
                                k: list(v) for k, v in sd.history.items()
                            }
                except Exception:
                    pass

            # Snapshot de telemetria (cópia de listas — rápida, ~2ms)
            telemetry_snapshot = None
            if current_telemetry_count >= MIN_TELEMETRY_FOR_SAVE:
                try:
                    telemetry_snapshot = self.console.telemetry_plotter.get_data_dict()
                except Exception:
                    pass

            # --- Fase 3: I/O em thread background (não bloqueia UI) ---
            def _write_files():
                saved_items = []
                try:
                    if log_snapshot is not None:
                        log_filename = os.path.join(
                            AUTO_EXPORT_DIR, f"logs_{timestamp}.txt"
                        )
                        with open(log_filename, "w", encoding="utf-8") as f:
                            f.write("# F1 Client - Auto Save (20s)\n")
                            f.write(
                                f"# Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            )
                            f.write(f"# Linhas: {current_log_count}\n")
                            f.write("#" + "=" * 60 + "\n\n")
                            f.write(log_snapshot)
                        saved_items.append(f"{current_log_count} logs")

                    if sensor_snapshot is not None:
                        import pickle

                        sensor_filename = os.path.join(
                            AUTO_EXPORT_DIR, f"sensors_{timestamp}.pkl"
                        )
                        with open(sensor_filename, "wb") as f:
                            pickle.dump(
                                sensor_snapshot,
                                f,
                                protocol=pickle.HIGHEST_PROTOCOL,
                            )
                        saved_items.append(f"{current_sensor_count} sensores")

                    if telemetry_snapshot is not None:
                        import pickle

                        telemetry_filename = os.path.join(
                            AUTO_EXPORT_DIR, f"telemetry_{timestamp}.pkl"
                        )
                        with open(telemetry_filename, "wb") as f:
                            pickle.dump(telemetry_snapshot, f)
                        saved_items.append(
                            f"{current_telemetry_count} telemetria"
                        )

                    if saved_items:
                        print(
                            f"[AUTO-SAVE] {', '.join(saved_items)}"
                            f" -> {AUTO_EXPORT_DIR}/"
                        )
                except Exception as e:
                    print(f"[AUTO-SAVE] Erro I/O: {e}")

                # Reset na thread UI (Tkinter não é thread-safe)
                try:
                    if self.console.is_running and self.console.root:
                        self.console.root.after(0, lambda: self._reset_after_save(
                            log_snapshot is not None,
                            sensor_snapshot is not None,
                            telemetry_snapshot is not None,
                        ))
                except Exception:
                    pass

            thread = threading.Thread(target=_write_files, daemon=True)
            thread.start()

        except Exception as e:
            print(f"[AUTO-SAVE] Erro: {e}")

        self._schedule_next()

    def _reset_after_save(self, reset_logs, reset_sensors, reset_telemetry):
        """Reseta dados após save bem-sucedido (executado na thread UI)"""
        try:
            if reset_logs and self.console.log_text:
                self.console.log_text.delete("1.0", tk.END)
                self.last_log_count = 0
            if reset_sensors and self.console.sensor_display:
                self.console.sensor_display.reset_statistics()
                self.last_sensor_count = 0
            if reset_telemetry and self.console.telemetry_plotter:
                self.console.telemetry_plotter.reset()
                self.last_telemetry_count = 0
        except Exception:
            pass

    def _schedule_next(self):
        """Reagenda próximo auto-save"""
        if self.console.is_running and self.console.root:
            try:
                from ..utils.constants import AUTO_SAVE_INTERVAL

                self.console.root.after(AUTO_SAVE_INTERVAL, self.periodic_auto_save)
            except Exception:
                pass
