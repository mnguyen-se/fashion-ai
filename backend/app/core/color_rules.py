"""
Quy tắc phối màu — đây là "bộ não" chính của hệ thống.
Không cần AI cho phần này.
"""

# Màu nào phối được với màu nào
COLOR_RULES: dict[str, list[str]] = {
    # Neutral — phối với hầu hết màu
    "black":      ["white", "gray", "silver", "red", "pink", "blue", "navy", "beige", "cream", "gold"],
    "white":      ["black", "navy", "gray", "beige", "brown", "red", "blue", "green", "pink"],
    "gray":       ["black", "white", "navy", "pink", "purple", "blue", "red"],
    "beige":      ["white", "brown", "navy", "olive", "black", "cream", "camel"],
    "cream":      ["brown", "beige", "navy", "black", "camel", "tan"],

    # Màu đậm
    "navy":       ["white", "beige", "cream", "gray", "light-blue", "pink", "red", "gold"],
    "brown":      ["beige", "cream", "white", "olive", "camel", "tan", "orange"],
    "camel":      ["white", "black", "navy", "brown", "beige"],
    "olive":      ["beige", "brown", "white", "black", "camel", "tan"],

    # Màu sáng / pastel
    "pink":       ["white", "black", "gray", "navy", "beige", "light-gray"],
    "light-blue": ["white", "navy", "beige", "gray", "cream"],
    "lavender":   ["white", "gray", "beige", "navy"],
    "mint":       ["white", "beige", "navy", "gray"],

    # Màu nổi bật
    "red":        ["white", "black", "navy", "beige", "gray"],
    "blue":       ["white", "beige", "gray", "light-gray", "navy"],
    "green":      ["white", "beige", "brown", "tan", "black"],
    "yellow":     ["white", "black", "navy", "gray"],
    "orange":     ["white", "black", "navy", "brown", "beige"],
    "purple":     ["white", "black", "gray", "beige"],

    # Denim — đặc biệt
    "denim":      ["white", "black", "gray", "beige", "red", "pink", "navy", "brown"],

    # Metallic
    "gold":       ["black", "navy", "white", "beige", "brown"],
    "silver":     ["black", "white", "gray", "navy", "blue"],
}

def get_compatible_colors(color: str) -> list[str]:
    """Lấy danh sách màu phối được."""
    color = color.lower().strip()
    
    # Thêm chính màu đó vào (tone-on-tone)
    compatible = COLOR_RULES.get(color, []).copy()
    compatible.append(color)
    
    return compatible

def normalize_color(color: str) -> str:
    """Chuẩn hóa tên màu (vd: 'Xanh navy' → 'navy')"""
    color_map = {
        "xanh navy": "navy",
        "xanh đen": "navy",
        "xanh dương": "blue",
        "xanh lá": "green",
        "đen": "black",
        "trắng": "white",
        "xám": "gray",
        "đỏ": "red",
        "vàng": "yellow",
        "hồng": "pink",
        "nâu": "brown",
        "be": "beige",
        "kem": "cream",
        "tím": "purple",
        "cam": "orange",
        "bạc": "silver",
        "vàng gold": "gold",
        "xanh nhạt": "light-blue",
        "jean": "denim",
        "bò": "denim",
    }
    return color_map.get(color.lower().strip(), color.lower().strip())
