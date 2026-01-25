"""
Сервис для отправки уведомлений - обновлен для новой логики переносов
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
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Подтвердить", 
                                       callback_data=f"action_confirm_{booking_data['booking_id']}"),
                    InlineKeyboardButton("❌ Отклонить", 
                                       callback_data=f"action_reject_{booking_data['booking_id']}")
                ],
                [
                    InlineKeyboardButton("🔄 Предложить перенос", 
                                       callback_data=f"reschedule_master_offer_{booking_data['booking_id']}")
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
    
    async def notify_master_reschedule_request(self, old_booking: dict, new_booking: dict, 
                                              user, new_booking_id: str):
        """Уведомляет мастера о запросе переноса записи"""
        try:
            message = self._format_reschedule_request_message(old_booking, new_booking, user)
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Принять перенос", 
                                       callback_data=f"action_accept_{new_booking_id}"),
                    InlineKeyboardButton("❌ Отклонить перенос", 
                                       callback_data=f"action_reject_{new_booking_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=MASTER_CHAT_ID,
                text=message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
            print(f"✅ Уведомление о переносе отправлено мастеру")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка уведомления мастера о переносе: {e}")
            return False
    
    async def notify_master_client_decision(self, booking_id: str, decision: str, 
                                           client_name: str, date: str, time: str):
        """Уведомляет мастера о решении клиента"""
        try:
            decision_text = "принял" if decision == 'accept' else "отклонил"
            
            message = (
                f"📢 <b>КЛИЕНТ {decision_text.upper()} ПРЕДЛОЖЕНИЕ</b>\n\n"
                f"👤 Клиент: <b>{client_name}</b>\n"
                f"📅 Дата: {date}\n"
                f"⏰ Время: {time}\n\n"
                f"✅ Клиент {decision_text} ваше предложение."
            )
            
            await self.bot.send_message(
                chat_id=MASTER_CHAT_ID,
                text=message,
                parse_mode='HTML'
            )
            
            print(f"✅ Мастер уведомлен о решении клиента: {decision}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка уведомления мастера о решении клиента: {e}")
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
    
    async def notify_client_reschedule_offer(self, booking_id: str, new_date: str, new_time: str,
                                           user_id: str, user_name: str):
        """Отправляет клиенту предложение о переносе от мастера"""
        try:
            message = (
                f"📨 <b>ПРЕДЛОЖЕНИЕ О ПЕРЕНОСЕ ОТ МАСТЕРА</b>\n\n"
                f"👋 {user_name}, мастер предлагает новое время для вашей записи:\n\n"
                f"🔄 <b>Предлагаемое время:</b>\n"
                f"📅 Дата: {new_date}\n"
                f"⏰ Время: {new_time}\n\n"
                f"Вы согласны на это время?"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Да, согласен", 
                                       callback_data=f"reschedule_client_accept_{booking_id}"),
                    InlineKeyboardButton("❌ Нет, не согласен", 
                                       callback_data=f"reschedule_client_reject_{booking_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
            print(f"✅ Клиенту {user_id} отправлено предложение о переносе")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка отправки предложения о переносе: {e}")
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
    
    def _format_reschedule_request_message(self, old_booking: dict, new_booking: dict, user) -> str:
        """Форматирует сообщение о запросе переноса"""
        return (f"🔄 <b>ЗАПРОС НА ПЕРЕНОС ОТ КЛИЕНТА</b>\n\n"
                f"👤 <b>{user.first_name or 'Клиент'}</b>\n"
                f"📱 @{user.username or 'без username'}\n\n"
                f"📅 <b>Текущее время:</b>\n"
                f"{old_booking.get('date', '')} в {old_booking.get('time', '')}\n\n"
                f"🔄 <b>Предлагаемое время:</b>\n"
                f"{new_booking.get('date', '')} в {new_booking.get('time', '')}\n\n"
                f"💅 Услуга: {old_booking.get('service', '')}\n"
                f"📞 Телефон: {old_booking.get('phone', '')}\n\n"
                f"⏱️ Запрошено: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    
    def _format_client_notification(self, booking: dict, status: str, user_name: str) -> str:
        """Форматирует уведомление для клиента"""
        status_messages = {
            'подтверждено': (
                f"🎉 Отличные новости, {user_name}!\n\n"
                f"✅ Ваша запись на <b>{booking.get('date', '??.??.????')}</b> "
                f"в <b>{booking.get('time', '??:??')}</b> "
                f"на услугу <b>'{booking.get('service', 'без услуги')}'</b> ПОДТВЕРЖДЕНА!\n\n"
                f"Ждем вас в салоне! 💅"
            ),
            'отклонено': (
                f"❌ К сожалению, {user_name}...\n\n"
                f"Ваша запись на <b>{booking.get('date', '??.??.????')}</b> "
                f"в <b>{booking.get('time', '??:??')}</b> "
                f"на услугу <b>'{booking.get('service', 'без услуги')}'</b> была ОТКЛОНЕНА.\n\n"
                f"Пожалуйста, выберите другое время."
            ),
            'выполнено': (
                f"✨ Спасибо за визит, {user_name}!\n\n"
                f"Ваша запись отмечена как ВЫПОЛНЕНА.\n\n"
                f"Будем рады видеть вас снова! 💅"
            ),
            'отменено': (
                f"⏸️ Запись отменена, {user_name}.\n\n"
                f"Ваша запись на <b>{booking.get('date', '??.??.????')}</b> "
                f"в <b>{booking.get('time', '??:??')}</b> была отменена.\n\n"
                f"Вы можете записаться на другое время."
            ),
            'запрос переноса': (
                f"🔄 Запрос на перенос отправлен, {user_name}!\n\n"
                f"Ваш запрос на перенос записи с <b>{booking.get('date', '??.??.????')}</b> "
                f"в <b>{booking.get('time', '??:??')}</b> отправлен мастеру.\n\n"
                f"⏳ Ожидайте подтверждения."
            ),
            'предложение переноса': (
                f"📨 Получено предложение переноса, {user_name}!\n\n"
                f"Мастер предлагает новое время для вашей записи.\n\n"
                f"Проверьте предложение в разделе '📅 Мои записи'."
            )
        }
        
        return status_messages.get(status, 
            f"Статус вашей записи изменен на: {status}")