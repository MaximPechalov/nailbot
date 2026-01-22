"""
Сервис для отправки уведомлений
"""

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from config import TELEGRAM_BOT_TOKEN, MASTER_CHAT_ID
from datetime import datetime

class NotificationService:
    def __init__(self, storage_manager):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.storage = storage_manager
    
    async def notify_master_new_booking(self, booking_data: dict):
        """Уведомляет мастера о новой записи"""
        try:
            message = self._format_new_booking_message(booking_data)
            
            # Создаем кнопки для действий
            keyboard = [
                [
                    InlineKeyboardButton("✅ Подтвердить", 
                                       callback_data=f"action_confirm_{booking_data['booking_id']}"),
                    InlineKeyboardButton("❌ Отклонить", 
                                       callback_data=f"action_reject_{booking_data['booking_id']}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=MASTER_CHAT_ID,
                text=message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
            print(f"✅ Уведомление отправлено мастеру")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка уведомления мастера: {e}")
            return False
    
    async def notify_client_booking_update(self, booking_id: str, status: str, 
                                          user_id: str, user_name: str):
        """Уведомляет клиента об изменении статуса"""
        try:
            booking = self.storage.get_booking(booking_id)
            if not booking:
                return False
            
            message = self._format_client_notification(booking, status, user_name)
            
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='HTML'
            )
            
            print(f"✅ Клиент {user_id} уведомлен о статусе {status}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка уведомления клиента: {e}")
            return False
    
    def _format_new_booking_message(self, booking: dict) -> str:
        """Форматирует сообщение о новой записи"""
        return (f"📢 <b>НОВАЯ ЗАПИСЬ!</b>\n\n"
                f"👤 <b>{booking.get('name', 'Без имени')}</b>\n"
                f"📱 {booking.get('phone', 'без телефона')}\n"
                f"📅 {booking.get('date', '??.??.????')} в {booking.get('time', '??:??')}\n"
                f"💅 {booking.get('service', 'без услуги')}\n\n"
                f"🆔 {booking.get('booking_id', '')[:8]}...\n"
                f"⏱️ {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    
    def _format_client_notification(self, booking: dict, status: str, user_name: str) -> str:
        """Форматирует уведомление для клиента"""
        status_messages = {
            'подтверждено': (
                f"🎉 Отличные новости, {user_name}!\n\n"
                f"✅ Ваша запись на <b>{booking.get('date', '??.??.????')}</b> "
                f"в <b>{booking.get('time', '??:??')}</b> "
                f"на услугу <b>'{booking.get('service', 'без услуги')}'</b> ПОДТВЕРЖДЕНА!\n\n"
                f"Ждем вас в салоне! 💅\n\n"
                f"📍 Адрес: ул. Красивых ногтей, д. 10\n"
                f"📞 Телефон: +7 (999) 123-45-67"
            ),
            'отклонено мастером': (
                f"❌ К сожалению, {user_name}...\n\n"
                f"Ваша запись на <b>{booking.get('date', '??.??.????')}</b> "
                f"в <b>{booking.get('time', '??:??')}</b> "
                f"на услугу <b>'{booking.get('service', 'без услуги')}'</b> была ОТКЛОНЕНА.\n\n"
                f"Пожалуйста, выберите другое время или свяжитесь с нами.\n\n"
                f"📞 Телефон: +7 (999) 123-45-67\n"
                f"✉️ Email: support@manicure.ru"
            ),
            'выполнено': (
                f"✨ Спасибо за визит, {user_name}!\n\n"
                f"Ваша запись на <b>{booking.get('date', '??.??.????')}</b> "
                f"в <b>{booking.get('time', '??:??')}</b> "
                f"на услугу <b>'{booking.get('service', 'без услуги')}'</b> отмечена как ВЫПОЛНЕНА.\n\n"
                f"Будем рады видеть вас снова! 💅\n\n"
                f"📍 Адрес: ул. Красивых ногтей, д. 10\n"
                f"📞 Телефон: +7 (999) 123-45-67"
            )
        }
        
        return status_messages.get(status, 
            f"Статус вашей записи изменен на: {status}")