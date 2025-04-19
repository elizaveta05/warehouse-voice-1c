import os
import whisperx

def main():
    print("Loading Whisper‑medium model (CPU, float32)…")
    model = whisperx.load_model("medium", device="cpu", compute_type="float32")

    data_dir = os.path.join(os.path.dirname(__file__), "test_data")
    for fname in sorted(os.listdir(data_dir)):
        if not fname.lower().endswith(".wav"):
            continue
        path = os.path.join(data_dir, fname)
        print(f"\n→ Processing {fname} …")
        # Транскрибируем
        result = model.transcribe(path)
        # Узнаём, что внутри
        # print("DEBUG result keys:", result.keys())

        # Собираем все сегменты в одну строку
        segments = result.get("segments", [])
        text = " ".join([seg.text for seg in segments]).strip()

        print(f"Result: «{text}»")

if __name__ == "__main__":
    main()
