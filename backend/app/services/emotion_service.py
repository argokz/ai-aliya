from __future__ import annotations

from app.schemas import EmotionType


class EmotionService:
    """Lightweight heuristic to drive eye animation in the frontend."""

    def detect(self, user_text: str, assistant_text: str) -> EmotionType:
        text = f"{user_text} {assistant_text}".lower()

        if "?" in user_text or any(k in text for k in ("почему", "как", "зачем", "когда")):
            return "thinking"
        if any(k in text for k in ("отлично", "супер", "класс", "рад", "спасибо")):
            return "happy"
        if any(k in text for k in ("груст", "плохо", "устал", "больно", "тревог")):
            return "empathetic"
        if any(k in text for k in ("вау", "неожидан", "серьезно", "ого")):
            return "surprised"
        if any(k in text for k in ("прости", "жаль", "сожалею")):
            return "sad"
        return "neutral"
