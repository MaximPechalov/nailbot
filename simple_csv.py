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
                # Добавляем заголовки для статусов
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
                'ожидает',  # Статус по умолчанию
                ''  # Время изменения статуса
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
            # Читаем все записи
            rows = []
            with open(self.filename, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                rows = list(reader)
            
            # Ищем запись для обновления
            updated = False
            for i, row in enumerate(rows):
                if i == 0:
                    continue  # Пропускаем заголовки
                
                # Проверяем по нескольким параметрам (упрощенная логика)
                if (len(row) >= 8 and 
                    row[1] == booking_data.get('name') and
                    row[3] == booking_data.get('date') and
                    row[4] == booking_data.get('time')):
                    
                    # Обновляем статус
                    if len(row) >= 9:
                        row[8] = status  # Статус
                    if len(row) >= 10:
                        row[9] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Время обновления
                    
                    updated = True
                    print(f"✅ Статус обновлен в строке {i}: {status}")
                    break
            
            if updated:
                # Записываем обновленные данные обратно
                with open(self.filename, 'w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerows(rows)
            else:
                print(f"⚠️ Запись не найдена для обновления статуса")
            
            return updated
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении статуса в CSV: {e}")
            return False