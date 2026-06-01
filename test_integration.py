import os
import unittest
from config_loader import load_config, get_api_key
from recorder import AudioRecorder
from transcriber import Transcriber
from inserter import insert_text

class TestWisprIntegration(unittest.TestCase):
    def test_config_loader(self):
        config = load_config()
        self.assertIsNotNone(config)
        self.assertIn("stt_provider", config)
        self.assertIn("hotkey", config)
        
    def test_recorder_init(self):
        recorder = AudioRecorder(filename="test_recording.wav")
        self.assertEqual(os.path.basename(recorder.filename), "test_recording.wav")
        
    def test_transcriber_no_key(self):
        config = load_config()
        # Принудительно очистим ключи для теста, чтобы проверить генерацию ошибки
        config["api_keys"]["groq"] = "YOUR_GROQ_API_KEY_HERE"
        config["api_keys"]["openai"] = "YOUR_OPENAI_API_KEY_HERE"
        
        transcriber = Transcriber(config)
        with self.assertRaises(ValueError):
            transcriber.transcribe("nonexistent.wav")

    def test_inserter_runs(self):
        # Проверяем, что вызов функции не падает с ошибкой
        try:
            insert_text("")
            success = True
        except Exception:
            success = False
        self.assertTrue(success)

if __name__ == "__main__":
    unittest.main()
