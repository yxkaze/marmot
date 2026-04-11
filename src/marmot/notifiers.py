"""
Marmot Alert Framework — Notifiers

Notification channels: Webhook, Console, DingTalk, WeCom (企业微信),
Feishu (飞书), Email, and Phone (abstract stub).

Each notifier implements the ``Notifier`` base class with a single
``send(n: Notification)`` method.  Subclasses handle platform-specific
formatting and delivery.

Design philosophy:
    - Base class is a single-method interface — maximally simple.
    - Each platform formats its own payload; the framework is agnostic.
    - ``MarkdownWebhookNotifier`` wraps any webhook URL with Markdown content,
      useful for Slack, Discord, generic webhooks, etc.
    - ``EmailNotifier`` and ``PhoneNotifier`` are abstract-ready: they provide
      the interface and configuration, leaving the actual delivery to a
      user-supplied callback (to avoid hard dependencies on SMTP SDKs).
"""
from __future__ import annotations

import abc
import hashlib
import hmac
import json
import base64
import logging
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import URLError, HTTPError

from .models import Notification, utcnow, to_iso

logger = logging.getLogger("marmot.notifiers")

UTC = timezone.utc

# Colors for severity (used in Markdown/HTML notifiers)
_SEVERITY_EMOJI = {
    "info": "\u2139\ufe0f",
    "warning": "\u26a0\ufe0f",
    "error": "\u274c",
    "critical": "\U0001f6a8",
}

_STATE_ICON = {
    "firing": "\U0001f525",
    "resolved": "\u2705",
    "escalated": "\u2b06\ufe0f",
    "silenced": "\U0001f6ab",
    "pending": "\u23f3",
    "resolving": "\U0001f504",
}


# ═══════════════════════════════════════════════════════════════════════════
# Base
# ═══════════════════════════════════════════════════════════════════════════

class Notifier(abc.ABC):
    """Abstract base for all notification channels."""

    @abc.abstractmethod
    def send(self, n: Notification) -> bool:
        """Send a notification.  Return True on success."""
        ...


def _http_post(url: str, body: bytes, headers: dict[str, str],
               timeout: float = 5.0) -> bool:
    """Low-level HTTP POST helper used by webhook-based notifiers."""
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (URLError, HTTPError, OSError):
        logger.exception("HTTP POST to %s failed", url)
        return False


def _severity_emoji(severity: str) -> str:
    return _SEVERITY_EMOJI.get(severity, "")


def _state_icon(state: str) -> str:
    return _STATE_ICON.get(state, "")


# ═══════════════════════════════════════════════════════════════════════════
# Console (dev / debugging)
# ═══════════════════════════════════════════════════════════════════════════

class ConsoleNotifier(Notifier):
    """Print notification to stdout.  Ideal for development and debugging.

    Example::

        app.register_notifier("console", ConsoleNotifier())
    """

    def send(self, n: Notification) -> bool:
        ts = to_iso(n.sent_at) or utcnow().isoformat()
        emoji = _severity_emoji(n.severity)
        icon = _state_icon(n.state)
        print(
            f"[{ts}] {emoji} [{n.severity.upper()}] "
            f"{icon} {n.rule_name}: {n.message} "
            f"(state={n.state}, stage={n.stage})"
        )
        return True


# ═══════════════════════════════════════════════════════════════════════════
# Generic Webhook (raw JSON)
# ═══════════════════════════════════════════════════════════════════════════

class WebhookNotifier(Notifier):
    """Send the full notification dict as JSON to a generic webhook endpoint.

    Example::

        app.register_notifier("hook", WebhookNotifier(
            url="https://hooks.example.com/alerts",
        ))
    """

    def __init__(self, url: str, headers: dict[str, str] | None = None,
                 timeout: float = 5.0):
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout

    def send(self, n: Notification) -> bool:
        body = json.dumps(n.to_dict(), ensure_ascii=False).encode("utf-8")
        hdrs = {"Content-Type": "application/json", **self.headers}
        return _http_post(self.url, body, hdrs, self.timeout)


# ═══════════════════════════════════════════════════════════════════════════
# Markdown Webhook (Slack / Discord / generic Markdown receivers)
# ═══════════════════════════════════════════════════════════════════════════

