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
                headers = list(COLUMNS.values())
                writer.writerow(headers)
            print(f"✅ Создан файл {self.filename}")
        else:
            print(f"✅ Файл {self.filename} уже существует")
    
    def add_booking(self, booking_data):
        """Добавляет запись в CSV файл"""
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
                booking_data.get('status', 'ожидает'),
                ''
            ]
            
            with open(self.filename, 'a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(row)
            
            print(f"✅ Запись сохранена в {self.filename}")
            return True
        except Exception as e:
            print(f"❌ Ошибка при сохранении в CSV: {e}")
            return False
    
    def add_status(self, booking_data, status):
        """Обновляет статус записи в CSV"""
        try:
            rows = []
            with open(self.filename, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                rows = list(reader)
            
            updated = False
            for i, row in enumerate(rows):
                if i == 0:
                    continue
                
                if (len(row) >= 8 and 
                    row[1] == booking_data.get('name') and
                    row[3] == booking_data.get('date') and
                    row[4] == booking_data.get('time')):
                    
                    if len(row) >= 9:
                        row[8] = status
                    if len(row) >= 10:
                        row[9] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    updated = True
                    print(f"✅ Статус обновлен в строке {i}: {status}")
                    break
            
            if updated:
                with open(self.filename, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerows(rows)
            else:
                print(f"⚠️ Запись не найдена для обновления статуса")
            
            return updated
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении статуса в CSV: {e}")
            return False
    
    def update_booking_status_by_index(self, row_index, status):
        """Обновляет статус записи по индексу строки"""
        try:
            rows = []
            with open(self.filename, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                rows = list(reader)
            
            if 1 <= row_index < len(rows):
                if len(rows[row_index]) >= 9:
                    rows[row_index][8] = status
                if len(rows[row_index]) >= 10:
                    rows[row_index][9] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                with open(self.filename, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerows(rows)
                
                print(f"✅ Статус обновлен в строке {row_index}: {status}")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении статуса по индексу в CSV: {e}")
            return False
    
    def get_all_bookings(self):
        """Получает все записи из CSV"""
        try:
            rows = []
            with open(self.filename, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                rows = list(reader)
            return rows
        except Exception as e:
            print(f"❌ Ошибка получения записей из CSV: {e}")
            return []
    
    def get_bookings_by_status(self, status):
        """Получает записи по статусу"""
        try:
            all_bookings = self.sheet.get_all_values()
            result = []
            
            for i, record in enumerate(all_bookings):
                if i == 0:
                    continue
                
                if len(record) >= 9 and record[8].lower() == status.lower():
                    result.append({
                        'row': i + 1,
                        'data': record,
                        'name': record[1] if len(record) > 1 else '',
                        'date': record[3] if len(record) > 3 else '',
                        'time': record[4] if len(record) > 4 else '',
                        'status': record[8] if len(record) > 8 else ''
                    })
            
            return result
        except Exception as e:
            print(f"❌ Ошибка получения записей по статусу: {e}")
            return []