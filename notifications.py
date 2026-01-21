from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot
from datetime import datetime
from config import MASTER_CHAT_ID, TELEGRAM_BOT_TOKEN
import json
import os

class NotificationManager:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.storage_file = 'bookings_storage.json'
        self._ensure_storage()
    
    def _ensure_storage(self):
        """Создает файл хранилища если его нет"""
        if not os.path.exists(self.storage_file):
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            print(f"✅ Создан файл хранилища: {self.storage_file}")
    
    async def notify_master(self, booking_data: dict, user):
        """Отправляет уведомление мастеру с кнопками"""
        try:
            message = f"""
📢 НОВАЯ ЗАПИСЬ!

👤 Клиент: {booking_data['name']}
📱 Телефон: {booking_data['phone']}
📅 Дата: {booking_data['date']}
⏰ Время: {booking_data['time']}
💅 Услуга: {booking_data['service']}

👤 Telegram: @{user.username if user.username else 'не указан'}
📊 ID: {user.id}

⏱️ Запись создана: {booking_data['timestamp']}
"""
            
            # Создаем уникальный ID для записи
            booking_id = f"booking_{user.id}_{int(datetime.now().timestamp())}"
            
            # Создаем кнопки для мастера
            keyboard = [
                [
                    InlineKeyboardButton("✅ Подтвердить", 
                                       callback_data=f"confirm_{booking_id}"),
                    InlineKeyboardButton("❌ Отклонить", 
                                       callback_data=f"reject_{booking_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Сохраняем данные
            booking_data['booking_id'] = booking_id
            booking_data['user_id'] = user.id
            booking_data['status'] = 'ожидает'  # Начальный статус
            
            # Загружаем и обновляем хранилище
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                all_bookings = json.load(f)
            
            all_bookings[booking_id] = booking_data
            
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(all_bookings, f, ensure_ascii=False, indent=2)
            
            # Отправляем сообщение мастеру
            await self.bot.send_message(
                chat_id=MASTER_CHAT_ID,
                text=message,
                reply_markup=reply_markup
            )
            
            print(f"✅ Уведомление отправлено мастеру (Chat ID: {MASTER_CHAT_ID})")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка при отправке уведомления: {e}")
            try:
                with open('error_log.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{datetime.now()}: {str(e)}\n")
            except:
                pass
            return False
    
    async def send_master_menu(self):
        """Отправляет меню мастера с кнопками"""
        try:
            keyboard = [
                [
                    InlineKeyboardButton("📋 Активные записи", callback_data="master_active"),
                    InlineKeyboardButton("✅ Выполненные", callback_data="master_completed")
                ],
                [
                    InlineKeyboardButton("⏳ Ожидают подтверждения", callback_data="master_pending"),
                    InlineKeyboardButton("📊 Статистика", callback_data="master_stats")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=MASTER_CHAT_ID,
                text="🎛️ Панель управления мастера\nВыберите действие:",
                reply_markup=reply_markup
            )
            
            print(f"✅ Меню мастера отправлено")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка отправки меню мастера: {e}")
            return False
    
    def get_booking(self, booking_id):
        """Получает данные записи по ID"""
        if not os.path.exists(self.storage_file):
            return None
        
        with open(self.storage_file, 'r', encoding='utf-8') as f:
            all_bookings = json.load(f)
        
        return all_bookings.get(booking_id)
    
    def get_bookings_by_status(self, status):
        """Получает все записи по статусу"""
        if not os.path.exists(self.storage_file):
            return {}
        
        with open(self.storage_file, 'r', encoding='utf-8') as f:
            all_bookings = json.load(f)
        
        return {k: v for k, v in all_bookings.items() if v.get('status') == status}
    
    def update_booking_status(self, booking_id, status):
        """Обновляет статус записи"""
        if not os.path.exists(self.storage_file):
            return False
        
        with open(self.storage_file, 'r', encoding='utf-8') as f:
            all_bookings = json.load(f)
        
        if booking_id in all_bookings:
            all_bookings[booking_id]['status'] = status
            all_bookings[booking_id]['status_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(all_bookings, f, ensure_ascii=False, indent=2)
            
            return True
        
        return False
    
    def remove_booking(self, booking_id):
        """Удаляет запись из хранилища"""
        if not os.path.exists(self.storage_file):
            return False
        
        with open(self.storage_file, 'r', encoding='utf-8') as f:
            all_bookings = json.load(f)
        
        if booking_id in all_bookings:
            del all_bookings[booking_id]
            
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(all_bookings, f, ensure_ascii=False, indent=2)
            
            return True
        
        return False
    
    def get_all_bookings(self):
        """Получает все записи"""
        if not os.path.exists(self.storage_file):
            return {}
        
        with open(self.storage_file, 'r', encoding='utf-8') as f:
            all_bookings = json.load(f)
        
        return all_bookings
    
    def get_statistics(self):
        """Возвращает статистику записей"""
        if not os.path.exists(self.storage_file):
            return {}
        
        with open(self.storage_file, 'r', encoding='utf-8') as f:
            all_bookings = json.load(f)
        
        total = len(all_bookings)
        pending = len([b for b in all_bookings.values() if b.get('status') == 'ожидает'])
        confirmed = len([b for b in all_bookings.values() if b.get('status') == 'подтверждено'])
        completed = len([b for b in all_bookings.values() if b.get('status') == 'выполнено'])
        rejected = len([b for b in all_bookings.values() if b.get('status') == 'отклонено мастером'])
        cancelled = len([b for b in all_bookings.values() if b.get('status') == 'отменено'])
        
        today = datetime.now().strftime('%Y-%m-%d')
        today_bookings = len([b for b in all_bookings.values() 
                             if b.get('date') == today])
        
        return {
            'total': total,
            'pending': pending,
            'confirmed': confirmed,
            'completed': completed,
            'rejected': rejected,
            'cancelled': cancelled,
            'today': today_bookings
        }