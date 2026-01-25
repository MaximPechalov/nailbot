"""
Упрощенный модуль для панели мастера - только обработка callback
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta
import re
from config import MASTER_CHAT_ID

class MasterPanel:
    def __init__(self, storage_manager, notification_service):
        self.storage = storage_manager
        self.notifications = notification_service
        
        # Состояния для переноса мастером
        self.MASTER_RESCHEDULE_DATE = 100
        self.MASTER_RESCHEDULE_TIME = 101
        self.MASTER_RESCHEDULE_CONFIRM = 102
    
    def _get_date_keyboard_master(self, start_day=1, days=5):
        """Создает клавиатуру с датами для мастера"""
        keyboard = []
        row = []
        
        # Текущая дата
        today = datetime.now()
        
        # Добавляем даты
        for i in range(start_day, start_day + days):
            date = today + timedelta(days=i)
            date_str = date.strftime('%d.%m.%Y')
            
            # Форматируем красиво
            day_name = self._get_day_name(date.weekday())
            date_display = f"{date_str} ({day_name})"
            
            row.append(date_display)
            
            # Каждые 2 даты в строку
            if len(row) == 2:
                keyboard.append(row)
                row = []
        
        # Добавляем последнюю строку если есть остаток
        if row:
            keyboard.append(row)
        
        # Добавляем кнопку для ввода другой даты
        keyboard.append(['📅 Ввести другую дату'])
        
        return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    def _get_day_name(self, weekday):
        """Возвращает русское название дня недели"""
        days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Срб', 'Вск']
        return days[weekday]
    
    def _is_valid_date(self, date_str):
        """Проверяет, корректна ли дата и не в прошлом"""
        try:
            # Парсим дату
            date_obj = datetime.strptime(date_str, '%d.%m.%Y')
            
            # Проверяем, что дата не в прошлом
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if date_obj < today:
                return False
            
            # Проверяем, что дата не дальше чем через 30 дней
            max_date = today + timedelta(days=30)
            if date_obj > max_date:
                return False
            
            return True
            
        except ValueError:
            return False
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Основной обработчик callback от мастера и клиентов"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        user_id = update.effective_user.id
        print(f"📲 Получен callback: {data} от пользователя {user_id} (мастер: {user_id == int(MASTER_CHAT_ID)})")
        
        # Обрабатываем callback от клиента (переносы)
        if data.startswith('reschedule_client_'):
            parts = data.split('_')
            if len(parts) >= 4:
                action = parts[2]
                booking_id = parts[3]
                
                print(f"📞 Callback от клиента {user_id}, action: {action}, booking_id: {booking_id}")
                
                if action == 'accept':
                    await self._client_accept_reschedule(update, booking_id)
                elif action == 'reject':
                    await self._client_reject_reschedule(update, booking_id)
                return
        
        # Все остальные callback - только для мастера
        if str(user_id) != str(MASTER_CHAT_ID):
            print(f"⚠️ Не-мастер {user_id} пытается использовать мастерские callback: {data}")
            await query.edit_message_text("❌ Эта функция доступна только мастеру.")
            return
        
        # Это мастер
        if data.startswith('action_'):
            parts = data.split('_')
            if len(parts) >= 3:
                action = parts[1]
                booking_id = parts[2]
                await self._handle_booking_action(update, context, action, booking_id)
        
        elif data.startswith('reschedule_') and not data.startswith('reschedule_client_'):
            parts = data.split('_')
            if len(parts) >= 3:
                action = parts[1]
                booking_id = parts[2]
                await self._handle_reschedule_action(update, context, action, booking_id)
        
        elif data.startswith('view_'):
            view_type = data.split('_')[1]
            await self._show_view(update, context, view_type)
        
        elif data == 'menu_master':
            await self._show_main_menu(update)
    
    async def _handle_booking_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, booking_id: str):
        """Обрабатывает действие с записью"""
        booking = self.storage.get_booking(booking_id)
        
        if not booking:
            await update.callback_query.edit_message_text("❌ Запись не найдена")
            return
        
        if action == 'confirm':
            await self._confirm_booking(update, booking_id, booking)
        elif action == 'reject':
            await self._reject_booking(update, booking_id, booking)
        elif action == 'complete':
            await self._complete_booking(update, booking_id, booking)
        elif action == 'cancel':
            await self._cancel_booking(update, booking_id, booking)
        elif action == 'reschedule':
            # Начинаем процесс переноса мастером
            await self._start_master_reschedule(update, context, booking_id, booking)
    
    async def _start_master_reschedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE, booking_id: str, booking: dict):
        """Начинает процесс переноса записи мастером"""
        context.user_data['master_reschedule'] = {
            'booking_id': booking_id,
            'booking_data': booking
        }
        
        # Сохраняем состояние
        context.user_data['_conversation_state'] = self.MASTER_RESCHEDULE_DATE
        
        # Удаляем меню
        await update.callback_query.delete_message()
        
        # Отправляем выбор даты
        message = f"""
