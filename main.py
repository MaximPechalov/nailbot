"""
Основной файл - обновлен для поддержки напоминаний
"""

from telegram import Update
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from config import TELEGRAM_BOT_TOKEN, MASTER_CHAT_ID
import os
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    print("🤖 Бот запускается...")
    
    # Инициализация хранилища
    try:
        from google_sheets import GoogleSheets
        google_sheets = GoogleSheets()
        print("✅ Используем Google Sheets")
    except Exception as e:
        print(f"⚠️ Google Sheets не доступен ({e}), используем CSV")
        from simple_csv import SimpleCSVManager
        google_sheets = SimpleCSVManager()
    
    # Инициализация менеджеров
    from storage_manager import StorageManager
    from notification_service import NotificationService
    from master_panel import MasterPanel
    from availability_manager import AvailabilityManager
    from reminder_service import ReminderService
    
    # Импортируем BookingHandlers
    from bot_handlers import BookingHandlers
    
    storage_manager = StorageManager(google_sheets)
    notification_service = NotificationService(storage_manager)
    
    # Инициализируем сервис напоминаний
    reminder_service = ReminderService(storage_manager)
    
    # Инициализируем менеджер доступности
    availability_manager = AvailabilityManager(storage_manager)
    storage_manager.availability_manager = availability_manager
    
    master_panel = MasterPanel(storage_manager, notification_service)
    master_panel.set_availability_manager(availability_manager)
    
    booking_handlers = BookingHandlers(storage_manager, notification_service)
    
    # Определяем состояния (ВАЖНО: должно совпадать с bot_handlers.py)
    (
        NAME, PHONE, DATE, TIME, SERVICE, CONFIRM, 
        BOOKING_ACTION_SELECT, CANCEL_CONFIRM,
        RESCHEDULE_DATE, RESCHEDULE_TIME, RESCHEDULE_CONFIRM
    ) = range(11)
    
    # Состояния для мастера - должны быть отдельными
    (
        MASTER_RESCHEDULE_DATE, MASTER_RESCHEDULE_TIME, MASTER_RESCHEDULE_CONFIRM
    ) = range(100, 103)
    
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    def is_master(update):
        """Проверяет, является ли пользователь мастером"""
        return str(update.effective_user.id) == str(MASTER_CHAT_ID)
    
    # === Обработчик callback для напоминаний ===
    async def handle_reminder_callback_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик callback от кнопок напоминаний"""
        query = update.callback_query
        data = query.data
        
        if data.startswith('pause_reminders_') or data.startswith('disable_reminders_'):
            await reminder_service.handle_reminder_callback(update, context, data)
        else:
            await query.answer()
            await query.edit_message_text("❌ Неизвестная команда")
    
    # === ConversationHandler для записи ===
    booking_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^📝 Записаться на маникюр$'), 
                          booking_handlers.book)
        ],
        states={
            NAME: [
                MessageHandler(filters.Regex('^(Использовать имя из профиля Telegram|Ввести другое имя)$'), 
                              booking_handlers.get_name),
                MessageHandler(filters.TEXT & ~filters.COMMAND, booking_handlers.handle_name_text)
            ],
            PHONE: [
                MessageHandler(filters.Regex(r'^Использовать .*'), booking_handlers.get_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, booking_handlers.get_phone)
            ],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_handlers.get_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_handlers.get_time)],
            SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_handlers.get_service)],
            CONFIRM: [MessageHandler(filters.Regex('^(✅ Да, всё верно|❌ Нет, исправить)$'), 
                                    booking_handlers.confirm_booking)],
        },
        fallbacks=[
            CommandHandler('cancel', booking_handlers.cancel),
            CommandHandler('start', booking_handlers.start)
        ],
        name="booking_conversation",
        persistent=False
    )
    
    # === ConversationHandler для управления записями (объединенный) ===
    bookings_management_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^📅 Мои записи$'), 
                          booking_handlers.view_bookings)
        ],
        states={
            BOOKING_ACTION_SELECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                              booking_handlers.select_booking_action)
            ],
            CANCEL_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                              booking_handlers.confirm_cancel_booking)
            ],
            RESCHEDULE_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                              booking_handlers.get_reschedule_date)
            ],
            RESCHEDULE_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                              booking_handlers.get_reschedule_time)
            ],
            RESCHEDULE_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                              booking_handlers.confirm_reschedule)
            ],
        },
        fallbacks=[
            CommandHandler('cancel', booking_handlers.cancel),
            CommandHandler('start', booking_handlers.start),
            MessageHandler(filters.Regex('^🔙 Назад в меню$'), 
                          lambda update, context: booking_handlers.cancel(update, context))
        ],
        name="bookings_management_conversation",
        persistent=False
    )
    
    # === ConversationHandler для переноса записей (мастер) ===
    async def master_reschedule_date_wrapper(update, context):
        if not is_master(update):
            await update.message.reply_text("❌ Эта команда доступна только мастеру.")
            return ConversationHandler.END
        return await master_panel.handle_master_reschedule_date(update, context)
    
    async def master_reschedule_time_wrapper(update, context):
        if not is_master(update):
            await update.message.reply_text("❌ Эта команда доступна только мастеру.")
            return ConversationHandler.END
        return await master_panel.handle_master_reschedule_time(update, context)
    
    async def master_reschedule_confirm_wrapper(update, context):
        if not is_master(update):
            await update.message.reply_text("❌ Эта команда доступна только мастеру.")
            return ConversationHandler.END
        return await master_panel.handle_master_reschedule_confirm(update, context)
    
    async def master_cancel_reschedule_wrapper(update, context):
        if not is_master(update):
            await update.message.reply_text("❌ Эта команда доступна только мастеру.")
            return ConversationHandler.END
        return await master_panel.handle_master_cancel_reschedule(update, context)
    
    master_reschedule_conv_handler = ConversationHandler(
        entry_points=[],
        states={
            MASTER_RESCHEDULE_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, master_reschedule_date_wrapper)
            ],
            MASTER_RESCHEDULE_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, master_reschedule_time_wrapper)
            ],
            MASTER_RESCHEDULE_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, master_reschedule_confirm_wrapper)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex('^❌ Нет, отменить$'), master_cancel_reschedule_wrapper)
        ],
        name="master_reschedule_conversation",
        persistent=False
    )
    
    # === Команда для управления напоминаниями ===
    async def reminders_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает настройки напоминаний"""
        from datetime import datetime  # Добавляем импорт здесь
        user_id = update.effective_user.id
        user_settings = reminder_service.get_user_settings(user_id)
        
        enabled_emoji = "✅" if user_settings.get('enabled', True) else "❌"
        reminder_24h_emoji = "✅" if user_settings.get('reminder_24h', True) else "❌"
        reminder_2h_emoji = "✅" if user_settings.get('reminder_2h', True) else "❌"
        
        pause_until = user_settings.get('pause_until')
        pause_text = ""
        if pause_until:
            try:
                pause_dt = datetime.fromisoformat(pause_until)
                if pause_dt > datetime.now():
                    pause_text = f"\n⏸️ Напоминания приостановлены до: {pause_dt.strftime('%d.%m.%Y %H:%M')}"
                else:
                    pause_text = "\n✅ Напоминания активны"
            except:
                pause_text = "\n✅ Напоминания активны"
        else:
            pause_text = "\n✅ Напоминания активны"
        
        message = (
            f"🔔 <b>Настройки напоминаний</b>\n\n"
            f"Вы будете получать напоминания:\n"
            f"{reminder_24h_emoji} <b>За 24 часа</b> до записи\n"
            f"{reminder_2h_emoji} <b>За 2 часа</b> до записи\n\n"
            f"{enabled_emoji} <b>Статус:</b> {'Включены' if user_settings.get('enabled', True) else 'Отключены'}\n"
            f"{pause_text}\n\n"
            f"<i>Выберите действие:</i>"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Включить напоминания", callback_data="reminders_enable"),
                InlineKeyboardButton("❌ Выключить напоминания", callback_data="reminders_disable")
            ],
            [
                InlineKeyboardButton("⏰ За 24 часа", 
                                   callback_data=f"reminders_toggle_24h_{'off' if user_settings.get('reminder_24h', True) else 'on'}"),
                InlineKeyboardButton("⏱️ За 2 часа", 
                                   callback_data=f"reminders_toggle_2h_{'off' if user_settings.get('reminder_2h', True) else 'on'}")
            ],
            [
                InlineKeyboardButton("⏸️ Приостановить на сутки", callback_data="reminders_pause_24"),
                InlineKeyboardButton("⏸️ Приостановить на 3 дня", callback_data="reminders_pause_72")
            ],
            [
                InlineKeyboardButton("⏸️ Приостановить на неделю", callback_data="reminders_pause_168"),
                InlineKeyboardButton("🚫 Отключить навсегда", callback_data="reminders_disable_forever")
            ],
            [
                InlineKeyboardButton("🔙 Назад в меню", callback_data="reminders_back")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    # === Обработчик callback для настроек напоминаний ===
    async def handle_reminder_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает callback от настроек напоминаний"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        if data == "reminders_enable":
            reminder_service.enable_reminders(user_id)
            await query.edit_message_text(
                "✅ Напоминания включены. Вы будете получать уведомления:\n"
                "• За 24 часа до записи\n"
                "• За 2 часа до записи",
                parse_mode='HTML'
            )
            
        elif data == "reminders_disable":
            reminder_service.disable_reminders(user_id)
            await query.edit_message_text(
                "❌ Напоминания отключены. Вы больше не будете получать уведомления о записях.",
                parse_mode='HTML'
            )
            
        elif data == "reminders_disable_forever":
            reminder_service.disable_reminders(user_id)
            await query.edit_message_text(
                "🚫 Напоминания отключены навсегда.\n"
                "Вы можете включить их снова через настройки бота.",
                parse_mode='HTML'
            )
            
        elif data.startswith("reminders_toggle_"):
            parts = data.split('_')
            if len(parts) >= 4:
                reminder_type = parts[2]  # 24h или 2h
                action = parts[3]  # on или off
                
                new_value = action == 'on'
                updates = {f'reminder_{reminder_type}': new_value}
                reminder_service.update_user_settings(user_id, updates)
                
                time_text = "24 часа" if reminder_type == "24h" else "2 часа"
                status = "включено" if new_value else "отключено"
                await query.edit_message_text(
                    f"✅ Напоминание за {time_text} {status}.",
                    parse_mode='HTML'
                )
                
        elif data.startswith("reminders_pause_"):
            parts = data.split('_')
            if len(parts) >= 3:
                duration_hours = int(parts[2])  # 24, 72 или 168
                pause_until = reminder_service.pause_reminders(user_id, duration_hours)
                
                duration_text = reminder_service._get_duration_text(duration_hours)
                await query.edit_message_text(
                    f"⏸️ Напоминания приостановлены на {duration_text}.\n"
                    f"Вы снова будете получать их после {pause_until.strftime('%d.%m.%Y %H:%M')}.",
                    parse_mode='HTML'
                )
                
        elif data == "reminders_back":
            await query.delete_message()
            await booking_handlers.start(update, context)
    
    # === Добавляем обработчики ===
    
    # 1. Обработчик callback-кнопок мастера
    application.add_handler(CallbackQueryHandler(
        master_panel.handle_callback,
        pattern="^(action_|reschedule_|view_|menu_|availability_|work_hours_|save_hours_|set_day_off_|remove_day_off_)"
    ))
    
    # 2. Обработчик callback-кнопок напоминаний
    application.add_handler(CallbackQueryHandler(
        handle_reminder_callback_wrapper,
        pattern="^(pause_reminders_|disable_reminders_)"
    ))
    
    # 3. Обработчик callback-кнопок настроек напоминаний
    application.add_handler(CallbackQueryHandler(
        handle_reminder_settings_callback,
        pattern="^(reminders_enable|reminders_disable|reminders_toggle_|reminders_pause_|reminders_back|reminders_disable_forever)"
    ))
    
    # 4. ConversationHandler для переноса записей (мастер)
    application.add_handler(master_reschedule_conv_handler)
    
    # 5. ConversationHandler для управления записями (клиент - объединенный)
    application.add_handler(bookings_management_conv_handler)
    
    # 6. ConversationHandler для создания записи
    application.add_handler(booking_conv_handler)
    
    # 7. Команда для меню мастера
    async def send_master_menu(update, context):
        """Команда для отправки меню мастера"""
        if str(update.effective_chat.id) != MASTER_CHAT_ID:
            await update.message.reply_text("❌ Эта команда доступна только мастеру.")
            return
        
        await master_panel.send_master_menu(context.bot, MASTER_CHAT_ID)
    
    application.add_handler(CommandHandler("master", send_master_menu))
    
    # 8. Команда для настроек напоминаний
    application.add_handler(CommandHandler("reminders", reminders_settings))
    
    # 9. Обработчик команды /start
    application.add_handler(CommandHandler("start", booking_handlers.start))
    
    # 10. Обработчик информационных кнопок главного меню
    async def handle_info_buttons(update, context):
        """Обработчик информационных кнопок главного меню"""
        text = update.message.text
        
        if text == 'ℹ️ О нас':
            await update.message.reply_text(
                booking_handlers._get_about_info(),
                reply_markup=booking_handlers._get_main_menu()
            )
        elif text == '📞 Контакты':
            await update.message.reply_text(
                booking_handlers._get_contacts_info(),
                reply_markup=booking_handlers._get_main_menu()
            )
        elif text == '👨‍💻 Поддержка':
            await update.message.reply_text(
                booking_handlers._get_support_info(),
                reply_markup=booking_handlers._get_main_menu()
            )
        elif text == '🔔 Настройки напоминаний':
            await reminders_settings(update, context)
        else:
            await update.message.reply_text(
                "Пожалуйста, используйте меню ниже ⬇️",
                reply_markup=booking_handlers._get_main_menu()
            )
        
        return ConversationHandler.END
    
    application.add_handler(MessageHandler(
        filters.Regex('^(ℹ️ О нас|📞 Контакты|👨‍💻 Поддержка|🔔 Настройки напоминаний)$'), 
        handle_info_buttons
    ))
    
    # 11. Обработчик неизвестных команд
    application.add_handler(MessageHandler(
        filters.COMMAND, 
        booking_handlers.handle_unknown
    ))
    
    # 12. Запасной обработчик текстовых сообщений
    async def handle_text_messages(update, context):
        """Обрабатывает текстовые сообщения"""
        # Проверяем, является ли пользователь мастером
        if is_master(update):
            if 'master_reschedule' in context.user_data:
                current_state = context.user_data.get('_conversation_state')
                if current_state == MASTER_RESCHEDULE_DATE:
                    return await master_reschedule_date_wrapper(update, context)
                elif current_state == MASTER_RESCHEDULE_TIME:
                    return await master_reschedule_time_wrapper(update, context)
                elif current_state == MASTER_RESCHEDULE_CONFIRM:
                    return await master_reschedule_confirm_wrapper(update, context)
        
        # Для клиентов - просто показываем главное меню
        await update.message.reply_text(
            "Извините, я не понимаю эту команду.\n"
            "Пожалуйста, используйте меню ниже ⬇️",
            reply_markup=booking_handlers._get_main_menu()
        )
        return ConversationHandler.END
    
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_text_messages
    ))
    
    # 13. Обработчик для любого другого контента
    application.add_handler(MessageHandler(
        filters.ALL, 
        booking_handlers.handle_unknown
    ))
    
    # Обработчик ошибок
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает ошибки"""
        logger.error(f"Ошибка при обработке обновления {update}: {context.error}")
        
        if context.error:
            try:
                # Если это ошибка "Message is not modified", просто игнорируем
                if "Message is not modified" in str(context.error):
                    return
                    
                # Другие ошибки логируем
                error_message = f"⚠️ Произошла ошибка: {context.error}"
                
                # Отправляем сообщение только если есть куда отправлять
                if update and update.effective_chat:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="❌ Произошла ошибка. Пожалуйста, попробуйте позже."
                    )
                    
            except Exception as e:
                logger.error(f"Ошибка в обработчике ошибок: {e}")
    
    application.add_error_handler(error_handler)
    
    # Запускаем сервис напоминаний
    reminder_service.start()
    
    # Отправляем меню мастера при запуске
    async def post_init(application):
        try:
            print(f"🔄 Отправка меню мастера в чат {MASTER_CHAT_ID}...")
            await master_panel.send_master_menu(application.bot, MASTER_CHAT_ID)
            print("✅ Меню мастера отправлено при запуске")
            
            print("✅ Сервис напоминаний запущен")
            
        except Exception as e:
            print(f"⚠️ Не удалось отправить меню мастера при запуске: {e}")
    
    application.post_init = post_init
    
    # Останавливаем сервисы при завершении
    async def shutdown(application):
        print("🛑 Остановка сервисов...")
        await reminder_service.stop()
        print("✅ Все сервисы остановлены")
    
    # Запускаем бота
    print("✅ Бот запущен!")
    print("ℹ️ Для остановки нажмите Ctrl+C")
    print("📱 Перейдите в Telegram и найдите вашего бота")
    print("👑 Мастер получит уведомления и меню управления")
    print("💼 Команда /master - открыть панель управления")
    print("🔔 Команда /reminders - настройки напоминаний")
    
    # Проверяем MASTER_CHAT_ID
    if not MASTER_CHAT_ID or MASTER_CHAT_ID == "ваш_chat_id_здесь":
        print("❌ ВНИМАНИЕ: MASTER_CHAT_ID не установлен в .env файле!")
    
    try:
        await application.initialize()
        await application.start()
        await application.post_init(application)
        await application.updater.start_polling()
        
        # Держим бота запущенным
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
    finally:
        # Останавливаем сервисы при завершении
        await shutdown(application)
        await application.stop()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())