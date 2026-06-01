import os
import queue
import threading
import sounddevice as sd
import soundfile as sf
import numpy as np

class AudioRecorder:
    def __init__(self, filename="temp_recording.wav", samplerate=16000, channels=1, device_index=None):
        import tempfile
        self.filename = os.path.join(tempfile.gettempdir(), filename)
        self.samplerate = samplerate
        self.channels = channels
        self.device_index = device_index
        self.recording = False
        self.q = queue.Queue()
        self.thread = None
        self.current_volume = 0.0

    def _record_loop(self):
        def callback(indata, frames, time, status):
            if status:
                print(f"Статус записи: {status}", flush=True)
            self.q.put(indata.copy())
            # Вычисляем максимальную амплитуду (громкость)
            if len(indata) > 0:
                self.current_volume = float(np.max(np.abs(indata)))

        try:
            with sd.InputStream(samplerate=self.samplerate, channels=self.channels, device=self.device_index, callback=callback):
                while self.recording:
                    sd.sleep(50)
        except Exception as e:
            print(f"Ошибка в потоке записи: {e}")
            self.recording = False

    def start(self):
        if self.recording:
            return
        
        # Удаляем предыдущий файл, если он есть
        if os.path.exists(self.filename):
            try:
                os.remove(self.filename)
            except Exception as e:
                print(f"Не удалось удалить старый файл записи: {e}")

        self.recording = True
        self.q = queue.Queue()
        self.thread = threading.Thread(target=self._record_loop, daemon=True)
        self.thread.start()
        print("Запись звука начата...")

    def stop(self):
        if not self.recording:
            return None
        
        self.recording = False
        if self.thread:
            self.thread.join(timeout=2.0)
        
        print("Запись звука остановлена. Сохранение файла...")
        
        # Сбор данных из очереди
        data = []
        while not self.q.empty():
            data.append(self.q.get())
        
        if not data:
            print("Аудиоданные не записаны (пустая очередь).")
            return None
        
        try:
            audio_data = np.concatenate(data, axis=0)
            sf.write(self.filename, audio_data, self.samplerate)
            print(f"Файл успешно сохранен: {self.filename}")
            return self.filename
        except Exception as e:
            print(f"Ошибка при сохранении аудиофайла: {e}")
            return None

    def get_volume(self):
        if not self.recording:
            self.current_volume = max(0.0, self.current_volume - 0.1)
        return self.current_volume
