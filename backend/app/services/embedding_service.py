"""
Embedding service — chuyển sản phẩm thành vector để tính similarity.
Chạy embed_products.py 1 lần để index toàn bộ catalog.
"""
import chromadb
from sentence_transformers import SentenceTransformer
from app.core.config import settings
from app.models.product import Product

_model: SentenceTransformer = None
_chroma_client: chromadb.Client = None
_collection = None

def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _model

def _get_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
        _collection = _chroma_client.get_or_create_collection(
            name="products",
            metadata={"hnsw:space": "cosine"}
        )
    return _collection

def embed_product(product: Product):
    """Embed 1 sản phẩm vào ChromaDB."""
    model = _get_model()
    collection = _get_collection()
    
    text = product.to_embed_text()
    embedding = model.encode(text).tolist()
    
    collection.upsert(
        ids=[str(product.id)],
        embeddings=[embedding],
        documents=[text],
        metadatas=[{
            "category": product.category,
            "color":    product.color,
            "occasions": ",".join(product.occasions),
            "in_stock":  str(product.in_stock),
        }]
    )

def find_similar_products(
    query_text: str,
    category_filter: str = None,
    color_filter: list[str] = None,
    occasion_filter: list[str] = None,
    top_k: int = 10,
) -> list[tuple[str, float]]:
    """
    Tìm sản phẩm tương tự.
    Returns: list of (product_id, similarity_score)
    """
    model = _get_model()
    collection = _get_collection()
    
    query_embedding = model.encode(query_text).tolist()

    # Build where filter cho ChromaDB
    where = None
    if category_filter:
        where = {"category": {"$eq": category_filter}}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k * 3, 50),
        where=where,
    )
    
    if not results["ids"][0]:
        return []
    
    # Filter thêm theo color và occasion (ChromaDB không support list filter tốt)
    output = []
    for i, product_id in enumerate(results["ids"][0]):
        meta = results["metadatas"][0][i]
        score = 1 - results["distances"][0][i]  # cosine distance → similarity
        
        # Filter color
        if color_filter and meta.get("color") not in color_filter:
            continue
        
        # Filter occasion
        if occasion_filter:
            product_occasions = meta.get("occasions", "").split(",")
            if not any(occ in product_occasions for occ in occasion_filter):
                continue
        
        output.append((product_id, round(score, 3)))
    
    return output[:top_k]

def delete_product_embedding(product_id: str):
    """Xóa embedding khi sản phẩm hết hàng / bị xóa."""
    collection = _get_collection()
    collection.delete(ids=[product_id])