class MarkdownWebhookNotifier(Notifier):
    """Send a Markdown-formatted payload to a webhook.

    Compatible with Slack incoming webhooks, Discord webhooks,
    and any service that accepts JSON with a ``"text"`` field.

    Example::

        app.register_notifier("slack", MarkdownWebhookNotifier(
            url="https://hooks.slack.com/services/...",
        ))
    """

    def __init__(self, url: str, headers: dict[str, str] | None = None,
                 timeout: float = 5.0):
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout

    def _format(self, n: Notification) -> str:
        emoji = _severity_emoji(n.severity)
        icon = _state_icon(n.state)
        labels_str = ", ".join(f"{k}={v}" for k, v in n.labels.items()) if n.labels else ""
        label_line = f"\nLabels: {labels_str}" if labels_str else ""
        ts = to_iso(n.sent_at) or ""
        return (
            f"{emoji} **[{n.severity.upper()}]** {icon} **{n.rule_name}**\n\n"
            f"> {n.message}\n\n"
            f"State: `{n.state}` | Stage: `{n.stage}`{label_line}\n"
            f"Time: {ts}"
        )

    def send(self, n: Notification) -> bool:
        payload = {"text": self._format(n)}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        hdrs = {"Content-Type": "application/json", **self.headers}
        return _http_post(self.url, body, hdrs, self.timeout)


# ═══════════════════════════════════════════════════════════════════════════
# DingTalk (钉钉自定义机器人)
# ═══════════════════════════════════════════════════════════════════════════

class DingTalkNotifier(Notifier):
    """Send alerts to a DingTalk (钉钉) custom robot webhook.

    Supports optional HMAC signing for security.

    Parameters
    ----------
    webhook_url : str
        The complete webhook URL (including ``access_token``).
    secret : str | None
        If provided, the webhook payload will be signed with this secret.
    timeout : float
        Request timeout in seconds.

    Example::

        app.register_notifier("ding", DingTalkNotifier(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx",
            secret="SEC...",
        ))
    """

    DINGTALK_API = "https://oapi.dingtalk.com/robot/send"

    def __init__(self, webhook_url: str, secret: str | None = None,
                 timeout: float = 5.0):
        self.webhook_url = webhook_url
        self.secret = secret
        self.timeout = timeout

    def _sign_url(self) -> str:
        if not self.secret:
            return self.webhook_url
        ts = int(datetime.now(UTC).timestamp() * 1000)
        string_to_sign = f"{ts}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        sep = "&" if "?" in self.webhook_url else "?"
        return f"{self.webhook_url}{sep}timestamp={ts}&sign={sign}"

    def _format(self, n: Notification) -> dict[str, Any]:
        emoji = _severity_emoji(n.severity)
        icon = _state_icon(n.state)
        labels_str = (
            ", ".join(f"**{k}**: {v}" for k, v in n.labels.items())
            if n.labels else ""
        )
        label_line = f"\n{labels_str}" if labels_str else ""
        ts = to_iso(n.sent_at) or ""

        text = (
            f"{emoji} **[{n.severity.upper()}]** {icon} **{n.rule_name}**\n\n"
            f"> {n.message}\n\n"
            f"State: {n.state} | Stage: {n.stage}{label_line}\n"
            f"Time: {ts}"
        )
        return {
            "msgtype": "markdown",
            "markdown": {
                "title": f"[{n.severity.upper()}] {n.rule_name}",
                "text": text,
            },
        }

    def send(self, n: Notification) -> bool:
        url = self._sign_url()
        payload = self._format(n)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        hdrs = {"Content-Type": "application/json; charset=utf-8"}
        return _http_post(url, body, hdrs, self.timeout)


# ═══════════════════════════════════════════════════════════════════════════
# WeCom / 企业微信
# ═══════════════════════════════════════════════════════════════════════════

