from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from config import TELEGRAM_BOT_TOKEN, MASTER_CHAT_ID
import json
import os
from datetime import datetime

async def handle_master_callback(update: Update, context):
    """Обработчик callback от мастера"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    print(f"📲 Получен callback от мастера: {data}")
    
    # Обработка действий с конкретной записью
    if data.startswith('confirm_') or data.startswith('reject_') or data.startswith('complete_'):
        if '_' in data:
            action, booking_id = data.split('_', 1)
            await handle_booking_action(update, context, action, booking_id)
    
    # Обработка меню мастера
    elif data.startswith('master_'):
        await handle_master_menu(update, context, data)
    
    else:
        print(f"❌ Неизвестный callback: {data}")

async def handle_booking_action(update: Update, context, action: str, booking_id: str):
    """Обрабатывает действие с записью"""
    storage_file = 'bookings_storage.json'
    if not os.path.exists(storage_file):
        await update.callback_query.edit_message_text("❌ Данные не найдены")
        return
    
    with open(storage_file, 'r', encoding='utf-8') as f:
        all_bookings = json.load(f)
    
    booking_data = all_bookings.get(booking_id)
    
    if not booking_data:
        await update.callback_query.edit_message_text("❌ Запись не найдена")
        return
    
    user_id = booking_data.get('user_id')
    user_name = booking_data.get('name', 'клиент')
    
    if action == 'confirm':
        status = 'подтверждено'
        status_text = "ПОДТВЕРЖДЕНА"
        message_to_master = f"✅ Запись подтверждена!"
        
        message_to_client = (
            f"🎉 Отличные новости, {user_name}!\n\n"
            f"✅ Ваша запись на {booking_data['date']} в {booking_data['time']} "
            f"на услугу '{booking_data['service']}' ПОДТВЕРЖДЕНА мастером!\n\n"
            f"Ждем вас в салоне! 💅\n\n"
            f"📍 Адрес: ул. Красивых ногтей, д. 10\n"
            f"📞 Тел: +7 (999) 123-45-67"
        )
        
    elif action == 'reject':
        status = 'отклонено мастером'
        status_text = "ОТКЛОНЕНА"
        message_to_master = f"❌ Запись отклонена мастером"
        
        message_to_client = (
            f"❌ К сожалению, {user_name}...\n\n"
            f"Ваша запись на {booking_data['date']} в {booking_data['time']} "
            f"на услугу '{booking_data['service']}' была ОТКЛОНЕНА мастером.\n\n"
            f"Пожалуйста, выберите другое время или свяжитесь с нами для уточнения.\n\n"
            f"📞 Тел: +7 (999) 123-45-67\n"
            f"✉️ Email: support@manicure.ru"
        )
        
    elif action == 'complete':
        status = 'выполнено'
        status_text = "ВЫПОЛНЕНА"
        message_to_master = f"✨ Запись отмечена как выполненная!"
        
        message_to_client = (
            f"✨ Спасибо за визит, {user_name}!\n\n"
            f"Ваша запись на {booking_data['date']} в {booking_data['time']} "
            f"на услугу '{booking_data['service']}' отмечена как ВЫПОЛНЕНА.\n\n"
            f"Будем рады видеть вас снова! 💅\n\n"
            f"📍 Напоминаем адрес: ул. Красивых ногтей, д. 10\n"
            f"📞 Тел: +7 (999) 123-45-67"
        )
    
    # Обновляем статус в хранилище
    booking_data['status'] = status
    booking_data['status_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    with open(storage_file, 'w', encoding='utf-8') as f:
        json.dump(all_bookings, f, ensure_ascii=False, indent=2)
    
    # Отправляем сообщение мастеру
    await update.callback_query.edit_message_text(
        f"{message_to_master}\n\n"
        f"👤 Клиент: {booking_data['name']}\n"
        f"📱 Телефон: {booking_data['phone']}\n"
        f"📅 Дата: {booking_data['date']}\n"
        f"⏰ Время: {booking_data['time']}\n"
        f"💅 Услуга: {booking_data['service']}\n\n"
        f"⏱️ {status_text} в: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=None
    )
    
    # Отправляем уведомление клиенту
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=message_to_client
        )
        print(f"✅ Клиенту {user_id} отправлено уведомление: {status}")
    except Exception as e:
        print(f"⚠️ Не удалось отправить уведомление клиенту {user_id}: {e}")
    
    # Обновляем статус в Google Sheets или CSV
    try:
        from google_sheets import GoogleSheets
        google_sheets = GoogleSheets()
        success = google_sheets.add_status(booking_data, status)
        if not success:
            print(f"⚠️ Не удалось обновить статус в Google Sheets")
    except Exception as e:
        print(f"⚠️ Google Sheets не доступен, используем CSV: {e}")
        try:
            from simple_csv import SimpleCSVManager
            csv_manager = SimpleCSVManager()
            success = csv_manager.add_status(booking_data, status)
            if not success:
                print(f"⚠️ Не удалось обновить статус в CSV")
        except Exception as csv_error:
            print(f"❌ Ошибка обновления статуса в CSV: {csv_error}")
    
    print(f"✅ Статус записи {booking_id} обновлен: {status}")

async def handle_master_menu(update: Update, context, menu_action: str):
    """Обрабатывает меню мастера"""
    try:
        from notifications import NotificationManager
        notification_manager = NotificationManager()
    except Exception as e:
        print(f"❌ Ошибка импорта NotificationManager: {e}")
        await update.callback_query.edit_message_text("❌ Ошибка системы. Попробуйте позже.")
        return
    
    if menu_action == 'master_active':
        # Активные записи (подтвержденные)
        active_bookings = notification_manager.get_bookings_by_status('подтверждено')
        
        if not active_bookings:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="master_back")]]
            await update.callback_query.edit_message_text(
                "📭 Нет активных записей (подтвержденных).",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        message = "📋 Активные записи (подтвержденные):\n\n"
        keyboard = []
        
        for i, (booking_id, booking) in enumerate(active_bookings.items(), 1):
            message += f"{i}. {booking.get('name', 'Неизвестно')} - {booking.get('date', '?')} {booking.get('time', '?')}\n"
            message += f"   📞 {booking.get('phone', 'Не указан')}\n"
            message += f"   💅 {booking.get('service', 'Не указано')}\n\n"
            
            # Кнопка для отметки как выполненной
            keyboard.append([
                InlineKeyboardButton(
                    f"✅ Выполнено #{i}", 
                    callback_data=f"complete_{booking_id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="master_back")])
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif menu_action == 'master_completed':
        # Выполненные записи
        completed_bookings = notification_manager.get_bookings_by_status('выполнено')
        
        if not completed_bookings:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="master_back")]]
            await update.callback_query.edit_message_text(
                "📭 Нет выполненных записей.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        message = "✅ Выполненные записи:\n\n"
        
        for i, (booking_id, booking) in enumerate(completed_bookings.items(), 1):
            message += f"{i}. {booking.get('name', 'Неизвестно')} - {booking.get('date', '?')} {booking.get('time', '?')}\n"
            message += f"   📞 {booking.get('phone', 'Не указан')}\n"
            message += f"   💅 {booking.get('service', 'Не указано')}\n"
            if booking.get('status_updated'):
                message += f"   ⏱️ Выполнено: {booking['status_updated']}\n"
            message += "\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="master_back")]]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif menu_action == 'master_pending':
        # Ожидающие подтверждения
        pending_bookings = notification_manager.get_bookings_by_status('ожидает')
        
        if not pending_bookings:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="master_back")]]
            await update.callback_query.edit_message_text(
                "📭 Нет записей, ожидающих подтверждения.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        message = "⏳ Записи, ожидающие подтверждения:\n\n"
        
        for i, (booking_id, booking) in enumerate(pending_bookings.items(), 1):
            message += f"{i}. {booking.get('name', 'Неизвестно')} - {booking.get('date', '?')} {booking.get('time', '?')}\n"
            message += f"   📞 {booking.get('phone', 'Не указан')}\n"
            message += f"   💅 {booking.get('service', 'Не указано')}\n"
            message += f"   ⏱️ Создана: {booking.get('timestamp', '?')}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="master_back")]]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif menu_action == 'master_stats':
        # Статистика
        stats = notification_manager.get_statistics()
        
        today = datetime.now().strftime('%Y-%m-%d')
        message = (
            f"📊 Статистика записей:\n\n"
            f"📈 Всего записей: {stats.get('total', 0)}\n"
            f"⏳ Ожидают подтверждения: {stats.get('pending', 0)}\n"
            f"✅ Подтвержденные: {stats.get('confirmed', 0)}\n"
            f"✨ Выполненные: {stats.get('completed', 0)}\n"
            f"❌ Отклоненные мастером: {stats.get('rejected', 0)}\n"
            f"⏸️ Отмененные: {stats.get('cancelled', 0)}\n\n"
            f"📅 Записи на сегодня ({today}): {stats.get('today', 0)}"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Обновить", callback_data="master_stats"),
                InlineKeyboardButton("🔙 Назад", callback_data="master_back")
            ]
        ]
        
        await update.callback_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif menu_action == 'master_back':
        # Возврат в главное меню мастера
        keyboard = [
            [
                InlineKeyboardButton("📋 Активные записи", callback_data="master_active"),
                InlineKeyboardButton("✅ Выполненные", callback_data="master_completed")
            ],
            [
                InlineKeyboardButton("⏳ Ожидают подтверждения", callback_data="master_pending"),
                InlineKeyboardButton("📊 Статистика", callback_data="master_stats")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "🎛️ Панель управления мастера\nВыберите действие:",
            reply_markup=reply_markup
        )
    
    else:
        await update.callback_query.edit_message_text(f"❌ Неизвестная команда меню: {menu_action}")

async def send_master_menu_command(update: Update, context):
    """Команда для отправки меню мастера"""
    if str(update.effective_chat.id) != MASTER_CHAT_ID:
        await update.message.reply_text("❌ Эта команда доступна только мастеру.")
        return
    
    try:
        from notifications import NotificationManager
        notification_manager = NotificationManager()
        await notification_manager.send_master_menu()
    except Exception as e:
        print(f"❌ Ошибка отправки меню мастера: {e}")
        await update.message.reply_text("❌ Ошибка при отправке меню.")

def main():
    """Запуск бота (синхронная версия)"""
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
    from bot_handlers import BookingHandlers, NAME, PHONE, DATE, TIME, SERVICE, CONFIRM, CANCEL_SELECT, CANCEL_CONFIRM
    
    notification_manager = NotificationManager()
    booking_handlers = BookingHandlers(google_sheets, notification_manager)
    
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Создаем ConversationHandler для записи
    conv_handler_booking = ConversationHandler(
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
    
    # Создаем ConversationHandler для отмены записей
    conv_handler_cancel = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(📅 Мои записи)$'), booking_handlers.view_bookings)
        ],
        states={
            CANCEL_SELECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, booking_handlers.select_booking_to_cancel)
            ],
            CANCEL_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, booking_handlers.confirm_cancel_booking)
            ],
        },
        fallbacks=[
            CommandHandler('cancel', booking_handlers.cancel),
            CommandHandler('start', booking_handlers.start),
            MessageHandler(filters.Regex('^🔙 Назад в меню$'), booking_handlers.start)
        ]
    )
    
    # Добавляем обработчики в правильном порядке
    # 1. Обработчик callback-кнопок мастера (должен быть ПЕРВЫМ!)
    application.add_handler(CallbackQueryHandler(
        handle_master_callback,
        pattern="^(confirm|reject|complete|master_)"
    ))
    
    # 2. Команда для меню мастера
    application.add_handler(CommandHandler("master", send_master_menu_command))
    
    # 3. ConversationHandler для отмены записей
    application.add_handler(conv_handler_cancel)
    
    # 4. ConversationHandler для записи на маникюр
    application.add_handler(conv_handler_booking)
    
    # 5. Обработчик команды /start
    application.add_handler(CommandHandler("start", booking_handlers.start))
    
    # 6. Обработчик главного меню
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        booking_handlers.handle_main_menu
    ))
    
    # 7. Обработчик неизвестных команд
    application.add_handler(MessageHandler(
        filters.COMMAND, 
        booking_handlers.handle_unknown
    ))
    
    # Запускаем бота
    print("✅ Бот запущен!")
    print("ℹ️ Для остановки нажмите Ctrl+C")
    print("📱 Перейдите в Telegram и найдите вашего бота")
    print("👑 Мастер получит уведомления о новых записях")
    print("💼 Команда /master - открыть панель управления")
    print("\n📋 Примечание: Мастер должен ввести команду /master в чате с ботом, чтобы получить меню управления")
    
    # Запускаем polling
    application.run_polling()

if __name__ == '__main__':
    main()