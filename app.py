import os
import sys
import time
import threading
import ctypes
import ctypes.wintypes
import keyboard
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QWidget
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QPen, QPainterPath, QLinearGradient, QBrush

# --- Проверка единственной копии (Single Instance) ---
MUTEX_NAME = "Global\\WisprFlowClone_SingleInstance_Mutex_Unique_12345"
_app_mutex = None

def check_single_instance():
    """Проверяет, запущена ли уже копия приложения с помощью именованного мьютекса Windows."""
    if sys.platform != 'win32':
        return True
    
    global _app_mutex
    try:
        kernel32 = ctypes.windll.kernel32
        # Создаем мьютекс
        _app_mutex = kernel32.CreateMutexW(None, True, MUTEX_NAME)
        last_error = kernel32.GetLastError()
        # ERROR_ALREADY_EXISTS = 183
        if last_error == 183:
            return False
        return True
    except Exception as e:
        print(f"[Single Instance] Ошибка при проверке мьютекса: {e}")
        return True

from config_loader import load_config, save_config
from recorder import AudioRecorder
from transcriber import Transcriber
from inserter import insert_text
from overlay import RecordingOverlay

def parse_hotkey_to_vks(hotkey_str):
    """Парсит строку хоткея (например, 'alt+q') в список VK-кодов Windows."""
    VK_MAP = {
        'alt': 0x12, 'ctrl': 0x11, 'control': 0x11,
        'shift': 0x10, 'win': 0x5B, 'windows': 0x5B, 'super': 0x5B,
        'space': 0x20, 'enter': 0x0D, 'tab': 0x09,
        'esc': 0x1B, 'backspace': 0x08, 'delete': 0x2E, 'insert': 0x2D,
    }
    parts = hotkey_str.lower().split('+')
    vks = []
    for part in parts:
        part = part.strip()
        if part in VK_MAP:
            vks.append(VK_MAP[part])
        elif len(part) == 1:
            vks.append(ord(part.upper()))
        elif part.startswith('f') and part[1:].isdigit():
            vks.append(0x70 + int(part[1:]) - 1)
    return vks


class KeyboardHotkeyHook:
    """
    Перехватывает хоткеи через библиотеку keyboard с suppress=True.
    Клавиши полностью поглощаются — Telegram и другие приложения не получат событие.
    """

    def __init__(self, on_hold_pressed, on_hold_released, on_toggle_pressed):
        self._on_hold_pressed   = on_hold_pressed
        self._on_hold_released  = on_hold_released
        self._on_toggle_pressed = on_toggle_pressed
        self._hold_hotkey_str   = ""
        self._toggle_hotkey_str = ""
        self._hold_active   = False
        self._toggle_active = False
        self._running = False

    def configure(self, hold_hotkey_str, toggle_hotkey_str):
        self._hold_hotkey_str   = hold_hotkey_str
        self._toggle_hotkey_str = toggle_hotkey_str
        print(f"[Hook] Hold='{hold_hotkey_str}'")
        print(f"[Hook] Toggle='{toggle_hotkey_str}'")

    def start(self):
        self._running = True
        self._register()
        print("[Hook] Хоткеи зарегистрированы с подавлением (keyboard library)")

    def stop(self):
        self._running = False
        try:
            keyboard.unhook_all()
        except Exception:
            pass

    def restart(self, hold_hotkey_str, toggle_hotkey_str):
        self.stop()
        time.sleep(0.05)
        self.configure(hold_hotkey_str, toggle_hotkey_str)
        self.start()

    def _register(self):
        # --- Hold хоткей: нажатие ---
        keyboard.add_hotkey(
            self._hold_hotkey_str,
            self._on_hold_key_down,
            suppress=True,
            trigger_on_release=False,
        )
        # --- Hold хоткей: отпускание ---
        keyboard.add_hotkey(
            self._hold_hotkey_str,
            self._on_hold_key_up,
            suppress=True,
            trigger_on_release=True,
        )
        # --- Toggle хоткей: нажатие ---
        keyboard.add_hotkey(
            self._toggle_hotkey_str,
            self._on_toggle_key_down,
            suppress=True,
            trigger_on_release=False,
        )
        # --- Toggle хоткей: отпускание ---
        keyboard.add_hotkey(
            self._toggle_hotkey_str,
            self._on_toggle_key_up,
            suppress=True,
            trigger_on_release=True,
        )

    def _on_hold_key_down(self):
        if not self._hold_active:
            self._hold_active = True
            threading.Thread(target=self._on_hold_pressed, daemon=True).start()

    def _on_hold_key_up(self):
        if self._hold_active:
            self._hold_active = False
            threading.Thread(target=self._on_hold_released, daemon=True).start()

    def _on_toggle_key_down(self):
        if not self._toggle_active:
            self._toggle_active = True
            threading.Thread(target=self._on_toggle_pressed, daemon=True).start()

    def _on_toggle_key_up(self):
        self._toggle_active = False

