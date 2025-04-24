# voice_server/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # домены, которым разрешён CORS-доступ
    cors_origins: str = "*"

    # каталог для временных WAV-файлов
    tmp_dir: str = "temp_audio"

    voicemodel: str = "small"
    device: str = "cpu"

    class Config:
        env_prefix = "VOICE_"      # можно переопределять переменными окружения


settings = Settings()
