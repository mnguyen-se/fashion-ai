from pydantic import BaseModel
from typing import Optional

# --- Cart / Wardrobe item (internal representation) ---

class CartItem(BaseModel):
    product_id:   str
    product_name: str
    color:        str
    category:     str
    occasions:    list[str]

# --- Chat ---

class ChatRequest(BaseModel):
    message:          str            # "áo này đi đám cưới phối quần gì?"
    user_id:          str            # UUID của user, để query wardrobe_item
    wardrobe_item_id: Optional[str] = None   # chỉ định rõ món đồ muốn hỏi (optional)

class ProductResponse(BaseModel):
    id:        str
    name:      str
    category:  Optional[str] = None
    color:     Optional[str] = None
    occasions: list[str] = []
    price:     Optional[int] = None
    in_stock:  bool = True
    images: list[str] = []

class SuggestedProduct(BaseModel):
    product:          ProductResponse
    similarity_score: float
    reason:           str

class ChatResponse(BaseModel):
    message:     str
    suggestions: list[SuggestedProduct]
    intent:      dict

# --- Intent (internal) ---

class ParsedIntent(BaseModel):
    occasion:       str
    category_want:  str
    style_hint:     Optional[str] = None
    ref_product_id: Optional[str] = None