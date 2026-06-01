import time
import pyperclip
import keyboard

def insert_text(text):
    if not text:
        return
        
    print(f"Вставка текста: {text[:50]}...")
    
    try:
        # Записываем новый текст в буфер обмена
        pyperclip.copy(text)
        
        # Ждем обновления буфера обмена
        time.sleep(0.05)
        
        # Имитируем нажатие Ctrl+V
        # Отпускаем потенциально зажатые модификаторы, чтобы Ctrl+V сработал корректно
        keyboard.release('shift')
        keyboard.release('ctrl')
        keyboard.release('alt')
        keyboard.release('windows')
        
        # Отправляем комбинацию клавиш для вставки
        keyboard.send('ctrl+v')
        
        # Даем операционной системе время завершить операцию вставки
        time.sleep(0.2)
        
    except Exception as e:
        print(f"Ошибка при вставке текста: {e}")
