"""
Менеджер для управления доступными временными слотами мастера
"""

import json
import os
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import copy

@dataclass
class TimeSlot:
    """Структура для временного слота"""
    date: str  # ДД.ММ.ГГГГ
    time: str  # ЧЧ:ММ
    is_available: bool = True
    booking_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'date': self.date,
            'time': self.time,
            'is_available': self.is_available,
            'booking_id': self.booking_id
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TimeSlot':
        return cls(
            date=data['date'],
            time=data['time'],
            is_available=data.get('is_available', True),
            booking_id=data.get('booking_id')
        )


class AvailabilityManager:
    """Менеджер доступных слотов"""
    
    def __init__(self, storage_manager):
        self.storage = storage_manager
        self.data_dir = 'data'
        self.availability_file = os.path.join(self.data_dir, 'availability.json')
        
        self._ensure_data_dir()
        self.default_work_hours = {
            'monday': {'start': '10:00', 'end': '20:00', 'enabled': True},
            'tuesday': {'start': '10:00', 'end': '20:00', 'enabled': True},
            'wednesday': {'start': '10:00', 'end': '20:00', 'enabled': True},
            'thursday': {'start': '10:00', 'end': '20:00', 'enabled': True},
            'friday': {'start': '10:00', 'end': '20:00', 'enabled': True},
            'saturday': {'start': '10:00', 'end': '18:00', 'enabled': True},
            'sunday': {'start': '10:00', 'end': '16:00', 'enabled': False}
        }
        self.slot_duration = 60  # Длительность слота в минутах
        
        # Загружаем настройки
        self.work_hours = self._load_work_hours()
    
    def _ensure_data_dir(self):
        """Создает папку data если её нет"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
    
    def _load_availability(self) -> Dict:
        """Загружает данные о доступности"""
        try:
            with open(self.availability_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_availability(self, data: Dict):
        """Сохраняет данные о доступности"""
        with open(self.availability_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load_work_hours(self) -> Dict:
        """Загружает рабочие часы"""
        availability = self._load_availability()
        return availability.get('work_hours', self.default_work_hours.copy())
    
    def _save_work_hours(self):
        """Сохраняет рабочие часы"""
        availability = self._load_availability()
        availability['work_hours'] = self.work_hours
        self._save_availability(availability)
    
    def get_weekday_name(self, date_str: str) -> str:
        """Возвращает название дня недели на английском для date_str"""
        try:
            date_obj = datetime.strptime(date_str, '%d.%m.%Y')
            days = ['monday', 'tuesday', 'wednesday', 'thursday', 
                   'friday', 'saturday', 'sunday']
            return days[date_obj.weekday()]
        except:
            return 'monday'  # По умолчанию
    
    def generate_slots_for_month(self, year: int = None, month: int = None) -> Dict[str, List[TimeSlot]]:
        """Генерирует слоты на указанный месяц"""
        today = datetime.now()
        if year is None:
            year = today.year
        if month is None:
            month = today.month
        
        slots_by_date = {}
        
        # Первый день месяца
        current_date = date(year, month, 1)
        
        # Генерируем до конца месяца
        while current_date.month == month:
            date_str = current_date.strftime('%d.%m.%Y')
            weekday = self.get_weekday_name(date_str)
            
            # Проверяем, рабочий ли это день
            day_settings = self.work_hours.get(weekday, {'enabled': False})
            if day_settings.get('enabled', False):
                start_time = datetime.strptime(day_settings['start'], '%H:%M')
                end_time = datetime.strptime(day_settings['end'], '%H:%M')
                
                slots = []
                current_time = start_time
                
                while current_time < end_time:
                    time_str = current_time.strftime('%H:%M')
                    slots.append(TimeSlot(date=date_str, time=time_str))
                    current_time += timedelta(minutes=self.slot_duration)
                
                slots_by_date[date_str] = slots
            
            current_date += timedelta(days=1)
        
        return slots_by_date
    
    def get_available_slots(self, date_str: str) -> List[str]:
        """Возвращает список доступных времен для указанной даты"""
        # Генерируем слоты для даты
        date_obj = datetime.strptime(date_str, '%d.%m.%Y')
        month_slots = self.generate_slots_for_month(date_obj.year, date_obj.month)
        
        available_slots = []
        
        if date_str in month_slots:
            # Получаем существующие записи на эту дату
            all_bookings = self.storage._load_bookings()
            booked_times = []
            
            for booking in all_bookings.values():
                if booking.get('date') == date_str:
                    status = booking.get('status', '')
                    # Учитываем только активные и подтвержденные записи
                    if status in ['ожидает', 'подтверждено', 'запрос переноса']:
                        booked_times.append(booking.get('time'))
            
            # Фильтруем свободные слоты
            for slot in month_slots[date_str]:
                if slot.time not in booked_times:
                    available_slots.append(slot.time)
        
        return sorted(available_slots)
    
    def is_slot_available(self, date_str: str, time_str: str) -> bool:
        """Проверяет, доступен ли слот"""
        available_slots = self.get_available_slots(date_str)
        return time_str in available_slots
    
    def update_work_hours(self, weekday: str, start: str, end: str, enabled: bool = True):
        """Обновляет рабочие часы для дня недели - ИСПРАВЛЕННЫЙ МЕТОД"""
        if weekday in self.work_hours:
            # ВАЖНОЕ ИСПРАВЛЕНИЕ: всегда обновляем все поля
            new_settings = {
                'start': start,
                'end': end,
                'enabled': enabled  # Исправлено: сохраняем переданное значение
            }
            
            self.work_hours[weekday] = new_settings
            self._save_work_hours()
            
            print(f"✅ Рабочие часы обновлены для {weekday}: start={start}, end={end}, enabled={enabled}")
            return True
        return False
    
    def set_day_off(self, date_str: str):
        """Устанавливает выходной на конкретную дату"""
        availability = self._load_availability()
        
        if 'days_off' not in availability:
            availability['days_off'] = []
        
        if date_str not in availability['days_off']:
            availability['days_off'].append(date_str)
            self._save_availability(availability)
            return True
        
        return False
    
    def remove_day_off(self, date_str: str):
        """Удаляет выходной на конкретную дату"""
        availability = self._load_availability()
        
        if 'days_off' in availability and date_str in availability['days_off']:
            availability['days_off'].remove(date_str)
            self._save_availability(availability)
            return True
        
        return False
    
    def get_days_off(self) -> List[str]:
        """Возвращает список выходных дней"""
        availability = self._load_availability()
        return availability.get('days_off', [])
    
    def get_work_hours_display(self) -> str:
        """Возвращает рабочие часы в читаемом формате"""
        days_ru = {
            'monday': 'Понедельник',
            'tuesday': 'Вторник',
            'wednesday': 'Среда',
            'thursday': 'Четверг',
            'friday': 'Пятница',
            'saturday': 'Суббота',
            'sunday': 'Воскресенье'
        }
        
        result = "🕒 Рабочие часы:\n\n"
        
        for eng_day, ru_day in days_ru.items():
            settings = self.work_hours.get(eng_day, {})
            enabled = settings.get('enabled', False)  # Исправлено: по умолчанию False
            start = settings.get('start', '--:--')
            end = settings.get('end', '--:--')
            
            status = "✅" if enabled else "❌"
            hours = f"{start} - {end}" if enabled else "выходной"
            
            result += f"{status} {ru_day}: {hours}\n"
        
        return result
    
    def get_available_dates(self, days_ahead: int = 30) -> List[str]:
        """Возвращает список доступных дат на указанное количество дней вперед"""
        available_dates = []
        today = datetime.now()
        
        for i in range(1, days_ahead + 1):
            check_date = today + timedelta(days=i)
            date_str = check_date.strftime('%d.%m.%Y')
            
            # Проверяем, не выходной ли это день
            days_off = self.get_days_off()
            if date_str in days_off:
                continue
            
            # Проверяем, рабочий ли это день по расписанию
            weekday = self.get_weekday_name(date_str)
            day_settings = self.work_hours.get(weekday, {'enabled': False})
            
            if day_settings.get('enabled', False):
                # Проверяем, есть ли свободные слоты
                available_slots = self.get_available_slots(date_str)
                if available_slots:  # Если есть хотя бы один свободный слот
                    available_dates.append(date_str)
        
        return available_dates