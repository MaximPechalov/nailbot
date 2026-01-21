import gspread
from google.oauth2.service_account import Credentials
from config import CREDENTIALS_FILE, SPREADSHEET_ID, COLUMNS
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
            self.sheet.format("A1:J1", {
                "textFormat": {"bold": True},
                "horizontalAlignment": "CENTER",
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
            })
            
            # Настройка ширины колонок
            self.sheet.columns_auto_resize(0, 9)  # Автоширина для колонок A-J
            
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
        colors = {
            'ожидает': {"red": 1.0, "green": 1.0, "blue": 0.9},  # Светло-желтый
            'подтверждено': {"red": 0.85, "green": 1.0, "blue": 0.85},  # Светло-зеленый
            'отклонено': {"red": 1.0, "green": 0.85, "blue": 0.85},  # Светло-красный
            'отклонено мастером': {"red": 1.0, "green": 0.75, "blue": 0.75},  # Красный
            'выполнено': {"red": 0.9, "green": 0.9, "blue": 1.0},  # Светло-синий
            'отменено': {"red": 0.95, "green": 0.95, "blue": 0.95},  # Серый
        }
        return colors.get(status, {"red": 1.0, "green": 1.0, "blue": 1.0})  # Белый по умолчанию
    
    def _sort_bookings(self, all_bookings):
        """Сортирует записи по дате и времени"""
        try:
            # Создаем список кортежей (дата_время, индекс, запись)
            bookings_with_dates = []
            
            for i, record in enumerate(all_bookings):
                if i == 0:  # Пропускаем заголовки
                    continue
                
                if len(record) >= 5:
                    date_str = record[3] if len(record) > 3 else ""
                    time_str = record[4] if len(record) > 4 else ""
                    
                    if date_str and time_str:
                        try:
                            dt = self._parse_date_time(date_str, time_str)
                            bookings_with_dates.append((dt, i, record))
                        except:
                            # Если не удалось распарсить, добавляем с текущим временем
                            bookings_with_dates.append((datetime.now(), i, record))
            
            # Сортируем по дате и времени
            bookings_with_dates.sort(key=lambda x: x[0])
            
            # Возвращаем отсортированные записи
            sorted_bookings = [all_bookings[0]]  # Заголовки
            
            for dt, original_index, record in bookings_with_dates:
                sorted_bookings.append(record)
            
            return sorted_bookings
            
        except Exception as e:
            print(f"❌ Ошибка сортировки записей: {e}")
            return all_bookings
    
    def _apply_color_coding(self, all_bookings):
        """Применяет цветовое кодирование к строкам"""
        try:
            for i, record in enumerate(all_bookings):
                if i == 0:  # Пропускаем заголовки
                    continue
                
                if len(record) >= 9:  # Проверяем наличие колонки статуса
                    status = record[8].lower() if record[8] else 'ожидает'
                    color = self._get_status_color(status)
                    
                    # Применяем цвет к строке (колонки A-J)
                    row_range = f"A{i+1}:J{i+1}"
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
            
            # Очищаем таблицу (кроме заголовков)
            self.sheet.delete_rows(2, len(all_bookings))
            
            # Добавляем отсортированные записи (начиная с заголовков)
            if len(sorted_bookings) > 1:
                for record in sorted_bookings[1:]:  # Пропускаем уже существующие заголовки
                    self.sheet.append_row(record)
            
            # Применяем цветовое кодирование
            updated_bookings = self.sheet.get_all_values()
            self._apply_color_coding(updated_bookings)
            
            print(f"✅ Таблица отсортирована по дате и времени")
            
        except Exception as e:
            print(f"❌ Ошибка при сортировке таблицы: {e}")
    
    def add_status(self, booking_data, status):
        """Обновляет статус записи в таблице"""
        try:
            # Находим строку с записью
            all_records = self.sheet.get_all_values()
            
            for i, record in enumerate(all_records):
                # Проверяем по нескольким параметрам
                if (i > 0 and  # Пропускаем заголовки
                    len(record) >= 5 and
                    record[1] == booking_data.get('name') and  # Имя
                    record[3] == booking_data.get('date') and  # Дата
                    record[4] == booking_data.get('time')):    # Время
                    
                    # Обновляем статус и время изменения
                    update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Обновляем ячейки
                    if len(record) >= 9:
                        self.sheet.update_cell(i + 1, 9, status)  # Статус в колонке 9
                    else:
                        # Если колонки нет, добавляем
                        self.sheet.update_cell(i + 1, 9, status)
                    
                    if len(record) >= 10:
                        self.sheet.update_cell(i + 1, 10, update_time)  # Время в колонке 10
                    else:
                        # Если колонки нет, добавляем
                        self.sheet.update_cell(i + 1, 10, update_time)
                    
                    # Применяем цвет в зависимости от статуса
                    color = self._get_status_color(status.lower())
                    row_range = f"A{i+1}:J{i+1}"
                    self.sheet.format(row_range, {
                        "backgroundColor": color
                    })
                    
                    print(f"✅ Статус обновлен в строке {i + 1}: {status}")
                    
                    # Обновляем сортировку
                    self._sort_and_update_all()
                    
                    return True
            
            print(f"⚠️ Запись не найдена для обновления статуса")
            return False
            
        except Exception as e:
            print(f"❌ Ошибка при обновлении статуса в Google Sheets: {e}")
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
                if i == 0:  # Пропускаем заголовки
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