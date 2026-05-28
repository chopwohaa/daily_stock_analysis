# -*- coding: utf-8 -*-
"""ntfy notification sender."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import unquote, urlparse, urlunparse

import requests

from src.config import Config
from src.formatters import chunk_content_by_max_bytes


logger = logging.getLogger(__name__)


def resolve_ntfy_endpoint(ntfy_url: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Split NTFY_URL into server root and topic from the final path segment."""
    raw_url = (ntfy_url or "").strip().rstrip("/")
    if not raw_url:
        return None, None

    parsed = urlparse(raw_url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None, None

    path_segments = [segment for segment in parsed.path.split("/") if segment]
    if not path_segments:
        return None, None

    topic = unquote(path_segments[-1]).strip()
    if not topic:
        return None, None

    root_path = "/".join(path_segments[:-1])
    server_url = urlunparse(
        parsed._replace(
            path=f"/{root_path}" if root_path else "",
            params="",
            query="",
            fragment="",
        )
    ).rstrip("/")

    return server_url, topic


class NtfySender:
    """Send Markdown text notifications through the ntfy JSON publish API."""

    def __init__(self, config: Config):
        self._ntfy_url = getattr(config, "ntfy_url", None)
        self._ntfy_token = getattr(config, "ntfy_token", None)
        self._webhook_verify_ssl = getattr(config, "webhook_verify_ssl", True)

    def _is_ntfy_configured(self) -> bool:
        return bool(self._ntfy_url)

    def _resolve_ntfy_endpoint(self) -> Tuple[Optional[str], Optional[str]]:
        return resolve_ntfy_endpoint(self._ntfy_url)

    def send_to_ntfy(
        self,
        content: str,
        title: Optional[str] = None,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """Publish a notification to ntfy using a JSON body with UTF-8 text."""
        if not self._is_ntfy_configured():
            logger.warning("ntfy URL 未配置，跳过推送")
            return False

        server_url, topic = self._resolve_ntfy_endpoint()
        if not server_url or not topic:
            logger.error("NTFY_URL 必须是包含 topic path 的完整 endpoint，例如 https://ntfy.sh/my-topic")
            return False

        if title is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            title = f"📈 股票分析报告 - {date_str}"

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "daily_stock_analysis",
        }
        token = (self._ntfy_token or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # ntfy.sh 限制整个请求体 ≤ 4096 字节；预留空间给 JSON 结构 / topic / title
        _NTFY_MAX_BODY_BYTES = 4096
        _NTFY_PAYLOAD_OVERHEAD = 600
        budget = _NTFY_MAX_BODY_BYTES - _NTFY_PAYLOAD_OVERHEAD

        content_bytes = len(content.encode("utf-8"))
        if content_bytes > budget:
            logger.info(
                "ntfy 消息内容超长 (%d 字节/%d 字符)，将分批发送",
                content_bytes,
                len(content),
            )
            return self._send_ntfy_chunked(
                content,
                title=title,
                topic=topic,
                server_url=server_url,
                headers=headers,
                timeout_seconds=timeout_seconds,
                budget=budget,
            )

        payload = {
            "topic": topic,
            "title": title,
            "message": content,
            "markdown": True,
        }

        return self._post_ntfy(server_url, payload, headers, timeout_seconds)

    # ------------------------------------------------------------------
    # 分块发送（与项目其他 sender 保持一致）
    # ------------------------------------------------------------------

    def _send_ntfy_chunked(
        self,
        content: str,
        *,
        title: str,
        topic: str,
        server_url: str,
        headers: dict,
        timeout_seconds: Optional[float],
        budget: int,
    ) -> bool:
        """Split long content into chunks and send each as a separate ntfy message."""
        chunks = chunk_content_by_max_bytes(content, budget, add_page_marker=True)
        total = len(chunks)
        success_count = 0

        logger.info("ntfy 分批发送：共 %d 批", total)

        for i, chunk in enumerate(chunks):
            chunk_title = f"{title} ({i + 1}/{total})" if total > 1 else title
            payload = {
                "topic": topic,
                "title": chunk_title,
                "message": chunk,
                "markdown": True,
            }
            if self._post_ntfy(server_url, payload, headers, timeout_seconds):
                success_count += 1
                logger.info("ntfy 第 %d/%d 批发送成功", i + 1, total)
            else:
                logger.error("ntfy 第 %d/%d 批发送失败", i + 1, total)

            if i < total - 1:
                time.sleep(1)

        return success_count == total

    # ------------------------------------------------------------------
    # 底层 POST 请求
    # ------------------------------------------------------------------

    def _post_ntfy(
        self,
        server_url: str,
        payload: dict,
        headers: dict,
        timeout_seconds: Optional[float],
    ) -> bool:
        """Execute a single ntfy POST request."""
        try:
            response = requests.post(
                server_url,
                json=payload,
                headers=headers,
                timeout=timeout_seconds or 10,
                verify=self._webhook_verify_ssl,
            )
            if 200 <= response.status_code < 300:
                logger.info("ntfy 消息发送成功")
                return True

            logger.error("ntfy 请求失败: HTTP %s", response.status_code)
            logger.debug("ntfy 响应内容: %s", response.text)
            return False
        except requests.exceptions.Timeout:
            logger.error("发送 ntfy 消息失败: 请求超时")
            return False
        except requests.exceptions.RequestException as exc:
            logger.error("发送 ntfy 消息失败: 网络请求异常")
            logger.debug("ntfy 请求异常类型: %s", type(exc).__name__)
            return False
        except Exception as exc:
            logger.error("发送 ntfy 消息失败: 未知异常")
            logger.debug("ntfy 未知异常类型: %s", type(exc).__name__)
            return False
