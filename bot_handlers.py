from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta
import re
import json
import os

# Определяем состояния для ConversationHandler
NAME, PHONE, DATE, TIME, SERVICE, CONFIRM, CANCEL_SELECT, CANCEL_CONFIRM = range(8)

class BookingHandlers:
    def __init__(self, google_sheets, notification_manager):
        self.google_sheets = google_sheets
        self.notification_manager = notification_manager
        self.users_file = 'users_phones.json'
        self._ensure_users_file()
    
    def _ensure_users_file(self):
        """Создает файл для хранения телефонов пользователей если его нет"""
        if not os.path.exists(self.users_file):
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
    
    def _save_user_phone(self, user_id, phone):
        """Сохраняет телефон пользователя"""
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
            
            users_data[str(user_id)] = {
                'phone': phone,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(users_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Телефон сохранен для пользователя {user_id}")
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения телефона: {e}")
            return False
    
    def _get_user_phone(self, user_id):
        """Получает сохраненный телефон пользователя"""
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
            
            user_data = users_data.get(str(user_id))
            if user_data:
                return user_data.get('phone')
            return None
        except Exception as e:
            print(f"❌ Ошибка получения телефона: {e}")
            return None
    
    def _get_main_menu(self):
        """Создает главное меню"""
        keyboard = [
            ['📝 Записаться на маникюр'],
            ['📅 Мои записи', 'ℹ️ О нас'],
            ['📞 Контакты', '👨‍💻 Поддержка']
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    def _get_date_keyboard(self):
        """Создает клавиатуру с датами на 5 дней вперед"""
        keyboard = []
        row = []
        
        # Текущая дата
        today = datetime.now()
        
        # Добавляем даты со следующего дня
        for i in range(1, 6):  # 5 дней вперед
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
           (phone_clean.startswith('7') and len(phone_clean) == 11):
            return True
        return False
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        
        if full_name:
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
        """Обработчик главного меню"""
        text = update.message.text
        
        if text == '📝 Записаться на маникюр':
            # Начинаем процесс записи
            return await self.book(update, context)
        elif text == '📅 Мои записи':
            return await self.view_bookings(update, context)
        elif text == 'ℹ️ О нас':
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
    
    async def view_bookings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает записи пользователя с кнопками отмены"""
        user_id = update.effective_user.id
        
        try:
            # Пытаемся получить записи из Google Sheets
            all_bookings = self.google_sheets.get_all_bookings()
            
            user_bookings = []
            for i, record in enumerate(all_bookings):
                if i == 0:  # Пропускаем заголовки
                    continue
                
                if len(record) >= 7:  # Проверяем наличие колонки Telegram ID
                    record_user_id = record[6] if record[6] else ''
                    record_status = record[8] if len(record) > 8 else 'ожидает'
                    
                    # Показываем только активные записи (ожидает, подтверждено)
                    if record_user_id == str(user_id) and record_status in ['ожидает', 'подтверждено']:
                        user_bookings.append({
                            'row_index': i,  # Сохраняем индекс строки
                            'date': record[3] if len(record) > 3 else '',
                            'time': record[4] if len(record) > 4 else '',
                            'service': record[5] if len(record) > 5 else '',
                            'status': record_status
                        })
            
            if user_bookings:
                # Сохраняем записи в контексте для отмены
                context.user_data['my_bookings'] = user_bookings
                
                message = "📅 Ваши активные записи:\n\n"
                keyboard = []
                
                for i, booking in enumerate(user_bookings, 1):
                    status_emoji = {
                        'ожидает': '⏳',
                        'подтверждено': '✅'
                    }.get(booking['status'], '📌')
                    
                    # Форматируем запись
                    message += f"{i}. {status_emoji} {booking['date']} в {booking['time']}\n"
                    message += f"   Услуга: {booking['service']}\n"
                    message += f"   Статус: {booking['status']}\n\n"
                    
                    # Добавляем кнопки для каждой записи
                    btn_text = f"❌ Отменить запись {i}"
                    keyboard.append([btn_text])
                
                # Добавляем кнопку возврата
                keyboard.append(['🔙 Назад в меню'])
                
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
                
                message += "Выберите запись для отмены или вернитесь в меню:"
                await update.message.reply_text(message, reply_markup=reply_markup)
                
                return CANCEL_SELECT
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
        
        # Проверяем, выбрана ли запись для отмены
        if '❌ Отменить запись' in user_input:
            # Извлекаем номер записи из текста кнопки
            try:
                booking_number = int(user_input.split(' ')[-1])
                user_bookings = context.user_data.get('my_bookings', [])
                
                if 1 <= booking_number <= len(user_bookings):
                    selected_booking = user_bookings[booking_number - 1]
                    
                    # Сохраняем выбранную запись для подтверждения
                    context.user_data['booking_to_cancel'] = selected_booking
                    context.user_data['booking_number'] = booking_number
                    
                    # Формируем сообщение для подтверждения
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
                    return CANCEL_CONFIRM
                    
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
                    # Получаем все записи
                    all_bookings = self.google_sheets.get_all_bookings()
                    
                    # Находим полную запись по данным
                    row_index = booking_to_cancel['row_index']
                    
                    if row_index < len(all_bookings):
                        record = all_bookings[row_index]
                        
                        # Создаем данные для обновления статуса
                        booking_data = {
                            'name': record[1] if len(record) > 1 else '',
                            'date': record[3] if len(record) > 3 else '',
                            'time': record[4] if len(record) > 4 else '',
                            'service': record[5] if len(record) > 5 else '',
                            'phone': record[2] if len(record) > 2 else ''
                        }
                        
                        # Обновляем статус в Google Sheets
                        success = self.google_sheets.add_status(booking_data, 'отменено')
                        
                        if success:
                            # Уведомляем мастера об отмене
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
                        
                    else:
                        message = "❌ Запись не найдена. Возможно, она уже была отменена."
                        
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
        
        # Очищаем временные данные
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
            from config import MASTER_CHAT_ID
            
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
            
            await self.notification_manager.bot.send_message(
                chat_id=MASTER_CHAT_ID,
                text=message
            )
            
            print(f"✅ Мастер уведомлен об отмене записи")
            
        except Exception as e:
            print(f"❌ Ошибка уведомления мастера об отмене: {e}")
    
    async def book(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает процесс записи"""
        # Получаем имя пользователя из профиля Telegram
        user = update.effective_user
        first_name = user.first_name or ""
        
        if first_name:
            greeting = f"{first_name}, давайте начнем запись!"
        else:
            greeting = "Давайте начнем запись!"
        
        # Предлагаем использовать имя из профиля или ввести своё
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
        
        # Сохраняем имя из профиля для возможного использования
        if first_name:
            context.user_data['profile_name'] = first_name
        
        return NAME
    
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
                # Если имени нет в профиле, просим ввести
                await update.message.reply_text(
                    "😕 Не удалось получить имя из профиля.\n"
                    "Пожалуйста, введите ваше имя:",
                    reply_markup=ReplyKeyboardRemove()
                )
                return NAME
        elif user_choice == 'Ввести другое имя':
            await update.message.reply_text(
                "✏️ Введите ваше имя:",
                reply_markup=ReplyKeyboardRemove()
            )
            return NAME
        else:
            # Пользователь ввел имя напрямую
            context.user_data['name'] = update.message.text
        
        # Проверяем, есть ли сохраненный телефон у пользователя
        user_id = update.effective_user.id
        saved_phone = self._get_user_phone(user_id)
        
        if saved_phone:
            # Показываем сохраненный телефон и спрашиваем, нужно ли его изменить
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
            # Нет сохраненного телефона, просим ввести
            await update.message.reply_text(
                "📱 Введите ваш номер телефона:\n"
                "Например: +79123456789",
                reply_markup=ReplyKeyboardRemove()
            )
        
        return PHONE
    
    async def get_name_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем введенное имя"""
        context.user_data['name'] = update.message.text
        
        # Обращаемся по имени
        name = context.user_data['name']
        
        # Проверяем, есть ли сохраненный телефон у пользователя
        user_id = update.effective_user.id
        saved_phone = self._get_user_phone(user_id)
        
        if saved_phone:
            # Показываем сохраненный телефон и спрашиваем, нужно ли его изменить
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
            # Нет сохраненного телефона, просим ввести
            await update.message.reply_text(
                f"✅ Отлично, {name}!\n\n"
                "📱 Теперь введите ваш номер телефона:\n"
                "Например: +79123456789",
                reply_markup=ReplyKeyboardRemove()
            )
        
        return PHONE
    
    async def get_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем телефон и проверяем формат"""
        user_input = update.message.text
        
        # Проверяем, выбрал ли пользователь "Использовать сохраненный номер"
        if user_input.startswith('Использовать'):
            # Извлекаем телефон из текста кнопки
            phone_match = re.search(r'(\+?\d[\d\s\-\(\)]+)', user_input)
            if phone_match:
                phone = phone_match.group(1)
                if self._validate_phone(phone):
                    context.user_data['phone'] = phone
                    
                    # Сохраняем телефон пользователя
                    user_id = update.effective_user.id
                    self._save_user_phone(user_id, phone)
                    
                    name = context.user_data.get('name', '')
                    formatted_phone = self._format_phone(phone)
                    
                    await update.message.reply_text(
                        f"✅ Отлично, {name}!\n"
                        f"Ваш номер: {formatted_phone}\n\n"
                        f"📅 Теперь выберите дату визита:\n"
                        f"Доступные даты на ближайшие 5 дней:",
                        reply_markup=self._get_date_keyboard()
                    )
                    return DATE
                else:
                    await update.message.reply_text(
                        "❌ Неверный формат телефона в сохраненных данных.\n"
                        "Пожалуйста, введите номер вручную:"
                    )
                    return PHONE
            else:
                await update.message.reply_text(
                    "❌ Не удалось извлечь номер телефона.\n"
                    "Пожалуйста, введите номер вручную:"
                )
                return PHONE
        
        # Пользователь вводит телефон вручную
        phone = user_input
        
        # Проверяем валидность телефона
        if self._validate_phone(phone):
            context.user_data['phone'] = phone
            
            # Сохраняем телефон пользователя
            user_id = update.effective_user.id
            self._save_user_phone(user_id, phone)
            
            # Форматируем номер для красивого отображения
            formatted_phone = self._format_phone(phone)
            
            name = context.user_data.get('name', '')
            
            await update.message.reply_text(
                f"✅ Отлично, {name}!\n"
                f"Ваш номер: {formatted_phone}\n\n"
                f"📅 Теперь выберите дату визита:\n"
                f"Доступные даты на ближайшие 5 дней:",
                reply_markup=self._get_date_keyboard()
            )
            return DATE
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
            return PHONE
    
    async def get_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем дату через кнопки или текстом"""
        user_input = update.message.text
        
        # Если пользователь выбрал "Ввести другую дату"
        if user_input == '📅 Ввести другую дату':
            await update.message.reply_text(
                "📝 Введите дату вручную в формате ДД.ММ.ГГГГ\n"
                "Например: 25.12.2024\n\n"
                "⚠️ Дата должна быть не ранее завтрашнего дня\n"
                "и не позднее чем через 30 дней.",
                reply_markup=ReplyKeyboardRemove()
            )
            return DATE
        
        # Проверяем, является ли ввод датой с кнопки (формат: ДД.ММ.ГГГГ (День))
        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', user_input)
        
        if date_match:
            # Извлекаем чистую дату из строки с кнопки
            date_str = date_match.group(1)
            
            # Проверяем валидность даты
            if self._is_valid_date(date_str):
                context.user_data['date'] = date_str
                
                # Предлагаем выбрать время
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
                return TIME
            else:
                await update.message.reply_text(
                    "❌ Выбрана некорректная дата.\n"
                    "Дата должна быть не ранее завтрашнего дня.\n\n"
                    "Пожалуйста, выберите дату из списка:",
                    reply_markup=self._get_date_keyboard()
                )
                return DATE
        else:
            # Пользователь ввел дату вручную
            date_str = user_input.strip()
            
            # Проверяем формат даты
            try:
                datetime.strptime(date_str, '%d.%m.%Y')
                
                # Проверяем валидность даты
                if self._is_valid_date(date_str):
                    context.user_data['date'] = date_str
                    
                    # Предлагаем выбрать время
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
                    return TIME
                else:
                    await update.message.reply_text(
                        "❌ Некорректная дата!\n"
                        "Дата должна быть:\n"
                        "✅ Не ранее завтрашнего дня\n"
                        "✅ Не позднее чем через 30 дней\n\n"
                        "Пожалуйста, введите дату в формате ДД.ММ.ГГГГ:"
                    )
                    return DATE
                    
            except ValueError:
                await update.message.reply_text(
                    "❌ Неверный формат даты!\n"
                    "Пожалуйста, введите дату в формате ДД.ММ.ГГГГ\n"
                    "Например: 25.12.2024\n\n"
                    "Или выберите из предложенных вариантов:",
                    reply_markup=self._get_date_keyboard()
                )
                return DATE
    
    async def get_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем время"""
        context.user_data['time'] = update.message.text
        
        # Предлагаем выбрать услугу
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
        return SERVICE
    
    async def get_service(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем услугу и показываем подтверждение"""
        context.user_data['service'] = update.message.text
        
        # Формируем текст для подтверждения
        name = context.user_data.get('name', '')
        phone = context.user_data.get('phone', '')
        date = context.user_data.get('date', '')
        time = context.user_data.get('time', '')
        service = context.user_data.get('service', '')
        
        # Форматируем телефон для красивого отображения
        formatted_phone = self._format_phone(phone)
        
        # Получаем день недели для красивого отображения
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
        return CONFIRM
    
    async def confirm_booking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение и сохранение записи"""
        if 'Да' in update.message.text:
            # Сохраняем запись
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
            
            # Добавляем в Google Sheets или CSV
            self.google_sheets.add_booking(booking_data)
            
            # Отправляем уведомление мастеру
            await self.notification_manager.notify_master(booking_data, update.effective_user)
            
            # Убеждаемся, что телефон сохранен
            user_id = update.effective_user.id
            self._save_user_phone(user_id, context.user_data['phone'])
            
            name = context.user_data.get('name', '')
            await update.message.reply_text(
                f"🎉 {name}, запись успешно сохранена!\n\n"
                "✅ Мастер получил уведомление о вашей записи.\n"
                "⏳ Ожидайте подтверждения в течение часа.\n"
                "📱 Мы сообщим вам о решении мастера.\n\n"
                "✅ Ваш номер телефона сохранен для будущих записей.\n\n"
                "Вы можете записаться снова через главное меню.",
                reply_markup=self._get_main_menu()
            )
        else:
            # Предлагаем начать заново
            await update.message.reply_text(
                "Давайте начнем запись заново.",
                reply_markup=self._get_main_menu()
            )
        
        # Очищаем данные пользователя
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
    
    async def handle_name_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает введенное имя напрямую"""
        return await self.get_name_input(update, context)