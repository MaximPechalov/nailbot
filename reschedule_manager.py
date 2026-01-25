"""
Централизованный менеджер для управления переносами записей
Предотвращает race conditions и упрощает логику
"""

import threading
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json
from uuid import uuid4


class RescheduleManager:
    """Менеджер для безопасного управления переносами"""
    
    def __init__(self, storage_manager):
        self.storage = storage_manager
        self.locks = {}  # Блокировки по booking_id
        self.lock = threading.Lock()  # Общая блокировка для управления locks
        
    def _get_lock(self, booking_id: str) -> threading.Lock:
        """Получает или создает блокировку для записи"""
        with self.lock:
            if booking_id not in self.locks:
                self.locks[booking_id] = threading.Lock()
            return self.locks[booking_id]
    
    def _cleanup_lock(self, booking_id: str):
        """Очищает блокировку если она больше не нужна"""
        with self.lock:
            if booking_id in self.locks:
                del self.locks[booking_id]
    
    def request_reschedule(self, original_booking_id: str, new_booking_data: Dict) -> Tuple[bool, str, str]:
        """
        Клиент запрашивает перенос записи
        Возвращает: (успех, новый_booking_id, сообщение_об_ошибке)
        """
        lock = self._get_lock(original_booking_id)
        
        with lock:
            try:
                # 1. Проверяем, что запись существует и доступна для переноса
                original_booking = self.storage.get_booking(original_booking_id)
                if not original_booking:
                    return False, "", "Запись не найдена"
                
                current_status = original_booking.get('status')
                if current_status not in ['ожидает', 'подтверждено']:
                    return False, "", "Эту запись нельзя перенести"
                
                # 2. Сохраняем старый статус
                old_status = current_status
                
                # 3. Создаем новую запись с предложенным временем
                new_booking_data.update({
                    'status': 'запрос переноса',
                    'original_booking_id': original_booking_id,
                    'old_status': old_status,
                    'reschedule_type': 'client_requested'
                })
                
                new_booking_id = self.storage.add_booking(new_booking_data)
                if not new_booking_id:
                    return False, "", "Не удалось создать новую запись"
                
                # 4. Обновляем статус оригинальной записи
                self.storage.update_booking_status(
                    original_booking_id, 
                    'запрос переноса',
                    master_comment=f"Запрос переноса на {new_booking_data.get('date')} {new_booking_data.get('time')}"
                )
                
                # 5. Сохраняем связь между записями
                self._save_reschedule_relation(original_booking_id, new_booking_id, 'client_requested')
                
                print(f"✅ Запрос переноса создан: {original_booking_id[:8]} -> {new_booking_id[:8]}")
                return True, new_booking_id, ""
                
            except Exception as e:
                print(f"❌ Ошибка при запросе переноса: {e}")
                return False, "", f"Ошибка: {str(e)}"
            finally:
                self._cleanup_lock(original_booking_id)
    
    def offer_reschedule(self, original_booking_id: str, new_date: str, new_time: str) -> Tuple[bool, str, str]:
        """
        Мастер предлагает перенос записи
        Возвращает: (успех, новый_booking_id, сообщение_об_ошибке)
        """
        lock = self._get_lock(original_booking_id)
        
        with lock:
            try:
                # 1. Проверяем, что запись существует и доступна для переноса
                original_booking = self.storage.get_booking(original_booking_id)
                if not original_booking:
                    return False, "", "Запись не найдена"
                
                current_status = original_booking.get('status')
                if current_status not in ['ожидает', 'подтверждено', 'запрос переноса']:
                    return False, "", "Эту запись нельзя перенести"
                
                # 2. Сохраняем старый статус
                old_status = current_status if current_status != 'запрос переноса' else original_booking.get('old_status', 'ожидает')
                
                # 3. Создаем новую запись с предложенным временем
                new_booking_data = {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'name': original_booking.get('name', ''),
                    'phone': original_booking.get('phone', ''),
                    'date': new_date,
                    'time': new_time,
                    'service': original_booking.get('service', ''),
                    'telegram_id': original_booking.get('telegram_id', ''),
                    'username': original_booking.get('username', ''),
                    'status': 'предложение переноса',
                    'original_booking_id': original_booking_id,
                    'old_status': old_status,
                    'reschedule_type': 'master_offered',
                    'master_proposed': True
                }
                
                new_booking_id = self.storage.add_booking(new_booking_data)
                if not new_booking_id:
                    return False, "", "Не удалось создать новую запись"
                
                # 4. Обновляем статус оригинальной записи (если это не уже запрос)
                if current_status != 'запрос переноса':
                    self.storage.update_booking_status(
                        original_booking_id, 
                        'предложение переноса',
                        master_comment=f"Предложение переноса на {new_date} {new_time}"
                    )
                
                # 5. Сохраняем связь между записями
                self._save_reschedule_relation(original_booking_id, new_booking_id, 'master_offered')
                
                print(f"✅ Предложение переноса создано: {original_booking_id[:8]} -> {new_booking_id[:8]}")
                return True, new_booking_id, ""
                
            except Exception as e:
                print(f"❌ Ошибка при предложении переноса: {e}")
                return False, "", f"Ошибка: {str(e)}"
            finally:
                self._cleanup_lock(original_booking_id)
    
    def accept_reschedule(self, reschedule_booking_id: str, accepted_by: str) -> Tuple[bool, str]:
        """
        Принимает перенос (клиентом или мастером)
        accepted_by: 'client' или 'master'
        """
        lock = self._get_lock(reschedule_booking_id)
        
        with lock:
            try:
                # 1. Получаем информацию о переносе
                reschedule_booking = self.storage.get_booking(reschedule_booking_id)
                if not reschedule_booking:
                    return False, "Запись не найдена"
                
                reschedule_type = reschedule_booking.get('reschedule_type')
                original_booking_id = reschedule_booking.get('original_booking_id')
                
                if not original_booking_id:
                    return False, "Не найдена исходная запись"
                
                # 2. Проверяем, кто может принять
                if accepted_by == 'client' and reschedule_type != 'master_offered':
                    return False, "Клиент может принять только предложения мастера"
                
                if accepted_by == 'master' and reschedule_type != 'client_requested':
                    return False, "Мастер может принять только запросы клиента"
                
                # 3. Получаем оригинальную запись
                original_booking = self.storage.get_booking(original_booking_id)
                if not original_booking:
                    return False, "Исходная запись не найдена"
                
                # 4. Обновляем статусы в зависимости от типа
                if reschedule_type == 'client_requested':
                    # Клиент запросил, мастер принимает
                    # Отменяем оригинальную, подтверждаем новую
                    self.storage.update_booking_status(original_booking_id, 'отменено')
                    self.storage.update_booking_status(reschedule_booking_id, 'подтверждено')
                    
                    # Удаляем связь, так как перенос завершен
                    self._remove_reschedule_relation(original_booking_id)
                    
                    message = "Перенос подтвержден. Оригинальная запись отменена."
                    
                else:  # master_offered
                    # Мастер предложил, клиент принимает
                    # Подтверждаем новую, отменяем оригинальную (если она не запрос)
                    if original_booking.get('status') != 'запрос переноса':
                        self.storage.update_booking_status(original_booking_id, 'отменено')
                    self.storage.update_booking_status(reschedule_booking_id, 'подтверждено')
                    
                    # Удаляем связь
                    self._remove_reschedule_relation(original_booking_id)
                    
                    message = "Предложение переноса принято."
                
                print(f"✅ Перенос принят ({accepted_by}): {reschedule_booking_id[:8]}")
                return True, message
                
            except Exception as e:
                print(f"❌ Ошибка при принятии переноса: {e}")
                return False, f"Ошибка: {str(e)}"
            finally:
                self._cleanup_lock(reschedule_booking_id)
                if original_booking_id:
                    self._cleanup_lock(original_booking_id)
    
    def reject_reschedule(self, reschedule_booking_id: str, rejected_by: str, reason: str = "") -> Tuple[bool, str]:
        """
        Отклоняет перенос (клиентом или мастером)
        """
        lock = self._get_lock(reschedule_booking_id)
        
        with lock:
            try:
                # 1. Получаем информацию о переносе
                reschedule_booking = self.storage.get_booking(reschedule_booking_id)
                if not reschedule_booking:
                    return False, "Запись не найдена"
                
                reschedule_type = reschedule_booking.get('reschedule_type')
                original_booking_id = reschedule_booking.get('original_booking_id')
                
                if not original_booking_id:
                    return False, "Не найдена исходная запись"
                
                # 2. Проверяем, кто может отклонить
                if rejected_by == 'client' and reschedule_type != 'master_offered':
                    return False, "Клиент может отклонить только предложения мастера"
                
                if rejected_by == 'master' and reschedule_type != 'client_requested':
                    return False, "Мастер может отклонить только запросы клиента"
                
                # 3. Получаем оригинальную запись
                original_booking = self.storage.get_booking(original_booking_id)
                if not original_booking:
                    return False, "Исходная запись не найдена"
                
                # 4. Обновляем статусы
                old_status = reschedule_booking.get('old_status', 'ожидает')
                
                # Возвращаем оригинальную запись в старый статус
                self.storage.update_booking_status(
                    original_booking_id, 
                    old_status,
                    master_comment=f"Перенос отклонен ({rejected_by}): {reason}"
                )
                
                # Отклоняем запись переноса
                self.storage.update_booking_status(reschedule_booking_id, 'отклонено')
                
                # Удаляем связь
                self._remove_reschedule_relation(original_booking_id)
                
                print(f"✅ Перенос отклонен ({rejected_by}): {reschedule_booking_id[:8]}")
                return True, "Перенос отклонен"
                
            except Exception as e:
                print(f"❌ Ошибка при отклонении переноса: {e}")
                return False, f"Ошибка: {str(e)}"
            finally:
                self._cleanup_lock(reschedule_booking_id)
                if original_booking_id:
                    self._cleanup_lock(original_booking_id)
    
    def cancel_reschedule_request(self, original_booking_id: str) -> Tuple[bool, str]:
        """
        Клиент отменяет свой запрос на перенос
        """
        lock = self._get_lock(original_booking_id)
        
        with lock:
            try:
                # 1. Находим запись переноса
                reschedule_booking_id = self._find_reschedule_booking(original_booking_id, 'client_requested')
                if not reschedule_booking_id:
                    return False, "Не найден запрос на перенос"
                
                # 2. Получаем записи
                original_booking = self.storage.get_booking(original_booking_id)
                reschedule_booking = self.storage.get_booking(reschedule_booking_id)
                
                if not original_booking or not reschedule_booking:
                    return False, "Записи не найдены"
                
                # 3. Возвращаем оригинальную запись в старый статус
                old_status = original_booking.get('old_status', 'ожидает')
                self.storage.update_booking_status(original_booking_id, old_status)
                
                # 4. Отменяем запись переноса
                self.storage.update_booking_status(reschedule_booking_id, 'отменено')
                
                # 5. Удаляем связь
                self._remove_reschedule_relation(original_booking_id)
                
                print(f"✅ Запрос переноса отменен: {original_booking_id[:8]}")
                return True, "Запрос переноса отменен"
                
            except Exception as e:
                print(f"❌ Ошибка при отмене запроса переноса: {e}")
                return False, f"Ошибка: {str(e)}"
            finally:
                self._cleanup_lock(original_booking_id)
    
    def _save_reschedule_relation(self, original_id: str, new_id: str, reschedule_type: str):
        """Сохраняет связь между записями при переносе"""
        relations_file = 'data/reschedule_relations.json'
        
        try:
            # Загружаем существующие связи
            try:
                with open(relations_file, 'r', encoding='utf-8') as f:
                    relations = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                relations = {}
            
            # Сохраняем связь
            relations[original_id] = {
                'new_id': new_id,
                'type': reschedule_type,
                'created_at': datetime.now().isoformat()
            }
            
            # Сохраняем обратную связь
            relations[new_id] = {
                'original_id': original_id,
                'type': reschedule_type,
                'created_at': datetime.now().isoformat()
            }
            
            # Сохраняем в файл
            with open(relations_file, 'w', encoding='utf-8') as f:
                json.dump(relations, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"⚠️ Ошибка сохранения связи переноса: {e}")
    
    def _remove_reschedule_relation(self, booking_id: str):
        """Удаляет связь между записями"""
        relations_file = 'data/reschedule_relations.json'
        
        try:
            # Загружаем существующие связи
            try:
                with open(relations_file, 'r', encoding='utf-8') as f:
                    relations = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return
            
            # Удаляем связи
            if booking_id in relations:
                related_id = relations[booking_id].get('new_id') or relations[booking_id].get('original_id')
                if related_id and related_id in relations:
                    del relations[related_id]
                del relations[booking_id]
            
            # Сохраняем в файл
            with open(relations_file, 'w', encoding='utf-8') as f:
                json.dump(relations, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"⚠️ Ошибка удаления связи переноса: {e}")
    
    def _find_reschedule_booking(self, original_id: str, reschedule_type: str) -> Optional[str]:
        """Находит запись переноса по оригинальному ID и типу"""
        relations_file = 'data/reschedule_relations.json'
        
        try:
            with open(relations_file, 'r', encoding='utf-8') as f:
                relations = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        
        if original_id in relations:
            relation = relations[original_id]
            if relation.get('type') == reschedule_type:
                return relation.get('new_id')
        
        return None
    
    def get_reschedule_info(self, booking_id: str) -> Optional[Dict]:
        """Получает информацию о переносе записи"""
        relations_file = 'data/reschedule_relations.json'
        
        try:
            with open(relations_file, 'r', encoding='utf-8') as f:
                relations = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        
        if booking_id not in relations:
            return None
        
        relation = relations[booking_id]
        related_id = relation.get('new_id') or relation.get('original_id')
        
        if not related_id:
            return None
        
        # Получаем обе записи
        booking1 = self.storage.get_booking(booking_id)
        booking2 = self.storage.get_booking(related_id)
        
        if not booking1 or not booking2:
            return None
        
        # Определяем какая запись оригинальная, какая новая
        if relation.get('type') == 'client_requested':
            original = booking1 if booking_id == relation.get('original_id', '') else booking2
            new = booking2 if booking_id == relation.get('original_id', '') else booking1
        else:  # master_offered
            # Для предложений мастера, booking_id всегда новая запись
            original = booking2
            new = booking1
        
        return {
            'reschedule_id': booking_id,
            'original_booking_id': original.get('booking_id', ''),
            'new_booking_id': new.get('booking_id', ''),
            'reschedule_type': relation.get('type', ''),
            'client_name': original.get('name', ''),
            'client_phone': original.get('phone', ''),
            'old_date': original.get('date', ''),
            'old_time': original.get('time', ''),
            'new_date': new.get('date', ''),
            'new_time': new.get('time', ''),
            'service': original.get('service', ''),
            'created_at': relation.get('created_at', ''),
            'client_id': original.get('telegram_id', ''),
            'client_username': original.get('username', '')
        }
    
    def get_active_reschedules(self, reschedule_type: str = None) -> List[Dict]:
        """Получает все активные переносы"""
        relations_file = 'data/reschedule_relations.json'
        
        try:
            with open(relations_file, 'r', encoding='utf-8') as f:
                relations = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
        
        result = []
        processed = set()
        
        for booking_id, relation in relations.items():
            # Пропускаем обратные ссылки и уже обработанные
            if booking_id in processed:
                continue
            
            related_id = relation.get('new_id') or relation.get('original_id')
            if not related_id or related_id in processed:
                continue
            
            # Фильтруем по типу если указан
            if reschedule_type and relation.get('type') != reschedule_type:
                continue
            
            # Получаем информацию о переносе
            info = self.get_reschedule_info(booking_id)
            if info:
                result.append(info)
                processed.add(booking_id)
                processed.add(related_id)
        
        # Сортировка по дате создания
        result.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return result