"""Shared prompt-safety helpers for untrusted scraped content."""


def delimited_text(text: str) -> str:
    return f"```\n{text}\n```"
