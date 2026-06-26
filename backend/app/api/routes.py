from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
import base64
import uuid

from app.db.database import get_db
from app.services import outfit_service
from app.services.image_service import (
    process_outfit_with_gemini,
    compose_all_outfits,
)

router = APIRouter()


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def _get_image_url_for_wardrobe_item(wardrobe_item_id: str, db: Session) -> str | None:
    from app.models.product import WardrobeItem, Product

    wardrobe = db.query(WardrobeItem).filter(
        WardrobeItem.id == uuid.UUID(wardrobe_item_id)
    ).first()

    if not wardrobe:
        return None

    if wardrobe.image_url:
        return wardrobe.image_url

    if wardrobe.product_id:
        product = db.query(Product).filter(Product.id == wardrobe.product_id).first()
        if product and product.images and len(product.images) > 0:
            return product.images[0]

    return None


async def _build_outfit_images(outfits: list[dict], db: Session) -> list[bytes]:
    outfit_imgs = []

    for outfit in outfits:
        items_with_urls = []

        for item in outfit["items"]:
            image_url = _get_image_url_for_wardrobe_item(item["product_id"], db)
            items_with_urls.append({
                "name":      item["name"],
                "category":  item["category"],
                "image_url": image_url,
            })

        outfit_img = process_outfit_with_gemini(items_with_urls)
        if outfit_img:
            outfit_imgs.append(outfit_img)

    return outfit_imgs


# ─────────────────────────────────────────
# 1. Phối đồ tự động (không theo dịp)
# ─────────────────────────────────────────

@router.get("/wardrobe/{user_id}/outfits")
def generate_wardrobe_outfits(
    user_id:     str,
    max_outfits: int = 3,
    db:          Session = Depends(get_db),
):
    return outfit_service.generate_outfits_from_wardrobe(user_id, db, max_outfits)


@router.get("/wardrobe/{user_id}/outfits/image")
async def generate_wardrobe_outfits_image(
    user_id:     str,
    max_outfits: int = 3,
    db:          Session = Depends(get_db),
):
    result = outfit_service.generate_outfits_from_wardrobe(user_id, db, max_outfits)

    if not result["outfits"]:
        return {"error": result["message"], "outfit_image": None}

    outfit_imgs = await _build_outfit_images(result["outfits"], db)
    if not outfit_imgs:
        return {"error": "Không tạo được ảnh", "outfit_image": None}

    labels    = [f"Bộ {o['outfit_number']}" for o in result["outfits"]]
    final_img = compose_all_outfits(outfit_imgs, labels)
    final_b64 = base64.b64encode(final_img).decode()

    return {
        "outfit_image": f"data:image/png;base64,{final_b64}",
        "outfits":      result["outfits"],
        "message":      result["message"],
    }


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


@router.post("/wardrobe/{user_id}/outfits/occasion/image")
async def generate_outfits_occasion_image(
    user_id:     str,
    body:        OccasionRequest,
    max_outfits: int = 3,
    db:          Session = Depends(get_db),
):
    result = outfit_service.generate_outfits_by_occasion(
        user_id, body.message, db, max_outfits
    )

    if not result["outfits"]:
        return {"error": result["message"], "outfit_image": None}

    outfit_imgs = await _build_outfit_images(result["outfits"], db)
    if not outfit_imgs:
        return {"error": "Không tạo được ảnh", "outfit_image": None}

    labels    = [f"Bộ {o['outfit_number']}" for o in result["outfits"]]
    final_img = compose_all_outfits(outfit_imgs, labels)
    final_b64 = base64.b64encode(final_img).decode()

    return {
        "outfit_image": f"data:image/png;base64,{final_b64}",
        "outfits":      result["outfits"],
        "message":      result["message"],
        "occasion":     result.get("occasion", ""),
    }


# ─────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────

@router.get("/health")
def health_check():
    return {"status": "ok"}