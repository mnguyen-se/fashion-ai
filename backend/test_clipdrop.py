import requests
from app.core.config import settings
import urllib.request

# Download ảnh test từ Cloudinary
url = "https://res.cloudinary.com/dktu0nbjx/image/upload/v1782197887/prm/products/mnguyen0811/file_ntfyge.jpg"
urllib.request.urlretrieve(url, "test.jpg")

with open("test.jpg", "rb") as f:
    res = requests.post(
        "https://clipdrop-api.co/remove-background/v1",
        files={"image_file": ("test.jpg", f, "image/jpeg")},
        headers={"x-api-key": settings.CLIPDROP_API_KEY},
    )

print("Status:", res.status_code)
print("Response:", res.text[:300])

if res.status_code == 200:
    with open("test_output.png", "wb") as f:
        f.write(res.content)
    print("✅ Lưu ảnh output vào test_output.png")