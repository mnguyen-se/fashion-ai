"""
Outfit service — AI gợi ý phối đồ dựa trên message của user.

CHỈ 1 API DUY NHẤT:
  generate_outfits(db, message, max_outfits=3)

Flow:
  message → ai_service.parse_intent() → occasion, category_want, style_hint, min_price, max_price
  → category_want cụ thể (top/bottom/dress/accessory) → trả N sản phẩm đơn lẻ đúng slot đó
  → category_want = full_outfit (hoặc không rõ) → tổ hợp top+bottom / dress + outer/accessory,
    chấm điểm phối màu theo COLOR_RULES + occasion tag + giá.

Không dùng ChromaDB, embedding. Chỉ dùng COLOR_RULES + occasion tags + parse_intent (Ollama NLU).
"""
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.services import ai_service
import asyncio

from app.models.product import Product, Category
from app.models.schemas import CartItem
from app.core.color_rules import get_compatible_colors, normalize_color

CATALOG_STATUS = "AVAILABLE"
CANDIDATE_LIMIT = 12
NEUTRALS = {"black", "white", "gray", "beige", "navy", "cream", "camel"}

SLOT_CATEGORY_NAMES = {
    "top": ["top", "áo thun"],
    "bottom": ["bottom"],
    "dress": ["dresses"],
    "outer": ["blazers"],
    "accessory": ["bag"],
}

ALL_SLOTS = ["top", "bottom", "dress", "outer", "accessory"]

OCCASION_DISPLAY = {
    "wedding": "đám cưới", "office": "đi làm", "beach": "đi biển",
    "party": "tiệc", "date": "hẹn hò", "sport": "thể thao",
    "outdoor": "dã ngoại", "formal": "trang trọng", "casual": "dạo phố",
}


# ═════════════════════════════════════════════════════
# PUBLIC — 1 API duy nhất
# ═════════════════════════════════════════════════════

async def generate_outfits(
    db: Session,
    message: str,
    max_outfits: int = 3,
) -> dict:
    if not message or not message.strip():
        return {"outfits": [], "message": "Vui lòng nhập yêu cầu, ví dụ: 'gợi ý đồ đi biển' hoặc 'áo sơ mi công sở dưới 300k'."}

    intent = await ai_service.parse_intent(message, cart_items=[])

    occasion_tags = [intent.occasion] if intent.occasion else ["casual"]
    occasion_display = OCCASION_DISPLAY.get(intent.occasion, "dịp thường ngày")

    if intent.category_want == "shoes":
        return {"outfits": [], "message": "Xin lỗi, shop hiện chưa hỗ trợ gợi ý giày. Bạn thử hỏi về áo/quần/đầm/blazer/túi nhé."}

    if intent.category_want in ("top", "bottom", "dress", "accessory"):
        outfits = await _single_slot_outfits(
            intent.category_want, occasion_tags, intent.style_hint,
            intent.min_price, intent.max_price, occasion_display, db, max_outfits,
        )
    else:
        outfits = await _combo_outfits(
            occasion_tags, occasion_display, intent.style_hint, intent.min_price, intent.max_price, db, max_outfits,
        )

    if not outfits:
        return {
            "outfits": [],
            "message": f"Không tìm thấy sản phẩm phù hợp cho '{message}'. Bạn thử mô tả khác hoặc nới ngân sách xem sao.",
            "occasion": occasion_display,
            "occasion_tags": occasion_tags,
        }

    return {
        "message": f"Gợi ý {len(outfits)} bộ để {occasion_display} theo yêu cầu của bạn.",
        "occasion": occasion_display,
        "occasion_tags": occasion_tags,
        "outfits": outfits,
    }


# ═════════════════════════════════════════════════════
# PATH 1: category cụ thể (top/bottom/dress/accessory)
# ═════════════════════════════════════════════════════

