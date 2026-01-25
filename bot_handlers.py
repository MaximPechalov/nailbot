from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta
import re
from config import MASTER_CHAT_ID

class BookingHandlers:
    def __init__(self, storage_manager, notification_service):
        self.storage = storage_manager
        self.notifications = notification_service
    
    def _get_main_menu(self):
        """Создает главное меню"""
        keyboard = [
            ['📝 Записаться на маникюр'],
            ['📅 Мои записи', '🔄 Перенести запись'],
            ['ℹ️ О нас', '📞 Контакты'],
            ['👨‍💻 Поддержка']
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    def _get_date_keyboard(self, start_day=1, days=5):
        """Создает клавиатуру с датами на указанное количество дней вперед"""
        keyboard = []
        row = []
        
        # Текущая дата
        today = datetime.now()
        
        # Добавляем даты
        for i in range(start_day, start_day + days):
            date = today + timedelta(days=i)
            date_str = date.strftime('%d.%m.%Y')
            
            # Форматируем красиво
            day_name = self._get_day_name(date.weekday())
            date_display = f"{date_str} ({day_name})"
            
            row.append(date_display)
            
            # Каждые 2 даты в строку
            if len(row) == 2:
                keyboard.append(row)
                row = []
        
        # Добавляем последнюю строку если есть остаток
        if row:
            keyboard.append(row)
        
        # Добавляем кнопку для ввода другой даты
        keyboard.append(['📅 Ввести другую дату'])
        
        return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    def _get_day_name(self, weekday):
        """Возвращает русское название дня недели"""
        days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        return days[weekday]
    
    def _is_valid_date(self, date_str):
        """Проверяет, корректна ли дата и не в прошлом"""
        try:
            # Парсим дату
            date_obj = datetime.strptime(date_str, '%d.%m.%Y')
            
            # Проверяем, что дата не в прошлом
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if date_obj < today:
                return False
            
            # Проверяем, что дата не дальше чем через 30 дней
            max_date = today + timedelta(days=30)
            if date_obj > max_date:
                return False
            
            return True
            
        except ValueError:
            return False
    
    def _format_phone(self, phone):
        """Форматирует телефон для красивого отображения"""
        phone_clean = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        if phone_clean.startswith('+7') and len(phone_clean) == 12:
            return f"+7 ({phone_clean[2:5]}) {phone_clean[5:8]}-{phone_clean[8:10]}-{phone_clean[10:12]}"
        elif phone_clean.startswith('8') and len(phone_clean) == 11:
            return f"8 ({phone_clean[1:4]}) {phone_clean[4:7]}-{phone_clean[7:9]}-{phone_clean[9:11]}"
        elif phone_clean.startswith('7') and len(phone_clean) == 11:
            return f"+7 ({phone_clean[1:4]}) {phone_clean[4:7]}-{phone_clean[7:9]}-{phone_clean[9:11]}"
        else:
            return phone
    
    def _validate_phone(self, phone):
        """Проверяет валидность номера телефона"""
        phone_clean = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Проверяем российские форматы
        if (phone_clean.startswith('+7') and len(phone_clean) == 12) or \
           (phone_clean.startswith('8') and len(phone_clean) == 11) or \
           (phone_clean.startswith('7') and len(phone_clean) == 11) or \
           (phone_clean.startswith('9') and len(phone_clean) == 10):
            return True
        return False
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        first_name = user.first_name or ""
        
        if first_name:
            welcome_text = f"""
👋 Привет, {first_name}! Я бот для записи на маникюр!

Выберите действие из меню ниже ⬇️
"""
        else:
            welcome_text = """
👋 Привет! Я бот для записи на маникюр!

Выберите действие из меню ниже ⬇️
"""
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=self._get_main_menu()
        )
        return ConversationHandler.END
    
    async def handle_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик главного меню (только информационные кнопки)"""
        text = update.message.text
        
        if text == 'ℹ️ О нас':
            await update.message.reply_text(
                "💅 Салон маникюра 'Лаковые нежности'\n\n"
                "🕒 Режим работы: 10:00 - 22:00\n"
                "📍 Адрес: ул. Красивых ногтей, д. 10\n\n"
                "Мы делаем ваши ногти красивыми!",
                reply_markup=self._get_main_menu()
            )
        elif text == '📞 Контакты':
            await update.message.reply_text(
                "📞 Наши контакты:\n\n"
                "☎️ Телефон: +7 (999) 123-45-67\n"
                "📍 Адрес: ул. Красивых ногтей, д. 10\n"
                "🕒 Часы работы: 10:00 - 22:00\n\n"
                "📱 Instagram: @manicure_beauty\n"
                "📸 VK: vk.com/manicure_beauty",
                reply_markup=self._get_main_menu()
            )
        elif text == '👨‍💻 Поддержка':
            await update.message.reply_text(
                "Если у вас возникли проблемы с записью:\n\n"
                "📱 Напишите нам: @manicure_support\n"
                "☎️ Позвоните: +7 (999) 123-45-67\n"
                "✉️ Email: support@manicure.ru",
                reply_markup=self._get_main_menu()
            )
        else:
            await update.message.reply_text(
                "Пожалуйста, используйте меню ниже ⬇️",
                reply_markup=self._get_main_menu()
            )
        
        return ConversationHandler.END
    
    async def start_reschedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает процесс переноса записи"""
        user_id = update.effective_user.id
        
        try:
            user_bookings = self.storage.get_user_bookings(
                user_id, 
                status_filter=['подтверждено', 'ожидает']
            )
            
            if not user_bookings:
                await update.message.reply_text(
                    "📭 У вас нет активных записей для переноса.\n"
                    "Перенести можно только записи со статусом 'ожидает' или 'подтверждено'.",
                    reply_markup=self._get_main_menu()
                )
                return ConversationHandler.END
            
            context.user_data['my_bookings'] = user_bookings
            
            message = "📅 Выберите запись для переноса:\n\n"
            keyboard = []
            
            for i, booking in enumerate(user_bookings, 1):
                status_emoji = {
                    'ожидает': '⏳',
                    'подтверждено': '✅'
                }.get(booking['status'], '📌')
                
                message += f"{i}. {status_emoji} {booking['date']} в {booking['time']}\n"
                message += f"   Услуга: {booking['service']}\n"
                message += f"   Статус: {booking['status']}\n\n"
                
                btn_text = f"🔄 Перенести запись {i}"
                keyboard.append([btn_text])
            
            keyboard.append(['🔙 Назад в меню'])
            
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            message += "Выберите запись для переноса или вернитесь в меню:"
            
            await update.message.reply_text(message, reply_markup=reply_markup)
            return 8  # RESCHEDULE_SELECT
            
        except Exception as e:
            print(f"❌ Ошибка при получении записей для переноса: {e}")
            await update.message.reply_text(
                "⚠️ Не удалось получить список записей. Попробуйте позже.",
                reply_markup=self._get_main_menu()
            )
            return ConversationHandler.END
    
    async def select_booking_to_reschedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор записи для переноса"""
        user_input = update.message.text
        
        if user_input == '🔙 Назад в меню':
            await update.message.reply_text(
                "Возвращаюсь в главное меню...",
                reply_markup=self._get_main_menu()
            )
            return ConversationHandler.END
        
        if '🔄 Перенести запись' in user_input:
            try:
                booking_number = int(user_input.split(' ')[-1])
                user_bookings = context.user_data.get('my_bookings', [])
                
                if 1 <= booking_number <= len(user_bookings):
                    selected_booking = user_bookings[booking_number - 1]
                    
                    context.user_data['booking_to_reschedule'] = selected_booking
                    context.user_data['booking_number'] = booking_number
                    
                    message = f"""