class WeComNotifier(Notifier):
    """Send alerts to a WeCom (企业微信) group robot webhook.

    Parameters
    ----------
    webhook_url : str
        The complete webhook URL including ``key`` parameter.
    mentioned_list : list[str] | None
        User IDs to @mention (use ``"@all"`` for everyone).

    Example::

        app.register_notifier("wecom", WeComNotifier(
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
            mentioned_list=["@all"],
        ))
    """

    def __init__(self, webhook_url: str,
                 mentioned_list: list[str] | None = None,
                 timeout: float = 5.0):
        self.webhook_url = webhook_url
        self.mentioned_list = mentioned_list
        self.timeout = timeout

    def _format(self, n: Notification) -> dict[str, Any]:
        emoji = _severity_emoji(n.severity)
        icon = _state_icon(n.state)
        labels_str = (
            ", ".join(f"{k}: {v}" for k, v in n.labels.items())
            if n.labels else ""
        )
        label_line = f"\n{labels_str}" if labels_str else ""
        ts = to_iso(n.sent_at) or ""

        content = (
            f"{emoji} **[{n.severity.upper()}]** {icon} **{n.rule_name}**\n"
            f"> {n.message}\n"
            f"State: {n.state} | Stage: {n.stage}{label_line}\n"
            f"Time: {ts}"
        )

        payload: dict[str, Any] = {
            "msgtype": "markdown",
            "markdown": {"content": content},
        }
        if self.mentioned_list:
            payload["markdown"]["mentioned_list"] = self.mentioned_list
        return payload

    def send(self, n: Notification) -> bool:
        payload = self._format(n)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        hdrs = {"Content-Type": "application/json; charset=utf-8"}
        return _http_post(self.webhook_url, body, hdrs, self.timeout)


# ═══════════════════════════════════════════════════════════════════════════
# Feishu / 飞书
# ═══════════════════════════════════════════════════════════════════════════

class FeishuNotifier(Notifier):
    """Send alerts to a Feishu (飞书) custom bot webhook.

    Parameters
    ----------
    webhook_url : str
        The complete webhook URL.
    secret : str | None
        Optional signing secret for verification.

    Example::

        app.register_notifier("feishu", FeishuNotifier(
            webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
            secret="your_signing_secret",
        ))
    """

    def __init__(self, webhook_url: str, secret: str | None = None,
                 timeout: float = 5.0):
        self.webhook_url = webhook_url
        self.secret = secret
        self.timeout = timeout

    def _sign(self) -> dict[str, str]:
        if not self.secret:
            return {}
        ts = int(datetime.now(UTC).timestamp())
        string_to_sign = f"{ts}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        return {"timestamp": str(ts), "sign": sign}

    def _format(self, n: Notification) -> dict[str, Any]:
        emoji = _severity_emoji(n.severity)
        labels_str = (
            ", ".join(f"{k}: {v}" for k, v in n.labels.items())
            if n.labels else ""
        )
        label_line = f"\n{labels_str}" if labels_str else ""
        ts = to_iso(n.sent_at) or ""

        content = [
            {"tag": "text", "text": f"{emoji} "},
            {"tag": "text", "text": f"[{n.severity.upper()}] ", "style": ["bold"]},
            {"tag": "text", "text": f"{n.rule_name}\n"},
            {"tag": "text", "text": f"  {n.message}\n"},
            {"tag": "text", "text": f"  State: {n.state} | Stage: {n.stage}"},
        ]
        if label_line:
            content.append({"tag": "text", "text": label_line})
        content.append({"tag": "text", "text": f"\n  Time: {ts}"})

        payload: dict[str, Any] = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"[{n.severity.upper()}] {n.rule_name}",
                    },
                    "template": self._severity_color(n.severity),
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": "".join(
                        c.get("text", "") for c in content
                    )}},
                ],
            },
        }
        payload.update(self._sign())
        return payload

    @staticmethod
    def _severity_color(severity: str) -> str:
        return {
            "info": "blue",
            "warning": "orange",
            "error": "red",
            "critical": "red",
        }.get(severity, "grey")

    def send(self, n: Notification) -> bool:
        payload = self._format(n)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        hdrs = {"Content-Type": "application/json; charset=utf-8"}
        return _http_post(self.webhook_url, body, hdrs, self.timeout)


# ═══════════════════════════════════════════════════════════════════════════
# Email (callback-based — zero hard dependencies)
# ═══════════════════════════════════════════════════════════════════════════

