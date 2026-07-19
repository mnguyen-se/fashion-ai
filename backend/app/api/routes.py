from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.services import outfit_service

router = APIRouter()


class GenerateOutfitsRequest(BaseModel):
    message: str


@router.post("/wardrobe/{user_id}/outfits")
async def generate_outfits(
    user_id:     str,   # giữ lại để tương thích route Java, hiện chưa dùng tới trong logic
    body:        GenerateOutfitsRequest,
    max_outfits: int = Query(default=3),
    db:          Session = Depends(get_db),
):
    return await outfit_service.generate_outfits(db, body.message, max_outfits)


@router.get("/health")
def health_check():
    from app.services.ai_service import check_ollama_connection
    return {"status": "ok", "ollama": "connected" if check_ollama_connection() else "disconnected ⚠️"}