📝 Вы выбрали запись для переноса:

📅 Текущая дата: {selected_booking['date']}
⏰ Текущее время: {selected_booking['time']}
💅 Услуга: {selected_booking['service']}
📊 Статус: {selected_booking['status']}

Теперь выберите новую дату для записи:
"""
                    await update.message.reply_text(
                        message,
                        reply_markup=self._get_date_keyboard()
                    )
                    return 9  # RESCHEDULE_DATE
                    
            except (ValueError, IndexError) as e:
                print(f"❌ Ошибка обработки выбора записи: {e}")
        
        await update.message.reply_text(
            "Пожалуйста, выберите запись из списка:",
            reply_markup=self._get_main_menu()
        )
        return ConversationHandler.END
    
    async def get_reschedule_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получает новую дату для переноса"""
        user_input = update.message.text
        
        if user_input == '📅 Ввести другую дату':
            await update.message.reply_text(
                "📝 Введите новую дату в формате ДД.ММ.ГГГГ\n"
                "Например: 25.12.2024\n\n"
                "⚠️ Дата должна быть не ранее завтрашнего дня\n"
                "и не позднее чем через 30 дней.",
                reply_markup=ReplyKeyboardRemove()
            )
            return 9  # RESCHEDULE_DATE
        
        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', user_input)
        
        if date_match:
            date_str = date_match.group(1)
        else:
            date_str = user_input.strip()
        
        try:
            datetime.strptime(date_str, '%d.%m.%Y')
            
            if not self._is_valid_date(date_str):
                await update.message.reply_text(
                    "❌ Некорректная дата!\n"
                    "Дата должна быть:\n"
                    "✅ Не ранее завтрашнего дня\n"
                    "✅ Не позднее чем через 30 дней\n\n"
                    "Пожалуйста, выберите дату из списка:",
                    reply_markup=self._get_date_keyboard()
                )
                return 9
                
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты!\n"
                "Пожалуйста, введите дату в формате ДД.ММ.ГГГГ\n"
                "Например: 25.12.2024\n\n"
                "Или выберите из предложенных вариантов:",
                reply_markup=self._get_date_keyboard()
            )
            return 9
        
        context.user_data['new_date'] = date_str
        
        keyboard = [
            ['10:00', '11:00', '12:00'],
            ['13:00', '14:00', '15:00'],
            ['16:00', '17:00', '18:00'],
            ['19:00', '20:00', '21:00']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "⏰ Выберите новое время для записи:",
            reply_markup=reply_markup
        )
        return 10  # RESCHEDULE_TIME
    
    async def get_reschedule_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получает новое время для переноса"""
        context.user_data['new_time'] = update.message.text
        
        booking = context.user_data.get('booking_to_reschedule', {})
        new_date = context.user_data.get('new_date', '')
        new_time = context.user_data.get('new_time', '')
        
        try:
            date_obj = datetime.strptime(new_date, '%d.%m.%Y')
            day_name = self._get_day_name(date_obj.weekday())
            new_date_display = f"{new_date} ({day_name})"
        except:
            new_date_display = new_date
        
        message = f"""
