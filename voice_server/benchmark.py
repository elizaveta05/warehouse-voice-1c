import os
import whisperx

def main():
    # 1) Информация о запуске
    print("Loading Whisper‑medium model (CPU, float32)…")
    
    # 2) Загружаем модель WhisperX формата "medium" для CPU
    #    compute_type="float32" — принудительно используем 32‑битные вычисления,
    #    иначе на Windows по умолчанию попытка float16 упадёт
    model = whisperx.load_model("medium", device="cpu", compute_type="float32")

    # 3) Путь до папки с тестовыми аудиофайлами
    data_dir = os.path.join(os.path.dirname(__file__), "test_data")

    # 4) Проходим по всем файлам в папке test_data
    for fname in sorted(os.listdir(data_dir)):
        # — пропускаем всё, что не .wav
        if not fname.lower().endswith(".wav"):
            continue

        path = os.path.join(data_dir, fname)
        print(f"\n→ Processing {fname} …")

        # 5) Транскрибируем аудио
        #    result — это словарь с ключами: 'segments', 'language', и т.п.
        result = model.transcribe(path)

        # 6) Извлекаем распарсенные фрагменты речи
        #    segments — список словарей, каждый содержит ключ 'text'
        segments = result.get("segments", [])

        # 7) Собираем финальный текст из всех сегментов
        text = " ".join([seg["text"] for seg in segments]).strip()

        # 8) Выводим результат
        print(f"Result: «{text}»")

# точка входа
if __name__ == "__main__":
    main()
