import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types
from google.oauth2 import service_account
from app.core.config import settings
import base64
# ─────────────────────────────────────────
# Configure Gemini qua Vertex AI (thay cho AI Studio / API key)
# ─────────────────────────────────────────
# Yêu cầu:
#   1. settings.google_cloud_project  -> project id trên GCP
#   2. settings.google_cloud_location -> region, ví dụ "us-central1" hoặc "global"
#   3. Application Default Credentials (service account JSON)
#
# Thay vì dựa vào os.environ["GOOGLE_APPLICATION_CREDENTIALS"] (ADC tự tìm —
# có thể không tin cậy khi uvicorn spawn process riêng trên Windows), load
# trực tiếp file JSON ở đây và truyền explicit vào genai.Client(). Nếu path
# sai, lỗi sẽ hiện rõ ngay khi khởi động app, thay vì lỗi mơ hồ "default
# credentials were not found" lúc gọi API.
import tempfile

credential_value = settings.google_application_credentials

if not credential_value:
    raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS chưa được thiết lập.")

# Nếu biến môi trường chứa JSON (Railway)
if credential_value.strip().startswith("{"):
    temp = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    )
    temp.write(credential_value)
    temp.close()

    credentials_path = temp.name

# Nếu là đường dẫn file (Local)
else:
    credentials_path = credential_value

    if not os.path.isfile(credentials_path):
        raise RuntimeError(
            f"Không tìm thấy credentials file: {credentials_path}"
        )

_vertex_credentials = service_account.Credentials.from_service_account_file(
    credentials_path,
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)
client = genai.Client(
    vertexai=True,
    project=settings.google_cloud_project,
    location=settings.google_cloud_location,
    credentials=_vertex_credentials,
)

SLOT_W   = 250
SLOT_H   = 300
PADDING  = 20
BG_COLOR = (250, 248, 245, 255)

# Lưu ý: model image-gen của Gemini hiện chỉ available ở một số region trên Vertex
# (thường là "global" hoặc "us-central1"). Nếu gặp lỗi 404/NOT_FOUND khi gọi model,
# thử đổi GOOGLE_CLOUD_LOCATION sang "global" hoặc "us-central1".
IMAGE_MODEL = "gemini-3.1-flash-image"


# ─────────────────────────────────────────
# Gender detection
# ─────────────────────────────────────────

def _detect_gender(items: list[dict]) -> str:
    male_keywords   = ["shorts", "swim", "boxer", "cargo", "polo",
                       "blazer nam", "quần nam", "áo nam", "suit"]
    female_keywords = ["skirt", "váy", "blouse", "heels", "dress",
                       "mini", "pleated", "midi", "crop", "áo nữ", "quần nữ"]

    male_score   = 0
    female_score = 0

    for item in items:
        combined = ((item.get("name") or "") + " " + (item.get("category") or "")).lower()
        for kw in male_keywords:
            if kw in combined:
                male_score += 1
        for kw in female_keywords:
            if kw in combined:
                female_score += 1

    if male_score > female_score:
        return "male"
    if female_score > male_score:
        return "female"
    return "neutral"


def _gender_to_mannequin(gender: str) -> str:
    if gender == "male":
        return "a male body shape and proportions"
    if gender == "female":
        return "a female body shape and proportions"
    return "a gender-neutral body shape and proportions"


# ─────────────────────────────────────────
# Download helper
# ─────────────────────────────────────────

def _download_image(url: str) -> Image.Image | None:
    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return None
        return Image.open(BytesIO(res.content)).convert("RGB")
    except Exception as e:
        print(f"Download error: {e}")
        return None


# ─────────────────────────────────────────
# Gemini image processing (qua Vertex AI)
# ─────────────────────────────────────────

