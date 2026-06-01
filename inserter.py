import time
import pyperclip
import ctypes

def insert_text(text):
    if not text:
        return
        
    print(f"Вставка текста: {text[:50]}...")
    
    try:
        # Записываем новый текст в буфер обмена
        pyperclip.copy(text)
        
        # Ждем обновления буфера обмена
        time.sleep(0.05)
        
        # Нативные константы Windows API
        KEYEVENTF_KEYUP = 0x0002
        VK_CONTROL = 0x11
        VK_V = 0x56
        VK_MENU = 0x12  # Клавиша Alt
        
        # Нативно отпускаем Alt (если он зажат при Alt+Q / Alt+A),
        # чтобы Windows не восприняла вставку как Ctrl + Alt + V
        ctypes.windll.user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.01)
        
        # Эмулируем нажатие Ctrl+V
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)  # Ctrl Down
        ctypes.windll.user32.keybd_event(VK_V, 0, 0, 0)        # V Down
        
        time.sleep(0.01)
        
        ctypes.windll.user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)        # V Up
        ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)  # Ctrl Up
        
        # Даем операционной системе время завершить операцию вставки
        time.sleep(0.15)
        
    except Exception as e:
        print(f"Ошибка при нативной вставке текста: {e}")
