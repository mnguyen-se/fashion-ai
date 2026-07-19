from sqlalchemy import Column, String, BigInteger, SmallInteger, Text, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "category"

    id          = Column(UUID(as_uuid=True), primary_key=True)
    name        = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)


class Product(Base):
    __tablename__ = "product"

    id          = Column(UUID(as_uuid=True), primary_key=True)
    title       = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("category.id"), nullable=True)
    type        = Column(String, nullable=False)
    condition   = Column(SmallInteger, nullable=True)
    price       = Column(BigInteger, nullable=True)
    size        = Column(String(20), nullable=True)
    color       = Column(String(50), nullable=True)
    images      = Column(JSON, nullable=True)
    ai_tags     = Column("ai_tags", JSON, nullable=True)
    status      = Column(String, nullable=False)
    shop_id     = Column(UUID(as_uuid=True), nullable=True)

    category_ref = relationship("Category", lazy="joined")

    @property
    def category(self):
        """Tương thích code cũ dùng product.category — trả về tên category."""
        return self.category_ref.name if self.category_ref else None

    def to_embed_text(self) -> str:
        tags = " ".join(self.ai_tags or [])
        return f"{self.category} {self.color} {tags} {self.title}"

    @property
    def in_stock(self):
        return self.status == "AVAILABLE"

    @property
    def occasions(self):
        return self.ai_tags or ["casual"]

    @property
    def name(self):
        return self.title

    def to_dict(self):
        return {
            "id":        str(self.id),
            "name":      self.title,
            "category":  self.category,
            "color":     self.color,
            "occasions": self.occasions,
            "price":     self.price,
            "in_stock":  self.in_stock,
            "images": self.images or [],
        }

class WardrobeItem(Base):
    __tablename__ = "wardrobe_item"

    id          = Column(UUID(as_uuid=True), primary_key=True)
    user_id     = Column(UUID(as_uuid=True), nullable=False)
    product_id  = Column(UUID(as_uuid=True), ForeignKey("product.id"), nullable=True)
    name        = Column(String(150), nullable=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("category.id"), nullable=True)
    image_url   = Column(Text, nullable=True)
    status      = Column(String, nullable=True)
    added_via   = Column(String, nullable=True)
    acquired_at = Column(Date, nullable=True)

    category_ref = relationship("Category", lazy="joined")

    @property
    def category_name(self):
        """Trả về tên category dạng string, tương thích với code cũ dùng item.category."""
        return self.category_ref.name if self.category_ref else None