from telegram import Bot
from config import MASTER_CHAT_ID, TELEGRAM_BOT_TOKEN

class NotificationManager:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    async def notify_master(self, booking_data: dict, user):
        """Отправляет уведомление мастеру о новой записи"""
        message = f"""
        📢 НОВАЯ ЗАПИСЬ!
        
        👤 Клиент: {booking_data['name']}
        📱 Телефон: {booking_data['phone']}
        📅 Дата: {booking_data['date']}
        ⏰ Время: {booking_data['time']}
        💅 Услуга: {booking_data['service']}
        
        Telegram: @{user.username if user.username else 'нет'}
        ID: {user.id}
        
        ⏱️ Запись создана: {booking_data['timestamp']}
        """
        
        try:
            await self.bot.send_message(
                chat_id=MASTER_CHAT_ID,
                text=message
            )
            print(f"✅ Уведомление отправлено мастеру (Chat ID: {MASTER_CHAT_ID})")
            return True
        except Exception as e:
            print(f"❌ Ошибка при отправке уведомления: {e}")
            return False