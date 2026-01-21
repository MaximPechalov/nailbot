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
            
            # Создаем кнопки
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
            # Временное решение: сохраняем в лог
            try:
                with open('error_log.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{datetime.now()}: {str(e)}\n")
            except:
                pass
            return False
    
    def get_booking(self, booking_id):
        """Получает данные записи по ID"""
        if not os.path.exists(self.storage_file):
            return None
        
        with open(self.storage_file, 'r', encoding='utf-8') as f:
            all_bookings = json.load(f)
        
        return all_bookings.get(booking_id)
    
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