class EmailNotifier(Notifier):
    """Send alerts via email using a user-supplied send callback.

    This notifier does NOT bundle any email library — the caller provides
    a ``send_fn`` that receives the formatted subject and body, giving full
    control over SMTP configuration, template engines, etc.

    Parameters
    ----------
    send_fn : Callable[[str, str, list[str]], bool]
        A function ``(subject, body, to_addresses) -> bool``.
    to : list[str]
        Recipient email addresses.
    from_addr : str | None
        Sender address (passed to ``send_fn`` as extra context).

    Example::

        import smtplib
        from email.mime.text import MIMEText

        def my_send(subject, body, to):
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = "alert@example.com"
            msg["To"] = ", ".join(to)
            with smtplib.SMTP("smtp.example.com") as s:
                s.send_message(msg)
            return True

        app.register_notifier("email", EmailNotifier(
            send_fn=my_send,
            to=["oncall@example.com"],
        ))
    """

    def __init__(
        self,
        send_fn: Callable[[str, str, list[str]], bool],
        to: list[str],
        from_addr: str | None = None,
    ):
        self.send_fn = send_fn
        self.to = to
        self.from_addr = from_addr

    def _format(self, n: Notification) -> tuple[str, str]:
        emoji = _severity_emoji(n.severity)
        labels_str = (
            ", ".join(f"  {k}: {v}" for k, v in n.labels.items())
            if n.labels else ""
        )
        label_block = f"\nLabels:\n{labels_str}" if labels_str else ""
        ts = to_iso(n.sent_at) or ""

        subject = f"[Marmot {emoji} {n.severity.upper()}] {n.rule_name}: {n.message}"
        body = (
            f"Marmot Alert\n"
            f"{'=' * 40}\n\n"
            f"Rule:    {n.rule_name}\n"
            f"Severity: {n.severity}\n"
            f"State:   {n.state}\n"
            f"Stage:   {n.stage}\n"
            f"Message: {n.message}\n"
            f"{label_block}\n\n"
            f"Time: {ts}\n"
        )
        return subject, body

    def send(self, n: Notification) -> bool:
        subject, body = self._format(n)
        try:
            return self.send_fn(subject, body, self.to)
        except Exception:
            logger.exception("Email send failed")
            return False


# ═══════════════════════════════════════════════════════════════════════════
# Phone / SMS (callback-based — zero hard dependencies)
# ═══════════════════════════════════════════════════════════════════════════

class PhoneNotifier(Notifier):
    """Send alerts via SMS / phone call using a user-supplied callback.

    Like ``EmailNotifier``, this avoids hard dependencies on any SMS
    provider SDK.  The caller provides a ``send_fn``.

    Parameters
    ----------
    send_fn : Callable[[str, list[str]], bool]
        A function ``(message, phone_numbers) -> bool``.
    to : list[str]
        Recipient phone numbers.

    Example::

        def my_sms(message, phones):
            # Integrate with Twilio / Aliyun SMS / etc.
            for p in phones:
                print(f"SMS to {p}: {message}")
            return True

        app.register_notifier("sms", PhoneNotifier(
            send_fn=my_sms,
            to=["+8613800138000"],
        ))
    """

    def __init__(
        self,
        send_fn: Callable[[str, list[str]], bool],
        to: list[str],
    ):
        self.send_fn = send_fn
        self.to = to

    def _format(self, n: Notification) -> str:
        emoji = _severity_emoji(n.severity)
        labels_str = (
            " ".join(f"{k}={v}" for k, v in n.labels.items())
            if n.labels else ""
        )
        label_part = f" {labels_str}" if labels_str else ""
        return (
            f"[Marmot{emoji}][{n.severity.upper()}] "
            f"{n.rule_name}: {n.message}{label_part}"
        )

    def send(self, n: Notification) -> bool:
        # Only send SMS for critical / error severity
        if n.severity not in ("critical", "error"):
            logger.debug(
                "PhoneNotifier: skipping %s severity (only critical/error)",
                n.severity,
            )
            return True

        message = self._format(n)
        try:
            return self.send_fn(message, self.to)
        except Exception:
            logger.exception("Phone/SMS send failed")
            return False
