"""
Outfit service — phối đồ từ wardrobe của user.

2 tính năng:
1. generate_outfits_from_wardrobe() — tự động phối 3 bộ đẹp nhất
2. generate_outfits_by_occasion()   — phối theo dịp user nhắn

Không dùng catalog, ChromaDB, embedding.
Chỉ dùng COLOR_RULES + occasion tags.
"""
from sqlalchemy.orm import Session

from app.models.product import Product, WardrobeItem
from app.models.schemas import CartItem
from app.core.color_rules import get_compatible_colors, normalize_color
from app.core.occasion_rules import get_occasion_tags, OCCASION_MAP

ACTIVE_WARDROBE_STATUSES = ["OWNED"]
NEUTRALS = {"black", "white", "gray", "beige", "navy", "cream", "camel"}


# ═════════════════════════════════════════════════════
# PUBLIC — 2 hàm chính
# ═════════════════════════════════════════════════════

def generate_outfits_from_wardrobe(
    user_id: str,
    db: Session,
    max_outfits: int = 3,
) -> dict:
    """
    Tự động phối đồ từ wardrobe — không lọc theo dịp.
    Ví dụ: 3 áo (xanh/đỏ/đen) + 3 quần (xanh/đỏ/trắng)
    → chọn 3 bộ đẹp nhất theo màu sắc.
    """
    all_items = _get_wardrobe_items(user_id, db)
    if not all_items:
        return {"outfits": [], "message": "Tủ đồ trống!"}

    groups = _group_by_category(all_items)
    valid, msg = _check_groups(groups)
    if not valid:
        return {"outfits": [], "message": msg, "wardrobe_summary": {k: len(v) for k, v in groups.items()}}

    scored  = _score_all_combinations(groups, occasion_filter=None)
    best    = _pick_diverse(scored, max_outfits)
    outfits = _format_outfits(best)

    return {
        "message": f"Tìm được {len(outfits)} bộ phù hợp nhất từ {len(all_items)} món đồ.",
        "wardrobe_summary": {k: len(v) for k, v in groups.items()},
        "outfits": outfits,
    }


def generate_outfits_by_occasion(
    user_id: str,
    message: str,
    db: Session,
    max_outfits: int = 3,
) -> dict:
    occasion_tags    = _parse_occasion_from_message(message)
    occasion_display = _occasion_display_name(message)

    all_items = _get_wardrobe_items(user_id, db)
    if not all_items:
        return {"outfits": [], "message": "Tủ đồ của bạn hiện đang trống!"}

    groups = _group_by_category(all_items)
    valid, msg = _check_groups(groups)
    if not valid:
        return {
            "outfits": [],
            "message": msg,
            "wardrobe_summary": {k: len(v) for k, v in groups.items()}
        }

    # Kiểm tra xem có ít nhất 1 áo VÀ 1 quần phù hợp occasion không
    tops_matched    = [i for i in groups["top"]    if any(t in i.occasions for t in occasion_tags)]
    bottoms_matched = [i for i in groups["bottom"] if any(t in i.occasions for t in occasion_tags)]

    has_occasion_match = len(tops_matched) > 0 and len(bottoms_matched) > 0

    if not has_occasion_match:
        # Tìm trong catalog
        catalog_suggestions = _get_catalog_suggestions(occasion_tags, db, limit=6)

        if catalog_suggestions:
            return {
                "message": f"Trong tủ đồ của bạn hiện không có trang phục phù hợp để {occasion_display}. Bạn có thể tham khảo các sản phẩm sau từ cửa hàng:",
                "occasion": occasion_display,
                "occasion_tags": occasion_tags,
                "wardrobe_suggestion": False,
                "outfits": [],
                "catalog_suggestions": catalog_suggestions,
                "wardrobe_summary": {k: len(v) for k, v in groups.items()},
            }
        else:
            return {
                "message": f"Trong tủ đồ của bạn hiện không có trang phục phù hợp để {occasion_display} và cửa hàng cũng chưa có sản phẩm phù hợp.",
                "occasion": occasion_display,
                "occasion_tags": occasion_tags,
                "wardrobe_suggestion": False,
                "outfits": [],
                "catalog_suggestions": [],
                "wardrobe_summary": {k: len(v) for k, v in groups.items()},
            }

    # Có đồ phù hợp → phối từ tủ
    scored  = _score_all_combinations(groups, occasion_filter=occasion_tags)
    best    = _pick_diverse(scored, max_outfits)
    outfits = _format_outfits(best)

    return {
        "message":             f"Gợi ý {len(outfits)} bộ để {occasion_display}.",
        "occasion":            occasion_display,
        "occasion_tags":       occasion_tags,
        "wardrobe_suggestion": True,
        "outfits":             outfits,
        "catalog_suggestions": [],
        "wardrobe_summary":    {k: len(v) for k, v in groups.items()},
    }
