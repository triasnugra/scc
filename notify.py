from __future__ import annotations

import os


def send(text: str) -> None:
    print(text, flush=True)
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return
    try:
        import requests

        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      json={"chat_id": chat, "text": text[:3900]}, timeout=10)
    except Exception as e:  # notifikasi tidak boleh menjatuhkan bot
        print(f"[notify] gagal: {e}")