🔄 ПЕРЕНАЗНАЧИТЬ ЗАПИСЬ МАСТЕРОМ

Вы хотите перенести запись клиента:

👤 Клиент: {booking.get('name', '')}
📅 Текущая дата: {booking.get('date', '')}
⏰ Текущее время: {booking.get('time', '')}
💅 Услуга: {booking.get('service', '')}

Выберите новую дату для записи:
"""
        
        await context.bot.send_message(
            chat_id=MASTER_CHAT_ID,
            text=message,
            reply_markup=self._get_date_keyboard_master()
        )
        
        return self.MASTER_RESCHEDULE_DATE
    
    async def handle_master_reschedule_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор даты мастером для переноса"""
        # Обновляем состояние
        context.user_data['_conversation_state'] = self.MASTER_RESCHEDULE_DATE
        
        user_input = update.message.text
        
        if user_input == '📅 Ввести другую дату':
            await update.message.reply_text(
                "📝 Введите новую дату в формате ДД.ММ.ГГГГ\n"
                "Например: 25.12.2024\n\n"
                "⚠️ Дата должна быть не ранее завтрашнего дня\n"
                "и не позднее чем через 30 дней.",
                reply_markup=ReplyKeyboardRemove()
            )
            return self.MASTER_RESCHEDULE_DATE
        
        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', user_input)
        
        if date_match:
            date_str = date_match.group(1)
        else:
            date_str = user_input.strip()
        
        try:
            datetime.strptime(date_str, '%d.%m.%Y')
            
            if not self._is_valid_date(date_str):
                await update.message.reply_text(
                    "❌ Некорректная дата!\n"
                    "Дата должна быть:\n"
                    "✅ Не ранее завтрашнего дня\n"
                    "✅ Не позднее чем через 30 дней\n\n"
                    "Пожалуйста, выберите дату из списка:",
                    reply_markup=self._get_date_keyboard_master()
                )
                return self.MASTER_RESCHEDULE_DATE
                
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты!\n"
                "Пожалуйста, введите дату в формате ДД.ММ.ГГГГ\n"
                "Например: 25.12.2024\n\n"
                "Или выберите из предложенных вариантов:",
                reply_markup=self._get_date_keyboard_master()
            )
            return self.MASTER_RESCHEDULE_DATE
        
        context.user_data['master_reschedule']['new_date'] = date_str
        
        # Обновляем состояние
        context.user_data['_conversation_state'] = self.MASTER_RESCHEDULE_TIME
        
        keyboard = [
            ['10:00', '11:00', '12:00'],
            ['13:00', '14:00', '15:00'],
            ['16:00', '17:00', '18:00'],
            ['19:00', '20:00', '21:00']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "⏰ Выберите новое время для записи:",
            reply_markup=reply_markup
        )
        
        return self.MASTER_RESCHEDULE_TIME
    
    async def handle_master_reschedule_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор времени мастером для переноса"""
        # Обновляем состояние
        context.user_data['_conversation_state'] = self.MASTER_RESCHEDULE_TIME
        
        context.user_data['master_reschedule']['new_time'] = update.message.text
        
        # Обновляем состояние
        context.user_data['_conversation_state'] = self.MASTER_RESCHEDULE_CONFIRM
        
        reschedule_data = context.user_data['master_reschedule']
        booking = reschedule_data['booking_data']
        new_date = reschedule_data.get('new_date', '')
        new_time = reschedule_data.get('new_time', '')
        
        try:
            date_obj = datetime.strptime(new_date, '%d.%m.%Y')
            day_name = self._get_day_name(date_obj.weekday())
            new_date_display = f"{new_date} ({day_name})"
        except:
            new_date_display = new_date
        
        message = f"""
