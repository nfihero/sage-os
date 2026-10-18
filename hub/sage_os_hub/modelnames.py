"""Cloud model lists a newcomer can choose from (Mac test, 17 Oct 2026; D42).

A provider's /models lists everything it serves: Gemini's has text-to-speech, image, music, robotics and
computer-use models next to the chat ones, and picking one of those just errors. Here the list is cut to models that
chat, the few best-known ones come first with a plain description, and every id gets a readable name.
"""
from __future__ import annotations

import re

# not chat models, or not chat on the OpenAI-compatible endpoint
NOT_CHAT = re.compile(
    r"(tts|audio|image|imagen|veo|lyria|music|robotics|computer-use|transcri|embed|whisper|dall-e|moderation|"
    r"realtime|live|nano-banana|aqa|sora|search-preview|-instruct|babbage|davinci|gpt-image|codex-mini-latest)", re.I)
FIRST = 4                                   # how many come first, before "More models"
UPPER = {"gpt": "GPT", "o3": "o3", "o4": "o4", "o1": "o1", "ai": "AI"}


def plain_id(model: str) -> str:
    return (model or "").removeprefix("models/")


def is_chat(model: str) -> bool:
    return not NOT_CHAT.search(plain_id(model))


def friendly(model: str) -> str:
    """'models/gemini-2.5-flash' -> 'Gemini 2.5 Flash'; 'gpt-5.4-mini' -> 'GPT-5.4 mini'."""
    m = plain_id(model)
    if m.lower().startswith("gpt-"):
        head, *rest = m[4:].split("-")
        return " ".join([f"GPT-{head}", *rest])
    def word(w: str) -> str:
        if re.fullmatch(r"\d+b", w, re.I) or w.lower() == "it":
            return w.upper()                          # 31b -> 31B, it (instruction-tuned) -> IT
        return UPPER.get(w.lower(), w[:1].upper() + w[1:])
    return " ".join(word(w) for w in m.split("-") if w)


def describe(model: str, provider: str) -> str:
    m = plain_id(model).lower()
    words = set(re.split(r"[-_.\s]", m))           # "gemini" contains "mini": match whole words
    if words & {"lite", "nano"}:
        return "the fastest and cheapest"
    if words & {"flash", "mini"}:
        return "fast, low cost" + (", has a free tier" if provider == "gemini" else "")
    if words & {"pro", "argon"}:
        return "the best answers; slower and costs more"
    if re.match(r"o\d", m):
        return "thinks before answering; slower"
    return "good all-round answers"


def arrange(provider: str, models: list[str], price_order: list[str]) -> list[dict]:
    """Chat models only: the first few best-known (in the price list's newest-first order) with a description, then
    the rest alphabetically. -> [{"id", "name", "note", "first"}]"""
    chat = [m for m in models if is_chat(m)]
    known = {plain_id(m).lower(): m for m in chat}
    first = [known[p] for p in price_order if p in known][:FIRST]
    rest = sorted((m for m in chat if m not in first), key=lambda m: plain_id(m).lower())
    return ([{"id": m, "name": friendly(m), "note": describe(m, provider), "first": True} for m in first]
            + [{"id": m, "name": friendly(m), "note": None, "first": False} for m in rest])
