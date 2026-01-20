import csv
import os
from datetime import datetime
from config import COLUMNS

class SimpleCSVManager:
    """Временное решение - сохраняем в CSV файл вместо Google Sheets"""
    
    def __init__(self):
        self.filename = 'bookings.csv'
        self._setup_csv()
    
    def _setup_csv(self):
        """Создает CSV файл с заголовками если его нет"""
        if not os.path.exists(self.filename):
            with open(self.filename, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(list(COLUMNS.values()))
            print(f"✅ Создан файл {self.filename}")
        else:
            print(f"✅ Файл {self.filename} уже существует")
    
    def add_booking(self, booking_data):
        """Добавляет запись в CSV файл"""
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
        
        with open(self.filename, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(row)
        
        print(f"✅ Запись сохранена в {self.filename}")
        print(f"📋 Данные: {row}")
        return True