async def _single_slot_outfits(
    slot: str,
    occasion_tags: list[str],
    style_hint: str | None,
    min_price: int | None,
    max_price: int | None,
    occasion_display: str,
    db: Session,
    max_outfits: int,
) -> list[dict]:
    candidates = _get_catalog_candidates(slot, occasion_tags, db, set(), CANDIDATE_LIMIT, min_price, max_price)
    if style_hint:
        candidates = _rank_by_style(candidates, style_hint) or candidates
    picked = candidates[:max_outfits]

    outfits = []
    for i, item in enumerate(picked):
        items_info = [_item_info(item, selected=False)]
        color_reason = await ai_service.generate_color_reason(items_info, occasion_display)
        outfits.append({
            "outfit_number": i + 1,
            "score": None,
            "items": items_info,
            "description": _describe(items_info),
            "color_reason": color_reason,
        })
    return outfits


# ═════════════════════════════════════════════════════
# PATH 2: full_outfit — tổ hợp top+bottom / dress + outer/accessory
# ═════════════════════════════════════════════════════

async def _combo_outfits(
    occasion_tags: list[str],
    occasion_display: str,
    style_hint: str | None,
    min_price: int | None,
    max_price: int | None,
    db: Session,
    max_outfits: int,
) -> list[dict]:
    groups = {
        "top":       _get_catalog_candidates("top", occasion_tags, db, set(), CANDIDATE_LIMIT, min_price, max_price),
        "bottom":    _get_catalog_candidates("bottom", occasion_tags, db, set(), CANDIDATE_LIMIT, min_price, max_price),
        "dress":     _get_catalog_candidates("dress", occasion_tags, db, set(), CANDIDATE_LIMIT, min_price, max_price),
        "outer":     _get_catalog_candidates("outer", occasion_tags, db, set(), CANDIDATE_LIMIT, min_price, max_price),
        "accessory": _get_catalog_candidates("accessory", occasion_tags, db, set(), CANDIDATE_LIMIT, min_price, max_price),
    }

    scored = _score_all_combinations(groups, occasion_filter=occasion_tags)
    best = _pick_diverse(scored, max_outfits)
    return await _format_outfits(best, occasion_display)


def _get_catalog_candidates(
    slot: str,
    occasion_tags: list[str] | None,
    db: Session,
    exclude_ids: set[str],
    limit: int,
    min_price: int | None = None,
    max_price: int | None = None,
) -> list[CartItem]:
    names = SLOT_CATEGORY_NAMES[slot]

    query = db.query(Product).filter(
        Product.status == CATALOG_STATUS,
        Product.category_ref.has(func.lower(Category.name).in_(names)),
    )
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    products = [p for p in query.all() if str(p.id) not in exclude_ids]

    if occasion_tags:
        matched = [p for p in products if any(t in (p.ai_tags or []) for t in occasion_tags)]
        pool = matched if matched else products
    else:
        pool = products

    return [
        CartItem(
            product_id=str(p.id),
            product_name=p.title or "Không tên",
            color=normalize_color(p.color or "black"),
            category=slot,
            occasions=p.ai_tags or [],
        )
        for p in pool[:limit]
    ]


def _rank_by_style(candidates: list[CartItem], style_hint: str) -> list[CartItem]:
    hint = style_hint.lower().strip()
    matched = [c for c in candidates if hint in c.product_name.lower()]
    rest = [c for c in candidates if c not in matched]
    return matched + rest


# ═════════════════════════════════════════════════════
# CORE LOGIC — chấm điểm tổ hợp (giữ nguyên từ bản trước)
# ═════════════════════════════════════════════════════

