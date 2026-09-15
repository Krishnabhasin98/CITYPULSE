from typing import Optional

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    """JSON body used by API clients and tests (the app posts multipart)."""

    description: str = Field(min_length=8, max_length=5000)
    title: Optional[str] = Field(default=None, max_length=255)
    category: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    address: Optional[str] = Field(default=None, max_length=500)
    pincode: Optional[str] = Field(default=None, max_length=10)
    image_url: Optional[str] = Field(default=None, max_length=1000)


class PostResponse(BaseModel):
    id: int
    user_id: int
    description: str
    category: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    address: Optional[str]
    pincode: Optional[str] = None
    image_url: Optional[str] = None
    status: str
    trust_status: Optional[str] = None

    class Config:
        from_attributes = True


class ClusterResult(BaseModel):
    message: str
    clustered: bool
    match_reason: str
    analysis: dict
    credits: int
    credits_awarded: int
    incident: dict
    post_id: int
