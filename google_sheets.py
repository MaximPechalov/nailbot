import gspread
from google.oauth2.service_account import Credentials
from config import CREDENTIALS_FILE, SPREADSHEET_ID, COLUMNS

class GoogleSheets:
    def __init__(self):
        # Настраиваем доступ к Google API
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_file(
            CREDENTIALS_FILE,
            scopes=scopes
        )
        
        self.client = gspread.authorize(credentials)
        self.sheet = self.client.open_by_key(SPREADSHEET_ID).sheet1
        
        # Создаем заголовки, если их нет
        self._setup_headers()
    
    def _setup_headers(self):
        """Создает заголовки таблицы если они отсутствуют"""
        if not self.sheet.get_all_values():
            headers = list(COLUMNS.values())
            self.sheet.append_row(headers)
    
    def add_booking(self, booking_data):
        """Добавляет запись в таблицу"""
        row = [
            booking_data.get('timestamp', ''),
            booking_data.get('name', ''),
            booking_data.get('phone', ''),
            booking_data.get('date', ''),
            booking_data.get('time', ''),
            booking_data.get('service', ''),
            booking_data.get('telegram_id', ''),
            booking_data.get('username', '')
        ]
        
        self.sheet.append_row(row)
        return True
