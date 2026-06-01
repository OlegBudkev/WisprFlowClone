import random
import time
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QApplication, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QFont, QCursor, QGuiApplication

class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setFixedHeight(30)
        self.num_bars = 40
        self.bars = [0.05] * self.num_bars
        self.target_volume = 0.05
        # Для автоусиления: храним максимальную амплитуду звука за последнее время
        self.max_observed_volume = 0.08
        
    def update_volume(self, volume):
        volume = max(0.0, volume)
        
        # Динамически подстраиваем чувствительность: медленно гасим пиковое значение,
        # но моментально поднимаем его при появлении громкого звука
        self.max_observed_volume = max(self.max_observed_volume * 0.996, volume, 0.04)
        
        # Масштабируем громкость к диапазону [0, 1] относительно максимальной
        normalized_volume = volume / self.max_observed_volume
        normalized_volume = min(normalized_volume, 1.0)
        
        # Добавляем живой микро-шум в тишине
        if normalized_volume < 0.06:
            normalized_volume += random.uniform(0.0, 0.03)
            
        self.target_volume = normalized_volume
        
        # Сдвиг волны влево и сглаживание нового значения
        self.bars.pop(0)
        last_bar = self.bars[-1] if self.bars else 0.05
        new_val = last_bar + (self.target_volume - last_bar) * 0.35
        self.bars.append(new_val)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        bar_width = 3
        gap = 2
        total_width = self.num_bars * (bar_width + gap) - gap
        start_x = (width - total_width) // 2
        center_y = height // 2
        
        # Красивый неоновый градиент для волны
        gradient = QLinearGradient(0, 0, width, 0)
        gradient.setColorAt(0.0, QColor("#a8ff78"))  # Зеленый
        gradient.setColorAt(0.5, QColor("#78ffd6"))  # Мятный
        gradient.setColorAt(1.0, QColor("#ffa07a"))  # Оранжевый
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        
        for i, val in enumerate(self.bars):
            # Высота столбика
            bar_height = max(2.0, val * height * 0.95)
            x = start_x + i * (bar_width + gap)
            y = center_y - bar_height / 2
            
            painter.drawRoundedRect(x, int(y), bar_width, int(bar_height), 1.5, 1.5)

class RecordingOverlay(QWidget):
    def __init__(self, app_instance, parent=None):
        super().__init__(parent)
        self.app_instance = app_instance
        self.drag_position = QPoint()
        self.theme_name = self.app_instance.config.get("theme", "dark")
        
        # Настройка флагов окна: без рамок, поверх всех, не берет фокус ввода
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Увеличиваем размер окна, чтобы поместилась тень (отступы по 15px с каждой стороны)
        self.setFixedSize(360 + 30, 60 + 30)
        
        self.init_ui()
        self.apply_theme(self.theme_name)
        self.center_on_screen()
        
        # Таймеры
        self.wave_timer = QTimer(self)
        self.wave_timer.timeout.connect(self.update_wave)
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_time)
        
        self.start_time = 0
        
    def init_ui(self):
        # Контейнер внутри окна, смещенный на 15px для отображения тени
        self.container = QWidget(self)
        self.container.setGeometry(15, 15, 360, 60)
        
        # Добавляем мягкую глубокую тень
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setColor(QColor(0, 0, 0, 75))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)
        
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(15, 5, 15, 5)
        layout.setSpacing(12)
        
        # 1. Аудио-волна
        self.waveform = WaveformWidget(self.container)
        self.waveform.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.waveform)
        
        # 2. Таймер
        self.timer_label = QLabel("0:00", self.container)
        self.timer_label.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        layout.addWidget(self.timer_label)
        
        # 3. Кнопка отмены (крестик)
        self.cancel_btn = QPushButton("×", self.container)
        self.cancel_btn.setFixedSize(24, 24)
        self.cancel_btn.setFont(QFont("Segoe UI", 13))
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout.addWidget(self.cancel_btn)
        self.cancel_btn.clicked.connect(self.cancel_recording)
        
    def apply_theme(self, theme_name):
        self.theme_name = theme_name
        if theme_name == "light":
            # Светлая Apple-style тема
            self.container.setStyleSheet("""
                QWidget {
                    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f6f6f9);
                    border: 1px solid rgba(0, 0, 0, 0.08);
                    border-radius: 16px;
                }
            """)
            self.timer_label.setStyleSheet("color: #1d1d1f; background: transparent; border: none;")
            self.cancel_btn.setStyleSheet("""
                QPushButton {
                    color: rgba(0, 0, 0, 0.4);
                    background-color: rgba(0, 0, 0, 0.04);
                    border: none;
                    border-radius: 12px;
                }
                QPushButton:hover {
                    color: #000000;
                    background-color: rgba(255, 23, 68, 0.12);
                }
            """)
        else:
            # Премиальная темная тема
            self.container.setStyleSheet("""
                QWidget {
                    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a1a1c, stop:1 #111113);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 16px;
                }
            """)
            self.timer_label.setStyleSheet("color: #ffffff; background: transparent; border: none;")
            self.cancel_btn.setStyleSheet("""
                QPushButton {
                    color: rgba(255, 255, 255, 0.4);
                    background-color: rgba(255, 255, 255, 0.04);
                    border: none;
                    border-radius: 12px;
                }
                QPushButton:hover {
                    color: #ffffff;
                    background-color: rgba(255, 23, 68, 0.2);
                }
            """)

    def center_on_screen(self):
        screen = QGuiApplication.screenAt(QCursor.pos())
        if not screen:
            screen = QApplication.primaryScreen()
        
        screen_geo = screen.geometry()
        x = screen_geo.x() + (screen_geo.width() - self.width()) // 2
        y = screen_geo.y() + (screen_geo.height() - self.height()) // 2
        self.move(x, y)
        
    def start(self):
        # Принудительно считываем текущую тему из конфига перед каждым показом
        current_theme = self.app_instance.config.get("theme", "dark")
        if current_theme != self.theme_name:
            self.apply_theme(current_theme)
            
        self.start_time = time.time()
        self.timer_label.setText("0:00")
        self.center_on_screen()
        self.show()
        self.center_on_screen()
        self.wave_timer.start(40)  # ~25 FPS
        self.time_timer.start(500)
        
    def stop(self):
        self.wave_timer.stop()
        self.time_timer.stop()
        self.hide()
        
    def cancel_recording(self):
        self.stop()
        self.app_instance.cancel_recording()
        
    def update_wave(self):
        volume = 0.0
        if self.app_instance.recorder:
            volume = self.app_instance.recorder.get_volume()
        self.waveform.update_volume(volume)
        
    def update_time(self):
        elapsed = int(time.time() - self.start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        self.timer_label.setText(f"{minutes}:{seconds:02d}")
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
