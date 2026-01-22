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
    
    async def _show_main_menu(self, update: Update):
        """Показывает главное меню мастера"""
        keyboard = [
            [
                InlineKeyboardButton("📋 Активные", callback_data="view_active"),
                InlineKeyboardButton("⏳ Ожидают", callback_data="view_pending")
            ],
            [
                InlineKeyboardButton("✅ Выполненные", callback_data="view_completed"),
                InlineKeyboardButton("📊 Статистика", callback_data="view_stats")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "🎛️ Панель управления мастера\nВыберите раздел:",
            reply_markup=reply_markup
        )
    
    async def _show_view(self, update: Update, context, view_type: str):
        """Показывает записи по категории"""
        status_map = {
            'active': 'подтверждено',
            'pending': 'ожидает',
            'completed': 'выполнено'
        }
        
        if view_type == 'stats':
            await self._show_statistics(update)
            return
        
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
    
    async def _show_statistics(self, update: Update):
        """Показывает статистику"""
        stats = self.storage.get_statistics()
        
        message = (
            f"📊 <b>Статистика записей:</b>\n\n"
            f"📈 Всего записей: <b>{stats['total']}</b>\n"
            f"⏳ Ожидают подтверждения: <b>{stats['ожидает']}</b>\n"
            f"✅ Подтвержденные: <b>{stats['подтверждено']}</b>\n"
            f"✨ Выполненные: <b>{stats['выполнено']}</b>\n"
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
        """Отправляет меню мастера в чат
        Args:
            bot: объект Bot или Application.bot
            chat_id: ID чата мастера
        """
        keyboard = [
            [
                InlineKeyboardButton("📋 Активные", callback_data="view_active"),
                InlineKeyboardButton("⏳ Ожидают", callback_data="view_pending")
            ],
            [
                InlineKeyboardButton("✅ Выполненные", callback_data="view_completed"),
                InlineKeyboardButton("📊 Статистика", callback_data="view_stats")
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
                                       callback_data=f"action_complete_{booking['booking_id']}")
                ])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_master")])
        
        return message, keyboard
    
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