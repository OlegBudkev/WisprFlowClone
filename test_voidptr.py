import sys
from PyQt6.QtWidgets import QApplication, QWidget

app = QApplication(sys.argv)
w = QWidget()
w.show()

# Получим любой voidptr, например, из winId() или nativeEvent
print("Тип winId():", type(w.winId()))
print("Значение winId():", w.winId())
try:
    print("Приведение к int:", int(w.winId()))
except Exception as e:
    print("Ошибка приведения winId к int:", e)

# Проверим ctypes приведение
try:
    import ctypes
    hwnd = w.winId()
    print("HWND через ctypes:", ctypes.c_void_p(int(hwnd)).value)
except Exception as e:
    print("Ошибка ctypes:", e)
