import os

PORT = int(os.getenv("PORT", "8000"))


def greeting() -> str:
    return "hello"
