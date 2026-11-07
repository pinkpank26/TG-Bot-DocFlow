from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

from config import settings
from repositories.admin_sessions import AdminSessionsRepository
from services.audit import log_action
from services.security import decrypt_session, encrypt_session


class AdminSessionService:
    def __init__(self):
        self.repo = AdminSessionsRepository()

    async def start_auth(self, admin_user_id: int, phone: str) -> str:
        temp = StringSession()
        client = TelegramClient(temp, settings.api_id, settings.api_hash)
        await client.connect()
        try:
            sent = await client.send_code_request(phone)
            self.repo.save_auth_state(
                admin_user_id=admin_user_id,
                phone=phone,
                phone_code_hash=sent.phone_code_hash,
                status="waiting_code",
                temp_session=encrypt_session(client.session.save()),
            )
            log_action(admin_user_id, "admin_auth_flow_started", "admin_auth_states", str(admin_user_id), {"phone": phone})
            return "Код отправлен в Telegram"
        finally:
            await client.disconnect()

    async def submit_code(self, admin_user_id: int, code: str) -> str:
        state = self.repo.get_auth_state(admin_user_id)
        if not state or state["status"] not in {"waiting_code", "code_sent"}:
            raise ValueError("Нет активной авторизации. Начните заново.")
        if state["expires_at"] and datetime.fromisoformat(state["expires_at"]).replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            self.repo.set_auth_status(admin_user_id, "expired")
            raise ValueError("Сессия авторизации истекла")

        client = TelegramClient(StringSession(decrypt_session(state["temp_session_string"])), settings.api_id, settings.api_hash)
        await client.connect()
        try:
            try:
                await client.sign_in(phone=state["phone"], code=code, phone_code_hash=state["phone_code_hash"])
            except SessionPasswordNeededError:
                self.repo.set_auth_status(admin_user_id, "waiting_password", encrypt_session(client.session.save()), attempts_inc=True)
                return "Нужен пароль 2FA. Отправьте его сообщением."

            me = await client.get_me()
            encrypted = encrypt_session(client.session.save())
            self.repo.save_authorized_account(
                admin_user_id=admin_user_id,
                phone=state["phone"],
                telegram_user_id=me.id,
                username=me.username,
                first_name=me.first_name,
                encrypted_session=encrypted,
            )
            self.repo.set_auth_status(admin_user_id, "authorized", encrypted)
            log_action(admin_user_id, "admin_authorized", "admin_telegram_accounts", str(admin_user_id), {"telegram_user_id": me.id})
            return "Telegram аккаунт успешно подключен"
        finally:
            await client.disconnect()

    async def submit_password(self, admin_user_id: int, password: str) -> str:
        state = self.repo.get_auth_state(admin_user_id)
        if not state or state["status"] != "waiting_password":
            raise ValueError("Сначала введите код из Telegram")

        client = TelegramClient(StringSession(decrypt_session(state["temp_session_string"])), settings.api_id, settings.api_hash)
        await client.connect()
        try:
            await client.sign_in(password=password)
            me = await client.get_me()
            encrypted = encrypt_session(client.session.save())
            self.repo.save_authorized_account(
                admin_user_id=admin_user_id,
                phone=state["phone"],
                telegram_user_id=me.id,
                username=me.username,
                first_name=me.first_name,
                encrypted_session=encrypted,
            )
            self.repo.set_auth_status(admin_user_id, "authorized", encrypted)
            log_action(admin_user_id, "admin_authorized_2fa", "admin_telegram_accounts", str(admin_user_id), {"telegram_user_id": me.id})
            return "Telegram аккаунт успешно подключен"
        finally:
            await client.disconnect()

    async def is_session_valid(self, admin_user_id: int) -> bool:
        account = self.repo.get_account(admin_user_id)
        if not account:
            return False
        session = decrypt_session(account["session_encrypted"])
        client = TelegramClient(StringSession(session), settings.api_id, settings.api_hash)
        await client.connect()
        try:
            authorized = await client.is_user_authorized()
            return bool(authorized)
        finally:
            await client.disconnect()

    async def get_client(self, admin_user_id: int) -> TelegramClient:
        account = self.repo.get_account(admin_user_id)
        if not account:
            raise ValueError("Telegram аккаунт не подключен")
        session = decrypt_session(account["session_encrypted"])
        client = TelegramClient(StringSession(session), settings.api_id, settings.api_hash)
        await client.connect()
        return client

    def remove_session(self, admin_user_id: int) -> None:
        self.repo.delete_account(admin_user_id)
        log_action(admin_user_id, "admin_session_removed", "admin_telegram_accounts", str(admin_user_id), {})


admin_session_service = AdminSessionService()
