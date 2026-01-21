import gspread
from google.oauth2.service_account import Credentials
from config import CREDENTIALS_FILE, SPREADSHEET_ID, COLUMNS
from datetime import datetime

class GoogleSheets:
    def __init__(self):
        # Настраиваем доступ к Google API
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        try:
            credentials = Credentials.from_service_account_file(
                CREDENTIALS_FILE,
                scopes=scopes
            )
            
            self.client = gspread.authorize(credentials)
            self.sheet = self.client.open_by_key(SPREADSHEET_ID).sheet1
            
            # Создаем заголовки, если их нет
            self._setup_headers()
            print("✅ Подключение к Google Sheets успешно")
            
        except Exception as e:
            print(f"❌ Ошибка подключения к Google Sheets: {e}")
            raise e
    
    def _setup_headers(self):
        """Создает заголовки таблицы если они отсутствуют"""
        try:
            current_data = self.sheet.get_all_values()
            if not current_data or len(current_data) == 0:
                headers = list(COLUMNS.values())
                self.sheet.append_row(headers)
                print("✅ Заголовки таблицы созданы")
        except Exception as e:
            print(f"⚠️ Ошибка при создании заголовков: {e}")
    
    def add_booking(self, booking_data):
        """Добавляет запись в таблицу"""
        try:
            row = [
                booking_data.get('timestamp', ''),
                booking_data.get('name', ''),
                booking_data.get('phone', ''),
                booking_data.get('date', ''),
                booking_data.get('time', ''),
                booking_data.get('service', ''),
                booking_data.get('telegram_id', ''),
                booking_data.get('username', ''),
                'ожидает',  # Статус по умолчанию
                ''  # Время изменения статуса
            ]
            
            self.sheet.append_row(row)
            print(f"✅ Запись добавлена в Google Sheets")
            return True
        except Exception as e:
            print(f"❌ Ошибка при добавлении записи в Google Sheets: {e}")
            return False
    
    def add_status(self, booking_data, status):
        """Обновляет статус записи в таблице"""
        try:
            # Находим строку с записью
            all_records = self.sheet.get_all_values()
            
            for i, record in enumerate(all_records):
                # Проверяем по нескольким параметрам
                if (i > 0 and  # Пропускаем заголовки
                    record[1] == booking_data.get('name') and  # Имя
                    record[3] == booking_data.get('date') and  # Дата
                    record[4] == booking_data.get('time')):    # Время
                    
                    # Обновляем статус и время изменения
                    self.sheet.update_cell(i + 1, 9, status)  # Статус в колонке 9
                    self.sheet.update_cell(i + 1, 10, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))  # Время в колонке 10
                    
                    print(f"✅ Статус обновлен в строке {i + 1}: {status}")
                    return True
            
            print(f"⚠️ Запись не найдена для обновления статуса")
            return False
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении статуса в Google Sheets: {e}")
            return False