📋 ПОДТВЕРЖДЕНИЕ ПЕРЕНОСА МАСТЕРОМ

📅 ТЕКУЩАЯ запись:
👤 Клиент: {booking.get('name', '')}
📞 Телефон: {booking.get('phone', '')}
📅 Дата: {booking.get('date', '')}
⏰ Время: {booking.get('time', '')}
💅 Услуга: {booking.get('service', '')}

🔄 НОВАЯ запись:
📅 Дата: {new_date_display}
⏰ Время: {new_time}
💅 Услуга: {booking.get('service', '')}

После подтверждения:
• Клиент получит предложение о новом времени
• Клиент должен будет подтвердить или отклонить перенос
• Текущая запись сохранится до решения клиента

Вы уверены, что хотите предложить этот новый слот клиенту?
"""
        
        keyboard = [['✅ Да, предложить клиенту', '❌ Нет, отменить перенос']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        
        return self.MASTER_RESCHEDULE_CONFIRM
    
    async def handle_master_reschedule_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение переноса мастером"""
        # Обновляем состояние
        context.user_data['_conversation_state'] = self.MASTER_RESCHEDULE_CONFIRM
        
        if 'Да' in update.message.text:
            reschedule_data = context.user_data['master_reschedule']
            booking_id = reschedule_data['booking_id']
            booking = reschedule_data['booking_data']
            new_date = reschedule_data.get('new_date', '')
            new_time = reschedule_data.get('new_time', '')
            
            try:
                # Создаем запись с предложенным временем
                new_booking_data = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'name': booking.get('name', ''),
                    'phone': booking.get('phone', ''),
                    'date': new_date,
                    'time': new_time,
                    'service': booking.get('service', ''),
                    'telegram_id': booking.get('telegram_id', ''),
                    'username': booking.get('username', ''),
                    'status': 'перенос (ожидание клиента)',
                    'original_booking_id': booking_id,
                    'offered_by_master': True,
                    'master_proposed': True
                }
                
                # Сохраняем новую запись
                new_booking_id = self.storage.add_booking(new_booking_data)
                
                if new_booking_id:
                    # Обновляем статус старой записи
                    self.storage.update_booking_status(
                        booking_id, 
                        'перенос (ожидание клиента)'
                    )
                    
                    # Отправляем предложение клиенту
                    await self.notifications.notify_client_reschedule_offer(
                        new_booking_id,
                        new_date,
                        new_time,
                        booking.get('telegram_id'),
                        booking.get('name')
                    )
                    
                    message = f"""
✅ Предложение о переносе отправлено клиенту!

👤 Клиент: {booking.get('name', '')}
📅 Новое предложенное время: {new_date} в {new_time}
💅 Услуга: {booking.get('service', '')}

📱 Клиент получил уведомление и должен будет подтвердить или отклонить перенос.

⏳ Ожидайте решения клиента.
"""
                else:
                    message = "❌ Не удалось создать предложение о переносе."
                    
            except Exception as e:
                print(f"❌ Ошибка при создании предложения о переносе: {e}")
                message = "❌ Произошла ошибка при создании предложения о переносе."
        else:
            message = "❌ Перенос записи отменен."
        
        # Очищаем данные
        if 'master_reschedule' in context.user_data:
            del context.user_data['master_reschedule']
        if '_conversation_state' in context.user_data:
            del context.user_data['_conversation_state']
        
        # Возвращаем меню мастера
        keyboard = [
            [
                InlineKeyboardButton("📋 Активные", callback_data="view_active"),
                InlineKeyboardButton("⏳ Ожидают", callback_data="view_pending")
            ],
            [
                InlineKeyboardButton("🔄 Переносы", callback_data="view_rescheduling"),
                InlineKeyboardButton("✅ Выполненные", callback_data="view_completed")
            ],
            [
                InlineKeyboardButton("📊 Статистика", callback_data="view_stats"),
                InlineKeyboardButton("🔄 Обновить", callback_data="menu_master")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup
        )
        
        return ConversationHandler.END
    
    async def handle_master_cancel_reschedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена переноса мастером"""
        if 'master_reschedule' in context.user_data:
            del context.user_data['master_reschedule']
        if '_conversation_state' in context.user_data:
            del context.user_data['_conversation_state']
        
        await update.message.reply_text(
            "❌ Перенос записи отменен.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Возвращаем меню мастера
        await self._show_main_menu_from_message(update, context)
        
        return ConversationHandler.END
    
    async def _show_main_menu_from_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает главное меню мастера из обычного сообщения"""
        keyboard = [
            [
                InlineKeyboardButton("📋 Активные", callback_data="view_active"),
                InlineKeyboardButton("⏳ Ожидают", callback_data="view_pending")
            ],
            [
                InlineKeyboardButton("🔄 Переносы", callback_data="view_rescheduling"),
                InlineKeyboardButton("✅ Выполненные", callback_data="view_completed")
            ],
            [
                InlineKeyboardButton("📊 Статистика", callback_data="view_stats"),
                InlineKeyboardButton("🔄 Обновить", callback_data="menu_master")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=MASTER_CHAT_ID,
            text="🎛️ Панель управления мастера\nВыберите раздел:",
            reply_markup=reply_markup
        )
    
    async def _handle_reschedule_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, booking_id: str):
        """Обрабатывает действие с переносом записи (для мастера)"""
        if action == 'confirm':
            await self._confirm_reschedule(update, booking_id)
        elif action == 'reject':
            await self._reject_reschedule(update, booking_id)
    
    async def _confirm_booking(self, update: Update, booking_id: str, booking: dict):
        """Подтверждает запись"""
        success = self.storage.update_booking_status(booking_id, 'подтверждено')
        
        if success:
            await self.notifications.notify_client_booking_update(
                booking_id, 'подтверждено', 
                booking['telegram_id'], booking['name']
            )
            
            await update.callback_query.edit_message_text(
                f"✅ Запись подтверждена!\n\n"
                f"👤 {booking['name']}\n"
                f"📅 {booking['date']} в {booking['time']}\n"
                f"💅 {booking['service']}\n\n"
                f"✅ Клиент уведомлен",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
        else:
            await update.callback_query.edit_message_text(
                "❌ Ошибка при подтверждении записи",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
    
    async def _reject_booking(self, update: Update, booking_id: str, booking: dict):
        """Отклоняет запись"""
        success = self.storage.update_booking_status(booking_id, 'отклонено мастером')
        
        if success:
            await self.notifications.notify_client_booking_update(
                booking_id, 'отклонено мастером', 
                booking['telegram_id'], booking['name']
            )
            
            await update.callback_query.edit_message_text(
                f"❌ Запись отклонена!\n\n"
                f"👤 {booking['name']}\n"
                f"📅 {booking['date']} в {booking['time']}\n"
                f"💅 {booking['service']}\n\n"
                f"✅ Клиент уведомлен",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
        else:
            await update.callback_query.edit_message_text(
                "❌ Ошибка при отклонении записи",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
    
    async def _complete_booking(self, update: Update, booking_id: str, booking: dict):
        """Отмечает запись как выполненную"""
        success = self.storage.update_booking_status(booking_id, 'выполнено')
        
        if success:
            await self.notifications.notify_client_booking_update(
                booking_id, 'выполнено', 
                booking['telegram_id'], booking['name']
            )
            
            await update.callback_query.edit_message_text(
                f"✨ Запись отмечена как выполненная!\n\n"
                f"👤 {booking['name']}\n"
                f"📅 {booking['date']} в {booking['time']}\n"
                f"💅 {booking['service']}\n\n"
                f"✅ Клиент уведомлен",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
        else:
            await update.callback_query.edit_message_text(
                "❌ Ошибка при обновлении записи",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
    
    async def _cancel_booking(self, update: Update, booking_id: str, booking: dict):
        """Отменяет запись (мастер)"""
        success = self.storage.update_booking_status(booking_id, 'отменено')
        
        if success:
            await self.notifications.notify_client_booking_update(
                booking_id, 'отменено', 
                booking['telegram_id'], booking['name']
            )
            
            await update.callback_query.edit_message_text(
                f"⏸️ Запись отменена мастером!\n\n"
                f"👤 {booking['name']}\n"
                f"📅 {booking['date']} в {booking['time']}\n"
                f"💅 {booking['service']}\n\n"
                f"✅ Клиент уведомлен",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
        else:
            await update.callback_query.edit_message_text(
                "❌ Ошибка при отмене записи",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
    
    async def _confirm_reschedule(self, update: Update, reschedule_id: str):
        """Подтверждает перенос записи мастером (когда клиент запросил перенос)"""
        reschedule_info = self.storage.get_reschedule_info(reschedule_id)
        
        if not reschedule_info:
            await update.callback_query.edit_message_text("❌ Информация о переносе не найдена")
            return
        
        original_booking_id = reschedule_info.get('original_booking_id')
        new_booking_id = reschedule_info.get('new_booking_id')
        
        success = self.storage.confirm_reschedule(original_booking_id, new_booking_id)
        
        if success:
            new_booking = self.storage.get_booking(new_booking_id)
            client_id = new_booking.get('telegram_id')
            client_name = new_booking.get('name')
            
            await self.notifications.notify_client_reschedule_confirmed(
                original_booking_id, new_booking_id,
                client_id, client_name,
                new_booking.get('date'), new_booking.get('time')
            )
            
            message = f"""
✅ Перенос записи подтвержден!

📅 Старая запись: {reschedule_info.get('old_date')} в {reschedule_info.get('old_time')}
🔄 Новая запись: {reschedule_info.get('new_date')} в {reschedule_info.get('new_time')}
👤 Клиент: {reschedule_info.get('client_name')}
💅 Услуга: {reschedule_info.get('service')}

✅ Клиент уведомлен о новом времени.
"""
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
        else:
            await update.callback_query.edit_message_text(
                "❌ Ошибка при подтверждении переноса",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
    
    async def _reject_reschedule(self, update: Update, reschedule_id: str):
        """Отклоняет перенос записи мастером (когда клиент запросил перенос)"""
        reschedule_info = self.storage.get_reschedule_info(reschedule_id)
        
        if not reschedule_info:
            await update.callback_query.edit_message_text("❌ Информация о переносе не найдена")
            return
        
        original_booking_id = reschedule_info.get('original_booking_id')
        new_booking_id = reschedule_info.get('new_booking_id')
        
        success = self.storage.reject_reschedule(original_booking_id, new_booking_id)
        
        if success:
            new_booking = self.storage.get_booking(new_booking_id)
            client_id = new_booking.get('telegram_id')
            client_name = new_booking.get('name')
            
            await self.notifications.notify_client_reschedule_rejected(
                original_booking_id,
                client_id, client_name,
                reschedule_info.get('old_date'), reschedule_info.get('old_time')
            )
            
            message = f"""
❌ Перенос записи отклонен!

Запись остается на прежнее время:
📅 Дата: {reschedule_info.get('old_date')}
⏰ Время: {reschedule_info.get('old_time')}
👤 Клиент: {reschedule_info.get('client_name')}
💅 Услуга: {reschedule_info.get('service')}

✅ Клиент уведомлен об отклонении переноса.
"""
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
        else:
            await update.callback_query.edit_message_text(
                "❌ Ошибка при отклонении переноса",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
    
    async def _client_accept_reschedule(self, update: Update, booking_id: str):
        """Клиент принимает предложенный мастером перенос"""
        query = update.callback_query
        
        booking = self.storage.get_booking(booking_id)
        
        if not booking:
            await query.edit_message_text("❌ Запись не найдена")
            return
        
        # Проверяем, что это предложение от мастера
        if not booking.get('master_proposed', False):
            await query.edit_message_text("❌ Это не предложение от мастера")
            return
        
        success = self.storage.update_booking_status(booking_id, 'подтверждено')
        
        if success:
            # Получаем client_id из booking
            client_id = booking.get('telegram_id')
            client_name = booking.get('name')
            
            if client_id:
                await self.notifications.notify_master_client_decision(
                    booking_id, 'accept', 
                    client_name, booking.get('date'), booking.get('time')
                )
            
            original_booking_id = booking.get('original_booking_id')
            if original_booking_id:
                self.storage.update_booking_status(original_booking_id, 'перенесена')
            
            message = f"""
✅ Вы приняли новое время записи!

📅 Дата: {booking.get('date')}
⏰ Время: {booking.get('time')}
💅 Услуга: {booking.get('service')}

✅ Мастер уведомлен о вашем согласии.
Ждем вас в салоне! 💅
"""
            
            await query.edit_message_text(message)
        else:
            await query.edit_message_text(
                "❌ Ошибка при подтверждении записи"
            )
    
    async def _client_reject_reschedule(self, update: Update, booking_id: str):
        """Клиент отклоняет предложенный мастером перенос"""
        query = update.callback_query
        
        booking = self.storage.get_booking(booking_id)
        
        if not booking:
            await query.edit_message_text("❌ Запись не найдена")
            return
        
        # Проверяем, что это предложение от мастера
        if not booking.get('master_proposed', False):
            await query.edit_message_text("❌ Это не предложение от мастера")
            return
        
        success = self.storage.update_booking_status(booking_id, 'отклонено мастером')
        
        if success:
            # Получаем client_id из booking
            client_id = booking.get('telegram_id')
            client_name = booking.get('name')
            
            if client_id:
                await self.notifications.notify_master_client_decision(
                    booking_id, 'reject', 
                    client_name, booking.get('date'), booking.get('time')
                )
            
            original_booking_id = booking.get('original_booking_id')
            if original_booking_id:
                # Возвращаем оригинальную запись в предыдущий статус
                old_status = booking.get('old_status', 'ожидает')
                self.storage.update_booking_status(original_booking_id, old_status)
            
            message = f"""
❌ Вы отклонили предложенное время записи.

Предложенный слот:
📅 Дата: {booking.get('date')}
⏰ Время: {booking.get('time')}
💅 Услуга: {booking.get('service')}

✅ Мастер уведомлен о вашем решении.
Ваша оригинальная запись остается на прежнее время.
"""
            
            await query.edit_message_text(message)
        else:
            await query.edit_message_text(
                "❌ Ошибка при отмене записи"
            )
    
    async def _show_main_menu(self, update: Update):
        """Показывает главное меню мастера"""
        keyboard = [
            [
                InlineKeyboardButton("📋 Активные", callback_data="view_active"),
                InlineKeyboardButton("⏳ Ожидают", callback_data="view_pending")
            ],
            [
                InlineKeyboardButton("🔄 Переносы", callback_data="view_rescheduling"),
                InlineKeyboardButton("✅ Выполненные", callback_data="view_completed")
            ],
            [
                InlineKeyboardButton("📊 Статистика", callback_data="view_stats"),
                InlineKeyboardButton("🔄 Обновить", callback_data="menu_master")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        stats = self.storage.get_statistics()
        pending_count = stats.get('ожидает', 0)
        rescheduling_count = self.storage.get_reschedule_requests_count()
        
        menu_text = f"""
🎛️ Панель управления мастера

📊 Быстрая статистика:
⏳ Ожидают: {pending_count}
🔄 Переносы: {rescheduling_count}

Выберите раздел:
"""
        
        await update.callback_query.edit_message_text(
            menu_text,
            reply_markup=reply_markup
        )
    
    async def _show_view(self, update: Update, context: ContextTypes.DEFAULT_TYPE, view_type: str):
        """Показывает записи по категории"""
        if view_type == 'rescheduling':
            await self._show_reschedule_requests(update)
            return
        elif view_type == 'stats':
            await self._show_statistics(update)
            return
        
        status_map = {
            'active': 'подтверждено',
            'pending': 'ожидает',
            'completed': 'выполнено'
        }
        
        status = status_map.get(view_type)
        bookings = self.storage.get_bookings_by_status(status)
        
        if not bookings:
            message = self._get_empty_message(view_type)
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu_master")]]
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        message, keyboard = self._format_bookings_list(bookings, view_type)
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    async def _show_reschedule_requests(self, update: Update):
        """Показывает запросы на перенос"""
        reschedule_requests = self.storage.get_reschedule_requests()
        
        if not reschedule_requests:
            message = "📭 Нет запросы на перенос записей"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu_master")]]
            
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        message = "<b>🔄 Запросы на перенос записей:</b>\n\n"
        keyboard = []
        
        for i, request in enumerate(reschedule_requests, 1):
            message += self._format_reschedule_request(request, i)
            
            keyboard.append([
                InlineKeyboardButton(f"✅ Подтвердить #{i}", 
                                   callback_data=f"reschedule_confirm_{request['reschedule_id']}"),
                InlineKeyboardButton(f"❌ Отклонить #{i}", 
                                   callback_data=f"reschedule_reject_{request['reschedule_id']}")
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_master")])
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    async def _show_statistics(self, update: Update):
        """Показывает статистику"""
        stats = self.storage.get_statistics()
        
        message = (
            f"📊 <b>Статистика записей:</b>\n\n"
            f"📈 Всего записей: <b>{stats['total']}</b>\n"
            f"⏳ Ожидают подтверждения: <b>{stats['ожидает']}</b>\n"
            f"✅ Подтвержденные: <b>{stats['подтверждено']}</b>\n"
            f"✨ Выполненные: <b>{stats['выполнено']}</b>\n"
            f"🔄 Переносы (ожидание мастера): <b>{stats.get('перенос (ожидание мастера)', 0)}</b>\n"
            f"🔄 Переносы (ожидание клиента): <b>{stats.get('перенос (ожидание клиента)', 0)}</b>\n"
            f"🔄 Перенесенные: <b>{stats.get('перенесена', 0)}</b>\n"
            f"❌ Отклоненные: <b>{stats['отклонено мастером']}</b>\n"
            f"⏸️ Отмененные: <b>{stats['отменено']}</b>\n\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y')}"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Обновить", callback_data="view_stats"),
                InlineKeyboardButton("🔙 Назад", callback_data="menu_master")
            ]
        ]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    async def send_master_menu(self, bot, chat_id: str):
        """Отправляет меню мастера в чат"""
        keyboard = [
            [
                InlineKeyboardButton("📋 Активные", callback_data="view_active"),
                InlineKeyboardButton("⏳ Ожидают", callback_data="view_pending")
            ],
            [
                InlineKeyboardButton("🔄 Переносы", callback_data="view_rescheduling"),
                InlineKeyboardButton("✅ Выполненные", callback_data="view_completed")
            ],
            [
                InlineKeyboardButton("📊 Статистика", callback_data="view_stats"),
                InlineKeyboardButton("🔄 Обновить", callback_data="menu_master")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await bot.send_message(
            chat_id=chat_id,
            text="🎛️ Панель управления мастера\nВыберите раздел:",
            reply_markup=reply_markup
        )
    
    def _get_empty_message(self, view_type: str) -> str:
        messages = {
            'active': "📭 Нет активных записей",
            'pending': "📭 Нет записей, ожидающих подтверждения",
            'completed': "📭 Нет выполненных записей"
        }
        return messages.get(view_type, "📭 Нет записей")
    
    def _format_bookings_list(self, bookings: list, view_type: str):
        """Форматирует список записей с кнопками"""
        message = f"<b>{self._get_view_title(view_type)}</b>\n\n"
        keyboard = []
        
        for i, booking in enumerate(bookings, 1):
            message += self._format_booking_info(booking, i)
            
            if view_type == 'pending':
                keyboard.append([
                    InlineKeyboardButton(f"✅ Подтвердить #{i}", 
                                       callback_data=f"action_confirm_{booking['booking_id']}"),
                    InlineKeyboardButton(f"❌ Отклонить #{i}", 
                                       callback_data=f"action_reject_{booking['booking_id']}")
                ])
            elif view_type == 'active':
                keyboard.append([
                    InlineKeyboardButton(f"✨ Выполнено #{i}", 
                                       callback_data=f"action_complete_{booking['booking_id']}"),
                    InlineKeyboardButton(f"🔄 Перенести #{i}", 
                                       callback_data=f"action_reschedule_{booking['booking_id']}")
                ])
            elif view_type == 'completed':
                keyboard.append([
                    InlineKeyboardButton(f"📋 Детали #{i}", 
                                       callback_data=f"action_view_{booking['booking_id']}")
                ])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_master")])
        
        return message, keyboard
    
    def _format_reschedule_request(self, request: dict, index: int) -> str:
        """Форматирует информацию о запросе на перенос"""
        return (f"<b>{index}. Запрос на перенос</b>\n"
                f"👤 Клиент: {request.get('client_name', '')}\n"
                f"📞 Телефон: {request.get('client_phone', '')}\n"
                f"📅 Старая дата: {request.get('old_date', '')} в {request.get('old_time', '')}\n"
                f"🔄 Новая дата: {request.get('new_date', '')} в {request.get('new_time', '')}\n"
                f"💅 Услуга: {request.get('service', '')}\n"
                f"⏱️ Запрошено: {request.get('requested_at', '')}\n\n")
    
    def _format_booking_info(self, booking: dict, index: int) -> str:
        """Форматирует информацию о записи для отображения"""
        try:
            created = datetime.fromisoformat(booking['created_at']).strftime('%d.%m.%Y %H:%M')
        except:
            created = "неизвестно"
        
        return (f"<b>{index}. {booking.get('name', 'Без имени')}</b>\n"
                f"📅 {booking.get('date', '??.??.????')} в {booking.get('time', '??:??')}\n"
                f"📞 {booking.get('phone', 'без телефона')}\n"
                f"💅 {booking.get('service', 'без услуги')}\n"
                f"🆔 {booking.get('booking_id', '')[:8]}...\n"
                f"⏱️ Создана: {created}\n\n")
    
    def _get_view_title(self, view_type: str) -> str:
        """Возвращает заголовок для раздела"""
        titles = {
            'active': '📋 Активные записи (подтвержденные)',
            'pending': '⏳ Записи, ожидающие подтверждения',
            'completed': '✅ Выполненные записи'
        }
        return titles.get(view_type, 'Записи')