def _score_all_combinations(groups: dict, occasion_filter: list[str] | None) -> list:
    tops, bottoms, dresses = groups["top"], groups["bottom"], groups["dress"]
    outers, accessories = groups["outer"], groups["accessory"]
    scored = []

    for top in tops:
        for bottom in bottoms:
            score = _score_color_pair(top.color, bottom.color)
            if occasion_filter:
                score += _occasion_bonus(top, occasion_filter)
                score += _occasion_bonus(bottom, occasion_filter)
            outfit = {"items": [top, bottom], "score": score, "base_ids": (top.product_id, bottom.product_id)}
            _attach_optional(outfit, [top, bottom], outers, occasion_filter, weight=0.3)
            _attach_optional(outfit, [top, bottom], accessories, occasion_filter, weight=0.2)
            scored.append(outfit)

    for dress in dresses:
        score = 1.0
        if occasion_filter:
            score += _occasion_bonus(dress, occasion_filter)
        outfit = {"items": [dress], "score": score, "base_ids": (dress.product_id,)}
        _attach_optional(outfit, [dress], outers, occasion_filter, weight=0.3)
        _attach_optional(outfit, [dress], accessories, occasion_filter, weight=0.2)
        scored.append(outfit)

    return scored


def _score_color_pair(color1: str, color2: str) -> float:
    c1, c2 = normalize_color(color1), normalize_color(color2)
    if c1 == c2:
        return 0.6
    compatible = get_compatible_colors(c1)
    if c2 in compatible:
        if c1 in NEUTRALS and c2 in NEUTRALS:
            return 1.2
        if c1 in NEUTRALS or c2 in NEUTRALS:
            return 1.0
        return 0.8
    return 0.1


def _occasion_bonus(item: CartItem, occasion_tags: list[str]) -> float:
    if not item.occasions:
        return 0.0
    for tag in occasion_tags:
        if tag in item.occasions:
            return 0.5
    return 0.0


def _attach_optional(outfit, anchors, candidates, occasion_filter, weight):
    if not candidates:
        return
    best = _best_match_item(anchors, candidates, occasion_filter)
    if best is None:
        return
    outfit["items"].append(best)
    avg = sum(_score_color_pair(a.color, best.color) for a in anchors) / len(anchors)
    outfit["score"] += avg * weight
    if occasion_filter:
        outfit["score"] += _occasion_bonus(best, occasion_filter) * weight


def _best_match_item(anchors, candidates, occasion_filter):
    best, best_score = None, -1.0
    for c in candidates:
        score = sum(_score_color_pair(a.color, c.color) for a in anchors) / len(anchors)
        if occasion_filter:
            score += _occasion_bonus(c, occasion_filter)
        if score > best_score:
            best, best_score = c, score
    return best if best_score > 0.5 else None


def _pick_diverse(scored: list, max_n: int) -> list:
    sorted_outfits = sorted(scored, key=lambda x: x["score"], reverse=True)
    selected, used_ids = [], set()
    for outfit in sorted_outfits:
        if len(selected) >= max_n:
            break
        if not any(bid in used_ids for bid in outfit["base_ids"]):
            selected.append(outfit)
            used_ids.update(outfit["base_ids"])
    if len(selected) < max_n:
        for outfit in sorted_outfits:
            if outfit not in selected:
                selected.append(outfit)
            if len(selected) >= max_n:
                break
    return selected


# ═════════════════════════════════════════════════════
# FORMAT
# ═════════════════════════════════════════════════════

def _item_info(item: CartItem, selected: bool) -> dict:
    return {
        "product_id": item.product_id,
        "name": item.product_name,
        "category": item.category,
        "color": item.color,
        "occasions": item.occasions,
        "selected_by_user": selected,
    }


async def _format_outfits(best: list, occasion_display: str | None = None) -> list:
    async def _build_one(i: int, outfit: dict) -> dict:
        items_info = [_item_info(item, selected=False) for item in outfit["items"]]
        color_reason = await ai_service.generate_color_reason(items_info, occasion_display)
        return {
            "outfit_number": i + 1,
            "score": round(outfit["score"], 2),
            "items": items_info,
            "description": _describe(items_info),
            "color_reason": color_reason,
        }

    tasks = [_build_one(i, outfit) for i, outfit in enumerate(best)]
    return list(await asyncio.gather(*tasks))


def _describe(items: list[dict]) -> str:
    return " + ".join(f"{i['name']} ({i['color']})" for i in items)