def process_outfit_with_gemini(items_with_urls: list[dict]) -> bytes | None:
    """
    Gửi tất cả ảnh đồ trong 1 bộ lên Gemini (Vertex AI).
    Gemini xóa người/bg, ghép layout, thêm ma nơ canh.
    Trả về ảnh PNG bytes.
    """
    try:
        # Download tất cả ảnh
        images = []
        for item in items_with_urls:
            url = item.get("image_url")
            if url:
                img = _download_image(url)
                if img:
                    images.append((img, item))

        if not images:
            print("Không có ảnh nào download được")
            return None

        # Detect giới tính
        gender    = _detect_gender([i[1] for i in images])
        mannequin = _gender_to_mannequin(gender)

        # Build prompt
        items_text = "\n".join(
            f"- {item['name']} ({item['category']})"
            for _, item in images
        )

        prompt = f"""You are a fashion stylist AI. I give you {len(images)} clothing product images.

        Items:
        {items_text}

        Instructions:
        1. Remove the background and any person/model from each clothing image — keep ONLY the clothing item itself
        2. Generate a realistic, full-body retail store display mannequin with {mannequin} — a smooth, featureless, glossy plastic mannequin in light gray or white, with a blank head that has NO facial features (no eyes, nose, mouth, hair, or skin texture). This must look like a literal physical mannequin object, NOT a real human, NOT a photo of an actual person's face or skin.
        3. The mannequin must be actually WEARING all the clothing items together as one complete outfit (top, bottom, shoes, accessories combined on the same mannequin body), standing in a simple neutral standing pose, facing forward
        4. Do NOT lay the clothes flat on the ground or arrange them as a flat lay. A dressed mannequin figure is required.
        5. Keep proportions realistic and natural, like a clean retail mannequin product photo
        6. Pure white or very light cream studio background, soft even lighting, centered composition

        Return a single composed image of the faceless plastic mannequin wearing the full outfit only."""

        # Build content parts
        parts = []
        for img, _ in images:
            buf = BytesIO()
            img.save(buf, format="JPEG")
            parts.append(
                types.Part.from_bytes(
                    data=buf.getvalue(),
                    mime_type="image/jpeg",
                )
            )
        parts.append(types.Part.from_text(text=prompt))

        # Gọi Gemini qua Vertex AI
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=parts,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"]
            ),
        )

        # Lấy ảnh từ response
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                data = part.inline_data.data
                # Nếu là string base64 → decode thành bytes để trả về
                if isinstance(data, str):
                    data = base64.b64decode(data)
                # Nếu đã là bytes → dùng thẳng
                print(f"✅ Gemini generated image, size={len(data)} bytes")
                return data

        print("Gemini không trả về ảnh")
        return None

    except Exception as e:
        print(f"Gemini (Vertex AI) error: {e}")
        return None


# ─────────────────────────────────────────
# Compose all outfits (3 bộ cạnh nhau)
# ─────────────────────────────────────────

def compose_all_outfits(outfit_images: list[bytes], labels: list[str] = None) -> bytes:
    """Ghép tất cả bộ đồ cạnh nhau thành 1 ảnh tổng."""
    if not outfit_images:
        return b""

    imgs    = [Image.open(BytesIO(b)).convert("RGBA") for b in outfit_images]
    label_h = 36
    max_h   = max(img.height for img in imgs)
    total_w = sum(img.width for img in imgs) + PADDING * (len(imgs) + 1)
    total_h = max_h + label_h + PADDING * 2

    canvas = Image.new("RGBA", (total_w, total_h), BG_COLOR)
    draw   = ImageDraw.Draw(canvas)

    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font = ImageFont.load_default()

    x = PADDING
    for i, img in enumerate(imgs):
        label   = labels[i] if labels and i < len(labels) else f"Bộ {i + 1}"
        label_x = x + (img.width - len(label) * 8) // 2
        draw.text((label_x, PADDING), label, fill=(80, 60, 50, 255), font=font)
        canvas.paste(img, (x, PADDING + label_h), img)

        if i < len(imgs) - 1:
            lx = x + img.width + PADDING // 2
            draw.line(
                [(lx, PADDING), (lx, total_h - PADDING)],
                fill=(200, 190, 185, 180),
                width=1,
            )

        x += img.width + PADDING

    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()