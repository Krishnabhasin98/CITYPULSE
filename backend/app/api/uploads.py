"""Evidence uploads.

Community actions (extra evidence, a repair photo, an after-photo proving a fix)
need a URL to point at, so this endpoint stores a validated image and returns
its public path.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from ..core.security import get_current_user
from ..models.user import User
from ..services.errors import ValidationError
from ..services.storage import MAX_UPLOAD_BYTES, UPLOAD_DIR, save_upload

router = APIRouter(prefix="/api/uploads", tags=["Uploads"])


@router.post("/evidence", summary="Upload a photo and get back its URL")
def upload_evidence(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if file is None or not file.filename:
        raise ValidationError("No file received.")
    url = save_upload(file)
    return {
        "url": url,
        "uploaded_by": current_user.name,
        "max_upload_mb": MAX_UPLOAD_BYTES / 1024 / 1024,
        "storage": str(UPLOAD_DIR),
    }