class HotkeySignalHelper(QObject):
    toggle_signal = pyqtSignal()
    cancel_signal = pyqtSignal()
    release_signal = pyqtSignal()

class WisprApp(QObject):
    def __init__(self):
        super().__init__()
        # Инициализируем QApplication
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setQuitOnLastWindowClosed(False)
        
        # Регистрируем AppUserModelID, чтобы Windows корректно показывала Toast-уведомления
        if sys.platform == 'win32':
            import ctypes
            try:
                myappid = "Antigravity.WisprFlowClone.1.0"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception as e:
                print(f"Не удалось установить AppUserModelID: {e}")
        
        self.config = load_config()
        
        # Инициализация рекордера с учетом сохраненного устройства
        device_index = self.config.get("device_index")
        self.recorder = AudioRecorder(device_index=device_index)
        self.transcriber = Transcriber(self.config)
        self.state = "idle" # idle, recording, processing
        self.processing_lock = threading.Lock()
        self.settings_win = None
        self.current_recording_mode = None
        
        # Сигналы для безопасного общения фонового потока хоткеев с GUI-потоком Qt
        self.signals = HotkeySignalHelper()
        self.signals.toggle_signal.connect(self.on_toggle)
        self.signals.cancel_signal.connect(self.on_cancel)
        self.signals.release_signal.connect(self.on_hotkey_hold_released_gui)
        
        # Создаём перехватчик хоткеев с подавлением (keyboard library, suppress=True)
        self.hotkey_poller = KeyboardHotkeyHook(
            on_hold_pressed=self._on_hold_pressed,
            on_hold_released=self._on_hold_released,
            on_toggle_pressed=self._on_toggle_pressed,
        )
        
        # Генерация красивых минималистичных иконок для трея
        self.icons = {
            "idle": self.create_icon_image("blue"),
            "recording": self.create_icon_image("red"),
            "processing": self.create_icon_image("orange")
        }
        
        # Устанавливаем глобальную иконку для всех окон приложения (включая панель задач)
        self.qt_app.setWindowIcon(self.icons["idle"])
        
        # Автоматически синхронизируем автозагрузку при запуске
        if self.config.get("autostart", False):
            self.sync_autostart()
            
        # Создаем оверлей и системный трей
        self.overlay = RecordingOverlay(self)
        self.init_tray()
        
    def create_icon_image(self, color):
        """Рисует стильные и современные иконки для системного трея."""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if color == "blue":
            # 1. Idle: Минималистичная звуковая волна (3 вертикальные полоски с градиентом)
            gradient = QLinearGradient(0, 0, 32, 32)
            gradient.setColorAt(0.0, QColor("#8a2be2")) # Фиолетовый
            gradient.setColorAt(1.0, QColor("#00c6ff")) # Голубой
            
            pen = QPen(QBrush(gradient), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            
            # Рисуем 3 вертикальные линии
            painter.drawLine(8, 16 - 5, 8, 16 + 5)
            painter.drawLine(16, 16 - 10, 16, 16 + 10)
            painter.drawLine(24, 16 - 5, 24, 16 + 5)
            
        elif color == "red":
            # 2. Recording: Светящийся радар записи (центральный круг и внешние круги)
            # Центральный красный круг
            painter.setBrush(QColor("#ff1744"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(12, 12, 8, 8)
            
            # Внешнее полупрозрачное кольцо
            painter.setBrush(Qt.GlobalColor.transparent)
            painter.setPen(QPen(QColor(255, 23, 68, 120), 2))
            painter.drawEllipse(7, 7, 18, 18)
            
            # Дальнее тонкое кольцо
            painter.setPen(QPen(QColor(255, 23, 68, 50), 1.5))
            painter.drawEllipse(2, 2, 28, 28)
            
        elif color == "orange":
            # 3. Processing: Две звездочки AI (Gemini style)
            def draw_sparkle(painter, cx, cy, r, color_hex):
                path = QPainterPath()
                path.moveTo(cx, cy - r)
                path.quadTo(cx, cy, cx + r, cy)
                path.quadTo(cx, cy, cx, cy + r)
                path.quadTo(cx, cy, cx - r, cy)
                path.quadTo(cx, cy, cx, cy - r)
                painter.fillPath(path, QBrush(QColor(color_hex)))
            
            # Рисуем большую звезду в центре
            draw_sparkle(painter, 14, 14, 10, "#ffaa00")
            # Рисуем маленькую звезду сбоку-сверху
            draw_sparkle(painter, 24, 8, 5, "#ffea00")
            
        painter.end()
        return QIcon(pixmap)

    def set_state(self, state):
        self.state = state
        self.tray_icon.setIcon(self.icons[state])
        status_text = {
            "idle": "Wispr: Готов",
            "recording": "Wispr: Запись...",
            "processing": "Wispr: Распознавание..."
        }
        self.tray_icon.setToolTip(status_text.get(state, "Wispr"))

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self.icons["idle"], self.qt_app)
        self.tray_icon.setToolTip("Wispr: Готов")
        
        # Клик по иконке в трее
        self.tray_icon.activated.connect(self.on_tray_activated)
        
        # Контекстное меню (правый клик)
        menu = QMenu()
        
        settings_action = QAction("Настройки...", menu)
        settings_action.triggered.connect(self.show_settings_window)
        menu.addAction(settings_action)
        
        self.llm_action = QAction("Умное форматирование (LLM)", menu, checkable=True)
        self.llm_action.setChecked(self.config.get("llm_refinement", False))
        self.llm_action.triggered.connect(self.toggle_llm_refinement)
        menu.addAction(self.llm_action)
        
        menu.addSeparator()
        
        exit_action = QAction("Выход", menu)
        exit_action.triggered.connect(self.exit_app)
        menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        # Открытие настроек при левом клике на иконку в трее
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_settings_window()

    def show_settings_window(self):
        try:
            # Открываем окно настроек, если оно еще не открыто
            if self.settings_win is None:
                from settings_window import SettingsWindow
                self.settings_win = SettingsWindow(self)
                self.settings_win.finished.connect(self.on_settings_closed)
                self.settings_win.show()
            
            self.settings_win.raise_()
            self.settings_win.activateWindow()
        except Exception as e:
            import traceback
            print("[WisprApp] ОШИБКА при открытии окна настроек:")
            traceback.print_exc()

    def on_settings_closed(self):
        self.settings_win = None

    def toggle_llm_refinement(self):
        self.config["llm_refinement"] = self.llm_action.isChecked()
        save_config(self.config)
        self.transcriber.config = self.config
        print(f"Умная обработка (LLM): {self.config['llm_refinement']}")

    def apply_new_settings(self):
        """Применяет новые настройки без перезапуска приложения."""
        self.transcriber.config = self.config
        
        # Обновляем тему оверлея
        self.overlay.apply_theme(self.config.get("theme", "dark"))
        
        # Передаем новый микрофон в рекордер
        self.recorder.device_index = self.config.get("device_index")
        
        # Синхронизируем флаг LLM в меню трея
        self.llm_action.setChecked(self.config.get("llm_refinement", False))
        
        # Перерегистрируем горячие клавиши
        self.reregister_hotkeys()
        
        print("Настройки успешно обновлены и применены.")

    def _on_hold_pressed(self):
        """Вызывается из потока поллера при нажатии hold-хоткея."""
        print("[WisprApp] Hold-хоткей НАЖАТ. Состояние приложения:", self.state)
        if self.state == "idle":
            self.current_recording_mode = "hold"
            self.signals.toggle_signal.emit()

    def _on_hold_released(self):
        """Вызывается из потока поллера при отпускании hold-хоткея."""
        print("[WisprApp] Hold-хоткей ОТПУЩЕН. Состояние приложения:", self.state)
        self.signals.release_signal.emit()

    def _on_toggle_pressed(self):
        """Вызывается из потока поллера при нажатии toggle-хоткея."""
        print("[WisprApp] Toggle-хоткей НАЖАТ. Состояние приложения:", self.state)
        if self.state == "idle":
            self.current_recording_mode = "toggle"
            self.signals.toggle_signal.emit()
        elif self.state == "recording" and self.current_recording_mode == "toggle":
            self.signals.toggle_signal.emit()

    def on_hotkey_hold_released_gui(self):
        if self.state == "recording" and self.current_recording_mode == "hold":
            self.signals.toggle_signal.emit()

    def on_toggle(self):
        if self.state == "idle":
            self.start_recording()
        elif self.state == "recording":
            self.stop_and_process()

    def on_cancel(self):
        if self.state == "recording":
            self.recorder.stop()
            self.set_state("idle")
            print("Запись отменена.")

    def cancel_recording(self):
        self.signals.cancel_signal.emit()

    def start_recording(self):
        self.set_state("recording")
        self.overlay.start()
        self.recorder.start()

    def stop_and_process(self):
        self.set_state("processing")
        self.overlay.stop()
        threading.Thread(target=self._process_audio_flow, daemon=True).start()

    def _process_audio_flow(self):
        if not self.processing_lock.acquire(blocking=False):
            return
            
        try:
            filepath = self.recorder.stop()
            if not filepath or not os.path.exists(filepath):
                self.show_no_speech_warning()
                self.set_state("idle")
                return

            if os.path.getsize(filepath) < 1000:
                self.show_no_speech_warning()
                self.set_state("idle")
                return

            text = self.transcriber.transcribe(filepath)
            
            if text:
                insert_text(text)
            else:
                self.show_no_speech_warning()
                
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass

        except Exception as e:
            print(f"Ошибка: {e}")
            self.tray_icon.showMessage(
                "Ошибка распознавания",
                str(e),
                QSystemTrayIcon.MessageIcon.Warning,
                5000
            )
        finally:
            self.set_state("idle")
            self.processing_lock.release()

    def show_no_speech_warning(self):
        """Показывает уведомление о том, что речь не была распознана."""
        self.tray_icon.showMessage(
            "Голос не распознан",
            "Не удалось разобрать речь. Попробуйте говорить немного громче и четче или проверьте микрофон в настройках.",
            QSystemTrayIcon.MessageIcon.Information,
            4500
        )

    def sync_autostart(self):
        import sys
        if sys.platform != 'win32':
            return
        import os
        import winreg
        
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "WisprFlowClone"
        
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
        else:
            exe_path = os.path.abspath(sys.argv[0])
            
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
            winreg.CloseKey(key)
            print(f"[Автозагрузка] Синхронизирован путь в реестре: {exe_path}")
        except Exception as e:
            print(f"[Автозагрузка] Ошибка при синхронизации пути: {e}")

    def register_hotkeys(self):
        hold_str = self.config.get("hotkey_hold", "alt+q")
        toggle_str = self.config.get("hotkey_toggle", "alt+a")
        print(f"Запуск поллера хоткеев: Hold='{hold_str}', Toggle='{toggle_str}'")
        self.hotkey_poller.configure(hold_str, toggle_str)
        self.hotkey_poller.start()

    def reregister_hotkeys(self):
        hold_str = self.config.get("hotkey_hold", "alt+q")
        toggle_str = self.config.get("hotkey_toggle", "alt+a")
        self.hotkey_poller.restart(hold_str, toggle_str)

    def run(self):
        self.register_hotkeys()
        print("Приложение запущено.")
        sys.exit(self.qt_app.exec())

    def exit_app(self):
        print("Выход...")
        self.tray_icon.hide()
        self.hotkey_poller.stop()
        self.qt_app.quit()
        os._exit(0)

if __name__ == "__main__":
    if not check_single_instance():
        print("Wispr уже запущен! Допускается только одна активная копия приложения.")
        sys.exit(0)
        
    app = WisprApp()
    app.run()
