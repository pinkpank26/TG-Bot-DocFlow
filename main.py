import asyncio
import logging
import os
import re
import sqlite3
import sys
import uuid
import io
import json
import random
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, Contact, InlineQueryResultArticle, InputTextMessageContent, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, 
    filters, ContextTypes, ConversationHandler, PicklePersistence, InlineQueryHandler
)
from telegram.error import BadRequest
from telethon import TelegramClient
from telethon.errors import FloodWaitError, PhoneNumberInvalidError, PhoneNumberUnoccupiedError
from telethon.tl.types import InputPhoneContact, User
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from contextlib import contextmanager
from auth_bot import get_admin_session, get_all_active_admins
from config import settings
from database import init_database
from services.web_auth import web_auth_service
from web.server import start_web_auth_server
import time

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DEVELOPER_ADMIN_ID = int(os.getenv("DEVELOPER_ADMIN_ID", "0"))
BOT_TOKEN = settings.bot_token

WAITING_RECIPIENTS = 1
WAITING_ADD_CONTACT = 2
WAITING_MESSAGE_THEME = 3

# ====== КОНСТАНТЫ ЯЗЫКОВ ======
LANGUAGES = {
    'ru': '🇷🇺 Русский',
    'en': '🇬🇧 English'
}

# ====== КОНСТАНТЫ ТАЙМАУТОВ ======
COMMENT_REMINDER_TIME = 300  # 5 минут в секундах для напоминания о комментарии
FINAL_REMINDER_TIME = 600    # 10 минут в секундах для финального напоминания
AUTO_APPROVE_TIME = 1800     # 30 минут в секундах для автосогласования (если нужно)

# ====== КЛАСС С ПЕРЕВОДАМИ (ОБНОВЛЕННЫЙ) ======
class Translations:
    @staticmethod
    def get(key: str, lang: str = 'ru') -> str:
        translations = {
            'main_menu_title': {
                'ru': '👑 Администратор DocFlow',
                'en': '👑 DocFlow Administrator'
            },
            'statistics': {
                'ru': '📊 Краткая статистика',
                'en': '📊 Quick statistics'
            },
            'users': {
                'ru': '👥 Пользователей',
                'en': '👥 Users'
            },
            'with_phones': {
                'ru': '📱 С телефонами',
                'en': '📱 With phones'
            },
            'with_username': {
                'ru': '👤 С username',
                'en': '👤 With username'
            },
            'documents': {
                'ru': '📄 Документов',
                'en': '📄 Documents'
            },
            'pending_approval': {
                'ru': '⏳ Ожидают согласования',
                'en': '⏳ Pending approval'
            },
            'auto_send': {
                'ru': '🤖 Автоматическая отправка',
                'en': '🤖 Auto sending'
            },
            'send_from': {
                'ru': '📱 Отправка от',
                'en': '📱 Sending from'
            },
            'in_queue': {
                'ru': '📨 В очереди',
                'en': '📨 In queue'
            },
            'sent': {
                'ru': '✅ Отправлено',
                'en': '✅ Sent'
            },
            'bot': {
                'ru': '📱 Бот',
                'en': '📱 Bot'
            },
            'your_id': {
                'ru': '🆔 Ваш ID',
                'en': '🆔 Your ID'
            },
            'select_action': {
                'ru': '👇 Выберите действия',
                'en': '👇 Select action'
            },
            'current_language': {
                'ru': '🌐 Текущий язык',
                'en': '🌐 Current language'
            },
            'send_document': {
                'ru': '📤 ОТПРАВИТЬ ДОКУМЕНТ',
                'en': '📤 SEND DOCUMENT'
            },
            'contacts': {
                'ru': '📋 Контакты',
                'en': '📋 Contacts'
            },
            'add': {
                'ru': '➕ Добавить',
                'en': '➕ Add'
            },
            'reports': {
                'ru': '📊 Отчеты по документам',
                'en': '📊 Document reports'
            },
            'queue_status': {
                'ru': '🤖 Статус отправки',
                'en': '🤖 Sending status'
            },
            'instructions': {
                'ru': '📖 ИНСТРУКЦИЯ',
                'en': '📖 INSTRUCTIONS'
            },
            'change_language': {
                'ru': '🌐 Сменить язык',
                'en': '🌐 Change language'
            },
            'refresh': {
                'ru': '🔄 Обновить',
                'en': '🔄 Refresh'
            },
            'back': {
                'ru': '⬅️ Назад',
                'en': '⬅️ Back'
            },
            'back_to_menu': {
                'ru': '⬅️ Назад в меню',
                'en': '⬅️ Back to menu'
            },
            'select_language': {
                'ru': '🌐 Выберите язык',
                'en': '🌐 Select language'
            },
            'russian': {
                'ru': '🇷🇺 Русский',
                'en': '🇷🇺 Russian'
            },
            'english': {
                'ru': '🇬🇧 English',
                'en': '🇬🇧 English'
            },
            'language_changed_ru': {
                'ru': '✅ Язык изменен на Русский!',
                'en': '✅ Language changed to Russian!'
            },
            'language_changed_en': {
                'ru': '✅ Язык изменен на English!',
                'en': '✅ Language changed to English!'
            },
            'continue_btn': {
                'ru': '✅ Продолжить',
                'en': '✅ Continue'
            },
            'received_documents': {
                'ru': '📚 Получено документов',
                'en': '📚 Received documents'
            },
            'group_id': {
                'ru': '🆔 Группа ID',
                'en': '🆔 Group ID'
            },
            'document_list': {
                'ru': '📋 Список документов',
                'en': '📋 Document list'
            },
            'specify_recipients': {
                'ru': '📋 Укажите получателей (телефоны или username)',
                'en': '📋 Specify recipients (phones or username)'
            },
            'phones_format': {
                'ru': '📱 Телефоны (любой формат)',
                'en': '📱 Phones (any format)'
            },
            'username_format': {
                'ru': '👤 Username',
                'en': '👤 Username'
            },
            'mixed_format': {
                'ru': '📝 Смешанно',
                'en': '📝 Mixed'
            },
            'or_select_from_contacts': {
                'ru': '👥 Или нажмите кнопку для выбора из списка контактов',
                'en': '👥 Or click the button to select from contacts'
            },
            'cancel': {
                'ru': '❌ Отмена',
                'en': '❌ Cancel'
            },
            'select_from_contacts': {
                'ru': '👥 ВЫБРАТЬ ИЗ КОНТАКТОВ',
                'en': '👥 SELECT FROM CONTACTS'
            },
            'no_recipients': {
                'ru': '❌ Не указаны получатели',
                'en': '❌ No recipients specified'
            },
            'recipients_not_recognized': {
                'ru': '❌ Не удалось распознать получателей',
                'en': '❌ Failed to recognize recipients'
            },
            'welcome': {
                'ru': 'Добро пожаловать',
                'en': 'Welcome'
            },
            'database_locked': {
                'ru': '❌ База данных временно заблокирована\n\nПодождите 30 секунд и попробуйте снова',
                'en': '❌ Database is temporarily locked\n\nWait 30 seconds and try again'
            },
            'contact_updated': {
                'ru': '✅ Контакт обновлен',
                'en': '✅ Contact updated'
            },
            'contact_added': {
                'ru': '✅ Контакт добавлен',
                'en': '✅ Contact added'
            },
            'auto_send_success': {
                'ru': '🤖 Приглашение отправлено автоматически',
                'en': '🤖 Invitation sent automatically'
            },
            'manual_send_required': {
                'ru': '📋 Требуется ручная отправка',
                'en': '📋 Manual sending required'
            },
            'user_not_activated': {
                'ru': '📨 Пользователь не активирован',
                'en': '📨 User not activated'
            },
            'unknown_error': {
                'ru': '❌ Неизвестная ошибка',
                'en': '❌ Unknown error'
            },
            # ====== НОВЫЕ ПЕРЕВОДЫ ДЛЯ ФУНКЦИОНАЛА КОММЕНТАРИЕВ ======
            'view_recipients': {
                'ru': '👥 Кто еще получил',
                'en': '👥 Who else received'
            },
            'leave_comment': {
                'ru': '💬 Оставить комментарий',
                'en': '💬 Leave comment'
            },
            'comment_text': {
                'ru': '📝 Напишите ваш комментарий к документу:',
                'en': '📝 Write your comment for the document:'
            },
            'comment_saved': {
                'ru': '💬 Ваш комментарий сохранен',
                'en': '💬 Your comment saved'
            },
            'comment_added': {
                'ru': '💬 Добавлен комментарий',
                'en': '💬 Comment added'
            },
            'view_instructions': {
                'ru': '📖 Инструкция',
                'en': '📖 Instructions'
            },
            'instructions_title': {
                'ru': '📖 ИНСТРУКЦИЯ ДЛЯ ПОЛЬЗОВАТЕЛЯ',
                'en': '📖 USER INSTRUCTIONS'
            },
            'instructions_text': {
                'ru': """📖 **ИНСТРУКЦИЯ ДЛЯ ПОЛЬЗОВАТЕЛЯ**

**🎯 КАК ЭТО РАБОТАЕТ:**

1. **📩 Получение документа**
   - Вам приходит документ от администратора
   - Документ требует вашего согласования или комментария

2. **👀 Просмотр документа**
   - Вы можете просмотреть все страницы документа
   - Для этого прокрутите вниз, чтобы увидеть все файлы

3. **👥 Кто еще получил документ**
   - Нажмите кнопку "👥 Кто еще получил"
   - Вы увидите список всех получателей документа

4. **💬 Комментарий к документу**
   - Нажмите кнопку "💬 Комментарий"
   - Введите ваш комментарий в появившемся окне
   - Комментарий будет сохранен вместе с вашим решением

5. **✅ Согласование документа**
   - Нажмите кнопку "✅ Согласен" чтобы утвердить документ
   - Или кнопку "❌ Отклонить" чтобы отклонить документ

6. **📊 После согласования**
   - Вы увидите подтверждение вашего решения
   - Администратор получит уведомление о вашем решении
   - Все решения собираются в единый отчет

**💡 ПОЛЕЗНЫЕ СОВЕТЫ:**

• Всегда проверяйте документы перед согласованием
• Используйте комментарии для пояснения своего решения
• Если есть вопросы - напишите администратору
• После активации все документы будут приходить автоматически

**🆘 ЕСЛИ ЧТО-ТО НЕ РАБОТАЕТ:**

1. Перезапустите бота командой /start
2. Проверьте интернет-соединение
3. Обратитесь к администратору

**📞 ПОДДЕРЖКА:**
Администратор: @admin_username""",
                'en': """📖 **USER INSTRUCTIONS**

**🎯 HOW IT WORKS:**

1. **📩 Receiving a document**
   - You receive a document from the administrator
   - The document requires your approval or comment

2. **👀 Viewing the document**
   - You can view all pages of the document
   - Scroll down to see all files

3. **👥 Who else received the document**
   - Click the "👥 Who else received" button
   - You will see a list of all document recipients

4. **💬 Comment on the document**
   - Click the "💬 Comment" button
   - Enter your comment in the window that appears
   - The comment will be saved along with your decision

5. **✅ Document approval**
   - Click "✅ Agree" to approve the document
   - Or click "❌ Reject" to reject the document

6. **📊 After approval**
   - You will see confirmation of your decision
   - The administrator will receive notification of your decision
   - All decisions are collected into a single report

**💡 USEFUL TIPS:**

• Always check documents before approval
• Use comments to explain your decision
• If you have questions - write to the administrator
• After activation, all documents will come automatically

**🆘 IF SOMETHING DOESN'T WORK:**

1. Restart the bot with the /start command
2. Check your internet connection
3. Contact the administrator

**📞 SUPPORT:**
Administrator: @admin_username"""
            },
            'recipients_list': {
                'ru': '👥 **Список получателей документа:**\n\n',
                'en': '👥 **Document recipients list:**\n\n'
            },
            'recipient_item': {
                'ru': '{index}. {name} - {status}\n',
                'en': '{index}. {name} - {status}\n'
            },
            'recipient_status_pending': {
                'ru': '⏳ Ожидает решения',
                'en': '⏳ Pending decision'
            },
            'recipient_status_approved': {
                'ru': '✅ Согласовано',
                'en': '✅ Approved'
            },
            'recipient_status_rejected': {
                'ru': '❌ Отклонено',
                'en': '❌ Rejected'
            },
            'waiting_comment': {
                'ru': '💬 *Ожидаю ваш комментарий*\n\nНапишите комментарий к документу:',
                'en': '💬 *Waiting for your comment*\n\nWrite your comment for the document:'
            },
            'comment_cancel': {
                'ru': '❌ Отмена комментария',
                'en': '❌ Cancel comment'
            },
            'comment_too_long': {
                'ru': '❌ Комментарий слишком длинный (максимум 1000 символов)',
                'en': '❌ Comment is too long (maximum 1000 characters)'
            },
            'edit_comment': {
                'ru': '💬 Изменить комментарий',
                'en': '💬 Edit comment'
            },
            'change_comment': {
                'ru': '💬 Изменить комментарий',
                'en': '💬 Change comment'
            },
            'no_comments_waiting': {
                'ru': '❌ Не найдено ожидающих комментариев',
                'en': '❌ No pending comments found'
            },
            'back_to_document': {
                'ru': '⬅️ Назад к документу',
                'en': '⬅️ Back to document'
            },
            # ====== НОВЫЕ ПЕРЕВОДЫ ДЛЯ СИСТЕМЫ НАПОМИНАНИЙ ======
            'comment_reminder': {
                'ru': '⏰ *Напоминание о комментарии*\n\n'
                      'Вы оставили комментарий к документу, но еще не приняли решение.\n\n'
                      'Пожалуйста, нажмите кнопку "✅ Согласен" или "❌ Отклонить" для завершения согласования.\n\n'
                      '💡 *Комментарий будет сохранен вместе с вашим решением.*',
                'en': '⏰ *Comment Reminder*\n\n'
                      'You left a comment on the document but have not made a decision yet.\n\n'
                      'Please click "✅ Agree" or "❌ Reject" to complete the approval.\n\n'
                      '💡 *The comment will be saved along with your decision.*'
            },
            'comment_without_decision_admin': {
                'ru': '📝 *Пользователь оставил комментарий без решения*\n\n'
                      '👤 Пользователь: {user_info}\n'
                      '🆔 ID документа: {doc_id}\n'
                      '💬 Комментарий: "{comment}"\n\n'
                      '⏰ Время комментария: {time}\n'
                      '⏳ Ожидает решения уже 5 минут\n\n'
                      '📋 *Что делать:*\n'
                      '1. Свяжитесь с пользователем для уточнения\n'
                      '2. Дождитесь его решения\n'
                      '3. Через 5 минут будет отправлено финальное напоминание',
                'en': '📝 *User left comment without decision*\n\n'
                      '👤 User: {user_info}\n'
                      '🆔 Document ID: {doc_id}\n'
                      '💬 Comment: "{comment}"\n\n'
                      '⏰ Comment time: {time}\n'
                      '⏳ Waiting for decision for 5 minutes\n\n'
                      '📋 *What to do:*\n'
                      '1. Contact the user for clarification\n'
                      '2. Wait for his decision\n'
                      '3. Final reminder will be sent in 5 minutes'
            },
            'final_reminder': {
                'ru': '⚠️ *Финальное напоминание*\n\n'
                      'Вы оставили комментарий к документу, но до сих пор не приняли решение.\n\n'
                      'Пожалуйста, нажмите кнопку "✅ Согласен" или "❌ Отклонить" в течение 10 минут.\n\n'
                      '⏰ *Иначе будет считаться, что вы:*\n'
                      '1. Просмотрели документ\n'
                      '2. Ознакомились с содержимым\n'
                      '3. Оставили комментарий\n'
                      '4. Не выразили явного согласия/несогласия\n\n'
                      '💡 *Комментарий:*\n'
                      '"{comment}"',
                'en': '⚠️ *Final Reminder*\n\n'
                      'You left a comment on the document but still have not made a decision.\n\n'
                      'Please click "✅ Agree" or "❌ Reject" within 10 minutes.\n\n'
                      '⏰ *Otherwise it will be considered that you:*\n'
                      '1. Viewed the document\n'
                      '2. Familiarized yourself with the content\n'
                      '3. Left a comment\n'
                      '4. Did not express explicit agreement/disagreement\n\n'
                      '💡 *Comment:*\n'
                      '"{comment}"'
            },
            'comment_only_admin': {
                'ru': '📋 *Комментарий без решения*\n\n'
                      '👤 Пользователь: {user_info}\n'
                      '🆔 ID документа: {doc_id}\n'
                      '💬 Комментарий: "{comment}"\n\n'
                      '⏰ Время: {time}\n'
                      '⏳ Статус: Комментарий оставлен, но решение не принято\n'
                      '⏱️ Прошло времени: {elapsed_time}\n\n'
                      '📊 *Информация:*\n'
                      'Пользователь ознакомился с документом и оставил комментарий,\n'
                      'но не выразил явного согласия или несогласия.',
                'en': '📋 *Comment without decision*\n\n'
                      '👤 User: {user_info}\n'
                      '🆔 Document ID: {doc_id}\n'
                      '💬 Comment: "{comment}"\n\n'
                      '⏰ Time: {time}\n'
                      '⏳ Status: Comment left but no decision made\n'
                      '⏱️ Time elapsed: {elapsed_time}\n\n'
                      '📊 *Information:*\n'
                      'The user reviewed the document and left a comment,\n'
                      'but did not express explicit agreement or disagreement.'
            },
            'comment_with_decision_admin': {
                'ru': '📋 *Комментарий с решением*\n\n'
                      '👤 Пользователь: {user_info}\n'
                      '🆔 ID документа: {doc_id}\n'
                      '📄 Документ: {document_name}\n'
                      '✅ Решение: {decision}\n'
                      '💬 Комментарий: "{comment}"\n\n'
                      '⏰ Время: {time}\n'
                      '⏱️ Время отклика: {response_time}\n\n'
                      '🎉 *Пользователь принял решение!*',
                'en': '📋 *Comment with decision*\n\n'
                      '👤 User: {user_info}\n'
                      '🆔 Document ID: {doc_id}\n'
                      '📄 Document: {document_name}\n'
                      '✅ Decision: {decision}\n'
                      '💬 Comment: "{comment}"\n\n'
                      '⏰ Time: {time}\n'
                      '⏱️ Response time: {response_time}\n\n'
                      '🎉 *User made a decision!*'
            },
            # ====== ДЛЯ ИНЛАЙН-КНОПКИ ======
            'inline_start_button': {
                'ru': '🚀 Restart / Menu',
                'en': '🚀 Restart / Menu'
            },
            'inline_start_description': {
                'ru': 'Открыть главное меню',
                'en': 'Open main menu'
            },
            # ====== ДЛЯ REPLY-КНОПКИ ======
            'start_button': {
                'ru': '🚀 Restart / Menu',
                'en': '🚀 Restart / Menu'
            }
        }
        
        return translations.get(key, {}).get(lang, key)

# ====== КЛАСС ДЛЯ УПРАВЛЕНИЯ ЗАДАЧАМИ НАПОМИНАНИЙ ======
class ReminderManager:
    """Менеджер для управления напоминаниями и таймерами"""
    
    def __init__(self):
        self.pending_reminders = {}
        self.final_reminders = {}
        self.reminder_tasks = {}
    
    def add_reminder(self, doc_id: str, user_id: int, comment_time: datetime, comment_text: str, user_info: Dict):
        """Добавляет задачу напоминания"""
        reminder_key = f"{doc_id}_{user_id}"
        
        # Вычисляем время напоминания (5 минут)
        reminder_time = comment_time + timedelta(seconds=COMMENT_REMINDER_TIME)
        
        self.pending_reminders[reminder_key] = {
            'doc_id': doc_id,
            'user_id': user_id,
            'comment_time': comment_time,
            'reminder_time': reminder_time,
            'comment_text': comment_text,
            'user_info': user_info,
            'reminder_sent': False
        }
        
        logger.info(f"⏰ Добавлено напоминание для {user_id} по документу {doc_id} на {reminder_time}")
    
    def add_final_reminder(self, doc_id: str, user_id: int, comment_time: datetime, comment_text: str, user_info: Dict):
        """Добавляет задачу финального напоминания"""
        reminder_key = f"{doc_id}_{user_id}"
        
        # Вычисляем время финального напоминания (10 минут)
        final_time = comment_time + timedelta(seconds=FINAL_REMINDER_TIME)
        
        self.final_reminders[reminder_key] = {
            'doc_id': doc_id,
            'user_id': user_id,
            'comment_time': comment_time,
            'final_time': final_time,
            'comment_text': comment_text,
            'user_info': user_info,
            'final_sent': False
        }
        
        logger.info(f"⚠️ Добавлено финальное напоминание для {user_id} по документу {doc_id} на {final_time}")
    
    def remove_reminder(self, doc_id: str, user_id: int):
        """Удаляет задачу напоминания"""
        reminder_key = f"{doc_id}_{user_id}"
        
        if reminder_key in self.pending_reminders:
            del self.pending_reminders[reminder_key]
            logger.info(f"✅ Удалено напоминание для {user_id} по документу {doc_id}")
        
        if reminder_key in self.final_reminders:
            del self.final_reminders[reminder_key]
            logger.info(f"✅ Удалено финальное напоминание для {user_id} по документу {doc_id}")
        
        # Останавливаем задачи если они есть
        if reminder_key in self.reminder_tasks:
            task = self.reminder_tasks[reminder_key]
            if not task.done():
                task.cancel()
            del self.reminder_tasks[reminder_key]
    
    def get_pending_reminders(self) -> List[Dict]:
        """Получает список ожидающих напоминаний"""
        return list(self.pending_reminders.values())
    
    def get_final_reminders(self) -> List[Dict]:
        """Получает список ожидающих финальных напоминаний"""
        return list(self.final_reminders.values())
    
    async def start_reminder_checker(self, bot_instance):
        """Запускает проверщик напоминаний"""
        logger.info("⏰ Запуск системы напоминаний...")
        
        while True:
            try:
                current_time = datetime.now()
                
                # Проверяем обычные напоминания
                for reminder_key, reminder in list(self.pending_reminders.items()):
                    if not reminder['reminder_sent'] and current_time >= reminder['reminder_time']:
                        # Отправляем напоминание
                        await self.send_reminder(bot_instance, reminder)
                        reminder['reminder_sent'] = True
                        
                        # Запускаем финальное напоминание через 5 минут
                        await asyncio.sleep(COMMENT_REMINDER_TIME)
                        
                        # Проверяем, не принято ли решение за это время
                        if reminder_key in self.pending_reminders:
                            await self.send_final_reminder(bot_instance, reminder)
                            reminder['final_sent'] = True
                
                # Проверяем финальные напоминания (на всякий случай)
                for reminder_key, reminder in list(self.final_reminders.items()):
                    if not reminder['final_sent'] and current_time >= reminder['final_time']:
                        await self.send_final_reminder(bot_instance, reminder)
                        reminder['final_sent'] = True
                
                await asyncio.sleep(10)  # Проверяем каждые 10 секунд
                
            except Exception as e:
                logger.error(f"❌ Ошибка в системе напоминаний: {e}")
                await asyncio.sleep(30)
    
    async def send_reminder(self, bot_instance, reminder: Dict):
        """Отправляет напоминание пользователю"""
        try:
            doc_id = reminder['doc_id']
            user_id = reminder['user_id']
            comment_text = reminder['comment_text']
            
            lang = bot_instance.get_user_language(user_id)
            
            # Отправляем напоминание пользователю
            await bot_instance.application.bot.send_message(
                chat_id=user_id,
                text=Translations.get('comment_reminder', lang),
                parse_mode='Markdown'
            )
            
            logger.info(f"⏰ Отправлено напоминание пользователю {user_id} по документу {doc_id}")
            
            # Отправляем уведомление администратору
            user_info = reminder['user_info']
            user_identifier = user_info.get('identifier', f"ID: {user_id}")
            comment_time_str = reminder['comment_time'].strftime('%H:%M %d.%m.%Y')
            
            admin_message = Translations.get('comment_without_decision_admin', 'ru').format(
                user_info=user_identifier,
                doc_id=doc_id,
                comment=comment_text,
                time=comment_time_str
            )
            
            await bot_instance.application.bot.send_message(
                chat_id=DEVELOPER_ADMIN_ID,
                text=admin_message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки напоминания: {e}")
    
    async def send_final_reminder(self, bot_instance, reminder: Dict):
        """Отправляет финальное напоминание пользователю"""
        try:
            doc_id = reminder['doc_id']
            user_id = reminder['user_id']
            comment_text = reminder['comment_text']
            user_info = reminder['user_info']
            
            lang = bot_instance.get_user_language(user_id)
            
            # Отправляем финальное напоминание пользователю
            final_message = Translations.get('final_reminder', lang).format(
                comment=comment_text
            )
            
            await bot_instance.application.bot.send_message(
                chat_id=user_id,
                text=final_message,
                parse_mode='Markdown'
            )
            
            logger.info(f"⚠️ Отправлено финальное напоминание пользователю {user_id} по документу {doc_id}")
            
            # Отправляем уведомление администратору о том, что пользователь оставил только комментарий
            user_identifier = user_info.get('identifier', f"ID: {user_id}")
            comment_time = reminder['comment_time']
            current_time = datetime.now()
            elapsed_minutes = (current_time - comment_time).total_seconds() / 60
            comment_time_str = comment_time.strftime('%H:%M %d.%m.%Y')
            
            admin_message = Translations.get('comment_only_admin', 'ru').format(
                user_info=user_identifier,
                doc_id=doc_id,
                comment=comment_text,
                time=comment_time_str,
                elapsed_time=f"{elapsed_minutes:.1f} минут"
            )
            
            await bot_instance.application.bot.send_message(
                chat_id=DEVELOPER_ADMIN_ID,
                text=admin_message,
                parse_mode='Markdown'
            )
            
            # Обновляем статус в базе данных
            await bot_instance.update_comment_only_status(doc_id, user_id, comment_text)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки финального напоминания: {e}")

# ====== КЛАСС ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ С РЕТРАЯМИ ======
class DatabaseManager:
    """Менеджер для работы с базой данных с ретраями"""
    
    @staticmethod
    @contextmanager
    def db_connection(db_path, timeout=60, retries=3):
        """Контекстный менеджер для работы с базой данных с ретраями"""
        delay = 1
        
        for attempt in range(retries):
            try:
                conn = sqlite3.connect(db_path, timeout=timeout)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=60000")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=10000")
                yield conn
                conn.close()
                return
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retries - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
                else:
                    raise

    @staticmethod
    def optimize_database(db_path):
        """Оптимизация базы данных"""
        try:
            with DatabaseManager.db_connection(db_path) as conn:
                # Оптимизация базы
                conn.execute("PRAGMA optimize")
                conn.execute("PRAGMA vacuum")  # Дефрагментация базы
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                logger.info("✅ База данных оптимизирована")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось оптимизировать базу: {e}")

# ====== КЛАСС ДЛЯ АВТОМАТИЧЕСКОЙ ОТПРАВКИ (ОБНОВЛЕННЫЙ) ======
class IntegratedAdminSender:
    """Интегрированное решение для отправки от имени админа"""
    
    def __init__(self, db_path: str, admin_phone: str):
        self.db_path = db_path
        self.admin_phone = admin_phone
        self.client = None
        self.running = False
        self.bot_username = None
        
        # Telegram API credentials come from the local environment.
        self.API_ID = settings.api_id
        self.API_HASH = settings.api_hash
        
        # Создаем таблицы если не существуют
        self._init_tables()
    
    def _init_tables(self):
        """Создаем необходимые таблицы в базе"""
        with DatabaseManager.db_connection(self.db_path) as conn:
            c = conn.cursor()
            
            # Таблица для очереди сообщений
            c.execute('''CREATE TABLE IF NOT EXISTS message_queue (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL,
                        message TEXT NOT NULL,
                        doc_id TEXT NOT NULL,
                        identifier_type TEXT DEFAULT 'username',
                        status TEXT DEFAULT 'pending',
                        error_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        sent_at TIMESTAMP
                    )''')
            
            # Таблица для информации о боте
            c.execute('''CREATE TABLE IF NOT EXISTS bot_info (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        username TEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
            
            # Таблица для логов отправки на телефоны
            c.execute('''CREATE TABLE IF NOT EXISTS phone_sending_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        phone TEXT NOT NULL,
                        doc_id TEXT NOT NULL,
                        method TEXT NOT NULL,
                        status TEXT NOT NULL,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
            
            conn.commit()
        logger.info("✅ Таблицы для автоматической отправки созданы")
    
    async def initialize(self, bot_username: str):
        """Инициализация отправителя"""
        try:
            self.bot_username = bot_username
            
            # Сохраняем username бота в базу
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''INSERT OR REPLACE INTO bot_info (id, username) 
                            VALUES (1, ?)''', (bot_username,))
                conn.commit()
            
            # Создаем клиент Telegram
            self.client = TelegramClient(
                'admin_session',
                self.API_ID,
                self.API_HASH
            )
            
            # Подключаемся к аккаунту админа
            print(f"📱 Подключение к аккаунту {self.admin_phone}...")
            print("⚠️ При первом запуске потребуется ввести код из Telegram")
            
            await self.client.start(phone=self.admin_phone)
            
            print(f"✅ Отправитель инициализирован для {self.admin_phone}")
            self.running = True
            
            # Запускаем фоновую задачу обработки очереди
            asyncio.create_task(self._process_queue_loop())
            
            # Запускаем периодическую оптимизацию базы
            asyncio.create_task(self._optimize_database_periodically())
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации отправителя: {e}")
            return False
    
    async def _optimize_database_periodically(self):
        """Периодическая оптимизация базы данных"""
        while True:
            await asyncio.sleep(3600)  # Каждый час
            
            try:
                DatabaseManager.optimize_database(self.db_path)
                logger.info("✅ База данных оптимизирована")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось оптимизировать базу: {e}")
    
    async def send_invitation_to_username(self, username: str, doc_id: str, file_name: str, file_count: int) -> Dict:
        """Отправляет приглашение пользователю по username от лица админа"""
        try:
            deep_link = f"https://t.me/{self.bot_username}?start=doc_{doc_id}"
            
            # Текст сообщения
            file_text = f"{file_count} документов" if file_count > 1 else "документ"
            message = (
                f"👋 Здравствуйте!\n\n"
                f"📄 **Вам отправлен {file_text} для согласования:**\n"
                f"**{file_name}**\n"
                f"{f'📚 Всего файлов: {file_count}' if file_count > 1 else ''}\n\n"
                f"Для просмотра и подписания перейдите по ссылке:\n"
                f"{deep_link}\n\n"
                f"🔗 **Ссылка активна 7 дней.**\n"
                f"После первого входа все документы будут приходить автоматически.\n\n"
                f"💡 **Как это работает:**\n"
                f"1. Нажмите на ссылку выше\n"
                f"2. Откроется бот с документами\n"
                f"3. Вы сможете их просмотреть и согласовать\n"
                f"4. После этого все будущие документы будут приходить автоматически"
            )
            
            # Отправляем сообщение
            clean_username = username.lstrip('@')
            await self.client.send_message(clean_username, message)
            
            logger.info(f"✅ Приглашение отправлено @{clean_username}")
            
            return {
                'success': True,
                'message': f"✅ Приглашение отправлено @{username}",
                'method': 'admin_direct',
                'deep_link': deep_link
            }
            
        except FloodWaitError as e:
            logger.warning(f"⏳ Требуется ожидание {e.seconds} секунд для @{username}")
            return {
                'success': False,
                'message': f"⏳ Требуется ожидание {e.seconds} секунд",
                'method': 'flood_wait'
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки @{username}: {e}")
            
            # Если ошибка "User not found" или "Cannot send message"
            error_msg = str(e).lower()
            if 'user not found' in error_msg or 'cannot send message' in error_msg or 'username not found' in error_msg:
                return {
                    'success': False,
                    'message': f"❌ Не удалось отправить @{username}",
                    'method': 'error',
                    'deep_link': deep_link,
                    'error': str(e)
                }
            else:
                return {
                    'success': False,
                    'message': f"❌ Ошибка: {str(e)[:50]}",
                    'method': 'error'
                }

    async def send_invitation_to_phone(self, phone: str, doc_id: str, file_name: str, file_count: int, theme: str = None) -> Dict:
        """Отправляет приглашение пользователю по телефону от лица админа"""
        try:
            deep_link = f"https://t.me/{self.bot_username}?start=doc_{doc_id}"
            
            # Текст сообщения
            file_text = f"{file_count} документов" if file_count > 1 else "документ"
            
            # ===== ФОРМИРУЕМ ТЕКСТ С ТЕМОЙ =====
            theme_line = ""
            if theme:
                theme_line = f"📌 **Тема:** {theme}\n\n"
            
            # Формируем сообщение с темой
            message = (
                f"👋 Здравствуйте!\n\n"
                f"{theme_line}"
                f"📄 **Вам отправлен {file_text} для согласования:**\n"
                f"**{file_name}**\n"
                f"{f'📚 Всего файлов: {file_count}' if file_count > 1 else ''}\n\n"
                f"Для просмотра и подписания перейдите по ссылке:\n"
                f"{deep_link}\n\n"
                f"📱 **Ваш телефон:** {phone}\n\n"
                f"🔗 **Ссылка активна 7 дней.**\n"
                f"После первого входа все документы будут приходить автоматически.\n\n"
                f"💡 **Как это работает:**\n"
                f"1. Нажмите на ссылку выше\n"
                f"2. Откроется бот с документами\n"
                f"3. Вы сможете их просмотреть и согласовать\n"
                f"4. После этого все будущие документы будут приходить автоматически"
            )
            
            # Пытаемся отправить автоматически
            auto_result = await self._try_auto_send_to_phone(phone, message, doc_id)
            
            if auto_result['success']:
                logger.info(f"✅ Приглашение отправлено на {phone}")
                return {
                    'success': True,
                    'message': f"✅ Приглашение отправлено на {phone}",
                    'method': auto_result['method'],
                    'note': auto_result.get('note', ''),
                    'deep_link': deep_link
                }
            else:
                return {
                    'success': False,
                    'message': f"❌ Не удалось отправить автоматически на {phone}",
                    'method': 'error',
                    'deep_link': deep_link,
                    'note': auto_result.get('note', 'Требуется ручная отправка')
                }
                
        except FloodWaitError as e:
            logger.warning(f"⏳ Требуется ожидание {e.seconds} секунд для {phone}")
            return {
                'success': False,
                'message': f"⏳ Требуется ожидание {e.seconds} секунд",
                'method': 'flood_wait'
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки на {phone}: {e}")
            return {
                'success': False,
                'message': f"❌ Ошибка: {str(e)[:50]}",
                'method': 'error'
            }

    async def _try_auto_send_to_phone(self, phone: str, message: str, doc_id: str) -> Dict:
        """Пытается автоматически отправить сообщение на телефон"""
        retry_count = 3
        retry_delay = 1
        
        for attempt in range(retry_count):
            try:
                phone_clean = phone.lstrip('+')
                
                # Метод 1: Пробуем найти пользователя по номеру в Telegram
                try:
                    logger.info(f"🔍 Пробуем найти пользователя в Telegram: {phone}")
                    # Пробуем получить информацию о пользователе по номеру
                    user = await self.client.get_entity(phone)
                    
                    if user:
                        logger.info(f"✅ Пользователь найден в Telegram: {phone}")
                        # Отправляем сообщение
                        await self.client.send_message(user, message)
                        
                        # Сохраняем в лог
                        self._save_phone_sending_log(phone, doc_id, 'telegram_direct', 'sent')
                        
                        return {
                            'success': True,
                            'method': 'telegram_direct',
                            'note': f'Сообщение отправлено напрямую в Telegram на {phone}'
                        }
                        
                except (ValueError, TypeError) as e:
                    logger.info(f"📞 {phone} не найден в базе Telegram: {e}")
                    
                # Метод 2: Пробуем отправить по номеру напрямую
                try:
                    logger.info(f"📤 Пробуем отправить по номеру напрямую: {phone}")
                    # Отправляем сообщение напрямую по номеру
                    await self.client.send_message(phone, message)
                    
                    self._save_phone_sending_log(phone, doc_id, 'phone_direct', 'sent')
                    
                    return {
                        'success': True,
                        'method': 'phone_direct',
                        'note': f'Сообщение отправлено по номеру {phone}'
                    }
                    
                except Exception as direct_error:
                    logger.warning(f"❌ Не удалось отправить на {phone} напрямую: {direct_error}")
                    
                # Метод 3: Пробуем импортировать контакт и отправить
                try:
                    logger.info(f"👤 Пробуем импортировать контакт: {phone}")
                    # Генерируем уникальный client_id
                    client_id = random.randint(0, 10000)
                    
                    # Создаем контакт
                    contact = InputPhoneContact(
                        client_id=client_id,
                        phone=phone_clean,
                        first_name="Пользователь",
                        last_name=f"Док {doc_id[:8]}"
                    )
                    
                    # Импортируем контакт
                    result = await self.client(ImportContactsRequest([contact]))
                    
                    if result.users:
                        logger.info(f"✅ Контакт импортирован: {phone}")
                        # Отправляем сообщение новому контакту
                        user = result.users[0]
                        await self.client.send_message(user, message)
                        
                        # Удаляем контакт, чтобы не засорять список
                        try:
                            await self.client(DeleteContactsRequest([user]))
                        except:
                            pass
                        
                        self._save_phone_sending_log(phone, doc_id, 'telegram_new_contact', 'sent')
                        
                        return {
                            'success': True,
                            'method': 'telegram_new_contact',
                            'note': f'Контакт добавлен и сообщение отправлено'
                        }
                        
                except Exception as import_error:
                    logger.warning(f"❌ Не удалось добавить контакт {phone}: {import_error}")
            
            except Exception as e:
                logger.error(f"❌ Ошибка автоматической отправки на {phone} (попытка {attempt + 1}): {e}")
            
            # Задержка между попытками
            if attempt < retry_count - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
        
        # Если все попытки не удались
        self._save_phone_sending_log(phone, doc_id, 'failed', 'error', 'Все попытки отправки не удались')
        return {
            'success': False,
            'method': 'error',
            'note': 'Требуется ручная отправка'
        }

    def _save_phone_sending_log(self, phone: str, doc_id: str, method: str, status: str, error_message: str = None):
        """Сохраняет лог отправки на телефон"""
        with DatabaseManager.db_connection(self.db_path) as conn:
            c = conn.cursor()
            
            c.execute('''INSERT INTO phone_sending_logs 
                        (phone, doc_id, method, status, error_message)
                        VALUES (?, ?, ?, ?, ?)''',
                     (phone, doc_id, method, status, error_message))
            
            conn.commit()
    
    async def _process_queue_loop(self):
        """Фоновая задача для обработки очереди"""
        logger.info("🚀 Фоновая обработка очереди запущена")
        
        while self.running:
            try:
                # Проверяем есть ли сообщения в очереди
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    c.execute('''SELECT id, username, message, doc_id, identifier_type
                                FROM message_queue 
                                WHERE status = 'pending'
                                AND identifier_type = 'username'  
                                ORDER BY created_at ASC
                                LIMIT 5''')
                    
                    pending_messages = c.fetchall()
                
                if pending_messages:
                    logger.info(f"📋 Найдено {len(pending_messages)} сообщений в очереди")
                
                for msg_id, username, message, doc_id, identifier_type in pending_messages:
                    success = await self._send_single_message(
                        username=username,
                        message=message,
                        msg_id=msg_id,
                        doc_id=doc_id
                    )
                    
                    if not success:
                        # Если ошибка, ждем перед следующей попыткой
                        await asyncio.sleep(5)
                
                # Пауза между проверками очереди
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в обработке очереди: {e}")
                await asyncio.sleep(10)
    
    async def _send_single_message(self, username: str, message: str, 
                                  msg_id: int, doc_id: str) -> bool:
        """Отправка одного сообщения"""
        retry_count = 3
        retry_delay = 1
        
        for attempt in range(retry_count):
            try:
                # Убираем @ из username если есть
                clean_username = username.lstrip('@')
                
                logger.info(f"📤 Отправка сообщения @{clean_username}...")
                
                # Отправляем сообщение
                await self.client.send_message(clean_username, message)
                
                logger.info(f"✅ Сообщение отправлено @{clean_username}")
                
                # Обновляем статус в базе
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # Обновляем очередь
                    c.execute('''UPDATE message_queue 
                                SET status = 'sent',
                                    sent_at = CURRENT_TIMESTAMP
                                WHERE id = ?''', (msg_id,))
                    
                    # Обновляем таблицу recipients
                    c.execute('''UPDATE recipients 
                                SET sent_via = 'admin_auto',
                                    status = 'invitation_sent'
                                WHERE identifier_value = ?
                                AND doc_id = ?''',
                             (username, doc_id))
                    
                    conn.commit()
                
                return True
                
            except FloodWaitError as e:
                logger.warning(f"⏳ Требуется ожидание {e.seconds} секунд...")
                await asyncio.sleep(e.seconds)
                return False
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retry_count - 1:
                    logger.warning(f"База заблокирована при отправке @{username}, попытка {attempt + 1}")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error(f"❌ Ошибка базы данных @{username}: {e}")
                    
                    # Увеличиваем счетчик ошибок
                    with DatabaseManager.db_connection(self.db_path) as conn:
                        c = conn.cursor()
                        c.execute('''UPDATE message_queue 
                                    SET error_count = error_count + 1
                                    WHERE id = ?''', (msg_id,))
                        conn.commit()
                    
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Ошибка отправки @{username}: {e}")
                
                # Увеличиваем счетчик ошибок
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    c.execute('''UPDATE message_queue 
                                SET error_count = error_count + 1
                                WHERE id = ?''', (msg_id,))
                    conn.commit()
                
                return False
    
    async def get_stats(self):
        """Получение статистики очереди"""
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                c.execute('''SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                            SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
                            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                            FROM message_queue''')
                
                stats = c.fetchone()
            
            if stats:
                return {
                    'total': stats[0] or 0,
                    'pending': stats[1] or 0,
                    'sent': stats[2] or 0,
                    'failed': stats[3] or 0
                }
            
            return {'total': 0, 'pending': 0, 'sent': 0, 'failed': 0}
            
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {'total': 0, 'pending': 0, 'sent': 0, 'failed': 0}

# ====== ОСНОВНОЙ КЛАСС БОТА С ИНТЕГРАЦИЕЙ (ОБНОВЛЕННЫЙ) ======
class UniversalContactBot:
    def __init__(self):
        self.db_path = os.getenv("CONTACTS_DB_PATH", "universal_contacts.db")
        self.init_db()
        self.admin_sender = None
        self.bot_username = None
        self.reminder_manager = ReminderManager()
        self.application = None  # Будет установлен позже
        self.reminder_task = None
    
    def init_db(self):
        """Инициализация базы данных - ТОЛЬКО ТЕЛЕФОНЫ"""
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # ========== 1. СОЗДАЕМ ТАБЛИЦЫ ==========
                
                # Таблица контактов - ТОЛЬКО ТЕЛЕФОНЫ, username опциональный
                c.execute('''CREATE TABLE IF NOT EXISTS contacts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            phone TEXT UNIQUE,
                            username TEXT,
                            telegram_id INTEGER UNIQUE,
                            name TEXT,
                            first_activation TIMESTAMP,
                            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )''')
                logger.info("✅ Таблица contacts создана/проверена")
                
                # Таблица документов
                c.execute('''CREATE TABLE IF NOT EXISTS documents (
                            id TEXT PRIMARY KEY,
                            admin_id INTEGER,
                            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            status TEXT DEFAULT 'active'
                        )''')
                logger.info("✅ Таблица documents создана/проверена")
                
                # Таблица файлов документов
                c.execute('''CREATE TABLE IF NOT EXISTS document_files (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            doc_id TEXT NOT NULL,
                            file_id TEXT NOT NULL,
                            file_name TEXT,
                            file_order INTEGER DEFAULT 1,
                            FOREIGN KEY(doc_id) REFERENCES documents(id)
                        )''')
                logger.info("✅ Таблица document_files создана/проверена")
                
                # Таблица получателей
                c.execute('''CREATE TABLE IF NOT EXISTS recipients (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            doc_id TEXT,
                            contact_id INTEGER,
                            identifier_type TEXT,
                            identifier_value TEXT,
                            status TEXT DEFAULT 'pending',
                            comment TEXT,
                            comment_only BOOLEAN DEFAULT FALSE,
                            response_time TIMESTAMP,
                            sent_via TEXT DEFAULT 'direct',
                            notification_sent BOOLEAN DEFAULT FALSE,
                            FOREIGN KEY(doc_id) REFERENCES documents(id),
                            FOREIGN KEY(contact_id) REFERENCES contacts(id)
                        )''')
                logger.info("✅ Таблица recipients создана/проверена")
                
                # Таблица языков пользователей
                c.execute('''CREATE TABLE IF NOT EXISTS user_languages (
                            user_id INTEGER PRIMARY KEY,
                            language TEXT DEFAULT 'ru',
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )''')
                logger.info("✅ Таблица user_languages создана/проверена")
                
                # Таблица для хранения напоминаний
                c.execute('''CREATE TABLE IF NOT EXISTS comment_reminders (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            doc_id TEXT NOT NULL,
                            user_id INTEGER NOT NULL,
                            comment TEXT,
                            comment_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            reminder_sent BOOLEAN DEFAULT FALSE,
                            final_reminder_sent BOOLEAN DEFAULT FALSE,
                            decision_made BOOLEAN DEFAULT FALSE,
                            FOREIGN KEY(doc_id) REFERENCES documents(id)
                        )''')
                logger.info("✅ Таблица comment_reminders создана/проверена")
                
                # Таблица для очереди сообщений
                c.execute('''CREATE TABLE IF NOT EXISTS message_queue (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT NOT NULL,
                            message TEXT NOT NULL,
                            doc_id TEXT NOT NULL,
                            identifier_type TEXT DEFAULT 'username',
                            status TEXT DEFAULT 'pending',
                            error_count INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            sent_at TIMESTAMP
                        )''')
                logger.info("✅ Таблица message_queue создана/проверена")
                
                # Таблица для информации о боте
                c.execute('''CREATE TABLE IF NOT EXISTS bot_info (
                            id INTEGER PRIMARY KEY CHECK (id = 1),
                            username TEXT NOT NULL,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )''')
                logger.info("✅ Таблица bot_info создана/проверена")

                c.execute('''CREATE TABLE IF NOT EXISTS user_roles (
                            user_id INTEGER PRIMARY KEY,
                            role TEXT DEFAULT 'user',
                            is_admin BOOLEAN DEFAULT FALSE,
                            can_send_docs BOOLEAN DEFAULT FALSE,
                            can_manage_contacts BOOLEAN DEFAULT FALSE,
                            can_view_reports BOOLEAN DEFAULT FALSE,
                            auto_send_enabled BOOLEAN DEFAULT FALSE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )''')
    
                # Таблица для связи с сессиями авторизации
                c.execute('''CREATE TABLE IF NOT EXISTS admin_sessions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER UNIQUE,
                            phone TEXT,
                            session_string TEXT,
                            is_active BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY(user_id) REFERENCES user_roles(user_id)
                        )''')
    
                # Таблица для приглашений новых админов
                c.execute('''CREATE TABLE IF NOT EXISTS admin_invites (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            invited_by INTEGER,
                            invite_code TEXT UNIQUE,
                            phone TEXT,
                            role TEXT DEFAULT 'admin',
                            status TEXT DEFAULT 'pending',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            expires_at TIMESTAMP,
                            used_at TIMESTAMP,
                            FOREIGN KEY(invited_by) REFERENCES user_roles(user_id)
                        )''')
    
                # Добавляем суперадмина (разработчика)
                c.execute('''INSERT OR IGNORE INTO user_roles 
                            (user_id, role, is_admin, can_send_docs, can_manage_contacts, can_view_reports, auto_send_enabled)
                            VALUES (?, 'super_admin', TRUE, TRUE, TRUE, TRUE, TRUE)''', 
                            (DEVELOPER_ADMIN_ID,))

                # Таблица для логов отправки на телефоны
                c.execute('''CREATE TABLE IF NOT EXISTS phone_sending_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            phone TEXT NOT NULL,
                            doc_id TEXT NOT NULL,
                            method TEXT NOT NULL,
                            status TEXT NOT NULL,
                            error_message TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )''')
                logger.info("✅ Таблица phone_sending_logs создана/проверена")
                
                # ========== 2. ПРОВЕРЯЕМ И ДОБАВЛЯЕМ ПОЛЯ ЕСЛИ НУЖНО ==========
                
                # Проверяем структуру таблицы contacts
                c.execute("PRAGMA table_info(contacts)")
                contacts_columns = [col[1] for col in c.fetchall()]
                logger.info(f"📊 Структура contacts: {contacts_columns}")
                
                # Добавляем поле first_activation если его нет
                if 'first_activation' not in contacts_columns:
                    try:
                        c.execute('ALTER TABLE contacts ADD COLUMN first_activation TIMESTAMP')
                        logger.info("✅ Добавлено поле first_activation в таблицу contacts")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось добавить поле first_activation: {e}")
                
                # Проверяем структуру таблицы recipients
                c.execute("PRAGMA table_info(recipients)")
                recipients_columns = [col[1] for col in c.fetchall()]
                logger.info(f"📊 Структура recipients: {recipients_columns}")
                
                # Добавляем поле comment_only если его нет
                if 'comment_only' not in recipients_columns:
                    try:
                        c.execute('ALTER TABLE recipients ADD COLUMN comment_only BOOLEAN DEFAULT FALSE')
                        logger.info("✅ Добавлено поле comment_only в таблицу recipients")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось добавить поле comment_only: {e}")
                
                # ========== 3. СОЗДАЕМ ИНДЕКСЫ ==========
                try:
                    # Индексы для contacts
                    c.execute('CREATE INDEX IF NOT EXISTS idx_contacts_telegram ON contacts(telegram_id)')
                    c.execute('CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone)')
                    
                    # Индекс для username (опционально, может быть NULL)
                    c.execute('CREATE INDEX IF NOT EXISTS idx_contacts_username ON contacts(username)')
                    
                    # Индексы для recipients
                    c.execute('CREATE INDEX IF NOT EXISTS idx_recipients_doc_id ON recipients(doc_id)')
                    c.execute('CREATE INDEX IF NOT EXISTS idx_recipients_contact_id ON recipients(contact_id)')
                    
                    # Индекс для document_files
                    c.execute('CREATE INDEX IF NOT EXISTS idx_document_files_doc_id ON document_files(doc_id)')
                    
                    logger.info("✅ Индексы созданы/обновлены")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось создать индексы: {e}")
                
                conn.commit()
                logger.info("✅ База данных инициализирована успешно")
                
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Ошибка инициализации базы: {e}")
            # Пробуем с новым именем файла
            import time
            self.db_path = f"universal_contacts_{int(time.time())}.db"
            logger.info(f"🔄 Создаю новую базу: {self.db_path}")
            # Рекурсивный вызов с новым путем
            self.init_db()
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при инициализации базы: {e}")
            import time
            self.db_path = f"universal_contacts_{int(time.time())}.db"
            logger.info(f"🔄 Создаю новую базу: {self.db_path}")
            self.init_db()
        
        # ===== ВАЖНО: ОБНОВЛЯЕМ СХЕМУ БАЗЫ ДАННЫХ =====
        try:
            # Запускаем обновление схемы (синхронно)
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Если цикл уже запущен, создаем задачу
                asyncio.create_task(self.update_database_schema())
            else:
                # Если цикл не запущен, запускаем синхронно
                loop.run_until_complete(self.update_database_schema())
        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении схемы базы данных: {e}")
        
    def get_user_language(self, user_id: int) -> str:
            """Получаем язык пользователя"""
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    c.execute('SELECT language FROM user_languages WHERE user_id = ?', (user_id,))
                    result = c.fetchone()
                return result[0] if result else 'ru'
            except sqlite3.OperationalError:
                return 'ru'
        
        
    def get_user_language(self, user_id: int) -> str:
        """Получаем язык пользователя"""
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                c.execute('SELECT language FROM user_languages WHERE user_id = ?', (user_id,))
                result = c.fetchone()
            return result[0] if result else 'ru'
        except sqlite3.OperationalError:
            return 'ru'
        except Exception as e:
            logger.error(f"Ошибка получения языка пользователя: {e}")
            return 'ru'
        
    def add_start_button_to_keyboard(self, keyboard_buttons: List[List[InlineKeyboardButton]], user_id: int = None) -> InlineKeyboardMarkup:
        """Добавляет кнопку Start/Menu внизу клавиатуры"""
        if user_id == DEVELOPER_ADMIN_ID:
                callback_data = "menu_back"
        else:
            callback_data = "user_back_to_menu"
        
        # Добавляем кнопку внизу
        keyboard_buttons.append([InlineKeyboardButton(Translations.get('inline_start_button', self.get_user_language(user_id) if user_id else 'ru'), callback_data=callback_data)])
        
        return InlineKeyboardMarkup(keyboard_buttons)
    
    def get_reply_keyboard(self, user_id: int = None) -> ReplyKeyboardMarkup:
        """Создает Reply-клавиатуру с кнопкой Start"""
        lang = self.get_user_language(user_id) if user_id else 'ru'
        keyboard = [[KeyboardButton(Translations.get('start_button', lang))]]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    async def setup_bot_info(self, bot):
        """Получаем информацию о боте и настраиваем отправщика"""
        bot_info = await bot.get_me()
        self.bot_username = bot_info.username
        
        print(f"🤖 Username бота: @{self.bot_username}")
        print(f"🔗 Ссылка на бот: https://t.me/{self.bot_username}")
        
        # Проверяем, нужно ли настраивать отправщик
        if not self.admin_sender:
            print("\n" + "="*60)
            print("🤖 НАСТРОЙКА АВТОМАТИЧЕСКОЙ ОТПРАВКИ")
            print("="*60)

            print("💡 Автонастройка при старте отключена — номер телефона не запрашивается интерактивно.")
            print("💡 Настройте автоматическую отправку командой /setup_admin.")
        else:
            print("\n✅ Автоматическая отправка уже настроена")
            print(f"📱 Отправка от: {self.admin_sender.admin_phone}")
    
    async def start_reminder_system(self):
        """Запускает систему напоминаний"""
        if self.reminder_task is None:
            self.reminder_task = asyncio.create_task(
                self.reminder_manager.start_reminder_checker(self)
            )
            logger.info("⏰ Система напоминаний запущена")
    
    async def _show_stats_periodically(self):
        """Периодический показ статистики"""
        while True:
            await asyncio.sleep(60)
            
            if self.admin_sender:
                stats = await self.admin_sender.get_stats()
                if stats['total'] > 0:
                    print(f"\n📊 Статистика отправки: "
                          f"Всего: {stats['total']}, "
                          f"Ожидают: {stats['pending']}, "
                          f"Отправлено: {stats['sent']}, "
                          f"Ошибок: {stats['failed']}")
                    
    def cleanup_duplicate_contacts(self):
        """Очищает дубликаты контактов в базе данных"""
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # 1. Находим дубликаты по telegram_id
                c.execute('''SELECT telegram_id, COUNT(*) as cnt 
                        FROM contacts 
                        WHERE telegram_id IS NOT NULL 
                        GROUP BY telegram_id 
                        HAVING cnt > 1''')
                telegram_duplicates = c.fetchall()
                
                for telegram_id, count in telegram_duplicates:
                    logger.info(f"Найдено {count} дубликатов для telegram_id {telegram_id}")
                    # Оставляем первую запись, удаляем остальные
                    c.execute('''DELETE FROM contacts 
                            WHERE telegram_id = ? AND id NOT IN (
                                SELECT MIN(id) FROM contacts WHERE telegram_id = ?
                            )''', (telegram_id, telegram_id))
                
                # 2. Находим дубликаты по username
                c.execute('''SELECT username, COUNT(*) as cnt 
                        FROM contacts 
                        WHERE username IS NOT NULL AND username != ''
                        GROUP BY username 
                        HAVING cnt > 1''')
                username_duplicates = c.fetchall()
                
                for username, count in username_duplicates:
                    logger.info(f"Найдено {count} дубликатов для username {username}")
                    # Оставляем запись с telegram_id, если есть, иначе первую
                    c.execute('''DELETE FROM contacts 
                            WHERE username = ? AND id NOT IN (
                                SELECT COALESCE(
                                    MIN(CASE WHEN telegram_id IS NOT NULL THEN id END),
                                    MIN(id)
                                ) FROM contacts WHERE username = ?
                            )''', (username, username))
                
                # 3. Находим дубликаты по phone
                c.execute('''SELECT phone, COUNT(*) as cnt 
                        FROM contacts 
                        WHERE phone IS NOT NULL AND phone != ''
                        GROUP BY phone 
                        HAVING cnt > 1''')
                phone_duplicates = c.fetchall()
                
                for phone, count in phone_duplicates:
                    logger.info(f"Найдено {count} дубликатов для phone {phone}")
                    # Оставляем запись с telegram_id, если есть, иначе первую
                    c.execute('''DELETE FROM contacts 
                            WHERE phone = ? AND id NOT IN (
                                SELECT COALESCE(
                                    MIN(CASE WHEN telegram_id IS NOT NULL THEN id END),
                                    MIN(id)
                                ) FROM contacts WHERE phone = ?
                            )''', (phone, phone))
                
                conn.commit()
                logger.info("Очистка дубликатов завершена")
                
        except Exception as e:
            logger.error(f"Ошибка очистки дубликатов: {e}")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start - ИСПРАВЛЕННАЯ ВЕРСИЯ (единая активация)"""
        user_id = update.effective_user.id
        first_name = update.effective_user.first_name
        last_name = update.effective_user.last_name
        name = f"{first_name or ''} {last_name or ''}".strip()
        username = update.effective_user.username
        
        # Проверяем, есть ли аргументы (переход по ссылке)
        args = context.args
        if args:
            arg = args[0]
            if arg.startswith('doc_'):
                # Обрабатываем ссылку с документом
                await self.handle_document_link(update, arg, user_id, context)
                return
            elif arg.startswith('phone_'):
                # Обрабатываем ссылку с телефоном
                phone = arg.replace('phone_', '')
                
                # ✅ ЕДИНАЯ АКТИВАЦИЯ
                await self.activate_user(
                    user_id=user_id,
                    phone=phone,
                    username=username
                )
                
                # Показываем меню
                if user_id == DEVELOPER_ADMIN_ID:
                    await self.show_admin_menu(update, context)
                else:
                    await self.show_user_menu(update, first_name, context)
                return
        
        # ===== ОБЫЧНЫЙ START (без ссылки) =====
        
        # ✅ ВСЕГДА АКТИВИРУЕМ ЧЕРЕЗ ЕДИНЫЙ МЕТОД
        # Это безопасно - activate_user сам проверит существование контакта
        await self.activate_user(
            user_id=user_id,
            username=username
        )
        
        # Проверяем, есть ли ожидающие документы
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''
                    SELECT COUNT(*) FROM recipients r
                    JOIN contacts c ON r.contact_id = c.id
                    WHERE c.telegram_id = ? AND r.status = 'pending'
                ''', (user_id,))
                pending_count = c.fetchone()[0] or 0
        except:
            pending_count = 0
        
        # Проверяем, первый ли это вход
        with DatabaseManager.db_connection(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT first_activation FROM contacts WHERE telegram_id = ?', (user_id,))
            result = c.fetchone()
            is_first_activation = result and result[0] is not None and \
                                (datetime.now() - datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')).total_seconds() < 10
        
        # Формируем приветствие
        reply_keyboard = self.get_reply_keyboard(user_id)
        
        if is_first_activation:
            # Первый вход
            if pending_count > 0:
                welcome_message = (
                    f"👋 Добро пожаловать, {first_name}!\n\n"
                    f"✅ Ваш аккаунт активирован!\n\n"
                    f"📬 У вас уже есть {pending_count} документ(ов) для согласования\n\n"
                    f"Нажмите '📄 Мои документы' для просмотра"
                )
            else:
                welcome_message = (
                    f"👋 Добро пожаловать, {first_name}!\n\n"
                    f"✅ Ваш аккаунт активирован!\n\n"
                    f"📄 Теперь вы будете получать документы для согласования автоматически."
                )
            
            # Отправляем ожидающие документы
            await self.send_pending_documents_to_user(user_id)
        else:
            # Повторный вход
            if pending_count > 0:
                welcome_message = (
                    f"👋 С возвращением, {first_name}!\n\n"
                    f"📬 У вас есть {pending_count} документ(ов) для согласования\n\n"
                    f"Нажмите '📄 Мои документы' для просмотра"
                )
            else:
                welcome_message = (
                    f"👋 С возвращением, {first_name}!\n\n"
                    f"📄 Используйте меню для работы с документами"
                )
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=reply_keyboard
        )
        
        # Показываем меню
        if user_id == DEVELOPER_ADMIN_ID:
            await self.show_admin_menu(update, context)
        else:
            await self.show_user_menu(update, first_name, context)

    async def send_final_report_to_admin(self, doc_id: str):
        """Отправляет финальный отчет по документу администратору"""
        try:
            logger.info(f"📊 Начинаю формирование финального отчета для документа {doc_id}")
            
            # Проверяем, не отправляли ли уже финальный отчет
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Проверяем, был ли уже отправлен финальный отчет
                try:
                    c.execute('SELECT final_report_sent FROM documents WHERE id = ?', (doc_id,))
                    result = c.fetchone()
                    if result and result[0] == 1:
                        logger.info(f"📊 Финальный отчет для документа {doc_id} уже был отправлен")
                        return
                except:
                    # Если поля нет - игнорируем
                    pass
                
                # Получаем информацию о документе с темой
                c.execute('''SELECT d.created, d.theme,
                            GROUP_CONCAT(df.file_name, '\n') as files
                            FROM documents d
                            LEFT JOIN document_files df ON d.id = df.doc_id
                            WHERE d.id = ?''', (doc_id,))
                
                doc_info = c.fetchone()
                
                if not doc_info:
                    logger.error(f"❌ Документ {doc_id} не найден для финального отчета")
                    await self.application.bot.send_message(
                        chat_id=DEVELOPER_ADMIN_ID,
                        text=f"❌ Не удалось сформировать отчет по документу {doc_id}: документ не найден"
                    )
                    return
                
                created, theme, files = doc_info
                
                # Безопасное парсинг даты
                if created:
                    try:
                        created_dt = datetime.strptime(created, '%Y-%m-%d %H:%M:%S')
                        created_str = created_dt.strftime('%d.%m.%Y %H:%M:%S')
                    except:
                        created_str = "Неизвестно"
                else:
                    created_str = "Неизвестно"
                
                # Получаем детальную информацию о получателях
                c.execute('''SELECT c.name, c.phone, c.username, c.telegram_id,
                            r.status, r.comment, r.response_time, r.sent_via,
                            r.comment_only
                            FROM recipients r
                            LEFT JOIN contacts c ON r.contact_id = c.id
                            WHERE r.doc_id = ?
                            ORDER BY 
                                CASE r.status 
                                    WHEN 'approved' THEN 1
                                    WHEN 'rejected' THEN 2
                                    WHEN 'pending' THEN 3
                                    ELSE 4
                                END,
                                c.name''', (doc_id,))
                
                recipients = c.fetchall()
                
                if not recipients:
                    logger.error(f"❌ Нет получателей для документа {doc_id}")
                    await self.application.bot.send_message(
                        chat_id=DEVELOPER_ADMIN_ID,
                        text=f"❌ Не удалось сформировать отчет по документу {doc_id}: нет получателей"
                    )
                    return
                
                # Получаем статистику
                c.execute('''SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                            SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                            SUM(CASE WHEN comment_only = 1 THEN 1 ELSE 0 END) as comment_only,
                            SUM(CASE WHEN sent_via IS NOT NULL THEN 1 ELSE 0 END) as sent_count
                            FROM recipients WHERE doc_id = ?''', (doc_id,))
                
                stats = c.fetchone()
                total, approved, rejected, pending, comment_only, sent_count = stats if stats else (0, 0, 0, 0, 0, 0)
                
                logger.info(f"📊 Статистика для документа {doc_id}: всего={total}, согласовано={approved}, отклонено={rejected}, ожидает={pending}")
                
                # ===== ВАЖНО: Проверяем, все ли действительно ответили =====
                if pending > 0:
                    logger.info(f"⏳ Еще есть ожидающие ({pending}), финальный отчет не отправляется")
                    return
                
                # ===== ФОРМИРУЕМ ФИНАЛЬНЫЙ ОТЧЕТ БЕЗ MARKDOWN =====
                report_lines = []
                
                report_lines.append("📊 ФИНАЛЬНЫЙ ОТЧЕТ ПО ДОКУМЕНТУ")
                report_lines.append("")
                report_lines.append(f"🆔 ID документа: {doc_id}")
                
                # Добавляем тему если есть - ЭКРАНИРУЕМ
                if theme:
                    safe_theme = self.escape_markdown(theme)
                    report_lines.append(f"📌 Тема: {safe_theme}")
                
                report_lines.append(f"📅 Дата создания: {created_str}")
                report_lines.append("")
                
                if files:
                    file_list = files.split('\n')
                    report_lines.append(f"📄 Файлы ({len(file_list)}):")
                    for i, file_name in enumerate(file_list, 1):
                        # Экранируем имя файла
                        safe_file_name = self.escape_markdown(file_name)
                        report_lines.append(f"{i}. {safe_file_name}")
                    report_lines.append("")
                
                report_lines.append("📈 СТАТИСТИКА СОГЛАСОВАНИЯ:")
                report_lines.append("─" * 40)
                report_lines.append("")
                
                report_lines.append(f"👥 Всего получателей: {total}")
                report_lines.append(f"✅ Согласовано: {approved}")
                report_lines.append(f"❌ Отклонено: {rejected}")
                report_lines.append(f"💬 Только комментарий: {comment_only}")
                report_lines.append(f"⏳ Ожидает решения: {pending}")
                
                if total > 0:
                    completion_rate = ((approved or 0) + (rejected or 0) + (comment_only or 0)) / total * 100
                    if (approved or 0) + (rejected or 0) > 0:
                        approval_rate = (approved or 0) / ((approved or 0) + (rejected or 0)) * 100
                    else:
                        approval_rate = 0
                    
                    report_lines.append("")
                    report_lines.append("📊 ЭФФЕКТИВНОСТЬ:")
                    report_lines.append(f"• Завершено согласование: {completion_rate:.1f}%")
                    report_lines.append(f"• Процент согласования: {approval_rate:.1f}%")
                
                report_lines.append("")
                report_lines.append("👥 ДЕТАЛЬНЫЙ СПИСОК ПОЛУЧАТЕЛЕЙ:")
                report_lines.append("─" * 40)
                report_lines.append("")
                
                if recipients:
                    for i, (name, phone, username, telegram_id, 
                            recipient_status, recipient_comment, response_time, 
                            sent_via, is_comment_only) in enumerate(recipients, 1):
                        
                        # Определяем имя получателя - ЭКРАНИРУЕМ
                        if name:
                            recipient_name = self.escape_markdown(name)
                        elif phone:
                            recipient_name = phone
                        elif username:
                            recipient_name = f"@{self.escape_markdown(username)}"
                        else:
                            recipient_name = f"Получатель {i}"
                        
                        report_lines.append(f"{i}. {recipient_name}")
                        
                        # Контактная информация
                        contact_info = []
                        if phone:
                            contact_info.append(f"📱 {phone}")
                        if username:
                            safe_username = self.escape_markdown(username)
                            contact_info.append(f"👤 @{safe_username}")
                        if telegram_id:
                            contact_info.append(f"✅ Активирован (ID: {telegram_id})")
                        else:
                            contact_info.append("⏳ Не активирован")
                        
                        if contact_info:
                            report_lines.append(f"   {', '.join(contact_info)}")
                        
                        # Статус
                        if is_comment_only:
                            status_display = "💬 Только комментарий"
                        elif recipient_status == 'approved':
                            status_display = "✅ Согласовано"
                        elif recipient_status == 'rejected':
                            status_display = "❌ Отклонено"
                        elif recipient_status == 'pending':
                            status_display = "⏳ Ожидает решения"
                        else:
                            status_display = "📨 Не отправлено"
                        
                        status_line = f"   📊 Статус: {status_display}"
                        if sent_via:
                            status_line += f" ({sent_via})"
                        report_lines.append(status_line)
                        
                        # Комментарий - ЭКРАНИРУЕМ
                        if recipient_comment:
                            safe_comment = self.escape_markdown(recipient_comment[:100])
                            if len(recipient_comment) > 100:
                                safe_comment += "..."
                            report_lines.append(f"   💬 Комментарий: {safe_comment}")
                        
                        # Время ответа
                        if response_time:
                            try:
                                resp_dt = datetime.strptime(response_time, '%Y-%m-%d %H:%M:%S')
                                resp_str = resp_dt.strftime('%d.%m.%Y %H:%M')
                                report_lines.append(f"   🕐 Время ответа: {resp_str}")
                            except Exception as time_error:
                                logger.warning(f"⚠️ Ошибка форматирования времени: {time_error}")
                        
                        report_lines.append("")
                
                report_lines.append("─" * 40)
                report_lines.append(f"📋 Отчет сгенерирован: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
                report_lines.append("─" * 40)
                
                # Объединяем все строки в один текст
                report = "\n".join(report_lines)
                
                # ===== ОБНОВЛЕННАЯ КЛАВИАТУРА =====
                keyboard_buttons = [
                    [
                        InlineKeyboardButton("📄 PDF отчет", callback_data=f"export_pdf_{doc_id}"),
                        InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")
                    ],
                    [
                        InlineKeyboardButton("📝 TXT отчет", callback_data=f"export_txt_{doc_id}"),
                        InlineKeyboardButton("📊 Статистика", callback_data=f"export_stats_{doc_id}")
                    ],
                    [
                        InlineKeyboardButton("📋 Все отчеты", callback_data="menu_reports"),
                        InlineKeyboardButton("📤 Новый документ", callback_data="menu_send_doc")
                    ]
                ]
                
                keyboard = InlineKeyboardMarkup(keyboard_buttons)
                
                # Отправляем финальный отчет администратору
                await self.application.bot.send_message(
                    chat_id=DEVELOPER_ADMIN_ID,
                    text=report,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                
                logger.info(f"📊 Финальный отчет отправлен админу по документу {doc_id}")
                
                # Помечаем, что финальный отчет отправлен
                try:
                    c.execute('UPDATE documents SET final_report_sent = 1 WHERE id = ?', (doc_id,))
                    conn.commit()
                except:
                    # Если поля нет - игнорируем
                    pass
                
        except Exception as e:
            logger.error(f"❌ Ошибка отправки финального отчета админу: {e}")
            # Отправляем сообщение об ошибке
            try:
                await self.application.bot.send_message(
                    chat_id=DEVELOPER_ADMIN_ID,
                    text=f"❌ Ошибка при формировании финального отчета по документу {doc_id}: {str(e)[:100]}"
                )
            except:
                pass

    async def update_recipient_status(self, doc_id: str, user_id: int, status: str, comment: str = None):
        """Обновляет статус получателя и отправляет уведомление админу"""
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # ===== 1. НАХОДИМ ПОЛУЧАТЕЛЯ =====
                update_success = False
                contact_id = None
                
                # Поиск по telegram_id
                c.execute('''
                    UPDATE recipients 
                    SET status = ?, 
                        response_time = CURRENT_TIMESTAMP,
                        comment = COALESCE(?, comment)
                    WHERE doc_id = ? 
                    AND contact_id = (
                        SELECT id FROM contacts WHERE telegram_id = ?
                    )
                ''', (status, comment, doc_id, user_id))
                
                if c.rowcount > 0:
                    update_success = True
                    c.execute('SELECT id FROM contacts WHERE telegram_id = ?', (user_id,))
                    contact_result = c.fetchone()
                    if contact_result:
                        contact_id = contact_result[0]
                
                # Если не нашли по telegram_id, ищем по телефону
                if not update_success:
                    c.execute('SELECT phone FROM contacts WHERE telegram_id = ?', (user_id,))
                    phone_result = c.fetchone()
                    
                    if phone_result and phone_result[0]:
                        phone = phone_result[0]
                        
                        c.execute('''
                            SELECT r.id, r.contact_id 
                            FROM recipients r
                            JOIN contacts c ON r.contact_id = c.id
                            WHERE r.doc_id = ? AND c.phone = ? AND r.status = 'pending'
                            ORDER BY r.id LIMIT 1
                        ''', (doc_id, phone))
                        
                        recipient_info = c.fetchone()
                        
                        if recipient_info:
                            recipient_id, found_contact_id = recipient_info
                            contact_id = found_contact_id
                            
                            c.execute('''
                                UPDATE recipients 
                                SET status = ?, 
                                    response_time = CURRENT_TIMESTAMP,
                                    comment = COALESCE(?, comment)
                                WHERE id = ?
                            ''', (status, comment, recipient_id))
                            
                            update_success = True
                            
                            # ✅ АКТИВИРУЕМ ПОЛЬЗОВАТЕЛЯ (если ещё не активирован)
                            await self.activate_user(
                                user_id=user_id,
                                phone=phone,
                                username=None  # username уже есть в базе
                            )
                
                if update_success:
                    # Получаем информацию о пользователе и документе
                    c.execute('''
                        SELECT c.name, c.phone, c.username, df.file_name, d.created
                        FROM recipients r
                        JOIN contacts c ON r.contact_id = c.id
                        LEFT JOIN document_files df ON r.doc_id = df.doc_id AND df.file_order = 1
                        LEFT JOIN documents d ON r.doc_id = d.id
                        WHERE r.doc_id = ? AND r.contact_id = ?
                    ''', (doc_id, contact_id))
                    
                    user_info = c.fetchone()
                    
                    if user_info:
                        name, phone, username, file_name, doc_created = user_info
                        
                        # Определяем идентификатор пользователя
                        if name:
                            user_identifier = name
                        elif username:
                            user_identifier = f"@{username}"
                        elif phone:
                            user_identifier = phone
                        else:
                            user_identifier = f"ID: {user_id}"
                        
                        # Определяем статус текстом
                        status_text = "согласовал" if status == 'approved' else "отклонил"
                        
                        # ===== ИСПРАВЛЕННАЯ СТАТИСТИКА =====
                        # Получаем статистику по документу (только для этого документа)
                        c.execute('''
                            SELECT 
                                COUNT(*) as total,
                                SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
                            FROM recipients 
                            WHERE doc_id = ?
                        ''', (doc_id,))
                        
                        stats = c.fetchone()
                        total, approved, rejected, pending = stats if stats else (0, 0, 0, 0)
                        
                        # ===== ФОРМИРУЕМ СООБЩЕНИЕ ДЛЯ АДМИНА =====
                        admin_message = f"✅ {user_identifier} {status_text} документ\n\n"
                        admin_message += f"🆔 ID: {doc_id}\n"
                        
                        if file_name:
                            admin_message += f"📄 Документ: {file_name}\n"
                        
                        if comment:
                            admin_message += f"💬 Комментарий: {comment}\n"
                        
                        admin_message += f"\n📊 Статус согласования:\n"
                        admin_message += f"✅ Согласовано: {approved or 0}\n"
                        admin_message += f"❌ Отклонено: {rejected or 0}\n"
                        admin_message += f"⏳ Ожидает: {pending or 0}\n"
                        admin_message += f"📋 Всего: {total or 0}\n\n"
                        admin_message += f"⏰ Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}"
                        
                        conn.commit()
                        
                        # ===== ОТПРАВКА УВЕДОМЛЕНИЯ АДМИНУ =====
                        try:
                            await self.application.bot.send_message(
                                chat_id=DEVELOPER_ADMIN_ID,
                                text=admin_message,
                                parse_mode='Markdown'
                            )
                            logger.info(f"📤 Уведомление админу: {user_identifier} {status_text} документ {doc_id}")
                            
                            # Удаляем задачу напоминания
                            self.reminder_manager.remove_reminder(doc_id, user_id)
                            
                            # ===== ЕСЛИ ВСЕ ОТВЕТИЛИ - ОТПРАВЛЯЕМ ФИНАЛЬНЫЙ ОТЧЕТ =====
                            # ВАЖНО: используем свежую статистику и проверяем, не отправляли ли уже
                            if pending == 0 and total > 0:
                                # Проверяем, не отправляли ли уже финальный отчет
                                c.execute('''
                                    SELECT COUNT(*) FROM recipients 
                                    WHERE doc_id = ? AND status IN ('approved', 'rejected', 'pending')
                                ''', (doc_id,))
                                
                                total_recipients = c.fetchone()[0] or 0
                                
                                if total_recipients > 0:
                                    # Небольшая задержка, чтобы не флудить
                                    await asyncio.sleep(2)
                                    await self.send_final_report_to_admin(doc_id)
                                
                        except Exception as e:
                            logger.error(f"❌ Ошибка отправки уведомления админу: {e}")
                        
                        return True
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статуса получателя: {e}")
        
        return False

    async def update_existing_contact(self, user_id: int, username: str = None, phone: str = None):
        """Обновляет существующий контакт при повторной активации"""
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Ищем контакт по telegram_id, username или phone
                if username:
                    c.execute('''SELECT id FROM contacts 
                            WHERE username = ? AND telegram_id IS NULL''', (username,))
                elif phone:
                    normalized_phone = self.normalize_phone(phone)
                    c.execute('''SELECT id FROM contacts 
                            WHERE phone = ? AND telegram_id IS NULL''', (normalized_phone,))
                else:
                    return False
                
                result = c.fetchone()
                if result:
                    contact_id = result[0]
                    # Обновляем контакт
                    c.execute('''UPDATE contacts 
                            SET telegram_id = ?, 
                                last_activity = CURRENT_TIMESTAMP,
                                first_activation = COALESCE(first_activation, CURRENT_TIMESTAMP)
                            WHERE id = ?''', (user_id, contact_id))
                    
                    conn.commit()
                    logger.info(f"✅ Контакт обновлен: ID {contact_id} -> пользователь {user_id}")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления контакта: {e}")
            return False


    async def process_phone_link(self, update: Update, phone: str, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Обработка перехода по ссылке с телефоном - УПРОЩЁННАЯ ВЕРСИЯ"""
        try:
            normalized_phone = self.normalize_phone(phone)
            username = update.effective_user.username
            
            # ===== 1. ✅ ЕДИНАЯ АКТИВАЦИЯ =====
            success = await self.activate_user(
                user_id=user_id,
                phone=normalized_phone,
                username=username
            )
            
            if not success:
                await update.message.reply_text(
                    "❌ Не удалось активировать аккаунт. Обратитесь к администратору.",
                    reply_markup=self.get_reply_keyboard(user_id)
                )
                return
            
            # ===== 2. ПРИВЕТСТВИЕ =====
            await update.message.reply_text(
                "👋 *Добро пожаловать в DocFlow!*\n\n"
                "✅ *Ваш аккаунт активирован.*\n\n"
                "📄 Если у вас есть ожидающие документы, "
                "они придут в этот чат в течение минуты.\n\n"
                "💡 *Все будущие документы будут доставляться автоматически.*",
                parse_mode='Markdown',
                reply_markup=self.get_reply_keyboard(user_id)
            )
            
            # ===== 3. ОТПРАВЛЯЕМ ОЖИДАЮЩИЕ ДОКУМЕНТЫ =====
            await self.send_pending_documents_to_user(user_id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в process_phone_link: {e}")
            await update.message.reply_text(
                "❌ Ошибка активации. Обратитесь к администратору.",
                reply_markup=self.get_reply_keyboard(user_id)
            )

    async def send_document_to_user(self, user_id: int, doc_id: str, files: list, total_files: int, context):
        """Отправляет один документ пользователю"""
        try:
            # Сортируем файлы по порядку
            files.sort(key=lambda x: x[2])
            
            # Создаем клавиатуру
            lang = self.get_user_language(user_id)
            keyboard_buttons = [
                [
                    InlineKeyboardButton("✅ Согласен", callback_data=f"approve_{doc_id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{doc_id}")
                ],
                [
                    InlineKeyboardButton("💬 Комментарий", callback_data=f"comment_{doc_id}"),
                    InlineKeyboardButton("👥 Кто еще получил", callback_data=f"view_recipients_{doc_id}")
                ]
            ]
            
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
            
            # Отправляем первый файл с кнопками
            first_file_id, first_file_name, _ = files[0]
            
            await context.bot.send_document(
                chat_id=user_id,
                document=first_file_id,
                caption=(
                    f"📄 *Новый документ для согласования*\n\n"
                    f"**{first_file_name}**\n"
                    f"{f'📚 Всего файлов: {total_files}' if total_files > 1 else ''}\n\n"
                    f"👇 Используйте кнопки ниже"
                ),
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            # Отправляем остальные файлы
            for i in range(1, len(files)):
                file_id, file_name, _ = files[i]
                await context.bot.send_document(
                    chat_id=user_id,
                    document=file_id,
                    caption=f"📄 *Документ {i+1}:* {file_name}",
                    parse_mode='Markdown'
                )
                
            logger.info(f"✅ Документ {doc_id} отправлен пользователю {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки документа {doc_id} пользователю {user_id}: {e}")

    async def send_pending_documents_to_user(self, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Отправляет пользователю все документы, которые ждали его активации"""
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()

                # Получаем все pending-документы для этого пользователя
                c.execute('''
                    SELECT DISTINCT r.doc_id, df.file_id, df.file_name
                    FROM recipients r
                    JOIN contacts c ON r.contact_id = c.id
                    JOIN document_files df ON r.doc_id = df.doc_id AND df.file_order = 1
                    WHERE c.telegram_id = ?
                    AND r.status = 'pending'
                    ORDER BY r.id DESC
                    LIMIT 5
                ''', (user_id,))

                pending_docs = c.fetchall()

                if not pending_docs:
                    return

                logger.info(f"📨 Отправка {len(pending_docs)} накопленных документов пользователю {user_id}")

                for doc_id, file_id, file_name in pending_docs:
                    # Клавиатура для документа
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Согласен", callback_data=f"approve_{doc_id}"),
                            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{doc_id}")
                        ],
                        [
                            InlineKeyboardButton("💬 Комментарий", callback_data=f"comment_{doc_id}"),
                            InlineKeyboardButton("👥 Кто еще получил", callback_data=f"view_recipients_{doc_id}")
                        ]
                    ])

                    await context.bot.send_document(
                        chat_id=user_id,
                        document=file_id,
                        caption=f"📄 *Новый документ для согласования*\n\n"
                                f"**{file_name}**\n\n"
                                f"👇 Используйте кнопки ниже",
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )

                    # Небольшая пауза, чтобы не флудить
                    await asyncio.sleep(0.3)

        except Exception as e:
            logger.error(f"❌ Ошибка send_pending_documents_to_user: {e}")
    
    async def handle_start_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатия на кнопку Start в Reply-клавиатуре"""
        user_id = update.effective_user.id
        first_name = update.effective_user.first_name
        
        # Показываем меню в зависимости от пользователя
        if user_id == DEVELOPER_ADMIN_ID:
            await self.show_admin_menu(update, context)
        else:
            await self.show_user_menu(update, first_name, context)
    
    async def show_admin_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает главное меню администратора с поддержкой языков"""
        user_id = update.effective_user.id
        lang = self.get_user_language(user_id)
        
        keyboard_buttons = [
            [
                InlineKeyboardButton(
                    Translations.get('send_document', lang), 
                    callback_data="menu_send_doc"
                )
            ],
            [
                InlineKeyboardButton(
                    Translations.get('contacts', lang), 
                    callback_data="menu_contacts"
                ),
                InlineKeyboardButton(
                    Translations.get('add', lang), 
                    callback_data="menu_add"
                )
            ],
            [
                InlineKeyboardButton(
                    Translations.get('reports', lang), 
                    callback_data="menu_reports"
                ),
                InlineKeyboardButton(
                    Translations.get('queue_status', lang), 
                    callback_data="menu_queue"
                )
            ],
            [
                InlineKeyboardButton(
                    Translations.get('instructions', lang), 
                    callback_data="menu_instructions"
                )
            ],
            [
                InlineKeyboardButton(
                    Translations.get('change_language', lang), 
                    callback_data="menu_change_language"
                ),
                InlineKeyboardButton(
                    Translations.get('refresh', lang), 
                    callback_data="menu_refresh"
                )
            ]
        ]
        
        # УБРАНА кнопка Start/Menu из основного меню (только в Reply-клавиатуре)
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        # Получаем статистику
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                c.execute("SELECT COUNT(*) FROM contacts WHERE telegram_id IS NOT NULL")
                active_users = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM contacts WHERE phone IS NOT NULL")
                with_phone = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM contacts WHERE username IS NOT NULL")
                with_username = c.fetchone()[0]
                
                c.execute("SELECT COUNT(*) FROM documents")
                total_docs = c.fetchone()[0]
                
                c.execute('''SELECT COUNT(DISTINCT doc_id) FROM recipients 
                           WHERE status = 'pending' ''')
                pending_docs = c.fetchone()[0] or 0
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            active_users = with_phone = with_username = total_docs = pending_docs = 0
        
        # Добавляем информацию об автоматической отправке
        auto_send_info = ""
        if self.admin_sender:
            stats = await self.admin_sender.get_stats()
            auto_send_info = (
                f"\n{Translations.get('auto_send', lang)}:\n"
                f"• {Translations.get('send_from', lang)}: {self.admin_sender.admin_phone}\n"
                f"• {Translations.get('in_queue', lang)}: {stats['pending']}\n"
                f"• {Translations.get('sent', lang)}: {stats['sent']}\n"
            )
        
        # Формируем сообщение с переводами
        message_text = (
            f"{Translations.get('main_menu_title', lang)}\n\n"
            f"{Translations.get('statistics', lang)}:\n"
            f"• {Translations.get('users', lang)}: {active_users}\n"
            f"• {Translations.get('with_phones', lang)}: {with_phone}\n"
            f"• {Translations.get('with_username', lang)}: {with_username}\n"
            f"• {Translations.get('documents', lang)}: {total_docs}\n"
            f"• {Translations.get('pending_approval', lang)}: {pending_docs}\n"
            f"{auto_send_info}\n"
            f"{Translations.get('bot', lang)}: @{self.bot_username}\n"
            f"{Translations.get('your_id', lang)}: {update.effective_user.id}\n\n"
            f"{Translations.get('select_action', lang)}:"
        )
        
        # Определяем текущий язык для отображения
        current_lang = LANGUAGES.get(lang, '🇷🇺 Русский')
        message_text += f"\n\n{Translations.get('current_language', lang)}: {current_lang}"
        
        # Отправляем или редактируем сообщение
        if update.message:
            await update.message.reply_text(message_text, reply_markup=keyboard)
        elif update.callback_query:
            await update.callback_query.message.edit_text(message_text, reply_markup=keyboard)
            await update.callback_query.answer()
    
    async def show_instructions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает инструкции для админа"""
        query = update.callback_query
        if query:
            await query.answer()
        
        instructions = (
            "📖 *ИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ БОТА*\n\n"
            
            "👑 *ДЛЯ АДМИНИСТРАТОРА:*\n\n"
            
            "📤 *ОТПРАВКА ДОКУМЕНТОВ:*\n"
            "1. Нажмите '📤 ОТПРАВИТЬ ДОКУМЕНТ'\n"
            "2. Отправьте один или несколько документов\n"
            "3. Укажите получателей (телефоны или @usernames)\n"
            "4. Или выберите из списка контактов\n\n"
            
            "➕ *ДОБАВЛЕНИЕ КОНТАКТОВ:*\n"
            "• По телефону: <PHONE_NUMBER> Имя Фамилия\n"
            "• По username: @ivanov Иван Иванов\n"
            "• Или отправить контакт из телефонной книги\n\n"
            
            "🤖 *АВТОМАТИЧЕСКАЯ ОТПРАВКА:*\n"
            "• Для @username - всегда автоматически\n"
            "• Для телефонов - система попытается отправить автоматически\n\n"
            
            "👤 *ДЛЯ ПОЛЬЗОВАТЕЛЕЙ:*\n"
            "1. Получают ссылку на документ\n"
            "2. Переходят по ссылке в бота\n"
            "3. Согласовывают или отклоняют документ\n"
            "4. Могут оставлять комментарии\n"
            "5. После активации документы приходят автоматически\n\n"
            
            "⏰ *СИСТЕМА НАПОМИНАНИЙ:*\n"
            "• Через 5 минут после комментария - напоминание\n"
            "• Через 10 минут - финальное напоминание\n"
            "• Админ получает уведомления о комментариях без решений\n\n"
            
            "📊 *ОТЧЕТЫ:*\n"
            "• Статус согласования документов\n"
            "• Экспорт в PDF/TXT\n"
            "• Статистика по пользователям\n\n"
            
            "🌐 *СМЕНА ЯЗЫКА:*\n"
            "• Русский / English\n"
            "• Все меню и сообщения переключаются\n\n"
            
            "💡 *СОВЕТЫ:*\n"
            "• Всегда проверяйте правильность телефонов\n"
            "• Для быстрой отправки используйте @usernames\n"
            "• Экспортируйте отчеты для документации"
        )
        
        # УБРАНА кнопка Start/Menu из основного меню
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
        ])
        
        if query:
            await query.message.edit_text(instructions, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await update.message.reply_text(instructions, reply_markup=keyboard, parse_mode='Markdown')
    
    async def show_language_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню выбора языка"""
        query = update.callback_query
        await query.answer()
        
        keyboard_buttons = [
            [
                InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru"),
                InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu_back")]
        ]
        
        # УБРАНА кнопка Start/Menu из основного меню
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        message = Translations.get('select_language', 'ru') + " / " + Translations.get('select_language', 'en')
        
        await query.message.edit_text(message, reply_markup=keyboard)
    
    async def handle_language_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора языка"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data == "set_lang_ru":
            self.set_user_language(user_id, 'ru')
            message = Translations.get('language_changed_ru', 'ru')
        elif data == "set_lang_en":
            self.set_user_language(user_id, 'en')
            message = Translations.get('language_changed_en', 'en')
        else:
            message = "❌ Ошибка выбора языка"
        
        keyboard_buttons = [
            [InlineKeyboardButton("✅ Продолжить", callback_data="menu_back")]
        ]
        
        # УБРАНА кнопка Start/Menu из основного меню
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await query.message.edit_text(message, reply_markup=keyboard)
        await asyncio.sleep(1)
        await self.show_admin_menu(update, context)
    
    async def show_user_menu(self, update: Update, first_name: str, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню обычного пользователя"""
        user_id = update.effective_user.id
        lang = self.get_user_language(user_id)
        
        keyboard_buttons = [
            [InlineKeyboardButton("📄 Мои документы", callback_data="user_documents")],
            [InlineKeyboardButton("🆔 Мой профиль", callback_data="user_profile")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="user_help")]
            # УБРАНА КНОПКА СМЕНЫ ЯЗЫКА
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        welcome = Translations.get('welcome', lang) if hasattr(Translations, 'get') else "Добро пожаловать"
        
        message = f"👤 {welcome}, {first_name}!\n\n"
        message += "📄 *DocFlow - система согласования документов*\n\n"
        message += "✅ *Ваши возможности:*\n"
        message += "• 📄 Просмотр документов для согласования\n"
        message += "• ✅ Подтверждение или отклонение документов\n"
        message += "• 💬 Добавление комментариев\n"
        message += "• 📊 Просмотр истории согласований\n\n"
        
        # Проверяем, есть ли ожидающие документы
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''SELECT COUNT(*) FROM recipients r
                        JOIN contacts c ON r.contact_id = c.id
                        WHERE c.telegram_id = ? AND r.status = 'pending' ''', (user_id,))
                pending_count = c.fetchone()[0] or 0
        except:
            pending_count = 0
        
        if pending_count > 0:
            message += f"📬 *У вас {pending_count} документ(ов) ожидают согласования*\n\n"
        
        message += "💡 *После первого входа:*\n"
        message += "Все документы будут приходить автоматически!"
        
        await update.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')

    async def show_user_menu_by_query(self, update: Update, first_name: str, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню пользователя через callback query"""
        query = update.callback_query
        user_id = query.from_user.id
        lang = self.get_user_language(user_id)
        
        keyboard_buttons = [
            [InlineKeyboardButton("📄 Мои документы", callback_data="user_documents")],
            [InlineKeyboardButton("🆔 Мой профиль", callback_data="user_profile")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="user_help")]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        welcome = Translations.get('welcome', lang) if hasattr(Translations, 'get') else "Добро пожаловать"
        
        message = f"👤 {welcome}, {first_name}!\n\n"
        message += "📄 *DocFlow - система согласования документов*\n\n"
        message += "✅ *Ваши возможности:*\n"
        message += "• 📄 Просмотр документов для согласования\n"
        message += "• ✅ Подтверждение или отклонение документов\n"
        message += "• 💬 Добавление комментариев\n"
        message += "• 📊 Просмотр истории согласований\n\n"
        
        # Проверяем, есть ли ожидающие документы
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''SELECT COUNT(*) FROM recipients r
                        JOIN contacts c ON r.contact_id = c.id
                        WHERE c.telegram_id = ? AND r.status = 'pending' ''', (user_id,))
                pending_count = c.fetchone()[0] or 0
        except:
            pending_count = 0
        
        if pending_count > 0:
            message += f"📬 *У вас {pending_count} документ(ов) ожидают согласования*\n\n"
        
        message += "💡 *После первого входа:*\n"
        message += "Все документы будут приходить автоматически!"
        
        await query.message.edit_text(message, reply_markup=keyboard, parse_mode='Markdown')

    async def show_recipients_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE, doc_id: str):
        """Показывает список получателей документа"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        lang = self.get_user_language(user_id)
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем список получателей
                c.execute('''SELECT c.name, c.phone, c.username, r.status, r.comment
                            FROM recipients r
                            JOIN contacts c ON r.contact_id = c.id
                            WHERE r.doc_id = ?
                            ORDER BY 
                                CASE r.status 
                                    WHEN 'approved' THEN 1
                                    WHEN 'rejected' THEN 2
                                    WHEN 'pending' THEN 3
                                    ELSE 4
                                END,
                                c.name''', (doc_id,))
                
                recipients = c.fetchall()
                
                if not recipients:
                    await query.message.edit_text("📭 Нет получателей для этого документа")
                    return
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения списка получателей: {e}")
            await query.message.edit_text("❌ Ошибка базы данных")
            return
        
        # Формируем сообщение
        message = Translations.get('recipients_list', lang)
        
        for i, (name, phone, username, status, comment) in enumerate(recipients, 1):
            # Определяем имя получателя
            recipient_name = ""
            if name:
                recipient_name = name
            elif phone:
                recipient_name = phone
            elif username:
                recipient_name = f"@{username}"
            else:
                recipient_name = f"Получатель {i}"
            
            # Определяем статус
            if status == 'approved':
                status_text = Translations.get('recipient_status_approved', lang)
            elif status == 'rejected':
                status_text = Translations.get('recipient_status_rejected', lang)
            elif status == 'pending':
                status_text = Translations.get('recipient_status_pending', lang)
            else:
                status_text = "📨 Неизвестно"
            
            if comment:
                status_text += f" 💬"
            
            message += f"{i}. **{recipient_name}** - {status_text}\n"
            
            if comment:
                message += f"   💬 *Комментарий:* {comment[:50]}{'...' if len(comment) > 50 else ''}\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(Translations.get('back_to_document', lang), 
                            callback_data=f"back_to_doc_{doc_id}")]
        ])
        
        await query.message.edit_text(message, reply_markup=keyboard, parse_mode='Markdown')
    
    async def handle_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на кнопки меню"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        action = query.data
        
        if user_id != DEVELOPER_ADMIN_ID and action not in ["user_back_to_menu", "user_instructions", 
                                                        "user_documents", "user_profile", "user_help", 
                                                        "user_change_language"]:
            # Проверяем, не является ли это действием пользователя с документом
            if not (action.startswith("approve_") or action.startswith("reject_") or 
                    action.startswith("comment_") or action.startswith("view_recipients_") or
                    action.startswith("back_to_doc_") or action.startswith("view_status_")):
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Назад в меню", callback_data="user_back_to_menu")]
                ])
                
                await query.message.edit_text(
                    "❌ У вас нет прав администратора",
                    reply_markup=keyboard
                )
                return
        
        # Обработка действий администратора
        if action == "menu_contacts":
            await self.show_contacts_menu(update, context)
        elif action == "contacts_phone":
            await self.show_contacts_list(update, context, 'phone')
        elif action == "contacts_active":
            await self.show_contacts_list(update, context, 'active')
        elif action == "contacts_all":
            await self.show_contacts_list(update, context, 'all')
        elif action == "menu_add":
            await self.show_add_menu(update, context)
        elif action == "menu_send_doc":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
            ])
            
            await query.message.edit_text(
                "📤 ОТПРАВКА ДОКУМЕНТА\n\n"
                "📝 Готов к приему документов!\n\n"
                "Просто отправьте мне документ(ы) в этот чат.\n\n"
                "🤖 Поддерживается:\n"
                "• Любые форматы файлов\n"
                "• Один или несколько документов\n"
                "• Фотографии, PDF, Word, Excel и т.д.\n\n"
                "💡 После отправки документа я запрошу список получателей.",
                reply_markup=keyboard
            )
        elif action == "menu_queue":
            await self.show_queue_menu(update, context)
        elif action == "menu_instructions":
            await self.show_instructions(update, context)
        elif action == "menu_reports":
            await self.show_reports_menu(update, context)
        elif action == "menu_refresh":
            await self.show_admin_menu(update, context)
        elif action == "menu_back":
            await self.show_admin_menu(update, context)
        elif action == "menu_change_language":
            await self.show_language_menu(update, context)
        
        # Обработка действий пользователя с документами
        elif action.startswith("approve_"):
            # Обработка согласия с документом
            doc_id = action.replace("approve_", "")
            
            # Обновляем статус
            success = await self.update_recipient_status(doc_id, user_id, 'approved')
            
            if success:
                lang = self.get_user_language(user_id)
                await query.message.edit_text(
                    f"✅ *Документ согласован!*\n\n"
                    f"🆔 ID документа: {doc_id}\n"
                    f"✅ Ваше решение сохранено\n"
                    f"📤 Администратор уведомлен",
                    parse_mode='Markdown'
                )
            else:
                await query.message.edit_text("❌ Ошибка при сохранении решения")
            
            # После обработки возвращаемся к документу
            await self.show_document_to_user(update, context, doc_id)
            
        elif action.startswith("reject_"):
            # Обработка отказа от документа
            doc_id = action.replace("reject_", "")
            
            # Обновляем статус
            success = await self.update_recipient_status(doc_id, user_id, 'rejected')
            
            if success:
                lang = self.get_user_language(user_id)
                await query.message.edit_text(
                    f"❌ *Документ отклонен!*\n\n"
                    f"🆔 ID документа: {doc_id}\n"
                    f"❌ Ваше решение сохранено\n"
                    f"📤 Администратор уведомлен",
                    parse_mode='Markdown'
                )
            else:
                await query.message.edit_text("❌ Ошибка при сохранении решения")
            
            # После обработки возвращаемся к документу
            await self.show_document_to_user(update, context, doc_id)
            
        elif action.startswith("comment_"):
            # Обработка комментария к документу
            doc_id = action.replace("comment_", "")
            context.user_data['commenting_doc_id'] = doc_id
            
            lang = self.get_user_language(user_id)
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(Translations.get('cancel', lang), 
                                callback_data=f"back_to_doc_{doc_id}")]
            ])
            
            await query.message.edit_text(
                Translations.get('waiting_comment', lang),
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        elif action.startswith("back_to_doc_"):
            # Возврат к документу из режима комментария
            doc_id = action.replace("back_to_doc_", "")
            
            if 'commenting_doc_id' in context.user_data:
                del context.user_data['commenting_doc_id']
            
            await self.show_document_to_user(update, context, doc_id)
            
        elif action.startswith("view_recipients_"):
            # Просмотр списка получателей
            doc_id = action.replace("view_recipients_", "")
            await self.show_recipients_list(update, context, doc_id)
            
        elif action.startswith("view_status_"):
            # Просмотр статуса документа
            doc_id = action.replace("view_status_", "")
            
            # Просто показываем документ снова
            await self.show_document_to_user(update, context, doc_id)
        
        # Обработка действий пользователя
        elif action == "user_back_to_menu":
            if user_id == DEVELOPER_ADMIN_ID:
                await self.show_admin_menu(update, context)
            else:
                first_name = query.from_user.first_name
                await self.show_user_menu_by_query(update, first_name, context)
        elif action == "user_instructions":
            await self.show_user_instructions(update, context)
        elif action == "user_documents":
            await self.show_user_documents(update, context)
        elif action == "user_profile":
            await self.show_user_profile(update, context)
        elif action == "user_help":
            await self.show_user_help(update, context)
        elif action == "user_change_language":
            await self.show_user_language_menu(update, context)
        elif action == "menu_templates":
            await self.show_admin_menu(update, context)
        elif action == "user_help":
            await self.show_user_help(update, context)

    async def open_user_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Открывает документ пользователя по ID"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("open_doc_"):
            doc_id = query.data.replace("open_doc_", "")
            user_id = query.from_user.id
            
            await self.show_document_to_user(update, context, doc_id)
    
    async def show_user_documents(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает документы пользователя"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        lang = self.get_user_language(user_id)
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # ИСПРАВЛЕНО: используем правильное название колонки
                # В таблице documents колонка называется 'created_at', а не 'created'
                c.execute('''SELECT DISTINCT d.id, df.file_name, r.status, r.response_time,
                        r.comment, r.comment_only
                        FROM recipients r
                        JOIN documents d ON r.doc_id = d.id
                        JOIN document_files df ON d.id = df.doc_id AND df.file_order = 1
                        JOIN contacts c ON r.contact_id = c.id
                        WHERE c.telegram_id = ? 
                        ORDER BY 
                            CASE 
                                WHEN r.status = 'pending' THEN 1
                                WHEN r.status = 'approved' THEN 2
                                WHEN r.status = 'rejected' THEN 3
                                ELSE 4
                            END,
                            d.created_at DESC  -- ИСПРАВЛЕНО: created_at вместо created
                        LIMIT 20''', (user_id,))
                
                documents = c.fetchall()
                
                # Также проверяем документы, которые были отправлены напрямую
                # но пользователь еще не взаимодействовал с ними
                c.execute('''SELECT r.doc_id, df.file_name 
                        FROM recipients r
                        JOIN document_files df ON r.doc_id = df.doc_id AND df.file_order = 1
                        WHERE r.contact_id = (SELECT id FROM contacts WHERE telegram_id = ?)
                        AND r.status = 'pending'
                        AND r.sent_via = 'direct'
                        ORDER BY d.created_at DESC''', (user_id,))  # ИСПРАВЛЕНО: created_at вместо created
                
                direct_docs = c.fetchall()
                
                # Объединяем документы
                all_documents = list(documents)
                
                # Добавляем документы, отправленные напрямую
                for doc_id, file_name in direct_docs:
                    if not any(d[0] == doc_id for d in all_documents):
                        all_documents.append((doc_id, file_name, 'pending', None, None, False))
                
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Ошибка получения документов пользователя: {e}")
            all_documents = []
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка: {e}")
            all_documents = []
        
        if not all_documents:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад в меню", callback_data="user_back_to_menu")]
            ])
            
            message = "📭 У вас пока нет документов для согласования."
            await query.message.edit_text(message, reply_markup=keyboard)
            return
        
        message = "📄 *Ваши документы для согласования:*\n\n"
        
        for i, (doc_id, file_name, status, response_time, comment, comment_only) in enumerate(all_documents, 1):
            status_text = {
                'pending': '⏳ Ожидает решения',
                'approved': '✅ Согласовано',
                'rejected': '❌ Отклонено'
            }.get(status, '📨 Неизвестно')
            
            if comment_only:
                status_text = '💬 Только комментарий'
            
            time_text = ""
            if response_time:
                try:
                    resp_dt = datetime.strptime(response_time, '%Y-%m-%d %H:%M:%S')
                    time_text = resp_dt.strftime(' (%d.%m %H:%M)')
                except:
                    pass
            
            comment_text = ""
            if comment:
                comment_text = f"\n   💬 Комментарий: {comment[:50]}{'...' if len(comment) > 50 else ''}"
            
            # Создаем кнопку для доступа к документу
            message += f"{i}. *{file_name[:30]}...*\n"
            message += f"   {status_text}{time_text}\n"
            message += f"   🆔 ID: {doc_id[:8]}{comment_text}\n\n"
        
        message += f"\n📊 Всего документов: {len(all_documents)}"
        
        # Создаем клавиатуру с кнопками для документов
        keyboard_buttons = []
        
        # Добавляем кнопки для каждого документа со статусом "pending"
        pending_docs = [d for d in all_documents if d[2] == 'pending']
        for doc_id, file_name, _, _, _, _ in pending_docs[:3]:  # Максимум 3 кнопки
            short_name = file_name[:15] + "..." if len(file_name) > 15 else file_name
            keyboard_buttons.append([
                InlineKeyboardButton(f"📝 {short_name}", callback_data=f"open_doc_{doc_id}")
            ])
        
        if pending_docs:
            keyboard_buttons.append([
                InlineKeyboardButton(f"📝 Обработать все ({len(pending_docs)})", callback_data="process_all_docs")
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton("🔄 Обновить", callback_data="user_documents"),
            InlineKeyboardButton("⬅️ Назад в меню", callback_data="user_back_to_menu")
        ])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        # Проверяем тип сообщения перед редактированием
        try:
            if query.message.text:
                await query.message.edit_text(message, reply_markup=keyboard, parse_mode='Markdown')
            else:
                # Если это не текстовое сообщение, отправляем новое
                await query.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке списка документов: {e}")
            # Пробуем отправить новое сообщение
            await query.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
    
    async def show_user_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает профиль пользователя"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем информацию о пользователе
                c.execute('''SELECT phone, username, name, last_activity 
                           FROM contacts WHERE telegram_id = ?''', (user_id,))
                
                user_info = c.fetchone()
                
                # Получаем статистику
                c.execute('''SELECT 
                           COUNT(*) as total_docs,
                           SUM(CASE WHEN r.status = 'approved' THEN 1 ELSE 0 END) as approved,
                           SUM(CASE WHEN r.status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                           SUM(CASE WHEN r.status = 'pending' THEN 1 ELSE 0 END) as pending
                           FROM recipients r
                           JOIN contacts c ON r.contact_id = c.id
                           WHERE c.telegram_id = ?''', (user_id,))
                
                stats = c.fetchone()
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Ошибка получения профиля: {e}")
            user_info = None
            stats = (0, 0, 0, 0)
        
        message = "👤 *Ваш профиль*\n\n"
        
        if user_info:
            phone, username, name, last_activity = user_info
            if name:
                message += f"👤 *Имя:* {name}\n"
            if username:
                message += f"📱 *Username:* @{username}\n"
            if phone:
                message += f"📞 *Телефон:* {phone}\n"
            
            message += f"🆔 *ID:* {user_id}\n"
            
            if last_activity:
                activity_dt = datetime.strptime(last_activity, '%Y-%m-%d %H:%M:%S')
                message += f"🕐 *Последняя активность:* {activity_dt.strftime('%d.%m.%Y %H:%M')}\n"
        
        total, approved, rejected, pending = stats if stats else (0, 0, 0, 0)
        message += f"\n📊 *Статистика:*\n"
        message += f"📄 Всего документов: {total}\n"
        message += f"✅ Согласовано: {approved}\n"
        message += f"❌ Отклонено: {rejected}\n"
        message += f"⏳ Ожидает решения: {pending}\n"
        
        # УБРАНА кнопка Start/Menu из основного меню
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="user_back_to_menu")]
        ])
        
        await query.message.edit_text(message, reply_markup=keyboard, parse_mode='Markdown')
    
    # Добавьте этот метод в класс UniversalContactBot после метода show_user_help

    async def show_user_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает помощь для пользователя с контактами администратора"""
        query = update.callback_query
        if query:
            await query.answer()
        
        user_id = query.from_user.id if query else update.effective_user.id
        lang = self.get_user_language(user_id)
        
        # Получаем информацию об администраторе
        admin_info = "Администратор"
        admin_contact = f"@{self.bot_username}" if self.bot_username else "@admin"
        
        # Пытаемся получить имя администратора из базы
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                c.execute('SELECT name FROM contacts WHERE telegram_id = ?', (DEVELOPER_ADMIN_ID,))
                admin_result = c.fetchone()
                if admin_result and admin_result[0]:
                    admin_info = admin_result[0]
        except:
            pass
        
        message = "❓ *ПОМОЩЬ И ПОДДЕРЖКА*\n\n"
        
        message += "📞 *СВЯЗЬ С АДМИНИСТРАТОРОМ:*\n"
        message += f"👤 **{admin_info}**\n"
        message += f"📱 **Контакт:** {admin_contact}\n\n"
        
        message += "📋 *ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ:*\n\n"
        
        message += "❓ *Как согласовать документ?*\n"
        message += "1️⃣ Откройте документ из списка 'Мои документы'\n"
        message += "2️⃣ Нажмите кнопку '✅ Согласен' или '❌ Отклонить'\n"
        message += "3️⃣ При необходимости добавьте комментарий\n\n"
        
        message += "❓ *Как добавить комментарий?*\n"
        message += "• Нажмите кнопку '💬 Комментарий' под документом\n"
        message += "• Напишите комментарий и отправьте\n"
        message += "• После этого нажмите '✅ Согласен' или '❌ Отклонить'\n\n"
        
        message += "❓ *Где посмотреть кто еще получил документ?*\n"
        message += "• Нажмите кнопку '👥 Кто еще получил' под документом\n"
        message += "• Вы увидите список всех получателей и их статусы\n\n"
        
        message += "❓ *Документы не приходят?*\n"
        message += "1️⃣ Проверьте интернет-соединение\n"
        message += "2️⃣ Нажмите кнопку '🚀 Restart / Menu'\n"
        message += "3️⃣ Перейдите в 'Мои документы' для проверки\n"
        message += "4️⃣ Если проблема не решена - обратитесь к администратору\n\n"
        
        message += "❓ *Как посмотреть свои документы?*\n"
        message += "• В главном меню нажмите '📄 Мои документы'\n"
        message += "• Вы увидите список всех ваших документов\n"
        message += "• Нажмите на документ для просмотра деталей\n\n"
        
        message += "❓ *Что значит статус 'Только комментарий'?*\n"
        message += "• Вы оставили комментарий, но еще не приняли решение\n"
        message += "• Вернитесь к документу и нажмите '✅ Согласен' или '❌ Отклонить'\n\n"
        
        message += "💡 *ПОЛЕЗНЫЕ СОВЕТЫ:*\n"
        message += "• Всегда проверяйте документы перед согласованием\n"
        message += "• Используйте комментарии для пояснения своего решения\n"
        message += "• После активации все документы приходят автоматически\n"
        message += "• При возникновении ошибок - перезапустите бота\n\n"
        
        message += "⚠️ *ВАЖНО:*\n"
        message += "• Срок действия ссылок на документы - 7 дней\n"
        message += "• После первого входа бот запомнит вас\n"
        message += "• Все будущие документы будут приходить автоматически\n\n"
        
        message += "📱 *ТЕХНИЧЕСКАЯ ПОДДЕРЖКА:*\n"
        message += f"По всем вопросам обращайтесь к администратору:\n"
        message += f"{admin_contact}\n\n"
        message += f"⏰ *Время ответа:* обычно в течение рабочего дня"
        
        # Кнопки для навигации
        keyboard_buttons = [
            [InlineKeyboardButton("📄 Мои документы", callback_data="user_documents")],
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="user_back_to_menu")]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        if query:
            try:
                await query.message.edit_text(
                    message,
                    reply_markup=keyboard,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error(f"❌ Ошибка редактирования сообщения помощи: {e}")
                # Если не удалось отредактировать, отправляем новое
                await query.message.reply_text(
                    message,
                    reply_markup=keyboard,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
        else:
            await update.message.reply_text(
                message,
                reply_markup=keyboard,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
    
    async def show_user_language_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню выбора языка для пользователя"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        lang = self.get_user_language(user_id)
        
        keyboard_buttons = [
            [
                InlineKeyboardButton("🇷🇺 Русский", callback_data="user_set_lang_ru"),
                InlineKeyboardButton("🇬🇧 English", callback_data="user_set_lang_en")
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data="user_back_to_menu")]
        ]
        
        # УБРАНА кнопка Start/Menu из основного меню
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        message = Translations.get('select_language', lang)
        
        await query.message.edit_text(message, reply_markup=keyboard)
    
    async def handle_user_language_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора языка пользователем"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data == "user_set_lang_ru":
            self.set_user_language(user_id, 'ru')
            message = Translations.get('language_changed_ru', 'ru')
        elif data == "user_set_lang_en":
            self.set_user_language(user_id, 'en')
            message = Translations.get('language_changed_en', 'en')
        else:
            message = "❌ Ошибка выбора языка"
        
        # УБРАНА кнопка Start/Menu из основного меню
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="user_back_to_menu")]
        ])
        
        await query.message.edit_text(message, reply_markup=keyboard)
        await asyncio.sleep(1)
        
        # Возвращаемся в меню пользователя
        first_name = query.from_user.first_name
        await self.show_user_menu(update, first_name, context)
    
    async def show_reports_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню отчетов - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        query = update.callback_query
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем статистику
                c.execute("SELECT COUNT(*) FROM documents")
                total_docs = c.fetchone()[0] or 0
                
                c.execute('''SELECT COUNT(DISTINCT doc_id) FROM recipients 
                        WHERE status = 'pending' ''')
                pending_docs = c.fetchone()[0] or 0
                
                c.execute('''SELECT COUNT(DISTINCT doc_id) FROM recipients 
                        WHERE status IN ('approved', 'rejected') ''')
                processed_docs = c.fetchone()[0] or 0
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Ошибка получения статистики отчетов: {e}")
            total_docs = pending_docs = processed_docs = 0
        
        keyboard_buttons = [
            [InlineKeyboardButton("📄 По конкретному документу", callback_data="report_document")],
            [InlineKeyboardButton("📊 Общая статистика", callback_data="report_statistics")],
            [InlineKeyboardButton("📅 За период", callback_data="report_period")],
            [InlineKeyboardButton("👥 По пользователям", callback_data="report_users")],
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        message = (
            f"📊 ОТЧЕТЫ ПО ДОКУМЕНТАМ\n\n"
            f"📈 Общая статистика:\n"
            f"• Всего документов: {total_docs}\n"
            f"• ⏳ В обработке: {pending_docs}\n"
            f"• ✅ Обработано: {processed_docs}\n\n"
            f"📋 Типы отчетов:\n\n"
            f"📄 По конкретному документу\n"
            f"- Детальная информация по документу\n"
            f"- Список получателей и их статусы\n"
            f"- Время ответов и комментарии\n\n"
            f"📊 Общая статистика\n"
            f"- Сводка по всем документам\n"
            f"- Эффективность согласования\n\n"
            f"📅 За период\n"
            f"- Отчет за выбранный период\n"
            f"- Динамика согласований\n\n"
            f"👥 По пользователям\n"
            f"- Статистика по каждому пользователю\n"
            f"- Количество документов\n\n"
            f"💡 Экспорт:\n"
            f"Все отчеты можно экспортировать в PDF/TXT форматы"
        )
        
        # ===== ВАЖНО: Проверяем тип сообщения =====
        if query:
            # Проверяем, есть ли текст в сообщении
            if query.message.text:
                # Если есть текст - редактируем
                await query.message.edit_text(message, reply_markup=keyboard)
            else:
                # Если нет текста (сообщение с документом) - отправляем новое
                await query.message.reply_text(message, reply_markup=keyboard)
        else:
            # Если это не callback (обычное сообщение)
            await update.message.reply_text(message, reply_markup=keyboard)
    
    async def handle_report_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на кнопки отчетов"""
        query = update.callback_query
        await query.answer()
        
        action = query.data
        
        if action == "report_document":
            await self.show_document_report_menu(update, context)
        elif action == "report_statistics":
            await self.export_statistics_report(update, context)
        elif action == "report_period":
            await self.show_period_report_menu(update, context)
        elif action == "report_users":
            await self.show_users_report(update, context)
        elif action.startswith("export_pdf_"):
            doc_id = action.replace("export_pdf_", "")
            await self.export_report_to_pdf(update, context, doc_id)
        elif action.startswith("export_txt_"):
            doc_id = action.replace("export_txt_", "")
            await self.export_report_to_txt(update, context, doc_id)
        elif action.startswith("export_stats_"):
            doc_id = action.replace("export_stats_", "")
            await self.export_statistics_report(update, context, doc_id)
        elif action == "menu_reports":  
            await self.show_reports_menu(update, context)
        elif action.startswith("export_pdf_"):
            doc_id = action.replace("export_pdf_", "")
            await self.export_report_to_pdf(update, context, doc_id)
    
    async def show_document_report_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню для выбора документа для отчета - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        query = update.callback_query
        await query.answer()
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем последние 10 документов
                c.execute('''SELECT d.id, d.created, 
                            GROUP_CONCAT(df.file_name, '; ') as files,
                            COUNT(r.id) as recipients_count
                            FROM documents d
                            LEFT JOIN document_files df ON d.id = df.doc_id
                            LEFT JOIN recipients r ON d.id = r.doc_id
                            GROUP BY d.id
                            ORDER BY d.created DESC
                            LIMIT 10''')
                
                documents = c.fetchall()
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Ошибка получения списка документов: {e}")
            documents = []
        
        if not documents:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад к отчетам", callback_data="menu_reports")]
            ])
            
            message = "📭 Нет документов для отчетов"
            
            if query.message.text:
                await query.message.edit_text(message, reply_markup=keyboard)
            else:
                await query.message.reply_text(message, reply_markup=keyboard)
            return
        
        keyboard_buttons = []
        
        for doc_id, created, files, recipients_count in documents:
            created_dt = datetime.strptime(created, '%Y-%m-%d %H:%M:%S')
            created_str = created_dt.strftime('%d.%m %H:%M')
            
            # Берем первое имя файла
            first_file = files.split(';')[0].strip() if files else "Без названия"
            if len(first_file) > 20:
                first_file = first_file[:17] + "..."
            
            button_text = f"{created_str} - {first_file}"
            if recipients_count:
                button_text += f" ({recipients_count})"
            
            keyboard_buttons.append([
                InlineKeyboardButton(button_text, callback_data=f"view_doc_report_{doc_id}")
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton("⬅️ Назад", callback_data="menu_reports")
        ])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        message = (
            "📄 ВЫБОР ДОКУМЕНТА ДЛЯ ОТЧЕТА\n\n"
            "Выберите документ из списка:\n\n"
            "📅 Формат:\n"
            "Дата - Название файла (получателей)\n\n"
            "💡 Для просмотра:\n"
            "Нажмите на документ для получения детального отчета"
        )
        
        if query.message.text:
            await query.message.edit_text(message, reply_markup=keyboard)
        else:
            await query.message.reply_text(message, reply_markup=keyboard)
    
    async def export_report_to_pdf(self, update: Update, context: ContextTypes.DEFAULT_TYPE, doc_id: str):
        """Экспорт отчета в PDF с поддержкой кириллицы"""
        query = update.callback_query
        await query.answer("📄 Генерирую PDF отчет...")
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем информацию о документе
                c.execute('''SELECT d.created, d.theme,
                            GROUP_CONCAT(df.file_name, '\n') as files,
                            GROUP_CONCAT(df.file_id, '\n') as file_ids
                            FROM documents d
                            LEFT JOIN document_files df ON d.id = df.doc_id
                            WHERE d.id = ?''', (doc_id,))
                
                doc_info = c.fetchone()
                
                if not doc_info:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Назад к отчетам", callback_data="menu_reports")]
                    ])
                    await query.message.edit_text("❌ Документ не найден", reply_markup=keyboard)
                    return
                
                created, theme, files, file_ids = doc_info
                
                # Получаем информацию о получателях
                c.execute('''SELECT c.name, c.phone, c.username, 
                            r.status, r.comment, r.response_time,
                            r.sent_via, r.comment_only
                            FROM recipients r
                            LEFT JOIN contacts c ON r.contact_id = c.id
                            WHERE r.doc_id = ?
                            ORDER BY 
                                CASE r.status 
                                    WHEN 'approved' THEN 1
                                    WHEN 'rejected' THEN 2
                                    WHEN 'pending' THEN 3
                                    ELSE 4
                                END,
                                r.response_time DESC''', (doc_id,))
                
                recipients = c.fetchall()
                
                # Получаем статистику
                c.execute('''SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                            SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                            SUM(CASE WHEN comment_only = 1 THEN 1 ELSE 0 END) as comment_only
                            FROM recipients WHERE doc_id = ?''', (doc_id,))
                
                stats = c.fetchone()
                total, approved, rejected, pending, comment_only = stats if stats else (0, 0, 0, 0, 0)
            
            # Создаем PDF в памяти
            pdf_buffer = io.BytesIO()
            
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            import textwrap
            import os
            
            # ===== ВАЖНО: РЕГИСТРИРУЕМ ШРИФТ С ПОДДЕРЖКОЙ КИРИЛЛИЦЫ =====
            font_registered = False
            
            # Пробуем разные пути к шрифтам в зависимости от ОС
            font_paths = []
            
            # Windows
            if os.name == 'nt':
                font_paths = [
                    'C:\\Windows\\Fonts\\arial.ttf',
                    'C:\\Windows\\Fonts\\times.ttf',
                    'C:\\Windows\\Fonts\\verdana.ttf',
                    'C:\\Windows\\Fonts\\tahoma.ttf'
                ]
            # Linux
            else:
                font_paths = [
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                    '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
                    '/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf'
                ]
            
            # Пробуем зарегистрировать шрифт
            for font_path in font_paths:
                try:
                    if os.path.exists(font_path):
                        pdfmetrics.registerFont(TTFont('CyrillicFont', font_path))
                        font_registered = True
                        print(f"✅ Шрифт зарегистрирован: {font_path}")
                        break
                except:
                    continue
            
            # Если не нашли системный шрифт, используем встроенный шрифт ReportLab
            if not font_registered:
                # Используем стандартный шрифт, но он может не поддерживать кириллицу
                from reportlab.pdfbase.pdfmetrics import registerFont
                from reportlab.pdfbase.ttfonts import TTFont
                # Пробуем загрузить шрифт из текущей директории
                if os.path.exists('DejaVuSans.ttf'):
                    pdfmetrics.registerFont(TTFont('CyrillicFont', 'DejaVuSans.ttf'))
                    font_registered = True
                else:
                    # Если ничего не нашли, используем Helvetica (может не работать с кириллицей)
                    print("⚠️ Шрифт с кириллицей не найден, используется стандартный")
            
            # Настраиваем документ
            doc = SimpleDocTemplate(
                pdf_buffer,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72,
            )
            
            # Стили
            styles = getSampleStyleSheet()
            
            # Определяем имя шрифта для использования
            font_name = 'CyrillicFont' if font_registered else 'Helvetica'
            font_name_bold = 'CyrillicFont' if font_registered else 'Helvetica-Bold'
            
            # Создаем стиль с поддержкой кириллицы
            normal_style = ParagraphStyle(
                'Normal',
                parent=styles['Normal'],
                fontName=font_name,
                fontSize=10,
                leading=12,
                encoding='utf-8'
            )
            
            title_style = ParagraphStyle(
                'Title',
                parent=styles['Title'],
                fontName=font_name_bold,
                fontSize=16,
                leading=20,
                alignment=1,  # Center alignment
                encoding='utf-8'
            )
            
            heading_style = ParagraphStyle(
                'Heading',
                parent=styles['Heading2'],
                fontName=font_name_bold,
                fontSize=12,
                leading=16,
                spaceAfter=6,
                encoding='utf-8'
            )
            
            # Собираем элементы PDF
            elements = []
            
            # Заголовок
            elements.append(Paragraph("ФИНАЛЬНЫЙ ОТЧЕТ ПО ДОКУМЕНТУ", title_style))
            elements.append(Spacer(1, 0.3*inch))
            
            # Информация о документе
            elements.append(Paragraph(f"<b>ID документа:</b> {doc_id}", normal_style))
            if theme:
                elements.append(Paragraph(f"<b>Тема:</b> {theme}", normal_style))
            
            # Форматируем дату создания
            if created:
                try:
                    created_dt = datetime.strptime(created, '%Y-%m-%d %H:%M:%S')
                    created_str = created_dt.strftime('%d.%m.%Y %H:%M:%S')
                    elements.append(Paragraph(f"<b>Дата создания:</b> {created_str}", normal_style))
                except:
                    pass
            
            elements.append(Spacer(1, 0.2*inch))
            
            # Информация о файлах
            if files:
                file_list = files.split('\n')
                elements.append(Paragraph(f"<b>Документы ({len(file_list)}):</b>", heading_style))
                elements.append(Spacer(1, 0.1*inch))
                
                for i, file_name in enumerate(file_list, 1):
                    # Обрезаем длинные имена
                    if len(file_name) > 60:
                        file_name = file_name[:57] + "..."
                    elements.append(Paragraph(f"{i}. {file_name}", normal_style))
                
                elements.append(Spacer(1, 0.2*inch))
            
            # Статистика
            elements.append(Paragraph("СТАТИСТИКА СОГЛАСОВАНИЯ", heading_style))
            elements.append(Spacer(1, 0.1*inch))
            
            # Создаем таблицу статистики
            stats_data = [
                ['Показатель', 'Количество'],
                ['Всего получателей', str(total)],
                ['Согласовано', str(approved)],
                ['Отклонено', str(rejected)],
                ['Только комментарий', str(comment_only)],
                ['Ожидает решения', str(pending)],
            ]
            
            stats_table = Table(stats_data, colWidths=[2.5*inch, 1.5*inch])
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), font_name_bold),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, 1), (-1, -1), font_name),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(stats_table)
            elements.append(Spacer(1, 0.2*inch))
            
            # Эффективность
            if total > 0:
                completion_rate = (approved + rejected + comment_only) / total * 100
                if approved + rejected > 0:
                    approval_rate = approved / (approved + rejected) * 100
                else:
                    approval_rate = 0
                
                elements.append(Paragraph(f"<b>Завершено согласование:</b> {completion_rate:.1f}%", normal_style))
                elements.append(Paragraph(f"<b>Процент согласования:</b> {approval_rate:.1f}%", normal_style))
                elements.append(Spacer(1, 0.2*inch))
            
            # Список получателей
            if recipients:
                elements.append(Paragraph("ПОЛУЧАТЕЛИ", heading_style))
                elements.append(Spacer(1, 0.2*inch))
                
                for i, (name, phone, username, status, comment, response_time, sent_via, comment_only_flag) in enumerate(recipients, 1):
                    # Формируем имя получателя
                    if name:
                        recipient_name = name
                    elif phone:
                        recipient_name = phone
                    elif username:
                        recipient_name = f"@{username}"
                    else:
                        recipient_name = f"Получатель {i}"
                    
                    elements.append(Paragraph(f"<b>{i}. {recipient_name}</b>", normal_style))
                    
                    # Контактная информация
                    contact_info = []
                    if phone:
                        contact_info.append(f"Телефон: {phone}")
                    if username:
                        contact_info.append(f"Username: @{username}")
                    if contact_info:
                        elements.append(Paragraph(f"   {', '.join(contact_info)}", normal_style))
                    
                    # Статус
                    if comment_only_flag:
                        status_text = "Только комментарий"
                    elif status == 'approved':
                        status_text = "Согласовано"
                    elif status == 'rejected':
                        status_text = "Отклонено"
                    elif status == 'pending':
                        status_text = "Ожидает решения"
                    else:
                        status_text = "Не отправлено"
                    
                    status_line = f"   Статус: {status_text}"
                    if sent_via:
                        status_line += f" (метод: {sent_via})"
                    elements.append(Paragraph(status_line, normal_style))
                    
                    # Комментарий
                    if comment:
                        # Разбиваем длинный комментарий на строки
                        comment_lines = textwrap.wrap(comment, width=80)
                        elements.append(Paragraph(f"   Комментарий:", normal_style))
                        for line in comment_lines:
                            elements.append(Paragraph(f"      {line}", normal_style))
                    
                    # Время ответа
                    if response_time:
                        try:
                            resp_dt = datetime.strptime(response_time, '%Y-%m-%d %H:%M:%S')
                            resp_str = resp_dt.strftime('%d.%m.%Y %H:%M')
                            elements.append(Paragraph(f"   Время ответа: {resp_str}", normal_style))
                        except:
                            pass
                    
                    elements.append(Spacer(1, 0.1*inch))
            
            # Подвал
            elements.append(Spacer(1, 0.2*inch))
            elements.append(Paragraph("─" * 50, normal_style))
            elements.append(Paragraph(f"Отчет сгенерирован: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}", normal_style))
            elements.append(Paragraph("DocFlow - Система согласования документов", normal_style))
            
            # Строим PDF
            doc.build(elements)
            
            # Перематываем буфер в начало
            pdf_buffer.seek(0)
            
            # Формируем имя файла
            first_file = files.split('\n')[0][:30] if files else "document"
            safe_filename = re.sub(r'[^\w\s-]', '', first_file).strip().replace(' ', '_')
            filename = f"report_{doc_id}_{safe_filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            # Отправляем PDF документ
            await query.message.reply_document(
                document=pdf_buffer,
                filename=filename,
                caption=f"PDF отчет по документу\nID: {doc_id}\nВсего получателей: {total}"
            )
            
            # Кнопка возврата к отчетам
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад к отчетам", callback_data="menu_reports")]
            ])
            
            await query.message.reply_text(
                f"PDF отчет для документа {doc_id} отправлен!\n\nНажмите кнопку ниже для возврата в меню отчетов.",
                reply_markup=keyboard
            )
            
            logger.info(f"✅ PDF отчет отправлен для документа {doc_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания PDF отчета: {e}", exc_info=True)
            
            # Отправляем сообщение об ошибке с кнопками
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Попробовать TXT отчет", callback_data=f"export_txt_{doc_id}")],
                [InlineKeyboardButton("⬅️ Назад к отчетам", callback_data="menu_reports")]
            ])
            
            await query.message.edit_text(
                f"❌ Ошибка при создании PDF отчета:\n{str(e)[:200]}\n\n"
                f"💡 Попробуйте использовать TXT формат.",
                reply_markup=keyboard
            )
    
    async def export_report_to_txt(self, update: Update, context: ContextTypes.DEFAULT_TYPE, doc_id: str):
        """Экспорт отчета в TXT"""
        query = update.callback_query
        await query.answer("⏳ Генерирую TXT отчет...")
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем информацию о документе
                c.execute('''SELECT d.created, 
                            GROUP_CONCAT(df.file_name, '\n') as files
                            FROM documents d
                            LEFT JOIN document_files df ON d.id = df.doc_id
                            WHERE d.id = ?''', (doc_id,))
                
                doc_info = c.fetchone()
                
                if not doc_info:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Назад к отчетам", callback_data="menu_reports")]
                    ])
                    
                    await query.message.edit_text("❌ Документ не найден", reply_markup=keyboard)
                    return
                
                created, files = doc_info
                created_dt = datetime.strptime(created, '%Y-%m-%d %H:%M:%S')
                created_str = created_dt.strftime('%d.%m.%Y %H:%M:%S')
                
                # Получаем информацию о получателях
                c.execute('''SELECT c.name, c.phone, c.username, 
                            r.status, r.comment, r.response_time,
                            r.sent_via, r.comment_only
                            FROM recipients r
                            LEFT JOIN contacts c ON r.contact_id = c.id
                            WHERE r.doc_id = ?
                            ORDER BY r.response_time DESC''', (doc_id,))
                
                recipients = c.fetchall()
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Ошибка получения данных для отчета: {e}")
            await query.message.edit_text("❌ Ошибка базы данных при формировании отчета")
            return
        
        # Формируем TXT отчет
        txt_report = "=" * 60 + "\n"
        txt_report += "ОТЧЕТ ПО ДОКУМЕНТУ\n"
        txt_report += "=" * 60 + "\n\n"
        
        txt_report += f"ID документа: {doc_id}\n"
        txt_report += f"Дата создания: {created_str}\n\n"
        
        if files:
            file_list = files.split('\n')
            txt_report += f"Файлы ({len(file_list)}):\n"
            for i, file_name in enumerate(file_list, 1):
                txt_report += f"  {i}. {file_name}\n"
            txt_report += "\n"
        
        txt_report += "ПОЛУЧАТЕЛИ:\n"
        txt_report += "-" * 40 + "\n\n"
        
        if recipients:
            approved = 0
            rejected = 0
            pending = 0
            comment_only = 0
            
            for name, phone, username, status, comment, response_time, sent_via, comment_only_flag in recipients:
                txt_report += "▫️ "
                if name:
                    txt_report += f"{name}\n"
                
                if phone:
                    txt_report += f"  Телефон: {phone}\n"
                elif username:
                    txt_report += f"  Username: @{username}\n"
                
                # Определяем статус
                if comment_only_flag:
                    status_text = "💬 Только комментарий"
                    comment_only += 1
                elif status == 'approved':
                    status_text = '✅ Согласовано'
                    approved += 1
                elif status == 'rejected':
                    status_text = '❌ Отклонено'
                    rejected += 1
                elif status == 'pending':
                    status_text = '⏳ Ожидает'
                    pending += 1
                else:
                    status_text = '📨 Не отправлено'
                
                txt_report += f"  Статус: {status_text}"
                if sent_via:
                    txt_report += f" ({sent_via})"
                txt_report += "\n"
                
                if comment:
                    txt_report += f"  Комментарий: {comment}\n"
                
                if response_time:
                    resp_dt = datetime.strptime(response_time, '%Y-%m-%d %H:%M:%S')
                    resp_str = resp_dt.strftime('%d.%m.%Y %H:%M')
                    txt_report += f"  Время ответа: {resp_str}\n"
                
                txt_report += "\n"
            
            txt_report += "=" * 60 + "\n"
            txt_report += "СТАТИСТИКА:\n"
            txt_report += "-" * 40 + "\n\n"
            
            total = len(recipients)
            txt_report += f"Всего получателей: {total}\n"
            txt_report += f"✅ Согласовано: {approved}\n"
            txt_report += f"❌ Отклонено: {rejected}\n"
            txt_report += f"💬 Только комментарий: {comment_only}\n"
            txt_report += f"⏳ Ожидает: {pending}\n\n"
            
            if total > 0:
                completion_rate = (approved + rejected + comment_only) / total * 100
                if approved + rejected > 0:
                    approval_rate = approved / (approved + rejected) * 100
                else:
                    approval_rate = 0
                
                txt_report += f"Завершено согласование: {completion_rate:.1f}%\n"
                txt_report += f"Процент согласования: {approval_rate:.1f}%\n"
        
        txt_report += "\n" + "=" * 60 + "\n"
        txt_report += f"Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        txt_report += "=" * 60
        
        # Создаем файл в памяти
        txt_bytes = txt_report.encode('utf-8')
        txt_file = io.BytesIO(txt_bytes)
        txt_file.name = f"report_{doc_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        # Отправляем TXT документ
        await query.message.reply_document(
            document=txt_file,
            caption=f"📝 TXT отчет по документу\n🆔 ID: {doc_id}"
        )
        
        # ===== ИСПРАВЛЕНИЕ: ТОЛЬКО КНОПКА НАЗАД, БЕЗ PDF =====
        keyboard_buttons = [
            [InlineKeyboardButton("⬅️ НАЗАД К ОТЧЕТАМ", callback_data="menu_reports")]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await query.message.reply_text(
            f"📝 TXT отчет отправлен!\n\nВыберите действие:",
            reply_markup=keyboard
        )
    
    async def export_statistics_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE, specific_doc_id: str = None):
        """Экспорт статистического отчета"""
        query = update.callback_query
        if query:
            await query.answer("⏳ Генерирую статистику...")
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                if specific_doc_id:
                    # Статистика по конкретному документу
                    c.execute('''SELECT 
                                 COUNT(*) as total_recipients,
                                 SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                                 SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                                 SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                                 SUM(CASE WHEN comment_only = 1 THEN 1 ELSE 0 END) as comment_only
                                 FROM recipients 
                                 WHERE doc_id = ?''', (specific_doc_id,))
                    
                    stats = c.fetchone()
                    total, approved, rejected, pending, comment_only = stats if stats else (0, 0, 0, 0, 0)
                    
                    message = f"📊 *СТАТИСТИКА ПО ДОКУМЕНТУ*\n\n"
                    message += f"🆔 ID: {specific_doc_id}\n\n"
                    message += f"👥 *Получатели:*\n"
                    message += f"• Всего: {total or 0}\n"
                    message += f"• ✅ Согласовано: {approved or 0}\n"
                    message += f"• ❌ Отклонено: {rejected or 0}\n"
                    message += f"• 💬 Только комментарий: {comment_only or 0}\n"
                    message += f"• ⏳ Ожидает: {pending or 0}\n\n"
                    
                    if total and total > 0:
                        completion_rate = ((approved or 0) + (rejected or 0) + (comment_only or 0)) / total * 100
                        if (approved or 0) + (rejected or 0) > 0:
                            approval_rate = (approved or 0) / ((approved or 0) + (rejected or 0)) * 100
                        else:
                            approval_rate = 0
                        
                        message += f"📈 *Эффективность:*\n"
                        message += f"• Завершено: {completion_rate:.1f}%\n"
                        message += f"• Согласовано: {approval_rate:.1f}%\n\n"
                else:
                    # Общая статистика
                    c.execute("SELECT COUNT(*) FROM documents")
                    total_docs = c.fetchone()[0] or 0
                    
                    c.execute("SELECT COUNT(*) FROM contacts")
                    total_contacts = c.fetchone()[0] or 0
                    
                    c.execute("SELECT COUNT(*) FROM contacts WHERE telegram_id IS NOT NULL")
                    active_users = c.fetchone()[0] or 0
                    
                    c.execute('''SELECT 
                                 COUNT(*) as total_recipients,
                                 SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                                 SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                                 SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                                 SUM(CASE WHEN comment_only = 1 THEN 1 ELSE 0 END) as comment_only
                                 FROM recipients''')
                    
                    stats = c.fetchone()
                    total_recipients, approved, rejected, pending, comment_only = stats if stats else (0, 0, 0, 0, 0)
                    
                    message = "📊 *ОБЩАЯ СТАТИСТИКА СИСТЕМЫ*\n\n"
                    
                    message += f"📄 *Документы:*\n"
                    message += f"• Всего документов: {total_docs}\n\n"
                    
                    message += f"👥 *Пользователи:*\n"
                    message += f"• Всего контактов: {total_contacts}\n"
                    message += f"• Активированных: {active_users}\n"
                    message += f"• Не активированных: {total_contacts - active_users}\n\n"
                    
                    message += f"📨 *Отправки документов:*\n"
                    message += f"• Всего отправок: {total_recipients or 0}\n"
                    message += f"• ✅ Согласовано: {approved or 0}\n"
                    message += f"• ❌ Отклонено: {rejected or 0}\n"
                    message += f"• 💬 Только комментарий: {comment_only or 0}\n"
                    message += f"• ⏳ Ожидает: {pending or 0}\n\n"
                    
                    if total_recipients and total_recipients > 0:
                        completion_rate = ((approved or 0) + (rejected or 0) + (comment_only or 0)) / total_recipients * 100
                        if (approved or 0) + (rejected or 0) > 0:
                            approval_rate = (approved or 0) / ((approved or 0) + (rejected or 0)) * 100
                        else:
                            approval_rate = 0
                        
                        activation_rate = active_users / max(total_contacts, 1) * 100
                        
                        message += f"📈 *ЭФФЕКТИВНОСТЬ:*\n"
                        message += f"• Активация пользователей: {activation_rate:.1f}%\n"
                        message += f"• Завершено согласований: {completion_rate:.1f}%\n"
                        message += f"• Процент согласования: {approval_rate:.1f}%\n\n"
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            message = "❌ Ошибка базы данных при получении статистики"
        
        keyboard_buttons = []
        if specific_doc_id:
            keyboard_buttons.append([
                InlineKeyboardButton("📄 Подробный отчет", callback_data=f"export_txt_{specific_doc_id}")
            ])
        keyboard_buttons.append([
            InlineKeyboardButton("⬅️ Назад к отчетам", callback_data="menu_reports")
        ])
        
        # УБРАНА кнопка Start/Menu из основного меню
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        if query:
            await query.message.edit_text(message, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await update.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
    
    async def show_period_report_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню отчетов за период - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        query = update.callback_query
        await query.answer()
        
        keyboard_buttons = [
            [
                InlineKeyboardButton("📅 Сегодня", callback_data="period_today"),
                InlineKeyboardButton("📅 Неделя", callback_data="period_week")
            ],
            [
                InlineKeyboardButton("📅 Месяц", callback_data="period_month"),
                InlineKeyboardButton("📅 Все время", callback_data="period_all")
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu_reports")]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        message = (
            "📅 ОТЧЕТ ЗА ПЕРИОД\n\n"
            "Выберите период для отчета:\n\n"
            "📅 Сегодня - данные за сегодняшний день\n"
            "📅 Неделя - данные за последние 7 дней\n"
            "📅 Месяц - данные за последние 30 дней\n"
            "📅 Все время - полная статистика\n\n"
            "💡 В отчете будет:\n"
            "• Количество документов\n"
            "• Активность пользователей\n"
            "• Статистика согласований\n"
            "• Эффективность работы"
        )
        
        # ===== Проверяем тип сообщения =====
        if query.message.text:
            await query.message.edit_text(message, reply_markup=keyboard)
        else:
            await query.message.reply_text(message, reply_markup=keyboard)
    
    async def show_users_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает отчет по пользователям"""
        query = update.callback_query
        await query.answer()
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем статистику по пользователям
                c.execute('''SELECT c.name, c.phone, c.username, c.telegram_id,
                            COUNT(r.id) as total_docs,
                            SUM(CASE WHEN r.status = 'approved' THEN 1 ELSE 0 END) as approved,
                            SUM(CASE WHEN r.status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                            SUM(CASE WHEN r.status = 'pending' THEN 1 ELSE 0 END) as pending,
                            SUM(CASE WHEN r.comment_only = 1 THEN 1 ELSE 0 END) as comment_only
                            FROM contacts c
                            LEFT JOIN recipients r ON c.id = r.contact_id
                            GROUP BY c.id
                            ORDER BY total_docs DESC, c.last_activity DESC
                            LIMIT 20''')
                
                users = c.fetchall()
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Ошибка получения отчета по пользователям: {e}")
            users = []
        
        if not users:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад к отчетам", callback_data="menu_reports")]
            ])
            
            await query.message.edit_text("📭 Нет данных о пользователях", reply_markup=keyboard)
            return
        
        message = "👥 ОТЧЕТ ПО ПОЛЬЗОВАТЕЛЯМ\n\n"
        message += f"📊 Всего пользователей в отчете: {len(users)}\n\n"
        
        for i, (name, phone, username, telegram_id, total_docs, approved, rejected, pending, comment_only) in enumerate(users, 1):
            message += f"{i}. "
            
            if name:
                message += f"{name}\n"
            elif phone:
                message += f"{phone}\n"
            elif username:
                message += f"@{username}\n"
            else:
                message += f"Пользователь #{i}\n"
            
            if phone and username:
                message += f"   📱 {phone} | 👤 @{username}\n"
            elif phone:
                message += f"   📱 {phone}\n"
            elif username:
                message += f"   👤 @{username}\n"
            
            if telegram_id:
                message += f"   ✅ Активирован (ID: {telegram_id})\n"
            else:
                message += f"   ⏳ Не активирован\n"
            
            if total_docs and total_docs > 0:
                message += f"   📄 Документов: {total_docs}\n"
                message += f"      ✅ Согласовано: {approved or 0}\n"
                message += f"      ❌ Отклонено: {rejected or 0}\n"
                message += f"      💬 Только комментарий: {comment_only or 0}\n"
                message += f"      ⏳ Ожидает: {pending or 0}\n"
            
            message += "\n"
        
        keyboard_buttons = [
            [
                InlineKeyboardButton("📄 PDF отчет", callback_data="export_users_pdf"),
                InlineKeyboardButton("📝 TXT отчет", callback_data="export_users_txt")
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu_reports")]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await query.message.edit_text(message, reply_markup=keyboard)
    
    async def show_contacts_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню контактов"""
        query = update.callback_query
        if query:
            await query.answer()
            logger.info(f"📋 Показ меню контактов для пользователя {query.from_user.id}")
        
        keyboard_buttons = [
            [
                InlineKeyboardButton("📱 С телефонами", callback_data="contacts_phone"),
            ],
            [
                InlineKeyboardButton("✅ Активные", callback_data="contacts_active"),
                InlineKeyboardButton("📋 Все", callback_data="contacts_all")
            ],
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        message_text = (
            "📋 Управление контактами\n\n"
            "Выберите тип контактов для просмотра:\n\n"
            "📱 С телефонами - только контакты с номерами телефонов\n"
            "✅ Активные - пользователи, которые активировали бота\n"
            "📋 Все - полный список всех контактов"
        )
        
        try:
            if query:
                await query.message.edit_text(message_text, reply_markup=keyboard)
                logger.info("✅ Меню контактов отображено")
            else:
                await update.message.reply_text(message_text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"❌ Ошибка показа меню контактов: {e}")
            # Если не удалось отредактировать, пробуем отправить новое сообщение
            if query:
                await query.message.reply_text(message_text, reply_markup=keyboard)
    
    async def handle_contacts_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на кнопки контактов - ПОЛНОСТЬЮ ПЕРЕПИСАНА"""
        query = update.callback_query
        if not query:
            return
        
        await query.answer()
        action = query.data
        user_id = query.from_user.id
        
        logger.info(f"📱 Нажата кнопка контактов: {action} от пользователя {user_id}")
        
        try:
            if action == "contacts_phone":
                logger.info("📱 Запрос контактов с телефонами")
                await self.show_contacts_list(update, context, 'phone')
            elif action == "contacts_active":
                logger.info("✅ Запрос активных контактов")
                await self.show_contacts_list(update, context, 'active')
            elif action == "contacts_all":
                logger.info("📋 Запрос всех контактов")
                await self.show_contacts_list(update, context, 'all')
            elif action == "menu_add":
                logger.info("➕ Переход к добавлению контакта")
                await self.show_add_menu(update, context)
            elif action == "menu_back":
                logger.info("⬅️ Возврат в главное меню")
                await self.show_admin_menu(update, context)
            else:
                logger.warning(f"⚠️ Неизвестное действие: {action}")
        except Exception as e:
            logger.error(f"❌ Ошибка в handle_contacts_callback: {e}")
            logger.error(traceback.format_exc())
            await query.message.reply_text(f"❌ Произошла ошибка: {str(e)[:100]}")
    
    async def show_contacts_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE, filter_type: str = 'all'):
        """Показывает список контактов с фильтрацией - ИСПРАВЛЕННАЯ ВЕРСИЯ (без Markdown)"""
        query = update.callback_query
        if not query:
            return
        
        await query.answer()
        logger.info(f"📋 Загрузка контактов с фильтром: {filter_type}")
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем контакты в зависимости от фильтра
                if filter_type == 'phone':
                    c.execute('''
                        SELECT phone, username, name, telegram_id, last_activity 
                        FROM contacts 
                        WHERE phone IS NOT NULL AND phone != '' 
                        ORDER BY 
                            CASE WHEN telegram_id IS NOT NULL THEN 1 ELSE 2 END,
                            last_activity DESC NULLS LAST, 
                            name
                    ''')
                    title = "📱 Контакты с телефонами"
                elif filter_type == 'active':
                    c.execute('''
                        SELECT phone, username, name, telegram_id, last_activity 
                        FROM contacts 
                        WHERE telegram_id IS NOT NULL 
                        ORDER BY last_activity DESC NULLS LAST, name
                    ''')
                    title = "✅ Активные пользователи"
                else:  # 'all'
                    c.execute('''
                        SELECT phone, username, name, telegram_id, last_activity 
                        FROM contacts 
                        WHERE (phone IS NOT NULL AND phone != '') 
                        OR (username IS NOT NULL AND username != '')
                        ORDER BY 
                            CASE WHEN telegram_id IS NOT NULL THEN 1 ELSE 2 END,
                            last_activity DESC NULLS LAST, 
                            name
                    ''')
                    title = "📋 Все контакты"
                
                contacts = c.fetchall()
                logger.info(f"📊 Найдено контактов: {len(contacts)}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при получении контактов: {e}")
            contacts = []
        
        if not contacts:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 Добавить контакт", callback_data="menu_add")],
                [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
            ])
            
            message = "📭 В базе нет контактов\n\n"
            message += "💡 Вы можете добавить контакты через меню:\n"
            message += "• 📱 Добавить контакт\n"
            message += "• Или командой /add"
            
            try:
                await query.message.edit_text(message, reply_markup=keyboard)
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке сообщения: {e}")
                await query.message.reply_text(message, reply_markup=keyboard)
            return
        
        # Подсчет статистики
        total = len(contacts)
        active = sum(1 for c in contacts if c[3] is not None)  # telegram_id
        with_phone = sum(1 for c in contacts if c[0] is not None)  # phone
        with_username = sum(1 for c in contacts if c[1] is not None)  # username
        
        # Формируем сообщение БЕЗ Markdown разметки (используем обычный текст)
        message = f"{title} (всего: {total})\n\n"
        message += f"📊 Статистика:\n"
        message += f"• ✅ Активных: {active}\n"
        message += f"• 📱 С телефонами: {with_phone}\n"
        message += f"• 👤 С username: {with_username}\n"
        message += f"• ⏳ Неактивных: {total - active}\n\n"
        
        message += f"📋 СПИСОК КОНТАКТОВ:\n"
        message += "─" * 40 + "\n\n"
        
        for i, (phone, username, name, telegram_id, last_activity) in enumerate(contacts, 1):
            if i > 20:  # Показываем только первые 20 контактов
                message += f"... и еще {total - 20} контактов\n\n"
                break
            
            # Определяем статус и имя
            status_icon = "✅" if telegram_id else "⏳"
            display_name = name or phone or f"@{username}" or f"Контакт #{i}"
            
            # Экранируем специальные символы для обычного текста
            display_name = display_name.replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')
            
            message += f"{i}. {status_icon} {display_name}\n"
            
            # Контактная информация
            info_parts = []
            if phone:
                info_parts.append(f"📱 {phone}")
            if username:
                info_parts.append(f"👤 @{username}")
            if info_parts:
                message += f"   {' | '.join(info_parts)}\n"
            
            # Статус активации
            if telegram_id:
                message += f"   ✅ Активирован (ID: {telegram_id})\n"
            else:
                message += f"   ⏳ Не активирован\n"
            
            # Последняя активность
            if last_activity:
                try:
                    last_dt = datetime.strptime(last_activity, '%Y-%m-%d %H:%M:%S')
                    last_str = last_dt.strftime('%d.%m.%Y %H:%M')
                    message += f"   🕐 Последняя активность: {last_str}\n"
                except:
                    pass
            
            message += "\n"
        
        # Клавиатура
        keyboard_buttons = [
            [
                InlineKeyboardButton("📱 С телефонами", callback_data="contacts_phone"),
                InlineKeyboardButton("✅ Активные", callback_data="contacts_active")
            ],
            [
                InlineKeyboardButton("📋 Все", callback_data="contacts_all"),
                InlineKeyboardButton("➕ Добавить", callback_data="menu_add")
            ],
            [
                InlineKeyboardButton("🔄 Обновить", callback_data=f"contacts_{filter_type}"),
                InlineKeyboardButton("⬅️ Назад", callback_data="menu_back")
            ]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        try:
            # Убираем parse_mode='Markdown' чтобы избежать ошибок форматирования
            await query.message.edit_text(message, reply_markup=keyboard)
            logger.info(f"✅ Список контактов ({filter_type}) успешно отображен")
        except Exception as e:
            logger.error(f"❌ Ошибка при отображении списка контактов: {e}")
            # Пробуем отправить новое сообщение
            await query.message.reply_text(message, reply_markup=keyboard)

    async def check_user_role(self, user_id: int):
        """Проверяет роль пользователя и дает соответствующий доступ"""
        with DatabaseManager.db_connection(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''SELECT role, is_admin, can_send_docs, can_manage_contacts, 
                        can_view_reports, auto_send_enabled 
                        FROM user_roles WHERE user_id = ?''', (user_id,))
            role_data = c.fetchone()
            
            if role_data:
                return {
                    'role': role_data[0],
                    'is_admin': role_data[1],
                    'can_send_docs': role_data[2],
                    'can_manage_contacts': role_data[3],
                    'can_view_reports': role_data[4],
                    'auto_send_enabled': role_data[5]
                }
        
        # По умолчанию обычный пользователь
        return {
            'role': 'user',
            'is_admin': False,
            'can_send_docs': False,
            'can_manage_contacts': False,
            'can_view_reports': False,
            'auto_send_enabled': False
        }

    async def promote_to_admin(self, user_id: int, phone: str = None):
        """Повышает пользователя до админа"""
        with DatabaseManager.db_connection(self.db_path) as conn:
            c = conn.cursor()
            
            # Проверяем, есть ли уже роль
            c.execute('SELECT role FROM user_roles WHERE user_id = ?', (user_id,))
            existing = c.fetchone()
            
            if existing:
                # Обновляем существующую роль
                c.execute('''UPDATE user_roles 
                            SET role = 'admin', 
                                is_admin = TRUE,
                                can_send_docs = TRUE,
                                can_manage_contacts = TRUE,
                                can_view_reports = TRUE,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE user_id = ?''', (user_id,))
            else:
                # Создаем новую роль
                c.execute('''INSERT INTO user_roles 
                            (user_id, role, is_admin, can_send_docs, can_manage_contacts, can_view_reports)
                            VALUES (?, 'admin', TRUE, TRUE, TRUE, TRUE)''', (user_id,))
            
            # Если есть телефон, обновляем или создаем контакт
            if phone:
                c.execute('''INSERT OR REPLACE INTO contacts (telegram_id, phone, name)
                            VALUES (?, ?, ?)''', (user_id, phone, f"Admin {user_id}"))
            
            conn.commit()
            
            logger.info(f"✅ Пользователь {user_id} повышен до админа с телефоном {phone}")

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start - с проверкой роли"""
        user_id = update.effective_user.id
        first_name = update.effective_user.first_name
        
        # Проверяем роль
        role_info = await self.check_user_role(user_id)
        
        # Проверяем, есть ли аргументы
        args = context.args
        if args:
            arg = args[0]
            if arg.startswith('doc_'):
                await self.handle_document_link(update, arg, user_id, context)
                return
            elif arg.startswith('phone_'):
                phone = arg.replace('phone_', '')
                await self.activate_user(user_id=user_id, phone=phone)
        
        # Если пользователь - админ, проверяем наличие сессии
        if role_info['is_admin'] or user_id == DEVELOPER_ADMIN_ID:
            # Проверяем сессию в боте авторизации
            session_data = get_admin_session(user_id)
            
            if session_data:
                phone, session_string, name = session_data
                
                # Если есть сессия, но пользователь еще не админ в нашей БД - повышаем
                if not role_info['is_admin'] and user_id != DEVELOPER_ADMIN_ID:
                    await self.promote_to_admin(user_id, phone)
                    role_info = await self.check_user_role(user_id)
                
                # Показываем админ-меню с активной сессией
                await self.show_admin_menu_with_session(update, context, phone)
            else:
                # Нет сессии - предлагаем авторизоваться
                await self.show_auth_required(update, context)
        else:
            # Обычный пользователь
            await self.activate_user(user_id=user_id)
            await self.show_user_menu(update, first_name, context)

    async def show_auth_required(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает сообщение о необходимости авторизации"""
        user_id = update.effective_user.id
        token = web_auth_service.create_link_token(user_id)
        link = f"{settings.web_auth_base_url}/auth/{token}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔐 Перейти к авторизации", url=link)],
            [InlineKeyboardButton("✅ Я уже авторизовался", callback_data="check_auth_status")]
        ])

        text = (
            "🔐 **Требуется авторизация**\n\n"
            "Для использования админ-панели необходимо подключить свой Telegram аккаунт "
            "через отдельную веб-страницу (не в этом чате — Telegram блокирует вход, "
            "если код подтверждения пересылается сообщением).\n\n"
            "📱 **Зачем это нужно?**\n"
            "• Безопасный вход в аккаунт Telegram\n"
            "• Автоматическая отправка документов\n"
            "• Доступ ко всем функциям админа\n\n"
            "👉 **Нажмите кнопку ниже, чтобы открыть страницу подключения** "
            "(ссылка действует 15 минут).\n\n"
            "После успешного входа нажмите «Я уже авторизовался»."
        )
        
        if update.message:
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode='Markdown')

    async def check_auth_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверяет статус авторизации"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        session_data = get_admin_session(user_id)
        
        if session_data:
            phone, session_string, name = session_data
            
            # Повышаем до админа если нужно
            role_info = await self.check_user_role(user_id)
            if not role_info['is_admin']:
                await self.promote_to_admin(user_id, phone)
            
            await query.message.edit_text(
                f"✅ **Авторизация подтверждена!**\n\n"
                f"📱 Телефон: {phone}\n"
                f"👤 Имя: {name or 'Не указано'}\n\n"
                f"🔓 **Доступ к админ-панели открыт!**"
            )
            
            # Показываем админ-меню
            await asyncio.sleep(1)
            await self.show_admin_menu_with_session(update, context, phone)
        else:
            token = web_auth_service.create_link_token(user_id)
            link = f"{settings.web_auth_base_url}/auth/{token}"
            await query.message.edit_text(
                "❌ **Авторизация не найдена**\n\n"
                "Пожалуйста, сначала подключите Telegram аккаунт через веб-страницу:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔐 Открыть страницу подключения", url=link)],
                    [InlineKeyboardButton("🔄 Проверить еще раз", callback_data="check_auth_status")]
                ])
            )

    async def show_admin_menu_with_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE, phone: str):
        """Показывает админ-меню с информацией о сессии"""
        user_id = update.effective_user.id
        lang = self.get_user_language(user_id)
        
        # Получаем статистику
        stats = await self.get_admin_stats()
        
        # Получаем всех активных админов
        active_admins = get_all_active_admins()
        
        keyboard_buttons = [
            [
                InlineKeyboardButton(Translations.get('send_document', lang), callback_data="menu_send_doc")
            ],
            [
                InlineKeyboardButton(Translations.get('contacts', lang), callback_data="menu_contacts"),
                InlineKeyboardButton(Translations.get('add', lang), callback_data="menu_add")
            ],
            [
                InlineKeyboardButton(Translations.get('reports', lang), callback_data="menu_reports"),
                InlineKeyboardButton(Translations.get('queue_status', lang), callback_data="menu_queue")
            ],
            [
                InlineKeyboardButton("👥 Управление админами", callback_data="menu_manage_admins")
            ],
            [
                InlineKeyboardButton(Translations.get('instructions', lang), callback_data="menu_instructions"),
                InlineKeyboardButton(Translations.get('change_language', lang), callback_data="menu_change_language")
            ]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        # Формируем сообщение
        message = (
            f"👑 **Панель администратора**\n\n"
            f"📱 **Активная сессия:** {phone}\n"
            f"🆔 **Ваш ID:** {user_id}\n\n"
            f"📊 **Статистика системы:**\n"
            f"• 👥 Всего админов: {stats['total_admins']}\n"
            f"• ✅ Активных сессий: {len(active_admins)}\n"
            f"• 📄 Документов: {stats['total_docs']}\n"
            f"• 📨 Ожидают отправки: {stats['pending']}\n\n"
            f"🤖 **Автоотправка:** {'✅ Вкл' if self.admin_sender else '❌ Выкл'}\n"
            f"📱 **Бот:** @{self.bot_username}\n\n"
            f"👇 Выберите действие:"
        )
        
        if update.message:
            await update.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.message.edit_text(message, reply_markup=keyboard, parse_mode='Markdown')

    async def get_admin_stats(self):
        """Получает статистику для админов"""
        with DatabaseManager.db_connection(self.db_path) as conn:
            c = conn.cursor()
            
            # Всего админов
            c.execute('SELECT COUNT(*) FROM user_roles WHERE is_admin = TRUE')
            total_admins = c.fetchone()[0] or 0
            
            # Всего документов
            c.execute('SELECT COUNT(*) FROM documents')
            total_docs = c.fetchone()[0] or 0
            
            # Ожидают отправки
            c.execute('''SELECT COUNT(*) FROM recipients WHERE status = 'pending' ''')
            pending = c.fetchone()[0] or 0
            
            return {
                'total_admins': total_admins,
                'total_docs': total_docs,
                'pending': pending
            }

    async def show_admin_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Управление админами (только для суперадмина)"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Только разработчик может управлять админами
        if user_id != DEVELOPER_ADMIN_ID:
            await query.message.edit_text("❌ У вас нет прав для управления админами")
            return
        
        # Получаем всех админов
        with DatabaseManager.db_connection(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''SELECT u.user_id, u.role, u.created_at, 
                        c.phone, c.name, c.username,
                        s.is_active as session_active
                        FROM user_roles u
                        LEFT JOIN contacts c ON u.user_id = c.telegram_id
                        LEFT JOIN auth_sessions s ON u.user_id = s.user_id AND s.is_active = TRUE
                        WHERE u.is_admin = TRUE
                        ORDER BY u.created_at DESC''')
            admins = c.fetchall()
        
        message = "👥 **Управление администраторами**\n\n"
        
        keyboard_buttons = []
        
        for i, (admin_id, role, created, phone, name, username, session_active) in enumerate(admins, 1):
            status = "✅ Активен" if session_active else "❌ Неактивен"
            display_name = name or username or f"ID: {admin_id}"
            
            message += f"{i}. **{display_name}**\n"
            message += f"   🆔 ID: {admin_id}\n"
            message += f"   📱 Телефон: {phone or 'не указан'}\n"
            message += f"   🔑 Роль: {role}\n"
            message += f"   📊 Статус: {status}\n"
            message += f"   📅 Создан: {created[:16] if created else 'неизвестно'}\n\n"
            
            if admin_id != DEVELOPER_ADMIN_ID:
                keyboard_buttons.append([
                    InlineKeyboardButton(f"❌ Удалить {display_name[:15]}", callback_data=f"remove_admin_{admin_id}")
                ])
        
        keyboard_buttons.append([
            InlineKeyboardButton("➕ Пригласить админа", callback_data="invite_admin"),
            InlineKeyboardButton("⬅️ Назад", callback_data="menu_back")
        ])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await query.message.edit_text(message, reply_markup=keyboard, parse_mode='Markdown')

    async def invite_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Генерирует приглашение для нового админа"""
        query = update.callback_query
        await query.answer()
        
        if query.from_user.id != DEVELOPER_ADMIN_ID:
            return
        
        invite_code = str(uuid.uuid4())[:8]
        
        with DatabaseManager.db_connection(self.db_path) as conn:
            c = conn.cursor()
            expires_at = datetime.now() + timedelta(days=7)
            c.execute('''INSERT INTO admin_invites 
                        (invited_by, invite_code, expires_at)
                        VALUES (?, ?, ?)''', 
                    (DEVELOPER_ADMIN_ID, invite_code, expires_at))
            conn.commit()
        
        invite_link = f"https://t.me/{self.bot_username}?start=invite_{invite_code}"
        
        message = (
            "🔐 **Приглашение нового администратора**\n\n"
            f"📋 Код: `{invite_code}`\n"
            f"⏳ Действителен: 7 дней\n\n"
            f"🔗 **Ссылка-приглашение:**\n{invite_link}\n\n"
            "Пользователь, перейдя по ссылке, сможет стать администратором "
            "после авторизации в боте."
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад к админам", callback_data="menu_manage_admins")]
        ])
        
        await query.message.edit_text(message, reply_markup=keyboard)

    async def handle_invite_link(self, update: Update, invite_code: str, user_id: int):
        """Обработка ссылки-приглашения"""
        with DatabaseManager.db_connection(self.db_path) as conn:
            c = conn.cursor()
            
            # Проверяем код
            c.execute('''SELECT id, invited_by, expires_at 
                        FROM admin_invites 
                        WHERE invite_code = ? AND status = 'pending' 
                        AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)''', 
                    (invite_code,))
            invite = c.fetchone()
            
            if invite:
                invite_id, invited_by, expires_at = invite
                
                # Обновляем статус приглашения
                c.execute('''UPDATE admin_invites 
                            SET status = 'used', used_at = CURRENT_TIMESTAMP 
                            WHERE id = ?''', (invite_id,))
                
                # Создаем запись о пользователе (но админом станет после авторизации)
                c.execute('''INSERT OR IGNORE INTO user_roles (user_id, role, is_admin)
                            VALUES (?, 'pending_admin', FALSE)''', (user_id,))
                
                conn.commit()
                
                return True, invited_by
        
        return False, None

    def escape_markdown(self, text: str) -> str:
        """Экранирует специальные символы Markdown"""
        if not text:
            return text
        
        # Символы, которые нужно экранировать в Markdown
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        
        # Экранируем каждый специальный символ
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        
        return text
    
    async def show_add_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню добавления контакта с инструкцией"""
        query = update.callback_query
        if query:
            await query.answer()

        keyboard_buttons = [
            [
                InlineKeyboardButton("📱 По телефону", callback_data="add_phone"),
            ],
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
        ]

        keyboard = InlineKeyboardMarkup(keyboard_buttons)

        if query:
            await query.message.edit_text(
                "➕ Добавление контакта\n\n"
                "Выберите способ добавления:\n\n"
                "📱 По телефону - добавление по номеру телефона\n\n"
                "📝 **ИНСТРУКЦИЯ:**\n"
                "1. Выберите тип контакта\n"
                "2. Введите информацию в формате:\n"
                "   • **С пробелами:** +7 <PHONE_NUMBER> Иван Петров\n"
                "   • **Без пробелов:** <PHONE_NUMBER> Иван Петров\n"
                "   • **Скобки/тире:** <PHONE_NUMBER> Иван Петров\n\n"
                "🤖 **Бот автоматически:**\n"
                "• Нормализует номер в формат +7XXXXXXXXXX\n"
                "• Для телефона - попробует отправить автоматически",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "➕ Добавление контакта\n\n"
                "Выберите способ добавления:\n\n"
                "📱 По телефону - добавление по номеру телефона\n\n"
                "📝 **ИНСТРУКЦИЯ:**\n"
                "1. Выберите тип контакта\n"
                "2. Введите информацию в формате:\n"
                "   • **С пробелами:** +7 <PHONE_NUMBER> Иван Петров\n"
                "   • **Без пробелов:** <PHONE_NUMBER> Иван Петров\n"
                "   • **Скобки/тире:** <PHONE_NUMBER> Иван Петров\n\n"
                "🤖 **Бот автоматически:**\n"
                "• Нормализует номер в формат +7XXXXXXXXXX\n"
                "• Для телефона - попробует отправить автоматически",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
    
    async def handle_add_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на кнопки добавления"""
        query = update.callback_query
        await query.answer()
        
        action = query.data
        
        if action == "add_phone":
            context.user_data['waiting_add_contact'] = 'phone'
            # УБРАНА кнопка Start/Menu из основного меню
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
            ])
            
            await query.message.edit_text(
                "📱 Добавление по телефону\n\n"
                "Введите телефон и имя в формате:\n"
                "<PHONE_NUMBER> Иван Иванов\n\n"
                "📋 Поддерживаемые форматы телефонов:\n"
                "<PHONE_NUMBER>\n"
                "+7 <PHONE_NUMBER>\n"
                "<PHONE_NUMBER>\n"
                "<PHONE_NUMBER>\n\n"
                "💡 Что произойдет:\n"
                "• Контакт добавится в базу\n"
                "• Бот попробует отправить приглашение автоматически\n"
                "• Если автоматически не получится, приглашение будет сформировано для ручной отправки",
                reply_markup=keyboard
            )
            
    
    async def handle_add_contact_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода данных для добавления контакта - улучшенная версия"""
        if update.effective_user.id != DEVELOPER_ADMIN_ID:
            return

        # Проверяем, ожидаем ли мы добавление контакта
        if 'waiting_add_contact' not in context.user_data:
            # Если не ожидаем, показываем меню
            await self.show_admin_menu(update, context)
            return

        add_type = context.user_data.get('waiting_add_contact')
        text = update.message.text.strip()

        if not text:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
            ])

            await update.message.reply_text(
                "❌ Введите данные в формате:\n"
                "• Для телефона: <PHONE_NUMBER> Имя Фамилия\n"
                "• Или: +7 <PHONE_NUMBER> Имя Фамилия",
                reply_markup=keyboard
            )
            return

        if add_type == 'phone':
            # Используем регулярное выражение для извлечения телефона
            phone = None
            name = None

            # Ищем телефон в тексте (форматы: <PHONE_NUMBER>, +7 <PHONE_NUMBER>, <PHONE_NUMBER> и т.д.)
            import re

            # Улучшенное регулярное выражение для поиска телефона
            phone_pattern = r'(\+?7|8)[\s\-\(\)]*(\d[\s\-\(\)]*){10}'
            phone_match = re.search(phone_pattern, text)

            if phone_match:
                # Извлекаем найденный телефон
                phone_raw = phone_match.group(0)
                # Нормализуем телефон
                phone = self.normalize_phone(phone_raw)

                # Остаток текста - это имя
                name_part = text.replace(phone_raw, '').strip()
                if name_part:
                    name = name_part
            else:
                # Если не нашли телефон по шаблону, пробуем другой подход
                # Разбиваем на части и ищем телефон среди них
                parts = text.split()

                # Перебираем части, пока не найдем что-то похожее на телефон
                phone_parts = []
                name_parts = []
                found_phone = False

                for part in parts:
                    # Проверяем, похоже ли на телефон (содержит цифры и начинается с + или содержит много цифр)
                    if (part.startswith('+') and any(c.isdigit() for c in part)) or \
                    (part.replace('+', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '').isdigit() and
                        len(re.sub(r'\D', '', part)) >= 10):
                        phone_parts.append(part)
                        found_phone = True
                    else:
                        if found_phone:
                            # Если уже нашли телефон, остальное - имя
                            name_parts.append(part)
                        else:
                            # Если еще не нашли телефон, это может быть часть имени или телефон с пробелами
                            phone_parts.append(part)

                if phone_parts:
                    # Объединяем части телефона
                    phone_raw = ' '.join(phone_parts)
                    phone = self.normalize_phone(phone_raw)
                    name = ' '.join(name_parts) if name_parts else None

            if not phone or not re.match(r'^\+7\d{10}$', phone):
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
                ])

                await update.message.reply_text(
                    f"❌ Неверный формат телефона: {text}\n\n"
                    "📌 Правильные форматы:\n"
                    "<PHONE_NUMBER>\n"
                    "+7 <PHONE_NUMBER>\n"
                    "<PHONE_NUMBER>\n"
                    "<PHONE_NUMBER>\n\n"
                    "📝 Пример с именем:\n"
                    "+7 <PHONE_NUMBER> Иван Петров\n\n"
                    "Введите телефон снова:",
                    reply_markup=keyboard
                )
                return

            result = await self.add_contact_by_phone(phone, name, context)
        else:
            result = "❌ Неизвестный тип контакта"

        # Очищаем данные пользователя
        if 'waiting_add_contact' in context.user_data:
            del context.user_data['waiting_add_contact']

        keyboard_buttons = [
            [InlineKeyboardButton("➕ Добавить еще", callback_data="menu_add")],
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
        ]

        keyboard = InlineKeyboardMarkup(keyboard_buttons)

        # Отправляем результат пользователю
        await update.message.reply_text(result, reply_markup=keyboard, parse_mode='Markdown')

        # Небольшая пауза для уверенности
        await asyncio.sleep(0.5)
    
    async def add_contact_by_phone(self, phone: str, name: Optional[str] = None, context=None) -> str:
        """Добавление контакта по телефону с проверкой активации"""
        retry_count = 3
        retry_delay = 1
        
        for attempt in range(retry_count):
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # ВАЖНО: Проверяем, существует ли уже контакт с таким телефоном
                    c.execute('''SELECT id, telegram_id, name, username, first_activation 
                            FROM contacts WHERE phone = ?''', (phone,))
                    existing = c.fetchone()
                    
                    if existing:
                        contact_id, telegram_id, existing_name, existing_username, first_activation = existing
                        
                        # Обновляем имя если нужно
                        if name and name != existing_name:
                            c.execute('''UPDATE contacts SET name = ? WHERE id = ?''', (name, contact_id))
                        
                        # Проверяем, активирован ли пользователь
                        if telegram_id:
                            # ПОЛЬЗОВАТЕЛЬ АКТИВИРОВАН
                            response = f"✅ *Контакт обновлен:*\n\n"
                            response += f"📱 *Телефон:* `{phone}`\n"
                            if name:
                                response += f"👤 *Имя:* {name}\n"
                            response += f"✅ *Уже активирован!*\n"
                            response += f"Telegram ID: {telegram_id}\n"
                            response += f"Документы можно отправлять напрямую"
                            
                            # ВАЖНО: Устанавливаем first_activation, если его нет
                            if not first_activation:
                                c.execute('''UPDATE contacts 
                                        SET first_activation = CURRENT_TIMESTAMP 
                                        WHERE id = ? AND first_activation IS NULL''', 
                                        (contact_id,))
                                response += f"\n🕐 Время активации: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                        else:
                            # ПОЛЬЗОВАТЕЛЬ НЕ АКТИВИРОВАН
                            response = f"✅ *Контакт обновлен:*\n\n"
                            response += f"📱 *Телефон:* `{phone}`\n"
                            if name:
                                response += f"👤 *Имя:* {name}\n"
                            response += f"📨 *Пользователь не активирован*\n"
                            response += f"Будет доступен в списке контактов для отправки документов"
                    else:
                        # НОВЫЙ КОНТАКТ - ИЩЕМ АКТИВИРОВАННОГО ПОЛЬЗОВАТЕЛЯ ПО ТЕЛЕФОНУ
                        
                        # Генерируем все возможные вариации телефона для поиска
                        phone_normalized = self.normalize_phone(phone)
                        phone_clean = phone_normalized.lstrip('+7') if phone_normalized.startswith('+7') else phone_normalized
                        
                        # Все возможные форматы
                        phone_variations = [
                            phone_normalized,              # <PHONE_NUMBER>
                            phone_clean,                   # <PHONE_NUMBER>
                            f"8{phone_clean}",            # <PHONE_NUMBER>
                            f"+7{phone_clean}",           # <PHONE_NUMBER> (другой формат)
                            f"7{phone_clean}",            # <PHONE_NUMBER>
                            f"8{phone_clean[1:]}" if len(phone_clean) > 1 else None  # 8991234567 (без первой 9)
                        ]
                        
                        # Удаляем None и дубликаты
                        phone_variations = [p for p in phone_variations if p is not None]
                        phone_variations = list(set(phone_variations))
                        
                        # Ищем активированного пользователя
                        telegram_id_found = None
                        activation_found = None
                        for phone_var in phone_variations:
                            c.execute('''SELECT telegram_id, first_activation FROM contacts 
                                    WHERE (phone = ? OR phone LIKE ?) 
                                    AND telegram_id IS NOT NULL''',
                                    (phone_var, f"%{phone_var}%"))
                            result = c.fetchone()
                            if result and result[0]:
                                telegram_id_found = result[0]
                                activation_found = result[1]
                                logger.info(f"🔍 Найден активированный пользователь для телефона {phone}: {telegram_id_found}")
                                break
                        
                        if telegram_id_found:
                            # НАШЛИ АКТИВИРОВАННОГО ПОЛЬЗОВАТЕЛЯ!
                            # Обновляем существующую запись
                            c.execute('''UPDATE contacts 
                                    SET phone = ?, 
                                        name = COALESCE(?, name),
                                        last_activity = CURRENT_TIMESTAMP,
                                        first_activation = COALESCE(first_activation, CURRENT_TIMESTAMP)
                                    WHERE telegram_id = ?''',
                                    (phone, name, telegram_id_found))
                            
                            response = f"✅ *Контакт добавлен/обновлен:*\n\n"
                            response += f"📱 *Телефон:* `{phone}`\n"
                            if name:
                                response += f"👤 *Имя:* {name}\n"
                            response += f"✅ *Связан с активированным пользователем!*\n"
                            response += f"Telegram ID: {telegram_id_found}\n"
                            response += f"Документы можно отправлять напрямую\n"
                            
                            # Если активация не была записана, добавляем информацию
                            if not activation_found:
                                response += f"🕐 Время активации: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                        else:
                            # Создаем новую запись - пользователь не активирован
                            c.execute('''INSERT INTO contacts (phone, name) VALUES (?, ?)''', 
                                    (phone, name))
                            contact_id = c.lastrowid
                            
                            response = f"✅ *Контакт добавлен по телефону:*\n\n"
                            response += f"📱 *Телефон:* `{phone}`\n"
                            if name:
                                response += f"👤 *Имя:* {name}\n"
                            response += f"📨 *Пользователь не активирован*\n"
                            response += f"Будет доступен в списке контактов для отправки документов"
                    
                    conn.commit()
                
                return response
                    
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retry_count - 1:
                    logger.warning(f"База заблокирована при добавлении {phone}, попытка {attempt + 1}")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    return f"❌ *Ошибка базы данных:* {str(e)[:100]}\n\n📱 *Телефон:* `{phone}`"
            except Exception as e:
                return f"❌ *Неизвестная ошибка:* {str(e)}\n\n📱 *Телефон:* `{phone}`"
    
    
    def normalize_phone(self, phone: str) -> str:
        """Нормализация телефона в единый формат +7XXXXXXXXXX"""
        # Если номер пустой, возвращаем как есть
        if not phone:
            return phone
        
        # Удаляем все нецифровые символы: пробелы, скобки, тире, плюс
        digits = re.sub(r'\D', '', str(phone))
        
        # Российские номера:
        # 10 цифр - добавляем 7 в начало
        if len(digits) == 10:
            digits = '7' + digits
        # 11 цифр - если начинается с 8, заменяем на 7
        elif len(digits) == 11:
            if digits.startswith('8'):
                digits = '7' + digits[1:]
            elif digits.startswith('7'):
                # уже правильный формат, оставляем как есть
                pass
        # 12 цифр - если начинается с 78 или 79, берем последние 11
        elif len(digits) == 12:
            if digits.startswith('78') or digits.startswith('79'):
                digits = digits[1:]  # убираем первую цифру
        
        # Проверяем, что получился корректный номер (11 цифр, начинается с 7)
        if digits and digits.startswith('7') and len(digits) == 11:
            return f"+{digits}"
        
        # Если не удалось нормализовать, возвращаем как есть с +
        return f"+{digits}" if digits else phone

    def parse_phone_from_text(self, text: str) -> List[str]:
        """Парсит телефоны из текста, поддерживая различные форматы"""
        phones = []
        
        # Простое регулярное выражение для поиска电话号码
        # Ищем последовательности цифр длиной 10-12
        digit_sequences = re.findall(r'\d{10,12}', text)
        
        for seq in digit_sequences:
            phone_normalized = self.normalize_phone(seq)
            if re.match(r'^\+7\d{10}$', phone_normalized):
                phones.append(phone_normalized)
        
        return phones

    def parse_phone_from_text(self, text: str) -> List[str]:
        """Парсит телефоны из текста, поддерживая различные форматы"""
        phones = []
        
        # Более гибкое регулярное выражение для поиска российских номеров
        # Ищет: +7, 8, 7 в начале, затем цифры с возможными разделителями
        pattern = r'(?:(?:\+7|8|7)[\s\-\(\)]*)(?:\d[\s\-\(\)]*){10,11}'
        
        # Ищем все совпадения
        matches = re.finditer(pattern, text)
        
        for match in matches:
            phone_raw = match.group(0)
            # Нормализуем найденный номер
            phone_normalized = self.normalize_phone(phone_raw)
            # Проверяем, что получился валидный номер
            if re.match(r'^\+7\d{10}$', phone_normalized):
                phones.append(phone_normalized)
        
        # Дополнительный метод: ищем последовательности цифр, которые могут быть телефонами
        if not phones:
            # Находим все последовательности цифр длиной 10-12
            digit_sequences = re.findall(r'\d{10,12}', text)
            for seq in digit_sequences:
                phone_normalized = self.normalize_phone(seq)
                if re.match(r'^\+7\d{10}$', phone_normalized):
                    phones.append(phone_normalized)
        
        return phones
    
    async def contacts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != DEVELOPER_ADMIN_ID:
            return
        
        filter_type = context.args[0] if context.args else None
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                if filter_type == 'phone':
                    c.execute('''SELECT phone, name, telegram_id 
                               FROM contacts WHERE phone IS NOT NULL 
                               ORDER BY name, phone LIMIT 50''')
                    title = "Контакты с телефонами"
                elif filter_type == 'active':
                    c.execute('''SELECT phone, name, telegram_id 
                               FROM contacts WHERE telegram_id IS NOT NULL 
                               ORDER BY last_activity DESC LIMIT 50''')
                    title = "Активные пользователи"
                else:
                    c.execute('''SELECT phone, name, telegram_id 
                               FROM contacts ORDER BY last_activity DESC LIMIT 50''')
                    title = "Все контакты"
                
                contacts = c.fetchall()
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Ошибка получения контактов: {e}")
            contacts = []
        
        if not contacts:
            # УБРАНА кнопка Start/Menu из основного меню
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
            ])
            
            await update.message.reply_text("📭 В базе нет контактов", reply_markup=keyboard)
            return
        
        response = f"📋 {title} ({len(contacts)}):\n\n"
        
        for i, (phone, username, name, telegram_id) in enumerate(contacts, 1):
            response += f"{i}. "
            
            if name:
                response += f"{name}\n"
            
            if phone:
                response += f"   📱 {phone}\n"
            
            if telegram_id:
                response += f"   ✅ ID: {telegram_id} (активирован)\n"
            else:
                response += f"   ⏳ Не активирован\n"
            
            response += "\n"
        
        response += "\n📌 Фильтры:\n"
        response += "/contacts phone - только с телефонами\n"
        response += "/contacts active - только активные\n"
        
        # УБРАНА кнопка Start/Menu из основного меню
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
        ])
        
        await update.message.reply_text(response, reply_markup=keyboard)
    
    async def add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != DEVELOPER_ADMIN_ID:
            return
        
        if not context.args:
            # УБРАНА кнопка Start/Menu из основного меню
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
            ])
            
            await update.message.reply_text(
                "➕ Добавление контакта:\n\n"
                "По телефону (любой формат):\n"
                "/add <PHONE_NUMBER> Иван Иванов\n"
                "/add +7 <PHONE_NUMBER> Иван Иванов\n"
                "/add <PHONE_NUMBER> Иван Иванов\n"
                "/add <PHONE_NUMBER> Иван Иванов\n\n"
                "По username:\n"
                "/add @ivanov Иван Иванов\n\n"
                "Или используйте меню '➕ Добавить' для пошагового добавления.",
                reply_markup=keyboard
            )
            return
        
        args = context.args
        identifier = args[0]
        name = " ".join(args[1:]) if len(args) > 1 else None
        
        if identifier.startswith('+') or identifier[0].isdigit():
            phone_cleaned = re.sub(r'\s', '', identifier)
            phone = self.normalize_phone(phone_cleaned)
            result = await self.add_contact_by_phone(phone, name, context)
        else:
            result = "❌ Неверный формат. Используйте:\n• @username\n• <PHONE_NUMBER>\n• +7 <PHONE_NUMBER>"
        
        # УБРАНА кнопка Start/Menu из основного меню
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
        ])
        
        await update.message.reply_text(result, reply_markup=keyboard, parse_mode='Markdown')
    
    def parse_phone_from_text(self, text: str) -> List[str]:
        """Парсит телефоны из текста, поддерживая различные форматы"""
        phones = []
        
        # Регулярное выражение для поиска российских номеров
        pattern = r'''
            (?:\+7|8)[\s\-\(\)]*    # начало номера +7 или 8
            \d{3}[\s\-\(\)]*        # первые 3 цифры
            \d{3}[\s\-\(\)]*        # вторые 3 цифры
            \d{2}[\s\-\(\)]*        # первые 2 цифры
            \d{2}                   # последние 2 цифры
        '''
        
        # Ищем все совпадения
        matches = re.finditer(pattern, text, re.VERBOSE)
        
        for match in matches:
            phone_raw = match.group(0)
            # Нормализуем найденный номер
            phone_normalized = self.normalize_phone(phone_raw)
            if re.match(r'^\+7\d{10}$', phone_normalized):
                phones.append(phone_normalized)
        
        return phones
    
    
    def parse_recipients(self, text: str) -> List[Dict]:
        """Парсит получателей из текста, поддерживая телефоны с пробелами"""
        recipients = []
        
        # Сначала ищем все телефоны
        phones = self.parse_phone_from_text(text)
        
        # Добавляем найденные телефоны
        for phone in phones:
            recipients.append({
                'type': 'phone',
                'value': phone,
                'original': phone
            })
        
        # Теперь ищем username (начинающиеся с @)
        usernames = re.findall(r'@(\w+)', text)
        for username in usernames:
            recipients.append({
                'type': 'username',
                'value': f"@{username}",
                'original': f"@{username}"
            })
        
        # Удаляем дубликаты
        unique_recipients = []
        seen = set()
        for recipient in recipients:
            key = (recipient['type'], recipient['value'])
            if key not in seen:
                seen.add(key)
                unique_recipients.append(recipient)
        
        return unique_recipients
    
    async def upgrade_database_schema(self):
        """Обновление схемы базы данных для поддержки разных типов файлов"""
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Проверяем наличие новых колонок
                c.execute("PRAGMA table_info(document_files)")
                columns = [col[1] for col in c.fetchall()]
                
                if 'file_type' not in columns:
                    c.execute('ALTER TABLE document_files ADD COLUMN file_type TEXT DEFAULT "document"')
                    logger.info("✅ Добавлена колонка file_type")
                
                if 'mime_type' not in columns:
                    c.execute('ALTER TABLE document_files ADD COLUMN mime_type TEXT')
                    logger.info("✅ Добавлена колонка mime_type")
                
                if 'file_size' not in columns:
                    c.execute('ALTER TABLE document_files ADD COLUMN file_size INTEGER')
                    logger.info("✅ Добавлена колонка file_size")
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления схемы: {e}")
    
    async def send_to_recipient_enhanced(self, bot, recipient: Dict, doc_id: str, files: List[tuple], bot_username: str, file_types: List[str] = None) -> Dict:
        """Улучшенная отправка с поддержкой всех типов файлов"""
        
        retry_count = 3
        retry_delay = 1

        for attempt in range(retry_count):
            try:
                identifier_type = recipient['type']
                identifier_value = recipient['value']
                original = recipient['original']

                if identifier_type != 'phone':
                    return {
                        'success': False,
                        'type': 'invalid_type',
                        'recipient': original,
                        'message': "❌ Поддерживается только отправка по телефону"
                    }

                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # Находим или создаем контакт
                    c.execute('SELECT id, name, telegram_id FROM contacts WHERE phone = ?', (identifier_value,))
                    contact = c.fetchone()
                    
                    deep_link = f"https://t.me/{bot_username}?start=doc_{doc_id}"
                    
                    if contact:
                        contact_id, name, telegram_id = contact
                    else:
                        c.execute('INSERT INTO contacts (phone) VALUES (?)', (identifier_value,))
                        contact_id = c.lastrowid
                        name = None
                        telegram_id = None
                    
                    # Обновляем recipients
                    c.execute('''
                        UPDATE recipients 
                        SET identifier_type = ?, identifier_value = ?, sent_via = ?
                        WHERE doc_id = ? AND contact_id = ?
                    ''', (identifier_type, identifier_value, 
                        'direct' if telegram_id else 'phone_auto', doc_id, contact_id))
                    
                    if c.rowcount == 0:
                        c.execute('''
                            INSERT INTO recipients 
                            (doc_id, contact_id, identifier_type, identifier_value, sent_via, status)
                            VALUES (?, ?, ?, ?, ?, 'pending')
                        ''', (doc_id, contact_id, identifier_type, identifier_value,
                            'direct' if telegram_id else 'phone_auto'))
                    
                    conn.commit()
                    
                    # Отправка файлов
                    if telegram_id:
                        # Активированный пользователь
                        lang = self.get_user_language(telegram_id)
                        
                        keyboard = InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton("✅ Согласен", callback_data=f"approve_{doc_id}"),
                                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{doc_id}")
                            ],
                            [
                                InlineKeyboardButton("💬 Комментарий", callback_data=f"comment_{doc_id}"),
                                InlineKeyboardButton("👥 Кто еще получил", callback_data=f"view_recipients_{doc_id}")
                            ]
                        ])
                        
                        first_file_id, first_file_name = files[0]
                        
                        try:
                            # Отправляем первый файл с кнопками
                            await bot.send_document(
                                chat_id=telegram_id,
                                document=first_file_id,
                                caption=(
                                    f"📄 *Новый документ для согласования*\n\n"
                                    f"**{first_file_name}**\n"
                                    f"{f'📚 Всего файлов: {len(files)}' if len(files) > 1 else ''}\n\n"
                                    f"👇 Используйте кнопки ниже"
                                ),
                                reply_markup=keyboard,
                                parse_mode='Markdown'
                            )
                            
                            # Отправляем остальные файлы
                            for i in range(1, len(files)):
                                file_id, file_name = files[i]
                                await bot.send_document(
                                    chat_id=telegram_id,
                                    document=file_id,
                                    caption=f"📄 *Документ {i+1}:* {file_name}",
                                    parse_mode='Markdown'
                                )
                            
                            return {
                                'success': True,
                                'type': 'direct',
                                'recipient': original,
                                'name': name,
                                'telegram_id': telegram_id,
                                'message': "✅ Документ отправлен напрямую"
                            }
                            
                        except Exception as e:
                            logger.error(f"❌ Ошибка отправки: {e}")
                            return {
                                'success': False,
                                'type': 'send_error',
                                'recipient': original,
                                'name': name,
                                'message': f"❌ Ошибка: {str(e)[:60]}"
                            }
                    
                    else:
                        # Неактивированный пользователь - отправляем приглашение
                        if self.admin_sender:
                            first_file_name = files[0][1] if files else "Документ"
                            
                            send_result = await self.admin_sender.send_invitation_to_phone(
                                phone=identifier_value,
                                doc_id=doc_id,
                                file_name=first_file_name,
                                file_count=len(files)
                            )
                            
                            if send_result.get('success'):
                                return {
                                    'success': True,
                                    'type': 'phone_auto',
                                    'recipient': original,
                                    'name': name,
                                    'deep_link': deep_link,
                                    'message': "📲 Приглашение автоматически отправлено"
                                }
                        
                        return {
                            'success': False,
                            'type': 'invite_failed',
                            'recipient': original,
                            'name': name,
                            'deep_link': deep_link,
                            'message': "❌ Не удалось отправить приглашение"
                        }

            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retry_count - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return {
                    'success': False,
                    'type': 'database_error',
                    'recipient': recipient['original'],
                    'name': None,
                    'message': "❌ Ошибка базы данных"
                }
            except Exception as e:
                logger.error(f"❌ Ошибка отправки: {e}")
                return {
                    'success': False,
                    'type': 'error',
                    'recipient': recipient['original'],
                    'name': None,
                    'message': f"❌ Ошибка: {str(e)[:60]}"
                }
    

    async def handle_media_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка группы медиафайлов"""
        if update.effective_user.id != DEVELOPER_ADMIN_ID:
            return
        
        # Проверяем, есть ли media_group_id
        if not update.message.media_group_id:
            return
        
        media_group_id = update.message.media_group_id
        
        # Инициализируем сбор файлов
        if 'media_group' not in context.user_data:
            context.user_data['media_group'] = {
                'id': media_group_id,
                'files': [],
                'last_update': datetime.now()
            }
        
        # Определяем тип файла и добавляем в коллекцию
        file_info = None
        
        if update.message.document:
            doc = update.message.document
            file_info = {
                'file_id': doc.file_id,
                'file_name': doc.file_name or f"doc_{len(context.user_data['media_group']['files'])+1}",
                'type': 'document',
                'mime_type': doc.mime_type
            }
        elif update.message.photo:
            photo = update.message.photo[-1]
            file_info = {
                'file_id': photo.file_id,
                'file_name': f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(context.user_data['media_group']['files'])+1}.jpg",
                'type': 'photo'
            }
        elif update.message.video:
            video = update.message.video
            file_info = {
                'file_id': video.file_id,
                'file_name': video.file_name or f"video_{len(context.user_data['media_group']['files'])+1}.mp4",
                'type': 'video',
                'mime_type': video.mime_type
            }
        
        if file_info:
            context.user_data['media_group']['files'].append(file_info)
            context.user_data['media_group']['last_update'] = datetime.now()
            
            # Ждем 1.5 секунды после последнего файла
            await asyncio.sleep(1.5)
            
            # Если прошло достаточно времени, обрабатываем группу
            if (datetime.now() - context.user_data['media_group']['last_update']).total_seconds() >= 1.5:
                await self.process_media_group(update, context)


    async def handle_document_enhanced(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Улучшенная обработка документов с поддержкой всех форматов:"""
        if update.effective_user.id != DEVELOPER_ADMIN_ID:
            return
        
        # Очищаем контекст
        self._clear_document_context(context)
        
        # Определяем тип сообщения
        file_info = None
        file_type = None
        
        if update.message.document:
            # Обычный документ
            doc = update.message.document
            file_info = {
                'file_id': doc.file_id,
                'file_name': doc.file_name or "Документ",
                'file_size': doc.file_size,
                'mime_type': doc.mime_type,
                'type': 'document'
            }
            file_type = 'document'
            
        elif update.message.photo:
            # Фотография (получаем самое большое качество)
            photo = update.message.photo[-1]
            file_info = {
                'file_id': photo.file_id,
                'file_name': f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
                'file_size': photo.file_size,
                'type': 'photo'
            }
            file_type = 'photo'
            
        elif update.message.audio:
            # Аудио файл
            audio = update.message.audio
            file_info = {
                'file_id': audio.file_id,
                'file_name': audio.file_name or f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                'file_size': audio.file_size,
                'mime_type': audio.mime_type,
                'performer': audio.performer,
                'title': audio.title,
                'type': 'audio'
            }
            file_type = 'audio'
            
        elif update.message.voice:
            # Голосовое сообщение
            voice = update.message.voice
            file_info = {
                'file_id': voice.file_id,
                'file_name': f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ogg",
                'file_size': voice.file_size,
                'duration': voice.duration,
                'type': 'voice'
            }
            file_type = 'voice'
            
        elif update.message.video:
            # Видео
            video = update.message.video
            file_info = {
                'file_id': video.file_id,
                'file_name': video.file_name or f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4",
                'file_size': video.file_size,
                'mime_type': video.mime_type,
                'duration': video.duration,
                'type': 'video'
            }
            file_type = 'video'
            
        elif update.message.video_note:
            # Видео-кружок
            video_note = update.message.video_note
            file_info = {
                'file_id': video_note.file_id,
                'file_name': f"videonote_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4",
                'file_size': video_note.file_size,
                'duration': video_note.duration,
                'type': 'video_note'
            }
            file_type = 'video_note'
            
        elif update.message.animation:
            # GIF/анимация
            animation = update.message.animation
            file_info = {
                'file_id': animation.file_id,
                'file_name': animation.file_name or f"animation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.gif",
                'file_size': animation.file_size,
                'mime_type': animation.mime_type,
                'type': 'animation'
            }
            file_type = 'animation'
        
        if not file_info:
            await update.message.reply_text(
                "❌ Неподдерживаемый тип файла\n\n"
                "📋 Поддерживаются:\n"
                "• Фотографии (JPEG, PNG, GIF)\n"
                "• Документы (PDF, DOC, DOCX, XLS, XLSX, PPT, TXT)\n"
                "• Архивы (ZIP, RAR, 7z)\n"
                "• Видео и аудио файлы\n"
                "• Голосовые и видеосообщения"
            )
            return
        
        # Создаем ID документа
        doc_id = str(uuid.uuid4())[:8]
        
        # Сохраняем информацию
        context.user_data['pending_doc'] = {
            'id': doc_id,
            'file_info': file_info,
            'message_id': update.message.message_id,
            'chat_id': update.message.chat_id,
            'file_type': file_type
        }
        
        context.user_data['original_doc_message'] = update.message
        
        # Сохраняем в базу
        retry_count = 3
        retry_delay = 1
        
        for attempt in range(retry_count):
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # Основная запись документа
                    c.execute('''INSERT INTO documents (id, admin_id) 
                                VALUES (?, ?)''', (doc_id, DEVELOPER_ADMIN_ID))
                    
                    # Запись файла в отдельную таблицу - БЕЗ file_type (проблемная колонка)
                    c.execute('''INSERT INTO document_files 
                                (doc_id, file_id, file_name, file_order, mime_type, file_size) 
                                VALUES (?, ?, ?, ?, ?, ?)''',
                            (doc_id, 
                            file_info['file_id'], 
                            file_info['file_name'], 
                            1,
                            file_info.get('mime_type'),
                            file_info.get('file_size')))
                    
                    conn.commit()
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retry_count - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error(f"❌ Ошибка сохранения файла: {e}")
                    await update.message.reply_text("❌ Ошибка базы данных при сохранении файла")
                    return
        
        # Экранируем имя файла для Markdown
        safe_file_name = self.escape_markdown(file_info['file_name'])
        
        # Запрашиваем тему
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить (без темы)", callback_data=f"skip_theme_{doc_id}")]
        ])
        
        # Определяем эмодзи в зависимости от типа файла
        type_emoji = {
            'photo': '🖼️',
            'document': '📄',
            'audio': '🎵',
            'voice': '🎤',
            'video': '🎬',
            'video_note': '📹',
            'animation': '🎨'
        }.get(file_type, '📄')
        
        await update.message.reply_text(
            f"{type_emoji} *Файл получен:* {safe_file_name}\n\n"
            f"📝 *Укажите тему сообщения*\n\n"
            f"Напишите тему, которая будет отображаться в сообщении.\n\n"
            f"Или нажмите кнопку ниже, чтобы пропустить",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        context.user_data['waiting_message_theme'] = {
            'doc_id': doc_id,
            'file_names': [file_info['file_name']],
            'file_type': file_type
        }
    
    async def handle_contact_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != DEVELOPER_ADMIN_ID:
            return
        
        contact: Contact = update.message.contact
        phone = self.normalize_phone(contact.phone_number)
        name = f"{contact.first_name} {contact.last_name or ''}".strip()
        
        retry_count = 3
        retry_delay = 1
        
        for attempt in range(retry_count):
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # Проверяем, активирован ли уже контакт
                    c.execute('''SELECT telegram_id FROM contacts WHERE phone = ?''', (phone,))
                    existing = c.fetchone()
                    
                    if contact.user_id:
                        # Контакт из Telegram - сразу активируем
                        c.execute('''INSERT OR REPLACE INTO contacts 
                                   (phone, name, telegram_id) 
                                   VALUES (?, ?, ?)''', 
                                 (phone, name, contact.user_id))
                        
                        response = f"✅ *Контакт сохранен:*\n\n"
                        response += f"📱 *Телефон:* `{phone}`\n"
                        response += f"👤 *Имя:* {name}\n"
                        response += f"🆔 *Telegram ID:* {contact.user_id}\n"
                        response += f"✅ *Активирован!*\n\n"
                        response += f"Теперь можно отправлять документы напрямую"
                        
                    else:
                        # Контакт без Telegram ID
                        c.execute('''INSERT OR REPLACE INTO contacts 
                                   (phone, name) VALUES (?, ?)''', 
                                 (phone, name))
                        
                        contact_id = c.lastrowid
                        
                        # Пытаемся отправить автоматически
                        if self.admin_sender:
                            temp_doc_id = str(uuid.uuid4())[:8]
                            temp_file_name = "Приглашение в систему DocFlow"
                            
                            result = await self.admin_sender.send_invitation_to_phone(
                                phone=phone,
                                doc_id=temp_doc_id,
                                file_name=temp_file_name,
                                file_count=1
                            )
                            
                            # Проверяем результат
                            if result.get('success') == True:
                                response = f"✅ *Контакт сохранен:*\n\n"
                                response += f"📱 *Телефон:* `{phone}`\n"
                                response += f"👤 *Имя:* {name}\n\n"
                                response += f"🤖 *Приглашение отправлено автоматически!*\n\n"
                                response += f"💡 *Информация:*\n"
                                response += f"• {result.get('message', 'Сообщение отправлено')}\n"
                                if result.get('note'):
                                    response += f"• {result['note']}\n"
                            else:
                                # Автоматическая отправка не удалась
                                bot_username = self.bot_username or (await context.bot.get_me()).username
                                activation_link = f"https://t.me/{bot_username}?start=phone_{phone}"
                                
                                response = f"✅ *Контакт сохранен:*\n\n"
                                response += f"📱 *Телефон:* `{phone}`\n"
                                response += f"👤 *Имя:* {name}\n\n"
                                response += f"📨 *Пользователь не активирован*\n\n"
                                response += f"❌ *Ошибка автоматической отправки:* {result.get('message', 'Неизвестная ошибка')}\n\n"
                                response += f"💡 *Рекомендации:*\n"
                                response += f"1. Отправьте пользователю ссылку:\n"
                                response += f"   `{activation_link}`\n"
                                response += f"2. Или отправьте первый документ\n"
                    
                    conn.commit()
                
                # УБРАНА кнопка Start/Menu из основного меню
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
                ])
                
                await update.message.reply_text(response, reply_markup=keyboard, parse_mode='Markdown')
                return
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retry_count - 1:
                    logger.warning(f"База заблокирована при сохранении контакта, попытка {attempt + 1}")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    await update.message.reply_text(f"❌ Ошибка базы данных: {str(e)}")
                    return
            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка: {str(e)}")
                return
    
    async def show_queue_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает статус очереди отправки"""
        query = update.callback_query
        if query:
            await query.answer()
        
        if not self.admin_sender:
            response = "❌ Автоматическая отправка не настроена\n\n"
            response += "Для настройки:\n"
            response += "1. Перейдите в личные сообщения с ботом\n"
            response += "2. Отправьте команду /start\n"
            response += "3. Система запросит номер телефона админа\n\n"
            response += "⚠️ Внимание: Настройка возможна только в личных сообщениях!"
        else:
            stats = await self.admin_sender.get_stats()
            
            response = "📊 Статус автоматической отправки\n\n"
            response += f"✅ Настроено: Да\n"
            response += f"📱 Отправка от: {self.admin_sender.admin_phone}\n"
            response += f"🤖 Бот: @{self.bot_username}\n\n"
            response += f"📋 Очередь:\n"
            response += f"• Всего: {stats['total']}\n"
            response += f"• ⏳ Ожидают: {stats['pending']}\n"
            response += f"• ✅ Отправлено: {stats['sent']}\n"
            response += f"• ❌ Ошибок: {stats['failed']}\n"
        
        # УБРАНА кнопка Start/Menu из основного меню
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
        ])
        
        if query:
            await query.message.edit_text(response, reply_markup=keyboard)
        else:
            await update.message.reply_text(response, reply_markup=keyboard)
    
    def _clear_document_context(self, context):
        """Очистка контекста документов"""
        # Список всех ключей для удаления
        keys_to_remove = [
            'pending_doc', 'current_doc_id', 'contacts_for_selection',
            'selected_contacts', 'media_group', 'document_group',
            'documents_collected', 'waiting_recipients', 'waiting_add_contact',
            'cancelling', 'recipients_message_id', 'original_doc_message'
        ]
        
        # Удаляем каждый ключ
        for key in keys_to_remove:
            if key in context.user_data:
                del context.user_data[key]
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка одиночного документа"""
        if update.effective_user.id != DEVELOPER_ADMIN_ID:
            return
        
        self._clear_document_context(context)
        
        doc = update.message.document
        doc_id = str(uuid.uuid4())[:8]
        
        # СОХРАНЯЕМ информацию о сообщении для удаления
        context.user_data['pending_doc'] = {
            'id': doc_id,
            'file_id': doc.file_id,
            'file_name': doc.file_name or "Документ",
            'message_id': update.message.message_id,
            'chat_id': update.message.chat_id
        }
        
        # Также сохраняем ссылку на оригинальное сообщение
        context.user_data['original_doc_message'] = update.message
        
        retry_count = 3
        retry_delay = 1
        
        for attempt in range(retry_count):
            try:
                # Сохраняем в базу
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # Основная запись документа
                    c.execute('''INSERT INTO documents (id, admin_id) 
                                VALUES (?, ?)''', (doc_id, DEVELOPER_ADMIN_ID))
                    
                    # Запись файла в отдельную таблицу
                    c.execute('''INSERT INTO document_files 
                                (doc_id, file_id, file_name, file_order) 
                                VALUES (?, ?, ?, ?)''',
                            (doc_id, doc.file_id, doc.file_name or "Документ", 1))
                    
                    conn.commit()
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retry_count - 1:
                    logger.warning(f"База заблокирована при сохранении документа, попытка {attempt + 1}")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error(f"❌ Ошибка сохранения документа: {e}")
                    await update.message.reply_text("❌ Ошибка базы данных при сохранении документа")
                    return
        
        # ===== НОВЫЙ КОД: ЗАПРАШИВАЕМ ТЕМУ СООБЩЕНИЯ =====
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить (без темы)", callback_data=f"skip_theme_{doc_id}")]
        ])
        
        await update.message.reply_text(
            "📝 *Укажите тему сообщения*\n\n"
            "Напишите тему, которая будет отображаться в сообщении с документом.\n\n"
            "Примеры:\n"
            "• *Срочное согласование договора*\n"
            "• *Важно: изменение в документации*\n"
            "• *Годовой отчет за 2024*\n\n"
            "Или нажмите кнопку ниже, чтобы пропустить",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        # Устанавливаем флаг ожидания темы
        context.user_data['waiting_message_theme'] = {
            'doc_id': doc_id,
            'file_names': [doc.file_name or "Документ"]
        }

    async def handle_skip_theme(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка пропуска темы сообщения"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        if data.startswith("skip_theme_"):
            doc_id = data.replace("skip_theme_", "")
            
            # Очищаем ожидание темы
            if 'waiting_message_theme' in context.user_data:
                theme_data = context.user_data['waiting_message_theme']
                file_names = theme_data['file_names']
                del context.user_data['waiting_message_theme']
            else:
                # Если данных нет, пробуем получить из pending_doc
                if 'pending_doc' in context.user_data:
                    file_names = [context.user_data['pending_doc']['file_name']]
                else:
                    file_names = ["Документ"]
            
            # Устанавливаем флаг ожидания получателей
            context.user_data['waiting_recipients'] = True
            
            # Показываем меню для указания получателей
            await self._show_recipients_menu_by_query(query, context, doc_id, file_names)

    async def handle_message_theme(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода темы сообщения"""
        if update.effective_user.id != DEVELOPER_ADMIN_ID:
            return
        
        # Проверяем, ожидаем ли мы тему
        if 'waiting_message_theme' not in context.user_data:
            return
        
        theme_data = context.user_data['waiting_message_theme']
        doc_id = theme_data['doc_id']
        file_names = theme_data['file_names']
        
        theme_text = update.message.text.strip()
        
        # Сохраняем тему в базу данных
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Добавляем поле theme в таблицу documents если его нет
                c.execute("PRAGMA table_info(documents)")
                columns = [col[1] for col in c.fetchall()]
                
                if 'theme' not in columns:
                    try:
                        c.execute('ALTER TABLE documents ADD COLUMN theme TEXT')
                        logger.info("✅ Добавлено поле theme в таблицу documents")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось добавить поле theme: {e}")
                
                # Сохраняем тему
                c.execute('UPDATE documents SET theme = ? WHERE id = ?', (theme_text, doc_id))
                conn.commit()
                
            logger.info(f"✅ Тема сохранена для документа {doc_id}: {theme_text[:50]}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения темы: {e}")
        
        # Очищаем контекст
        del context.user_data['waiting_message_theme']
        
        # Устанавливаем флаг ожидания получателей
        context.user_data['waiting_recipients'] = True
        
        # Показываем меню для указания получателей
        await self._show_recipients_menu(update, context, doc_id, file_names)
    
    async def handle_multiple_documents(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нескольких документов"""
        if update.effective_user.id != DEVELOPER_ADMIN_ID:
            return
        
        # Проверяем, есть ли media_group_id
        if not update.message.media_group_id:
            # Если нет media_group, обрабатываем как одиночный документ
            return await self.handle_document(update, context)
        
        media_group_id = update.message.media_group_id
        
        # Инициализируем сбор документов
        if 'documents_collected' not in context.user_data:
            context.user_data['documents_collected'] = {
                'media_group_id': media_group_id,
                'documents': [],
                'last_message_time': datetime.now()
            }
        
        # Добавляем документ в коллекцию
        doc = update.message.document
        context.user_data['documents_collected']['documents'].append({
            'file_id': doc.file_id,
            'file_name': doc.file_name or f"Документ {len(context.user_data['documents_collected']['documents']) + 1}",
            'message_id': update.message.message_id,
            'chat_id': update.message.chat_id
        })
        
        # Сохраняем оригинальное сообщение
        context.user_data['original_doc_message'] = update.message
        
        # Обновляем время последнего сообщения
        context.user_data['documents_collected']['last_message_time'] = datetime.now()
        
        # Ждем 1 секунду для сбора всех документов группы
        await asyncio.sleep(1)
        
        # Проверяем, прошло ли достаточно времени для завершения сбора
        time_since_last = (datetime.now() - context.user_data['documents_collected']['last_message_time']).total_seconds()
        
        if time_since_last >= 1.5:  # Ждем 1.5 секунды после последнего документа
            documents = context.user_data['documents_collected']['documents']
            
            if documents:
                # Создаем общий doc_id для группы документов
                group_id = str(uuid.uuid4())[:8]
                
                retry_count = 3
                retry_delay = 1
                
                for attempt in range(retry_count):
                    try:
                        # Сохраняем документы в базу
                        with DatabaseManager.db_connection(self.db_path) as conn:
                            c = conn.cursor()
                            
                            # Основная запись документа
                            c.execute('''INSERT INTO documents (id, admin_id) 
                                        VALUES (?, ?)''', (group_id, DEVELOPER_ADMIN_ID))
                            
                            # Сохраняем каждый файл в отдельную таблицу
                            for i, doc_info in enumerate(documents, 1):
                                c.execute('''INSERT INTO document_files 
                                            (doc_id, file_id, file_name, file_order) 
                                            VALUES (?, ?, ?, ?)''',
                                        (group_id, doc_info['file_id'], doc_info['file_name'], i))
                            
                            conn.commit()
                        break
                    except sqlite3.OperationalError as e:
                        if "database is locked" in str(e) and attempt < retry_count - 1:
                            logger.warning(f"База заблокирована при сохранении группы документов, попытка {attempt + 1}")
                            time.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        else:
                            logger.error(f"❌ Ошибка сохранения группы документов: {e}")
                            await update.message.reply_text("❌ Ошибка базы данных при сохранении документов")
                            return
                
                # Формируем список имен файлов
                file_names = [doc['file_name'] for doc in documents]
                
                # Очищаем контекст от временных данных сбора
                if 'documents_collected' in context.user_data:
                    del context.user_data['documents_collected']
                
                # ===== ЗАПРАШИВАЕМ ТЕМУ СООБЩЕНИЯ =====
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⏭ Пропустить (без темы)", callback_data=f"skip_theme_{group_id}")]
                ])
                
                await update.message.reply_text(
                    "📝 *Укажите тему сообщения*\n\n"
                    "Напишите тему, которая будет отображаться в сообщении с документами.\n\n"
                    "Примеры:\n"
                    "• *Срочное согласование договора*\n"
                    "• *Важно: изменение в документации*\n"
                    "• *Годовой отчет за 2024*\n\n"
                    "Или нажмите кнопку ниже, чтобы пропустить",
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                
                # Устанавливаем флаг ожидания темы
                context.user_data['waiting_message_theme'] = {
                    'doc_id': group_id,
                    'file_names': file_names
                }
    
    async def handle_message_theme(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода темы сообщения"""
        if update.effective_user.id != DEVELOPER_ADMIN_ID:
            return
        
        # Проверяем, ожидаем ли мы тему
        if 'waiting_message_theme' not in context.user_data:
            return
        
        theme_data = context.user_data['waiting_message_theme']
        doc_id = theme_data['doc_id']
        file_names = theme_data['file_names']
        
        theme_text = update.message.text.strip()
        
        # Сохраняем тему в базу данных
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Добавляем поле theme в таблицу documents если его нет
                c.execute("PRAGMA table_info(documents)")
                columns = [col[1] for col in c.fetchall()]
                
                if 'theme' not in columns:
                    try:
                        c.execute('ALTER TABLE documents ADD COLUMN theme TEXT')
                        logger.info("✅ Добавлено поле theme в таблицу documents")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось добавить поле theme: {e}")
                
                # Сохраняем тему
                c.execute('UPDATE documents SET theme = ? WHERE id = ?', (theme_text, doc_id))
                conn.commit()
                
            logger.info(f"✅ Тема сохранена для документа {doc_id}: {theme_text[:50]}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения темы: {e}")
        
        # Очищаем контекст
        del context.user_data['waiting_message_theme']
        
        # Устанавливаем флаг ожидания получателей
        context.user_data['waiting_recipients'] = True
        
        # Показываем меню для указания получателей
        await self._show_recipients_menu(update, context, doc_id, file_names)
    
    async def _show_recipients_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE, doc_id: str, file_names: List[str]):
        """Показывает меню для указания получателей с кнопкой 'Ввести вручную' рядом"""
        # Получаем список последних контактов
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''SELECT phone, username, name FROM contacts 
                            ORDER BY last_activity DESC LIMIT 10''')
                recent_contacts = c.fetchall()
        except sqlite3.OperationalError:
            recent_contacts = []
        
        # Создаем клавиатуру - ВАЖНО: обе кнопки в одном ряду
        keyboard_buttons = []
        
        if recent_contacts:
            # ДВЕ КНОПКИ В ОДНОМ РЯДУ
            keyboard_buttons.append([
                InlineKeyboardButton("👥 ВЫБРАТЬ ИЗ КОНТАКТОВ", callback_data=f"select_contacts_{doc_id}"),
                InlineKeyboardButton("✏️ ВВЕСТИ ВРУЧНУЮ", callback_data=f"back_to_input_{doc_id}")
            ])
        else:
            # Если нет контактов, только кнопка ввода вручную
            keyboard_buttons.append([
                InlineKeyboardButton("✏️ ВВЕСТИ ВРУЧНУЮ", callback_data=f"back_to_input_{doc_id}")
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_doc")
        ])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        # Формируем сообщение
        if len(file_names) == 1:
            message_text = f"📄 Документ получен: {file_names[0]}\n"
        else:
            message_text = f"📚 Получено документов: {len(file_names)}\n"
            message_text += f"🆔 Группа ID: {doc_id}\n\n"
            message_text += "📋 Список документов:\n"
            for i, name in enumerate(file_names, 1):
                message_text += f"{i}. {name}\n"
            message_text += "\n"
        
        message_text += f"🆔 ID: {doc_id}\n\n"
        
        if recent_contacts:
            message_text += "📋 *Выберите способ указания получателей:*\n\n"
            message_text += "👥 **Выбрать из контактов** - выбрать из вашего списка контактов\n"
            message_text += "✏️ **Ввести вручную** - ввести телефоны или username вручную\n\n"
        else:
            message_text += "📋 *Укажите получателей:*\n"
            message_text += "Нажмите '✏️ ВВЕСТИ ВРУЧНУЮ' чтобы ввести телефоны или username\n\n"
        
        message_text += "📱 *Форматы телефонов:*\n"
        message_text += "<PHONE_NUMBER>, +7 <PHONE_NUMBER>, <PHONE_NUMBER>\n\n"
        message_text += "• Для телефонов - система попытается отправить автоматически"
        
        # Сохраняем ID сообщения для возможного удаления
        message = await update.message.reply_text(
            message_text,
            reply_markup=keyboard
        )
        context.user_data['recipients_message_id'] = message.message_id

    async def activate_contact(self, user_id: int, phone: str = None, username: str = None):
        """Единый метод активации. Связывает пользователя с существующим контактом."""
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Нормализация телефона
                if phone:
                    phone = self.normalize_phone(phone)
                
                # Получаем информацию о пользователе
                user = update.effective_user if hasattr(update, 'effective_user') else None
                user_name = user.first_name if user else None
                user_username = user.username if user else None
                
                # ===== 1. ПРОВЕРЯЕМ, ЕСТЬ ЛИ УЖЕ КОНТАКТ С ЭТИМ TELEGRAM_ID =====
                c.execute('SELECT id, first_activation FROM contacts WHERE telegram_id = ?', (user_id,))
                existing = c.fetchone()
                
                if existing:
                    contact_id, existing_first_activation = existing
                    # Обновляем существующий контакт
                    c.execute('''
                        UPDATE contacts 
                        SET last_activity = CURRENT_TIMESTAMP,
                            name = COALESCE(?, name),
                            username = COALESCE(?, username),
                            phone = COALESCE(?, phone)
                        WHERE id = ?
                    ''', (user_name, username or user_username, phone, contact_id))
                    
                    # Устанавливаем first_activation если его нет
                    if not existing_first_activation:
                        c.execute('UPDATE contacts SET first_activation = CURRENT_TIMESTAMP WHERE id = ?', (contact_id,))
                    
                    logger.info(f"✅ Контакт {contact_id} обновлен для пользователя {user_id}")
                    conn.commit()
                    return True
                
                # ===== 2. ИЩЕМ КОНТАКТ ПО ТЕЛЕФОНУ =====
                contact_id = None
                if phone:
                    c.execute('SELECT id FROM contacts WHERE phone = ?', (phone,))
                    row = c.fetchone()
                    if row:
                        contact_id = row[0]
                
                # ===== 3. ИЩЕМ КОНТАКТ ПО USERNAME =====
                if not contact_id and (username or user_username):
                    search_username = username or user_username
                    c.execute('SELECT id FROM contacts WHERE username = ?', (search_username,))
                    row = c.fetchone()
                    if row:
                        contact_id = row[0]
                
                # ===== 4. ОБНОВЛЯЕМ ИЛИ СОЗДАЕМ КОНТАКТ =====
                if contact_id:
                    # Обновляем существующий контакт
                    c.execute('''
                        UPDATE contacts 
                        SET telegram_id = ?,
                            first_activation = COALESCE(first_activation, CURRENT_TIMESTAMP),
                            last_activity = CURRENT_TIMESTAMP,
                            name = COALESCE(?, name),
                            username = COALESCE(?, username),
                            phone = COALESCE(?, phone)
                        WHERE id = ?
                    ''', (user_id, user_name, username or user_username, phone, contact_id))
                    logger.info(f"✅ Контакт {contact_id} активирован для пользователя {user_id}")
                else:
                    # Создаем новый контакт
                    c.execute('''
                        INSERT INTO contacts 
                        (telegram_id, phone, username, name, first_activation, last_activity)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ''', (user_id, phone, username or user_username, user_name))
                    contact_id = c.lastrowid
                    logger.info(f"✅ Создан новый контакт {contact_id} для пользователя {user_id}")
                
                conn.commit()
                
                # ===== 5. ОТПРАВЛЯЕМ ОЖИДАЮЩИЕ ДОКУМЕНТЫ =====
                await self.send_pending_documents_to_user(user_id, self.application)
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка активации: {e}")
            return False
    
    async def handle_contact_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора контактов - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        query = update.callback_query
        await query.answer()
        
        action = query.data
        
        if action.startswith("tog_"):
            # Переключение выбора контакта - БЕЗОПАСНОЕ РАСПАКОВЫВАНИЕ
            parts = action.split("_")
            if len(parts) >= 3:
                # Формат: tog_doc_id_contact_id
                doc_id = parts[1]
                try:
                    contact_id = int(parts[2])
                except (ValueError, IndexError):
                    await query.answer("❌ Неверный формат данных", show_alert=True)
                    return
            else:
                await query.answer("❌ Недостаточно данных", show_alert=True)
                return
            
            # Инициализируем если нужно
            if 'selected_contacts' not in context.user_data:
                context.user_data['selected_contacts'] = {}
            
            if doc_id not in context.user_data['selected_contacts']:
                context.user_data['selected_contacts'][doc_id] = []
            
            selected_list = context.user_data['selected_contacts'][doc_id]
            
            # Находим контакт в сохраненных данных
            contact_info = None
            if 'contacts_for_selection' in context.user_data:
                if doc_id in context.user_data['contacts_for_selection']:
                    # Ищем контакт по ID
                    for contact_key, contact_data in context.user_data['contacts_for_selection'][doc_id].items():
                        if contact_data.get('id') == contact_id:
                            contact_info = contact_data
                            break
            
            if not contact_info:
                await query.answer("❌ Контакт не найден", show_alert=True)
                return
            
            # Проверяем, выбран ли уже
            contact_found = False
            for i, contact in enumerate(selected_list):
                if contact.get('id') == contact_id:
                    # Удаляем из выбранных
                    selected_list.pop(i)
                    contact_found = True
                    break
            
            if not contact_found:
                # Добавляем в выбранные
                selected_list.append({
                    'id': contact_id,
                    'phone': contact_info.get('phone'),
                    'username': contact_info.get('username'),
                    'name': contact_info.get('name'),
                    'telegram_id': contact_info.get('telegram_id')
                })
            
            # Обновляем сообщение
            await self.show_contacts_selection(update, context)
        
        elif action.startswith("send_selected_"):
            # ОТПРАВКА ВЫБРАННЫХ КОНТАКТОВ
            doc_id = action.replace("send_selected_", "")
            
            if 'selected_contacts' not in context.user_data or doc_id not in context.user_data['selected_contacts']:
                await query.answer("❌ Не выбрано контактов", show_alert=True)
                return
            
            selected_contacts = context.user_data['selected_contacts'][doc_id]
            
            if not selected_contacts:
                await query.answer("❌ Не выбрано контактов", show_alert=True)
                return
            
            # Получаем файлы документа и тему
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    c.execute('''SELECT file_id, file_name FROM document_files 
                                WHERE doc_id = ? ORDER BY file_order''', (doc_id,))
                    files = c.fetchall()
                    
                    # Получаем тему документа
                    c.execute('SELECT theme FROM documents WHERE id = ?', (doc_id,))
                    theme_result = c.fetchone()
                    theme_text = theme_result[0] if theme_result else None
            except sqlite3.OperationalError:
                files = []
                theme_text = None
            
            if not files:
                await query.answer("❌ Файлы документа не найдены", show_alert=True)
                return
            
            # Формируем список получателей с сохранением имен
            recipient_list = []
            for contact in selected_contacts:
                recipient_info = {}
                if contact.get('phone'):
                    recipient_info = {
                        'type': 'phone',
                        'value': contact['phone'],
                        'original': contact['phone'],
                        'name': contact.get('name')
                    }
                    recipient_list.append(recipient_info)
                elif contact.get('username'):
                    recipient_info = {
                        'type': 'username',
                        'value': f"@{contact['username']}",
                        'original': f"@{contact['username']}",
                        'name': contact.get('name')
                    }
                    recipient_list.append(recipient_info)
            
            # Получаем объект бота из контекста
            bot = context.bot
            
            # Получаем username бота
            bot_info = await bot.get_me()
            bot_username = bot_info.username
            
            # Отправляем каждому получателю
            results = []
            for recipient in recipient_list:
                result = await self.send_to_recipient(
                    bot, recipient, doc_id, files, bot_username
                )
                results.append(result)
            
            # Генерируем отчет
            file_names = [file_name for _, file_name in files]
            report = await self.generate_report(results, file_names, doc_id)
            
            # Отправляем отчет
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
            ])
            
            try:
                await query.message.delete()
            except:
                pass
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=report,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            # Очищаем временные данные
            self._clear_document_context(context)
        
        # ДОБАВЛЕНА ОБРАБОТКА ПАГИНАЦИИ
        elif action.startswith("page_"):
            parts = action.split("_")
            if len(parts) >= 3:
                doc_id = parts[1]
                try:
                    page = int(parts[2])
                except (ValueError, IndexError):
                    page = 0
                
                if 'current_page' not in context.user_data:
                    context.user_data['current_page'] = {}
                context.user_data['current_page'][doc_id] = page
                context.user_data['current_doc_id'] = doc_id
            
            await self.show_contacts_selection(update, context)
        
        # ДОБАВЛЕНА ОБРАБОТКА КНОПКИ "ОБНОВИТЬ"
        elif action == "refresh_contacts" or action.startswith("select_contacts_"):
            if action.startswith("select_contacts_"):
                doc_id = action.replace("select_contacts_", "")
            else:
                if 'current_doc_id' in context.user_data:
                    doc_id = context.user_data['current_doc_id']
                elif 'pending_doc' in context.user_data:
                    doc_id = context.user_data['pending_doc']['id']
                else:
                    await query.answer("❌ Документ не найден", show_alert=True)
                    return
            
            if 'contacts_for_selection' in context.user_data:
                if doc_id in context.user_data['contacts_for_selection']:
                    del context.user_data['contacts_for_selection'][doc_id]
            
            if 'current_page' in context.user_data:
                if doc_id in context.user_data['current_page']:
                    context.user_data['current_page'][doc_id] = 0
            
            context.user_data['current_doc_id'] = doc_id
            await self.show_contacts_selection(update, context)
        
        elif action == "noop":
            await query.answer()
            return
        
        elif action.startswith("back_to_input_"):
            doc_id = action.replace("back_to_input_", "")
            
            if 'contacts_for_selection' in context.user_data:
                context.user_data['contacts_for_selection'] = {}
            if 'selected_contacts' in context.user_data:
                context.user_data['selected_contacts'] = {}
            
            if 'current_page' in context.user_data:
                if doc_id in context.user_data['current_page']:
                    del context.user_data['current_page'][doc_id]
            
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    c.execute('''SELECT file_name FROM document_files 
                                WHERE doc_id = ? ORDER BY file_order''', (doc_id,))
                    files = c.fetchall()
            except sqlite3.OperationalError:
                files = []
            
            file_names = [file_name for file_name, in files]
            await self._show_recipients_menu_by_query(query, context, doc_id, file_names)
        
        elif action == "cancel_selection":
            self._clear_document_context(context)
            await query.message.delete()
            await self.show_admin_menu(update, context)
        
        elif action == "cancel_doc":
            await self.cancel_command(update, context)
        
        else:
            await self.show_contacts_selection(update, context)
    
    async def _show_recipients_menu_by_query(self, query, context, doc_id: str, file_names: List[str]):
        """Показывает меню для указания получателей через query"""
        # Получаем список последних контактов
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''SELECT phone, username, name FROM contacts 
                            ORDER BY last_activity DESC LIMIT 10''')
                recent_contacts = c.fetchall()
        except sqlite3.OperationalError:
            recent_contacts = []
        
        # Создаем клавиатуру
        keyboard_buttons = []
        if recent_contacts:
            keyboard_buttons.append([
                InlineKeyboardButton("👥 ВЫБРАТЬ ИЗ КОНТАКТОВ", callback_data=f"select_contacts_{doc_id}")
            ])
        keyboard_buttons.append([
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_doc")
        ])
        
        # УБРАНА кнопка Start/Menu из основного меню
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        # Формируем сообщение
        if len(file_names) == 1:
            message_text = f"📄 Документ: {file_names[0]}\n"
        else:
            message_text = f"📚 Документов: {len(file_names)}\n"
            message_text += f"🆔 Группа ID: {doc_id}\n\n"
        
        message_text += f"📋 Укажите получателей:\n\n"
        
        if recent_contacts:
            message_text += "👥 Или нажмите 'ВЫБРАТЬ ИЗ КОНТАКТОВ'\n\n"
        
        try:
            await query.message.edit_text(message_text, reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка редактирования: {e}")
    
    async def handle_recipients(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода получателей"""
        if update.effective_user.id != DEVELOPER_ADMIN_ID:
            return
        
        # Проверяем, есть ли активный документ
        doc_id = None
        file_names = []
        
        if 'pending_doc' in context.user_data:
            doc_id = context.user_data['pending_doc']['id']
            file_names = [context.user_data['pending_doc']['file_name']]
        elif 'current_doc_id' in context.user_data:
            doc_id = context.user_data['current_doc_id']
            # Получаем файлы документа из базы
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    c.execute('''SELECT file_name FROM document_files 
                                WHERE doc_id = ? ORDER BY file_order''', (doc_id,))
                    files = c.fetchall()
                file_names = [file_name for file_name, in files]
            except sqlite3.OperationalError:
                files = []
        
        if not doc_id:
            await update.message.reply_text("❌ Сначала отправьте документ")
            return
        
        text = update.message.text.strip()
        
        if not text:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
            ])
            
            await update.message.reply_text(
                "❌ Не указаны получатели",
                reply_markup=keyboard
            )
            return
        
        recipients = self.parse_recipients(text)
        
        if not recipients:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
            ])
            
            await update.message.reply_text(
                "❌ Не удалось распознать получателей",
                reply_markup=keyboard
            )
            return
        
        # Получаем файлы документа
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''SELECT file_id, file_name FROM document_files 
                            WHERE doc_id = ? ORDER BY file_order''', (doc_id,))
                files = c.fetchall()
        except sqlite3.OperationalError:
            files = []
        
        if not files:
            await update.message.reply_text("❌ Файлы документа не найдены")
            return
        
        bot_info = await context.bot.get_me()
        bot_username = bot_info.username
        
        # Отправляем каждому получателю
        results = []
        for recipient in recipients:
            result = await self.send_to_recipient(
                context.bot, recipient, doc_id, files, bot_username
            )
            results.append(result)
        
        # Генерируем отчет
        file_names = [file_name for _, file_name in files]
        report = await self.generate_report(results, file_names, doc_id)
        
        # Отправляем отчет админу
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
        ])
        
        await update.message.reply_text(report, reply_markup=keyboard, parse_mode='Markdown')
        
        # Очищаем все временные данные
        self._clear_document_context(context)
    
    async def send_to_recipients(self, bot, recipients: List[Dict], doc_id: str, files: List[tuple], 
                                bot_username: str) -> List[Dict]:
        results = []
        
        for recipient in recipients:
            result = await self.send_to_recipient(
                bot, recipient, doc_id, files, bot_username
            )
            results.append(result)
        
        return results

    def cleanup_recipients_duplicates(self):
        """Очищает дубликаты в таблице recipients"""
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # 1. Находим дубликаты
                c.execute('''
                    SELECT doc_id, contact_id, COUNT(*) as cnt, 
                        GROUP_CONCAT(id) as ids,
                        GROUP_CONCAT(status) as statuses
                    FROM recipients
                    GROUP BY doc_id, contact_id
                    HAVING cnt > 1
                ''')
                
                duplicates = c.fetchall()
                
                if duplicates:
                    logger.info(f"🔍 Найдено {len(duplicates)} групп дубликатов в recipients")
                    
                    for doc_id, contact_id, cnt, ids, statuses in duplicates:
                        id_list = ids.split(',')
                        
                        # Стратегия: оставляем запись с решением (approved/rejected)
                        # или самую старую (минимальный id)
                        keep_id = None
                        
                        # Сначала ищем запись с approved/rejected
                        status_list = statuses.split(',')
                        for idx, status in enumerate(status_list):
                            if status in ('approved', 'rejected'):
                                keep_id = id_list[idx]
                                break
                        
                        # Если не нашли, берем самую старую (минимальный id)
                        if not keep_id:
                            keep_id = min(id_list, key=int)
                        
                        # Удаляем все остальные
                        delete_ids = [id for id in id_list if id != keep_id]
                        c.execute(f'''
                            DELETE FROM recipients 
                            WHERE id IN ({','.join(['?'] * len(delete_ids))})
                        ''', delete_ids)
                        
                        logger.info(f"✅ Оставлена запись {keep_id}, удалено {len(delete_ids)} дублей для doc_id={doc_id}, contact_id={contact_id}")
                    
                    conn.commit()
                
                # 2. Создаем уникальный индекс
                c.execute('''
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_recipients_unique 
                    ON recipients (doc_id, contact_id)
                ''')
                
                conn.commit()
                logger.info("✅ Индекс idx_recipients_unique создан/проверен")
                
                return len(duplicates)
                
        except Exception as e:
            logger.error(f"❌ Ошибка очистки recipients: {e}")
            return 0
    
    async def send_to_recipient(self, bot, recipient: Dict, doc_id: str, files: List[tuple], bot_username: str) -> Dict:
        """Отправка получателю с гарантией уникальности (doc_id, contact_id)"""
        
        retry_count = 3
        retry_delay = 1

        for attempt in range(retry_count):
            try:
                identifier_type = recipient['type']
                identifier_value = recipient['value']
                original = recipient['original']

                # ===== ТОЛЬКО ТЕЛЕФОНЫ =====
                if identifier_type != 'phone':
                    return {
                        'success': False,
                        'type': 'invalid_type',
                        'recipient': original,
                        'message': "❌ Поддерживается только отправка по телефону"
                    }

                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # ===== ПОЛУЧАЕМ ТЕМУ ДОКУМЕНТА =====
                    theme_text = None
                    try:
                        c.execute('SELECT theme FROM documents WHERE id = ?', (doc_id,))
                        theme_result = c.fetchone()
                        if theme_result and theme_result[0]:
                            theme_text = theme_result[0]
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось получить тему для документа {doc_id}: {e}")
                    
                    # ===== 1. НАХОДИМ ИЛИ СОЗДАЕМ КОНТАКТ =====
                    c.execute('SELECT id, name, telegram_id FROM contacts WHERE phone = ?', (identifier_value,))
                    contact = c.fetchone()
                    
                    deep_link = f"https://t.me/{bot_username}?start=doc_{doc_id}"
                    
                    if contact:
                        contact_id, name, telegram_id = contact
                    else:
                        # Создаем новый контакт
                        c.execute('INSERT INTO contacts (phone) VALUES (?)', (identifier_value,))
                        contact_id = c.lastrowid
                        name = None
                        telegram_id = None
                    
                    # ===== 2. UPSERT В ТАБЛИЦУ RECIPIENTS =====
                    c.execute('''
                        UPDATE recipients 
                        SET 
                            identifier_type = ?,
                            identifier_value = ?,
                            status = CASE 
                                WHEN status IN ('approved', 'rejected') THEN status 
                                ELSE 'pending' 
                            END,
                            sent_via = ?,
                            notification_sent = 0
                        WHERE doc_id = ? AND contact_id = ?
                    ''', (identifier_type, identifier_value, 
                        'direct' if telegram_id else 'phone_auto', 
                        doc_id, contact_id))
                    
                    # Если ничего не обновили - вставляем новую запись
                    if c.rowcount == 0:
                        c.execute('''
                            INSERT INTO recipients 
                            (doc_id, contact_id, identifier_type, identifier_value, sent_via, status)
                            VALUES (?, ?, ?, ?, ?, 'pending')
                        ''', (doc_id, contact_id, identifier_type, identifier_value,
                            'direct' if telegram_id else 'phone_auto'))
                    
                    conn.commit()
                    
                    # ===== 3. ОТПРАВКА =====
                    if telegram_id:
                        # АКТИВИРОВАННЫЙ ПОЛЬЗОВАТЕЛЬ - ОТПРАВЛЯЕМ НАПРЯМУЮ
                        lang = self.get_user_language(telegram_id)
                        
                        keyboard = InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton("✅ Согласен", callback_data=f"approve_{doc_id}"),
                                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{doc_id}")
                            ],
                            [
                                InlineKeyboardButton(
                                    Translations.get('leave_comment', lang),
                                    callback_data=f"comment_{doc_id}"
                                ),
                                InlineKeyboardButton(
                                    Translations.get('view_recipients', lang),
                                    callback_data=f"view_recipients_{doc_id}"
                                )
                            ]
                        ])
                        
                        first_file_id, first_file_name = files[0]
                        
                        # Экранируем имя файла для Markdown
                        safe_file_name = self.escape_markdown(first_file_name)
                        
                        # ===== ФОРМИРУЕМ ТЕКСТ С ТЕМОЙ И ЭКРАНИРОВАНИЕМ =====
                        theme_line = ""
                        if theme_text:
                            safe_theme = self.escape_markdown(theme_text)
                            theme_line = f"📌 **Тема:** {safe_theme}\n\n"
                        
                        caption_text = (
                            f"📄 *Новый документ для согласования*\n\n"
                            f"{theme_line}"
                            f"**{safe_file_name}**\n"
                            f"{f'📚 Всего файлов: {len(files)}' if len(files) > 1 else ''}\n\n"
                            f"👇 Используйте кнопки ниже"
                        )
                        
                        try:
                            await bot.send_document(
                                chat_id=telegram_id,
                                document=first_file_id,
                                caption=caption_text,
                                reply_markup=keyboard,
                                parse_mode='Markdown'
                            )
                            
                            for i in range(1, len(files)):
                                file_id, file_name = files[i]
                                safe_name = self.escape_markdown(file_name)
                                await bot.send_document(
                                    chat_id=telegram_id,
                                    document=file_id,
                                    caption=f"📄 *Документ {i+1}:* {safe_name}",
                                    parse_mode='Markdown'
                                )
                            
                            # ВОЗВРАЩАЕМ РЕЗУЛЬТАТ С ИМЕНЕМ
                            return {
                                'success': True,
                                'type': 'direct',
                                'recipient': original,
                                'name': name,
                                'telegram_id': telegram_id,
                                'message': "✅ Документ отправлен напрямую"
                            }
                            
                        except Exception as e:
                            logger.error(f"❌ Ошибка отправки пользователю {telegram_id}: {e}")
                            return {
                                'success': False,
                                'type': 'send_error',
                                'recipient': original,
                                'name': name,
                                'message': f"❌ Ошибка отправки: {str(e)[:60]}"
                            }
                    
                    else:
                        # НЕ АКТИВИРОВАННЫЙ ПОЛЬЗОВАТЕЛЬ - АВТО-ПРИГЛАШЕНИЕ
                        if self.admin_sender:
                            first_file_name = files[0][1] if files else "Документ"
                            
                            send_result = await self.admin_sender.send_invitation_to_phone(
                                phone=identifier_value,
                                doc_id=doc_id,
                                file_name=first_file_name,
                                file_count=len(files),
                                theme=theme_text
                            )
                            
                            if send_result.get('success'):
                                return {
                                    'success': True,
                                    'type': 'phone_auto',
                                    'recipient': original,
                                    'name': name,
                                    'deep_link': deep_link,
                                    'message': "📲 Приглашение автоматически отправлено"
                                }
                        
                        return {
                            'success': False,
                            'type': 'invite_failed',
                            'recipient': original,
                            'name': name,
                            'deep_link': deep_link,
                            'message': "❌ Не удалось отправить авто-приглашение"
                        }

            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retry_count - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return {
                    'success': False,
                    'type': 'database_error',
                    'recipient': recipient['original'],
                    'name': None,
                    'message': "❌ Ошибка базы данных"
                }
            except Exception as e:
                logger.error(f"❌ send_to_recipient error: {e}")
                return {
                    'success': False,
                    'type': 'error',
                    'recipient': recipient['original'],
                    'name': None,
                    'message': f"❌ Ошибка: {str(e)[:60]}"
                }
    
    async def generate_report(self, results: List[Dict], file_names: List[str], doc_id: str) -> str:
        """Упрощенный отчет после отправки документа с именами вместо телефонов"""
        
        # Считаем статистику
        total_success = sum(1 for r in results if r.get('success', False))
        total_failed = sum(1 for r in results if not r.get('success', False))
        total_recipients = len(results)
        
        if len(file_names) == 1:
            report = f"📄 *Отправка документа*\n\n"
            # Экранируем имя файла
            safe_file_name = self.escape_markdown(file_names[0])
            report += f"📄 *Название:* {safe_file_name}\n"
        else:
            report = f"📚 *Отправка документов*\n\n"
            report += f"📚 *Файлов:* {len(file_names)}\n"
        
        report += f"\n📊 *Статистика:*\n"
        report += f"• 👥 Получателей: {total_recipients}\n"
        report += f"• ✅ Отправлено: {total_success}\n"
        if total_failed > 0:
            report += f"• ❌ Ошибок: {total_failed}\n"
        
        # Показываем успешные отправки
        successful = [r for r in results if r.get('success', False)]
        if successful:
            report += f"\n✅ *Успешно отправлено:*\n"
            for i, result in enumerate(successful[:5], 1):
                recipient = result.get('recipient', '')
                name = result.get('name')
                message = result.get('message', '')
                
                # Очищаем сообщение
                if '✅' in message:
                    clean_msg = message.split('✅')[-1].strip()
                else:
                    clean_msg = message
                
                # Используем имя если есть, иначе телефон
                display_name = name if name else recipient
                safe_display_name = self.escape_markdown(display_name)
                
                report += f"{i}. {safe_display_name} - {clean_msg}\n"
            
            if len(successful) > 5:
                report += f"... и еще {len(successful) - 5}\n"
        
        # Показываем ошибки если есть
        failed = [r for r in results if not r.get('success', False)]
        if failed:
            report += f"\n❌ *Ошибки отправки:*\n"
            for i, result in enumerate(failed[:3], 1):
                recipient = result.get('recipient', '')
                name = result.get('name')
                message = result.get('message', 'Неизвестная ошибка')
                
                display_name = name if name else recipient
                safe_display_name = self.escape_markdown(display_name)
                report += f"{i}. {safe_display_name}: {message}\n"
            
            if len(failed) > 3:
                report += f"... и еще {len(failed) - 3}\n"
        
        report += f"\n🆔 *ID документа:* {doc_id[:8]}"
        
        # Добавляем информацию о том, что делать если есть ошибки
        if total_failed > 0:
            report += f"\n\n💡 *Что делать с ошибками:*\n"
            report += f"1. Проверьте правильность контактов\n"
            report += f"2. Попробуйте отправить снова через меню\n"
            report += f"3. Используйте другой способ отправки"
        
        return report
    
    async def show_document_to_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE, doc_id: str):
        """Показывает документ пользователю - ИСПРАВЛЕННЫЙ ВАРИАНТ"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем файлы документа
                c.execute('''SELECT file_id, file_name FROM document_files 
                            WHERE doc_id = ? ORDER BY file_order''', (doc_id,))
                files = c.fetchall()
                
                if not files:
                    await query.message.edit_text("❌ Документ не найден")
                    return
                
                # ========== ИСПРАВЛЕНИЕ НАЧАЛО ==========
                # Проверяем статус пользователя для этого документа
                # Сначала ищем по telegram_id
                user_status = None
                comment = None
                response_time = None
                comment_only = False
                status = 'pending'
                
                # Способ 1: Поиск по telegram_id
                c.execute('''SELECT r.status, r.comment, r.response_time, r.comment_only, c.id
                            FROM recipients r
                            JOIN contacts c ON r.contact_id = c.id
                            WHERE r.doc_id = ? AND c.telegram_id = ?''', (doc_id, user_id))
                
                user_status = c.fetchone()
                
                # Способ 2: Если не нашли по telegram_id, ищем пользователя, который еще не отвечал
                if not user_status:
                    # Ищем получателя, который ожидает ответа (статус 'pending')
                    # для этого документа
                    c.execute('''SELECT r.id, r.status, r.comment, r.response_time, r.comment_only, 
                                c.id as contact_id, c.phone, c.username
                                FROM recipients r
                                JOIN contacts c ON r.contact_id = c.id
                                WHERE r.doc_id = ? 
                                AND r.status = 'pending'
                                AND c.telegram_id IS NULL''', (doc_id,))
                    
                    pending_recipients = c.fetchall()
                    
                    if pending_recipients:
                        # Находим подходящего получателя
                        # Можно использовать разные стратегии:
                        # 1. Если у пользователя есть телефон, ищем соответствие по телефону
                        # 2. Берем первого ожидающего
                        
                        # Сначала проверим, есть ли у пользователя телефон в профиле Telegram
                        c.execute('''SELECT phone FROM contacts WHERE telegram_id = ?''', (user_id,))
                        user_phone_info = c.fetchone()
                        
                        recipient_found = None
                        
                        if user_phone_info and user_phone_info[0]:
                            # У пользователя есть телефон в профиле
                            user_phone = self.normalize_phone(user_phone_info[0])
                            
                            # Ищем получателя с таким же телефоном
                            for recipient in pending_recipients:
                                recipient_id, recipient_status, recipient_comment, recipient_response_time, \
                                recipient_comment_only, contact_id, phone, username = recipient
                                
                                if phone:
                                    normalized_phone = self.normalize_phone(phone)
                                    if normalized_phone == user_phone:
                                        recipient_found = recipient
                                        break
                        
                        # Если не нашли по телефону, берем первого ожидающего
                        if not recipient_found and pending_recipients:
                            recipient_found = pending_recipients[0]
                        
                        if recipient_found:
                            recipient_id, recipient_status, recipient_comment, recipient_response_time, \
                            recipient_comment_only, contact_id, phone, username = recipient_found
                            
                            # Обновляем контакт с telegram_id пользователя
                            c.execute('''UPDATE contacts 
                                        SET telegram_id = ?, last_activity = CURRENT_TIMESTAMP
                                        WHERE id = ? AND telegram_id IS NULL''', 
                                    (user_id, contact_id))
                            
                            user_status = (recipient_status, recipient_comment, 
                                        recipient_response_time, recipient_comment_only, contact_id)
                
                # Обрабатываем результат
                if user_status:
                    status, comment, response_time, comment_only, contact_id = user_status
                    
                    # Если пользователь впервые открывает документ по телефонной ссылке,
                    # обновляем его активацию
                    if response_time is None and not comment_only:
                        # Проверяем, есть ли у него запись first_activation
                        c.execute('''SELECT first_activation FROM contacts WHERE id = ?''', (contact_id,))
                        activation_info = c.fetchone()
                        
                        if not activation_info or activation_info[0] is None:
                            c.execute('''UPDATE contacts 
                                        SET first_activation = CURRENT_TIMESTAMP,
                                            last_activity = CURRENT_TIMESTAMP
                                        WHERE id = ?''', (contact_id,))
                            
                            logger.info(f"✅ Первая активация для контакта {contact_id} (пользователь {user_id})")
                # ========== ИСПРАВЛЕНИЕ КОНЕЦ ==========
                
                conn.commit()
                
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Ошибка получения документа: {e}")
            await query.message.edit_text("❌ Ошибка базы данных")
            return
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка: {e}")
            await query.message.edit_text("❌ Ошибка при загрузке документа")
            return
        
        # Определяем язык пользователя
        lang = self.get_user_language(user_id)
        
        # Определяем текст кнопки комментария
        if comment:
            comment_button_text = Translations.get('edit_comment', lang)
        else:
            comment_button_text = Translations.get('leave_comment', lang)
        
        # Создаем клавиатуру
        keyboard_buttons = []
        
        # Кнопки действий только если документ еще не обработан
        if status == 'pending' or comment_only:
            keyboard_buttons.append([
                InlineKeyboardButton("✅ Согласен", callback_data=f"approve_{doc_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{doc_id}")
            ])
            
            keyboard_buttons.append([
                InlineKeyboardButton(comment_button_text, callback_data=f"comment_{doc_id}"),
                InlineKeyboardButton(Translations.get('view_recipients', lang), 
                                callback_data=f"view_recipients_{doc_id}")
            ])
        else:
            # Если уже обработан, показываем статус
            keyboard_buttons.append([
                InlineKeyboardButton(f"📊 Статус: {Translations.get('recipient_status_' + status, lang)}", 
                                callback_data=f"view_status_{doc_id}")
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(Translations.get('view_instructions', lang), 
                            callback_data="user_instructions")
        ])
        
        # Кнопка возврата
        keyboard_buttons.append([
            InlineKeyboardButton(Translations.get('back_to_menu', lang), 
                            callback_data="user_back_to_menu")
        ])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        # Формируем сообщение
        first_file_name = files[0][1] if files else "Документ"
        message_text = f"📄 *Документ для согласования*\n\n"
        message_text += f"**Название:** {first_file_name}\n"
        
        if len(files) > 1:
            message_text += f"📚 **Всего файлов:** {len(files)}\n"
            message_text += "📄 **Прокрутите вниз, чтобы увидеть все файлы**\n\n"
        else:
            message_text += "\n"
        
        # Показываем статус пользователя
        status_translations = {
            'pending': Translations.get('recipient_status_pending', lang),
            'approved': Translations.get('recipient_status_approved', lang),
            'rejected': Translations.get('recipient_status_rejected', lang)
        }
        
        if comment_only:
            current_status = "💬 Только комментарий"
        else:
            current_status = status_translations.get(status, "📨 Неизвестно")
        
        message_text += f"📊 **Ваш статус:** {current_status}\n"
        
        if comment:
            message_text += f"💬 **Ваш комментарий:** {comment[:100]}{'...' if len(comment) > 100 else ''}\n"
        
        if response_time:
            try:
                resp_dt = datetime.strptime(response_time, '%Y-%m-%d %H:%M:%S')
                message_text += f"🕐 **Время ответа:** {resp_dt.strftime('%d.%m.%Y %H:%M')}\n"
            except:
                pass
        
        message_text += f"\n🆔 **ID документа:** {doc_id}\n\n"
        
        if status == 'pending' or comment_only:
            message_text += "👇 **Используйте кнопки ниже для работы с документом:**\n\n"
            message_text += "• ✅ **Согласен** - подтвердить документ\n"
            message_text += "• ❌ **Отклонить** - отклонить документ\n"
            message_text += "• 💬 **Комментарий** - оставить комментарий\n"
            message_text += "• 👥 **Кто еще получил** - список получателей\n"
            message_text += "• 📖 **Инструкция** - инструкция по работе\n"
        else:
            message_text += "✅ **Документ уже обработан**\n"
            message_text += "Вы можете просмотреть статус и комментарии."
        
        # Проверяем, есть ли предыдущее сообщение с файлом
        if query.message.document:
            # Если сообщение уже содержит документ, НЕ пытаемся его редактировать
            # Вместо этого отправляем новое текстовое сообщение
            await query.message.reply_text(
                message_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            # Если это обычное текстовое сообщение, редактируем его
            try:
                await query.message.edit_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"❌ Ошибка редактирования сообщения: {e}")
                # Пытаемся отправить новое сообщение
                await query.message.reply_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
        
        # Отправляем файлы документа отдельными сообщениями
        for i, (file_id, file_name) in enumerate(files):
            if i == 0:
                # Первый файл уже отправлен с кнопками
                continue
            
            try:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=file_id,
                    caption=f"📄 Документ {i+1}: {file_name}"
                )
            except Exception as e:
                logger.warning(f"⚠️ Не удалось отправить документ {i+1}: {e}")
        
    # ====== НОВЫЕ МЕТОДЫ ДЛЯ КОММЕНТАРИЕВ И СИСТЕМЫ НАПОМИНАНИЙ ======

    async def handle_approve_reject(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка согласия/отклонения документа (после комментария)"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        action = query.data
        
        if action.startswith("approve_"):
            doc_id = action.replace("approve_", "")
            decision = 'approved'
            decision_text = "✅ Согласен"
        elif action.startswith("reject_"):
            doc_id = action.replace("reject_", "")
            decision = 'rejected'
            decision_text = "❌ Отклонено"
        else:
            return
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем contact_id пользователя
                c.execute('SELECT id FROM contacts WHERE telegram_id = ?', (user_id,))
                contact_result = c.fetchone()
                
                if not contact_result:
                    await query.message.edit_text(
                        "❌ Пользователь не найден",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="user_back_to_menu")]
                        ])
                    )
                    return
                
                contact_id = contact_result[0]
                
                # Получаем текущий комментарий
                c.execute('''SELECT comment, comment_only FROM recipients 
                        WHERE doc_id = ? AND contact_id = ?''',
                        (doc_id, contact_id))
                recipient_info = c.fetchone()
                
                comment = None
                was_comment_only = False
                
                if recipient_info:
                    comment, comment_only_flag = recipient_info
                    was_comment_only = comment_only_flag == 1
                
                # Обновляем статус документа
                c.execute('''UPDATE recipients 
                        SET status = ?, 
                            response_time = CURRENT_TIMESTAMP,
                            comment_only = FALSE
                        WHERE doc_id = ? AND contact_id = ?''',
                        (decision, doc_id, contact_id))
                
                # Получаем информацию о документе
                c.execute('''SELECT df.file_name FROM document_files df
                        WHERE df.doc_id = ? AND df.file_order = 1''', (doc_id,))
                doc_info = c.fetchone()
                file_name = doc_info[0] if doc_info else "Документ"
                
                # Получаем информацию о пользователе
                c.execute('''SELECT name, phone, username FROM contacts WHERE id = ?''', (contact_id,))
                user_info = c.fetchone()
                user_name = user_info[0] if user_info else "Пользователь"
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки решения: {e}")
            await query.message.edit_text(
                "❌ Ошибка обработки решения",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Назад в меню", callback_data="user_back_to_menu")]
                ])
            )
            return
        
        # Формируем сообщение для пользователя
        message = f"*Решение принято!*\n\n"
        message += f"📄 Документ: {file_name}\n"
        message += f"✅ Решение: {decision_text}\n"
        
        if comment:
            message += f"💬 Ваш комментарий: {comment}\n\n"
        
        message += f"🎉 *Спасибо за участие в согласовании!*\n\n"
        message += f"📋 Все будущие документы будут приходить вам автоматически."
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 Мои документы", callback_data="user_documents")],
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="user_back_to_menu")]
        ])
        
        await query.message.edit_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        # Отправляем уведомление администратору
        try:
            admin_message = f"📋 *Пользователь принял решение*\n\n"
            admin_message += f"👤 Пользователь: {user_name}\n"
            admin_message += f"🆔 ID: {user_id}\n"
            admin_message += f"📄 Документ: {file_name}\n"
            admin_message += f"🆔 Doc ID: {doc_id}\n"
            admin_message += f"✅ Решение: {decision_text}\n"
            
            if comment:
                admin_message += f"💬 Комментарий: {comment}\n"
            
            if was_comment_only:
                admin_message += f"📝 *Было:* Только комментарий\n"
                admin_message += f"📝 *Стало:* Решение с комментарием\n"
            
            admin_message += f"\n⏰ Время ответа: {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            
            await context.bot.send_message(
                chat_id=DEVELOPER_ADMIN_ID,
                text=admin_message,
                parse_mode='Markdown'
            )
            
            # Удаляем напоминание если было
            self.reminder_manager.remove_reminder(doc_id, user_id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления админу: {e}")
    
    async def handle_comment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатия на кнопку комментария"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data.startswith("comment_"):
            doc_id = data.replace("comment_", "")
            
            # Сохраняем ID документа в контекст для ожидания комментария
            context.user_data['commenting_doc_id'] = doc_id
            
            # Получаем язык пользователя
            lang = self.get_user_language(user_id)
            
            # Проверяем, есть ли уже комментарий
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    c.execute('''SELECT r.comment 
                            FROM recipients r
                            JOIN contacts c ON r.contact_id = c.id
                            WHERE r.doc_id = ? AND c.telegram_id = ?''',
                            (doc_id, user_id))
                    result = c.fetchone()
                    existing_comment = result[0] if result else None
            except:
                existing_comment = None
            
            # Создаем клавиатуру с кнопкой отмены
            keyboard_buttons = [
                [InlineKeyboardButton("❌ Отмена", callback_data=f"back_to_doc_{doc_id}")]
            ]
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
            
            # Формируем текст сообщения
            if existing_comment:
                message_text = (
                    f"💬 *Изменить комментарий*\n\n"
                    f"Текущий комментарий:\n"
                    f"_{existing_comment[:500]}{'...' if len(existing_comment) > 500 else ''}_\n\n"
                    f"📝 Напишите новый комментарий к документу:"
                )
            else:
                message_text = "💬 Напишите ваш комментарий к документу:"
            
            # Проверяем тип сообщения и отправляем/редактируем
            try:
                if query.message.text:
                    await query.message.edit_text(
                        message_text,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
                else:
                    await query.message.reply_text(
                        message_text,
                        reply_markup=keyboard,
                        parse_mode='Markdown'
                    )
            except Exception as e:
                logger.error(f"❌ Ошибка при показе комментария: {e}")
                await query.message.reply_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )

    async def save_comment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохранение комментария"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        # Проверяем, есть ли документ для комментария
        if 'commenting_doc_id' not in context.user_data:
            # Если нет, показываем меню
            if user_id == DEVELOPER_ADMIN_ID:
                await self.show_admin_menu(update, context)
            else:
                first_name = update.effective_user.first_name
                await self.show_user_menu(update, first_name, context)
            return
        
        doc_id = context.user_data['commenting_doc_id']
        
        # Проверка длины комментария
        if not text:
            await update.message.reply_text("❌ Комментарий не может быть пустым")
            return
        
        if len(text) > 1000:
            lang = self.get_user_language(user_id)
            await update.message.reply_text(
                Translations.get('comment_too_long', lang),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Назад к документу", callback_data=f"back_to_doc_{doc_id}")]
                ])
            )
            return
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем contact_id пользователя
                c.execute('SELECT id FROM contacts WHERE telegram_id = ?', (user_id,))
                contact_result = c.fetchone()
                
                if not contact_result:
                    await update.message.reply_text("❌ Пользователь не найден в системе")
                    return
                
                contact_id = contact_result[0]
                
                # Сохраняем комментарий
                c.execute('''UPDATE recipients 
                            SET comment = ?,
                                comment_only = CASE 
                                    WHEN status = 'pending' THEN TRUE 
                                    ELSE FALSE 
                                END
                            WHERE doc_id = ? AND contact_id = ?''',
                        (text, doc_id, contact_id))
                
                # Если не обновилось, пробуем вставить
                if c.rowcount == 0:
                    c.execute('''INSERT INTO recipients 
                                (doc_id, contact_id, identifier_type, identifier_value, comment, comment_only, status)
                                VALUES (?, ?, 'telegram_id', ?, ?, TRUE, 'pending')''',
                            (doc_id, contact_id, str(user_id), text))
                
                conn.commit()
                
                logger.info(f"✅ Комментарий сохранен для пользователя {user_id} по документу {doc_id}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения комментария: {e}")
            await update.message.reply_text("❌ Ошибка при сохранении комментария")
            return
        
        # Очищаем контекст
        del context.user_data['commenting_doc_id']
        
        # Получаем язык пользователя
        lang = self.get_user_language(user_id)
        
        # Отправляем подтверждение
        keyboard_buttons = [
            [
                InlineKeyboardButton("✅ Согласен", callback_data=f"approve_{doc_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{doc_id}")
            ],
            [
                InlineKeyboardButton("💬 Изменить комментарий", callback_data=f"comment_{doc_id}"),
                InlineKeyboardButton("👥 Кто еще получил", callback_data=f"view_recipients_{doc_id}")
            ],
            [
                InlineKeyboardButton("⬅️ Назад к документу", callback_data=f"back_to_doc_{doc_id}")
            ]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await update.message.reply_text(
            f"✅ *Комментарий сохранен!*\n\n"
            f"📝 Ваш комментарий:\n_{text[:200]}{'...' if len(text) > 200 else ''}_\n\n"
            f"Теперь выберите решение по документу:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def handle_comment_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текста комментария"""
        user_id = update.effective_user.id
        
        # Проверяем, ожидаем ли мы комментарий от этого пользователя
        if 'waiting_comment' not in context.user_data:
            return
        
        waiting_data = context.user_data['waiting_comment']
        
        if waiting_data['user_id'] != user_id:
            return
        
        doc_id = waiting_data['doc_id']
        comment_text = update.message.text.strip()
        
        # Проверяем длину комментария
        if len(comment_text) > 1000:
            lang = self.get_user_language(user_id)
            await update.message.reply_text(
                Translations.get('comment_too_long', lang),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Назад к документу", callback_data=f"open_doc_{doc_id}")]
                ])
            )
            return
        
        # Сохраняем комментарий в базе
        retry_count = 3
        retry_delay = 1
        
        for attempt in range(retry_count):
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # Находим contact_id пользователя
                    c.execute('SELECT id FROM contacts WHERE telegram_id = ?', (user_id,))
                    contact_result = c.fetchone()
                    
                    if not contact_result:
                        logger.error(f"Контакт не найден для user_id {user_id}")
                        return
                    
                    contact_id = contact_result[0]
                    
                    # Обновляем комментарий
                    c.execute('''UPDATE recipients 
                            SET comment = ?, 
                                comment_time = CURRENT_TIMESTAMP,
                                comment_only = CASE 
                                    WHEN status = 'pending' THEN TRUE 
                                    ELSE FALSE 
                                END
                            WHERE doc_id = ? AND contact_id = ?''',
                            (comment_text, doc_id, contact_id))
                    
                    conn.commit()
                    
                    # Добавляем напоминание если пользователь еще не принял решение
                    if comment_text:
                        # Получаем информацию о пользователе
                        c.execute('''SELECT name, phone, username FROM contacts WHERE id = ?''', (contact_id,))
                        user_info = c.fetchone()
                        
                        if user_info:
                            name, phone, username = user_info
                            user_identifier = name or f"@{username}" if username else phone or f"ID: {user_id}"
                            
                            # Добавляем напоминание
                            self.reminder_manager.add_reminder(
                                doc_id=doc_id,
                                user_id=user_id,
                                comment_time=datetime.now(),
                                comment_text=comment_text,
                                user_info={
                                    'identifier': user_identifier,
                                    'name': name,
                                    'phone': phone,
                                    'username': username
                                }
                            )
                            
                            # Добавляем финальное напоминание
                            self.reminder_manager.add_final_reminder(
                                doc_id=doc_id,
                                user_id=user_id,
                                comment_time=datetime.now(),
                                comment_text=comment_text,
                                user_info={
                                    'identifier': user_identifier,
                                    'name': name,
                                    'phone': phone,
                                    'username': username
                                }
                            )
                    
                    # Отправляем уведомление администратору о комментарии
                    c.execute('''SELECT name, phone, username FROM contacts WHERE id = ?''', (contact_id,))
                    user_info = c.fetchone()
                    user_name = user_info[0] if user_info else f"Пользователь {user_id}"
                    
                    admin_message = (
                        f"💬 *Пользователь оставил комментарий*\n\n"
                        f"👤 Пользователь: {user_name}\n"
                        f"🆔 ID документа: {doc_id}\n"
                        f"💬 Комментарий: \"{comment_text}\"\n\n"
                        f"⏰ Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
                        f"📋 *Статус:* Комментарий сохранен, ожидается решение пользователя"
                    )
                    
                    try:
                        await context.bot.send_message(
                            chat_id=DEVELOPER_ADMIN_ID,
                            text=admin_message,
                            parse_mode='Markdown'
                        )
                    except Exception as admin_error:
                        logger.error(f"❌ Ошибка отправки уведомления админу: {admin_error}")
                    
                break
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retry_count - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error(f"❌ Ошибка сохранения комментария: {e}")
                    lang = self.get_user_language(user_id)
                    await update.message.reply_text("❌ Ошибка сохранения комментария")
                    return
        
        # Очищаем контекст
        del context.user_data['waiting_comment']
        
        # Подтверждаем сохранение
        lang = self.get_user_language(user_id)
        confirmation_message = Translations.get('comment_saved', lang)
        
        # Получаем информацию о документе
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''SELECT file_name FROM document_files 
                        WHERE doc_id = ? ORDER BY file_order LIMIT 1''', (doc_id,))
                doc_info = c.fetchone()
                doc_name = doc_info[0] if doc_info else "Документ"
        except:
            doc_name = "Документ"
        
        # Создаем кнопки для возврата к документу
        keyboard_buttons = [
            [
                InlineKeyboardButton("✅ Согласен", callback_data=f"approve_{doc_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{doc_id}")
            ],
            [
                InlineKeyboardButton("💬 Изменить комментарий", callback_data=f"comment_{doc_id}"),
                InlineKeyboardButton("👥 Кто еще получил", callback_data=f"view_recipients_{doc_id}")
            ],
            [
                InlineKeyboardButton("⬅️ Назад к документу", callback_data=f"open_doc_{doc_id}")
            ]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        # Отправляем подтверждение
        await update.message.reply_text(
            f"{confirmation_message}\n\n"
            f"📄 *Документ:* {doc_name}\n"
            f"💬 *Ваш комментарий:* {comment_text[:100]}{'...' if len(comment_text) > 100 else ''}\n\n"
            f"Теперь вы можете принять решение по документу:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def handle_comment_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена комментария"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        doc_id = query.data.replace('comment_cancel_', '')
        lang = self.get_user_language(user_id)
        
        # Удаляем ожидание комментария из контекста
        comment_key = f'waiting_comment_{doc_id}'
        if comment_key in context.user_data:
            if context.user_data[comment_key]['user_id'] == user_id:
                del context.user_data[comment_key]
        
        # Проверяем, есть ли уже комментарий от пользователя
        retry_count = 3
        retry_delay = 1
        
        for attempt in range(retry_count):
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # Проверяем, есть ли уже комментарий от пользователя
                    c.execute('''SELECT r.comment 
                               FROM recipients r
                               JOIN contacts c ON r.contact_id = c.id
                               WHERE r.doc_id = ? AND c.telegram_id = ?''',
                             (doc_id, user_id))
                    
                    comment_result = c.fetchone()
                    has_comment = comment_result and comment_result[0]
                    
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retry_count - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error(f"❌ Ошибка базы данных: {e}")
                    return
        
        # Создаем кнопки в зависимости от наличия комментария
        if has_comment:
            comment_button_text = Translations.get('change_comment', lang)
        else:
            comment_button_text = Translations.get('leave_comment', lang)
        
        keyboard_buttons = [
            [
                InlineKeyboardButton("✅ Согласен", callback_data=f"approve_{doc_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{doc_id}")
            ],
            [
                InlineKeyboardButton(comment_button_text, callback_data=f"comment_{doc_id}"),
                InlineKeyboardButton(Translations.get('view_recipients', lang), callback_data=f"view_recipients_{doc_id}")
            ],
            [
                InlineKeyboardButton(Translations.get('view_instructions', lang), callback_data="user_instructions")
            ]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await query.message.edit_text(
            f"❌ *{Translations.get('comment_cancel', lang)}*\n\n"
            f"Вы можете добавить комментарий позже, нажав кнопку '{comment_button_text}'.",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def handle_view_recipients(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает список всех получателей документа"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        doc_id = query.data.replace('view_recipients_', '')
        lang = self.get_user_language(user_id)
        
        # Получаем список всех получателей документа
        retry_count = 3
        retry_delay = 1
        
        for attempt in range(retry_count):
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # Получаем информацию о получателях
                    c.execute('''SELECT c.name, c.phone, c.username, r.status
                               FROM recipients r
                               LEFT JOIN contacts c ON r.contact_id = c.id
                               WHERE r.doc_id = ?
                               ORDER BY c.name, c.phone, c.username''', (doc_id,))
                    
                    recipients = c.fetchall()
                    
                    # Получаем текущего пользователя
                    c.execute('''SELECT phone, username, name FROM contacts WHERE telegram_id = ?''',
                             (user_id,))
                    current_user = c.fetchone()
                    
                    # Получаем информацию о документе
                    c.execute('''SELECT file_name FROM document_files WHERE doc_id = ? ORDER BY file_order''', 
                             (doc_id,))
                    files = c.fetchall()
                
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retry_count - 1:
                    logger.warning(f"База заблокирована при получении получателей, попытка {attempt + 1}")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error(f"❌ Ошибка получения получателей: {e}")
                    await query.answer("❌ Ошибка базы данных", show_alert=True)
                    return
        
        # Формируем сообщение
        if len(files) == 1:
            file_name = files[0][0]
            message = Translations.get('recipients_list', lang)
            message += f"📄 **{file_name}**\n\n"
        else:
            message = Translations.get('recipients_list', lang)
            message += f"📚 **{Translations.get('documents', lang)}: {len(files)}**\n\n"
        
        if recipients:
            # Считаем статистику
            total = len(recipients)
            approved = sum(1 for r in recipients if r[3] == 'approved')
            rejected = sum(1 for r in recipients if r[3] == 'rejected')
            pending = total - approved - rejected
            
            message += f"📊 *{Translations.get('statistics', lang)}:*\n"
            message += f"👥 {Translations.get('users', lang)}: {total}\n"
            message += f"✅ {Translations.get('recipient_status_approved', lang)}: {approved}\n"
            message += f"❌ {Translations.get('recipient_status_rejected', lang)}: {rejected}\n"
            message += f"⏳ {Translations.get('recipient_status_pending', lang)}: {pending}\n\n"
            
            message += f"📋 *{Translations.get('recipients_list', lang)}*\n\n"
            
            for i, (name, phone, username, status) in enumerate(recipients, 1):
                # Определяем отображаемое имя
                display_name = name or f"@{username}" or phone or f"{Translations.get('recipient_item', lang).format(index=i, name='Получатель', status='')}"
                
                # Определяем статус
                if status == 'approved':
                    status_text = Translations.get('recipient_status_approved', lang)
                elif status == 'rejected':
                    status_text = Translations.get('recipient_status_rejected', lang)
                else:
                    status_text = Translations.get('recipient_status_pending', lang)
                
                # Добавляем информацию о контакте
                contact_info = ""
                if name and (phone or username):
                    contact_info = f" ({phone or f'@{username}'})"
                elif phone:
                    contact_info = f" ({phone})"
                elif username:
                    contact_info = f" (@{username})"
                
                message += Translations.get('recipient_item', lang).format(
                    index=i, 
                    name=f"**{display_name}**{contact_info}",
                    status=status_text
                )
                
                # Если это текущий пользователь, отмечаем его
                if current_user:
                    current_phone, current_username, current_name = current_user
                    if (phone == current_phone) or (username == current_username) or (name == current_name):
                        message += f"   👈 **{Translations.get('your_id', lang).split(':')[0]}**\n"
                
                message += "\n"
        else:
            message += "📭 Получатели не найдены\n\n"
        
        message += "💡 *Совет:*\n"
        message += "Вы можете добавить комментарий к документу или оставить свое решение"
        
        # Кнопка назад
        keyboard_buttons = [
            [InlineKeyboardButton(Translations.get('back_to_document', lang), callback_data=f"back_to_doc_{doc_id}")]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await query.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def show_user_instructions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает инструкцию для пользователя"""
        query = update.callback_query
        if query:
            await query.answer()
        
        user_id = update.effective_user.id
        lang = self.get_user_language(user_id)
        
        instructions_title = Translations.get('instructions_title', lang)
        instructions_text = Translations.get('instructions_text', lang)
        
        # Заменяем @admin_username на реальный username администратора
        if self.bot_username:
            admin_mention = f"@{self.bot_username}"
            instructions_text = instructions_text.replace("@admin_username", admin_mention)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="user_back_to_menu")]
        ])
        
        if query:
            await query.message.edit_text(
                f"{instructions_title}\n\n{instructions_text}",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"{instructions_title}\n\n{instructions_text}",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
    
    async def handle_back_to_doc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возврат к документу из списка получателей"""
        query = update.callback_query
        await query.answer()
        
        doc_id = query.data.replace('back_to_doc_', '')
        
        # Удаляем сообщение со списком получателей
        try:
            await query.message.delete()
        except:
            pass
        
        # Получаем информацию о документе для обновления кнопок
        retry_count = 3
        retry_delay = 1
        
        for attempt in range(retry_count):
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # Проверяем, есть ли уже комментарий от пользователя
                    user_id = query.from_user.id
                    c.execute('''SELECT r.comment 
                               FROM recipients r
                               JOIN contacts c ON r.contact_id = c.id
                               WHERE r.doc_id = ? AND c.telegram_id = ?''',
                             (doc_id, user_id))
                    
                    comment_result = c.fetchone()
                    has_comment = comment_result and comment_result[0]
                    
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retry_count - 1:
                    logger.warning(f"База заблокирована, попытка {attempt + 1}")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error(f"❌ Ошибка базы данных: {e}")
                    return
        
        lang = self.get_user_language(user_id)
        
        # Создаем кнопки в зависимости от наличия комментария
        if has_comment:
            comment_button_text = Translations.get('change_comment', lang)
        else:
            comment_button_text = Translations.get('leave_comment', lang)
        
        keyboard_buttons = [
            [
                InlineKeyboardButton("✅ Согласен", callback_data=f"approve_{doc_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{doc_id}")
            ],
            [
                InlineKeyboardButton(comment_button_text, callback_data=f"comment_{doc_id}"),
                InlineKeyboardButton(Translations.get('view_recipients', lang), callback_data=f"view_recipients_{doc_id}")
            ],
            [
                InlineKeyboardButton(Translations.get('view_instructions', lang), callback_data="user_instructions")
            ]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        # Отправляем уведомление о возврате
        await query.answer("Возврат к документу")
    
    async def handle_document_link(self, update: Update, start_param: str, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ссылки с документом - пользователь перешёл по приглашению"""
        try:
            if start_param.startswith('doc_'):
                doc_id = start_param.replace('doc_', '')
                
                # ===== 1. ПОЛУЧАЕМ ДАННЫЕ ПОЛЬЗОВАТЕЛЯ =====
                username = update.effective_user.username
                first_name = update.effective_user.first_name
                last_name = update.effective_user.last_name
                name = f"{first_name or ''} {last_name or ''}".strip()
                
                logger.info(f"🔍 Пользователь {user_id} перешёл по ссылке на документ {doc_id}")
                
                # ===== 2. ПРОВЕРЯЕМ СУЩЕСТВОВАНИЕ ДОКУМЕНТА =====
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # Проверяем существование документа
                    c.execute('SELECT id FROM documents WHERE id = ?', (doc_id,))
                    if not c.fetchone():
                        logger.error(f"❌ Документ {doc_id} не найден в БД")
                        await update.message.reply_text(
                            "❌ Документ не найден или срок действия ссылки истек",
                            reply_markup=self.get_reply_keyboard(user_id)
                        )
                        return
                    
                    # ===== 3. ИЩЕМ ВСЕХ ПОЛУЧАТЕЛЕЙ ДОКУМЕНТА =====
                    c.execute('''
                        SELECT c.id, c.phone, c.username, c.telegram_id, r.status
                        FROM recipients r
                        LEFT JOIN contacts c ON r.contact_id = c.id
                        WHERE r.doc_id = ?
                    ''', (doc_id,))
                    
                    doc_recipients = c.fetchall()
                    
                    # ===== 4. ПРОВЕРЯЕМ, НЕ ОТВЕТИЛ ЛИ УЖЕ ЭТОТ ПОЛЬЗОВАТЕЛЬ =====
                    # Проверяем, есть ли контакт с таким telegram_id среди получателей
                    user_already_responded = False
                    target_phone = None
                    target_username = None
                    found_contact_id = None
                    
                    for recipient in doc_recipients:
                        contact_id, phone, doc_username, existing_telegram_id, recipient_status = recipient
                        
                        # Если этот пользователь уже ответил на документ
                        if existing_telegram_id == user_id and recipient_status in ['approved', 'rejected']:
                            user_already_responded = True
                            break
                        
                        # Если нашли контакт, который ещё не активирован и подходит для этого пользователя
                        if existing_telegram_id is None:
                            if phone:
                                target_phone = phone
                            if doc_username:
                                target_username = doc_username
                            if found_contact_id is None:
                                found_contact_id = contact_id
                    
                    # Если пользователь уже ответил на этот документ
                    if user_already_responded:
                        await update.message.reply_text(
                            "✅ Вы уже обработали этот документ",
                            reply_markup=self.get_reply_keyboard(user_id)
                        )
                        return
                    
                    # ===== 5. ✅ АКТИВИРУЕМ ПОЛЬЗОВАТЕЛЯ =====
                    # Всегда активируем пользователя, даже если не нашли целевой контакт
                    success = await self.activate_user(
                        user_id=user_id,
                        phone=target_phone,
                        username=username,
                        user_name=name
                    )
                    
                    if not success:
                        logger.error(f"❌ Ошибка активации пользователя {user_id}")
                        await update.message.reply_text(
                            "❌ Ошибка активации. Обратитесь к администратору.",
                            reply_markup=self.get_reply_keyboard(user_id)
                        )
                        return
                    
                    # ===== 6. ПОЛУЧАЕМ ID КОНТАКТА ПОЛЬЗОВАТЕЛЯ =====
                    c.execute('SELECT id FROM contacts WHERE telegram_id = ?', (user_id,))
                    contact_result = c.fetchone()
                    
                    if not contact_result:
                        logger.error(f"❌ Контакт не найден для пользователя {user_id}")
                        await update.message.reply_text(
                            "❌ Ошибка активации. Обратитесь к администратору.",
                            reply_markup=self.get_reply_keyboard(user_id)
                        )
                        return
                    
                    contact_id = contact_result[0]
                    
                    # ===== 7. СВЯЗЫВАЕМ ПОЛЬЗОВАТЕЛЯ С ДОКУМЕНТОМ =====
                    # Проверяем, есть ли уже запись для этого пользователя и документа
                    c.execute('''
                        SELECT id, status FROM recipients 
                        WHERE doc_id = ? AND contact_id = ?
                    ''', (doc_id, contact_id))
                    
                    existing_recipient = c.fetchone()
                    
                    if existing_recipient:
                        recipient_id, recipient_status = existing_recipient
                        
                        if recipient_status in ['approved', 'rejected']:
                            await update.message.reply_text(
                                "✅ Вы уже обработали этот документ",
                                reply_markup=self.get_reply_keyboard(user_id)
                            )
                            return
                        
                        # Обновляем статус на ожидание
                        c.execute('''
                            UPDATE recipients 
                            SET status = 'pending', notification_sent = 0
                            WHERE id = ?
                        ''', (recipient_id,))
                        
                        logger.info(f"📝 Обновлен существующий получатель для документа {doc_id}")
                        
                    else:
                        # Создаем новую запись получателя
                        identifier_value = target_phone or target_username or f"tg_{user_id}"
                        identifier_type = 'phone' if target_phone else ('username' if target_username else 'telegram_id')
                        
                        c.execute('''
                            INSERT INTO recipients 
                            (doc_id, contact_id, identifier_type, identifier_value, status)
                            VALUES (?, ?, ?, ?, 'pending')
                        ''', (doc_id, contact_id, identifier_type, identifier_value))
                        
                        logger.info(f"✅ Создан новый получатель для документа {doc_id}")
                    
                    conn.commit()
                    
                    # ===== 8. ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ О ДОСТАВКЕ АДМИНУ =====
                    delivery_message = f"✅ *Документ доставлен*\n\n"
                    delivery_message += f"👤 *Пользователь:* {self.escape_markdown(name or f'@{username}' or f'ID:{user_id}')}\n"
                    delivery_message += f"🆔 *Telegram ID:* {user_id}\n"
                    delivery_message += f"📄 *Документ ID:* {doc_id}\n"
                    delivery_message += f"⏰ *Время:* {datetime.now().strftime('%H:%M %d.%m.%Y')}"
                    
                    await context.bot.send_message(
                        chat_id=DEVELOPER_ADMIN_ID,
                        text=delivery_message,
                        parse_mode='Markdown'
                    )
                    
                    # ===== 9. ПОЛУЧАЕМ ФАЙЛЫ ДОКУМЕНТА =====
                    c.execute('''
                        SELECT file_id, file_name FROM document_files 
                        WHERE doc_id = ? ORDER BY file_order
                    ''', (doc_id,))
                    
                    files = c.fetchall()
                    
                    if not files:
                        await update.message.reply_text(
                            "❌ Файлы документа не найдены",
                            reply_markup=self.get_reply_keyboard(user_id)
                        )
                        return
                    
                # ===== 10. ОТПРАВЛЯЕМ ДОКУМЕНТЫ ПОЛЬЗОВАТЕЛЮ =====
                first_file_id, first_file_name = files[0]
                
                # Экранируем имя файла
                safe_file_name = self.escape_markdown(first_file_name)
                
                # Кнопки для документа
                keyboard_buttons = [
                    [
                        InlineKeyboardButton("✅ Согласен", callback_data=f"approve_{doc_id}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{doc_id}")
                    ],
                    [
                        InlineKeyboardButton("💬 Комментарий", callback_data=f"comment_{doc_id}"),
                        InlineKeyboardButton("👥 Кто еще получил", callback_data=f"view_recipients_{doc_id}")
                    ]
                ]
                keyboard = InlineKeyboardMarkup(keyboard_buttons)
                
                # Приветствие
                welcome_message = (
                    f"👋 *Добро пожаловать в систему DocFlow!*\n\n"
                    f"✅ *Ваш аккаунт активирован!*\n\n"
                    f"📋 *Сейчас вы получите документ для согласования.*"
                )
                
                await update.message.reply_text(
                    welcome_message,
                    parse_mode='Markdown',
                    reply_markup=self.get_reply_keyboard(user_id)
                )
                
                await asyncio.sleep(0.5)
                
                # Документ
                await context.bot.send_document(
                    chat_id=user_id,
                    document=first_file_id,
                    caption=(
                        f"📄 *Документ для согласования*\n\n"
                        f"**Название:** {safe_file_name}\n"
                        f"{f'📚 Всего файлов: {len(files)}' if len(files) > 1 else ''}\n\n"
                        f"👇 *Используйте кнопки ниже для согласования:*"
                    ),
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                
                # Остальные документы
                for i in range(1, len(files)):
                    file_id, file_name = files[i]
                    safe_name = self.escape_markdown(file_name)
                    await context.bot.send_document(
                        chat_id=user_id,
                        document=file_id,
                        caption=f"📄 *Документ {i+1}:* {safe_name}",
                        parse_mode='Markdown'
                    )
                
                logger.info(f"✅ Документ {doc_id} успешно отправлен пользователю {user_id}")
                
            elif start_param.startswith('phone_'):
                # ===== ЧИСТАЯ АКТИВАЦИЯ ПО ТЕЛЕФОНУ =====
                phone = start_param.replace('phone_', '')
                
                success = await self.activate_user(
                    user_id=user_id,
                    phone=phone,
                    username=update.effective_user.username,
                    user_name=f"{update.effective_user.first_name or ''} {update.effective_user.last_name or ''}".strip()
                )
                
                if success:
                    await update.message.reply_text(
                        f"👋 *Добро пожаловать в DocFlow!*\n\n"
                        f"✅ *Ваш аккаунт активирован!*\n\n"
                        f"📄 Если у вас есть ожидающие документы, они придут автоматически.",
                        parse_mode='Markdown',
                        reply_markup=self.get_reply_keyboard(user_id)
                    )
                    
                    await self.send_pending_documents_to_user(user_id, context)
                else:
                    await update.message.reply_text(
                        "❌ Не удалось активировать аккаунт.",
                        reply_markup=self.get_reply_keyboard(user_id)
                    )
        
        except Exception as e:
            logger.error(f"❌ Ошибка обработки ссылки: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Ошибка обработки. Обратитесь к администратору.",
                reply_markup=self.get_reply_keyboard(user_id)
            )
    
    async def handle_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка согласования документа"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        doc_id = query.data.split('_')[1]
        
        retry_count = 3
        retry_delay = 1
        
        for attempt in range(retry_count):
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # ===== 1. ПОЛУЧАЕМ КОММЕНТАРИЙ =====
                    c.execute('''SELECT r.comment 
                            FROM recipients r
                            JOIN contacts c ON r.contact_id = c.id
                            WHERE r.doc_id = ? AND c.telegram_id = ?''',
                            (doc_id, user_id))
                    
                    comment_result = c.fetchone()
                    user_comment = comment_result[0] if comment_result else None
                    
                    # ===== 2. ОБНОВЛЯЕМ СТАТУС =====
                    c.execute('''UPDATE recipients 
                            SET status='approved', 
                                response_time=CURRENT_TIMESTAMP,
                                comment_only=FALSE
                            WHERE doc_id=? AND contact_id IN 
                            (SELECT id FROM contacts WHERE telegram_id=?)''',
                            (doc_id, user_id))
                    
                    # ===== 3. ПОЛУЧАЕМ ИНФОРМАЦИЮ О ПОЛЬЗОВАТЕЛЕ =====
                    c.execute('''SELECT phone, username, name FROM contacts 
                            WHERE telegram_id = ?''', (user_id,))
                    user_info = c.fetchone()
                    
                    # ===== 4. ПОЛУЧАЕМ СТАТИСТИКУ ПО ДОКУМЕНТУ =====
                    c.execute('''SELECT 
                            COUNT(*) as total_recipients,
                            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                            SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
                            FROM recipients 
                            WHERE doc_id = ?''', (doc_id,))
                    
                    doc_stats = c.fetchone()
                    total_recipients, approved, rejected, pending = doc_stats
                    
                    # ===== 5. ПОЛУЧАЕМ ИНФОРМАЦИЮ О ДОКУМЕНТЕ =====
                    c.execute('''SELECT file_name FROM document_files 
                            WHERE doc_id = ? ORDER BY file_order LIMIT 1''', (doc_id,))
                    doc_file = c.fetchone()
                    doc_name = doc_file[0] if doc_file else "Документ"
                    
                    conn.commit()
                break
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retry_count - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error(f"❌ Ошибка согласования: {e}")
                    await query.answer("❌ Ошибка базы данных", show_alert=True)
                    return
        
        # Удаляем напоминание из системы
        self.reminder_manager.remove_reminder(doc_id, user_id)
        
        # Формируем информацию о пользователе
        phone, username, name = user_info if user_info else (None, None, None)
        user_display = name or f"@{username}" if username else phone or f"ID:{user_id}"
        
        # Экранируем имя документа для Markdown
        safe_doc_name = self.escape_markdown(doc_name)
        
        # ===== ОБНОВЛЯЕМ СООБЩЕНИЕ ДЛЯ ПОЛЬЗОВАТЕЛЯ =====
        user_message = f"✅ *Вы согласовали документ*\n\n"
        user_message += f"📄 Документ: {safe_doc_name}\n"
        
        if user_comment:
            safe_comment = self.escape_markdown(user_comment)
            user_message += f"💬 Ваш комментарий: {safe_comment}\n\n"
        
        user_message += f"🎉 *Спасибо!*"
        
        keyboard_buttons = [
            [InlineKeyboardButton("📄 Мои документы", callback_data="user_documents")],
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="user_back_to_menu")]
        ]
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        try:
            if query.message.caption:
                await query.edit_message_caption(
                    caption=user_message,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            else:
                await query.message.edit_text(
                    user_message,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"❌ Ошибка обновления сообщения: {e}")
        
        # ===== ПРОВЕРКА И ОТПРАВКА ФИНАЛЬНОГО ОТЧЕТА =====
        try:
            # Проверяем, все ли ответили на документ
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
                            FROM recipients WHERE doc_id = ?''', (doc_id,))
                
                stats = c.fetchone()
                if stats:
                    total, pending = stats
                    logger.info(f"📊 Проверка статуса документа {doc_id}: всего={total}, ожидает={pending}")
                    
                    if pending == 0 and total > 0:
                        # Проверяем, не отправляли ли уже финальный отчет
                        c.execute('SELECT final_report_sent FROM documents WHERE id = ?', (doc_id,))
                        result = c.fetchone()
                        
                        if not result or result[0] == 0:
                            # Все ответили - отправляем финальный отчет
                            logger.info(f"✅ Все получатели ответили на документ {doc_id}, отправляю финальный отчет")
                            await asyncio.sleep(2)  # Небольшая задержка
                            await self.send_final_report_to_admin(doc_id)
        except Exception as e:
            logger.error(f"❌ Ошибка проверки статуса документа после approve: {e}")

    async def send_final_report_with_comments(self, context, doc_id: str):
        """Отправляет финальный отчет по документу со всеми комментариями"""
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем информацию о документе
                c.execute('''SELECT d.created, 
                            GROUP_CONCAT(df.file_name, '\n') as files
                            FROM documents d
                            LEFT JOIN document_files df ON d.id = df.doc_id
                            WHERE d.id = ?''', (doc_id,))
                
                doc_info = c.fetchone()
                if not doc_info:
                    return
                
                created, files = doc_info
                created_dt = datetime.strptime(created, '%Y-%m-%d %H:%M:%S')
                created_str = created_dt.strftime('%d.%m.%Y %H:%M:%S')
                
                # Получаем всех получателей с комментариями
                c.execute('''SELECT c.name, c.phone, c.username, 
                            r.status, r.comment, r.response_time,
                            r.sent_via
                            FROM recipients r
                            LEFT JOIN contacts c ON r.contact_id = c.id
                            WHERE r.doc_id = ?
                            ORDER BY 
                                CASE r.status 
                                    WHEN 'approved' THEN 1
                                    WHEN 'rejected' THEN 2
                                    ELSE 3
                                END,
                                r.response_time''', (doc_id,))
                
                recipients = c.fetchall()
                
                # Получаем статистику
                c.execute('''SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                            SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
                            FROM recipients WHERE doc_id = ?''', (doc_id,))
                
                stats = c.fetchone()
                total, approved, rejected, pending = stats if stats else (0, 0, 0, 0)
                
            # ===== ФОРМИРУЕМ ФИНАЛЬНЫЙ ОТЧЕТ =====
            report = "📊 *ФИНАЛЬНЫЙ ОТЧЕТ ПО ДОКУМЕНТУ*\n\n"
            report += f"🆔 *ID документа:* `{doc_id}`\n"
            report += f"📅 *Дата создания:* {created_str}\n\n"
            
            if files:
                file_list = files.split('\n')
                report += f"📄 *Файлы ({len(file_list)}):*\n"
                for i, file_name in enumerate(file_list, 1):
                    report += f"{i}. {file_name}\n"
                report += "\n"
            
            report += "📈 *СТАТИСТИКА СОГЛАСОВАНИЯ:*\n"
            report += "─" * 40 + "\n\n"
            
            report += f"👥 *Всего получателей:* {total}\n"
            report += f"✅ *Согласовано:* {approved}\n"
            report += f"❌ *Отклонено:* {rejected}\n"
            report += f"⏳ *Ожидает:* {pending}\n\n"
            
            if total > 0:
                completion_rate = ((approved or 0) + (rejected or 0)) / total * 100
                if (approved or 0) + (rejected or 0) > 0:
                    approval_rate = (approved or 0) / ((approved or 0) + (rejected or 0)) * 100
                else:
                    approval_rate = 0
                
                report += f"📊 *ЭФФЕКТИВНОСТЬ:*\n"
                report += f"• Завершено согласование: *{completion_rate:.1f}%*\n"
                report += f"• Процент согласования: *{approval_rate:.1f}%*\n\n"
            
            report += "👥 *ДЕТАЛЬНЫЙ СПИСОК ПОЛУЧАТЕЛЕЙ:*\n"
            report += "─" * 40 + "\n\n"
            
            if recipients:
                for i, (name, phone, username, status, comment, response_time, sent_via) in enumerate(recipients, 1):
                    # Имя получателя
                    if name:
                        recipient_name = name
                    elif phone:
                        recipient_name = phone
                    elif username:
                        recipient_name = f"@{username}"
                    else:
                        recipient_name = f"Получатель {i}"
                    
                    report += f"**{i}. {recipient_name}**\n"
                    
                    # Контактная информация
                    contact_info = []
                    if phone:
                        contact_info.append(f"📱 {phone}")
                    if username:
                        contact_info.append(f"👤 @{username}")
                    if contact_info:
                        report += f"   {', '.join(contact_info)}\n"
                    
                    # Статус
                    if status == 'approved':
                        status_display = "✅ *Согласовано*"
                    elif status == 'rejected':
                        status_display = "❌ *Отклонено*"
                    else:
                        status_display = "⏳ *Ожидает*"
                    
                    report += f"   📊 Статус: {status_display}"
                    if sent_via:
                        report += f" ({sent_via})"
                    report += "\n"
                    
                    # ===== ВАЖНО: КОММЕНТАРИЙ В ФИНАЛЬНОМ ОТЧЕТЕ =====
                    if comment:
                        report += f"   💬 *Комментарий:* {comment}\n"
                    
                    # Время ответа
                    if response_time:
                        try:
                            resp_dt = datetime.strptime(response_time, '%Y-%m-%d %H:%M:%S')
                            resp_str = resp_dt.strftime('%d.%m.%Y %H:%M')
                            report += f"   🕐 Время ответа: {resp_str}\n"
                        except:
                            pass
                    
                    report += "\n"
            
            report += "─" * 40 + "\n"
            report += f"📋 *Отчет сгенерирован:* {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
            report += "─" * 40
            
            # Кнопки для отчета
            keyboard_buttons = [
                [
                    InlineKeyboardButton("📄 TXT отчет", callback_data=f"export_txt_{doc_id}"),
                    InlineKeyboardButton("📊 Статистика", callback_data=f"export_stats_{doc_id}")
                ],
                [
                    InlineKeyboardButton("📋 Все отчеты", callback_data="menu_reports"),
                    InlineKeyboardButton("📤 Новый документ", callback_data="menu_send_doc")
                ]
            ]
            keyboard = InlineKeyboardMarkup(keyboard_buttons)
            
            # Отправляем финальный отчет
            await context.bot.send_message(
                chat_id=DEVELOPER_ADMIN_ID,
                text=report,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
            logger.info(f"📊 Финальный отчет отправлен админу по документу {doc_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки финального отчета: {e}")
    
    async def handle_reject(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка отклонения документа"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        doc_id = query.data.split('_')[1]
        
        retry_count = 3
        retry_delay = 1
        
        for attempt in range(retry_count):
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # ===== 1. ПОЛУЧАЕМ КОММЕНТАРИЙ =====
                    c.execute('''SELECT r.comment 
                            FROM recipients r
                            JOIN contacts c ON r.contact_id = c.id
                            WHERE r.doc_id = ? AND c.telegram_id = ?''',
                            (doc_id, user_id))
                    
                    comment_result = c.fetchone()
                    user_comment = comment_result[0] if comment_result else None
                    
                    # ===== 2. ОБНОВЛЯЕМ СТАТУС =====
                    c.execute('''UPDATE recipients 
                            SET status='rejected', 
                                response_time=CURRENT_TIMESTAMP,
                                comment_only=FALSE
                            WHERE doc_id=? AND contact_id IN 
                            (SELECT id FROM contacts WHERE telegram_id=?)''',
                            (doc_id, user_id))
                    
                    # ===== 3. ПОЛУЧАЕМ ИНФОРМАЦИЮ О ПОЛЬЗОВАТЕЛЕ =====
                    c.execute('''SELECT phone, username, name FROM contacts 
                            WHERE telegram_id = ?''', (user_id,))
                    user_info = c.fetchone()
                    
                    # ===== 4. ПОЛУЧАЕМ СТАТИСТИКУ ПО ДОКУМЕНТУ =====
                    c.execute('''SELECT 
                            COUNT(*) as total_recipients,
                            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                            SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
                            FROM recipients 
                            WHERE doc_id = ?''', (doc_id,))
                    
                    doc_stats = c.fetchone()
                    total_recipients, approved, rejected, pending = doc_stats
                    
                    # ===== 5. ПОЛУЧАЕМ ИНФОРМАЦИЮ О ДОКУМЕНТЕ =====
                    c.execute('''SELECT file_name FROM document_files 
                            WHERE doc_id = ? ORDER BY file_order LIMIT 1''', (doc_id,))
                    doc_file = c.fetchone()
                    doc_name = doc_file[0] if doc_file else "Документ"
                    
                    conn.commit()
                break
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retry_count - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error(f"❌ Ошибка отклонения: {e}")
                    await query.answer("❌ Ошибка базы данных", show_alert=True)
                    return
        
        # Удаляем напоминание из системы
        self.reminder_manager.remove_reminder(doc_id, user_id)
        
        # Формируем информацию о пользователе
        phone, username, name = user_info if user_info else (None, None, None)
        user_display = name or f"@{username}" if username else phone or f"ID:{user_id}"
        
        # ===== ОБНОВЛЯЕМ СООБЩЕНИЕ ДЛЯ ПОЛЬЗОВАТЕЛЯ =====
        user_message = f"❌ *Вы отклонили документ*\n\n"
        user_message += f"📄 Документ: {doc_name}\n"
        
        if user_comment:
            user_message += f"💬 Ваш комментарий: {user_comment}\n\n"
        
        user_message += f"📝 *Спасибо за решение!*"
        
        keyboard_buttons = [
            [InlineKeyboardButton("📄 Мои документы", callback_data="user_documents")],
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="user_back_to_menu")]
        ]
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        try:
            if query.message.caption:
                await query.edit_message_caption(
                    caption=user_message,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
            else:
                await query.message.edit_text(
                    user_message,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"❌ Ошибка обновления сообщения: {e}")
        
        # ===== ДОБАВЛЕНО: ПРОВЕРКА И ОТПРАВКА ФИНАЛЬНОГО ОТЧЕТА =====
        try:
            # Проверяем, все ли ответили на документ
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
                            FROM recipients WHERE doc_id = ?''', (doc_id,))
                
                stats = c.fetchone()
                if stats:
                    total, pending = stats
                    logger.info(f"📊 Проверка статуса документа {doc_id}: всего={total}, ожидает={pending}")
                    
                    if pending == 0 and total > 0:
                        # Все ответили - отправляем финальный отчет
                        logger.info(f"✅ Все получатели ответили на документ {doc_id}, отправляю финальный отчет")
                        await asyncio.sleep(1)  # Небольшая задержка
                        await self.send_final_report_to_admin(doc_id)
        except Exception as e:
            logger.error(f"❌ Ошибка проверки статуса документа после reject: {e}")
    
    async def update_comment_only_status(self, doc_id: str, user_id: int, comment_text: str):
        """Обновляет статус 'только комментарий' в базе данных"""
        retry_count = 3
        retry_delay = 1
        
        for attempt in range(retry_count):
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # Обновляем статус в таблице recipients
                    c.execute('''UPDATE recipients 
                               SET comment_only = TRUE, response_time = CURRENT_TIMESTAMP
                               WHERE doc_id = ? AND contact_id IN 
                               (SELECT id FROM contacts WHERE telegram_id = ?)''',
                             (doc_id, user_id))
                    
                    # Обновляем в таблице comment_reminders
                    c.execute('''UPDATE comment_reminders 
                               SET final_reminder_sent = TRUE 
                               WHERE doc_id = ? AND user_id = ?''',
                             (doc_id, user_id))
                    
                    conn.commit()
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retry_count - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    logger.error(f"❌ Ошибка обновления статуса комментария: {e}")
                    return
    
    async def send_final_report(self, context, doc_id: str, file_names: List[str]):
        """Отправляет финальный отчет по документу"""
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем детальную информацию по получателям
                c.execute('''SELECT c.name, c.phone, c.username, 
                             r.status, r.comment, r.response_time,
                             r.sent_via, r.comment_only
                             FROM recipients r
                             LEFT JOIN contacts c ON r.contact_id = c.id
                             WHERE r.doc_id = ?
                             ORDER BY r.response_time DESC, r.status''', (doc_id,))
                
                recipients = c.fetchall()
                
                # Получаем статистику
                c.execute('''SELECT 
                             COUNT(*) as total_recipients,
                             SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                             SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                             SUM(CASE WHEN comment_only = 1 THEN 1 ELSE 0 END) as comment_only,
                             SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
                             FROM recipients 
                             WHERE doc_id = ?''', (doc_id,))
                
                stats = c.fetchone()
                total, approved, rejected, comment_only, pending = stats if stats else (0, 0, 0, 0, 0)
        except sqlite3.OperationalError as e:
            logger.error(f"❌ Ошибка получения финального отчета: {e}")
            recipients = []
            total = approved = rejected = comment_only = pending = 0
        
        # Формируем отчет
        report = f"📊 ФИНАЛЬНЫЙ ОТЧЕТ ПО ДОКУМЕНТУ\n\n"
        report += f"🆔 ID: {doc_id}\n"
        
        if len(file_names) == 1:
            report += f"📄 Документ: {file_names[0]}\n"
        else:
            report += f"📚 Документов: {len(file_names)}\n"
            report += f"📋 Список:\n"
            for i, name in enumerate(file_names, 1):
                report += f"{i}. {name}\n"
            report += "\n"
        
        report += f"📅 Дата завершения: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        
        report += f"📊 ИТОГОВАЯ СТАТИСТИКА:\n"
        report += f"• Всего получателей: {total or 0}\n"
        report += f"• ✅ Согласовано: {approved or 0}\n"
        report += f"• ❌ Отклонено: {rejected or 0}\n"
        report += f"• 💬 Только комментарий: {comment_only or 0}\n"
        report += f"• ⏳ Ожидает: {pending or 0}\n\n"
        
        if approved or rejected or comment_only:
            completion_rate = ((approved or 0) + (rejected or 0) + (comment_only or 0)) / max(total, 1) * 100
            if (approved or 0) + (rejected or 0) > 0:
                approval_rate = (approved or 0) / max((approved or 0) + (rejected or 0), 1) * 100
            else:
                approval_rate = 0
            
            report += f"📈 ЭФФЕКТИВНОСТЬ:\n"
            report += f"• Завершено согласование: {completion_rate:.1f}%\n"
            report += f"• Процент согласования: {approval_rate:.1f}%\n\n"
        
        if recipients:
            report += f"👥 РЕЗУЛЬТАТЫ ПОЛУЧАТЕЛЕЙ:\n\n"
            
            for i, (name, phone, username, status, comment, response_time, sent_via, comment_only_flag) in enumerate(recipients, 1):
                report += f"{i}. "
                
                if name:
                    report += f"{name}\n"
                
                if phone:
                    report += f"   📱 {phone}\n"
                elif username:
                    report += f"   👤 @{username}\n"
                
                # Статус
                if comment_only_flag:
                    report += f"   💬 Только комментарий"
                elif status == 'approved':
                    report += f"   ✅ Согласовано"
                elif status == 'rejected':
                    report += f"   ❌ Отклонено"
                elif status == 'pending':
                    report += f"   ⏳ Ожидает"
                else:
                    report += f"   📨 Не отправлено"
                
                if sent_via:
                    report += f" ({sent_via})"
                
                report += "\n"
                
                if comment:
                    report += f"   💬 Комментарий: {comment}\n"
                
                if response_time:
                    resp_dt = datetime.strptime(response_time, '%Y-%m-%d %H:%M:%S')
                    resp_str = resp_dt.strftime('%d.%m.%Y %H:%M')
                    report += f"   🕐 Время ответа: {resp_str}\n"
                
                report += "\n"
        
        report += f"💡 Отчеты доступны в меню: '📊 Отчеты по документам'\n"
        report += f"📁 Форматы: PDF, TXT, Статистика\n"
        
        keyboard_buttons = [
            [
                InlineKeyboardButton("📄 PDF отчет", callback_data=f"export_pdf_{doc_id}"),
                InlineKeyboardButton("📝 TXT отчет", callback_data=f"export_txt_{doc_id}")
            ],
            [
                InlineKeyboardButton("📊 Статистика", callback_data=f"export_stats_{doc_id}"),
                InlineKeyboardButton("📋 Все отчеты", callback_data="menu_reports")
            ],
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await context.bot.send_message(
            chat_id=DEVELOPER_ADMIN_ID,
            text=report,
            reply_markup=keyboard
        )
    
    async def check_and_send_delivery_notifications(self, bot, results: List[Dict], doc_id: str):
        """Проверяет и отправляет уведомления о доставке с именами вместо телефонов"""
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Для каждого результата проверяем статус и отправляем уведомление
                for result in results:
                    if result.get('success'):
                        recipient = result.get('recipient', 'Неизвестный')
                        name = result.get('name')  # Получаем имя
                        telegram_id = result.get('telegram_id')
                        
                        # ===== ИСПОЛЬЗУЕМ ИМЯ ЕСЛИ ЕСТЬ =====
                        display_name = name if name else recipient
                        
                        if telegram_id:
                            # Проверяем, было ли уже отправлено уведомление
                            c.execute('''SELECT notification_sent FROM recipients 
                                    WHERE doc_id = ? AND contact_id IN 
                                    (SELECT id FROM contacts WHERE telegram_id = ?)''',
                                    (doc_id, telegram_id))
                            
                            notification_sent = c.fetchone()
                            
                            if not notification_sent or not notification_sent[0]:
                                # Отправляем уведомление
                                try:
                                    admin_message = f"✅ *Документ доставлен*\n\n"
                                    admin_message += f"👤 *Пользователь:* {display_name}\n"  # Используем имя
                                    admin_message += f"🆔 *Telegram ID:* {telegram_id}\n"
                                    admin_message += f"📄 *Документ ID:* {doc_id}\n"
                                    admin_message += f"⏰ *Время:* {datetime.now().strftime('%H:%M %d.%m.%Y')}"
                                    
                                    await bot.send_message(
                                        chat_id=DEVELOPER_ADMIN_ID,
                                        text=admin_message,
                                        parse_mode='Markdown'
                                    )
                                    
                                    # Отмечаем в базе, что уведомление отправлено
                                    c.execute('''UPDATE recipients SET notification_sent = 1 
                                            WHERE doc_id = ? AND contact_id IN 
                                            (SELECT id FROM contacts WHERE telegram_id = ?)''',
                                            (doc_id, telegram_id))
                                    
                                    logger.info(f"✅ Уведомление о доставке отправлено для {telegram_id}")
                                except Exception as e:
                                    logger.error(f"❌ Ошибка отправки уведомления: {e}")
                        else:
                            # Для неактивированных тоже отправляем уведомление с именем
                            try:
                                admin_message = f"📨 *Приглашение отправлено*\n\n"
                                admin_message += f"👤 *Получатель:* {display_name}\n"  # Используем имя
                                admin_message += f"📄 *Документ ID:* {doc_id}\n"
                                admin_message += f"⏰ *Время:* {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
                                admin_message += f"💡 *Статус:* Пользователь не активирован, ожидается переход по ссылке"
                                
                                await bot.send_message(
                                    chat_id=DEVELOPER_ADMIN_ID,
                                    text=admin_message,
                                    parse_mode='Markdown'
                                )
                            except Exception as e:
                                logger.error(f"❌ Ошибка отправки уведомления: {e}")
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке уведомлений: {e}")
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        user_id = update.effective_user.id
        
        # ✅ ВАЖНО: Сначала проверяем, ожидаем ли мы тему сообщения
        if user_id == DEVELOPER_ADMIN_ID and 'waiting_message_theme' in context.user_data:
            await self.handle_message_theme(update, context)
            return
        
        # ✅ Затем проверяем, ожидаем ли мы комментарий
        if 'commenting_doc_id' in context.user_data:
            await self.save_comment(update, context)
            return
        
        # Проверяем, является ли сообщение кнопкой Start
        try:
            lang = self.get_user_language(user_id)
            start_button_text = Translations.get('start_button', lang)
            
            if update.message.text == start_button_text:
                await self.handle_start_button(update, context)
                return
            
            # Если это администратор и есть ожидание получателей
            if user_id == DEVELOPER_ADMIN_ID and context.user_data.get('waiting_recipients'):
                await self.handle_recipients(update, context)
                return
            
            # Если это администратор и есть ожидание добавления контакта
            if user_id == DEVELOPER_ADMIN_ID and 'waiting_add_contact' in context.user_data:
                await self.handle_add_contact_input(update, context)
                return
            
            # Если это администратор и есть ожидание номера телефона
            if user_id == DEVELOPER_ADMIN_ID and context.user_data.get('waiting_admin_phone'):
                await self.handle_admin_phone_input(update, context)
                return
            
            # Если это обычный пользователь и сообщение не обработано
            if user_id != DEVELOPER_ADMIN_ID:
                first_name = update.effective_user.first_name
                await self.show_user_menu(update, first_name, context)
                return
            
            # Для администратора показываем главное меню
            await self.show_admin_menu(update, context)
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки текстового сообщения: {e}")
            if user_id == DEVELOPER_ADMIN_ID:
                await self.show_admin_menu(update, context)
            else:
                first_name = update.effective_user.first_name
                await self.show_user_menu(update, first_name, context)
    
    async def handle_all_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Универсальный обработчик всех callback-кнопок - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        query = update.callback_query
        
        try:
            # Сначала отвечаем на callback чтобы убрать часики
            await query.answer()
            
            data = query.data
            logger.info(f"📱 Callback получен: {data}")
            
            # Проверяем, является ли текущее сообщение документом
            is_document_message = query.message.document is not None
            
            # ===== ОБРАБОТЧИК ДЛЯ ДОБАВЛЕНИЯ КОНТАКТОВ =====
            if data == "add_phone":
                # Устанавливаем флаг ожидания добавления контакта по телефону
                context.user_data['waiting_add_contact'] = 'phone'
                
                # Клавиатура для возврата
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
                ])
                
                # Отправляем сообщение с инструкцией
                message_text = (
                    "📱 Добавление по телефону\n\n"
                    "Введите телефон и имя в формате:\n"
                    "<PHONE_NUMBER> Иван Иванов\n\n"
                    "📋 Поддерживаемые форматы телефонов:\n"
                    "<PHONE_NUMBER>\n"
                    "+7 <PHONE_NUMBER>\n"
                    "<PHONE_NUMBER>\n"
                    "<PHONE_NUMBER>\n\n"
                    "💡 Что произойдет:\n"
                    "• Контакт добавится в базу\n"
                    "• Бот попробует отправить приглашение автоматически\n"
                    "• Если автоматически не получится, приглашение будет сформировано для ручной отправки"
                )
                
                if is_document_message:
                    await query.message.reply_text(message_text, reply_markup=keyboard)
                else:
                    await query.message.edit_text(message_text, reply_markup=keyboard)
                return
            
            # ===== ОБРАБОТЧИК ДЛЯ ПРОПУСКА ТЕМЫ =====
            if data.startswith("skip_theme_"):
                await self.handle_skip_theme(update, context)
                return
            
            # ===== ОБРАБОТЧИК ДЛЯ ВЫБОРА КОНТАКТОВ =====
            if data.startswith("select_contacts_"):
                await self.show_contacts_selection(update, context)
                return
            
            # ===== ОБРАБОТЧИК ДЛЯ ПАГИНАЦИИ =====
            if data.startswith("page_"):
                await self.show_contacts_selection(update, context)
                return
            
            # ===== ОБРАБОТЧИК ДЛЯ ПЕРЕКЛЮЧЕНИЯ ВЫБОРА КОНТАКТА =====
            if data.startswith("tog_"):
                await self.handle_contact_selection(update, context)
                return
            
            # ===== ОБРАБОТЧИК ДЛЯ ОТПРАВКИ ВЫБРАННЫХ КОНТАКТОВ =====
            if data.startswith("send_selected_"):
                await self.handle_contact_selection(update, context)
                return
            
            # ===== ОБРАБОТЧИК ДЛЯ ВОЗВРАТА К РУЧНОМУ ВВОДУ =====
            if data.startswith("back_to_input_"):
                await self.handle_contact_selection(update, context)
                return
            
            # ===== ОБРАБОТЧИК ДЛЯ ОТМЕНЫ ВЫБОРА =====
            if data == "cancel_selection":
                await self.handle_contact_selection(update, context)
                return
            
            # ===== ОБРАБОТЧИК ДЛЯ КНОПКИ "НОП" =====
            if data == "noop":
                # Пустое действие
                return
            
            # ===== ОБРАБОТЧИКИ ДЛЯ ОТЧЕТОВ =====
            if data == "report_statistics":
                if is_document_message:
                    await self.export_statistics_report(update, context)
                else:
                    await self.export_statistics_report(update, context)
                return
            
            if data == "report_period":
                if is_document_message:
                    # Для сообщений с документами отправляем новое сообщение
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("📅 Сегодня", callback_data="period_today"),
                            InlineKeyboardButton("📅 Неделя", callback_data="period_week")
                        ],
                        [
                            InlineKeyboardButton("📅 Месяц", callback_data="period_month"),
                            InlineKeyboardButton("📅 Все время", callback_data="period_all")
                        ],
                        [InlineKeyboardButton("⬅️ Назад", callback_data="menu_reports")]
                    ])
                    
                    await query.message.reply_text(
                        "📅 ОТЧЕТ ЗА ПЕРИОД\n\n"
                        "Выберите период для отчета:",
                        reply_markup=keyboard
                    )
                else:
                    await self.show_period_report_menu(update, context)
                return
            
            if data == "report_users":
                if is_document_message:
                    await self.show_users_report(update, context)
                else:
                    await self.show_users_report(update, context)
                return
            
            if data == "report_document":
                if is_document_message:
                    await self.show_document_report_menu(update, context)
                else:
                    await self.show_document_report_menu(update, context)
                return
            
            if data.startswith("view_doc_report_"):
                await self.view_document_report(update, context)
                return
            
            if data.startswith("period_"):
                await self.handle_period_report(update, context)
                return
            
            if data.startswith("export_users_"):
                await self.export_users_report(update, context)
                return
            
            # ===== ОБРАБОТЧИК ДЛЯ ЭКСПОРТА =====
            if data.startswith("export_"):
                await self.handle_report_callback(update, context)
                return
            
            # ===== ОБРАБОТКА КОНТАКТОВ =====
            if data in ["contacts_phone", "contacts_active", "contacts_all"]:
                filter_type = data.replace("contacts_", "")
                if is_document_message:
                    await self.show_contacts_list(update, context, filter_type)
                else:
                    await self.show_contacts_list(update, context, filter_type)
                return
            
            # ===== ОБРАБОТКА МЕНЮ =====
            if data == "menu_contacts":
                if is_document_message:
                    await self.show_contacts_menu(update, context)
                else:
                    await self.show_contacts_menu(update, context)
                return
            
            elif data == "menu_add":
                if is_document_message:
                    await self.show_add_menu(update, context)
                else:
                    await self.show_add_menu(update, context)
                return
            
            elif data == "menu_back":
                if is_document_message:
                    await self.show_admin_menu(update, context)
                else:
                    await self.show_admin_menu(update, context)
                return
            
            elif data == "menu_send_doc":
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu_back")]
                ])
                
                if is_document_message:
                    await query.message.reply_text(
                        "📤 ОТПРАВКА ДОКУМЕНТА\n\n"
                        "📝 Готов к приему документов!\n\n"
                        "Просто отправьте мне документ(ы) в этот чат.\n\n"
                        "🤖 Поддерживается:\n"
                        "• Любые форматы файлов\n"
                        "• Один или несколько документов\n"
                        "• Фотографии, PDF, Word, Excel и т.д.\n\n"
                        "💡 После отправки документа я запрошу список получателей.",
                        reply_markup=keyboard
                    )
                else:
                    await query.message.edit_text(
                        "📤 ОТПРАВКА ДОКУМЕНТА\n\n"
                        "📝 Готов к приему документов!\n\n"
                        "Просто отправьте мне документ(ы) в этот чат.\n\n"
                        "🤖 Поддерживается:\n"
                        "• Любые форматы файлов\n"
                        "• Один или несколько документов\n"
                        "• Фотографии, PDF, Word, Excel и т.д.\n\n"
                        "💡 После отправки документа я запрошу список получателей.",
                        reply_markup=keyboard
                    )
                return
            
            elif data == "menu_queue":
                if is_document_message:
                    await self.show_queue_menu(update, context)
                else:
                    await self.show_queue_menu(update, context)
                return
            
            elif data == "menu_instructions":
                if is_document_message:
                    await self.show_instructions(update, context)
                else:
                    await self.show_instructions(update, context)
                return
            
            elif data == "menu_reports":
                if is_document_message:
                    await self.show_reports_menu(update, context)
                else:
                    await self.show_reports_menu(update, context)
                return
            
            elif data == "menu_refresh":
                if is_document_message:
                    await self.show_admin_menu(update, context)
                else:
                    await self.show_admin_menu(update, context)
                return
            
            elif data == "menu_change_language":
                if is_document_message:
                    await self.show_language_menu(update, context)
                else:
                    await self.show_language_menu(update, context)
                return
            
            # ===== ОБРАБОТКА ДЕЙСТВИЙ ПОЛЬЗОВАТЕЛЯ С ДОКУМЕНТАМИ =====
            if data.startswith("approve_"):
                await self.handle_approve(update, context)
                return
            elif data.startswith("reject_"):
                await self.handle_reject(update, context)
                return
            elif data.startswith("comment_"):
                await self.handle_comment(update, context)
                return
            elif data.startswith("view_recipients_"):
                await self.handle_view_recipients(update, context)
                return
            elif data.startswith("back_to_doc_"):
                await self.handle_back_to_doc(update, context)
                return
            elif data.startswith("cancel_comment_"):
                await self.handle_comment_cancel(update, context)
                return
            elif data.startswith("open_doc_"):
                await self.open_user_document(update, context)
                return
            elif data == "process_all_docs":
                await self.handle_process_all_docs(update, context)
                return
            
            # ===== ОБРАБОТКА ДЕЙСТВИЙ ПОЛЬЗОВАТЕЛЯ В МЕНЮ =====
            if data.startswith("user_"):
                if data == "user_back_to_menu":
                    if query.from_user.id == DEVELOPER_ADMIN_ID:
                        if is_document_message:
                            await self.show_admin_menu(update, context)
                        else:
                            await self.show_admin_menu(update, context)
                    else:
                        first_name = query.from_user.first_name
                        if is_document_message:
                            await self.show_user_menu(update, first_name, context)
                        else:
                            await self.show_user_menu_by_query(update, first_name, context)
                elif data == "user_instructions":
                    if is_document_message:
                        await self.show_user_instructions(update, context)
                    else:
                        await self.show_user_instructions(update, context)
                elif data == "user_documents":
                    if is_document_message:
                        await self.show_user_documents(update, context)
                    else:
                        await self.show_user_documents(update, context)
                elif data == "user_profile":
                    if is_document_message:
                        await self.show_user_profile(update, context)
                    else:
                        await self.show_user_profile(update, context)
                elif data == "user_help":
                    if is_document_message:
                        await self.show_user_help(update, context)
                    else:
                        await self.show_user_help(update, context)
                elif data == "user_change_language":
                    if is_document_message:
                        await self.show_user_language_menu(update, context)
                    else:
                        await self.show_user_language_menu(update, context)
                elif data.startswith("user_set_lang_"):
                    await self.handle_user_language_callback(update, context)
                return
            
            # ===== ОБРАБОТКА СМЕНЫ ЯЗЫКА =====
            if data.startswith("set_lang_"):
                await self.handle_language_callback(update, context)
                return
            
            # ===== НЕИЗВЕСТНАЯ КОМАНДА =====
            logger.warning(f"⚠️ Неизвестная callback команда: {data}")
            
        except BadRequest as e:
            if "Message is not modified" in str(e):
                # Игнорируем ошибку, если сообщение не изменилось
                pass
            elif "Query is too old" in str(e):
                # Игнорируем старые запросы
                pass
            elif "There is no text in the message to edit" in str(e):
                # Игнорируем попытки редактировать сообщения без текста
                logger.warning(f"⚠️ Попытка редактировать сообщение без текста: {data}")
            else:
                logger.error(f"❌ Ошибка BadRequest в handle_all_callbacks: {e}")
                try:
                    await query.answer("❌ Произошла ошибка", show_alert=True)
                except:
                    pass
        except Exception as e:
            logger.error(f"❌ Ошибка в handle_all_callbacks: {e}")
            try:
                await query.answer("❌ Произошла ошибка", show_alert=True)
            except:
                pass
    
    # ====== ДОБАВЛЕННЫЕ МЕТОДЫ ДЛЯ ОБРАБОТКИ КОМАНД ======

    async def handle_comment_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка отмены комментария"""
        query = update.callback_query
        data = query.data
        
        if data.startswith("cancel_comment_"):
            doc_id = data.replace("cancel_comment_", "")
            user_id = query.from_user.id
            
            # Очищаем контекст
            if 'waiting_comment' in context.user_data:
                del context.user_data['waiting_comment']
            
            # Возвращаемся к документу
            lang = self.get_user_language(user_id)
            cancel_message = Translations.get('comment_cancel', lang)
            
            try:
                if query.message.text:  # Если есть текст
                    await query.message.edit_text(
                        cancel_message,
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("⬅️ Назад к документу", callback_data=f"open_doc_{doc_id}")]
                        ])
                    )
                else:
                    # Если нет текста, отправляем новое сообщение
                    await query.message.reply_text(
                        cancel_message,
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("⬅️ Назад к документу", callback_data=f"open_doc_{doc_id}")]
                        ])
                    )
            except Exception as e:
                logger.error(f"❌ Ошибка при отмене комментария: {e}")
                # Попробуем отправить новое сообщение
                await query.message.reply_text(
                    cancel_message,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Назад к документу", callback_data=f"open_doc_{doc_id}")]
                    ])
                )

    async def queue_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /queue"""
        await self.show_queue_menu(update, context)

    async def handle_view_recipients(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка просмотра списка получателей"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data.startswith("view_recipients_"):
            doc_id = data.replace("view_recipients_", "")
            lang = self.get_user_language(user_id)
            
            try:
                with DatabaseManager.db_connection(self.db_path) as conn:
                    c = conn.cursor()
                    
                    # Получаем информацию о документе
                    c.execute('''SELECT file_name FROM document_files 
                            WHERE doc_id = ? ORDER BY file_order LIMIT 1''', (doc_id,))
                    doc_info = c.fetchone()
                    doc_name = doc_info[0] if doc_info else "Документ"
                    
                    # Получаем список получателей
                    c.execute('''SELECT c.name, c.phone, c.username, r.status, 
                            r.comment, r.response_time, r.comment_only
                            FROM recipients r
                            JOIN contacts c ON r.contact_id = c.id
                            WHERE r.doc_id = ?
                            ORDER BY 
                                CASE 
                                    WHEN c.telegram_id = ? THEN 1
                                    ELSE 2 
                                END,
                                r.response_time DESC''', (doc_id, user_id))
                    
                    recipients = c.fetchall()
                    
            except Exception as e:
                logger.error(f"❌ Ошибка получения списка получателей: {e}")
                recipients = []
            
            if not recipients:
                message = Translations.get('recipients_list', lang) + "\n"
                message += "📭 Нет информации о получателях"
            else:
                message = Translations.get('recipients_list', lang)
                
                for i, (name, phone, username, status, comment, response_time, comment_only) in enumerate(recipients, 1):
                    # Формируем имя получателя
                    if name:
                        recipient_name = name
                    elif username:
                        recipient_name = f"@{username}"
                    elif phone:
                        recipient_name = phone
                    else:
                        recipient_name = f"Получатель #{i}"
                    
                    # Определяем статус
                    if comment_only:
                        status_text = Translations.get('recipient_status_pending', lang) + " 💬"
                    elif status == 'approved':
                        status_text = Translations.get('recipient_status_approved', lang)
                    elif status == 'rejected':
                        status_text = Translations.get('recipient_status_rejected', lang)
                    elif status == 'pending':
                        status_text = Translations.get('recipient_status_pending', lang)
                    else:
                        status_text = "📨 Неизвестно"
                    
                    # Добавляем время ответа если есть
                    time_text = ""
                    if response_time:
                        try:
                            resp_dt = datetime.strptime(response_time, '%Y-%m-%d %H:%M:%S')
                            time_text = f" ({resp_dt.strftime('%d.%m %H:%M')})"
                        except:
                            pass
                    
                    message += Translations.get('recipient_item', lang).format(
                        index=i,
                        name=recipient_name,
                        status=status_text + time_text
                    )
            
            # Кнопка возврата
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад к документу", callback_data=f"back_to_doc_{doc_id}")]
            ])
            
            try:
                if query.message.text:  # Если есть текст
                    await query.message.edit_text(message, reply_markup=keyboard, parse_mode='Markdown')
                else:
                    await query.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"❌ Ошибка отображения списка получателей: {e}")
                await query.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')

    async def handle_back_to_doc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка возврата к документу"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith("back_to_doc_"):
            doc_id = data.replace("back_to_doc_", "")
            user_id = query.from_user.id
            
            # Показываем документ
            await self.show_document_to_user(update, context, doc_id)

    async def activate_user(self, user_id: int, phone: str = None, username: str = None, user_name: str = None) -> bool:
        """🚀 АКТИВАЦИЯ ПОЛЬЗОВАТЕЛЯ ПОСЛЕ ПЕРЕХОДА ПО ССЫЛКЕ"""
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Нормализация телефона если есть
                if phone:
                    phone = self.normalize_phone(phone)
                
                # ===== 1. ПРОВЕРЯЕМ, ЕСТЬ ЛИ УЖЕ КОНТАКТ С TELEGRAM_ID =====
                c.execute('SELECT id, first_activation FROM contacts WHERE telegram_id = ?', (user_id,))
                existing = c.fetchone()
                
                if existing:
                    # Уже активирован - просто обновляем время
                    contact_id = existing[0]
                    c.execute('UPDATE contacts SET last_activity = CURRENT_TIMESTAMP WHERE id = ?', (contact_id,))
                    conn.commit()
                    logger.info(f"✅ Пользователь {user_id} уже активирован (contact_id={contact_id})")
                    return True
                
                # ===== 2. ИЩЕМ КОНТАКТ ПО ТЕЛЕФОНУ ИЛИ USERNAME =====
                contact_id = None
                
                if phone:
                    c.execute('SELECT id, first_activation FROM contacts WHERE phone = ?', (phone,))
                    row = c.fetchone()
                    if row:
                        contact_id = row[0]
                        logger.info(f"🔍 Найден контакт {contact_id} по телефону {phone}")
                
                if not contact_id and username:
                    c.execute('SELECT id, first_activation FROM contacts WHERE username = ?', (username,))
                    row = c.fetchone()
                    if row:
                        contact_id = row[0]
                        logger.info(f"🔍 Найден контакт {contact_id} по username @{username}")
                
                if contact_id:
                    # Активируем существующий контакт
                    c.execute('''
                        UPDATE contacts 
                        SET 
                            telegram_id = ?,
                            first_activation = COALESCE(first_activation, CURRENT_TIMESTAMP),
                            last_activity = CURRENT_TIMESTAMP,
                            name = COALESCE(?, name),
                            username = COALESCE(?, username),
                            phone = COALESCE(?, phone)
                        WHERE id = ?
                    ''', (user_id, user_name, username, phone, contact_id))
                    
                    logger.info(f"✅ Контакт {contact_id} активирован для пользователя {user_id}")
                else:
                    # Создаём новый контакт
                    c.execute('''
                        INSERT INTO contacts 
                        (telegram_id, phone, username, name, first_activation, last_activity)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ''', (user_id, phone, username, user_name))
                    
                    contact_id = c.lastrowid
                    logger.info(f"✅ Создан новый контакт {contact_id} для пользователя {user_id}")
                
                conn.commit()
                
                # ===== 3. ОБНОВЛЯЕМ RECIPIENTS =====
                try:
                    c.execute('''
                        UPDATE recipients 
                        SET status = 'pending', notification_sent = 0
                        WHERE contact_id = ? AND status = 'invitation_sent'
                    ''', (contact_id,))
                    
                    updated = c.rowcount
                    if updated > 0:
                        logger.info(f"📨 Обновлено {updated} ожидающих документов")
                    
                    conn.commit()
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось обновить recipients: {e}")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка активации пользователя {user_id}: {e}")
            return False

    async def show_contacts_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """👥 ВЫБОР КОНТАКТОВ — АКТИВНЫЕ ВСЕГДА ПЕРВЫЕ (по telegram_id)"""
        
        query = update.callback_query
        await query.answer()
        
        # Получаем doc_id
        doc_id = None
        if query.data.startswith("select_contacts_"):
            doc_id = query.data.replace("select_contacts_", "")
        elif 'current_doc_id' in context.user_data:
            doc_id = context.user_data['current_doc_id']
        elif 'pending_doc' in context.user_data:
            doc_id = context.user_data['pending_doc']['id']
        
        if not doc_id:
            await query.answer("❌ Документ не найден", show_alert=True)
            return
        
        # Пагинация
        page = 0
        if query.data.startswith("page_"):
            try:
                page = int(query.data.split("_")[2])
            except:
                pass
        
        context.user_data['current_doc_id'] = doc_id
        
        # Инициализация
        if 'selected_contacts' not in context.user_data:
            context.user_data['selected_contacts'] = {}
        if doc_id not in context.user_data['selected_contacts']:
            context.user_data['selected_contacts'][doc_id] = []
        
        # ========== ⚡️ ГЛАВНОЕ ИСПРАВЛЕНИЕ ==========
        # ✅ АКТИВНЫЕ = ЕСТЬ telegram_id
        # ✅ first_activation НЕ ИСПОЛЬЗУЕТСЯ для определения активности
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''
                    SELECT DISTINCT 
                        id, 
                        phone, 
                        username, 
                        name, 
                        telegram_id,
                        first_activation  -- только для информации
                    FROM contacts 
                    WHERE (phone IS NOT NULL AND phone != '') 
                    OR (username IS NOT NULL AND username != '')
                    ORDER BY 
                        CASE WHEN telegram_id IS NOT NULL THEN 1 ELSE 2 END,  -- ⚡️ ТОЛЬКО ЭТО!
                        last_activity DESC NULLS LAST,
                        name
                ''')
                contacts_raw = c.fetchall()
        except Exception as e:
            logger.error(f"❌ Ошибка получения контактов: {e}")
            contacts_raw = []
        
        # Преобразуем в словарь
        contacts = {}
        for contact_id, phone, username, name, telegram_id, first_activation in contacts_raw:
            unique_key = f"contact_{contact_id}"
            contacts[unique_key] = {
                'id': contact_id,
                'phone': phone,
                'username': username,
                'name': name,
                'telegram_id': telegram_id,
                'first_activation': first_activation,
                'is_active': telegram_id is not None  # ✅ ЯВНЫЙ ФЛАГ
            }
        
        # Сохраняем в контекст
        context.user_data['contacts_for_selection'] = {doc_id: contacts}
        selected_list = context.user_data['selected_contacts'][doc_id]
        
        # ========== ФОРМИРУЕМ КЛАВИАТУРУ ==========
        keyboard_buttons = []
        
        # 1. Кнопка отправки
        if selected_list:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    f"📤 ОТПРАВИТЬ ВЫБРАННЫЕ ({len(selected_list)})",
                    callback_data=f"send_selected_{doc_id}"
                )
            ])
            keyboard_buttons.append([])
        
        # 2. Пагинация
        contacts_items = list(contacts.items())
        per_page = 8
        total_pages = (len(contacts_items) + per_page - 1) // per_page
        page = max(0, min(page, total_pages - 1))
        
        start = page * per_page
        end = start + per_page
        page_items = contacts_items[start:end]
        
        # 3. Контакты текущей страницы
        for unique_key, contact_data in page_items:
            contact_id = contact_data['id']
            phone = contact_data['phone']
            username = contact_data['username']
            name = contact_data['name']
            is_active = contact_data['is_active']  # ✅ telegram_id is not None
            
            # Отображаемое имя
            if name:
                display_name = name
            elif phone:
                display_name = phone
            elif username:
                display_name = f"@{username}"
            else:
                display_name = f"Контакт #{contact_id}"
            
            if len(display_name) > 15:
                display_name = display_name[:12] + "..."
            
            # Тип контакта
            contact_type = ""
            if phone and username:
                contact_type = "📱👤"
            elif phone:
                contact_type = "📱"
            elif username:
                contact_type = "👤"
            
            # ✅ АКТИВАЦИЯ ТОЛЬКО ПО TELEGRAM_ID
            status = "✅" if is_active else "⏳"
            
            # Выбран?
            is_selected = any(str(s.get('id')) == str(contact_id) for s in selected_list)
            
            button_text = f"{'☑️ ' if is_selected else ''}{status}{contact_type} {display_name}"
            
            keyboard_buttons.append([
                InlineKeyboardButton(button_text, callback_data=f"tog_{doc_id}_{contact_id}")
            ])
        
        # 4. Пагинация
        if total_pages > 1:
            pagination = []
            if page > 0:
                pagination.append(InlineKeyboardButton("◀️ Назад", callback_data=f"page_{doc_id}_{page-1}"))
            pagination.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))
            if page < total_pages - 1:
                pagination.append(InlineKeyboardButton("Вперед ▶️", callback_data=f"page_{doc_id}_{page+1}"))
            keyboard_buttons.append(pagination)
        
        # 5. Действия
        keyboard_buttons.append([
            InlineKeyboardButton("✏️ Ввести вручную", callback_data=f"back_to_input_{doc_id}"),
            InlineKeyboardButton("🔄 Обновить", callback_data=f"select_contacts_{doc_id}")
        ])
        keyboard_buttons.append([
            InlineKeyboardButton("❌ Отмена отправки", callback_data="cancel_selection")
        ])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        # ========== СООБЩЕНИЕ ==========
        active_count = sum(1 for c in contacts.values() if c['is_active'])
        total_count = len(contacts)
        
        message = f"👥 **ВЫБОР КОНТАКТОВ**\n\n"
        message += f"🆔 Документ ID: `{doc_id}`\n\n"
        message += f"📊 **Статистика:**\n"
        message += f"• ✅ Активировано: {active_count}\n"
        message += f"• ⏳ Не активировано: {total_count - active_count}\n"
        message += f"• 📋 Всего контактов: {total_count}\n\n"
        
        if selected_list:
            message += f"✅ **Выбрано: {len(selected_list)} контактов**\n"
            message += f"📤 **Нажмите 'ОТПРАВИТЬ ВЫБРАННЫЕ'**\n\n"
        
        message += f"**Обозначения:**\n"
        message += f"✅ – Активирован (есть в Telegram)\n"
        message += f"⏳ – Не активирован\n"
        message += f"📱 – Есть телефон\n"
        message += f"👤 – Есть username\n"
        message += f"📱👤 – Есть и телефон, и username\n"
        message += f"☑️ – Выбран\n\n"
        
        if selected_list:
            message += f"✅ **ВЫБРАНЫ:**\n"
            for i, sel in enumerate(selected_list[:5], 1):
                name = sel.get('name') or sel.get('phone') or f"@{sel.get('username')}" if sel.get('username') else f"ID:{sel.get('id')}"
                message += f"{i}. {name[:30]}\n"
            if len(selected_list) > 5:
                message += f"... и еще {len(selected_list) - 5}\n"
            message += "\n"
        
        try:
            await query.message.edit_text(message, reply_markup=keyboard, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"❌ Ошибка редактирования: {e}")

    async def handle_process_all_docs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка кнопки 'Обработать все документы'"""
        query = update.callback_query
        await query.answer("⏳ Загружаю документы...")
        
        user_id = query.from_user.id
        
        # Получаем все ожидающие документы пользователя
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                c.execute('''SELECT DISTINCT d.id, df.file_name
                        FROM recipients r
                        JOIN documents d ON r.doc_id = d.id
                        JOIN document_files df ON d.id = df.doc_id AND df.file_order = 1
                        JOIN contacts c ON r.contact_id = c.id
                        WHERE c.telegram_id = ? AND r.status = 'pending'
                        ORDER BY d.created DESC''', (user_id,))
                
                pending_docs = c.fetchall()
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения документов: {e}")
            pending_docs = []
        
        if not pending_docs:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад в меню", callback_data="user_back_to_menu")]
            ])
            
            await query.message.edit_text(
                "📭 У вас нет документов для обработки.",
                reply_markup=keyboard
            )
            return
        
        # Показываем первый документ
        if pending_docs:
            first_doc_id = pending_docs[0][0]
            await self.show_document_to_user(update, context, first_doc_id)

    async def view_document_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Просмотр отчета по документу"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith("view_doc_report_"):
            doc_id = data.replace("view_doc_report_", "")
            await self.show_document_report_details(update, context, doc_id)

    async def show_document_report_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE, doc_id: str):
        """Показывает детали отчета по документу"""
        query = update.callback_query
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем информацию о документе
                c.execute('''SELECT d.created, 
                            GROUP_CONCAT(df.file_name, '; ') as files,
                            GROUP_CONCAT(df.file_id, '; ') as file_ids
                            FROM documents d
                            LEFT JOIN document_files df ON d.id = df.doc_id
                            WHERE d.id = ?''', (doc_id,))
                
                doc_info = c.fetchone()
                
                if not doc_info:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Назад к отчетам", callback_data="menu_reports")]
                    ])
                    
                    await query.message.edit_text("❌ Документ не найден", reply_markup=keyboard)
                    return
                
                created, files, file_ids = doc_info
                created_dt = datetime.strptime(created, '%Y-%m-%d %H:%M:%S')
                created_str = created_dt.strftime('%d.%m.%Y %H:%M:%S')
                
                # Получаем информацию о получателях
                c.execute('''SELECT c.name, c.phone, c.username, 
                            r.status, r.comment, r.response_time,
                            r.sent_via, r.comment_only
                            FROM recipients r
                            LEFT JOIN contacts c ON r.contact_id = c.id
                            WHERE r.doc_id = ?
                            ORDER BY r.response_time DESC''', (doc_id,))
                
                recipients = c.fetchall()
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных отчета: {e}")
            await query.message.edit_text("❌ Ошибка получения данных отчета")
            return
        
        # Формируем отчет
        message = f"📄 *ОТЧЕТ ПО ДОКУМЕНТУ*\n\n"
        message += f"🆔 ID: `{doc_id}`\n"
        message += f"📅 Дата создания: {created_str}\n\n"
        
        if files:
            file_list = files.split('; ')
            message += f"📋 Файлы ({len(file_list)}):\n"
            for i, file_name in enumerate(file_list, 1):
                message += f"{i}. {file_name}\n"
            message += "\n"
        
        if recipients:
            approved = 0
            rejected = 0
            pending = 0
            comment_only = 0
            
            message += "👥 *ПОЛУЧАТЕЛИ:*\n\n"
            
            for i, (name, phone, username, status, comment, response_time, sent_via, comment_only_flag) in enumerate(recipients, 1):
                # Определяем имя получателя
                if name:
                    recipient_name = name
                elif username:
                    recipient_name = f"@{username}"
                elif phone:
                    recipient_name = phone
                else:
                    recipient_name = f"Получатель #{i}"
                
                message += f"{i}. *{recipient_name}*\n"
                
                # Определяем статус
                if comment_only_flag:
                    status_text = "💬 Только комментарий"
                    comment_only += 1
                elif status == 'approved':
                    status_text = '✅ Согласовано'
                    approved += 1
                elif status == 'rejected':
                    status_text = '❌ Отклонено'
                    rejected += 1
                elif status == 'pending':
                    status_text = '⏳ Ожидает'
                    pending += 1
                else:
                    status_text = '📨 Не отправлено'
                
                message += f"   Статус: {status_text}"
                
                if sent_via:
                    message += f" ({sent_via})"
                message += "\n"
                
                if comment:
                    comment_preview = comment[:50] + "..." if len(comment) > 50 else comment
                    message += f"   Комментарий: {comment_preview}\n"
                
                if response_time:
                    resp_dt = datetime.strptime(response_time, '%Y-%m-%d %H:%M:%S')
                    resp_str = resp_dt.strftime('%d.%m.%Y %H:%M')
                    message += f"   Время ответа: {resp_str}\n"
                
                message += "\n"
            
            # Статистика
            total = len(recipients)
            message += "📊 *СТАТИСТИКА:*\n"
            message += f"• Всего получателей: {total}\n"
            message += f"• ✅ Согласовано: {approved}\n"
            message += f"• ❌ Отклонено: {rejected}\n"
            message += f"• 💬 Только комментарий: {comment_only}\n"
            message += f"• ⏳ Ожидает: {pending}\n\n"
            
            if total > 0:
                completion_rate = (approved + rejected + comment_only) / total * 100
                if approved + rejected > 0:
                    approval_rate = approved / (approved + rejected) * 100
                else:
                    approval_rate = 0
                
                message += f"📈 *ЭФФЕКТИВНОСТЬ:*\n"
                message += f"• Завершено согласование: {completion_rate:.1f}%\n"
                message += f"• Процент согласования: {approval_rate:.1f}%\n\n"
        
        else:
            message += "📭 Получатели не назначены\n\n"
        
        # ===== ИСПРАВЛЕНИЕ: Добавляем кнопку PDF отчета =====
        keyboard_buttons = [
            [
                InlineKeyboardButton("📊 Статистика", callback_data=f"export_stats_{doc_id}"),
                InlineKeyboardButton("📝 TXT отчет", callback_data=f"export_txt_{doc_id}")
            ],
            [
                InlineKeyboardButton("📄 PDF отчет", callback_data=f"export_pdf_{doc_id}")
            ],
            [
                InlineKeyboardButton("⬅️ Назад к выбору", callback_data="report_document")
            ]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        # Проверяем тип сообщения
        if query.message.text:
            await query.message.edit_text(message, reply_markup=keyboard, parse_mode='Markdown')
        else:
            await query.message.reply_text(message, reply_markup=keyboard, parse_mode='Markdown')

    async def handle_period_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка отчетов за период"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "period_today":
            await self.generate_period_report(update, context, "today")
        elif data == "period_week":
            await self.generate_period_report(update, context, "week")
        elif data == "period_month":
            await self.generate_period_report(update, context, "month")
        elif data == "period_all":
            await self.generate_period_report(update, context, "all")

    async def generate_period_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE, period: str):
        """Генерация отчета за период"""
        query = update.callback_query
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Определяем условия периода
                if period == "today":
                    period_condition = "DATE(d.created) = DATE('now')"
                    period_text = "сегодня"
                elif period == "week":
                    period_condition = "d.created >= DATE('now', '-7 days')"
                    period_text = "за последние 7 дней"
                elif period == "month":
                    period_condition = "d.created >= DATE('now', '-30 days')"
                    period_text = "за последний месяц"
                else:  # all
                    period_condition = "1=1"
                    period_text = "за все время"
                
                # Получаем статистику по документам
                c.execute(f'''SELECT 
                        COUNT(DISTINCT d.id) as total_docs,
                        SUM(CASE WHEN r.status = 'approved' THEN 1 ELSE 0 END) as approved,
                        SUM(CASE WHEN r.status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                        SUM(CASE WHEN r.status = 'pending' THEN 1 ELSE 0 END) as pending,
                        SUM(CASE WHEN r.comment_only = 1 THEN 1 ELSE 0 END) as comment_only,
                        COUNT(DISTINCT c.telegram_id) as active_users
                        FROM documents d
                        LEFT JOIN recipients r ON d.id = r.doc_id
                        LEFT JOIN contacts c ON r.contact_id = c.id
                        WHERE {period_condition}''')
                
                stats = c.fetchone()
                
                # Получаем топ документов
                c.execute(f'''SELECT d.id, 
                        GROUP_CONCAT(DISTINCT df.file_name) as files,
                        COUNT(DISTINCT r.id) as recipients_count
                        FROM documents d
                        LEFT JOIN document_files df ON d.id = df.doc_id
                        LEFT JOIN recipients r ON d.id = r.doc_id
                        WHERE {period_condition}
                        GROUP BY d.id
                        ORDER BY d.created DESC
                        LIMIT 5''')
                
                top_docs = c.fetchall()
                
        except Exception as e:
            logger.error(f"❌ Ошибка генерации отчета за период: {e}")
            stats = (0, 0, 0, 0, 0, 0)
            top_docs = []
        
        # Формируем отчет
        total_docs, approved, rejected, pending, comment_only, active_users = stats
        
        message = f"📊 *ОТЧЕТ {period_text.upper()}*\n\n"
        
        message += f"📄 *Документы:*\n"
        message += f"• Всего: {total_docs}\n"
        message += f"• ✅ Согласовано отправок: {approved}\n"
        message += f"• ❌ Отклонено отправок: {rejected}\n"
        message += f"• 💬 Только комментарий: {comment_only}\n"
        message += f"• ⏳ Ожидает: {pending}\n\n"
        
        message += f"👥 *Активные пользователи:* {active_users}\n\n"
        
        if top_docs:
            message += f"📋 *Последние документы:*\n"
            for i, (doc_id, files, recipients_count) in enumerate(top_docs, 1):
                file_list = files.split(',') if files else []
                first_file = file_list[0][:30] + "..." if len(file_list[0]) > 30 else file_list[0] if file_list else "Без названия"
                message += f"{i}. {first_file}\n"
                message += f"   🆔 ID: {doc_id[:8]}, 👥 Получателей: {recipients_count}\n\n"
        
        # Кнопки
        keyboard_buttons = [
            [InlineKeyboardButton("📝 TXT отчет", callback_data=f"export_period_{period}")],
            [InlineKeyboardButton("⬅️ Назад к периодам", callback_data="report_period")]
        ]
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await query.message.edit_text(message, reply_markup=keyboard, parse_mode='Markdown')

    async def export_users_pdf_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Экспорт отчета по пользователям в PDF"""
        query = update.callback_query
        await query.answer("📄 Генерирую PDF отчет по пользователям...")
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем статистику по пользователям
                c.execute('''SELECT c.name, c.phone, c.username, c.telegram_id,
                            COUNT(r.id) as total_docs,
                            SUM(CASE WHEN r.status = 'approved' THEN 1 ELSE 0 END) as approved,
                            SUM(CASE WHEN r.status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                            SUM(CASE WHEN r.status = 'pending' THEN 1 ELSE 0 END) as pending,
                            SUM(CASE WHEN r.comment_only = 1 THEN 1 ELSE 0 END) as comment_only,
                            MIN(r.response_time) as first_response,
                            MAX(r.response_time) as last_response,
                            c.last_activity
                            FROM contacts c
                            LEFT JOIN recipients r ON c.id = r.contact_id
                            GROUP BY c.id
                            ORDER BY 
                                CASE WHEN c.telegram_id IS NOT NULL THEN 1 ELSE 2 END,
                                total_docs DESC,
                                c.last_activity DESC''')
                
                users = c.fetchall()
                
                # Общая статистика
                c.execute('''SELECT 
                            COUNT(*) as total_contacts,
                            SUM(CASE WHEN telegram_id IS NOT NULL THEN 1 ELSE 0 END) as active_users,
                            COUNT(DISTINCT doc_id) as total_docs,
                            COUNT(*) as total_recipients
                            FROM contacts c
                            LEFT JOIN recipients r ON c.id = r.contact_id''')
                
                total_stats = c.fetchone()
                total_contacts, active_users, total_docs, total_recipients = total_stats if total_stats else (0, 0, 0, 0)
            
            # Создаем PDF в памяти
            pdf_buffer = io.BytesIO()
            
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            
            # Используем альбомную ориентацию для лучшего отображения таблиц
            doc = SimpleDocTemplate(
                pdf_buffer,
                pagesize=landscape(A4),
                rightMargin=36,
                leftMargin=36,
                topMargin=36,
                bottomMargin=36,
            )
            
            styles = getSampleStyleSheet()
            title_style = styles['Title']
            heading_style = styles['Heading2']
            normal_style = styles['Normal']
            
            # Создаем стиль для таблицы
            table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ])
            
            elements = []
            
            # Заголовок
            elements.append(Paragraph(f"📊 ОТЧЕТ ПО ПОЛЬЗОВАТЕЛЯМ", title_style))
            elements.append(Spacer(1, 0.1*inch))
            
            # Общая статистика
            elements.append(Paragraph(f"<b>Дата генерации:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}", normal_style))
            elements.append(Paragraph(f"<b>Всего контактов:</b> {total_contacts}", normal_style))
            elements.append(Paragraph(f"<b>✅ Активированных пользователей:</b> {active_users}", normal_style))
            elements.append(Paragraph(f"<b>⏳ Не активированных:</b> {total_contacts - active_users}", normal_style))
            elements.append(Paragraph(f"<b>📄 Всего документов:</b> {total_docs}", normal_style))
            elements.append(Paragraph(f"<b>📨 Всего отправок:</b> {total_recipients}", normal_style))
            elements.append(Spacer(1, 0.2*inch))
            
            if users:
                # Создаем таблицу пользователей
                table_data = [['№', 'Имя/Контакт', 'Телефон', 'Username', 'Статус', 'Документов', '✅', '❌', '💬', '⏳', 'Посл. активность']]
                
                for i, (name, phone, username, telegram_id, total_docs, approved, rejected, pending, comment_only, first_response, last_response, last_activity) in enumerate(users, 1):
                    # Имя для отображения
                    display_name = name or (f"@{username}" if username else phone or f"Контакт #{i}")
                    if len(display_name) > 20:
                        display_name = display_name[:17] + "..."
                    
                    # Телефон (обрезаем если длинный)
                    display_phone = phone if phone else "-"
                    if len(display_phone) > 15:
                        display_phone = display_phone[:12] + "..."
                    
                    # Username
                    display_username = f"@{username}" if username else "-"
                    if len(display_username) > 15:
                        display_username = display_username[:12] + "..."
                    
                    # Статус
                    status = "✅ Активен" if telegram_id else "⏳ Не активен"
                    
                    # Последняя активность
                    last_act = "-"
                    if last_activity:
                        try:
                            act_dt = datetime.strptime(last_activity, '%Y-%m-%d %H:%M:%S')
                            last_act = act_dt.strftime('%d.%m.%Y')
                        except:
                            pass
                    
                    table_data.append([
                        str(i),
                        display_name,
                        display_phone,
                        display_username,
                        status,
                        str(total_docs or 0),
                        str(approved or 0),
                        str(rejected or 0),
                        str(comment_only or 0),
                        str(pending or 0),
                        last_act
                    ])
                
                # Создаем таблицу с колонками разной ширины
                col_widths = [0.4*inch, 1.5*inch, 1.3*inch, 1.3*inch, 1.0*inch, 0.6*inch, 0.4*inch, 0.4*inch, 0.4*inch, 0.4*inch, 1.0*inch]
                user_table = Table(table_data, colWidths=col_widths, repeatRows=1)
                user_table.setStyle(table_style)
                elements.append(user_table)
                
                # Добавляем легенду
                elements.append(Spacer(1, 0.2*inch))
                elements.append(Paragraph("<b>Легенда:</b>", normal_style))
                elements.append(Paragraph("✅ - Согласовано, ❌ - Отклонено, 💬 - Только комментарий, ⏳ - Ожидает решения", normal_style))
                elements.append(Paragraph("✅ Активен - пользователь активировал бота", normal_style))
                elements.append(Paragraph("⏳ Не активен - пользователь еще не активировал бота", normal_style))
            
            # Подвал
            elements.append(Spacer(1, 0.2*inch))
            elements.append(Paragraph("─" * 80, normal_style))
            elements.append(Paragraph("📊 DocFlow - Система согласования документов", normal_style))
            
            # Строим PDF
            doc.build(elements)
            
            # Перематываем буфер
            pdf_buffer.seek(0)
            
            # Отправляем PDF
            filename = f"users_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            # Сначала отправляем PDF документ
            await query.message.reply_document(
                document=pdf_buffer,
                filename=filename,
                caption=f"📄 PDF отчет по пользователям\n👥 Всего пользователей: {total_contacts}\n✅ Активных: {active_users}"
            )
            
            # ===== ВАЖНО: ОТПРАВЛЯЕМ ОТДЕЛЬНОЕ СООБЩЕНИЕ С КНОПКОЙ НАВИГАЦИИ =====
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад к отчетам", callback_data="menu_reports")]
            ])
            
            await query.message.reply_text(
                "📊 PDF отчет отправлен!\n\nНажмите кнопку ниже для возврата в меню отчетов.",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания PDF отчета по пользователям: {e}", exc_info=True)
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Попробовать TXT отчет", callback_data="export_users_txt")],
                [InlineKeyboardButton("⬅️ Назад к отчетам", callback_data="menu_reports")]
            ])
            
            await query.message.edit_text(
                f"❌ Ошибка при создании PDF отчета:\n{str(e)[:200]}",
                reply_markup=keyboard
            )

    async def export_users_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Экспорт отчета по пользователям"""
        query = update.callback_query
        data = query.data
        
        if data == "export_users_pdf":
            await self.export_users_pdf_report(update, context)
        elif data == "export_users_txt":
            await self.export_users_txt_report(update, context)


    async def export_users_txt_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Экспорт отчета по пользователям в TXT с улучшенным форматированием"""
        query = update.callback_query
        await query.answer("⏳ Генерирую TXT отчет...")
        
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Получаем статистику по пользователям
                c.execute('''SELECT c.name, c.phone, c.username, c.telegram_id,
                            COUNT(r.id) as total_docs,
                            SUM(CASE WHEN r.status = 'approved' THEN 1 ELSE 0 END) as approved,
                            SUM(CASE WHEN r.status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                            SUM(CASE WHEN r.status = 'pending' THEN 1 ELSE 0 END) as pending,
                            SUM(CASE WHEN r.comment_only = 1 THEN 1 ELSE 0 END) as comment_only,
                            MIN(r.response_time) as first_response,
                            MAX(r.response_time) as last_response,
                            c.last_activity,
                            c.first_activation
                            FROM contacts c
                            LEFT JOIN recipients r ON c.id = r.contact_id
                            GROUP BY c.id
                            ORDER BY 
                                CASE WHEN c.telegram_id IS NOT NULL THEN 1 ELSE 2 END,
                                total_docs DESC,
                                c.last_activity DESC''')
                
                users = c.fetchall()
                
                # Общая статистика
                c.execute('''SELECT 
                            COUNT(*) as total_contacts,
                            SUM(CASE WHEN telegram_id IS NOT NULL THEN 1 ELSE 0 END) as active_users,
                            COUNT(DISTINCT doc_id) as total_docs,
                            COUNT(*) as total_recipients
                            FROM contacts c
                            LEFT JOIN recipients r ON c.id = r.contact_id''')
                
                total_stats = c.fetchone()
                total_contacts, active_users, total_docs, total_recipients = total_stats if total_stats else (0, 0, 0, 0)
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных пользователей: {e}")
            users = []
            total_contacts = active_users = total_docs = total_recipients = 0
        
        # Формируем TXT отчет
        txt_report = []
        txt_report.append("=" * 80)
        txt_report.append("ОТЧЕТ ПО ПОЛЬЗОВАТЕЛЯМ".center(80))
        txt_report.append("=" * 80)
        txt_report.append("")
        
        txt_report.append(f"Дата генерации: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        txt_report.append(f"Всего контактов: {total_contacts}")
        txt_report.append(f"✅ Активированных пользователей: {active_users}")
        txt_report.append(f"⏳ Не активированных: {total_contacts - active_users}")
        txt_report.append(f"📄 Всего документов: {total_docs}")
        txt_report.append(f"📨 Всего отправок: {total_recipients}")
        txt_report.append("")
        
        if users:
            txt_report.append("=" * 80)
            txt_report.append("ДЕТАЛЬНЫЙ СПИСОК ПОЛЬЗОВАТЕЛЕЙ".center(80))
            txt_report.append("=" * 80)
            txt_report.append("")
            
            for i, (name, phone, username, telegram_id, total_docs, approved, rejected, pending, comment_only, first_response, last_response, last_activity, first_activation) in enumerate(users, 1):
                txt_report.append(f"{i}. " + ("=" * 40))
                
                # Основная информация
                if name:
                    txt_report.append(f"   👤 Имя: {name}")
                if phone:
                    txt_report.append(f"   📱 Телефон: {phone}")
                if username:
                    txt_report.append(f"   👤 Username: @{username}")
                
                # Статус активации
                if telegram_id:
                    txt_report.append(f"   ✅ АКТИВИРОВАН (ID: {telegram_id})")
                    if first_activation:
                        try:
                            act_dt = datetime.strptime(first_activation, '%Y-%m-%d %H:%M:%S')
                            txt_report.append(f"      🕐 Активирован: {act_dt.strftime('%d.%m.%Y %H:%M')}")
                        except:
                            pass
                else:
                    txt_report.append(f"   ⏳ НЕ АКТИВИРОВАН")
                
                # Последняя активность
                if last_activity:
                    try:
                        act_dt = datetime.strptime(last_activity, '%Y-%m-%d %H:%M:%S')
                        txt_report.append(f"      🕐 Последняя активность: {act_dt.strftime('%d.%m.%Y %H:%M')}")
                    except:
                        pass
                
                txt_report.append("")
                txt_report.append(f"   📊 СТАТИСТИКА ДОКУМЕНТОВ:")
                txt_report.append(f"      Всего документов: {total_docs or 0}")
                txt_report.append(f"      ✅ Согласовано: {approved or 0}")
                txt_report.append(f"      ❌ Отклонено: {rejected or 0}")
                txt_report.append(f"      💬 Только комментарий: {comment_only or 0}")
                txt_report.append(f"      ⏳ Ожидает решения: {pending or 0}")
                
                if total_docs and total_docs > 0:
                    approval_rate = (approved or 0) / max((approved or 0) + (rejected or 0), 1) * 100
                    completion_rate = ((approved or 0) + (rejected or 0) + (comment_only or 0)) / max(total_docs, 1) * 100
                    txt_report.append(f"      📈 Эффективность:")
                    txt_report.append(f"         Завершено: {completion_rate:.1f}%")
                    txt_report.append(f"         Согласовано: {approval_rate:.1f}%")
                
                txt_report.append("")
        
        # Добавляем статистику по статусам
        txt_report.append("=" * 80)
        txt_report.append("ИТОГОВАЯ СТАТИСТИКА".center(80))
        txt_report.append("=" * 80)
        txt_report.append("")
        
        txt_report.append(f"📊 Общая статистика системы:")
        txt_report.append(f"   👥 Пользователи: {total_contacts}")
        txt_report.append(f"   ✅ Активировано: {active_users} ({active_users/max(total_contacts,1)*100:.1f}%)")
        txt_report.append(f"   ⏳ Не активировано: {total_contacts - active_users}")
        txt_report.append(f"")
        txt_report.append(f"   📄 Документы: {total_docs}")
        txt_report.append(f"   📨 Отправки документов: {total_recipients}")
        
        txt_report.append("")
        txt_report.append("=" * 80)
        txt_report.append(f"КОНЕЦ ОТЧЕТА".center(80))
        txt_report.append("=" * 80)
        
        # Объединяем в одну строку
        final_report = "\n".join(txt_report)
        
        # Создаем файл в памяти
        txt_bytes = final_report.encode('utf-8')
        txt_file = io.BytesIO(txt_bytes)
        txt_file.name = f"users_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        # Сначала отправляем TXT документ
        await query.message.reply_document(
            document=txt_file,
            caption=f"📝 TXT отчет по пользователям\n👥 Всего пользователей: {total_contacts}\n✅ Активных: {active_users}"
        )
        
        # ===== ВАЖНО: ОТПРАВЛЯЕМ ОТДЕЛЬНОЕ СООБЩЕНИЕ С КНОПКОЙ НАВИГАЦИИ =====
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад к отчетам", callback_data="menu_reports")],
            [InlineKeyboardButton("📄 PDF отчет", callback_data="export_users_pdf")]
        ])
        
        await query.message.reply_text(
            "📝 TXT отчет отправлен!\n\nВыберите действие:",
            reply_markup=keyboard
        )

    async def queue_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /queue"""
        if update.effective_user.id != DEVELOPER_ADMIN_ID:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return
        
        await self.show_queue_menu(update, context)
    
    async def setup_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /setup_admin"""
        if update.effective_user.id != DEVELOPER_ADMIN_ID:
            await update.message.reply_text("❌ У вас нет прав администратора")
            return
        
        if self.admin_sender:
            await update.message.reply_text(
                f"✅ Автоматическая отправка уже настроена\n"
                f"📱 Отправка от: {self.admin_sender.admin_phone}\n"
                f"🤖 Бот: @{self.bot_username}"
            )
            return
        
        # Запрашиваем номер телефона
        await update.message.reply_text(
            "📱 Введите номер телефона администратора (с +7):\n\n"
            "Пример: <PHONE_NUMBER>"
        )
        
        # Устанавливаем флаг ожидания номера телефона
        context.user_data['waiting_admin_phone'] = True

    # Добавьте этот код в метод update_database_schema:
    async def update_database_schema(self):
        """Обновление схемы базы данных для поддержки новых полей"""
        try:
            with DatabaseManager.db_connection(self.db_path) as conn:
                c = conn.cursor()
                
                # Проверяем структуру таблицы document_files
                c.execute("PRAGMA table_info(document_files)")
                columns = [col[1] for col in c.fetchall()]
                
                # Добавляем недостающие колонки
                if 'file_type' not in columns:
                    try:
                        c.execute('ALTER TABLE document_files ADD COLUMN file_type TEXT DEFAULT "document"')
                        logger.info("✅ Добавлена колонка file_type в таблицу document_files")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось добавить колонку file_type: {e}")
                
                if 'mime_type' not in columns:
                    try:
                        c.execute('ALTER TABLE document_files ADD COLUMN mime_type TEXT')
                        logger.info("✅ Добавлена колонка mime_type в таблицу document_files")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось добавить колонку mime_type: {e}")
                
                if 'file_size' not in columns:
                    try:
                        c.execute('ALTER TABLE document_files ADD COLUMN file_size INTEGER')
                        logger.info("✅ Добавлена колонка file_size в таблицу document_files")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось добавить колонку file_size: {e}")
                
                # Проверяем структуру таблицы documents
                c.execute("PRAGMA table_info(documents)")
                doc_columns = [col[1] for col in c.fetchall()]
                
                if 'theme' not in doc_columns:
                    try:
                        c.execute('ALTER TABLE documents ADD COLUMN theme TEXT')
                        logger.info("✅ Добавлена колонка theme в таблицу documents")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось добавить колонку theme: {e}")
                
                # ДОБАВЛЯЕМ ПОЛЕ ДЛЯ ФИНАЛЬНОГО ОТЧЕТА
                if 'final_report_sent' not in doc_columns:
                    try:
                        c.execute('ALTER TABLE documents ADD COLUMN final_report_sent INTEGER DEFAULT 0')
                        logger.info("✅ Добавлена колонка final_report_sent в таблицу documents")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось добавить колонку final_report_sent: {e}")
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления схемы базы данных: {e}")

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /cancel для отмены текущей операции"""
        user_id = update.effective_user.id
        
        if user_id != DEVELOPER_ADMIN_ID:
            return
        
        # Очищаем контекст
        self._clear_document_context(context)
        
        # Удаляем флаги ожидания
        keys_to_remove = ['waiting_recipients', 'waiting_add_contact', 'waiting_admin_phone']
        for key in keys_to_remove:
            if key in context.user_data:
                del context.user_data[key]
        
        # Показываем главное меню
        await self.show_admin_menu(update, context)


async def main():
    print("=" * 70)
    print("🤖 DOCFLOW BOT - СИСТЕМА СОГЛАСОВАНИЯ ДОКУМЕНТОВ")
    print("=" * 70)
    
    # Создаем экземпляр бота
    init_database()
    bot = UniversalContactBot()
    
    # ===== ВАЖНО: ОЧИСТКА ДУБЛИКАТОВ ПРИ СТАРТЕ =====
    print("\n🧹 Проверка и очистка дубликатов в базе данных...")
    try:
        # Очищаем дубликаты контактов
        bot.cleanup_duplicate_contacts()
        
        # Очищаем дубликаты получателей
        duplicates_count = bot.cleanup_recipients_duplicates()
        if duplicates_count > 0:
            print(f"✅ Удалено {duplicates_count} групп дубликатов в recipients")
        else:
            print("✅ Дубликаты не найдены")
    except Exception as e:
        print(f"⚠️ Ошибка при очистке дубликатов: {e}")
    
    # Веб-страница для подключения Telegram аккаунта админа (вне чата с ботом)
    start_web_auth_server(settings.web_auth_host, settings.web_auth_port)

    # Используем PicklePersistence для сохранения состояний
    persistence = PicklePersistence(filepath='conversation_states')
    app = Application.builder().token(BOT_TOKEN).persistence(persistence).build()
    
    # Сохраняем ссылку на приложение в боте
    bot.application = app
    
    # Настройка автоматической отправки
    print("\n⚙️ Настройка автоматической отправки...")
    await bot.setup_bot_info(app.bot)
    
    # Запускаем систему напоминаний
    await bot.start_reminder_system()

    # Вспомогательная функция для queue
    async def queue_status_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await bot.show_queue_menu(update, context)
    
    # ===== РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ =====
    print("\n📋 Регистрация обработчиков...")
    
    # 1. Сначала обработчики команд
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("contacts", bot.contacts_command))
    app.add_handler(CommandHandler("add", bot.add_command))
    app.add_handler(CommandHandler("queue", queue_status_wrapper))
    app.add_handler(CommandHandler("setup_admin", bot.setup_admin_command))
    app.add_handler(CommandHandler("cancel", bot.cancel_command))
    
    # 2. ВАЖНО: Обработчик документов - используем УЛУЧШЕННУЮ версию
    app.add_handler(MessageHandler(
        filters.Document.ALL | 
        filters.PHOTO | 
        filters.AUDIO | 
        filters.VOICE | 
        filters.VIDEO | 
        filters.VIDEO_NOTE | 
        filters.ANIMATION, 
        bot.handle_document_enhanced  # ИСПРАВЛЕНО: используем enhanced версию
    ))
    
    # 3. Универсальный обработчик всех callback-кнопок
    app.add_handler(CallbackQueryHandler(bot.handle_all_callbacks))
    
    # 4. Обработчик для открытия документов
    app.add_handler(CallbackQueryHandler(bot.open_user_document, pattern="^(open_doc_|process_all_docs)"))
    
    # 5. Обработчик текстовых сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text_message))
    
    # 6. Обработчик контактов
    app.add_handler(MessageHandler(filters.CONTACT, bot.handle_contact_message))
    
    # 7. Опционально: обработчик медиа-групп (если нужна поддержка нескольких файлов одновременно)
    # app.add_handler(MessageHandler(
    #     filters.Document.ALL | filters.PHOTO | filters.VIDEO,
    #     bot.handle_media_group
    # ))
    
    print("\n✅ Бот успешно запущен!")
    print("=" * 70)
    
    # Информация о боте
    bot_info = await app.bot.get_me()
    print(f"\n🤖 Информация о боте:")
    print(f"   Имя: {bot_info.first_name}")
    print(f"   Username: @{bot_info.username}")
    print(f"   ID: {bot_info.id}")
    
    print(f"\n📱 Автоматическая отправка: {'✅ Настроена' if bot.admin_sender else '❌ Не настроена'}")
    if bot.admin_sender:
        print(f"   Отправка от: {bot.admin_sender.admin_phone}")
    
    print(f"\n⏰ Система напоминаний: ✅ Активна")
    print(f"   • Первое напоминание: через 5 минут")
    print(f"   • Финальное напоминание: через 10 минут")
    
    print("\n" + "=" * 70)
    print("📋 ПОДДЕРЖИВАЕМЫЕ ФОРМАТЫ ФАЙЛОВ:")
    print("=" * 70)
    print("📄 Документы: PDF, DOC, DOCX, XLS, XLSX, PPT, TXT")
    print("🖼️ Фотографии: JPEG, PNG, GIF")
    print("🎵 Аудио: MP3, WAV, OGG")
    print("🎤 Голосовые сообщения")
    print("🎬 Видео: MP4, AVI, MOV")
    print("📹 Видео-кружки")
    print("🎨 Анимации/GIF")
    print("📦 Архивы: ZIP, RAR, 7z")
    print("=" * 70)
    
    print("\n💡 ОСНОВНЫЕ ФУНКЦИИ:")
    print("📤 Отправить документ - для отправки документов получателям")
    print("➕ Добавить - для добавления контактов")
    print("📋 Контакты - просмотр списка контактов")
    print("📊 Отчеты - статистика и экспорт в PDF/TXT")
    print("🤖 Статус отправки - для просмотра статуса очереди")
    print("⏰ Система напоминаний - автоматические напоминания")
    print("🌐 Смена языка - русский/английский")
    print("=" * 70)
    
    print("\n🔄 Бот работает... Нажмите Ctrl+C для остановки")
    print("=" * 70)
    
    # Запуск бота
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    try:
        # Бесконечное ожидание
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\n🛑 Получен сигнал остановки...")
    finally:
        print("\n⏳ Останавливаю бота...")
        
        # Останавливаем систему напоминаний
        if bot.reminder_task:
            bot.reminder_task.cancel()
            print("   ✅ Система напоминаний остановлена")
        
        # Останавливаем отправитель
        if bot.admin_sender:
            bot.admin_sender.running = False
            print("   ✅ Автоматическая отправка остановлена")
        
        # Останавливаем бота
        await app.stop()
        await app.shutdown()
        
        print("\n" + "=" * 70)
        print("✅ БОТ ОСТАНОВЛЕН")
        print("=" * 70)
        print(f"📅 Время остановки: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        print("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
