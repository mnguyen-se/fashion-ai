from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.db.database import init_db

app = FastAPI(
    title="Fashion AI API",
    description="Gợi ý phối đồ thông minh cho cửa hàng thời trang",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Đổi lại khi production
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    print(f"📖 API docs: http://localhost:8000/docs")

app.include_router(router, prefix="/api")