def _get_catalog_suggestions(occasion_tags: list[str], db: Session, limit: int = 6) -> list[dict]:
    from app.models.product import Product

    products = db.query(Product).filter(
        Product.status == "AVAILABLE",
    ).all()

    # Filter theo occasion tags
    matched = []
    for product in products:
        tags = product.ai_tags or []
        if any(tag in tags for tag in occasion_tags):
            matched.append(product)

    if not matched:
        return []

    # Phân nhóm theo category, lấy 2 mỗi loại
    groups = {"top": [], "bottom": [], "shoes": [], "accessory": []}
    for p in matched:
        cat = (p.category or "top").lower()
        if cat in groups and len(groups[cat]) < 2:
            groups[cat].append(p)

    # Gộp lại
    result = []
    for items in groups.values():
        result.extend(items)

    # Nếu không đủ thì fill thêm từ matched
    if len(result) < limit:
        existing_ids = {p.id for p in result}
        for p in matched:
            if p.id not in existing_ids:
                result.append(p)
            if len(result) >= limit:
                break

    return [p.to_dict() for p in result[:limit]]


# ═════════════════════════════════════════════════════
# CORE LOGIC
# ═════════════════════════════════════════════════════

def _score_all_combinations(groups: dict, occasion_filter: list[str] | None) -> list:
    """Tính điểm tất cả tổ hợp top + bottom (+ shoes + accessory)."""
    tops      = groups["top"]
    bottoms   = groups["bottom"]
    shoes     = groups["shoes"]
    accessory = groups["accessory"]

    scored = []
    for top in tops:
        for bottom in bottoms:
            score  = _score_color_pair(top.color, bottom.color)

            if occasion_filter:
                score += _occasion_bonus(top, occasion_filter)
                score += _occasion_bonus(bottom, occasion_filter)

            outfit = {"items": [top, bottom], "score": score}

            if shoes:
                best_shoe = _best_match_item(top, bottom, shoes, occasion_filter)
                if best_shoe:
                    outfit["items"].append(best_shoe)
                    outfit["score"] += _score_color_pair(top.color, best_shoe.color) * 0.3
                    if occasion_filter:
                        outfit["score"] += _occasion_bonus(best_shoe, occasion_filter) * 0.3

            if accessory:
                best_acc = _best_match_item(top, bottom, accessory, occasion_filter)
                if best_acc:
                    outfit["items"].append(best_acc)
                    outfit["score"] += _score_color_pair(top.color, best_acc.color) * 0.2
                    if occasion_filter:
                        outfit["score"] += _occasion_bonus(best_acc, occasion_filter) * 0.2

            scored.append(outfit)

    return scored


def _score_color_pair(color1: str, color2: str) -> float:
    """
    Điểm phối màu:
      Cả 2 neutral  → 1.2
      1 neutral      → 1.0
      Tone-on-tone   → 0.6
      Phối được      → 0.8
      Không phối     → 0.1
    """
    c1 = normalize_color(color1)
    c2 = normalize_color(color2)

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
    """Thưởng 0.5 điểm nếu đồ có tag khớp occasion."""
    if not item.occasions:
        return 0.0
    for tag in occasion_tags:
        if tag in item.occasions:
            return 0.5
    return 0.0


def _best_match_item(
    top: CartItem,
    bottom: CartItem,
    candidates: list[CartItem],
    occasion_filter: list[str] | None,
) -> CartItem | None:
    """Tìm giày/phụ kiện phù hợp nhất với cả áo lẫn quần."""
    best, best_score = None, -1
    for c in candidates:
        score = (
            _score_color_pair(top.color, c.color)
            + _score_color_pair(bottom.color, c.color)
        )
        if occasion_filter:
            score += _occasion_bonus(c, occasion_filter)
        if score > best_score:
            best, best_score = c, score
    return best if best_score > 0.5 else None


def _pick_diverse(scored: list, max_n: int) -> list:
    """Chọn bộ đa dạng — mỗi áo/quần chỉ xuất hiện 1 lần."""
    sorted_outfits = sorted(scored, key=lambda x: x["score"], reverse=True)
    selected       = []
    used_tops      = set()
    used_bottoms   = set()

    # Vòng 1: strict
    for outfit in sorted_outfits:
        if len(selected) >= max_n:
            break
        top_id    = outfit["items"][0].product_id
        bottom_id = outfit["items"][1].product_id
        if top_id not in used_tops and bottom_id not in used_bottoms:
            selected.append(outfit)
            used_tops.add(top_id)
            used_bottoms.add(bottom_id)

    # Vòng 2: nới lỏng nếu chưa đủ
    if len(selected) < max_n:
        for outfit in sorted_outfits:
            if outfit not in selected:
                selected.append(outfit)
            if len(selected) >= max_n:
                break

    return selected


