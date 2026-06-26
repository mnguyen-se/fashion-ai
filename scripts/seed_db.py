"""
Chạy script này để tạo sample data:
    python scripts/seed_db.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from app.db.database import init_db, SessionLocal
from app.models.product import Product
from app.core.color_rules import normalize_color

SAMPLE_PRODUCTS = [
    # ── TOP ──
    {"name": "Áo sơ mi trắng basic", "category": "top", "color_vi": "Trắng", "color": "white",
     "occasions": ["office", "casual", "formal"], "price": 299000},
    {"name": "Áo thun đen oversize", "category": "top", "color_vi": "Đen", "color": "black",
     "occasions": ["casual", "sport"], "price": 199000},
    {"name": "Áo sơ mi navy kẻ sọc", "category": "top", "color_vi": "Xanh navy", "color": "navy",
     "occasions": ["office", "casual"], "price": 349000},
    {"name": "Áo blouse hồng pastel", "category": "top", "color_vi": "Hồng", "color": "pink",
     "occasions": ["casual", "date", "party"], "price": 279000},
    {"name": "Áo thun trắng cổ tròn", "category": "top", "color_vi": "Trắng", "color": "white",
     "occasions": ["casual", "sport"], "price": 149000},
    {"name": "Áo sơ mi beige linen", "category": "top", "color_vi": "Be", "color": "beige",
     "occasions": ["casual", "beach", "outdoor"], "price": 329000},

    # ── BOTTOM ──
    {"name": "Quần tây đen slim fit", "category": "bottom", "color_vi": "Đen", "color": "black",
     "occasions": ["office", "formal", "party"], "price": 449000},
    {"name": "Quần jean xanh dương", "category": "bottom", "color_vi": "Jean xanh", "color": "denim",
     "occasions": ["casual", "date", "outdoor"], "price": 399000},
    {"name": "Quần âu xám", "category": "bottom", "color_vi": "Xám", "color": "gray",
     "occasions": ["office", "formal"], "price": 429000},
    {"name": "Quần linen beige", "category": "bottom", "color_vi": "Be", "color": "beige",
     "occasions": ["casual", "beach", "outdoor"], "price": 299000},
    {"name": "Chân váy trắng midi", "category": "bottom", "color_vi": "Trắng", "color": "white",
     "occasions": ["casual", "date", "party"], "price": 349000},
    {"name": "Quần đen wide leg", "category": "bottom", "color_vi": "Đen", "color": "black",
     "occasions": ["casual", "office", "party"], "price": 379000},

    # ── SHOES ──
    {"name": "Giày sneaker trắng", "category": "shoes", "color_vi": "Trắng", "color": "white",
     "occasions": ["casual", "sport", "date"], "price": 599000},
    {"name": "Giày oxford đen", "category": "shoes", "color_vi": "Đen", "color": "black",
     "occasions": ["office", "formal", "party"], "price": 799000},
    {"name": "Sandal beige", "category": "shoes", "color_vi": "Be", "color": "beige",
     "occasions": ["casual", "beach", "outdoor"], "price": 399000},
    {"name": "Giày cao gót nude", "category": "shoes", "color_vi": "Nude/Beige", "color": "beige",
     "occasions": ["formal", "party", "wedding", "date"], "price": 699000},
    {"name": "Slip-on navy", "category": "shoes", "color_vi": "Xanh navy", "color": "navy",
     "occasions": ["casual", "office"], "price": 499000},

    # ── ACCESSORY ──
    {"name": "Túi tote canvas trắng", "category": "accessory", "color_vi": "Trắng", "color": "white",
     "occasions": ["casual", "beach", "outdoor"], "price": 249000},
    {"name": "Thắt lưng da đen", "category": "accessory", "color_vi": "Đen", "color": "black",
     "occasions": ["office", "formal", "casual"], "price": 199000},
    {"name": "Khăn lụa navy", "category": "accessory", "color_vi": "Xanh navy", "color": "navy",
     "occasions": ["formal", "office", "party"], "price": 149000},
    {"name": "Túi clutch đen", "category": "accessory", "color_vi": "Đen", "color": "black",
     "occasions": ["party", "formal", "wedding"], "price": 349000},
]

def seed():
    init_db()
    db = SessionLocal()
    
    # Xóa data cũ
    db.query(Product).delete()
    
    for data in SAMPLE_PRODUCTS:
        product = Product(
            name=data["name"],
            category=data["category"],
            color=normalize_color(data["color"]),
            color_vi=data.get("color_vi"),
            occasions=data["occasions"],
            price=data["price"],
        )
        db.add(product)
    
    db.commit()
    print(f"✅ Đã seed {len(SAMPLE_PRODUCTS)} sản phẩm")
    db.close()

if __name__ == "__main__":
    seed()
