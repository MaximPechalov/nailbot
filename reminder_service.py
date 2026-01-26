"""
Сервис для отправки напоминаний о записях
За сутки и за 2 часа до записи
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import os
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from config import TELEGRAM_BOT_TOKEN

class ReminderService:
    def __init__(self, storage_manager):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN)
        self.storage = storage_manager
        self.data_dir = 'data'
        self.reminders_file = os.path.join(self.data_dir, 'reminders_settings.json')
        self._ensure_data_dir()
        self._ensure_reminders_file()
        
        # Инициализируем, но не запускаем фоновую задачу здесь
        self.running = False
        self.background_task = None
        
    def start(self):
        """Запускает сервис напоминаний"""
        if not self.running:
            self.running = True
            # Создаем и запускаем фоновую задачу
            self.background_task = asyncio.create_task(self._reminder_checker())
            print("✅ Сервис напоминаний запущен")
    
    def _ensure_data_dir(self):
        """Создает папку data если её нет"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
    
    def _ensure_reminders_file(self):
        """Создает файл настроек напоминаний если его нет"""
        if not os.path.exists(self.reminders_file):
            default_settings = {
                'global_enabled': True,
                'user_settings': {},
                'sent_reminders': {}
            }
            with open(self.reminders_file, 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, ensure_ascii=False, indent=2)
    
    def _load_reminders_settings(self) -> Dict:
        """Загружает настройки напоминаний"""
        try:
            with open(self.reminders_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {'global_enabled': True, 'user_settings': {}, 'sent_reminders': {}}
    
    def _save_reminders_settings(self, settings: Dict):
        """Сохраняет настройки напоминаний"""
        with open(self.reminders_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    
    def get_user_settings(self, user_id: str) -> Dict:
        """Получает настройки напоминаний для пользователя"""
        settings = self._load_reminders_settings()
        user_settings = settings['user_settings'].get(str(user_id), {
            'enabled': True,
            'reminder_24h': True,
            'reminder_2h': True,
            'pause_until': None
        })
        return user_settings
    
    def update_user_settings(self, user_id: str, updates: Dict):
        """Обновляет настройки напоминаний для пользователя"""
        settings = self._load_reminders_settings()
        
        if str(user_id) not in settings['user_settings']:
            settings['user_settings'][str(user_id)] = {
                'enabled': True,
                'reminder_24h': True,
                'reminder_2h': True,
                'pause_until': None
            }
        
        settings['user_settings'][str(user_id)].update(updates)
        self._save_reminders_settings(settings)
    
    def pause_reminders(self, user_id: str, duration_hours: int):
        """Приостанавливает напоминания на указанное количество часов"""
        pause_until = datetime.now() + timedelta(hours=duration_hours)
        pause_until_str = pause_until.isoformat()
        
        self.update_user_settings(user_id, {
            'pause_until': pause_until_str
        })
        
        return pause_until
    
    def disable_reminders(self, user_id: str):
        """Полностью отключает напоминания для пользователя"""
        self.update_user_settings(user_id, {
            'enabled': False
        })
    
    def enable_reminders(self, user_id: str):
        """Включает напоминания для пользователя"""
        self.update_user_settings(user_id, {
            'enabled': True,
            'pause_until': None
        })
    
    def can_send_reminder(self, user_id: str, reminder_type: str) -> bool:
        """Проверяет, можно ли отправить напоминание"""
        settings = self._load_reminders_settings()
        
        # Глобальная настройка
        if not settings.get('global_enabled', True):
            return False
        
        # Настройки пользователя
        user_settings = self.get_user_settings(user_id)
        
        if not user_settings.get('enabled', True):
            return False
        
        # Проверка паузы
        pause_until = user_settings.get('pause_until')
        if pause_until:
            try:
                pause_until_dt = datetime.fromisoformat(pause_until)
                if datetime.now() < pause_until_dt:
                    return False
            except:
                pass
        
        # Проверка типа напоминания
        if reminder_type == '24h' and not user_settings.get('reminder_24h', True):
            return False
        if reminder_type == '2h' and not user_settings.get('reminder_2h', True):
            return False
        
        return True
    
    def mark_reminder_sent(self, user_id: str, booking_id: str, reminder_type: str):
        """Отмечает напоминание как отправленное"""
        settings = self._load_reminders_settings()
        
        if 'sent_reminders' not in settings:
            settings['sent_reminders'] = {}
        
        reminder_key = f"{user_id}_{booking_id}_{reminder_type}"
        settings['sent_reminders'][reminder_key] = datetime.now().isoformat()
        
        self._save_reminders_settings(settings)
    
    def was_reminder_sent(self, user_id: str, booking_id: str, reminder_type: str) -> bool:
        """Проверяет, было ли уже отправлено напоминание"""
        settings = self._load_reminders_settings()
        
        reminder_key = f"{user_id}_{booking_id}_{reminder_type}"
        return reminder_key in settings.get('sent_reminders', {})
    
    async def send_reminder(self, user_id: str, booking: Dict, reminder_type: str):
        """Отправляет напоминание пользователю"""
        try:
            if not self.can_send_reminder(user_id, reminder_type):
                return False
            
            # Проверяем, не было ли уже отправлено это напоминание
            booking_id = booking.get('booking_id', '')
            if self.was_reminder_sent(user_id, booking_id, reminder_type):
                return False
            
            # Форматируем сообщение в зависимости от типа напоминания
            if reminder_type == '24h':
                message = self._format_24h_reminder(booking)
            else:  # 2h
                message = self._format_2h_reminder(booking)
            
            # Создаем клавиатуру для управления напоминаниями
            keyboard = [
                [
                    InlineKeyboardButton("⏸️ На сутки", callback_data=f"pause_reminders_24_{booking_id}"),
                    InlineKeyboardButton("⏸️ На 3 дня", callback_data=f"pause_reminders_72_{booking_id}")
                ],
                [
                    InlineKeyboardButton("⏸️ На неделю", callback_data=f"pause_reminders_168_{booking_id}"),
                    InlineKeyboardButton("🚫 Навсегда", callback_data=f"disable_reminders_{booking_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Отправляем сообщение
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
            # Отмечаем как отправленное
            self.mark_reminder_sent(user_id, booking_id, reminder_type)
            
            print(f"✅ Напоминание {reminder_type} отправлено пользователю {user_id}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка отправки напоминания: {e}")
            return False
    
    def _format_24h_reminder(self, booking: Dict) -> str:
        """Форматирует напоминание за 24 часа"""
        return (
            f"⏰ <b>НАПОМИНАНИЕ О ЗАПИСИ</b>\n\n"
            f"У вас запись <b>завтра</b>:\n\n"
            f"📅 <b>Дата:</b> {booking.get('date', '')}\n"
            f"⏰ <b>Время:</b> {booking.get('time', '')}\n"
            f"💅 <b>Услуга:</b> {booking.get('service', '')}\n\n"
            f"📍 <b>Адрес:</b> {self._get_salon_address()}\n"
            f"📞 <b>Телефон:</b> {self._get_salon_phone()}\n\n"
            f"Ждем вас! 🕒\n\n"
            f"<i>Вы можете отключить напоминания:</i>"
        )
    
    def _format_2h_reminder(self, booking: Dict) -> str:
        """Форматирует напоминание за 2 часа"""
        return (
            f"⏰ <b>НАПОМИНАНИЕ О ЗАПИСИ</b>\n\n"
            f"У вас запись <b>через 2 часа</b>:\n\n"
            f"📅 <b>Дата:</b> {booking.get('date', '')}\n"
            f"⏰ <b>Время:</b> {booking.get('time', '')}\n"
            f"💅 <b>Услуга:</b> {booking.get('service', '')}\n\n"
            f"📍 <b>Адрес:</b> {self._get_salon_address()}\n"
            f"📞 <b>Телефон:</b> {self._get_salon_phone()}\n\n"
            f"Пожалуйста, не опаздывайте! 🕒\n\n"
            f"<i>Вы можете отключить напоминания:</i>"
        )
    
    def _get_salon_address(self) -> str:
        """Получает адрес салона"""
        try:
            from config import SALON_ADDRESS
            return SALON_ADDRESS
        except:
            return ""
    
    def _get_salon_phone(self) -> str:
        """Получает телефон салона"""
        try:
            from config import MASTER_PHONE
            return MASTER_PHONE
        except:
            return ""
    
    async def _reminder_checker(self):
        """Фоновая задача для проверки и отправки напоминаний"""
        print("✅ Сервис напоминаний запущен (за 24ч и 2ч до записи)")
        
        while self.running:
            try:
                await asyncio.sleep(60)  # Проверяем каждую минуту
                
                # Получаем текущее время
                now = datetime.now()
                
                # Получаем все активные записи (подтвержденные)
                active_bookings = self.storage.get_bookings_by_status('подтверждено')
                
                for booking in active_bookings:
                    try:
                        # Парсим дату и время записи
                        date_str = booking.get('date')
                        time_str = booking.get('time')
                        
                        if not date_str or not time_str:
                            continue
                        
                        # Преобразуем в datetime
                        booking_datetime = self._parse_booking_datetime(date_str, time_str)
                        if not booking_datetime:
                            continue
                        
                        # Проверяем, не прошла ли уже запись
                        if booking_datetime <= now:
                            continue
                        
                        # Вычисляем разницу во времени
                        time_diff = booking_datetime - now
                        minutes_diff = time_diff.total_seconds() / 60
                        hours_diff = minutes_diff / 60
                        
                        # Отправляем напоминания в нужное время
                        user_id = booking.get('telegram_id')
                        booking_id = booking.get('booking_id')
                        
                        if not user_id or not booking_id:
                            continue
                        
                        # За 24 часа (1440 минут) ± 1 час
                        if 1380 <= minutes_diff <= 1500:
                            await self.send_reminder(user_id, booking, '24h')
                        
                        # За 2 часа (120 минут) ± 10 минут
                        elif 110 <= minutes_diff <= 130:
                            await self.send_reminder(user_id, booking, '2h')
                            
                    except Exception as e:
                        print(f"❌ Ошибка обработки записи для напоминания: {e}")
                        continue
                        
            except Exception as e:
                print(f"❌ Ошибка в reminder_checker: {e}")
                await asyncio.sleep(300)  # Ждем 5 минут при ошибке
    
    def _parse_booking_datetime(self, date_str: str, time_str: str) -> Optional[datetime]:
        """Парсит дату и время записи"""
        try:
            # Парсим дату в формате ДД.ММ.ГГГГ
            day, month, year = map(int, date_str.split('.'))
            
            # Парсим время в формате ЧЧ:ММ
            hours, minutes = map(int, time_str.split(':'))
            
            return datetime(year, month, day, hours, minutes)
            
        except Exception as e:
            print(f"❌ Ошибка парсинга даты/времени: {date_str} {time_str}, {e}")
            return None
    
    async def handle_reminder_callback(self, update, context, data: str):
        """Обрабатывает callback от кнопок напоминаний"""
        query = update.callback_query
        await query.answer()
        
        parts = data.split('_')
        if len(parts) < 3:
            return
        
        action = parts[1]
        user_id = update.effective_user.id
        
        if action == 'pause':
            # Формат: pause_reminders_24_booking_id
            if len(parts) >= 4:
                duration_hours = int(parts[2])
                booking_id = parts[3]
                
                pause_until = self.pause_reminders(user_id, duration_hours)
                
                duration_text = self._get_duration_text(duration_hours)
                await query.edit_message_text(
                    f"⏸️ Напоминания приостановлены на {duration_text}.\n"
                    f"Вы снова будете получать их после {pause_until.strftime('%d.%m.%Y %H:%M')}.",
                    parse_mode='HTML'
                )
                
        elif action == 'disable':
            # Формат: disable_reminders_booking_id
            if len(parts) >= 3:
                booking_id = parts[2]
                self.disable_reminders(user_id)
                
                await query.edit_message_text(
                    "🚫 Напоминания отключены навсегда.\n"
                    "Вы можете включить их снова в настройках бота.",
                    parse_mode='HTML'
                )
    
    def _get_duration_text(self, hours: int) -> str:
        """Возвращает текстовое описание длительности"""
        if hours == 24:
            return "сутки"
        elif hours == 72:
            return "3 дня"
        elif hours == 168:
            return "неделю"
        else:
            days = hours // 24
            return f"{days} дней"
    
    async def stop(self):
        """Останавливает сервис напоминаний"""
        self.running = False
        if self.background_task:
            self.background_task.cancel()
            try:
                await self.background_task
            except asyncio.CancelledError:
                pass
        print("🛑 Сервис напоминаний остановлен")