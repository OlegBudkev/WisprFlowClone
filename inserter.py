import time
import ctypes
import ctypes.wintypes
import pyperclip

# --- Windows SendInput structures (correct alignment) ---
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD),
        ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.wintypes.DWORD),
        ("wParamL", ctypes.wintypes.WORD),
        ("wParamH", ctypes.wintypes.WORD),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.wintypes.DWORD),
        ("union", _INPUT_UNION),
    ]


def _send_keys(*key_actions):
    """Отправляет пакет клавиш через SendInput за один вызов.
    key_actions: список кортежей (vk, is_up)
    """
    n = len(key_actions)
    inputs = (INPUT * n)()
    for i, (vk, up) in enumerate(key_actions):
        inputs[i].type = INPUT_KEYBOARD
        inputs[i].union.ki.wVk = vk
        inputs[i].union.ki.dwFlags = KEYEVENTF_KEYUP if up else 0
    sent = ctypes.windll.user32.SendInput(n, ctypes.byref(inputs), ctypes.sizeof(INPUT))
    if sent != n:
        print(f"[Inserter] SendInput отправил {sent}/{n} событий")


def _release_modifiers():
    """Принудительно отпускает все модификаторы (Alt, Ctrl, Shift, Win) превентивно.
    Это сбрасывает зависшие логические состояния клавиш в Windows."""
    VK_MENU = 0x12
    VK_CONTROL = 0x11
    VK_SHIFT = 0x10
    VK_LWIN = 0x5B
    VK_RWIN = 0x5C
    
    # Всегда генерируем KEYUP для всех модификаторов превентивно
    modifiers = [VK_MENU, VK_CONTROL, VK_SHIFT, VK_LWIN, VK_RWIN]
    actions = [(vk, True) for vk in modifiers]
    _send_keys(*actions)
    print("[Inserter] Превентивно сброшены модификаторы (Alt, Ctrl, Shift, Win)")


def insert_text(text):
    if not text:
        return

    print(f"Вставка текста: {text[:50]}...")

    try:
        pyperclip.copy(text)
        print("[Inserter] Текст скопирован в буфер обмена")
    except Exception as e:
        print(f"[Inserter] Ошибка при копировании в буфер обмена: {e}")

    try:
        # Принудительно сбрасываем все зажатые модификаторы перед вводом
        _release_modifiers()
        time.sleep(0.05)

        # Подготовка Unicode-событий ввода для каждого символа текста
        # Каждый символ требует 2 события: KeyDown и KeyUp
        n = len(text) * 2
        inputs = (INPUT * n)()

        for i, char in enumerate(text):
            code = ord(char)
            
            # Нажатие клавиши Unicode
            inputs[i * 2].type = INPUT_KEYBOARD
            inputs[i * 2].union.ki.wVk = 0
            inputs[i * 2].union.ki.wScan = code
            inputs[i * 2].union.ki.dwFlags = KEYEVENTF_UNICODE
            inputs[i * 2].union.ki.time = 0
            inputs[i * 2].union.ki.dwExtraInfo = None

            # Отпускание клавиши Unicode
            inputs[i * 2 + 1].type = INPUT_KEYBOARD
            inputs[i * 2 + 1].union.ki.wVk = 0
            inputs[i * 2 + 1].union.ki.wScan = code
            inputs[i * 2 + 1].union.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            inputs[i * 2 + 1].union.ki.time = 0
            inputs[i * 2 + 1].union.ki.dwExtraInfo = None

        sent = ctypes.windll.user32.SendInput(n, ctypes.byref(inputs), ctypes.sizeof(INPUT))
        if sent == n:
            print(f"[Inserter] Текст успешно отправлен через KEYEVENTF_UNICODE ({n} событий)")
        else:
            print(f"[Inserter] Внимание: отправлено {sent} из {n} событий ввода")

    except Exception as e:
        print(f"Ошибка при вставке текста: {e}")
