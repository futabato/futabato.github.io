"""Anthropic Claude API クライアント"""

import json
import logging
import os
import re

import httpx

log = logging.getLogger(__name__)


class ClaudeClient:
    """Claude API の薄いラッパー。httpx.Client のライフサイクルを管理する。"""

    def __init__(self, model: str):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.model = model
        self._client = httpx.Client(
            base_url="https://api.anthropic.com",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=90.0,
        )

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._client.close()

    def request(self, prompt: str, max_tokens: int = 4000) -> list[dict]:
        """プロンプトを送信し、JSONリストとしてパースして返す。"""
        resp = self._client.post(
            "/v1/messages",
            json={
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        if resp.status_code != 200:
            log.warning(f"API error {resp.status_code}: {resp.text[:500]}")
        resp.raise_for_status()

        data = resp.json()
        text = "".join(block.get("text", "") for block in data.get("content", []))
        text = re.sub(r"```json|```", "", text).strip()
        return json.loads(text)
