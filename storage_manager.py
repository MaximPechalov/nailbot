"""
Упрощенный StorageManager с поддержкой нового менеджера переносов
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
        
        # Инициализируем менеджер переносов
        from reschedule_manager import RescheduleManager
        self.reschedule_manager = RescheduleManager(self)
        
        # Менеджер доступности будет установлен позже
        self.availability_manager = None
    
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
    
    # === Основные методы ===
    
    def add_booking(self, booking_data: Dict[str, Any]) -> str:
        """Добавляет запись во все хранилища"""
        # Генерируем booking_id
        booking_id = str(uuid4())
        booking_data['booking_id'] = booking_id
        booking_data['created_at'] = datetime.now().isoformat()
        
        # Устанавливаем статус по умолчанию, если не указан
        if 'status' not in booking_data:
            booking_data['status'] = 'ожидает'
        
        # Сохраняем в локальное JSON хранилище
        bookings = self._load_bookings()
        bookings[booking_id] = booking_data
        self._save_bookings(bookings)
        print(f"✅ Запись {booking_id[:8]}... сохранена в JSON")
        
        # Сохраняем в Google Sheets/CSV
        if self.google_sheets:
            try:
                # Копируем данные для Google Sheets с ID
                gs_data = booking_data.copy()
                
                # Убедимся, что есть все необходимые поля
                gs_data.setdefault('status_updated', '')
                gs_data.setdefault('reschedule_id', '')
                gs_data.setdefault('original_booking_id', '')
                
                self.google_sheets.add_booking(gs_data)
                print(f"✅ Запись {booking_id[:8]}... сохранена в Google Sheets/CSV")
            except Exception as e:
                print(f"⚠️ Ошибка сохранения в Google Sheets/CSV: {e}")
        
        return booking_id
    
    def update_booking_status(self, booking_id: str, status: str, 
                             master_comment: str = None) -> bool:
        """Обновляет статус записи во всех хранилищах"""
        bookings = self._load_bookings()
        
        if booking_id not in bookings:
            print(f"❌ Запись {booking_id} не найдена в хранилище")
            return False
        
        # Обновляем в JSON хранилище
        old_status = bookings[booking_id].get('status')
        bookings[booking_id]['status'] = status
        bookings[booking_id]['status_updated'] = datetime.now().isoformat()
        if master_comment:
            bookings[booking_id]['master_comment'] = master_comment
        
        self._save_bookings(bookings)
        print(f"✅ Статус записи {booking_id[:8]}... изменен: {old_status} -> {status}")
        
        # Обновляем в Google Sheets/CSV
        if self.google_sheets:
            try:
                booking = bookings[booking_id]
                
                # Собираем данные для поиска записи в таблице
                gs_data = {
                    'booking_id': booking_id,
                    'name': booking.get('name', ''),
                    'date': booking.get('date', ''),
                    'time': booking.get('time', ''),
                    'phone': booking.get('phone', '')
                }
                
                success = self.google_sheets.add_status(gs_data, status)
                if not success:
                    print(f"⚠️ Не удалось обновить статус в Google Sheets")
                
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
    
    # === Методы для работы с переносами (делегируем RescheduleManager) ===
    
    def request_reschedule(self, original_booking_id: str, new_booking_data: Dict) -> tuple:
        """Клиент запрашивает перенос записи"""
        return self.reschedule_manager.request_reschedule(original_booking_id, new_booking_data)
    
    def offer_reschedule(self, original_booking_id: str, new_date: str, new_time: str) -> tuple:
        """Мастер предлагает перенос записи"""
        return self.reschedule_manager.offer_reschedule(original_booking_id, new_date, new_time)
    
    def accept_reschedule(self, reschedule_booking_id: str, accepted_by: str) -> tuple:
        """Принимает перенос"""
        return self.reschedule_manager.accept_reschedule(reschedule_booking_id, accepted_by)
    
    def reject_reschedule(self, reschedule_booking_id: str, rejected_by: str, reason: str = "") -> tuple:
        """Отклоняет перенос"""
        return self.reschedule_manager.reject_reschedule(reschedule_booking_id, rejected_by, reason)
    
    def cancel_reschedule_request(self, original_booking_id: str) -> tuple:
        """Клиент отменяет свой запрос на перенос"""
        return self.reschedule_manager.cancel_reschedule_request(original_booking_id)
    
    def get_reschedule_info(self, booking_id: str) -> Optional[Dict]:
        """Получает информацию о переносе"""
        return self.reschedule_manager.get_reschedule_info(booking_id)
    
    def get_reschedule_requests(self) -> List[Dict]:
        """Получает все активные запросы на перенос"""
        return self.reschedule_manager.get_active_reschedules('client_requested')
    
    def get_reschedule_offers(self) -> List[Dict]:
        """Получает все активные предложения переноса"""
        return self.reschedule_manager.get_active_reschedules('master_offered')
    
    def get_reschedule_requests_count(self) -> int:
        """Получает количество запросы на перенос"""
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
            'запрос переноса': 0,
            'предложение переноса': 0,
            'отклонено': 0,
            'отменено': 0
        }
        
        for booking in bookings.values():
            status = booking.get('status')
            if status in stats:
                stats[status] += 1
        
        return stats
    
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