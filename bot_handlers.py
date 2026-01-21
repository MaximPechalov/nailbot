from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime
import re

# Определяем состояния для ConversationHandler
NAME, PHONE, DATE, TIME, SERVICE, CONFIRM = range(6)

class BookingHandlers:
    def __init__(self, google_sheets, notification_manager):
        self.google_sheets = google_sheets
        self.notification_manager = notification_manager
        
    def _get_main_menu(self):
        """Создает главное меню"""
        keyboard = [
            ['📝 Записаться на маникюр'],
            ['📅 Мои записи', 'ℹ️ О нас'],
            ['📞 Контакты', '👨‍💻 Поддержка']
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        # Получаем имя пользователя из профиля Telegram
        user = update.effective_user
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()
        
        # Если есть имя, используем его, иначе просим представиться
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
            await update.message.reply_text(
                "📅 Функция просмотра записей в разработке...\n"
                "Скоро вы сможете просматривать свои записи здесь!",
                reply_markup=self._get_main_menu()
            )
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
        
        # Переходим к следующему шагу - телефон
        await update.message.reply_text(
            "📱 Введите ваш номер телефона:\n"
            "Например: +79123456789"
        )
        return PHONE
    
    async def get_name_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем введенное имя"""
        context.user_data['name'] = update.message.text
        
        # Обращаемся по имени
        name = context.user_data['name']
        await update.message.reply_text(
            f"✅ Отлично, {name}!\n\n"
            "📱 Теперь введите ваш номер телефона:\n"
            "Например: +79123456789"
        )
        return PHONE
    
    async def get_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем телефон и проверяем формат"""
        phone = update.message.text
        
        # Простая проверка номера телефона
        phone_clean = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Проверяем российские форматы
        if (phone_clean.startswith('+7') and len(phone_clean) == 12) or \
           (phone_clean.startswith('8') and len(phone_clean) == 11) or \
           (phone_clean.startswith('7') and len(phone_clean) == 11):
            context.user_data['phone'] = phone
            
            # Форматируем номер для красивого отображения
            if phone_clean.startswith('+7'):
                formatted_phone = f"+7 ({phone_clean[2:5]}) {phone_clean[5:8]}-{phone_clean[8:10]}-{phone_clean[10:12]}"
            elif phone_clean.startswith('8'):
                formatted_phone = f"8 ({phone_clean[1:4]}) {phone_clean[4:7]}-{phone_clean[7:9]}-{phone_clean[9:11]}"
            else:
                formatted_phone = phone
            
            name = context.user_data.get('name', '')
            await update.message.reply_text(
                f"✅ Отлично, {name}!\n"
                f"Ваш номер: {formatted_phone}\n\n"
                "📅 Теперь выберите дату визита:\n"
                "Введите дату в формате ДД.ММ.ГГГГ\n"
                f"Например: {datetime.now().strftime('%d.%m.%Y')}"
            )
            return DATE
        else:
            await update.message.reply_text(
                "❌ Неверный формат телефона.\n"
                "Пожалуйста, введите российский номер в формате:\n"
                "+79123456789 или 89123456789"
            )
            return PHONE
    
    async def get_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем дату"""
        context.user_data['date'] = update.message.text
        
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
        
        booking_info = f"""
        📋 {name}, проверьте вашу запись:
        
        👤 Имя: {name}
        📱 Телефон: {phone}
        📅 Дата: {date}
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
            
            name = context.user_data.get('name', '')
            await update.message.reply_text(
                f"🎉 {name}, запись успешно сохранена!\n\n"
                "✅ Мастер получил уведомление о вашей записи.\n"
                "⏳ Ожидайте подтверждения в течение часа.\n"
                "📱 Мы сообщим вам о решении мастера.\n\n"
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