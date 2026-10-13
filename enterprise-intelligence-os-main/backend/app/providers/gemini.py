from __future__ import annotations

import json
import os
from urllib import error, request

from .base import ProviderNotConfiguredError


class GeminiProvider:
    name = "Google Gemini"
    simulated = False

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not self.api_key:
            raise ProviderNotConfiguredError("GEMINI_API_KEY is not configured")
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    def complete(self, prompt: str) -> str:
        payload = json.dumps(
            {"contents": [{"parts": [{"text": prompt}]}]},
            ensure_ascii=False,
        ).encode("utf-8")
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        req = request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"Gemini request failed ({exc.code}): {detail}") from exc
        except (error.URLError, TimeoutError) as exc:
            raise RuntimeError("Gemini could not be reached. Check network access.") from exc
        try:
            return body["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Gemini returned an unexpected response.") from exc
