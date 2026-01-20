from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters
from telegram import Update
from config import TELEGRAM_BOT_TOKEN

def main():
    """Запуск бота"""
    print("🤖 Бот запускается...")
    
    # Пытаемся использовать Google Sheets, если не получается - используем CSV
    try:
        from google_sheets import GoogleSheets
        google_sheets = GoogleSheets()
        print("✅ Используем Google Sheets")
    except Exception as e:
        print(f"⚠️ Google Sheets не доступен ({e}), используем CSV")
        from simple_csv import SimpleCSVManager
        google_sheets = SimpleCSVManager()
    
    from notifications import NotificationManager
    from bot_handlers import BookingHandlers, NAME, PHONE, DATE, TIME, SERVICE, CONFIRM
    
    notification_manager = NotificationManager()
    booking_handlers = BookingHandlers(google_sheets, notification_manager)
    
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Создаем ConversationHandler для записи
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('book', booking_handlers.book)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_handlers.get_name)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_handlers.get_phone)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_handlers.get_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_handlers.get_time)],
            SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_handlers.get_service)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_handlers.confirm_booking)],
        },
        fallbacks=[CommandHandler('cancel', booking_handlers.cancel)]
    )
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", booking_handlers.start))
    application.add_handler(conv_handler)
    
    # Запускаем бота
    print("✅ Бот запущен!")
    print("ℹ️ Для остановки нажмите Ctrl+C")
    print("📱 Перейдите в Telegram и найдите вашего бота")
    application.run_polling()

if __name__ == '__main__':
    main()