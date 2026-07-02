from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.services import outfit_service

router = APIRouter()


# ─────────────────────────────────────────
# 1. Phối đồ tự động
# ─────────────────────────────────────────

@router.get("/wardrobe/{user_id}/outfits")
def generate_wardrobe_outfits(
    user_id:     str,
    max_outfits: int = 3,
    db:          Session = Depends(get_db),
):
    return outfit_service.generate_outfits_from_wardrobe(user_id, db, max_outfits)


# ─────────────────────────────────────────
# 2. Phối đồ theo dịp
# ─────────────────────────────────────────

class OccasionRequest(BaseModel):
    message: str


@router.post("/wardrobe/{user_id}/outfits/occasion")
def generate_outfits_by_occasion(
    user_id:     str,
    body:        OccasionRequest,
    max_outfits: int = 3,
    db:          Session = Depends(get_db),
):
    return outfit_service.generate_outfits_by_occasion(
        user_id, body.message, db, max_outfits
    )


# ─────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────

@router.get("/health")
def health_check():
    from app.services.ai_service import check_ollama_connection
    return {
        "status": "ok",
        "ollama": "connected" if check_ollama_connection() else "disconnected ⚠️",
    }