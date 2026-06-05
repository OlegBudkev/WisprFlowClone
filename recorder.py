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
        self.target_samplerate = samplerate  # Целевая частота для Whisper
        self.channels = channels
        self.device_index = device_index
        self.recording = False
        self.q = queue.Queue()
        self.thread = None
        self.current_volume = 0.0
        self.actual_samplerate = samplerate  # Реальная частота записи

    def _get_device_samplerate(self):
        """Определяет рабочую частоту дискретизации для устройства."""
        try:
            dev_info = sd.query_devices(self.device_index)
            default_rate = int(dev_info['default_samplerate'])
            print(f"[Recorder] Устройство: {dev_info['name']}, default_samplerate: {default_rate}")
            return default_rate
        except Exception as e:
            print(f"[Recorder] Не удалось определить samplerate устройства: {e}")
            return self.target_samplerate

    def _get_decoded_device_name(self, dev):
        """Безопасно извлекает и декодирует имя устройства из PortAudio."""
        name = dev.get('name', '')
        # Пробуем декодировать из latin1 в cp1251 (помогает при кракозябрах на Windows)
        try:
            return name.encode('latin1').decode('cp1251')
        except Exception:
            return name

    def _find_gmix_device_index(self):
        """Ищет индекс устройства ввода, содержащего 'gmix' в имени (регистронезависимо)."""
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    name = self._get_decoded_device_name(dev).lower()
                    if 'gmix' in name:
                        return i
        except Exception as e:
            print(f"[Recorder] Ошибка при поиске Gmix устройства: {e}")
        return None

    def _find_bluetooth_device_index(self):
        """Ищет индекс Bluetooth устройства ввода (наушников/гарнитуры)."""
        keywords = ["bluetooth", "hands-free", "handsfree", "earbud", "headset", "headphones", "головной телефон", "блютуз", "наушник", "гарнитура"]
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    name = self._get_decoded_device_name(dev).lower()
                    if any(kw in name for kw in keywords):
                        return i
        except Exception as e:
            print(f"[Recorder] Ошибка при поиске Bluetooth устройства: {e}")
        return None

    def _record_loop(self):
        def callback(indata, frames, time, status):
            if status:
                print(f"Статус записи: {status}", flush=True)
            self.q.put(indata.copy())
            # Вычисляем максимальную амплитуду (громкость)
            if len(indata) > 0:
                self.current_volume = float(np.max(np.abs(indata)))

        # Определяем устройства, которые будем пробовать
        devices_to_try = []
        
        # 1. Сначала пробуем Bluetooth-микрофон (наивысший приоритет)
        bt_idx = self._find_bluetooth_device_index()
        if bt_idx is not None:
            devices_to_try.append(bt_idx)
            print(f"[Recorder] Обнаружены Bluetooth-наушники (приоритет): индекс {bt_idx}")

        # 2. Если настроен конкретный микрофон и он доступен, пробуем его
        if self.device_index is not None and self.device_index not in devices_to_try:
            try:
                sd.query_devices(self.device_index)
                devices_to_try.append(self.device_index)
            except Exception:
                print(f"[Recorder] Настроенное устройство с индексом {self.device_index} недоступно.")

        # 3. Затем пробуем Gmix
        gmix_idx = self._find_gmix_device_index()
        if gmix_idx is not None and gmix_idx not in devices_to_try:
            devices_to_try.append(gmix_idx)
            print(f"[Recorder] Добавлен приоритетный fallback: Gmix (индекс {gmix_idx})")

        # 4. Всегда добавляем системный дефолтный микрофон в качестве финального fallback
        devices_to_try.append(None)

        for dev in devices_to_try:
            # Получаем инфо об устройстве
            try:
                dev_info = sd.query_devices(dev, 'input')
                dev_name = dev_info['name']
                default_rate = int(dev_info['default_samplerate'])
            except Exception as e:
                print(f"[Recorder] Ошибка получения информации об устройстве {dev}: {e}")
                continue

            # Нам нужны только 2 частоты для попытки: дефолтная для этого устройства и 16000
            rates_to_try = [default_rate]
            if self.target_samplerate not in rates_to_try:
                rates_to_try.append(self.target_samplerate)

            for rate in rates_to_try:
                try:
                    dev_label = dev_name if dev is not None else 'системный по умолчанию'
                    print(f"[Recorder] Попытка: устройство='{dev_label}' (index={dev}), samplerate={rate}...")
                    with sd.InputStream(samplerate=rate, channels=self.channels, device=dev, callback=callback):
                        self.actual_samplerate = rate
                        print(f"[Recorder] Запись начата: устройство='{dev_label}', samplerate={rate}")
                        while self.recording:
                            sd.sleep(50)
                    return  # Успешно завершили запись
                except Exception as e:
                    print(f"[Recorder] Не удалось (dev={dev}, rate={rate}): {e}")
                    continue

        print("[Recorder] Не удалось открыть ни один поток записи!")
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
            
            # Ресемплинг до целевой частоты (16 kHz для Whisper) если записали на другой
            if self.actual_samplerate != self.target_samplerate:
                print(f"[Recorder] Ресемплинг: {self.actual_samplerate} -> {self.target_samplerate} Hz")
                duration = len(audio_data) / self.actual_samplerate
                num_samples = int(duration * self.target_samplerate)
                old_indices = np.linspace(0, len(audio_data) - 1, len(audio_data))
                new_indices = np.linspace(0, len(audio_data) - 1, num_samples)
                if audio_data.ndim == 1:
                    audio_data = np.interp(new_indices, old_indices, audio_data).astype(np.float32)
                else:
                    audio_data = np.column_stack([
                        np.interp(new_indices, old_indices, audio_data[:, ch]).astype(np.float32)
                        for ch in range(audio_data.shape[1])
                    ])
            
            sf.write(self.filename, audio_data, self.target_samplerate)
            print(f"Файл успешно сохранен: {self.filename}")
            return self.filename
        except Exception as e:
            print(f"Ошибка при сохранении аудиофайла: {e}")
            return None

    def get_volume(self):
        if not self.recording:
            self.current_volume = max(0.0, self.current_volume - 0.1)
        return self.current_volume
