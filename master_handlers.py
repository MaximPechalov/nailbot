from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime

class MasterHandlers:
    def __init__(self, google_sheets):
        self.google_sheets = google_sheets
    
    async def notify_master_with_buttons(self, booking_data: dict, user, bot):
        """Отправляет уведомление мастеру с кнопками подтверждения"""
        from config import MASTER_CHAT_ID
        
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
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{booking_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{booking_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            # Сохраняем данные записи для последующего использования
            booking_data['booking_id'] = booking_id
            booking_data['user_id'] = user.id
            booking_data['message_id'] = None  # Будет заполнено после отправки
            
            # Отправляем сообщение мастеру
            sent_message = await bot.send_message(
                chat_id=MASTER_CHAT_ID,
                text=message,
                reply_markup=reply_markup
            )
            
            # Сохраняем ID сообщения
            booking_data['message_id'] = sent_message.message_id
            
            # Сохраняем данные в контексте
            if 'master_bookings' not in bot.bot_data:
                bot.bot_data['master_bookings'] = {}
            bot.bot_data['master_bookings'][booking_id] = booking_data
            
            print(f"✅ Уведомление с кнопками отправлено мастеру (Chat ID: {MASTER_CHAT_ID})")
            print(f"📝 ID записи: {booking_id}")
            
            return sent_message.message_id
            
        except Exception as e:
            print(f"❌ Ошибка при отправке уведомления: {e}")
            return None
    
    async def handle_master_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатия кнопок мастера"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        booking_id = data.split('_')[1] if '_' in data else None
        
        # Получаем данные записи
        booking_data = context.bot_data.get('master_bookings', {}).get(booking_id)
        
        if not booking_data:
            await query.edit_message_text("❌ Запись не найдена или устарела.")
            return
        
        user_id = booking_data.get('user_id')
        
        if 'confirm' in data:
            # Мастер подтвердил запись
            await self._confirm_booking(query, booking_data, user_id, context)
            
        elif 'reject' in data:
            # Мастер отклонил запись
            await self._reject_booking(query, booking_data, user_id, context)
        
        # Удаляем запись из временного хранилища
        if booking_id in context.bot_data.get('master_bookings', {}):
            del context.bot_data['master_bookings'][booking_id]
    
    async def _confirm_booking(self, query, booking_data, user_id, context):
        """Подтверждение записи мастером"""
        try:
            # Обновляем сообщение у мастера
            await query.edit_message_text(
                f"✅ Запись подтверждена!\n\n"
                f"👤 Клиент: {booking_data['name']}\n"
                f"📅 Дата: {booking_data['date']}\n"
                f"⏰ Время: {booking_data['time']}\n"
                f"💅 Услуга: {booking_data['service']}\n\n"
                f"⏱️ Подтверждено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                reply_markup=None
            )
            
            # Отправляем уведомление клиенту
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"🎉 Отличные новости, {booking_data['name']}!\n\n"
                         f"✅ Ваша запись на {booking_data['date']} в {booking_data['time']} "
                         f"на услугу '{booking_data['service']}' ПОДТВЕРЖДЕНА мастером!\n\n"
                         f"Ждем вас в салоне! 💅"
                )
                print(f"✅ Клиенту {user_id} отправлено уведомление о подтверждении")
            except Exception as e:
                print(f"⚠️ Не удалось отправить уведомление клиенту: {e}")
            
            # Обновляем статус в Google Sheets/CSV
            self._update_booking_status(booking_data, 'confirmed')
            
        except Exception as e:
            print(f"❌ Ошибка при подтверждении записи: {e}")
    
    async def _reject_booking(self, query, booking_data, user_id, context):
        """Отклонение записи мастером"""
        try:
            # Обновляем сообщение у мастера
            await query.edit_message_text(
                f"❌ Запись отклонена\n\n"
                f"👤 Клиент: {booking_data['name']}\n"
                f"📅 Дата: {booking_data['date']}\n"
                f"⏰ Время: {booking_data['time']}\n"
                f"💅 Услуга: {booking_data['service']}\n\n"
                f"⏱️ Отклонено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                reply_markup=None
            )
            
            # Отправляем уведомление клиенту
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ К сожалению, {booking_data['name']}...\n\n"
                         f"Ваша запись на {booking_data['date']} в {booking_data['time']} "
                         f"на услугу '{booking_data['service']}' была ОТКЛОНЕНА мастером.\n\n"
                         f"Пожалуйста, выберите другое время или свяжитесь с нами для уточнения. 📞"
                )
                print(f"✅ Клиенту {user_id} отправлено уведомление об отклонении")
            except Exception as e:
                print(f"⚠️ Не удалось отправить уведомление клиенту: {e}")
            
            # Обновляем статус в Google Sheets/CSV
            self._update_booking_status(booking_data, 'rejected')
            
        except Exception as e:
            print(f"❌ Ошибка при отклонении записи: {e}")
    
    def _update_booking_status(self, booking_data, status):
        """Обновляет статус записи в хранилище"""
        try:
            # Добавляем статус и время обновления
            booking_data['status'] = status
            booking_data['status_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Обновляем в Google Sheets/CSV
            self.google_sheets.add_status(booking_data, status)
            
            print(f"📊 Статус записи обновлен: {status}")
            
        except Exception as e:
            print(f"⚠️ Ошибка при обновлении статуса: {e}")