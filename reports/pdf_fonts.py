from functools import lru_cache
from pathlib import Path

from django.conf import settings
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont


@lru_cache(maxsize=1)
def register_arabic_fonts():
    fonts_dir = Path(settings.BASE_DIR) / "assets" / "fonts"

    regular_path = fonts_dir / "NotoNaskhArabic-Regular.ttf"
    bold_path = fonts_dir / "NotoNaskhArabic-Bold.ttf"

    if not regular_path.exists():
        raise FileNotFoundError(f"Arabic font not found: {regular_path}")

    if not bold_path.exists():
        raise FileNotFoundError(f"Arabic font not found: {bold_path}")

    pdfmetrics.registerFont(TTFont("NotoNaskhArabic", str(regular_path)))
    pdfmetrics.registerFont(TTFont("NotoNaskhArabic-Bold", str(bold_path)))

    registerFontFamily(
        "NotoNaskhArabic",
        normal="NotoNaskhArabic",
        bold="NotoNaskhArabic-Bold",
    )