import gspread
from google.oauth2.service_account import Credentials
from config import CREDENTIALS_FILE, SPREADSHEET_ID, COLUMNS, STATUS_COLORS, STATUS_PRIORITY
from datetime import datetime
import re

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
            
            # Применяем форматирование к заголовкам
            self._format_headers()
            
        except Exception as e:
            print(f"⚠️ Ошибка при создании заголовков: {e}")
    
    def _format_headers(self):
        """Форматирование заголовков таблицы"""
        try:
            # Жирный шрифт для заголовков
            self.sheet.format("A1:M1", {
                "textFormat": {"bold": True},
                "horizontalAlignment": "CENTER",
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
            })
            
            # Настройка ширины колонок (ID - уже, остальные авто)
            self.sheet.columns_auto_resize(1, 12)  # Автоширина для колонок B-M
            
        except Exception as e:
            print(f"⚠️ Ошибка форматирования заголовков: {e}")
    
    def _parse_date_time(self, date_str, time_str):
        """Парсит дату и время для сортировки"""
        try:
            # Парсим дату в формате ДД.ММ.ГГГГ
            day, month, year = map(int, date_str.split('.'))
            
            # Парсим время в формате ЧЧ:ММ
            hours, minutes = map(int, time_str.split(':'))
            
            return datetime(year, month, day, hours, minutes)
            
        except Exception as e:
            print(f"❌ Ошибка парсинга даты/времени: {date_str} {time_str}, {e}")
            return datetime.now()
    
    def _get_status_color(self, status):
        """Возвращает цвет фона в зависимости от статуса"""
        return STATUS_COLORS.get(status.lower(), {"red": 1.0, "green": 1.0, "blue": 1.0})
    
    def _get_sorting_key(self, record):
        """Возвращает ключ для сортировки записей по приоритету статуса и дате"""
        if len(record) < 5:  # Минимальное количество колонок
            return (999, datetime.now())
        
        # Получаем статус (колонка J если считать с 1, но индекс 9 если с 0)
        status = 'ожидает'  # По умолчанию
        if len(record) > 9 and record[9]:
            status = record[9].lower()
        
        # Получаем дату и время
        date_str = record[4] if len(record) > 4 else ""
        time_str = record[5] if len(record) > 5 else ""
        
        # Приоритет статуса
        priority = STATUS_PRIORITY.get(status, 999)
        
        # Дата и время
        try:
            dt = self._parse_date_time(date_str, time_str)
        except:
            dt = datetime.now()
        
        return (priority, dt)
    
    def _sort_bookings(self, all_bookings):
        """Сортирует записи по статусу и дате"""
        try:
            if len(all_bookings) <= 1:  # Только заголовки
                return all_bookings
            
            # Отделяем заголовки
            headers = all_bookings[0]
            bookings = all_bookings[1:]
            
            # Сортируем записи
            sorted_bookings = sorted(bookings, key=self._get_sorting_key)
            
            # Возвращаем с заголовками
            return [headers] + sorted_bookings
            
        except Exception as e:
            print(f"❌ Ошибка сортировки записей: {e}")
            return all_bookings
    
    def _apply_color_coding(self, all_bookings):
        """Применяет цветовое кодирование к строкам"""
        try:
            for i, record in enumerate(all_bookings):
                if i == 0:  # Пропускаем заголовки
                    continue
                
                if len(record) >= 10:  # Проверяем наличие колонки статуса
                    status = record[9].lower() if record[9] else 'ожидает'
                    color = self._get_status_color(status)
                    
                    # Применяем цвет ко всей строке (колонки A-M)
                    row_range = f"A{i+1}:M{i+1}"
                    self.sheet.format(row_range, {
                        "backgroundColor": color,
                        "horizontalAlignment": "LEFT",
                        "verticalAlignment": "MIDDLE"
                    })
            
            print(f"✅ Цветовое кодирование применено к {len(all_bookings)-1} записям")
            
        except Exception as e:
            print(f"⚠️ Ошибка применения цветового кодирования: {e}")
    
    def add_booking(self, booking_data):
        """Добавляет запись в таблицу и сортирует"""
        try:
            # Формируем строку с учетом всех колонок
            row = [
                booking_data.get('booking_id', '')[:8] + '...',  # ID записи (усеченный)
                booking_data.get('timestamp', ''),
                booking_data.get('name', ''),
                booking_data.get('phone', ''),
                booking_data.get('date', ''),
                booking_data.get('time', ''),
                booking_data.get('service', ''),
                booking_data.get('telegram_id', ''),
                booking_data.get('username', ''),
                booking_data.get('status', 'ожидает'),
                booking_data.get('status_updated', ''),
                booking_data.get('reschedule_id', ''),
                booking_data.get('original_booking_id', '')
            ]
            
            # Добавляем запись
            self.sheet.append_row(row)
            print(f"✅ Запись добавлена в Google Sheets")
            
            # Сортируем все записи и применяем цвета
            self._sort_and_update_all()
            
            return True
        except Exception as e:
            print(f"❌ Ошибка при добавлении записи в Google Sheets: {e}")
            return False
    
    def _sort_and_update_all(self):
        """Сортирует все записи и обновляет таблицу"""
        try:
            # Получаем все записи
            all_bookings = self.sheet.get_all_values()
            
            if len(all_bookings) <= 1:  # Только заголовки или пусто
                return
            
            # Сортируем записи
            sorted_bookings = self._sort_bookings(all_bookings)
            
            # Обновляем всю таблицу
            self._update_entire_sheet(sorted_bookings)
            
            # Применяем цветовое кодирование
            self._apply_color_coding(sorted_bookings)
            
            print(f"✅ Таблица отсортирована по статусу и дате")
            
        except Exception as e:
            print(f"❌ Ошибка при сортировке таблицы: {e}")
    
    def _update_entire_sheet(self, bookings):
        """Обновляет всю таблицу новыми данными"""
        try:
            # Очищаем таблицу
            self.sheet.clear()
            
            # Добавляем заголовки и данные
            if bookings:
                self.sheet.append_rows(bookings)
            
        except Exception as e:
            print(f"❌ Ошибка обновления таблицы: {e}")
    
    def add_status(self, booking_data, status):
        """Обновляет статус записи в таблице"""
        try:
            # Находим строку с записью по ID (колонка A)
            all_records = self.sheet.get_all_values()
            
            for i, record in enumerate(all_records):
                if i == 0:  # Пропускаем заголовки
                    continue
                
                if (len(record) > 0 and 
                    booking_data.get('booking_id', '').startswith(record[0].replace('...', ''))):
                    
                    # Обновляем статус и время изменения
                    update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    if len(record) >= 10:
                        self.sheet.update_cell(i + 1, 10, status)  # Статус (колонка J)
                    if len(record) >= 11:
                        self.sheet.update_cell(i + 1, 11, update_time)  # Время изменения (колонка K)
                    
                    print(f"✅ Статус обновлен в строке {i + 1}: {status}")
                    
                    # Обновляем сортировку
                    self._sort_and_update_all()
                    
                    return True
            
            print(f"⚠️ Запись не найдена для обновления статуса")
            
            # Пробуем найти по другим полям (старый метод для обратной совместимости)
            for i, record in enumerate(all_records):
                if i == 0:
                    continue
                
                if (len(record) >= 5 and
                    record[2] == booking_data.get('name') and
                    record[4] == booking_data.get('date') and
                    record[5] == booking_data.get('time')):
                    
                    update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    if len(record) >= 10:
                        self.sheet.update_cell(i + 1, 10, status)
                    if len(record) >= 11:
                        self.sheet.update_cell(i + 1, 11, update_time)
                    
                    print(f"✅ Статус обновлен в строке {i + 1} (поиск по имени): {status}")
                    
                    self._sort_and_update_all()
                    return True
            
            return False
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении статуса в Google Sheets: {e}")
            return False
    
    def update_booking_status_by_index(self, row_index, status):
        """Обновляет статус записи по индексу строки"""
        try:
            # Обновляем статус и время изменения
            update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            self.sheet.update_cell(row_index + 1, 10, status)  # Статус (колонка J)
            self.sheet.update_cell(row_index + 1, 11, update_time)  # Время изменения (колонка K)
            
            # Обновляем сортировку
            self._sort_and_update_all()
            
            print(f"✅ Статус обновлен в строке {row_index + 1}: {status}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении статуса по индексу: {e}")
            return False
    
    def get_all_bookings(self):
        """Получает все записи из таблицы"""
        try:
            return self.sheet.get_all_values()
        except Exception as e:
            print(f"❌ Ошибка получения записей из Google Sheets: {e}")
            return []
    
    def get_bookings_by_status(self, status):
        """Получает записи по статусу"""
        try:
            all_bookings = self.sheet.get_all_values()
            result = []
            
            for i, record in enumerate(all_bookings):
                if i == 0:
                    continue
                
                if len(record) >= 10 and record[9].lower() == status.lower():
                    result.append({
                        'row': i + 1,
                        'data': record,
                        'name': record[2] if len(record) > 2 else '',
                        'date': record[4] if len(record) > 4 else '',
                        'time': record[5] if len(record) > 5 else '',
                        'status': record[9] if len(record) > 9 else ''
                    })
            
            return result
        except Exception as e:
            print(f"❌ Ошибка получения записей по статусу: {e}")
            return []