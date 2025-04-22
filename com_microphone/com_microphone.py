# Импорт COM API Windows и библиотек
import pythoncom                         # Необходим для поддержки COM-интерфейсов
import pyaudio                           # Библиотека для работы с микрофоном
from win32com.server import register     # Для регистрации класса как COM-сервиса

# Класс, который будет COM-компонентом
class MicrophoneCOM:
    # Уникальный идентификатор компонента (можно сгенерировать через GUID Generator)
    _reg_clsid_ = "{F1EAEACD-1234-4321-ABCD-987654321ABC}"
    # Программное имя компонента, которое используем в 1С: Новый COMОбъект("Vendor.Microphone")
    _reg_progid_ = "Vendor.Microphone"
    # Методы, доступные извне (в том числе из 1С)
    _public_methods_ = ["Инициализировать", "ПолучитьФрагментДанных", "ЗавершитьЗапись"]

    def __init__(self):
        # Объект PyAudio
        self.p = None
        # Поток для записи с микрофона
        self.stream = None

    def Инициализировать(self):
        """
        Метод инициализирует PyAudio и запускает захват с микрофона.
        Записывает звук в формате:
        - 16 бит на сэмпл (paInt16)
        - моно (1 канал)
        - 16000 Гц (частота дискретизации)
        - 1600 сэмплов = ~100 мс
        """
        if self.p is None:
            self.p = pyaudio.PyAudio()
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1600  # 100 мс аудио
            )

    def ПолучитьФрагментДанных(self):
        """
        Возвращает один фрагмент аудио из микрофона (1600 сэмплов ≈ 100 мс).
        Используется для стриминга на сервер или распознавания.
        """
        if self.stream is not None:
            data = self.stream.read(1600)  # Считываем 1600 сэмплов = 3200 байт
            return data
        return b""  # Если поток неактивен — возвращаем пустые байты

    def ЗавершитьЗапись(self):
        """
        Останавливает поток и очищает ресурсы.
        Вызывать перед закрытием приложения или при выключении микрофона.
        """
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        if self.p is not None:
            self.p.terminate()
            self.p = None

# Если файл запущен напрямую (например, python com_microphone.py --register),
# то регистрируем этот класс как COM-сервер в системе Windows
if __name__ == "__main__":
    register.UseCommandLine(MicrophoneCOM)
