"""Local evidence storage.

Files stay on the same disk as the database — no bucket, no key, no cost. Two
things changed from the first version, both risk fixes:

* uploads are validated (content type + size) instead of writing whatever
  arrives, and
* filenames are still generated server-side, so a hostile filename cannot
  escape the upload directory.
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from .. import config
from .errors import ValidationError

logger = logging.getLogger("citypulse.storage")

UPLOAD_DIR = config.UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

EXTENSION_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "image/svg+xml": ".svg",
    "image/gif": ".gif",
}

MAX_UPLOAD_BYTES = int(config.MAX_UPLOAD_MB * 1024 * 1024)


def save_upload(file: UploadFile) -> str:
    """Persist an uploaded photo and return its public URL path."""
    if file is None or not file.filename:
        raise ValidationError("No file received.")

    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type and content_type not in EXTENSION_BY_TYPE:
        raise ValidationError(
            f"Unsupported image type '{content_type}'.",
            extra={"allowed": sorted(EXTENSION_BY_TYPE)},
        )

    payload = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(payload) > MAX_UPLOAD_BYTES:
        raise ValidationError(f"Image is larger than the {config.MAX_UPLOAD_MB:.0f} MB limit.")
    if not payload:
        raise ValidationError("The uploaded file is empty.")

    suffix = EXTENSION_BY_TYPE.get(
        content_type, Path(file.filename).suffix[:8].lower() or ".bin"
    )
    name = f"{uuid4().hex}{suffix}"
    destination = UPLOAD_DIR / name
    destination.write_bytes(payload)
    logger.info("Stored upload %s (%s bytes)", name, len(payload))
    return f"/uploads/{name}"


def upload_stats() -> dict:
    files = [path for path in UPLOAD_DIR.glob("*") if path.is_file()]
    return {
        "directory": str(UPLOAD_DIR),
        "files": len(files),
        "bytes": sum(path.stat().st_size for path in files),
        "max_upload_mb": config.MAX_UPLOAD_MB,
    }
