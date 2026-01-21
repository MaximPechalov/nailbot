import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# Токен бота Telegram (получите у @BotFather)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# ID Google таблицы (скопируйте из URL таблицы)
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')

# ID чата мастера для уведомлений
MASTER_CHAT_ID = os.getenv('MASTER_CHAT_ID')  # Можно получить через @userinfobot

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
    'status_updated': 'Время изменения статуса'
}

# Цвета для статусов (для информации, используются в google_sheets.py)
STATUS_COLORS = {
    'ожидает': 'СВЕТЛО-ЖЕЛТЫЙ',
    'подтверждено': 'СВЕТЛО-ЗЕЛЕНЫЙ',
    'отклонено': 'СВЕТЛО-КРАСНЫЙ',
    'отклонено мастером': 'КРАСНЫЙ',
    'выполнено': 'СВЕТЛО-ГОЛУБОЙ',
    'отменено': 'СЕРЫЙ'
}

# Возможные статусы
STATUSES = {
    'PENDING': 'ожидает',
    'CONFIRMED': 'подтверждено',
    'REJECTED_BY_CLIENT': 'отклонено',
    'REJECTED_BY_MASTER': 'отклонено мастером',
    'COMPLETED': 'выполнено',
    'CANCELLED': 'отменено'
}
