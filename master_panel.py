"""
Отдельный модуль для всей логики панели мастера
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes
from datetime import datetime
import json
import os

class MasterPanel:
    def __init__(self, storage_manager, notification_service):
        self.storage = storage_manager
        self.notifications = notification_service
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Основной обработчик callback от мастера"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        print(f"📲 Получен callback от мастера: {data}")
        
        if data.startswith('action_'):
            # Обработка действий с записями
            parts = data.split('_')
            if len(parts) >= 3:
                action = parts[1]
                booking_id = parts[2]
                await self._handle_booking_action(update, context, action, booking_id)
        
        elif data.startswith('reschedule_'):
            # Обработка переносов записей
            parts = data.split('_')
            if len(parts) >= 3:
                action = parts[1]
                booking_id = parts[2]
                await self._handle_reschedule_action(update, context, action, booking_id)
        
        elif data.startswith('view_'):
            # Просмотр разных категорий записей
            view_type = data.split('_')[1]
            await self._show_view(update, context, view_type)
        
        elif data == 'menu_master':
            # Главное меню мастера
            await self._show_main_menu(update)
    
    async def _handle_booking_action(self, update: Update, context, action: str, booking_id: str):
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
            await self._start_master_reschedule(update, booking_id, booking)
    
    async def _handle_reschedule_action(self, update: Update, context, action: str, booking_id: str):
        """Обрабатывает действие с переносом записи"""
        if action == 'confirm':
            await self._confirm_reschedule(update, booking_id)
        elif action == 'reject':
            await self._reject_reschedule(update, booking_id)
        elif action == 'client_accept':
            await self._client_accept_reschedule(update, booking_id)
        elif action == 'client_reject':
            await self._client_reject_reschedule(update, booking_id)
    
    async def _confirm_booking(self, update: Update, booking_id: str, booking: dict):
        """Подтверждает запись"""
        success = self.storage.update_booking_status(booking_id, 'подтверждено')
        
        if success:
            # Уведомляем клиента
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
            # Уведомляем клиента
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
            # Уведомляем клиента
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
            # Уведомляем клиента
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
    
    async def _start_master_reschedule(self, update: Update, booking_id: str, booking: dict):
        """Начинает процесс переноса записи мастером"""
        # Сохраняем ID записи для переноса
        context.user_data['master_reschedule_booking_id'] = booking_id
        
        # Формируем сообщение с информацией
        message = f"""
🔄 ПЕРЕНЕСТИ ЗАПИСЬ

Вы выбрали запись для переноса:

👤 Клиент: {booking.get('name', '')}
📞 Телефон: {booking.get('phone', '')}
📅 Дата: {booking.get('date', '')}
⏰ Время: {booking.get('time', '')}
💅 Услуга: {booking.get('service', '')}

✏️ Введите новую дату в формате ДД.ММ.ГГГГ
(например: 25.12.2024)
"""
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Отмена", callback_data=f"action_view_{booking_id}")
            ]])
        )
        
        # Переходим в состояние ожидания ввода даты
        return "WAITING_RESCHEDULE_DATE"
    
    async def _confirm_reschedule(self, update: Update, reschedule_id: str):
        """Подтверждает перенос записи мастером"""
        reschedule_info = self.storage.get_reschedule_info(reschedule_id)
        
        if not reschedule_info:
            await update.callback_query.edit_message_text("❌ Информация о переносе не найдена")
            return
        
        original_booking_id = reschedule_info.get('original_booking_id')
        new_booking_id = reschedule_info.get('new_booking_id')
        
        # Подтверждаем новую запись
        success = self.storage.confirm_reschedule(original_booking_id, new_booking_id)
        
        if success:
            # Уведомляем клиента о переносе
            new_booking = self.storage.get_booking(new_booking_id)
            client_id = new_booking.get('telegram_id')
            client_name = new_booking.get('name')
            
            await self.notifications.notify_client_reschedule_confirmed(
                original_booking_id, new_booking_id,
                client_id, client_name,
                new_booking.get('date'), new_booking.get('time')
            )
            
            # Обновляем сообщение мастера
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
        """Отклоняет перенос записи мастером"""
        reschedule_info = self.storage.get_reschedule_info(reschedule_id)
        
        if not reschedule_info:
            await update.callback_query.edit_message_text("❌ Информация о переносе не найдена")
            return
        
        original_booking_id = reschedule_info.get('original_booking_id')
        new_booking_id = reschedule_info.get('new_booking_id')
        
        # Отклоняем перенос
        success = self.storage.reject_reschedule(original_booking_id, new_booking_id)
        
        if success:
            # Уведомляем клиента об отклонении переноса
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
        booking = self.storage.get_booking(booking_id)
        
        if not booking:
            await update.callback_query.edit_message_text("❌ Запись не найдена")
            return
        
        # Обновляем статус записи
        success = self.storage.update_booking_status(booking_id, 'подтверждено')
        
        if success:
            # Уведомляем мастера
            await self.notifications.notify_master_client_decision(
                booking_id, 'accept', 
                booking['name'], booking['date'], booking['time']
            )
            
            message = f"""
✅ Вы приняли новое время записи!

📅 Дата: {booking.get('date')}
⏰ Время: {booking.get('time')}
💅 Услуга: {booking.get('service')}

✅ Мастер уведомлен о вашем согласии.
Ждем вас в салоне! 💅
"""
            
            await update.callback_query.edit_message_text(message)
        else:
            await update.callback_query.edit_message_text(
                "❌ Ошибка при подтверждении записи"
            )
    
    async def _client_reject_reschedule(self, update: Update, booking_id: str):
        """Клиент отклоняет предложенный мастером перенос"""
        booking = self.storage.get_booking(booking_id)
        
        if not booking:
            await update.callback_query.edit_message_text("❌ Запись не найдена")
            return
        
        # Отменяем запись
        success = self.storage.update_booking_status(booking_id, 'отменено')
        
        if success:
            # Уведомляем мастера
            await self.notifications.notify_master_client_decision(
                booking_id, 'reject', 
                booking['name'], booking['date'], booking['time']
            )
            
            message = f"""
❌ Вы отклонили предложенное время записи.

Запись на {booking.get('date')} в {booking.get('time')} отменена.

✅ Мастер уведомлен о вашем решении.
Вы можете записаться на другое время через главное меню.
"""
            
            await update.callback_query.edit_message_text(message)
        else:
            await update.callback_query.edit_message_text(
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
                InlineKeyboardButton("🔄 Переносы", callback_data="view_rescheduling"),  # НОВЫЙ
                InlineKeyboardButton("✅ Выполненные", callback_data="view_completed")
            ],
            [
                InlineKeyboardButton("📊 Статистика", callback_data="view_stats"),
                InlineKeyboardButton("🔄 Обновить", callback_data="menu_master")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Получаем статистику для отображения
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
    
    async def _show_view(self, update: Update, context, view_type: str):
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
            message = "📭 Нет запросов на перенос записей"
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
            
            # Кнопки для действий
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
            f"🔄 Переносы (ожидание): <b>{stats.get('перенос (ожидание мастера)', 0)}</b>\n"
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
    
    # Вспомогательные методы для форматирования
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
            # Форматируем информацию о записи
            message += self._format_booking_info(booking, i)
            
            # Добавляем кнопки действий
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