"""
Map dịp/occasion từ ngôn ngữ tự nhiên sang tags trong DB.
"""

# Tags occasion trong DB
OCCASION_TAGS = [
    "casual",       # hàng ngày, dạo phố
    "office",       # đi làm
    "formal",       # trang trọng
    "party",        # tiệc tùng
    "wedding",      # đám cưới
    "beach",        # đi biển
    "sport",        # thể thao
    "date",         # hẹn hò
    "outdoor",      # hoạt động ngoài trời
]

# Map từ ngôn ngữ tự nhiên → occasion tags
OCCASION_MAP: dict[str, list[str]] = {
    # Casual
    "casual":       ["casual"],
    "hàng ngày":    ["casual"],
    "dạo phố":      ["casual"],
    "đi chơi":      ["casual", "date"],
    "đi cafe":      ["casual", "date"],
    "cuối tuần":    ["casual", "outdoor"],

    # Office
    "office":       ["office"],
    "đi làm":       ["office"],
    "công sở":      ["office"],
    "văn phòng":    ["office"],
    "họp":          ["office", "formal"],

    # Formal
    "formal":       ["formal"],
    "trang trọng":  ["formal"],
    "lịch sự":      ["formal", "office"],

    # Party / Event
    "party":        ["party"],
    "tiệc":         ["party", "formal"],
    "dạ tiệc":      ["party", "formal"],
    "đám cưới":     ["wedding", "formal"],
    "wedding":      ["wedding", "formal"],
    "sinh nhật":    ["party", "casual"],

    # Beach / Outdoor
    "biển":         ["beach", "outdoor"],
    "đi biển":      ["beach", "outdoor"],
    "beach":        ["beach"],
    "dã ngoại":     ["outdoor", "casual"],
    "cắm trại":     ["outdoor", "casual"],
    "leo núi":      ["outdoor", "sport"],

    # Sport
    "thể thao":     ["sport"],
    "gym":          ["sport"],
    "chạy bộ":      ["sport"],
    "sport":        ["sport"],

    # Date
    "hẹn hò":       ["date", "casual"],
    "date":         ["date", "casual"],
    "tối lãng mạn": ["date", "formal"],
}

def get_occasion_tags(occasion_text: str) -> list[str]:
    """
    Chuyển occasion từ text → list tags.
    Nếu không match → trả về ["casual"] làm default.
    """
    occasion_text = occasion_text.lower().strip()
    
    # Direct match
    if occasion_text in OCCASION_MAP:
        return OCCASION_MAP[occasion_text]
    
    # Partial match
    for key, tags in OCCASION_MAP.items():
        if key in occasion_text or occasion_text in key:
            return tags
    
    return ["casual"]  # default