# ═════════════════════════════════════════════════════
# WARDROBE QUERY
# ═════════════════════════════════════════════════════

def _get_wardrobe_items(user_id: str, db: Session) -> list[CartItem]:
    """Lấy đồ trong tủ, join product để có color/category/occasions."""
    rows = db.query(WardrobeItem).filter(
        WardrobeItem.user_id == user_id,
        WardrobeItem.status.in_(ACTIVE_WARDROBE_STATUSES),
    ).all()

    result = []
    for item in rows:
        product = None
        if item.product_id:
            product = db.query(Product).filter(Product.id == item.product_id).first()

        color     = normalize_color((product.color if product and product.color else None) or "black")
        category  = item.category or (product.category if product else None) or "top"
        name      = item.name or (product.title if product else "Không tên")
        occasions = (product.ai_tags if product and product.ai_tags else [])

        result.append(CartItem(
            product_id=str(item.id),
            product_name=name,
            color=color,
            category=category,
            occasions=occasions,
        ))
        print(f"Total rows found: {len(rows)}")
        for item in rows:
            print(f"id={item.id}, category={item.category}, status={item.status}, user_id={item.user_id}")
    return result


def _group_by_category(items: list[CartItem]) -> dict:
    groups = {"top": [], "bottom": [], "shoes": [], "accessory": []}
    for item in items:
        cat = (item.category or "top").lower()
        if cat in groups:
            groups[cat].append(item)
    return groups


def _check_groups(groups: dict) -> tuple[bool, str]:
    tops    = groups["top"]
    bottoms = groups["bottom"]
    if not tops or not bottoms:
        return False, f"Cần ít nhất 1 áo và 1 quần. Hiện có: {len(tops)} áo, {len(bottoms)} quần."
    return True, ""


# ═════════════════════════════════════════════════════
# FORMAT + PARSE
# ═════════════════════════════════════════════════════

def _format_outfits(best: list) -> list:
    outfits = []
    for i, outfit in enumerate(best):
        items_info = [
            {
                "product_id": item.product_id,
                "name":       item.product_name,
                "category":   item.category,
                "color":      item.color,
                "occasions":  item.occasions,
            }
            for item in outfit["items"]
        ]
        outfits.append({
            "outfit_number": i + 1,
            "score":         round(outfit["score"], 2),
            "items":         items_info,
            "description":   _describe(items_info),
            "color_reason":  _color_reason(outfit["items"]),
        })
    return outfits


def _parse_occasion_from_message(message: str) -> list[str]:
    """
    Tìm occasion trong câu nhắn.
    Ví dụ:
      "lựa cho tôi bộ đi đám cưới" → ["wedding", "formal"]
      "muốn mặc đi làm"            → ["office"]
    """
    msg = message.lower().strip()

    if msg in OCCASION_MAP:
        return OCCASION_MAP[msg]

    for key, tags in OCCASION_MAP.items():
        if key in msg:
            return tags

    return ["casual"]


def _occasion_display_name(message: str) -> str:
    """Lấy tên dịp hiển thị từ message."""
    msg = message.lower()
    display_map = {
        "đám cưới":  "đám cưới",
        "wedding":   "đám cưới",
        "đi làm":    "đi làm",
        "office":    "đi làm",
        "văn phòng": "đi làm",
        "đi biển":   "đi biển",
        "biển":      "đi biển",
        "beach":     "đi biển",
        "tiệc":      "tiệc",
        "party":     "tiệc",
        "hẹn hò":    "hẹn hò",
        "date":      "hẹn hò",
        "thể thao":  "thể thao",
        "gym":       "thể thao",
        "dã ngoại":  "dã ngoại",
        "đi chơi":   "đi chơi",
        "dạo phố":   "dạo phố",
        "casual":    "dạo phố",
    }
    for key, display in display_map.items():
        if key in msg:
            return display
    return "dịp thường ngày"


def _describe(items: list[dict]) -> str:
    return " + ".join(f"{i['name']} ({i['color']})" for i in items)


def _color_reason(items: list[CartItem]) -> str:
    if len(items) < 2:
        return ""
    c1 = normalize_color(items[0].color)
    c2 = normalize_color(items[1].color)
    if c1 in NEUTRALS and c2 in NEUTRALS:
        return f"Cả {c1} và {c2} đều là màu trung tính — bộ đôi kinh điển."
    if c1 in NEUTRALS:
        return f"Màu {c1} trung tính dễ phối với {c2}."
    if c2 in NEUTRALS:
        return f"Màu {c2} trung tính làm dịu màu {c1} nổi bật."
    return f"Màu {c1} và {c2} phối hợp hài hòa."