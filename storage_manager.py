"""
Централизованное управление данными с синхронизацией между:
- Google Sheets (основное)
- bookings_storage.json (для быстрого доступа)
- Кеш в памяти для производительности
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import uuid4

class StorageManager:
    def __init__(self, google_sheets=None):
        self.google_sheets = google_sheets
        self.data_dir = 'data'
        self.bookings_file = os.path.join(self.data_dir, 'bookings_storage.json')
        self.users_file = os.path.join(self.data_dir, 'users_data.json')
        
        self._ensure_data_dir()
        self._ensure_files()
        
        # Кеш в памяти для производительности
        self._bookings_cache = None
        self._users_cache = None
    
    def _ensure_data_dir(self):
        """Создает папку data если её нет"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            print(f"✅ Создана папка {self.data_dir}")
    
    def _ensure_files(self):
        """Создает необходимые файлы"""
        default_files = {
            self.bookings_file: {},
            self.users_file: {}
        }
        
        for file_path, default_data in default_files.items():
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(default_data, f, ensure_ascii=False, indent=2)
                print(f"✅ Создан файл {file_path}")
    
    # === Методы для записей ===
    
    def add_booking(self, booking_data: Dict[str, Any]) -> str:
        """Добавляет запись во все хранилища"""
        # Генерируем booking_id
        booking_id = str(uuid4())
        booking_data['booking_id'] = booking_id
        booking_data['created_at'] = datetime.now().isoformat()
        booking_data['status'] = 'ожидает'
        
        # 1. Сохраняем в локальное JSON хранилище
        bookings = self._load_bookings()
        bookings[booking_id] = booking_data
        self._save_bookings(bookings)
        print(f"✅ Запись {booking_id[:8]}... сохранена в JSON")
        
        # 2. Сохраняем в Google Sheets/CSV
        if self.google_sheets:
            try:
                # Удаляем служебные поля перед сохранением в Google Sheets
                gs_data = booking_data.copy()
                for field in ['booking_id', 'created_at']:
                    gs_data.pop(field, None)
                
                # Добавляем статус по умолчанию
                if 'status' not in gs_data:
                    gs_data['status'] = 'ожидает'
                
                self.google_sheets.add_booking(gs_data)
                print(f"✅ Запись {booking_id[:8]}... сохранена в Google Sheets/CSV")
            except Exception as e:
                print(f"⚠️ Ошибка сохранения в Google Sheets/CSV: {e}")
        
        return booking_id
    
    def add_reschedule_request(self, original_booking_id: str, new_booking_data: Dict[str, Any]) -> str:
        """Создает запрос на перенос записи"""
        # 1. Обновляем статус оригинальной записи
        original_updated = self.update_booking_status(
            original_booking_id, 
            'перенос (ожидание мастера)'
        )
        
        if not original_updated:
            print(f"❌ Не удалось обновить статус оригинальной записи {original_booking_id}")
            return ""
        
        # 2. Создаем новую запись
        new_booking_id = self.add_booking(new_booking_data)
        
        if not new_booking_id:
            print("❌ Не удалось создать новую запись для переноса")
            # Откатываем статус оригинальной записи
            self.update_booking_status(original_booking_id, 'ожидает')
            return ""
        
        # 3. Сохраняем связь между записями
        bookings = self._load_bookings()
        
        if original_booking_id in bookings and new_booking_id in bookings:
            # Добавляем ссылку на оригинальную запись
            bookings[new_booking_id]['original_booking_id'] = original_booking_id
            bookings[new_booking_id]['status'] = 'перенос (ожидание мастера)'
            
            # Добавляем ссылку на новую запись
            bookings[original_booking_id]['rescheduled_to'] = new_booking_id
            
            self._save_bookings(bookings)
            print(f"✅ Связь установлена: {original_booking_id[:8]}... -> {new_booking_id[:8]}...")
            
            # 4. Обновляем в Google Sheets/CSV
            if self.google_sheets:
                try:
                    # Обновляем оригинальную запись
                    original_booking = bookings[original_booking_id]
                    gs_original_data = {
                        'name': original_booking.get('name', ''),
                        'date': original_booking.get('date', ''),
                        'time': original_booking.get('time', ''),
                        'phone': original_booking.get('phone', '')
                    }
                    self.google_sheets.add_status(gs_original_data, 'перенос (ожидание мастера)')
                    
                    # Обновляем новую запись
                    new_booking = bookings[new_booking_id]
                    gs_new_data = {
                        'name': new_booking.get('name', ''),
                        'date': new_booking.get('date', ''),
                        'time': new_booking.get('time', ''),
                        'phone': new_booking.get('phone', '')
                    }
                    self.google_sheets.add_status(gs_new_data, 'перенос (ожидание мастера)')
                    
                except Exception as e:
                    print(f"⚠️ Ошибка обновления переноса в Google Sheets/CSV: {e}")
        
        return new_booking_id
    
    def confirm_reschedule(self, original_booking_id: str, new_booking_id: str) -> bool:
        """Подтверждает перенос записи"""
        bookings = self._load_bookings()
        
        if original_booking_id not in bookings or new_booking_id not in bookings:
            print(f"❌ Не найдены записи для подтверждения переноса")
            return False
        
        try:
            # 1. Отменяем оригинальную запись
            bookings[original_booking_id]['status'] = 'перенесена'
            bookings[original_booking_id]['status_updated'] = datetime.now().isoformat()
            
            # 2. Подтверждаем новую запись
            bookings[new_booking_id]['status'] = 'подтверждено'
            bookings[new_booking_id]['status_updated'] = datetime.now().isoformat()
            # Удаляем временную связь
            if 'original_booking_id' in bookings[new_booking_id]:
                del bookings[new_booking_id]['original_booking_id']
            
            self._save_bookings(bookings)
            print(f"✅ Перенос подтвержден: {original_booking_id[:8]}... -> {new_booking_id[:8]}...")
            
            # 3. Обновляем в Google Sheets/CSV
            if self.google_sheets:
                # Обновляем оригинальную запись
                original_booking = bookings[original_booking_id]
                gs_original_data = {
                    'name': original_booking.get('name', ''),
                    'date': original_booking.get('date', ''),
                    'time': original_booking.get('time', ''),
                    'phone': original_booking.get('phone', '')
                }
                self.google_sheets.add_status(gs_original_data, 'перенесена')
                
                # Обновляем новую запись
                new_booking = bookings[new_booking_id]
                gs_new_data = {
                    'name': new_booking.get('name', ''),
                    'date': new_booking.get('date', ''),
                    'time': new_booking.get('time', ''),
                    'phone': new_booking.get('phone', '')
                }
                self.google_sheets.add_status(gs_new_data, 'подтверждено')
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка подтверждения переноса: {e}")
            return False
    
    def reject_reschedule(self, original_booking_id: str, new_booking_id: str) -> bool:
        """Отклоняет перенос записи"""
        bookings = self._load_bookings()
        
        if original_booking_id not in bookings or new_booking_id not in bookings:
            print(f"❌ Не найдены записи для отклонения переноса")
            return False
        
        try:
            # 1. Возвращаем оригинальную запись в предыдущий статус
            # Определяем предыдущий статус
            original_booking = bookings[original_booking_id]
            old_status = original_booking.get('old_status', 'ожидает')
            bookings[original_booking_id]['status'] = old_status
            bookings[original_booking_id]['status_updated'] = datetime.now().isoformat()
            
            # 2. Удаляем новую запись (или отмечаем как отклоненную)
            bookings[new_booking_id]['status'] = 'отклонено мастером'
            bookings[new_booking_id]['status_updated'] = datetime.now().isoformat()
            
            # 3. Удаляем связи
            if 'rescheduled_to' in bookings[original_booking_id]:
                del bookings[original_booking_id]['rescheduled_to']
            if 'original_booking_id' in bookings[new_booking_id]:
                del bookings[new_booking_id]['original_booking_id']
            
            self._save_bookings(bookings)
            print(f"✅ Перенос отклонен: {original_booking_id[:8]}...")
            
            # 4. Обновляем в Google Sheets/CSV
            if self.google_sheets:
                # Обновляем оригинальную запись
                original_booking = bookings[original_booking_id]
                gs_original_data = {
                    'name': original_booking.get('name', ''),
                    'date': original_booking.get('date', ''),
                    'time': original_booking.get('time', ''),
                    'phone': original_booking.get('phone', '')
                }
                self.google_sheets.add_status(gs_original_data, old_status)
                
                # Обновляем новую запись
                new_booking = bookings[new_booking_id]
                gs_new_data = {
                    'name': new_booking.get('name', ''),
                    'date': new_booking.get('date', ''),
                    'time': new_booking.get('time', ''),
                    'phone': new_booking.get('phone', '')
                }
                self.google_sheets.add_status(gs_new_data, 'отклонено мастером')
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка отклонения переноса: {e}")
            return False
    
    def update_booking_status(self, booking_id: str, status: str, 
                             master_comment: str = None) -> bool:
        """Обновляет статус записи во всех хранилищах"""
        bookings = self._load_bookings()
        
        if booking_id not in bookings:
            print(f"❌ Запись {booking_id} не найдена в хранилище")
            return False
        
        # Сохраняем старый статус если это перенос
        if status == 'перенос (ожидание мастера)':
            bookings[booking_id]['old_status'] = bookings[booking_id].get('status', 'ожидает')
        
        # Обновляем в JSON хранилище
        bookings[booking_id]['status'] = status
        bookings[booking_id]['status_updated'] = datetime.now().isoformat()
        if master_comment:
            bookings[booking_id]['master_comment'] = master_comment
        
        self._save_bookings(bookings)
        print(f"✅ Статус записи {booking_id[:8]}... обновлен в JSON: {status}")
        
        # Обновляем в Google Sheets/CSV
        if self.google_sheets:
            try:
                booking = bookings[booking_id]
                gs_data = {
                    'name': booking.get('name', ''),
                    'date': booking.get('date', ''),
                    'time': booking.get('time', ''),
                    'phone': booking.get('phone', '')
                }
                self.google_sheets.add_status(gs_data, status)
                print(f"✅ Статус записи обновлен в Google Sheets/CSV: {status}")
            except Exception as e:
                print(f"⚠️ Ошибка обновления в Google Sheets/CSV: {e}")
        
        return True
    
    def get_booking(self, booking_id: str) -> Optional[Dict]:
        """Получает запись по ID"""
        bookings = self._load_bookings()
        return bookings.get(booking_id)
    
    def get_user_bookings(self, telegram_id: str, 
                         status_filter: List[str] = None) -> List[Dict]:
        """Получает записи пользователя"""
        bookings = self._load_bookings()
        
        user_bookings = []
        for booking_id, booking in bookings.items():
            if str(booking.get('telegram_id')) == str(telegram_id):
                if status_filter is None or booking.get('status') in status_filter:
                    user_bookings.append({
                        'booking_id': booking_id,
                        **booking
                    })
        
        # Сортировка по дате
        user_bookings.sort(key=lambda x: (
            x.get('date', ''),
            x.get('time', '')
        ))
        
        return user_bookings
    
    def cancel_booking_by_id(self, booking_id: str) -> bool:
        """Отменяет запись по ID"""
        return self.update_booking_status(booking_id, 'отменено')
    
    # === Методы для переносов ===
    
    def get_reschedule_requests(self) -> List[Dict]:
        """Получает все запросы на перенос"""
        bookings = self._load_bookings()
        reschedule_requests = []
        
        for booking_id, booking in bookings.items():
            if booking.get('status') == 'перенос (ожидание мастера)':
                original_booking_id = booking.get('original_booking_id')
                if original_booking_id and original_booking_id in bookings:
                    original_booking = bookings[original_booking_id]
                    
                    reschedule_requests.append({
                        'reschedule_id': booking_id,
                        'original_booking_id': original_booking_id,
                        'new_booking_id': booking_id,
                        'client_name': booking.get('name', ''),
                        'client_phone': booking.get('phone', ''),
                        'old_date': original_booking.get('date', ''),
                        'old_time': original_booking.get('time', ''),
                        'new_date': booking.get('date', ''),
                        'new_time': booking.get('time', ''),
                        'service': booking.get('service', ''),
                        'requested_at': booking.get('created_at', ''),
                        'client_id': booking.get('telegram_id', ''),
                        'client_username': booking.get('username', '')
                    })
        
        # Сортировка по дате запроса
        reschedule_requests.sort(key=lambda x: x.get('requested_at', ''), reverse=True)
        
        return reschedule_requests
    
    def get_reschedule_info(self, booking_id: str) -> Optional[Dict]:
        """Получает информацию о переносе по ID записи"""
        bookings = self._load_bookings()
        
        if booking_id not in bookings:
            return None
        
        booking = bookings[booking_id]
        
        if booking.get('status') != 'перенос (ожидание мастера)':
            return None
        
        original_booking_id = booking.get('original_booking_id')
        if not original_booking_id or original_booking_id not in bookings:
            return None
        
        original_booking = bookings[original_booking_id]
        
        return {
            'reschedule_id': booking_id,
            'original_booking_id': original_booking_id,
            'new_booking_id': booking_id,
            'client_name': booking.get('name', ''),
            'client_phone': booking.get('phone', ''),
            'old_date': original_booking.get('date', ''),
            'old_time': original_booking.get('time', ''),
            'new_date': booking.get('date', ''),
            'new_time': booking.get('time', ''),
            'service': booking.get('service', ''),
            'requested_at': booking.get('created_at', ''),
            'client_id': booking.get('telegram_id', ''),
            'client_username': booking.get('username', '')
        }
    
    def get_reschedule_requests_count(self) -> int:
        """Получает количество запросов на перенос"""
        return len(self.get_reschedule_requests())
    
    # === Методы для пользователей ===
    
    def save_user_phone(self, telegram_id: str, phone: str):
        """Сохраняет телефон пользователя"""
        users = self._load_users()
        
        users[str(telegram_id)] = {
            'phone': phone,
            'last_updated': datetime.now().isoformat()
        }
        
        self._save_users(users)
        print(f"✅ Телефон сохранен для пользователя {telegram_id}")
    
    def get_user_phone(self, telegram_id: str) -> Optional[str]:
        """Получает телефон пользователя"""
        users = self._load_users()
        user_data = users.get(str(telegram_id))
        return user_data.get('phone') if user_data else None
    
    # === Вспомогательные методы ===
    
    def _load_bookings(self) -> Dict:
        """Загружает записи из файла"""
        if self._bookings_cache is not None:
            return self._bookings_cache
        
        try:
            with open(self.bookings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        
        self._bookings_cache = data
        return data
    
    def _save_bookings(self, data: Dict):
        """Сохраняет записи в файл"""
        with open(self.bookings_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self._bookings_cache = data
    
    def _load_users(self) -> Dict:
        """Загружает данные пользователей"""
        if self._users_cache is not None:
            return self._users_cache
        
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        
        self._users_cache = data
        return data
    
    def _save_users(self, data: Dict):
        """Сохраняет данные пользователей"""
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self._users_cache = data
    
    # === Методы для мастера ===
    
    def get_bookings_by_status(self, status: str) -> List[Dict]:
        """Получает записи по статусу"""
        bookings = self._load_bookings()
        
        result = []
        for booking_id, booking in bookings.items():
            if booking.get('status') == status:
                result.append({
                    'booking_id': booking_id,
                    **booking
                })
        
        # Сортировка по дате
        result.sort(key=lambda x: (
            x.get('date', ''),
            x.get('time', '')
        ))
        
        return result
    
    def get_statistics(self) -> Dict[str, int]:
        """Возвращает статистику записей"""
        bookings = self._load_bookings()
        
        stats = {
            'total': len(bookings),
            'ожидает': 0,
            'подтверждено': 0,
            'выполнено': 0,
            'перенос (ожидание мастера)': 0,
            'перенос (ожидание клиента)': 0,
            'перенесена': 0,
            'отклонено мастером': 0,
            'отменено': 0
        }
        
        for booking in bookings.values():
            status = booking.get('status')
            if status in stats:
                stats[status] += 1
        
        return stats
    
    def find_booking_by_row_index(self, row_index: int) -> Optional[Dict]:
        """Находит запись по индексу строки (для совместимости со старым кодом)"""
        bookings = self._load_bookings()
        
        # Преобразуем в список для доступа по индексу
        bookings_list = list(bookings.items())
        
        if 0 <= row_index < len(bookings_list):
            booking_id, booking = bookings_list[row_index]
            return {'booking_id': booking_id, **booking}
        
        return None