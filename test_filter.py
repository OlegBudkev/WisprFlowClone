import sys
import ctypes
import ctypes.wintypes
from PyQt6.QtCore import QAbstractNativeEventFilter, QCoreApplication
from PyQt6.QtWidgets import QApplication

class TestFilter(QAbstractNativeEventFilter):
    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            try:
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == 0x0312:
                    print("Получен хоткей:", msg.wParam)
                    return True, 0
            except Exception as e:
                print("Ошибка в фильтре:", e)
        return False, 0

app = QApplication(sys.argv)
filt = TestFilter()
QCoreApplication.instance().installNativeEventFilter(filt)

# Зарегистрируем тестовый хоткей: Alt+Q (ID 1)
# MOD_ALT = 0x0001, Q = 0x51
res = ctypes.windll.user32.RegisterHotKey(0, 1, 0x0001, 0x51)
print("Регистрация хоткея Alt+Q на поток:", "Успех" if res else "Ошибка")

# Отменим при выходе
ctypes.windll.user32.UnregisterHotKey(0, 1)
print("Тест инициализации пройден успешно!")
