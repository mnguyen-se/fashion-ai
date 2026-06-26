"""
Test các API endpoint.
Chạy: pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import app
from app.db.database import init_db

client = TestClient(app)

def setup_module():
    init_db()

def test_health_check():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_create_and_get_product():
    # Tạo sản phẩm
    product_data = {
        "name": "Áo test",
        "category": "top",
        "color": "white",
        "color_vi": "Trắng",
        "occasions": ["casual"],
        "price": 199000,
    }
    res = client.post("/api/products", json=product_data)
    assert res.status_code == 201
    product_id = res.json()["id"]
    
    # Lấy lại
    res = client.get(f"/api/products/{product_id}")
    assert res.status_code == 200
    assert res.json()["name"] == "Áo test"

def test_quick_suggestions():
    # Tạo sản phẩm
    res = client.post("/api/products", json={
        "name": "Quần navy test",
        "category": "bottom",
        "color": "navy",
        "occasions": ["office"],
        "price": 299000,
    })
    product_id = res.json()["id"]
    
    # Lấy gợi ý
    res = client.get(f"/api/products/{product_id}/suggestions")
    assert res.status_code in [200, 404]  # 404 nếu chưa seed data

def test_chat_requires_cart():
    res = client.post("/api/chat", json={
        "message": "phối gì đây?",
        "cart_items": []
    })
    assert res.status_code == 400
