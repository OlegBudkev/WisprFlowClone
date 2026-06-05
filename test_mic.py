import sounddevice as sd
import numpy as np
import time

DEVICE_INDEX = 27
SAMPLERATE = 16000

print(f"Testing device [{DEVICE_INDEX}]: {sd.query_devices(DEVICE_INDEX)['name']}")
print(f"Samplerate: {SAMPLERATE}")
print("Recording 3 seconds... Speak into the mic!")
print()

max_volumes = []

def callback(indata, frames, time_info, status):
    if status:
        print(f"  Status: {status}")
    vol = float(np.max(np.abs(indata)))
    max_volumes.append(vol)
    bar = "#" * int(vol * 50)
    print(f"  Volume: {vol:.4f} |{bar}")

try:
    with sd.InputStream(samplerate=SAMPLERATE, channels=1, device=DEVICE_INDEX, callback=callback):
        for i in range(3, 0, -1):
            time.sleep(1)
    
    avg = np.mean(max_volumes) if max_volumes else 0
    peak = max(max_volumes) if max_volumes else 0
    print(f"\nResult: avg={avg:.4f}, peak={peak:.4f}")
    if peak < 0.01:
        print(">>> PROBLEM: Microphone is silent or not capturing audio!")
    else:
        print(">>> OK: Microphone is working.")
except Exception as e:
    print(f"\n>>> ERROR: Cannot open device {DEVICE_INDEX}: {e}")
    print("Try a different device_index.")
