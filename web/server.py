import asyncio
import html
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from telethon.errors import PasswordHashInvalidError, PhoneCodeExpiredError, PhoneCodeInvalidError

from repositories.admin_sessions import AdminSessionsRepository
from services.admin_sessions import admin_session_service
from services.web_auth import web_auth_service


logger = logging.getLogger(__name__)
repo = AdminSessionsRepository()

_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop
    with _loop_lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            threading.Thread(target=_loop.run_forever, daemon=True, name="web-auth-loop").start()
        return _loop


def run_async(coro, timeout: float = 60.0):
    return asyncio.run_coroutine_threadsafe(coro, _get_loop()).result(timeout=timeout)


PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Подключение Telegram аккаунта</title>
<style>
body{{font-family:-apple-system,Segoe UI,Arial,sans-serif;max-width:420px;margin:40px auto;padding:0 16px;color:#1a1a1a}}
h1{{font-size:18px}}
input{{width:100%;padding:10px;margin:8px 0;box-sizing:border-box;font-size:16px;border:1px solid #ccc;border-radius:6px}}
button{{padding:10px 16px;font-size:16px;cursor:pointer;border:0;border-radius:6px;background:#2481cc;color:#fff;width:100%}}
button.secondary{{background:#e6e6e6;color:#1a1a1a;margin-top:8px}}
.error{{color:#b00020;margin:8px 0}}
.ok{{color:#0a7a2f;margin:8px 0}}
p.hint{{color:#666;font-size:14px}}
</style></head><body>
<h1>Подключение Telegram аккаунта</h1>
{body}
</body></html>"""


def _render(body: str) -> bytes:
    return PAGE.format(body=body).encode("utf-8")


def _error_block(error: str | None) -> str:
    return f'<p class="error">{html.escape(error)}</p>' if error else ""


def phone_form(token: str, error: str | None = None) -> bytes:
    body = f"""
    {_error_block(error)}
    <p class="hint">Код никогда не отправляется через Telegram-сообщения — вводите его прямо здесь.</p>
    <form method="post" action="/auth/{html.escape(token)}/phone">
      <label>Номер телефона (формат +7...)</label>
      <input type="text" name="phone" placeholder="+7…" required>
      <button type="submit">Отправить код</button>
    </form>
    """
    return _render(body)


def code_form(token: str, error: str | None = None) -> bytes:
    t = html.escape(token)
    body = f"""
    {_error_block(error)}
    <p>Код отправлен в Telegram. Введите его ниже.</p>
    <form method="post" action="/auth/{t}/code">
      <label>Код из Telegram</label>
      <input type="text" name="code" inputmode="numeric" autocomplete="one-time-code" required>
      <button type="submit">Подтвердить</button>
    </form>
    <form method="post" action="/auth/{t}/resend">
      <button type="submit" class="secondary">Отправить код заново</button>
    </form>
    """
    return _render(body)


def password_form(token: str, error: str | None = None) -> bytes:
    body = f"""
    {_error_block(error)}
    <p>На аккаунте включена двухфакторная аутентификация. Введите пароль.</p>
    <form method="post" action="/auth/{html.escape(token)}/password">
      <label>Пароль 2FA</label>
      <input type="password" name="password" required>
      <button type="submit">Подтвердить</button>
    </form>
    """
    return _render(body)


def success_page() -> bytes:
    return _render('<p class="ok">Telegram аккаунт успешно подключён. Можно вернуться в бота.</p>')


def error_page(message: str) -> bytes:
    return _render(f'<p class="error">{html.escape(message)}</p>')


class AuthRequestHandler(BaseHTTPRequestHandler):
    server_version = "AdminAuthWeb/1.0"

    def log_message(self, fmt, *args):
        logger.info("web-auth %s - %s", self.address_string(), fmt % args)

    def _send_html(self, content: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _read_form(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        parsed = parse_qs(raw.decode("utf-8"))
        return {k: v[0] for k, v in parsed.items()}

    def do_GET(self):
        parts = self.path.split("?", 1)[0].strip("/").split("/")
        if len(parts) != 2 or parts[0] != "auth":
            self._send_html(error_page("Страница не найдена"), 404)
            return
        token = parts[1]
        admin_user_id = web_auth_service.resolve_token(token)
        if admin_user_id is None:
            self._send_html(
                error_page("Ссылка недействительна или истекла. Вернитесь в бота и начните подключение заново."), 403
            )
            return

        account = repo.get_account(admin_user_id)
        if account and account["session_status"] == "active":
            self._send_html(success_page())
            return

        state = repo.get_auth_state(admin_user_id)
        if not state or state["status"] == "expired":
            self._send_html(phone_form(token))
            return
        if state["status"] == "waiting_password":
            self._send_html(password_form(token))
            return
        self._send_html(code_form(token))

    def do_POST(self):
        parts = self.path.split("?", 1)[0].strip("/").split("/")
        if len(parts) != 3 or parts[0] != "auth":
            self._send_html(error_page("Страница не найдена"), 404)
            return
        token, step = parts[1], parts[2]
        admin_user_id = web_auth_service.resolve_token(token)
        if admin_user_id is None:
            self._send_html(
                error_page("Ссылка недействительна или истекла. Вернитесь в бота и начните подключение заново."), 403
            )
            return

        form = self._read_form()

        if step == "phone":
            phone = form.get("phone", "").strip()
            if not phone:
                self._send_html(phone_form(token, "Введите номер телефона"))
                return
            try:
                run_async(admin_session_service.start_auth(admin_user_id, phone))
            except Exception:
                logger.exception("web-auth: start_auth failed for user %s", admin_user_id)
                self._send_html(phone_form(token, "Не удалось отправить код. Проверьте номер и попробуйте снова."))
                return
            self._redirect(f"/auth/{token}")
            return

        if step == "resend":
            state = repo.get_auth_state(admin_user_id)
            if not state:
                self._send_html(phone_form(token, "Начните заново — введите номер телефона."))
                return
            try:
                run_async(admin_session_service.start_auth(admin_user_id, state["phone"]))
            except Exception:
                logger.exception("web-auth: resend failed for user %s", admin_user_id)
                self._send_html(code_form(token, "Не удалось отправить код повторно."))
                return
            self._redirect(f"/auth/{token}")
            return

        if step == "code":
            code = form.get("code", "").strip()
            try:
                msg = run_async(admin_session_service.submit_code(admin_user_id, code))
            except PhoneCodeInvalidError:
                self._send_html(code_form(token, "Неверный код, попробуйте ещё раз."))
                return
            except PhoneCodeExpiredError:
                self._send_html(code_form(token, "Код устарел. Нажмите «Отправить код заново»."))
                return
            except Exception:
                logger.exception("web-auth: submit_code failed for user %s", admin_user_id)
                self._send_html(code_form(token, "Не удалось подтвердить код."))
                return
            if "2FA" not in msg:
                web_auth_service.invalidate(token)
            self._redirect(f"/auth/{token}")
            return

        if step == "password":
            password = form.get("password", "")
            try:
                run_async(admin_session_service.submit_password(admin_user_id, password))
            except PasswordHashInvalidError:
                self._send_html(password_form(token, "Неверный пароль, попробуйте ещё раз."))
                return
            except Exception:
                logger.exception("web-auth: submit_password failed for user %s", admin_user_id)
                self._send_html(password_form(token, "Не удалось подтвердить пароль."))
                return
            web_auth_service.invalidate(token)
            self._redirect(f"/auth/{token}")
            return

        self._send_html(error_page("Неизвестное действие"), 404)


def start_web_auth_server(host: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), AuthRequestHandler)
    threading.Thread(target=server.serve_forever, daemon=True, name="web-auth-http").start()
    logger.info("Web auth server listening on %s:%s", host, port)
    return server
