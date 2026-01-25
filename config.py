import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# Токен бота Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# ID Google таблицы
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')

# ID чата мастера для уведомлений
MASTER_CHAT_ID = os.getenv('MASTER_CHAT_ID')

# Путь к файлу авторизации Google
CREDENTIALS_FILE = 'credentials.json'

# Названия колонок в таблице
COLUMNS = {
    'timestamp': 'Время записи',
    'name': 'Имя',
    'phone': 'Телефон',
    'date': 'Дата',
    'time': 'Время',
    'service': 'Услуга',
    'telegram_id': 'Telegram ID',
    'username': 'Username',
    'status': 'Статус',
    'status_updated': 'Время изменения статуса',
    'reschedule_id': 'ID переноса',
    'original_booking_id': 'ID исходной записи'
}

# Цвета для статусов
STATUS_COLORS = {
    'ожидает': {'red': 1.0, 'green': 1.0, 'blue': 0.9},
    'подтверждено': {'red': 0.85, 'green': 1.0, 'blue': 0.85},
    'выполнено': {'red': 0.9, 'green': 0.9, 'blue': 1.0},
    'отменено': {'red': 0.95, 'green': 0.95, 'blue': 0.95},
    'отклонено': {'red': 1.0, 'green': 0.85, 'blue': 0.85},
    'запрос переноса': {'red': 1.0, 'green': 0.9, 'blue': 0.8},
    'предложение переноса': {'red': 0.9, 'green': 0.95, 'blue': 1.0},
}

# Упрощенные статусы
STATUSES = {
    'PENDING': 'ожидает',
    'CONFIRMED': 'подтверждено',
    'COMPLETED': 'выполнено',
    'CANCELLED': 'отменено',
    'REJECTED': 'отклонено',
    'RESCHEDULE_REQUESTED': 'запрос переноса',
    'RESCHEDULE_OFFERED': 'предложение переноса',
}

# Коды статусов для мастер-панели
MASTER_STATUSES = {
    'active': 'подтверждено',
    'completed': 'выполнено',
    'pending': 'ожидает',
    'reschedule': 'запрос переноса',
}