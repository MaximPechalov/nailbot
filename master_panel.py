"""
Модуль для панели управления мастером
Упрощенная логика с новой системой переносов
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
        self.availability_manager = None
        
        # Состояния для переноса мастером
        self.MASTER_RESCHEDULE_DATE = 100
        self.MASTER_RESCHEDULE_TIME = 101
        self.MASTER_RESCHEDULE_CONFIRM = 102
    
    def set_availability_manager(self, availability_manager):
        """Устанавливает менеджер доступности"""
        self.availability_manager = availability_manager
    
    def _get_date_keyboard_master(self, start_day=1, days=5):
        """Создает клавиатуру с датами для мастера"""
        keyboard = []
        row = []
        
        today = datetime.now()
        
        for i in range(start_day, start_day + days):
            date = today + timedelta(days=i)
            date_str = date.strftime('%d.%m.%Y')
            
            day_name = self._get_day_name(date.weekday())
            date_display = f"{date_str} ({day_name})"
            
            row.append(date_display)
            
            if len(row) == 2:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append(['📅 Ввести другую дату'])
        
        return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    def _get_day_name(self, weekday):
        """Возвращает русское название дня недели"""
        days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        return days[weekday]
    
    def _is_valid_date(self, date_str):
        """Проверяет, корректна ли дата"""
        try:
            date_obj = datetime.strptime(date_str, '%d.%m.%Y')
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            if date_obj < today:
                return False
            
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
        
        # Обработка callback от клиента (для предложений переноса)
        if data.startswith('reschedule_client_'):
            parts = data.split('_')
            if len(parts) >= 4:
                action = parts[2]
                booking_id = parts[3]
                
                print(f"📞 Callback от клиента {user_id}, action: {action}, booking_id: {booking_id}")
                
                if action == 'accept':
                    await self._handle_client_accept_reschedule(update, booking_id)
                elif action == 'reject':
                    await self._handle_client_reject_reschedule(update, booking_id)
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
        
        elif data.startswith('reschedule_master_'):
            parts = data.split('_')
            if len(parts) >= 4:
                action = parts[2]
                booking_id = parts[3]
                
                if action == 'offer':
                    await self._start_master_reschedule_offer(update, context, booking_id)
                elif action == 'view':
                    await self._show_reschedule_requests(update, booking_id)
        
        elif data.startswith('view_'):
            view_type = data.split('_')[1]
            await self._show_view(update, context, view_type)
        
        elif data == 'menu_master':
            await self._show_main_menu(update)
        
        # Добавляем обработку availability callback
        elif data.startswith('availability_'):
            await self.handle_availability_callback(update, context)
        elif data.startswith('work_hours_'):
            await self.handle_availability_callback(update, context)
        elif data.startswith('save_hours_'):
            # Исправляем обработку callback данных
            parts = data.split('_')
            if len(parts) >= 5:
                # Проверяем, не нажата ли кнопка "Сохранить и выйти"
                if parts[2] == 'exit':
                    # Формат: save_hours_exit_{day}_{start}_{end}_{enabled}
                    if len(parts) >= 7:
                        day = parts[3]
                        start = parts[4]
                        end = parts[5]
                        enabled = parts[6] == 'true' if len(parts) > 6 else True
                        await self.save_work_hours_and_exit(update, context, day, start, end, enabled)
                else:
                    # Формат: save_hours_{day}_{start}_{end}_{enabled}
                    day = parts[2]
                    start = parts[3]
                    end = parts[4]
                    enabled = parts[5] == 'true' if len(parts) > 5 else True
                    await self.save_work_hours_and_stay(update, context, day, start, end, enabled)
        elif data.startswith('set_day_off_'):
            parts = data.split('_')
            if len(parts) >= 4:
                date_str = '_'.join(parts[3:])  # На случай даты с разделителями
                if self.availability_manager:
                    success = self.availability_manager.set_day_off(date_str)
                    if success:
                        await query.edit_message_text(
                            f"✅ {date_str} установлен как выходной день",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("🔙 Назад", callback_data="availability_menu")
                            ]])
                        )
        elif data.startswith('remove_day_off_'):
            parts = data.split('_')
            if len(parts) >= 4:
                date_str = '_'.join(parts[3:])
                if self.availability_manager:
                    success = self.availability_manager.remove_day_off(date_str)
                    if success:
                        await query.edit_message_text(
                            f"✅ {date_str} удален из выходных дней",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("🔙 Назад", callback_data="availability_menu")
                            ]])
                        )
    
    async def _handle_booking_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   action: str, booking_id: str):
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
            await self._start_master_reschedule_offer(update, context, booking_id)
        elif action == 'accept':
            # Принятие переноса от клиента
            await self._accept_reschedule_request(update, booking_id)
        elif action == 'reject':
            # Отклонение переноса от клиента
            await self._reject_reschedule_request(update, booking_id)
    
    async def _start_master_reschedule_offer(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                           booking_id: str):
        """Начинает процесс предложения переноса мастером"""
        booking = self.storage.get_booking(booking_id)
        
        if not booking:
            await update.callback_query.edit_message_text("❌ Запись не найдена")
            return
        
        # Проверяем, можно ли перенести эту запись
        current_status = booking.get('status')
        if current_status not in ['ожидает', 'подтверждено', 'запрос переноса']:
            await update.callback_query.edit_message_text(
                f"❌ Запись со статусом '{current_status}' нельзя перенести."
            )
            return
        
        context.user_data['master_reschedule'] = {
            'booking_id': booking_id,
            'booking_data': booking
        }
        
        context.user_data['_conversation_state'] = self.MASTER_RESCHEDULE_DATE
        
        await update.callback_query.delete_message()
        
        message = f"""
