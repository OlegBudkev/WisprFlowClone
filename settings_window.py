import sys
import sounddevice as sd
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QLineEdit, QCheckBox, QPushButton, QGroupBox, QFormLayout, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QKeySequence

from config_loader import save_config, get_api_key

class HotkeyLineEdit(QLineEdit):
    """Кастомное поле ввода для автоматического захвата комбинации клавиш."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Нажмите клавиши...")
        self.setReadOnly(True)

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        
        # Игнорируем одиночные нажатия клавиш-модификаторов
        if key in [Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta]:
            return
            
        parts = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("windows")
            
        # Определяем клавишу
        key_name = ""
        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
            key_name = f"f{key - Qt.Key.Key_F1 + 1}"
        elif key == Qt.Key.Key_Space:
            key_name = "space"
        elif key == Qt.Key.Key_CapsLock:
            key_name = "caps lock"
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            key_name = "enter"
        elif key == Qt.Key.Key_Backspace:
            key_name = "backspace"
        elif key == Qt.Key.Key_Tab:
            key_name = "tab"
        elif key == Qt.Key.Key_Escape:
            key_name = "esc"
        elif key == Qt.Key.Key_Delete:
            key_name = "delete"
        elif key == Qt.Key.Key_Insert:
            key_name = "insert"
        else:
            text = event.text().lower()
            if text and not text.isspace():
                key_name = text
            else:
                # Откатываемся на QKeySequence
                key_name = QKeySequence(key).toString().lower()

        if key_name:
            parts.append(key_name)
            
        hotkey_str = "+".join(parts)
        if hotkey_str:
            self.setText(hotkey_str)
            
    def mousePressEvent(self, event):
        # При клике очищаем поле
        if event.button() == Qt.MouseButton.LeftButton:
            self.clear()
            super().mousePressEvent(event)

class SettingsWindow(QDialog):
    def __init__(self, app_instance, parent=None):
        super().__init__(parent)
        self.app_instance = app_instance
        self.config = self.app_instance.config
        
        self.setWindowTitle("Настройки Wispr Clone")
        self.setFixedSize(460, 550)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        # Установка иконки окна
        if hasattr(self.app_instance, "icons") and "idle" in self.app_instance.icons:
            self.setWindowIcon(self.app_instance.icons["idle"])
        
        self.init_ui()
        self.load_settings_into_ui()
        self.apply_theme_qss()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        
        # 1. Группа "Распознавание (STT)"
        stt_group = QGroupBox("Распознавание речи (STT)", self)
        stt_layout = QFormLayout(stt_group)
        stt_layout.setSpacing(8)
        
        self.provider_combo = QComboBox(self)
        self.provider_combo.addItems(["Groq API (Облако)", "OpenAI API (Облако)", "Локальный Whisper"])
        self.provider_combo.currentIndexChanged.connect(self.on_provider_changed)
        stt_layout.addRow("Провайдер:", self.provider_combo)
        
        self.api_key_input = QLineEdit(self)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        stt_layout.addRow("API Ключ:", self.api_key_input)
        
        self.model_combo = QComboBox(self)
        self.model_combo.setEditable(True)
        stt_layout.addRow("Модель:", self.model_combo)
        
        main_layout.addWidget(stt_group)
        
        # 2. Группа "Аудиозапись"
        audio_group = QGroupBox("Аудиозапись", self)
        audio_layout = QFormLayout(audio_group)
        audio_layout.setSpacing(8)
        
        self.device_combo = QComboBox(self)
        self.populate_audio_devices()
        audio_layout.addRow("Микрофон:", self.device_combo)
        
        main_layout.addWidget(audio_group)
        
        # 3. Группа "Интерфейс и Горячие клавиши"
        ui_group = QGroupBox("Интерфейс и клавиши", self)
        ui_layout = QFormLayout(ui_group)
        ui_layout.setSpacing(8)
        
        self.hotkey_hold_input = HotkeyLineEdit(self)
        ui_layout.addRow("Клавиша удержания (Hold):", self.hotkey_hold_input)
        
        self.hotkey_toggle_input = HotkeyLineEdit(self)
        ui_layout.addRow("Клавиша Старт/Стоп (Toggle):", self.hotkey_toggle_input)
        
        self.theme_combo = QComboBox(self)
        self.theme_combo.addItem("Темная тема", "dark")
        self.theme_combo.addItem("Светлая тема", "light")
        ui_layout.addRow("Тема оверлея:", self.theme_combo)
        
        self.llm_check = QCheckBox("Включить умную обработку (LLM)", self)
        ui_layout.addRow("", self.llm_check)
        
        self.autostart_check = QCheckBox("Запускать при старте Windows (Автозагрузка)", self)
        ui_layout.addRow("", self.autostart_check)
        
        main_layout.addWidget(ui_group)
        
        # Кнопки "Сохранить" и "Отмена"
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.save_btn = QPushButton("Сохранить", self)
        self.save_btn.clicked.connect(self.save_settings)
        self.save_btn.setDefault(True)
        
        self.cancel_btn = QPushButton("Отмена", self)
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

    def populate_audio_devices(self):
        self.device_combo.clear()
        self.device_combo.addItem("Устройство по умолчанию (Windows)", None)
        
        try:
            devices = sd.query_devices()
            default_device = sd.query_devices(kind='input')
            default_idx = default_device.get('index', -1) if isinstance(default_device, dict) else -1
            hostapis = sd.query_hostapis()
            
            all_inputs = []
            wasapi_inputs = []
            
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    name = dev['name']
                    try:
                        name = name.encode('cp1251').decode('utf-8')
                    except Exception:
                        pass
                    
                    api_name = hostapis[dev['hostapi']]['name']
                    api_name = api_name.replace("Windows ", "")  # "Windows WASAPI" -> "WASAPI"
                    
                    item = {
                        "index": i,
                        "name": name,
                        "api": api_name,
                        "is_default": i == default_idx
                    }
                    
                    all_inputs.append(item)
                    if api_name == "WASAPI":
                        wasapi_inputs.append(item)
            
            # Если есть современные WASAPI-устройства, показываем только их (прячем дубли MME/DirectSound)
            # Иначе показываем вообще все, что есть в системе, как резервный вариант
            filtered_inputs = wasapi_inputs if wasapi_inputs else all_inputs
            
            for item in filtered_inputs:
                label = f"{item['name']} [{item['api']}] (Индекс: {item['index']})"
                if item['is_default']:
                    label += " [По умолчанию]"
                self.device_combo.addItem(label, item['index'])
        except Exception as e:
            print(f"Ошибка при получении списка микрофонов: {e}")

    def on_provider_changed(self, index):
        self.model_combo.clear()
        provider_text = self.provider_combo.itemText(index)
        
        if "Groq" in provider_text:
            self.model_combo.addItems(["whisper-large-v3", "whisper-large-v3-turbo"])
            self.api_key_input.setEnabled(True)
            # Заполняем ключ
            key = self.config.get("api_keys", {}).get("groq", "")
            self.api_key_input.setText("" if "YOUR_" in key else key)
        elif "OpenAI" in provider_text:
            self.model_combo.addItems(["whisper-1"])
            self.api_key_input.setEnabled(True)
            key = self.config.get("api_keys", {}).get("openai", "")
            self.api_key_input.setText("" if "YOUR_" in key else key)
        else: # Локальный Whisper
            self.model_combo.addItems(["base", "small", "tiny", "medium", "large-v3"])
            self.api_key_input.setEnabled(False)
            self.api_key_input.setText("Ключ не требуется")

    def load_settings_into_ui(self):
        # 1. Загрузка провайдера
        provider = self.config.get("stt_provider", "groq")
        if provider == "groq":
            self.provider_combo.setCurrentIndex(0)
        elif provider == "openai":
            self.provider_combo.setCurrentIndex(1)
        else:
            self.provider_combo.setCurrentIndex(2)
            
        self.on_provider_changed(self.provider_combo.currentIndex())
        
        # 2. Загрузка модели
        model = self.config.get("stt_model", "")
        if model:
            idx = self.model_combo.findText(model)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            else:
                self.model_combo.setEditText(model)
                
        # 3. Загрузка микрофона
        device_index = self.config.get("device_index")
        if device_index is not None:
            idx = self.device_combo.findData(device_index)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
                
        # 4. Загрузка горячих клавиш
        self.hotkey_hold_input.setText(self.config.get("hotkey_hold", "alt+q"))
        self.hotkey_toggle_input.setText(self.config.get("hotkey_toggle", "alt+a"))
        
        # 5. Тема
        theme = self.config.get("theme", "dark")
        idx = self.theme_combo.findData(theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
            
        # 6. Чекбокс умной обработки
        self.llm_check.setChecked(self.config.get("llm_refinement", False))
        
        # 7. Чекбокс автозагрузки
        self.autostart_check.setChecked(self.config.get("autostart", False))

    def save_settings(self):
        # 1. Считываем провайдера
        provider_idx = self.provider_combo.currentIndex()
        provider_map = {0: "groq", 1: "openai", 2: "local"}
        provider = provider_map[provider_idx]
        self.config["stt_provider"] = provider
        
        # 2. Считываем API-ключи
        key = self.api_key_input.text().strip()
        if provider == "groq" and key and "Ключ не" not in key:
            self.config["api_keys"]["groq"] = key
        elif provider == "openai" and key and "Ключ не" not in key:
            self.config["api_keys"]["openai"] = key
            
        # 3. Модель
        self.config["stt_model"] = self.model_combo.currentText().strip()
        
        # 4. Микрофон
        self.config["device_index"] = self.device_combo.currentData()
        
        # 5. Хоткеи
        self.config["hotkey_hold"] = self.hotkey_hold_input.text().strip()
        self.config["hotkey_toggle"] = self.hotkey_toggle_input.text().strip()
        
        # 6. Тема
        self.config["theme"] = self.theme_combo.currentData()
        
        # 7. Чекбокс LLM
        self.config["llm_refinement"] = self.llm_check.isChecked()
        
        # 8. Чекбокс автозагрузки
        autostart = self.autostart_check.isChecked()
        self.config["autostart"] = autostart
        self.update_autostart_registry(autostart)
        
        # Сохраняем в файл
        save_config(self.config)
        
        # Применяем в приложении
        self.app_instance.apply_new_settings()
        self.accept()

    def update_autostart_registry(self, enabled):
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
            if enabled:
                # Берем путь в двойные кавычки на случай пробелов в пути к файлу
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
                print(f"[Автозагрузка] Добавлено в реестр: {exe_path}")
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    print("[Автозагрузка] Удалено из реестра")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[Автозагрузка] Ошибка реестра Windows: {e}")

    def apply_theme_qss(self):
        """Стилизует окно настроек в стильный темный вид."""
        self.setStyleSheet("""
            QDialog {
                background-color: #161618;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 12px;
            }
            QGroupBox {
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
                font-weight: bold;
                color: #a8ff78;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
            QLineEdit, QComboBox {
                background-color: #222225;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 4px;
                padding: 5px;
                color: #ffffff;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #78ffd6;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #222225;
                color: #ffffff;
                selection-background-color: #a8ff78;
                selection-color: #161618;
                border: 1px solid rgba(255, 255, 255, 0.12);
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 8px;
            }
            QPushButton {
                background-color: #222225;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 4px;
                padding: 6px 16px;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2a2a2f;
                border: 1px solid #a8ff78;
            }
            QPushButton:default {
                background-color: #a8ff78;
                color: #161618;
                border: none;
            }
            QPushButton:default:hover {
                background-color: #78ffd6;
            }
        """)

if __name__ == "__main__":
    # Проверка работы GUI в изоляции
    app = QApplication(sys.argv)
    class DummyApp:
        def __init__(self):
            self.config = {
                "stt_provider": "groq",
                "stt_model": "whisper-large-v3",
                "hotkey": "ctrl+shift+space",
                "theme": "dark",
                "device_index": None,
                "api_keys": {"groq": "", "openai": ""}
            }
        def apply_new_settings(self):
            print("Настройки применены!")
            
    win = SettingsWindow(DummyApp())
    win.show()
    sys.exit(app.exec())
