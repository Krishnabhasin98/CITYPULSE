"""Citizen report ingestion.

Both endpoints route through the same service call, so a report created by the
web app (multipart with a photo) and one created by an API client (JSON) are
classified, clustered, credited and audited identically.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..core.security import get_current_user
from ..database import get_db
from ..models.post import Post
from ..models.user import User
from ..schemas.post import PostCreate, PostResponse
from ..services.intelligence import ingest_post, serialize_incident
from ..services.storage import save_upload
from ai.fake_detection.trust_engine import detect_ai_image

router = APIRouter(prefix="/api/posts", tags=["Reports"])


def _response(result: dict) -> dict:
    return {
        "message": "Clustered into an existing incident" if result["clustered"] else "New incident created",
        "clustered": result["clustered"],
        "match_reason": result["match_reason"],
        "analysis": result["analysis"],
        "trust": result["trust_eval"],
        "credits": result["credits"],
        "credits_awarded": result["credits_awarded"],
        "area_context": result["area_context"],
        "incident": serialize_incident(result["incident"]),
        "post_id": result["post"].id,
    }


@router.post("/", summary="Create a report with an optional photo")
def create_post(
    description: str = Form(..., min_length=8),
    category: str | None = Form(None),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    address: str | None = Form(None),
    pincode: str | None = Form(None),
    title: str | None = Form(None),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ai_image_detection = None
    if image is not None and image.filename:
        original_bytes = image.file.read()
        image.file.seek(0)
        ai_image_detection = detect_ai_image(original_bytes, image.filename)
        image_url = save_upload(image)
    else:
        image_url = None
    result = ingest_post(
        db,
        current_user,
        {
            "description": description,
            "category": category,
            "latitude": latitude,
            "longitude": longitude,
            "address": address,
            "pincode": pincode,
            "title": title,
            "image_url": image_url,
            "ai_image_detection": ai_image_detection,
        },
    )
    return _response(result)


@router.post("/json", summary="Create a report from JSON (no photo upload)")
def create_post_json(
    payload: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = ingest_post(db, current_user, payload.model_dump())
    return _response(result)


@router.get("/", response_model=list[PostResponse])
def get_posts(limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(Post)
        .order_by(Post.created_at.desc(), Post.id.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )


@router.get("/mine", response_model=list[PostResponse])
def my_posts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Post)
        .filter(Post.user_id == current_user.id)
        .order_by(Post.created_at.desc(), Post.id.desc())
        .all()
    )


@router.get("/{post_id}")
def get_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Report not found")
    return post
