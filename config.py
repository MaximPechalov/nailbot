import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# =====================
# ТЕХНИЧЕСКИЕ НАСТРОЙКИ
# =====================

# Токен бота Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# ID Google таблицы
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')

# ID чата мастера для уведомлений
MASTER_CHAT_ID = os.getenv('MASTER_CHAT_ID')

# Путь к файлу авторизации Google
CREDENTIALS_FILE = 'credentials.json'

# =====================
# ИНФОРМАЦИЯ О МАСТЕРЕ/САЛОНЕ
# =====================

# Основная информация
SALON_NAME = os.getenv('SALON_NAME', 'Салон маникюра')
SALON_ADDRESS = os.getenv('SALON_ADDRESS', 'Адрес не указан')
WORKING_HOURS = os.getenv('WORKING_HOURS', '10:00 - 22:00')

# Контакты
MASTER_PHONE = os.getenv('MASTER_PHONE', '+7 (999) 123-45-67')
MASTER_EMAIL = os.getenv('MASTER_EMAIL', 'info@manicure.ru')

# Социальные сети
INSTAGRAM_URL = os.getenv('INSTAGRAM_URL', 'https://instagram.com/manicure_beauty')
VK_URL = os.getenv('VK_URL', 'https://vk.com/manicure_beauty')
TELEGRAM_CHANNEL = os.getenv('TELEGRAM_CHANNEL', '@manicure_salon')

# =====================
# КОНФИГУРАЦИЯ ТАБЛИЦЫ
# =====================

# Названия колонок в таблице
COLUMNS = {
    'booking_id': 'ID записи',
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

# Уникальные цвета для статусов
STATUS_COLORS = {
    'ожидает': {'red': 1.0, 'green': 1.0, 'blue': 0.85},
    'подтверждено': {'red': 0.85, 'green': 1.0, 'blue': 0.85},
    'выполнено': {'red': 0.85, 'green': 0.95, 'blue': 1.0},
    'отменено': {'red': 0.95, 'green': 0.95, 'blue': 0.95},
    'отклонено': {'red': 1.0, 'green': 0.9, 'blue': 0.9},
    'запрос переноса': {'red': 1.0, 'green': 0.85, 'blue': 0.7},
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

# Приоритеты сортировки по статусам
STATUS_PRIORITY = {
    'ожидает': 1,
    'подтверждено': 2,
    'запрос переноса': 3,
    'предложение переноса': 4,
    'выполнено': 5,
    'отменено': 6,
    'отклонено': 7,
}

# =====================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================

def get_salon_info():
    """Возвращает полную информацию о салоне"""
    return {
        'name': SALON_NAME,
        'address': SALON_ADDRESS,
        'working_hours': WORKING_HOURS,
        'phone': MASTER_PHONE,
        'email': MASTER_EMAIL,
        'instagram': INSTAGRAM_URL,
        'vk': VK_URL,
        'telegram_channel': TELEGRAM_CHANNEL,
    }