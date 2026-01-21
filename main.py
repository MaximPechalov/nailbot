from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import Update
from config import TELEGRAM_BOT_TOKEN
import json
import os

async def handle_master_callback(update: Update, context):
    """Обработчик callback от мастера (подтверждение/отклонение записи)"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    print(f"📲 Получен callback от мастера: {data}")
    
    if '_' not in data:
        await query.edit_message_text("❌ Ошибка в данных")
        return
    
    action, booking_id = data.split('_', 1)
    
    # Загружаем данные из файла
    storage_file = 'bookings_storage.json'
    if not os.path.exists(storage_file):
        await query.edit_message_text("❌ Данные не найдены")
        return
    
    with open(storage_file, 'r', encoding='utf-8') as f:
        all_bookings = json.load(f)
    
    booking_data = all_bookings.get(booking_id)
    
    if not booking_data:
        await query.edit_message_text("❌ Запись не найдена")
        return
    
    user_id = booking_data.get('user_id')
    user_name = booking_data.get('name', 'клиент')
    
    if action == 'confirm':
        # Подтверждение записи
        status = 'подтверждено'
        await query.edit_message_text(
            f"✅ Запись подтверждена!\n\n"
            f"👤 Клиент: {booking_data['name']}\n"
            f"📱 Телефон: {booking_data['phone']}\n"
            f"📅 Дата: {booking_data['date']}\n"
            f"⏰ Время: {booking_data['time']}\n"
            f"💅 Услуга: {booking_data['service']}\n\n"
            f"⏱️ Подтверждено в: {query.message.date.strftime('%Y-%m-%d %H:%M:%S')}",
            reply_markup=None
        )
        
        # Отправляем уведомление клиенту
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 Отличные новости, {user_name}!\n\n"
                     f"✅ Ваша запись на {booking_data['date']} в {booking_data['time']} "
                     f"на услугу '{booking_data['service']}' ПОДТВЕРЖДЕНА мастером!\n\n"
                     f"Ждем вас в салоне! 💅\n\n"
                     f"📍 Адрес: ул. Красивых ногтей, д. 10\n"
                     f"📞 Тел: +7 (999) 123-45-67"
            )
            print(f"✅ Клиенту {user_id} отправлено уведомление о подтверждении")
        except Exception as e:
            print(f"⚠️ Не удалось отправить уведомление клиенту: {e}")
        
    elif action == 'reject':
        # Отклонение записи мастером
        status = 'отклонено мастером'
        await query.edit_message_text(
            f"❌ Запись отклонена мастером\n\n"
            f"👤 Клиент: {booking_data['name']}\n"
            f"📱 Телефон: {booking_data['phone']}\n"
            f"📅 Дата: {booking_data['date']}\n"
            f"⏰ Время: {booking_data['time']}\n"
            f"💅 Услуга: {booking_data['service']}\n\n"
            f"⏱️ Отклонено в: {query.message.date.strftime('%Y-%m-%d %H:%M:%S')}",
            reply_markup=None
        )
        
        # Отправляем уведомление клиенту
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ К сожалению, {user_name}...\n\n"
                     f"Ваша запись на {booking_data['date']} в {booking_data['time']} "
                     f"на услугу '{booking_data['service']}' была ОТКЛОНЕНА мастером.\n\n"
                     f"Пожалуйста, выберите другое время или свяжитесь с нами для уточнения.\n\n"
                     f"📞 Тел: +7 (999) 123-45-67\n"
                     f"✉️ Email: support@manicure.ru"
            )
            print(f"✅ Клиенту {user_id} отправлено уведомление об отклонении")
        except Exception as e:
            print(f"⚠️ Не удалось отправить уведомление клиенту: {e}")
    
    # Обновляем статус в Google Sheets или CSV
    try:
        from google_sheets import GoogleSheets
        google_sheets = GoogleSheets()
        google_sheets.add_status(booking_data, status)
    except:
        from simple_csv import SimpleCSVManager
        csv_manager = SimpleCSVManager()
        csv_manager.add_status(booking_data, status)
    
    # Удаляем запись из хранилища
    if booking_id in all_bookings:
        del all_bookings[booking_id]
        with open(storage_file, 'w', encoding='utf-8') as f:
            json.dump(all_bookings, f, ensure_ascii=False, indent=2)
        print(f"🗑️ Запись удалена из хранилища: {booking_id}")

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
        entry_points=[
            CommandHandler('book', booking_handlers.book),
            MessageHandler(filters.Regex('^(📝 Записаться на маникюр)$'), booking_handlers.book)
        ],
        states={
            NAME: [
                MessageHandler(filters.Regex('^(Использовать имя из профиля Telegram|Ввести другое имя)$'), 
                              booking_handlers.get_name),
                MessageHandler(filters.TEXT & ~filters.COMMAND, booking_handlers.handle_name_text)
            ],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_handlers.get_phone)],
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
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", booking_handlers.start))
    application.add_handler(conv_handler)
    
    # Добавляем обработчик callback-кнопок мастера
    application.add_handler(CallbackQueryHandler(
        handle_master_callback,
        pattern="^(confirm|reject)_"
    ))
    
    # Обработчик главного меню (сообщения без команд)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        booking_handlers.handle_main_menu
    ))
    
    # Обработчик неизвестных команд
    application.add_handler(MessageHandler(
        filters.COMMAND, 
        booking_handlers.handle_unknown
    ))
    
    # Запускаем бота
    print("✅ Бот запущен!")
    print("ℹ️ Для остановки нажмите Ctrl+C")
    print("📱 Перейдите в Telegram и найдите вашего бота")
    print("👑 Мастер получит уведомления с кнопками подтверждения")
    application.run_polling()

if __name__ == '__main__':
    main()