"""Tiny solid-color PNG avatars for demo staff and customers (no external URLs)."""

from __future__ import annotations

import io

from django.core.files.base import ContentFile
from PIL import Image


def solid_avatar_file(name: str, hex_color: str, size: int = 256) -> ContentFile:
    color = hex_color.lstrip("#")
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    img = Image.new("RGB", (size, size), (r, g, b))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ContentFile(buf.read(), name=f"{name}.png")