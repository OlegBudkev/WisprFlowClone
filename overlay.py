import random
import time
import math
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QApplication, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QFont, QCursor, QGuiApplication

class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setFixedHeight(30)
        self.num_bars = 30
        self.bars = [0.05] * self.num_bars
        self.target_volume = 0.05
        # Для автоусиления: держим порог низким чтобы даже тихий микрофон хорошо отображался
        self.max_observed_volume = 0.02
        
    def update_volume(self, volume):
        volume = max(0.0, volume)
        
        # Динамически подстраиваем чувствительность (агрессивное усиление для слабых микрофонов)
        self.max_observed_volume = max(self.max_observed_volume * 0.990, volume, 0.02)
        # Усиливаем сигнал в 1.5x для лучшей видимости
        normalized_volume = min((volume / self.max_observed_volume) * 1.5, 1.0)
        
        # Обновляем каждый столбик независимо для эффекта "прыгающих" по центру полосок
        for i in range(self.num_bars):
            # Симметричный коэффициент высоты (синусоидальная арка с пиком в центре)
            shape_factor = math.sin(math.pi * (i + 0.5) / self.num_bars)
            
            # Живой шум/колебания для естественности
            if normalized_volume > 0.05:
                jitter = random.uniform(0.6, 1.4)
                target = normalized_volume * shape_factor * jitter
            else:
                # В тишине - легкое естественное колыхание
                jitter = random.uniform(0.1, 0.4)
                target = 0.06 * shape_factor * jitter
                
            # Сглаживание движения столбиков
            self.bars[i] = self.bars[i] + (target - self.bars[i]) * 0.25
            self.bars[i] = max(0.04, min(self.bars[i], 1.0))
            
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        bar_width = 4
        gap = 3
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
            
            painter.drawRoundedRect(x, int(y), bar_width, int(bar_height), 2.0, 2.0)

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
        layout.setSpacing(0)  # Убираем дефолтный spacing для жесткого контроля геометрии
        
        # 1. Левая зона (таймер) шириной 50px
        self.timer_container = QWidget(self.container)
        self.timer_container.setFixedWidth(50)
        self.timer_container.setStyleSheet("background: transparent; border: none;")
        timer_layout = QHBoxLayout(self.timer_container)
        timer_layout.setContentsMargins(0, 0, 0, 0)
        timer_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        
        self.timer_label = QLabel("0:00", self.timer_container)
        self.timer_label.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        timer_layout.addWidget(self.timer_label)
        layout.addWidget(self.timer_container)
        
        # 2. Центральная зона (аудио-волна)
        self.waveform = WaveformWidget(self.container)
        self.waveform.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.waveform)
        
        # 3. Правая зона (кнопка отмены) шириной 50px
        self.cancel_container = QWidget(self.container)
        self.cancel_container.setFixedWidth(50)
        self.cancel_container.setStyleSheet("background: transparent; border: none;")
        cancel_layout = QHBoxLayout(self.cancel_container)
        cancel_layout.setContentsMargins(0, 0, 0, 0)
        cancel_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        
        self.cancel_btn = QPushButton("×", self.cancel_container)
        self.cancel_btn.setFixedSize(24, 24)
        # Шрифт Arial рендерит знак × более отцентрированным, чем Segoe UI
        self.cancel_btn.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        cancel_layout.addWidget(self.cancel_btn)
        layout.addWidget(self.cancel_container)
        
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
                    padding-bottom: 2px;
                    padding-right: 0.5px;
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
                    padding-bottom: 2px;
                    padding-right: 0.5px;
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
