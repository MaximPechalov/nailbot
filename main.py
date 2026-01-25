"""
Основной файл с исправленным ConversationHandler
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
    
    # Импортируем BookingHandlers и все состояния отдельно
    from bot_handlers import BookingHandlers
    
    storage_manager = StorageManager(google_sheets)
    notification_service = NotificationService(storage_manager)
    master_panel = MasterPanel(storage_manager, notification_service)
    
    # BookingHandlers теперь использует storage_manager вместо google_sheets напрямую
    booking_handlers = BookingHandlers(storage_manager, notification_service)
    
    # Определяем состояния для ConversationHandler (теперь здесь)
    (
        NAME, PHONE, DATE, TIME, SERVICE, CONFIRM, 
        CANCEL_SELECT, CANCEL_CONFIRM,
        RESCHEDULE_SELECT, RESCHEDULE_DATE, RESCHEDULE_TIME, RESCHEDULE_CONFIRM
    ) = range(12)
    
    # Определяем состояния для мастера
    (
        MASTER_RESCHEDULE_DATE, MASTER_RESCHEDULE_TIME, MASTER_RESCHEDULE_CONFIRM
    ) = range(100, 103)
    
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Функция для проверки, является ли пользователь мастером
    def is_master(update):
        """Проверяет, является ли пользователь мастером"""
        return str(update.effective_user.id) == str(MASTER_CHAT_ID)
    
    # === ОТДЕЛЬНЫЙ ConversationHandler для записи ===
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
        ]
    )
    
    # === ОТДЕЛЬНЫЙ ConversationHandler для отмены записей ===
    cancel_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^📅 Мои записи$'), 
                          booking_handlers.view_bookings)
        ],
        states={
            CANCEL_SELECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                              booking_handlers.select_booking_to_cancel)
            ],
            CANCEL_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                              booking_handlers.confirm_cancel_booking)
            ],
        },
        fallbacks=[
            CommandHandler('cancel', booking_handlers.cancel),
            CommandHandler('start', booking_handlers.start),
            MessageHandler(filters.Regex('^🔙 Назад в меню$'), 
                          lambda update, context: booking_handlers.cancel(update, context))
        ]
    )
    
    # === ОТДЕЛЬНЫЙ ConversationHandler для переноса записей (клиент) ===
    reschedule_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^🔄 Перенести запись$'), 
                          booking_handlers.start_reschedule)
        ],
        states={
            RESCHEDULE_SELECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, 
                              booking_handlers.select_booking_to_reschedule)
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
        ]
    )
    
    # === ОТДЕЛЬНЫЙ ConversationHandler для переноса записей (мастер) ===
    # Создаем функцию-обертку для проверки мастера
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
            MessageHandler(filters.Regex('^❌ Нет, отменить перенос$'), master_cancel_reschedule_wrapper)
        ]
    )
    
    # === Добавляем обработчики в правильном порядке ===
    
    # 1. Обработчик callback-кнопок мастера (включая переносы)
    application.add_handler(CallbackQueryHandler(
        master_panel.handle_callback,
        pattern="^(action_|reschedule_|view_|menu_)"
    ))
    
    # 2. Обработчик callback-кнопок клиента для переносов
    application.add_handler(CallbackQueryHandler(
        master_panel.handle_callback,
        pattern="^reschedule_client_"
    ))
    
    # 3. ConversationHandler для переноса записей (мастер)
    application.add_handler(master_reschedule_conv_handler)
    
    # 4. ConversationHandler для переноса записей (клиент)
    application.add_handler(reschedule_conv_handler)
    
    # 5. ConversationHandler для отмены записей
    application.add_handler(cancel_conv_handler)
    
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
    
    # 8. Обработчик команды /start
    application.add_handler(CommandHandler("start", booking_handlers.start))
    
    # 9. Обработчик главного меню (только информационные кнопки)
    application.add_handler(MessageHandler(
        filters.Regex('^(ℹ️ О нас|📞 Контакты|👨‍💻 Поддержка)$'), 
        booking_handlers.handle_main_menu
    ))
    
    # 10. Обработчик неизвестных команд
    application.add_handler(MessageHandler(
        filters.COMMAND, 
        booking_handlers.handle_unknown
    ))
    
    # 11. Запасной обработчик для любых других сообщений
    # Сначала проверяем, не мастер ли это в процессе переноса
    async def handle_text_messages(update, context):
        """Обрабатывает текстовые сообщения"""
        # Проверяем, не находится ли мастер в процессе переноса
        if is_master(update):
            # Проверяем, есть ли состояние переноса в context.user_data
            if 'master_reschedule' in context.user_data:
                current_state = context.user_data.get('_conversation_state')
                if current_state == MASTER_RESCHEDULE_DATE:
                    return await master_reschedule_date_wrapper(update, context)
                elif current_state == MASTER_RESCHEDULE_TIME:
                    return await master_reschedule_time_wrapper(update, context)
                elif current_state == MASTER_RESCHEDULE_CONFIRM:
                    return await master_reschedule_confirm_wrapper(update, context)
        
        # Если не мастер в процессе переноса, используем стандартный обработчик
        return await booking_handlers.handle_unknown(update, context)
    
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_text_messages
    ))
    
    # 12. Обработчик для любого другого контента
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
    print("🔄 Доступен функционал переноса записей (и для мастера тоже!)")
    
    # Проверяем, что MASTER_CHAT_ID установлен
    if not MASTER_CHAT_ID or MASTER_CHAT_ID == "ваш_chat_id_здесь":
        print("❌ ВНИМАНИЕ: MASTER_CHAT_ID не установлен в .env файле!")
        print("❌ Меню мастера не будет отправляться")
        print("❌ Установите правильный MASTER_CHAT_ID в файле .env")
    
    application.run_polling()

if __name__ == '__main__':
    main()