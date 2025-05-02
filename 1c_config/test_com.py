import pythoncom
from win32com.client import Dispatch

def test_com_connection():
    pythoncom.CoInitialize()
    try:
        # Создаём COMConnector
        connector = Dispatch("V83.COMConnector")

        # Подключаемся к файловой базе
        ib_path = r'File="C:\Users\elozo\OneDrive\Документы\InfoBase7"'
        conn = connector.Connect(ib_path)

        # Вызываем тестовую процедуру из модуля 1С
        conn.COMConnectionTest.TestCOMConnection()

        print("✅ Вызов TestCOMConnection отправлен, проверьте журнал регистрации 1С.")
    except Exception as e:
        print("❌ Ошибка COM-подключения или вызова:", e)
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    test_com_connection()
