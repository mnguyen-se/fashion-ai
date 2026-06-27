from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
import base64
import uuid
import asyncio

from app.db.database import get_db
from app.services import outfit_service
from app.services.image_service import process_outfit_with_gemini

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


async def _build_outfit_images(outfits: list[dict], db: Session) -> list[dict]:
    results = []

    for i, outfit in enumerate(outfits):
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
            results.append({
                "outfit_number": outfit["outfit_number"],
                "image_b64":     base64.b64encode(outfit_img).decode(),
                "outfit":        outfit,
            })

        # Delay 15 giây giữa các bộ để tránh rate limit
        if i < len(outfits) - 1:
            print(f"Chờ 15s trước khi generate bộ tiếp theo...")
            await asyncio.sleep(15)

    return results


# ─────────────────────────────────────────
# 1. Phối đồ tự động có ảnh
# ─────────────────────────────────────────

@router.get("/wardrobe/{user_id}/outfits/image")
async def generate_wardrobe_outfits_image(
    user_id:     str,
    max_outfits: int = 3,
    db:          Session = Depends(get_db),
):
    result = outfit_service.generate_outfits_from_wardrobe(user_id, db, max_outfits)

    if not result["outfits"]:
        return {"error": result["message"], "outfits": []}

    outfit_results = await _build_outfit_images(result["outfits"], db)

    if not outfit_results:
        return {"error": "Không tạo được ảnh", "outfits": []}

    return {
        "message": result["message"],
        "outfits": [
            {
                "outfit_number": r["outfit_number"],
                "image_b64":     f"data:image/png;base64,{r['image_b64']}",
                "items":         r["outfit"]["items"],
                "description":   r["outfit"]["description"],
                "color_reason":  r["outfit"]["color_reason"],
            }
            for r in outfit_results
        ],
    }


# ─────────────────────────────────────────
# 2. Phối đồ theo dịp có ảnh
# ─────────────────────────────────────────

class OccasionRequest(BaseModel):
    message: str


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
        return {"error": result["message"], "outfits": []}

    outfit_results = await _build_outfit_images(result["outfits"], db)

    if not outfit_results:
        return {"error": "Không tạo được ảnh", "outfits": []}

    return {
        "message":  result["message"],
        "occasion": result.get("occasion", ""),
        "outfits": [
            {
                "outfit_number": r["outfit_number"],
                "image_b64":     f"data:image/png;base64,{r['image_b64']}",
                "items":         r["outfit"]["items"],
                "description":   r["outfit"]["description"],
                "color_reason":  r["outfit"]["color_reason"],
            }
            for r in outfit_results
        ],
    }


# ─────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────

@router.get("/health")
def health_check():
    return {"status": "ok"}