📋 Проверьте детали переноса:

📅 ТЕКУЩАЯ запись:
Дата: {booking.get('date', '')}
Время: {booking.get('time', '')}
Услуга: {booking.get('service', '')}

🔄 НОВАЯ запись:
Дата: {new_date_display}
Время: {new_time}
Услуга: {booking.get('service', '')}

⚠️ После подтверждения:
• Будет создана новая запись со статусом "ожидает"
• Текущая запись перейдет в статус "перенос (ожидание мастера)"
• Мастер получит уведомление о запросе переноса
• После подтверждения мастера старая запись будет отменена

Всё верно?
"""
        
        keyboard = [['✅ Да, всё верно', '❌ Нет, отменить перенос']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        return 11  # RESCHEDULE_CONFIRM
    
    async def confirm_reschedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение переноса записи"""
        if 'Да' in update.message.text:
            booking = context.user_data.get('booking_to_reschedule', {})
            booking_id = booking.get('booking_id', '')
            new_date = context.user_data.get('new_date', '')
            new_time = context.user_data.get('new_time', '')
            
            if not booking_id:
                await update.message.reply_text(
                    "❌ Ошибка: данные записи не найдены.",
                    reply_markup=self._get_main_menu()
                )
                return ConversationHandler.END
            
            try:
                new_booking_data = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'name': booking.get('name', ''),
                    'phone': booking.get('phone', ''),
                    'date': new_date,
                    'time': new_time,
                    'service': booking.get('service', ''),
                    'telegram_id': update.effective_user.id,
                    'username': update.effective_user.username or '',
                    'status': 'перенос (ожидание мастера)',
                    'original_booking_id': booking_id
                }
                
                new_booking_id = self.storage.add_reschedule_request(
                    booking_id, 
                    new_booking_data
                )
                
                if new_booking_id:
                    await self.notifications.notify_master_reschedule_request(
                        booking, 
                        new_booking_data, 
                        update.effective_user,
                        new_booking_id
                    )
                    
                    message = f"""
✅ Запрос на перенос отправлен мастеру!

📅 Текущая запись: {booking.get('date')} в {booking.get('time')}
🔄 Новая запись: {new_date} в {new_time}
💅 Услуга: {booking.get('service')}

⏳ Ожидайте подтверждения мастера.
Мастер получил уведомление и скоро ответит.

Вы получите уведомление как только мастер примет решение.
"""
                else:
                    message = "❌ Не удалось создать запрос на перенос. Попробуйте позже."
                    
            except Exception as e:
                print(f"❌ Ошибка при переносе записи: {e}")
                message = "⚠️ Произошла ошибка при переносе записи. Попробуйте позже."
        else:
            message = "❌ Перенос записи отменен."
        
        await update.message.reply_text(
            message,
            reply_markup=self._get_main_menu()
        )
        
        for key in ['my_bookings', 'booking_to_reschedule', 'booking_number', 
                   'new_date', 'new_time']:
            if key in context.user_data:
                del context.user_data[key]
        
        return ConversationHandler.END
    
    async def view_bookings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает записи пользователя с кнопками отмены"""
        user_id = update.effective_user.id
        
        try:
            user_bookings = self.storage.get_user_bookings(
                user_id, 
                status_filter=['ожидает', 'подтверждено']
            )
            
            if user_bookings:
                context.user_data['my_bookings'] = user_bookings
                
                message = "📅 Ваши активные записи:\n\n"
                keyboard = []
                
                for i, booking in enumerate(user_bookings, 1):
                    status_emoji = {
                        'ожидает': '⏳',
                        'подтверждено': '✅'
                    }.get(booking['status'], '📌')
                    
                    message += f"{i}. {status_emoji} {booking['date']} в {booking['time']}\n"
                    message += f"   Услуга: {booking['service']}\n"
                    message += f"   Статус: {booking['status']}\n\n"
                    
                    btn_text = f"❌ Отменить запись {i}"
                    keyboard.append([btn_text])
                
                keyboard.append(['🔙 Назад в меню'])
                
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
                
                message += "Выберите запись для отмены или вернитесь в меню:"
                await update.message.reply_text(message, reply_markup=reply_markup)
                
                return 6  # CANCEL_SELECT
            else:
                await update.message.reply_text(
                    "📭 У вас пока нет активных записей.\n"
                    "Вы можете записаться через меню '📝 Записаться на маникюр'",
                    reply_markup=self._get_main_menu()
                )
                return ConversationHandler.END
            
        except Exception as e:
            print(f"❌ Ошибка при получении записей: {e}")
            await update.message.reply_text(
                "⚠️ Не удалось получить список записей. Попробуйте позже.",
                reply_markup=self._get_main_menu()
            )
            return ConversationHandler.END
    
    async def select_booking_to_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор записи для отмены"""
        user_input = update.message.text
        
        if user_input == '🔙 Назад в меню':
            await update.message.reply_text(
                "Возвращаюсь в главное меню...",
                reply_markup=self._get_main_menu()
            )
            return ConversationHandler.END
        
        if '❌ Отменить запись' in user_input:
            try:
                booking_number = int(user_input.split(' ')[-1])
                user_bookings = context.user_data.get('my_bookings', [])
                
                if 1 <= booking_number <= len(user_bookings):
                    selected_booking = user_bookings[booking_number - 1]
                    
                    context.user_data['booking_to_cancel'] = selected_booking
                    context.user_data['booking_number'] = booking_number
                    
                    message = f"""
⚠️ Вы действительно хотите отменить запись?

📅 Дата: {selected_booking['date']}
⏰ Время: {selected_booking['time']}
💅 Услуга: {selected_booking['service']}
📊 Статус: {selected_booking['status']}

⚠️ Отмена записи:
• Запись будет помечена как отмененная
• Время станет доступно для других клиентов
• Мастер получит уведомление об отмене
"""
                    
                    keyboard = [
                        ['✅ Да, отменить запись'],
                        ['❌ Нет, оставить запись']
                    ]
                    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
                    
                    await update.message.reply_text(message, reply_markup=reply_markup)
                    return 7  # CANCEL_CONFIRM
                    
            except (ValueError, IndexError) as e:
                print(f"❌ Ошибка обработки выбора записи: {e}")
        
        await update.message.reply_text(
            "Пожалуйста, выберите запись из списка ниже:",
            reply_markup=self._get_main_menu()
        )
        return ConversationHandler.END
    
    async def confirm_cancel_booking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение отмены записи"""
        if 'Да' in update.message.text:
            booking_to_cancel = context.user_data.get('booking_to_cancel')
            booking_number = context.user_data.get('booking_number')
            
            if booking_to_cancel:
                try:
                    success = self.storage.cancel_booking_by_id(booking_to_cancel['booking_id'])
                    
                    if success:
                        await self._notify_master_about_cancellation(
                            update, 
                            booking_to_cancel,
                            update.effective_user
                        )
                        
                        message = f"""
