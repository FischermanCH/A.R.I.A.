from __future__ import annotations

import contextlib
import imaplib
import smtplib
import time
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import EmailMessage
from typing import Any, Callable

RecipeText = Callable[..., str]


def decode_mail_header(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw))).strip()
    except Exception:
        return raw


class RecipeMessagingRuntime:
    def __init__(
        self,
        *,
        get_connection_profile: Callable[[str, str], Any],
        format_timestamp: Callable[[str], str],
        truncate_text: Callable[[str, int], str],
        recipe_text: RecipeText,
    ) -> None:
        self.get_connection_profile = get_connection_profile
        self.format_timestamp = format_timestamp
        self.truncate_text = truncate_text
        self.recipe_text = recipe_text

    def _text(self, language: str, key: str, default: str, **values: Any) -> str:
        return self.recipe_text(language, key, default, **values)

    def execute_email_send(self, connection_ref: str, content: str, *, language: str = "de") -> str:
        connection = self.get_connection_profile("email", connection_ref)
        host = str(getattr(connection, "smtp_host", "")).strip()
        user = str(getattr(connection, "user", "")).strip()
        password = str(getattr(connection, "password", "")).strip()
        from_email = str(getattr(connection, "from_email", "")).strip() or user
        to_email = str(getattr(connection, "to_email", "")).strip()
        port = int(getattr(connection, "port", 587) or 587)
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)
        use_ssl = bool(getattr(connection, "use_ssl", False))
        starttls = bool(getattr(connection, "starttls", True))
        body = str(content or "").strip()
        if not host:
            raise ValueError(self._text(language, "message_1805", "SMTP host is missing in the profile."))
        if not user:
            raise ValueError(self._text(language, "message_1807", "SMTP user is missing in the profile."))
        if not password:
            raise ValueError(self._text(language, "message_1809", "SMTP password is missing in the profile."))
        if not to_email:
            raise ValueError(self._text(language, "message_1811", "Default recipient is missing in the SMTP profile."))
        if not body:
            raise ValueError(self._text(language, "message_1813", "Email content is missing."))

        msg = EmailMessage()
        msg["From"] = from_email
        msg["To"] = to_email
        msg["Subject"] = self._text(language, "message_1818", "ARIA message")
        msg.set_content(body)

        try:
            if use_ssl:
                server = smtplib.SMTP_SSL(host, max(1, port), timeout=max(5, timeout_seconds))
            else:
                server = smtplib.SMTP(host, max(1, port), timeout=max(5, timeout_seconds))
            with server:
                server.ehlo()
                if starttls and not use_ssl:
                    server.starttls()
                    server.ehlo()
                server.login(user, password)
                server.send_message(msg)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(self._text(language, "message_1834", "SMTP send failed: {exc}", exc=exc)) from exc
        return self._text(language, "message_1835", "Email sent via `{connection_ref}` to {to_email}", connection_ref=connection_ref, to_email=to_email)

    def _open_imap_connection(self, connection_ref: str, *, language: str = "de") -> tuple[imaplib.IMAP4, str]:
        connection = self.get_connection_profile("imap", connection_ref)
        host = str(getattr(connection, "host", "")).strip()
        user = str(getattr(connection, "user", "")).strip()
        password = str(getattr(connection, "password", "")).strip()
        mailbox = str(getattr(connection, "mailbox", "INBOX")).strip() or "INBOX"
        port = int(getattr(connection, "port", 993) or 993)
        use_ssl = bool(getattr(connection, "use_ssl", True))
        if not host:
            raise ValueError(self._text(language, "message_1856", "IMAP host is missing in the profile."))
        if not user:
            raise ValueError(self._text(language, "message_1858", "IMAP user is missing in the profile."))
        if not password:
            raise ValueError(self._text(language, "message_1860", "IMAP password is missing in the profile."))
        try:
            client = imaplib.IMAP4_SSL(host, max(1, port)) if use_ssl else imaplib.IMAP4(host, max(1, port))
            status, _ = client.login(user, password)
            if status != "OK":
                raise ValueError(self._text(language, "message_1865", "IMAP login failed."))
            status, _ = client.select(mailbox, readonly=True)
            if status != "OK":
                raise ValueError(self._text(language, "message_1868", "IMAP mailbox not reachable: {mailbox}", mailbox=mailbox))
            return client, mailbox
        except Exception as exc:  # noqa: BLE001
            raise ValueError(self._text(language, "message_1871", "IMAP connection failed: {exc}", exc=exc)) from exc

    def execute_imap_read(self, connection_ref: str, *, language: str = "de") -> str:
        client, mailbox = self._open_imap_connection(connection_ref, language=language)
        try:
            status, data = client.search(None, "ALL")
            if status != "OK":
                raise ValueError(self._text(language, "message_1878", "IMAP search failed."))
            ids = [item for item in (data[0].split() if data and data[0] else [])][-5:]
            if not ids:
                return self._text(language, "message_1881", "Mailbox is empty: {mailbox}", mailbox=mailbox)
            lines = [self._text(language, "message_1882", "Latest emails from {mailbox}:", mailbox=mailbox)]
            for idx, msg_id in enumerate(reversed(ids), start=1):
                status, payload = client.fetch(msg_id, "(RFC822.HEADER)")
                if status != "OK" or not payload:
                    continue
                header_bytes = _first_header_bytes(payload)
                if not header_bytes:
                    continue
                msg = message_from_bytes(header_bytes)
                subject = decode_mail_header(msg.get("Subject", "")) or self._text(language, "message_1895", "(no subject)")
                sender = decode_mail_header(msg.get("From", "")) or "-"
                date = self.format_timestamp(msg.get("Date", ""))
                line = f"{idx}. {subject}"
                if date:
                    line += f" [{date}]"
                lines.append(line)
                lines.append(f"   {self._text(language, 'message_1902', 'From')}: {sender}")
            return self.truncate_text("\n".join(lines), 1400)
        finally:
            with contextlib.suppress(Exception):
                client.logout()

    def execute_imap_search(self, connection_ref: str, query: str, *, language: str = "de") -> str:
        term = str(query or "").strip()
        if not term:
            raise ValueError(self._text(language, "message_1911", "Search term for mail search is missing."))
        client, mailbox = self._open_imap_connection(connection_ref, language=language)
        try:
            status, data = client.search(None, "TEXT", f'"{term}"')
            if status != "OK":
                raise ValueError(self._text(language, "message_1916", "IMAP search failed."))
            ids = [item for item in (data[0].split() if data and data[0] else [])][-5:]
            if not ids:
                return self._text(language, "message_1919", "No matches in {mailbox} for “{term}”.", mailbox=mailbox, term=term)
            lines = [self._text(language, "message_1920", "Matches in {mailbox} for “{term}”:", mailbox=mailbox, term=term)]
            for idx, msg_id in enumerate(reversed(ids), start=1):
                status, payload = client.fetch(msg_id, "(RFC822.HEADER)")
                if status != "OK" or not payload:
                    continue
                header_bytes = _first_header_bytes(payload)
                if not header_bytes:
                    continue
                msg = message_from_bytes(header_bytes)
                subject = decode_mail_header(msg.get("Subject", "")) or self._text(language, "message_1933", "(no subject)")
                sender = decode_mail_header(msg.get("From", "")) or "-"
                date = self.format_timestamp(msg.get("Date", ""))
                line = f"{idx}. {subject}"
                if date:
                    line += f" [{date}]"
                lines.append(line)
                lines.append(f"   {self._text(language, 'message_1940', 'From')}: {sender}")
            return self.truncate_text("\n".join(lines), 1400)
        finally:
            with contextlib.suppress(Exception):
                client.logout()

    def execute_mqtt_publish(self, connection_ref: str, topic: str, content: str, *, language: str = "de") -> str:
        connection = self.get_connection_profile("mqtt", connection_ref)
        host = str(getattr(connection, "host", "")).strip()
        user = str(getattr(connection, "user", "")).strip()
        password = str(getattr(connection, "password", "")).strip()
        default_topic = str(getattr(connection, "topic", "")).strip()
        resolved_topic = str(topic or "").strip() or default_topic
        port = int(getattr(connection, "port", 1883) or 1883)
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)
        use_tls = bool(getattr(connection, "use_tls", False))
        payload = str(content or "").strip()
        if not host:
            raise ValueError(self._text(language, "message_1958", "MQTT host is missing in the profile."))
        if not user:
            raise ValueError(self._text(language, "message_1960", "MQTT user is missing in the profile."))
        if not password:
            raise ValueError(self._text(language, "message_1962", "MQTT password is missing in the profile."))
        if not resolved_topic:
            raise ValueError(self._text(language, "message_1964", "MQTT topic is missing. Configure it in the profile or provide it in the prompt."))
        if not payload:
            raise ValueError(self._text(language, "message_1966", "MQTT message is missing."))
        try:
            import paho.mqtt.client as mqtt  # type: ignore[import-not-found]
        except Exception as exc:
            raise ValueError(self._text(language, "message_1970", "Python module 'paho-mqtt' is missing. Please install it and restart ARIA.")) from exc

        result: dict[str, Any] = {"published": False, "rc": None}
        client = mqtt.Client()
        client.username_pw_set(user, password)
        if use_tls:
            client.tls_set()

        def _on_connect(_client: Any, _userdata: Any, _flags: Any, rc: int, _properties: Any = None) -> None:
            result["rc"] = rc
            if int(rc) == 0:
                info = _client.publish(resolved_topic, payload)
                result["published"] = bool(getattr(info, "rc", 1) == 0)
                with contextlib.suppress(Exception):
                    _client.disconnect()

        client.on_connect = _on_connect
        try:
            client.connect(host, max(1, port), keepalive=max(5, timeout_seconds))
            client.loop_start()
            deadline = time.time() + max(5, timeout_seconds)
            while not result["published"] and result["rc"] is None and time.time() < deadline:
                time.sleep(0.1)
            if result["rc"] is not None and int(result["rc"]) != 0:
                raise ValueError(self._text(language, "message_1996", "MQTT connect failed (rc={result_rc}).", result_rc=result["rc"]))
            if not result["published"]:
                raise ValueError(self._text(language, "message_1998", "MQTT publish failed or timed out."))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(self._text(language, "message_2000", "MQTT publish failed: {exc}", exc=exc)) from exc
        finally:
            with contextlib.suppress(Exception):
                client.loop_stop()
            with contextlib.suppress(Exception):
                client.disconnect()
        return self._text(language, "message_2006", "MQTT published via `{connection_ref}` on topic `{resolved_topic}`", connection_ref=connection_ref, resolved_topic=resolved_topic)


def _first_header_bytes(payload: Any) -> bytes:
    for part in payload:
        if isinstance(part, tuple) and len(part) > 1 and isinstance(part[1], (bytes, bytearray)):
            return bytes(part[1])
    return b""
