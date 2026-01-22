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
    from bot_handlers import BookingHandlers, NAME, PHONE, DATE, TIME, SERVICE, CONFIRM, CANCEL_SELECT, CANCEL_CONFIRM
    
    storage_manager = StorageManager(google_sheets)
    notification_service = NotificationService(storage_manager)
    master_panel = MasterPanel(storage_manager, notification_service)
    
    # BookingHandlers теперь использует storage_manager вместо google_sheets напрямую
    booking_handlers = BookingHandlers(storage_manager, notification_service)
    
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
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
    
    # === Добавляем обработчики в правильном порядке ===
    
    # 1. Обработчик callback-кнопок мастера
    application.add_handler(CallbackQueryHandler(
        master_panel.handle_callback,
        pattern="^(action_|view_|menu_)"
    ))
    
    # 2. ConversationHandler для отмены записей
    application.add_handler(cancel_conv_handler)
    
    # 3. ConversationHandler для создания записи
    application.add_handler(booking_conv_handler)
    
    # 4. Команда для меню мастера
    async def send_master_menu(update, context):
        """Команда для отправки меню мастера"""
        if str(update.effective_chat.id) != MASTER_CHAT_ID:
            await update.message.reply_text("❌ Эта команда доступна только мастеру.")
            return
        
        await master_panel.send_master_menu(context.bot, MASTER_CHAT_ID)
    
    application.add_handler(CommandHandler("master", send_master_menu))
    
    # 5. Обработчик команды /start
    application.add_handler(CommandHandler("start", booking_handlers.start))
    
    # 6. Обработчик главного меню (только информационные кнопки)
    application.add_handler(MessageHandler(
        filters.Regex('^(ℹ️ О нас|📞 Контакты|👨‍💻 Поддержка)$'), 
        booking_handlers.handle_main_menu
    ))
    
    # 7. Обработчик неизвестных команд
    application.add_handler(MessageHandler(
        filters.COMMAND, 
        booking_handlers.handle_unknown
    ))
    
    # 8. Запасной обработчик для любых других сообщений
    application.add_handler(MessageHandler(
        filters.TEXT, 
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
            # Можно добавить детальную информацию об ошибке
            import traceback
            traceback.print_exc()
    
    application.post_init = post_init
    
    # Запускаем бота
    print("✅ Бот запущен!")
    print("ℹ️ Для остановки нажмите Ctrl+C")
    print("📱 Перейдите в Telegram и найдите вашего бота")
    print("👑 Мастер получит уведомления и меню управления")
    print("💼 Команда /master - открыть панель управления")
    
    # Проверяем, что MASTER_CHAT_ID установлен
    if not MASTER_CHAT_ID or MASTER_CHAT_ID == "ваш_chat_id_здесь":
        print("❌ ВНИМАНИЕ: MASTER_CHAT_ID не установлен в .env файле!")
        print("❌ Меню мастера не будет отправляться")
        print("❌ Установите правильный MASTER_CHAT_ID в файле .env")
    
    application.run_polling()

if __name__ == '__main__':
    main()