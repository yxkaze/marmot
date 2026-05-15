"""
如流（InfoFlow）机器人 Webhook 渠道。

按如流机器人原生消息类型暴露发送方法：TEXT / LINK / MD / IMAGE，
其中 AT 仅可与 TEXT / LINK 组合使用。

零运行时依赖：使用 stdlib ``urllib.request`` 发送 POST。
"""
from __future__ import annotations

import base64
import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import ChannelError


class InfoFlowChannel:
    """如流机器人 Webhook 渠道。

    :param webhook_url: 机器人的 Webhook 地址（含 access_token 参数）
    :param to_ids: 默认接收方 id 列表（群聊为群 id）
    :param to_type: 接收方类型，默认 ``"GROUP"``
    :param timeout: HTTP 超时秒数，默认 10.0
    """

    def __init__(
        self,
        webhook_url: str,
        to_ids: list[int],
        to_type: str = "GROUP",
        timeout: float = 10.0,
    ) -> None:
        if not webhook_url:
            raise ValueError("webhook_url is required")
        if not to_ids:
            raise ValueError("to_ids must not be empty")
        self.webhook_url = webhook_url
        self.to_ids = list(to_ids)
        self.to_type = to_type
        self.timeout = timeout

    # ── 公共能力 ────────────────────────────────────────

    def send_text(
        self,
        content: str,
        *,
        at_user_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """发送 TEXT 消息，可选 @ 群成员。"""
        body: list[dict[str, Any]] = [{"type": "TEXT", "content": content}]
        if at_user_ids:
            body.extend(self._build_at_items(at_user_ids))
        return self._post(self._build_envelope(body))

    def send_link(
        self,
        title: str,
        url: str,
        *,
        at_user_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """发送 LINK 消息，可选 @ 群成员。"""
        body: list[dict[str, Any]] = [
            {"type": "LINK", "content": {"title": title, "url": url}}
        ]
        if at_user_ids:
            body.extend(self._build_at_items(at_user_ids))
        return self._post(self._build_envelope(body))

    def send_markdown(self, content: str) -> dict[str, Any]:
        """发送 MD 消息。MD 不支持 AT。"""
        body = [{"type": "MD", "content": content}]
        return self._post(self._build_envelope(body))

    def send_image(self, image: bytes | str | os.PathLike[str]) -> dict[str, Any]:
        """发送 IMAGE 消息。

        :param image: bytes 直接编码；str / PathLike 当作文件路径读取
        """
        if isinstance(image, (bytes, bytearray)):
            data = bytes(image)
        else:
            with open(image, "rb") as f:
                data = f.read()
        b64 = base64.b64encode(data).decode("utf-8")
        body = [{"type": "IMAGE", "content": b64}]
        return self._post(self._build_envelope(body))

    # ── 内部 ────────────────────────────────────────────

    def _build_envelope(self, body: list[dict[str, Any]]) -> dict[str, Any]:
        """构造如流消息信封。"""
        return {
            "message": {
                "header": {
                    "toid": list(self.to_ids),
                    "totype": self.to_type,
                    "msgtype": "MIXED",
                    "clientmsgid": int(time.time() * 1000),
                    "role": "robot",
                },
                "body": body,
            }
        }

    @staticmethod
    def _build_at_items(at_user_ids: list[int]) -> list[dict[str, Any]]:
        return [{"type": "AT", "content": str(uid)} for uid in at_user_ids]

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        """发送 POST 请求；非 2xx / 网络异常 → ChannelError。"""
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = Request(
            self.webhook_url,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                raw = resp.read()
        except HTTPError as e:
            raise ChannelError(
                f"InfoFlow HTTP error: {e.code} {e.reason}"
            ) from e
        except URLError as e:
            raise ChannelError(f"InfoFlow network error: {e.reason}") from e
        except OSError as e:
            raise ChannelError(f"InfoFlow OS error: {e}") from e

        if not (200 <= status < 300):
            raise ChannelError(f"InfoFlow non-2xx response: {status}")

        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise ChannelError(f"InfoFlow invalid JSON response: {e}") from e