✅ Запись #{booking_number} успешно отменена!

📅 Дата: {booking_to_cancel['date']}
⏰ Время: {booking_to_cancel['time']}
💅 Услуга: {booking_to_cancel['service']}

Вы можете записаться на другое время через главное меню.
"""
                    else:
                        message = "⚠️ Не удалось отменить запись. Попробуйте позже или свяжитесь с мастером."
                        
                except Exception as e:
                    print(f"❌ Ошибка отмены записи: {e}")
                    message = "⚠️ Произошла ошибка при отмене записи. Попробуйте позже."
            else:
                message = "❌ Данные записи не найдены."
        else:
            message = "Отмена записи отменена. Возвращаюсь в главное меню."
        
        await update.message.reply_text(
            message,
            reply_markup=self._get_main_menu()
        )
        
        if 'my_bookings' in context.user_data:
            del context.user_data['my_bookings']
        if 'booking_to_cancel' in context.user_data:
            del context.user_data['booking_to_cancel']
        if 'booking_number' in context.user_data:
            del context.user_data['booking_number']
        
        return ConversationHandler.END
    
    async def _notify_master_about_cancellation(self, update: Update, booking_data: dict, user):
        """Отправляет уведомление мастеру об отмене записи"""
        try:
            message = f"""
🔔 ОТМЕНА ЗАПИСИ

