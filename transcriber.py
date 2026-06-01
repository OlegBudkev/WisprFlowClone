import os
import requests
from config_loader import get_api_key

class Transcriber:
    def __init__(self, config):
        self.config = config
        self.local_model = None

    def transcribe(self, filepath):
        provider = self.config.get("stt_provider", "groq")
        
        if provider == "local":
            return self.transcribe_local(filepath)
            
        api_key = get_api_key(self.config, provider)
        if not api_key:
            raise ValueError(f"API ключ для провайдера '{provider}' не задан в config.json!")

        model = self.config.get("stt_model", "whisper-large-v3" if provider == "groq" else "whisper-1")
        language = self.config.get("language", "ru")

        if provider == "groq":
            url = "https://api.groq.com/openai/v1/audio/transcriptions"
        elif provider == "openai":
            url = "https://api.openai.com/v1/audio/transcriptions"
        else:
            raise ValueError(f"Неподдерживаемый провайдер STT: {provider}")

        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        
        # Подготовка данных формы
        data = {
            "model": model,
            "response_format": "json"
        }
        if language:
            data["language"] = language

        print(f"Отправка аудиофайла на {provider} STT (модель {model})...")
        
        try:
            with open(filepath, "rb") as f:
                files = {
                    "file": (os.path.basename(filepath), f, "audio/wav")
                }
                response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
                
            if response.status_code != 200:
                raise Exception(f"Ошибка API ({response.status_code}): {response.text}")
                
            result = response.json()
            text = result.get("text", "").strip()
            
            # Фильтруем галлюцинации Whisper
            text = self.filter_hallucinations(text)
            
            if not text:
                print("API вернуло пустой текст (или он отфильтрован как галлюцинация).")
                return ""
            
            print(f"Распознанный текст: {text}")
            
            # Умная постобработка, если включена
            if self.config.get("llm_refinement", False):
                text = self.refine_text(text)
                
            return text
            
        except Exception as e:
            print(f"Ошибка при транскрипции: {e}")
            raise e

    def transcribe_local(self, filepath):
        print("Инициализация локального распознавания (faster-whisper)...")
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ImportError(
                "Библиотека 'faster-whisper' не установлена!\n"
                "Установите ее вручную с помощью команды: pip install faster-whisper"
            )

        model_size = self.config.get("stt_model", "base")
        # Безопасный размер модели для CPU по умолчанию - base или small
        if model_size not in ["tiny", "base", "small", "medium", "large-v3"]:
            model_size = "base"

        if not self.local_model:
            print(f"Загрузка локальной модели '{model_size}' (может занять некоторое время при первом запуске)...")
            # device="auto" автоматически выберет GPU если доступен CUDA, иначе CPU
            self.local_model = WhisperModel(model_size, device="auto", compute_type="int8")

        print("Локальное распознавание аудиофайла...")
        language = self.config.get("language", "ru")
        
        try:
            segments, info = self.local_model.transcribe(
                filepath, 
                beam_size=5, 
                language=language if language else None
            )
            
            text_chunks = []
            for segment in segments:
                text_chunks.append(segment.text)
                
            text = " ".join(text_chunks).strip()
            
            # Фильтруем галлюцинации Whisper
            text = self.filter_hallucinations(text)
            
            if not text:
                print("Локальное распознавание вернуло пустой текст (или он отфильтрован как галлюцинация).")
                return ""
                
            print(f"Локально распознанный текст: {text}")
            
            # Умная постобработка, если включена
            if self.config.get("llm_refinement", False):
                text = self.refine_text(text)
                
            return text
        except Exception as e:
            print(f"Ошибка при локальном распознавании: {e}")
            raise e

    def filter_hallucinations(self, text):
        if not text:
            return ""
            
        clean_text = text.strip().lower()
        # Убираем знаки препинания и символы разметки для точного сравнения
        for char in [".", ",", "!", "?", "-", "\"", "'", "«", "»", ":", ";"]:
            clean_text = clean_text.replace(char, "")
        clean_text = clean_text.strip()
        
        hallucinations = [
            "продолжение следует",
            "субтитры",
            "субтитры созданы",
            "благодарю за просмотр",
            "спасибо за просмотр",
            "редактор субтитров",
            "thank you for watching",
            "thank you",
            "thank you very much",
            "подписывайтесь на канал",
            "подпишитесь на канал",
            "ставьте лайки",
            "конец записи",
            "спасибо",
            "благодарю",
            "пожалуйста",
            "thanks",
            "аминь",
            "amen",
            "yup",
            "продолжение",
            "просмотр",
            "hello",
            "hi",
            "bye"
        ]
        
        # Если чистый текст целиком входит в список галлюцинаций
        if clean_text in hallucinations:
            print(f"Обнаружена галлюцинация Whisper: '{text}'. Текст отфильтрован.")
            return ""
            
        # Также отсекаем короткие бессмысленные звуки
        if len(clean_text) <= 3 and clean_text in ["ch", "sh", "мм", "эм", "ну", "да", "хм", "ау", "оу"]:
            print(f"Обнаружен короткий шум/вздох: '{text}'. Текст отфильтрован.")
            return ""
            
        return text

    def refine_text(self, text):
        provider = self.config.get("llm_provider", "groq")
        api_key = get_api_key(self.config, provider)
        
        if not api_key:
            print(f"API ключ для LLM провайдера '{provider}' не задан. Пропускаем постобработку.")
            return text

        model = self.config.get("llm_model", "llama-3.3-70b-specdec" if provider == "groq" else "gpt-4o-mini")

        if provider == "groq":
            url = "https://api.groq.com/openai/v1/chat/completions"
        elif provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
        else:
            print(f"Неподдерживаемый провайдер LLM: {provider}. Пропускаем постобработку.")
            return text

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        system_prompt = (
            "Ты — инструмент для строгого форматирования надиктованного текста. Твоя единственная задача — исправить ошибки и оформить текст.\n"
            "КРИТИЧЕСКИЕ ПРАВИЛА:\n"
            "1. НИ В КОЕМ СЛУЧАЕ НЕ ОТВЕЧАЙ НА ВОПРОСЫ И НЕ ВЕДИ ДИАЛОГ С ПОЛЬЗОВАТЕЛЕМ. Если пользователь говорит 'Привет, как дела?', ты должен вернуть ровно 'Привет, как дела?' (с исправленной пунктуацией), а не отвечать на свой счет.\n"
            "2. Твоя задача — только исправлять грамматику, пунктуацию, опечатки и удалять повторы слов/фразы и слова-паразиты.\n"
            "3. Сохраняй исходный смысл, тон, все слова автора и язык на 100%. Не перефразируй без крайней необходимости.\n"
            "4. НЕ добавляй никаких своих комментариев, пояснений, кавычек или вводных фраз. Твой ответ должен содержать исключительно отредактированный текст пользователя.\n"
            "5. Если надиктован программный код или команды, форматируй их правильно."
        )

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "temperature": 0.2
        }

        print(f"Отправка текста на улучшение в {provider} LLM (модель {model})...")
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            if response.status_code != 200:
                print(f"Ошибка LLM API ({response.status_code}): {response.text}")
                return text
                
            result = response.json()
            refined_text = result["choices"][0]["message"]["content"].strip()
            
            if refined_text:
                print(f"Улучшенный текст: {refined_text}")
                return refined_text
            return text
        except Exception as e:
            print(f"Ошибка при улучшении текста: {e}")
            return text