🔄 ПРЕДЛОЖЕНИЕ ПЕРЕНОСА

Вы хотите предложить новое время для записи:

👤 Клиент: {booking.get('name', '')}
📅 Текущая дата: {booking.get('date', '')}
⏰ Текущее время: {booking.get('time', '')}
💅 Услуга: {booking.get('service', '')}

Выберите новую дату:
"""
        
        await context.bot.send_message(
            chat_id=MASTER_CHAT_ID,
            text=message,
            reply_markup=self._get_date_keyboard_master()
        )
        
        return self.MASTER_RESCHEDULE_DATE
    
    async def handle_master_reschedule_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор даты мастером"""
        context.user_data['_conversation_state'] = self.MASTER_RESCHEDULE_DATE
        
        user_input = update.message.text
        
        if user_input == '📅 Ввести другую дату':
            await update.message.reply_text(
                "📝 Введите новую дату в формате ДД.ММ.ГГГГ\n"
                "Например: 25.12.2024",
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
                    "❌ Некорректная дата! Выберите дату из списка:",
                    reply_markup=self._get_date_keyboard_master()
                )
                return self.MASTER_RESCHEDULE_DATE
                
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты! Введите ДД.ММ.ГГГГ:",
                reply_markup=self._get_date_keyboard_master()
            )
            return self.MASTER_RESCHEDULE_DATE
        
        context.user_data['master_reschedule']['new_date'] = date_str
        context.user_data['_conversation_state'] = self.MASTER_RESCHEDULE_TIME
        
        keyboard = [
            ['10:00', '11:00', '12:00'],
            ['13:00', '14:00', '15:00'],
            ['16:00', '17:00', '18:00'],
            ['19:00', '20:00', '21:00']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "⏰ Выберите новое время:",
            reply_markup=reply_markup
        )
        
        return self.MASTER_RESCHEDULE_TIME
    
    async def handle_master_reschedule_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор времени мастером"""
        context.user_data['_conversation_state'] = self.MASTER_RESCHEDULE_TIME
        
        context.user_data['master_reschedule']['new_time'] = update.message.text
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
📋 ПОДТВЕРЖДЕНИЕ ПРЕДЛОЖЕНИЯ

📅 Текущая запись:
👤 {booking.get('name', '')}
📞 {booking.get('phone', '')}
📅 {booking.get('date', '')} в {booking.get('time', '')}
💅 {booking.get('service', '')}

🔄 Предлагаемое время:
📅 {new_date_display}
⏰ {new_time}

Клиент получит это предложение и сможет его принять или отклонить.

Отправить предложение клиенту?
"""
        
        keyboard = [['✅ Да, отправить', '❌ Нет, отменить']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        
        return self.MASTER_RESCHEDULE_CONFIRM
    
    async def handle_master_reschedule_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение предложения переноса"""
        context.user_data['_conversation_state'] = self.MASTER_RESCHEDULE_CONFIRM
        
        if 'Да' in update.message.text:
            reschedule_data = context.user_data['master_reschedule']
            booking_id = reschedule_data['booking_id']
            booking = reschedule_data['booking_data']
            new_date = reschedule_data.get('new_date', '')
            new_time = reschedule_data.get('new_time', '')
            
            # Используем централизованный менеджер
            success, new_booking_id, error_message = self.storage.offer_reschedule(
                booking_id, new_date, new_time
            )
            
            if success:
                # Отправляем предложение клиенту
                await self.notifications.notify_client_reschedule_offer(
                    new_booking_id, new_date, new_time,
                    booking.get('telegram_id'), booking.get('name')
                )
                
                message = f"""
✅ Предложение переноса отправлено клиенту!

👤 Клиент: {booking.get('name', '')}
📅 Новое время: {new_date} в {new_time}
💅 Услуга: {booking.get('service', '')}

⏳ Ожидайте решения клиента.
"""
            else:
                message = f"❌ Не удалось создать предложение. {error_message}"
        else:
            message = "❌ Предложение переноса отменено."
        
        # Очищаем данные
        for key in ['master_reschedule', '_conversation_state']:
            if key in context.user_data:
                del context.user_data[key]
        
        # Возвращаем меню мастера
        keyboard = [
            [
                InlineKeyboardButton("📋 Активные", callback_data="view_active"),
                InlineKeyboardButton("⏳ Ожидают", callback_data="view_pending")
            ],
            [
                InlineKeyboardButton("🔄 Запросы переноса", callback_data="view_reschedule_requests"),
                InlineKeyboardButton("📨 Предложения", callback_data="view_reschedule_offers")
            ],
            [
                InlineKeyboardButton("🕒 Управление расписанием", callback_data="availability_menu"),
            ],
            [
                InlineKeyboardButton("✅ Выполненные", callback_data="view_completed"),
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
        """Отмена предложения переноса"""
        for key in ['master_reschedule', '_conversation_state']:
            if key in context.user_data:
                del context.user_data[key]
        
        await update.message.reply_text(
            "❌ Предложение переноса отменено.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        await self._show_main_menu_from_message(update, context)
        return ConversationHandler.END
    
    async def _accept_reschedule_request(self, update: Update, booking_id: str):
        """Мастер принимает запрос на перенос от клиента"""
        query = update.callback_query
        
        # Используем централизованный менеджер
        success, message = self.storage.accept_reschedule(booking_id, 'master')
        
        if success:
            # Получаем информацию о переносе
            reschedule_info = self.storage.get_reschedule_info(booking_id)
            if reschedule_info:
                client_id = reschedule_info.get('client_id')
                client_name = reschedule_info.get('client_name')
                
                if client_id:
                    # Уведомляем клиента
                    await self.notifications.notify_client_booking_update(
                        booking_id, 'подтверждено',
                        client_id, client_name
                    )
            
            await query.edit_message_text(f"✅ {message}")
        else:
            await query.edit_message_text(f"❌ {message}")
    
    async def _reject_reschedule_request(self, update: Update, booking_id: str):
        """Мастер отклоняет запрос на перенос от клиента"""
        query = update.callback_query
        
        # Используем централизованный менеджер
        success, message = self.storage.reject_reschedule(
            booking_id, 'master', "Мастер отклонил запрос"
        )
        
        if success:
            # Получаем информацию о переносе
            reschedule_info = self.storage.get_reschedule_info(booking_id)
            if reschedule_info:
                client_id = reschedule_info.get('client_id')
                client_name = reschedule_info.get('client_name')
                
                if client_id:
                    # Уведомляем клиента
                    await self.notifications.notify_client_booking_update(
                        booking_id, 'отклонено',
                        client_id, client_name
                    )
            
            await query.edit_message_text(f"✅ {message}")
        else:
            await query.edit_message_text(f"❌ {message}")
    
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
        success = self.storage.update_booking_status(booking_id, 'отклонено')
        
        if success:
            await self.notifications.notify_client_booking_update(
                booking_id, 'отклонено', 
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
                f"✨ Запись выполнена!\n\n"
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
                f"⏸️ Запись отменена!\n\n"
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
    
    async def _handle_client_accept_reschedule(self, update: Update, booking_id: str):
        """Обрабатывает принятие клиентом предложения переноса"""
        query = update.callback_query
        
        # Используем централизованный менеджер
        success, message = self.storage.accept_reschedule(booking_id, 'client')
        
        if success:
            booking = self.storage.get_booking(booking_id)
            if booking:
                await self.notifications.notify_master_client_decision(
                    booking_id, 'accept', 
                    booking.get('name'), 
                    booking.get('date'), booking.get('time')
                )
            
            await query.edit_message_text(f"✅ {message}")
        else:
            await query.edit_message_text(f"❌ {message}")
    
    async def _handle_client_reject_reschedule(self, update: Update, booking_id: str):
        """Обрабатывает отклонение клиентом предложения переноса"""
        query = update.callback_query
        
        # Используем централизованный менеджер
        success, message = self.storage.reject_reschedule(
            booking_id, 'client', "Клиент отказался от предложения"
        )
        
        if success:
            booking = self.storage.get_booking(booking_id)
            if booking:
                await self.notifications.notify_master_client_decision(
                    booking_id, 'reject', 
                    booking.get('name'), 
                    booking.get('date'), booking.get('time')
                )
            
            await query.edit_message_text(f"✅ {message}")
        else:
            await query.edit_message_text(f"❌ {message}")
    
    async def _show_reschedule_requests(self, update: Update, booking_id: str = None):
        """Показывает запросы на перенос"""
        if booking_id:
            # Показываем конкретный запрос
            reschedule_info = self.storage.get_reschedule_info(booking_id)
            
            if not reschedule_info:
                await update.callback_query.edit_message_text("❌ Информация о переносе не найдена")
                return
            
            message = self._format_reschedule_request(reschedule_info)
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Принять перенос", 
                                       callback_data=f"action_accept_{booking_id}"),
                    InlineKeyboardButton("❌ Отклонить перенос", 
                                       callback_data=f"action_reject_{booking_id}")
                ],
                [InlineKeyboardButton("🔙 Назад", callback_data="view_reschedule_requests")]
            ]
            
        else:
            # Показываем все запросы
            reschedule_requests = self.storage.get_reschedule_requests()
            
            if not reschedule_requests:
                message = "📭 Нет запросы на перенос от клиентов"
                keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data="menu_master")]]
            else:
                message = "<b>🔄 Запросы на перенос от клиентов:</b>\n\n"
                keyboard = []
                
                for i, request in enumerate(reschedule_requests, 1):
                    message += self._format_reschedule_request_short(request, i)
                    
                    keyboard.append([
                        InlineKeyboardButton(f"✅ Принять #{i}", 
                                           callback_data=f"action_accept_{request['new_booking_id']}"),
                        InlineKeyboardButton(f"❌ Отклонить #{i}", 
                                           callback_data=f"action_reject_{request['new_booking_id']}")
                    ])
                
                keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="menu_master")])
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    async def _show_view(self, update: Update, context: ContextTypes.DEFAULT_TYPE, view_type: str):
        """Показывает записи по категории"""
        if view_type == 'reschedule_requests':
            await self._show_reschedule_requests(update)
            return
        elif view_type == 'reschedule_offers':
            await self._show_reschedule_offers(update)
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
    
    async def _show_reschedule_offers(self, update: Update):
        """Показывает предложения переноса от мастера"""
        reschedule_offers = self.storage.get_reschedule_offers()
        
        if not reschedule_offers:
            message = "📭 Нет активных предложений переноса"
            keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data="menu_master")]]
        else:
            message = "<b>📨 Ваши предложения переноса:</b>\n\n"
            keyboard = []
            
            for i, offer in enumerate(reschedule_offers, 1):
                message += self._format_reschedule_offer_short(offer, i)
                
                keyboard.append([
                    InlineKeyboardButton(f"📋 Детали #{i}", 
                                       callback_data=f"view_offer_{offer['new_booking_id']}")
                ])
            
            keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="menu_master")])
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    async def _show_statistics(self, update: Update):
        """Показывает статистику"""
        stats = self.storage.get_statistics()
        reschedule_requests = len(self.storage.get_reschedule_requests())
        reschedule_offers = len(self.storage.get_reschedule_offers())
        
        message = (
            f"📊 <b>Статистика записей:</b>\n\n"
            f"📈 Всего записей: <b>{stats['total']}</b>\n"
            f"⏳ Ожидают: <b>{stats['ожидает']}</b>\n"
            f"✅ Подтверждены: <b>{stats['подтверждено']}</b>\n"
            f"✨ Выполнены: <b>{stats['выполнено']}</b>\n"
            f"🔄 Запросы переноса: <b>{reschedule_requests}</b>\n"
            f"📨 Предложения переноса: <b>{reschedule_offers}</b>\n"
            f"❌ Отклонены: <b>{stats['отклонено']}</b>\n"
            f"⏸️ Отменены: <b>{stats['отменено']}</b>\n\n"
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
                InlineKeyboardButton("🔄 Запросы переноса", callback_data="view_reschedule_requests"),
                InlineKeyboardButton("📨 Предложения", callback_data="view_reschedule_offers")
            ],
            [
                InlineKeyboardButton("🕒 Управление расписанием", callback_data="availability_menu"),
            ],
            [
                InlineKeyboardButton("✅ Выполненные", callback_data="view_completed"),
                InlineKeyboardButton("📊 Статистика", callback_data="view_stats")
            ],
            [
                InlineKeyboardButton("🔄 Обновить", callback_data="menu_master")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await bot.send_message(
            chat_id=chat_id,
            text="🎛️ Панель управления мастера\nВыберите раздел:",
            reply_markup=reply_markup
        )
    
    async def _show_main_menu(self, update: Update):
        """Показывает главное меню мастера"""
        keyboard = [
            [
                InlineKeyboardButton("📋 Активные", callback_data="view_active"),
                InlineKeyboardButton("⏳ Ожидают", callback_data="view_pending")
            ],
            [
                InlineKeyboardButton("🔄 Запросы переноса", callback_data="view_reschedule_requests"),
                InlineKeyboardButton("📨 Предложения", callback_data="view_reschedule_offers")
            ],
            [
                InlineKeyboardButton("🕒 Управление расписанием", callback_data="availability_menu"),
            ],
            [
                InlineKeyboardButton("✅ Выполненные", callback_data="view_completed"),
                InlineKeyboardButton("📊 Статистика", callback_data="view_stats")
            ],
            [
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
    
    async def _show_main_menu_from_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает главное меню из обычного сообщения"""
        await self.send_master_menu(context.bot, MASTER_CHAT_ID)
    
    # === Методы для управления доступностью ===
    
    async def show_availability_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню управления доступностью"""
        query = update.callback_query
        await query.answer()
        
        if not self.availability_manager:
            await query.edit_message_text(
                "❌ Менеджер доступности не инициализирован",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
            return
        
        message = "🎛️ Управление расписанием\n\n"
        message += self.availability_manager.get_work_hours_display()
        
        keyboard = [
            [
                InlineKeyboardButton("📅 Настроить рабочие часы", 
                                   callback_data="availability_work_hours"),
                InlineKeyboardButton("🚫 Установить выходной", 
                                   callback_data="availability_day_off")
            ],
            [
                InlineKeyboardButton("📋 Показать свободные слоты", 
                                   callback_data="availability_view_slots"),
                InlineKeyboardButton("🗑️ Удалить выходной", 
                                   callback_data="availability_remove_day_off")
            ],
            [
                InlineKeyboardButton("🔙 В меню", callback_data="menu_master"),
                InlineKeyboardButton("🔄 Обновить", callback_data="availability_menu")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                print("ℹ️ Сообщение не изменилось, пропускаем edit")
            else:
                print(f"⚠️ Ошибка редактирования, отправляем новое: {e}")
                await query.message.reply_text(
                    message,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
    
    async def handle_availability_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает callback для управления доступностью"""
        query = update.callback_query
        await query.answer()
        
        if not self.availability_manager:
            await query.edit_message_text(
                "❌ Менеджер доступности не инициализирован",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
            return
        
        data = query.data
        
        if data == "availability_menu":
            await self.show_availability_menu(update, context)
        elif data == "availability_work_hours":
            await self.show_work_hours_setup(update, context)
        elif data == "availability_day_off":
            await self.set_day_off(update, context)
        elif data == "availability_remove_day_off":
            await self.remove_day_off(update, context)
        elif data == "availability_view_slots":
            await self.view_available_slots(update, context)
        elif data.startswith("work_hours_"):
            parts = data.split("_")
            if len(parts) >= 3:
                day = parts[2]
                await self.edit_work_hours_day(update, context, day)
    
    async def show_work_hours_setup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает настройки рабочих часов по дням недели"""
        query = update.callback_query
        
        if not self.availability_manager:
            await query.edit_message_text(
                "❌ Менеджер доступности не инициализирован",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
            return
        
        days_ru = {
            'monday': 'Понедельник',
            'tuesday': 'Вторник',
            'wednesday': 'Среда',
            'thursday': 'Четверг',
            'friday': 'Пятница',
            'saturday': 'Суббота',
            'sunday': 'Воскресенье'
        }
        
        message = "🕒 Настройка рабочих часов\n\n"
        message += "Выберите день для настройки:\n"
        
        keyboard = []
        for eng_day, ru_day in days_ru.items():
            settings = self.availability_manager.work_hours.get(eng_day, {})
            enabled = settings.get('enabled', False)  # Исправлено: по умолчанию False
            start = settings.get('start', '--:--')
            end = settings.get('end', '--:--')
            
            status = "✅" if enabled else "❌"
            display_text = f"{status} {ru_day}"
            
            keyboard.append([
                InlineKeyboardButton(display_text, 
                                   callback_data=f"work_hours_{eng_day}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔙 Назад", callback_data="availability_menu"),
            InlineKeyboardButton("📋 Показать расписание", callback_data="availability_menu")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                message,
                reply_markup=reply_markup
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                print("ℹ️ Сообщение не изменилось, пропускаем edit")
            else:
                print(f"⚠️ Ошибка редактирования, отправляем новое: {e}")
                await query.message.reply_text(
                    message,
                    reply_markup=reply_markup
                )
    
    async def edit_work_hours_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE, day: str):
        """Редактирование рабочих часов для конкретного дня - ИСПРАВЛЕННЫЙ МЕТОД"""
        query = update.callback_query
        
        if not self.availability_manager:
            await query.edit_message_text(
                "❌ Менеджер доступности не инициализирован",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
            return
        
        days_ru = {
            'monday': 'Понедельник',
            'tuesday': 'Вторник',
            'wednesday': 'Среда',
            'thursday': 'Четверг',
            'friday': 'Пятница',
            'saturday': 'Суббота',
            'sunday': 'Воскресенье'
        }
        
        # ВАЖНОЕ ИСПРАВЛЕНИЕ: правильно определяем текущее состояние
        settings = self.availability_manager.work_hours.get(day, {})
        current_start = settings.get('start', '10:00')
        current_end = settings.get('end', '20:00')
        current_enabled = settings.get('enabled', False)  # Исправлено: по умолчанию False
        
        message = f"🕒 Настройка {days_ru[day]}\n\n"
        message += f"Текущие настройки:\n"
        message += f"Статус: {'✅ Работаю' if current_enabled else '❌ Выходной'}\n"
        if current_enabled:
            message += f"Часы: {current_start} - {current_end}\n\n"
        else:
            message += f"Часы: выходной\n\n"
        message += "Выберите параметр для изменения:"
        
        keyboard = []
        
        if current_enabled:
            # Кнопки для времени начала (сгруппированы по 3)
            start_times = ['08:00', '09:00', '10:00', '11:00', '12:00', '13:00']
            for i in range(0, len(start_times), 3):
                row = []
                for time in start_times[i:i+3]:
                    # Подсвечиваем текущее время начала
                    if time == current_start:
                        button_text = f"⏰ •{time}•"
                    else:
                        button_text = f"⏰ {time}"
                    row.append(InlineKeyboardButton(
                        button_text, 
                        callback_data=f"save_hours_{day}_{time}_{current_end}_true"  # enabled=true
                    ))
                keyboard.append(row)
            
            # Кнопки для времени окончания (сгруппированы по 3)
            end_times = ['17:00', '18:00', '19:00', '20:00', '21:00', '22:00']
            for i in range(0, len(end_times), 3):
                row = []
                for time in end_times[i:i+3]:
                    # Подсвечиваем текущее время окончания
                    if time == current_end:
                        button_text = f"🕓 •{time}•"
                    else:
                        button_text = f"🕓 {time}"
                    row.append(InlineKeyboardButton(
                        button_text, 
                        callback_data=f"save_hours_{day}_{current_start}_{time}_true"  # enabled=true
                    ))
                keyboard.append(row)
        else:
            # Если день выходной, НЕ показываем кнопки времени - только варианты включения
            message += "\nСейчас этот день выходной. Вы можете включить его с предустановленными часами:"
            
            # Варианты для включения дня
            keyboard.append([
                InlineKeyboardButton(
                    "✅ Включить с 10:00-20:00", 
                    callback_data=f"save_hours_{day}_10:00_20:00_true"
                )
            ])
            keyboard.append([
                InlineKeyboardButton(
                    "✅ Включить с 11:00-19:00", 
                    callback_data=f"save_hours_{day}_11:00_19:00_true"
                )
            ])
            keyboard.append([
                InlineKeyboardButton(
                    "✅ Включить с 09:00-18:00", 
                    callback_data=f"save_hours_{day}_09:00_18:00_true"
                )
            ])
        
        # Кнопки включения/выключения
        if current_enabled:
            keyboard.append([
                InlineKeyboardButton(
                    "❌ Сделать выходным", 
                    callback_data=f"save_hours_{day}_{current_start}_{current_end}_false"
                )
            ])
        else:
            # День уже выходной, показываем кнопку для включения со свободным выбором времени
            # (уже показана выше)
            pass
        
        keyboard.append([
            InlineKeyboardButton("💾 Сохранить и выйти", 
                               callback_data=f"save_hours_exit_{day}_{current_start}_{current_end}_{'true' if current_enabled else 'false'}"),
            InlineKeyboardButton("🔙 Назад", callback_data="availability_work_hours")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                message,
                reply_markup=reply_markup
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                print("ℹ️ Сообщение не изменилось, пропускаем edit")
            else:
                print(f"⚠️ Ошибка редактирования, отправляем новое: {e}")
                await query.message.reply_text(
                    message,
                    reply_markup=reply_markup
                )
    
    async def save_work_hours_and_stay(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                     day: str, start: str, end: str, enabled: bool):
        """Сохраняет рабочие часы для дня и остается в меню редактирования - ИСПРАВЛЕННЫЙ"""
        query = update.callback_query
        
        if not self.availability_manager:
            await query.edit_message_text(
                "❌ Менеджер доступности не инициализирован",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
            return
        
        # Сохраняем изменения
        success = self.availability_manager.update_work_hours(day, start, end, enabled)
        
        if success:
            # Получаем обновленные настройки
            settings = self.availability_manager.work_hours.get(day, {})
            current_start = settings.get('start', start)
            current_end = settings.get('end', end)
            current_enabled = settings.get('enabled', enabled)  # Исправлено: получаем из настроек
            
            # Обновляем сообщение с новыми настройками
            days_ru = {
                'monday': 'Понедельник',
                'tuesday': 'Вторник',
                'wednesday': 'Среда',
                'thursday': 'Четверг',
                'friday': 'Пятница',
                'saturday': 'Суббота',
                'sunday': 'Воскресенье'
            }
            
            message = f"✅ Настройки для {days_ru[day]} обновлены!\n\n"
            message += f"Статус: {'✅ Работаю' if current_enabled else '❌ Выходной'}\n"
            if current_enabled:
                message += f"Часы: {current_start} - {current_end}\n\n"
            else:
                message += f"Часы: выходной\n\n"
            message += "Выберите следующий параметр для изменения:"
            
            keyboard = []
            
            if current_enabled:
                # Кнопки для времени начала
                start_times = ['08:00', '09:00', '10:00', '11:00', '12:00', '13:00']
                for i in range(0, len(start_times), 3):
                    row = []
                    for time in start_times[i:i+3]:
                        # Подсвечиваем текущее время
                        if time == current_start:
                            button_text = f"⏰ •{time}•"
                        else:
                            button_text = f"⏰ {time}"
                        row.append(InlineKeyboardButton(
                            button_text, 
                            callback_data=f"save_hours_{day}_{time}_{current_end}_{'true' if current_enabled else 'false'}"
                        ))
                    keyboard.append(row)
                
                # Кнопки для времени окончания
                end_times = ['17:00', '18:00', '19:00', '20:00', '21:00', '22:00']
                for i in range(0, len(end_times), 3):
                    row = []
                    for time in end_times[i:i+3]:
                        # Подсвечиваем текущее время
                        if time == current_end:
                            button_text = f"🕓 •{time}•"
                        else:
                            button_text = f"🕓 {time}"
                        row.append(InlineKeyboardButton(
                            button_text, 
                            callback_data=f"save_hours_{day}_{current_start}_{time}_{'true' if current_enabled else 'false'}"
                        ))
                    keyboard.append(row)
                
                # Кнопка для выключения
                keyboard.append([
                    InlineKeyboardButton(
                        "❌ Сделать выходным", 
                        callback_data=f"save_hours_{day}_{current_start}_{current_end}_false"
                    )
                ])
            else:
                # Если день выходной, показываем варианты для включения
                message += "\nСейчас этот день выходной. Вы можете включить его с предустановленными часами:"
                
                keyboard.append([
                    InlineKeyboardButton(
                        "✅ Включить с 10:00-20:00", 
                        callback_data=f"save_hours_{day}_10:00_20:00_true"
                    )
                ])
                keyboard.append([
                    InlineKeyboardButton(
                        "✅ Включить с 11:00-19:00", 
                        callback_data=f"save_hours_{day}_11:00_19:00_true"
                    )
                ])
                keyboard.append([
                    InlineKeyboardButton(
                        "✅ Включить с 09:00-18:00", 
                        callback_data=f"save_hours_{day}_09:00_18:00_true"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("💾 Сохранить и выйти", 
                                   callback_data=f"save_hours_exit_{day}_{current_start}_{current_end}_{'true' if current_enabled else 'false'}"),
                InlineKeyboardButton("🔙 Назад", callback_data="availability_work_hours")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(
                    message,
                    reply_markup=reply_markup
                )
            except Exception as e:
                if "Message is not modified" in str(e):
                    print("ℹ️ Сообщение не изменилось, пропускаем edit")
                else:
                    print(f"⚠️ Ошибка редактирования, отправляем новое: {e}")
                    await query.message.reply_text(
                        message,
                        reply_markup=reply_markup
                    )
        else:
            message = "❌ Ошибка при сохранении настроек"
            keyboard = [
                [InlineKeyboardButton("🔙 Назад", callback_data=f"work_hours_{day}")],
                [InlineKeyboardButton("📋 Показать расписание", callback_data="availability_menu")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(
                    message,
                    reply_markup=reply_markup
                )
            except Exception as e:
                if "Message is not modified" in str(e):
                    print("ℹ️ Сообщение не изменилось, пропускаем edit")
                else:
                    print(f"⚠️ Ошибка редактирования, отправляем новое: {e}")
                    await query.message.reply_text(
                        message,
                        reply_markup=reply_markup
                    )
    
    async def save_work_hours_and_exit(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                     day: str, start: str, end: str, enabled: bool):
        """Сохраняет рабочие часы для дня и возвращается в меню"""
        query = update.callback_query
        
        if not self.availability_manager:
            await query.edit_message_text(
                "❌ Менеджер доступности не инициализирован",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
            return
        
        # Сохраняем изменения
        success = self.availability_manager.update_work_hours(day, start, end, enabled)
        
        if success:
            message = f"✅ Настройки для дня обновлены!\n\n"
            message += self.availability_manager.get_work_hours_display()
        else:
            message = "❌ Ошибка при сохранении настроек"
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="availability_work_hours")],
            [InlineKeyboardButton("📋 Показать расписание", callback_data="availability_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                message,
                reply_markup=reply_markup
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                print("ℹ️ Сообщение не изменилось, пропускаем edit")
            else:
                print(f"⚠️ Ошибка редактирования, отправляем новое: {e}")
                await query.message.reply_text(
                    message,
                    reply_markup=reply_markup
                )
    
    async def set_day_off(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Устанавливает выходной на конкретную дату"""
        query = update.callback_query
        
        if not self.availability_manager:
            await query.edit_message_text(
                "❌ Менеджер доступности не инициализирован",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
            return
        
        # Генерируем клавиатуру с датами на ближайшие 30 дней
        keyboard = []
        today = datetime.now()
        row = []
        
        for i in range(1, 31):
            date = today + timedelta(days=i)
            date_str = date.strftime('%d.%m.%Y')
            
            row.append(InlineKeyboardButton(
                date_str,
                callback_data=f"set_day_off_{date_str}"
            ))
            
            if len(row) == 3:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([
            InlineKeyboardButton("🔙 Назад", callback_data="availability_menu")
        ])
        
        message = "📅 Выберите дату для установки выходного дня:\n"
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                message,
                reply_markup=reply_markup
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                print("ℹ️ Сообщение не изменилось, пропускаем edit")
            else:
                print(f"⚠️ Ошибка редактирования, отправляем новое: {e}")
                await query.message.reply_text(
                    message,
                    reply_markup=reply_markup
                )
    
    async def remove_day_off(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаляет выходной на конкретную дату"""
        query = update.callback_query
        
        if not self.availability_manager:
            await query.edit_message_text(
                "❌ Менеджер доступности не инициализирован",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
            return
        
        days_off = self.availability_manager.get_days_off()
        
        if not days_off:
            await query.edit_message_text(
                "📭 Нет установленных выходных дней",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="availability_menu")
                ]])
            )
            return
        
        keyboard = []
        row = []
        
        for i, date_str in enumerate(days_off):
            row.append(InlineKeyboardButton(
                f"❌ {date_str}",
                callback_data=f"remove_day_off_{date_str}"
            ))
            
            if len(row) == 2:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([
            InlineKeyboardButton("🔙 Назад", callback_data="availability_menu")
        ])
        
        message = "📅 Выберите дату для удаления выходного:\n"
        message += f"Всего выходных: {len(days_off)}\n\n"
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                message,
                reply_markup=reply_markup
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                print("ℹ️ Сообщение не изменилось, пропускаем edit")
            else:
                print(f"⚠️ Ошибка редактирования, отправляем новое: {e}")
                await query.message.reply_text(
                    message,
                    reply_markup=reply_markup
                )
    
    async def view_available_slots(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает свободные слоты на ближайшие дни"""
        query = update.callback_query
        
        if not self.availability_manager:
            await query.edit_message_text(
                "❌ Менеджер доступности не инициализирован",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 В меню", callback_data="menu_master")
                ]])
            )
            return
        
        # Получаем доступные даты на ближайшие 7 дней
        available_dates = self.availability_manager.get_available_dates(days_ahead=7)
        
        if not available_dates:
            await query.edit_message_text(
                "📭 Нет свободных слотов на ближайшие 7 дней",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Назад", callback_data="availability_menu")
                ]])
            )
            return
        
        message = "📅 Свободные слоты на ближайшие 7 дней:\n\n"
        
        for date_str in available_dates[:10]:  # Показываем первые 10 дней
            available_slots = self.availability_manager.get_available_slots(date_str)
            date_obj = datetime.strptime(date_str, '%d.%m.%Y')
            day_name = self._get_day_name(date_obj.weekday())
            
            message += f"📅 {date_str} ({day_name}):\n"
            message += f"   Свободные слоты: {len(available_slots)}\n"
            if available_slots:
                # Показываем первые 5 слотов
                slots_display = ", ".join(available_slots[:5])
                if len(available_slots) > 5:
                    slots_display += f" ... и ещё {len(available_slots) - 5}"
                message += f"   {slots_display}\n"
            message += "\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="availability_view_slots")],
            [InlineKeyboardButton("🔙 Назад", callback_data="availability_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                message,
                reply_markup=reply_markup
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                print("ℹ️ Сообщение не изменилось, пропускаем edit")
            else:
                print(f"⚠️ Ошибка редактирования, отправляем новое: {e}")
                await query.message.reply_text(
                    message,
                    reply_markup=reply_markup
                )
    
    # === Вспомогательные методы форматирования ===
    
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
                keyboard.append([
                    InlineKeyboardButton(f"🔄 Предложить перенос #{i}", 
                                       callback_data=f"reschedule_master_offer_{booking['booking_id']}")
                ])
            elif view_type == 'active':
                keyboard.append([
                    InlineKeyboardButton(f"✨ Выполнено #{i}", 
                                       callback_data=f"action_complete_{booking['booking_id']}"),
                    InlineKeyboardButton(f"🔄 Предложить перенос #{i}", 
                                       callback_data=f"reschedule_master_offer_{booking['booking_id']}")
                ])
            elif view_type == 'completed':
                keyboard.append([
                    InlineKeyboardButton(f"📋 Детали #{i}", 
                                       callback_data=f"action_view_{booking['booking_id']}")
                ])
        
        keyboard.append([InlineKeyboardButton("🔙 В меню", callback_data="menu_master")])
        
        return message, keyboard
    
    def _format_reschedule_request(self, request: dict) -> str:
        """Форматирует информацию о запросе на перенос"""
        return (f"<b>🔄 Запрос на перенос от клиента</b>\n\n"
                f"👤 Клиент: {request.get('client_name', '')}\n"
                f"📞 Телефон: {request.get('client_phone', '')}\n"
                f"📅 Текущее время: {request.get('old_date', '')} в {request.get('old_time', '')}\n"
                f"🔄 Предлагаемое время: {request.get('new_date', '')} в {request.get('new_time', '')}\n"
                f"💅 Услуга: {request.get('service', '')}\n"
                f"⏱️ Запрошено: {request.get('created_at', '')}\n")
    
    def _format_reschedule_request_short(self, request: dict, index: int) -> str:
        """Краткая информация о запросе на перенос"""
        return (f"<b>{index}. {request.get('client_name', '')}</b>\n"
                f"📅 Сейчас: {request.get('old_date', '')} {request.get('old_time', '')}\n"
                f"🔄 На: {request.get('new_date', '')} {request.get('new_time', '')}\n"
                f"💅 {request.get('service', '')}\n\n")
    
    def _format_reschedule_offer_short(self, offer: dict, index: int) -> str:
        """Краткая информация о предложении переноса"""
        return (f"<b>{index}. {offer.get('client_name', '')}</b>\n"
                f"📅 Предложено: {offer.get('new_date', '')} {offer.get('new_time', '')}\n"
                f"💅 {offer.get('service', '')}\n"
                f"⏱️ Отправлено: {offer.get('created_at', '')[:10]}\n\n")
    
    def _format_booking_info(self, booking: dict, index: int) -> str:
        """Форматирует информацию о записи"""
        try:
            created = datetime.fromisoformat(booking['created_at']).strftime('%d.%m.%Y %H:%M')
        except:
            created = "неизвестно"
        
        return (f"<b>{index}. {booking.get('name', 'Без имени')}</b>\n"
                f"📅 {booking.get('date', '??.??.????')} в {booking.get('time', '??:??')}\n"
                f"📞 {booking.get('phone', 'без телефона')}\n"
                f"💅 {booking.get('service', 'без услуги')}\n"
                f"⏱️ Создана: {created}\n\n")
    
    def _get_view_title(self, view_type: str) -> str:
        """Возвращает заголовок для раздела"""
        titles = {
            'active': '📋 Активные записи (подтвержденные)',
            'pending': '⏳ Записи, ожидающие подтверждения',
            'completed': '✅ Выполненные записи'
        }
        return titles.get(view_type, 'Записи')