👤 Клиент: {user.first_name or 'Неизвестный'}
📱 Telegram: @{user.username if user.username else 'не указан'}

📅 Была отменена запись:
Дата: {booking_data['date']}
Время: {booking_data['time']}
Услуга: {booking_data['service']}
Статус: {booking_data['status']}

⏱️ Отменено в: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            await self.notifications.bot.send_message(
                chat_id=MASTER_CHAT_ID,
                text=message
            )
            
            print(f"✅ Мастер уведомлен об отмене записи")
            
        except Exception as e:
            print(f"❌ Ошибка уведомления мастера об отмене: {e}")
    
    async def book(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает процесс записи"""
        user = update.effective_user
        first_name = user.first_name or ""
        
        if first_name:
            greeting = f"{first_name}, давайте начнем запись!"
        else:
            greeting = "Давайте начнем запись!"
        
        keyboard = [
            ['Использовать имя из профиля Telegram'],
            ['Ввести другое имя']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            f"{greeting}\n\n"
            "Как вас записать?",
            reply_markup=reply_markup
        )
        
        if first_name:
            context.user_data['profile_name'] = first_name
        
        return 0  # NAME
    
    async def get_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатываем выбор имени"""
        user_choice = update.message.text
        
        if user_choice == 'Использовать имя из профиля Telegram':
            profile_name = context.user_data.get('profile_name', '')
            if profile_name:
                context.user_data['name'] = profile_name
                await update.message.reply_text(
                    f"✅ Отлично, {profile_name}!",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                await update.message.reply_text(
                    "😕 Не удалось получить имя из профиля.\n"
                    "Пожалуйста, введите ваше имя:",
                    reply_markup=ReplyKeyboardRemove()
                )
                return 0  # NAME
        elif user_choice == 'Ввести другое имя':
            await update.message.reply_text(
                "✏️ Введите ваше имя:",
                reply_markup=ReplyKeyboardRemove()
            )
            return 0  # NAME
        else:
            context.user_data['name'] = update.message.text
        
        user_id = update.effective_user.id
        saved_phone = self.storage.get_user_phone(user_id)
        
        if saved_phone:
            formatted_phone = self._format_phone(saved_phone)
            keyboard = [
                [f'Использовать {formatted_phone}'],
                ['Ввести другой номер']
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            
            name = context.user_data.get('name', '')
            await update.message.reply_text(
                f"✅ Отлично, {name}!\n\n"
                f"📱 У вас есть сохраненный номер: {formatted_phone}\n"
                "Хотите использовать его или ввести новый?",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "📱 Введите ваш номер телефона:\n"
                "Например: +79123456789",
                reply_markup=ReplyKeyboardRemove()
            )
        
        return 1  # PHONE
    
    async def handle_name_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем введенное имя напрямую"""
        context.user_data['name'] = update.message.text
        
        name = context.user_data['name']
        
        user_id = update.effective_user.id
        saved_phone = self.storage.get_user_phone(user_id)
        
        if saved_phone:
            formatted_phone = self._format_phone(saved_phone)
            keyboard = [
                [f'Использовать {formatted_phone}'],
                ['Ввести другой номер']
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            
            await update.message.reply_text(
                f"✅ Отлично, {name}!\n\n"
                f"📱 У вас есть сохраненный номер: {formatted_phone}\n"
                "Хотите использовать его или ввести новый?",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                f"✅ Отлично, {name}!\n\n"
                "📱 Теперь введите ваш номер телефона:\n"
                "Например: +79123456789",
                reply_markup=ReplyKeyboardRemove()
            )
        
        return 1  # PHONE
    
    async def get_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем телефон и проверяем формат"""
        user_input = update.message.text
        
        if user_input.startswith('Использовать'):
            phone_match = re.search(r'(\+?\d[\d\s\-\(\)]+)', user_input)
            if phone_match:
                phone = phone_match.group(1)
                if self._validate_phone(phone):
                    context.user_data['phone'] = phone
                    
                    user_id = update.effective_user.id
                    self.storage.save_user_phone(user_id, phone)
                    
                    name = context.user_data.get('name', '')
                    formatted_phone = self._format_phone(phone)
                    
                    await update.message.reply_text(
                        f"✅ Отлично, {name}!\n"
                        f"Ваш номер: {formatted_phone}\n\n"
                        f"📅 Теперь выберите дату визита:\n"
                        f"Доступные даты на ближайшие 5 дней:",
                        reply_markup=self._get_date_keyboard()
                    )
                    return 2  # DATE
                else:
                    await update.message.reply_text(
                        "❌ Неверный формат телефона в сохраненных данных.\n"
                        "Пожалуйста, введите номер вручную:"
                    )
                    return 1  # PHONE
            else:
                await update.message.reply_text(
                    "❌ Не удалось извлечь номер телефона.\n"
                    "Пожалуйста, введите номер вручную:"
                )
                return 1  # PHONE
        
        phone = user_input
        
        if self._validate_phone(phone):
            context.user_data['phone'] = phone
            
            user_id = update.effective_user.id
            self.storage.save_user_phone(user_id, phone)
            
            formatted_phone = self._format_phone(phone)
            
            name = context.user_data.get('name', '')
            
            await update.message.reply_text(
                f"✅ Отлично, {name}!\n"
                f"Ваш номер: {formatted_phone}\n\n"
                f"📅 Теперь выберите дату визита:\n"
                f"Доступные даты на ближайшие 5 дней:",
                reply_markup=self._get_date_keyboard()
            )
            return 2  # DATE
        else:
            await update.message.reply_text(
                "❌ Неверный формат телефона.\n"
                "Пожалуйста, введите российский номер в формате:\n"
                "+79123456789 или 89123456789\n\n"
                "Примеры корректных номеров:\n"
                "+7 (912) 345-67-89\n"
                "89123456789\n"
                "+79123456789"
            )
            return 1  # PHONE
    
    async def get_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем дату через кнопки или текстом"""
        user_input = update.message.text
        
        if user_input == '📅 Ввести другую дату':
            await update.message.reply_text(
                "📝 Введите дату вручную в формате ДД.ММ.ГГГГ\n"
                "Например: 25.12.2024\n\n"
                "⚠️ Дата должна быть не ранее завтрашнего дня\n"
                "и не позднее чем через 30 дней.",
                reply_markup=ReplyKeyboardRemove()
            )
            return 2  # DATE
        
        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', user_input)
        
        if date_match:
            date_str = date_match.group(1)
            
            if self._is_valid_date(date_str):
                context.user_data['date'] = date_str
                
                keyboard = [
                    ['10:00', '11:00', '12:00'],
                    ['13:00', '14:00', '15:00'],
                    ['16:00', '17:00', '18:00'],
                    ['19:00', '20:00', '21:00']
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
                
                name = context.user_data.get('name', '')
                await update.message.reply_text(
                    f"⏰ {name}, выберите удобное время:",
                    reply_markup=reply_markup
                )
                return 3  # TIME
            else:
                await update.message.reply_text(
                    "❌ Выбрана некорректная дата.\n"
                    "Дата должна быть не ранее завтрашнего дня.\n\n"
                    "Пожалуйста, выберите дату из списка:",
                    reply_markup=self._get_date_keyboard()
                )
                return 2  # DATE
        else:
            date_str = user_input.strip()
            
            try:
                datetime.strptime(date_str, '%d.%m.%Y')
                
                if self._is_valid_date(date_str):
                    context.user_data['date'] = date_str
                    
                    keyboard = [
                        ['10:00', '11:00', '12:00'],
                        ['13:00', '14:00', '15:00'],
                        ['16:00', '17:00', '18:00'],
                        ['19:00', '20:00', '21:00']
                    ]
                    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
                    
                    name = context.user_data.get('name', '')
                    await update.message.reply_text(
                        f"⏰ {name}, выберите удобное время:",
                        reply_markup=reply_markup
                    )
                    return 3  # TIME
                else:
                    await update.message.reply_text(
                        "❌ Некорректная дата!\n"
                        "Дата должна быть:\n"
                        "✅ Не ранее завтрашнего дня\n"
                        "✅ Не позднее чем через 30 дней\n\n"
                        "Пожалуйста, введите дату в формате ДД.ММ.ГГГГ:"
                    )
                    return 2  # DATE
                    
            except ValueError:
                await update.message.reply_text(
                    "❌ Неверный формат дата!\n"
                    "Пожалуйста, введите дату в формате ДД.ММ.ГГГГ\n"
                    "Например: 25.12.2024\n\n"
                    "Или выберите из предложенных вариантов:",
                    reply_markup=self._get_date_keyboard()
                )
                return 2  # DATE
    
    async def get_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем время"""
        context.user_data['time'] = update.message.text
        
        keyboard = [
            ['💅 Классический маникюр - 1500₽'],
            ['✨ Маникюр + покрытие - 2500₽'],
            ['👠 Педикюр - 2000₽'],
            ['🎨 Дизайн ногтей - от 500₽'],
            ['💎 Наращивание ногтей - 3500₽']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        name = context.user_data.get('name', '')
        await update.message.reply_text(
            f"💅 {name}, выберите услугу:",
            reply_markup=reply_markup
        )
        return 4  # SERVICE
    
    async def get_service(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем услугу и показываем подтверждение"""
        context.user_data['service'] = update.message.text
        
        name = context.user_data.get('name', '')
        phone = context.user_data.get('phone', '')
        date = context.user_data.get('date', '')
        time = context.user_data.get('time', '')
        service = context.user_data.get('service', '')
        
        formatted_phone = self._format_phone(phone)
        
        try:
            date_obj = datetime.strptime(date, '%d.%m.%Y')
            day_name = self._get_day_name(date_obj.weekday())
            date_display = f"{date} ({day_name})"
        except:
            date_display = date
        
        booking_info = f"""
📋 {name}, проверьте вашу запись:

👤 Имя: {name}
📱 Телефон: {formatted_phone}
📅 Дата: {date_display}
⏰ Время: {time}
💅 Услуга: {service}

Всё верно?
"""
        
        keyboard = [['✅ Да, всё верно', '❌ Нет, исправить']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            booking_info,
            reply_markup=reply_markup
        )
        return 5  # CONFIRM
    
    async def confirm_booking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение и сохранение записи"""
        if 'Да' in update.message.text:
            booking_data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'name': context.user_data['name'],
                'phone': context.user_data['phone'],
                'date': context.user_data['date'],
                'time': context.user_data['time'],
                'service': context.user_data['service'],
                'telegram_id': update.effective_user.id,
                'username': update.effective_user.username or ''
            }
            
            booking_id = self.storage.add_booking(booking_data)
            
            await self.notifications.notify_master_new_booking({
                **booking_data,
                'booking_id': booking_id
            })
            
            user_id = update.effective_user.id
            self.storage.save_user_phone(user_id, context.user_data['phone'])
            
            name = context.user_data.get('name', '')
            await update.message.reply_text(
                f"🎉 {name}, запись успешно создана!\n\n"
                "✅ Мастер получил уведомление о вашей записи.\n"
                "⏳ Ожидайте подтверждения в течение часа.\n"
                "📱 Мы сообщим вам о решении мастера.\n\n"
                "✅ Ваш номер телефона сохранен для будущих записей.\n\n"
                "Вы можете записаться снова через главное меню.",
                reply_markup=self._get_main_menu()
            )
        else:
            await update.message.reply_text(
                "Давайте начнем запись заново.",
                reply_markup=self._get_main_menu()
            )
        
        context.user_data.clear()
        return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена записи"""
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Запись отменена.\n"
            "Вы можете начать заново через главное меню.",
            reply_markup=self._get_main_menu()
        )
        return ConversationHandler.END
    
    async def handle_unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик неизвестных команд"""
        await update.message.reply_text(
            "Извините, я не понимаю эту команду.\n"
            "Пожалуйста, используйте меню ниже ⬇️",
            reply_markup=self._get_main_menu()
        )