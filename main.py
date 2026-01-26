"""
Основной файл - обновлен для новой логики меню
"""

from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from config import TELEGRAM_BOT_TOKEN, MASTER_CHAT_ID
import os

def main():
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
    
    # Импортируем BookingHandlers
    from bot_handlers import BookingHandlers
    
    storage_manager = StorageManager(google_sheets)
    notification_service = NotificationService(storage_manager)
    master_panel = MasterPanel(storage_manager, notification_service)
    
    booking_handlers = BookingHandlers(storage_manager, notification_service)
    
    # Определяем состояния (ВАЖНО: должно совпадать с bot_handlers.py)
    (
        NAME, PHONE, DATE, TIME, SERVICE, CONFIRM, 
        BOOKING_ACTION_SELECT, CANCEL_CONFIRM,
        RESCHEDULE_DATE, RESCHEDULE_TIME, RESCHEDULE_CONFIRM
    ) = range(11)  # 11 состояний (0-10)
    
    # Состояния для мастера - должны быть отдельными
    (
        MASTER_RESCHEDULE_DATE, MASTER_RESCHEDULE_TIME, MASTER_RESCHEDULE_CONFIRM
    ) = range(100, 103)  # Используем другие номера (100-102)
    
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    def is_master(update):
        """Проверяет, является ли пользователь мастером"""
        return str(update.effective_user.id) == str(MASTER_CHAT_ID)
    
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
            BOOKING_ACTION_SELECT: [  # Состояние 6
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                              booking_handlers.select_booking_action)
            ],
            CANCEL_CONFIRM: [  # Состояние 7
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                              booking_handlers.confirm_cancel_booking)
            ],
            RESCHEDULE_DATE: [  # Состояние 8
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                              booking_handlers.get_reschedule_date)
            ],
            RESCHEDULE_TIME: [  # Состояние 9
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                              booking_handlers.get_reschedule_time)
            ],
            RESCHEDULE_CONFIRM: [  # Состояние 10
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
    
    # === Добавляем обработчики ===
    
    # 1. Обработчик callback-кнопок
    application.add_handler(CallbackQueryHandler(
        master_panel.handle_callback,
        pattern="^(action_|reschedule_|view_|menu_)"
    ))
    
    # 2. ConversationHandler для переноса записей (мастер)
    application.add_handler(master_reschedule_conv_handler)
    
    # 3. ConversationHandler для управления записями (клиент - объединенный)
    application.add_handler(bookings_management_conv_handler)
    
    # 4. ConversationHandler для создания записи
    application.add_handler(booking_conv_handler)
    
    # 5. Команда для меню мастера
    async def send_master_menu(update, context):
        """Команда для отправки меню мастера"""
        if str(update.effective_chat.id) != MASTER_CHAT_ID:
            await update.message.reply_text("❌ Эта команда доступна только мастеру.")
            return
        
        await master_panel.send_master_menu(context.bot, MASTER_CHAT_ID)
    
    application.add_handler(CommandHandler("master", send_master_menu))
    
    # 6. Обработчик команды /start
    application.add_handler(CommandHandler("start", booking_handlers.start))
    
    # 7. Обработчик информационных кнопок главного меню
    async def handle_info_buttons(update, context):
        """Обработчик информационных кнопок главного меню"""
        text = update.message.text
        
        if text == 'ℹ️ О нас':
            await update.message.reply_text(
                "💅 Салон маникюра 'Лаковые нежности'\n\n"
                "🕒 Режим работы: 10:00 - 22:00\n"
                "📍 Адрес: ул. Красивых ногтей, д. 10\n\n"
                "Мы делаем ваши ногти красивыми!",
                reply_markup=booking_handlers._get_main_menu()
            )
        elif text == '📞 Контакты':
            await update.message.reply_text(
                "📞 Наши контакты:\n\n"
                "☎️ Телефон: +7 (999) 123-45-67\n"
                "📍 Адрес: ул. Красивых ногтей, д. 10\n"
                "🕒 Часы работы: 10:00 - 22:00\n\n"
                "📱 Instagram: @manicure_beauty\n"
                "📸 VK: vk.com/manicure_beauty",
                reply_markup=booking_handlers._get_main_menu()
            )
        elif text == '👨‍💻 Поддержка':
            await update.message.reply_text(
                "Если у вас возникли проблемы с записью:\n\n"
                "📱 Напишите нам: @manicure_support\n"
                "☎️ Позвоните: +7 (999) 123-45-67\n"
                "✉️ Email: support@manicure.ru",
                reply_markup=booking_handlers._get_main_menu()
            )
        else:
            await update.message.reply_text(
                "Пожалуйста, используйте меню ниже ⬇️",
                reply_markup=booking_handlers._get_main_menu()
            )
        
        return ConversationHandler.END
    
    application.add_handler(MessageHandler(
        filters.Regex('^(ℹ️ О нас|📞 Контакты|👨‍💻 Поддержка)$'), 
        handle_info_buttons
    ))
    
    # 8. Обработчик неизвестных команд
    application.add_handler(MessageHandler(
        filters.COMMAND, 
        booking_handlers.handle_unknown
    ))
    
    # 9. Запасной обработчик текстовых сообщений
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
    
    # 10. Обработчик для любого другого контента
    application.add_handler(MessageHandler(
        filters.ALL, 
        booking_handlers.handle_unknown
    ))
    
    # Отправляем меню мастера при запуске
    async def post_init(application):
        try:
            print(f"🔄 Отправка меню мастера в чат {MASTER_CHAT_ID}...")
            await master_panel.send_master_menu(application.bot, MASTER_CHAT_ID)
            print("✅ Меню мастера отправлено при запуске")
        except Exception as e:
            print(f"⚠️ Не удалось отправить меню мастера при запуске: {e}")
    
    application.post_init = post_init
    
    # Запускаем бота
    print("✅ Бот запущен!")
    print("ℹ️ Для остановки нажмите Ctrl+C")
    print("📱 Перейдите в Telegram и найдите вашего бота")
    print("👑 Мастер получит уведомления и меню управления")
    print("💼 Команда /master - открыть панель управления")
    
    # Проверяем MASTER_CHAT_ID
    if not MASTER_CHAT_ID or MASTER_CHAT_ID == "ваш_chat_id_здесь":
        print("❌ ВНИМАНИЕ: MASTER_CHAT_ID не установлен в .env файле!")
    
    application.run_polling()

if __name__ == '__main__':
    main()