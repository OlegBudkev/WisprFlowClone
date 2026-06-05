import sys
import os
import json

DEFAULT_CONFIG = {
    "stt_provider": "groq",
    "stt_model": "whisper-large-v3",
    "llm_provider": "groq",
    "llm_model": "llama-3.3-70b-versatile",
    "llm_refinement": False,
    "language": "ru",
    "theme": "dark",
    "device_index": None,
    "hotkey_hold": "alt+q",
    "hotkey_toggle": "alt+a",
    "api_keys": {
        "groq": "YOUR_GROQ_API_KEY_HERE",
        "openai": "YOUR_OPENAI_API_KEY_HERE"
    }
}

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(get_base_path(), "config.json")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Добавим отсутствующие ключи, если конфиг устарел
            updated = False
            for k, v in DEFAULT_CONFIG.items():
                if k not in config:
                    config[k] = v
                    updated = True
                elif isinstance(v, dict):
                    for sub_k, sub_v in v.items():
                        if sub_k not in config[k]:
                            config[k][sub_k] = sub_v
                            updated = True
            if updated:
                save_config(config)
            return config
    except Exception as e:
        print(f"Ошибка загрузки конфигурации: {e}. Используем дефолтные значения.")
        return DEFAULT_CONFIG

def save_config(config):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Ошибка сохранения конфигурации: {e}")

def get_api_key(config, provider):
    keys = config.get("api_keys", {})
    key = keys.get(provider, "")
    if "YOUR_" in key or not key.strip():
        return None
    return key.strip()
