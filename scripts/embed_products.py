"""
Chạy script này để embed toàn bộ catalog vào ChromaDB:
    python scripts/embed_products.py

Chạy lại khi:
- Thêm nhiều sản phẩm cùng lúc
- Reset ChromaDB
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from app.db.database import init_db, SessionLocal
from app.models.product import Product
from app.services.embedding_service import embed_product

def embed_all():
    init_db()
    db = SessionLocal()
    
    products = db.query(Product).filter(Product.status == "AVAILABLE").all()
    print(f"Đang embed {len(products)} sản phẩm...")
    
    for i, product in enumerate(products):
        embed_product(product)
        print(f"  [{i+1}/{len(products)}] {product.name}")
    
    print(f"\n✅ Hoàn thành! Đã embed {len(products)} sản phẩm vào ChromaDB")
    db.close()

if __name__ == "__main__":
    embed_all()
