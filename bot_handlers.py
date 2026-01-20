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
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        welcome_text = """
        👋 Привет! Я бот для записи на маникюр!
        
        Чтобы записаться, нажмите /book
        Для отмены записи нажмите /cancel
        """
        await update.message.reply_text(welcome_text)
        return ConversationHandler.END
    
    async def book(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает процесс записи"""
        await update.message.reply_text(
            "📝 Давайте начнем запись!\n"
            "Как вас зовут?",
            reply_markup=ReplyKeyboardRemove()
        )
        return NAME
    
    async def get_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем имя клиента"""
        context.user_data['name'] = update.message.text
        await update.message.reply_text(
            "📱 Введите ваш номер телефона:\n"
            "Например: +79123456789"
        )
        return PHONE
    
    async def get_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем телефон и проверяем формат"""
        phone = update.message.text
        
        # Простая проверка номера телефона
        if not re.match(r'^(\+7|8)\d{10}$', phone.replace(' ', '')):
            await update.message.reply_text(
                "❌ Неверный формат телефона.\n"
                "Пожалуйста, введите номер в формате:\n"
                "+79123456789 или 89123456789"
            )
            return PHONE
        
        context.user_data['phone'] = phone
        
        # Предлагаем выбрать дату (здесь можно сделать календарь, но для MVP просто текстом)
        today = datetime.now().strftime('%d.%m.%Y')
        await update.message.reply_text(
            "📅 На какую дату хотите записаться?\n"
            f"Например: {today}"
        )
        return DATE
    
    async def get_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем дату"""
        context.user_data['date'] = update.message.text
        
        # Предлагаем выбрать время
        keyboard = [
            ['10:00', '12:00', '14:00'],
            ['16:00', '18:00', '20:00']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        
        await update.message.reply_text(
            "⏰ Выберите удобное время:",
            reply_markup=reply_markup
        )
        return TIME
    
    async def get_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем время"""
        context.user_data['time'] = update.message.text
        
        # Предлагаем выбрать услугу
        keyboard = [
            ['Маникюр', 'Педикюр'],
            ['Маникюр + покрытие', 'Педикюр + покрытие'],
            ['Наращивание', 'Дизайн ногтей']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        
        await update.message.reply_text(
            "💅 Выберите услугу:",
            reply_markup=reply_markup
        )
        return SERVICE
    
    async def get_service(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получаем услугу и показываем подтверждение"""
        context.user_data['service'] = update.message.text
        
        # Формируем текст для подтверждения
        booking_info = f"""
        📋 Проверьте вашу запись:
        
        👤 Имя: {context.user_data['name']}
        📱 Телефон: {context.user_data['phone']}
        📅 Дата: {context.user_data['date']}
        ⏰ Время: {context.user_data['time']}
        💅 Услуга: {context.user_data['service']}
        
        Всё верно?
        """
        
        keyboard = [['✅ Да', '❌ Нет']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        
        await update.message.reply_text(
            booking_info,
            reply_markup=reply_markup
        )
        return CONFIRM
    
    async def confirm_booking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение и сохранение записи"""
        if update.message.text == '✅ Да':
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
            
            await update.message.reply_text(
                "🎉 Запись успешно сохранена!\n"
                "Мы с вами свяжемся для подтверждения.\n"
                "Для новой записи нажмите /book",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await update.message.reply_text(
                "❌ Запись отменена.\n"
                "Чтобы начать заново, нажмите /book",
                reply_markup=ReplyKeyboardRemove()
            )
        
        # Очищаем данные пользователя
        context.user_data.clear()
        return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена записи"""
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Запись отменена.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END