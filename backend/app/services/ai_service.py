"""
AI service dùng Ollama (local LLM).
Làm 2 việc:
1. Parse intent từ câu hỏi của user
2. Generate câu trả lời tự nhiên
"""
import json
import re
import ollama
from app.core.config import settings
from app.models.schemas import ParsedIntent, CartItem

NLU_SYSTEM_PROMPT = """Bạn là AI phân tích yêu cầu phối đồ thời trang.
Nhiệm vụ: Phân tích câu hỏi của user và trả về JSON.

Các occasion hợp lệ: casual, office, formal, party, wedding, beach, sport, date, outdoor
Các category hợp lệ: top, bottom, shoes, accessory, dress, full_outfit

Chỉ trả về JSON, không giải thích, không markdown:
{
  "occasion": "...",
  "category_want": "...",
  "style_hint": "..." hoặc null,
  "ref_product_index": 0 hoặc null,
  "max_price": số hoặc null,
  "min_price": số hoặc null
}

max_price/min_price: nếu user đề cập ngân sách (vd: "dưới 300k", "tầm 200-500k"),
trích ra số VND. Nếu không đề cập → null.
ref_product_index: index sản phẩm trong giỏ user đang hỏi (0-based), null nếu không rõ."""

RESPONSE_SYSTEM_PROMPT = """Bạn là stylist thời trang của một shop quần áo.
Nhiệm vụ: Dựa vào thông tin được cung cấp, viết 1-2 câu gợi ý phối đồ ngắn gọn, tự nhiên, thân thiện bằng tiếng Việt.
Đề cập tên sản phẩm cụ thể. Không liệt kê danh sách, chỉ viết 1-2 câu mượt mà."""


async def parse_intent(
    user_message: str,
    cart_items: list[CartItem],
) -> ParsedIntent:
    cart_summary = "\n".join([
        f"{i}. {item.product_name} ({item.color}, {item.category})"
        for i, item in enumerate(cart_items)
    ])

    user_content = f"""Giỏ hàng hiện tại:
{cart_summary}

Câu hỏi: {user_message}"""

    response = ollama.chat(
        model=settings.OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": NLU_SYSTEM_PROMPT},
            {"role": "user",   "content": user_content},
        ],
        options={"temperature": 0.1}
    )

    raw = response["message"]["content"].strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            data = {
                "occasion": "casual",
                "category_want": "full_outfit",
                "style_hint": None,
                "ref_product_index": 0,
                "max_price": None,
                "min_price": None,
            }

    ref_idx = data.get("ref_product_index")
    ref_product_id = (
        cart_items[ref_idx].product_id
        if ref_idx is not None and ref_idx < len(cart_items)
        else None
    )

    return ParsedIntent(
        occasion=data.get("occasion", "casual"),
        category_want=data.get("category_want", "full_outfit"),
        style_hint=data.get("style_hint"),
        ref_product_id=ref_product_id,
        max_price=data.get("max_price"),
        min_price=data.get("min_price"),
    )


async def generate_response(
    user_message: str,
    ref_product_name: str,
    occasion: str,
    suggested_names: list[str],
) -> str:
    if not suggested_names:
        return f"Hiện tại shop chưa có sản phẩm phù hợp để phối với {ref_product_name} cho dịp {occasion}. Bạn có muốn xem các lựa chọn khác không?"

    suggestions_str = ", ".join(suggested_names[:3])

    context = f"""Sản phẩm user vừa mua: {ref_product_name}
Dịp: {occasion}
Gợi ý phối: {suggestions_str}
Câu hỏi gốc: {user_message}"""

    response = ollama.chat(
        model=settings.OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": RESPONSE_SYSTEM_PROMPT},
            {"role": "user",   "content": context},
        ],
        options={"temperature": 0.7}
    )

    return response["message"]["content"].strip()


def check_ollama_connection() -> bool:
    try:
        ollama.list()
        return True
    except Exception:
        return False