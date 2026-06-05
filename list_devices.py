import sounddevice as sd

print("Default input/output device:", sd.default.device)
print()
print("Input devices:")
devices = sd.query_devices()
for i, d in enumerate(devices):
    if d["max_input_channels"] > 0:
        marker = " <-- DEFAULT" if i == sd.default.device[0] else ""
        print(f"  [{i}] {d['name']} (inputs: {d['max_input_channels']}, rate: {d['default_samplerate']}){marker}")
