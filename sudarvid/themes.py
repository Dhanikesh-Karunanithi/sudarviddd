from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class ThemeSpec:
    id: str
    label: str
    bg_color: str
    text_color: str
    accent_color: str
    secondary_accent: str
    font_heading: str
    font_body: str
    css_extra: str = ""
    google_fonts_url: str = ""


THEMES: Dict[str, ThemeSpec] = {
    "modern_newspaper": ThemeSpec(
        id="modern_newspaper",
        label="Modern Newspaper",
        bg_color="#F5F5F5",
        text_color="#111111",
        accent_color="#FFCC00",
        secondary_accent="#FF3333",
        font_heading="'DM Sans','Impact','Arial Black',sans-serif",
        font_body="'DM Sans','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&display=swap",
    ),
    "sharp_minimalism": ThemeSpec(
        id="sharp_minimalism",
        label="Sharp Minimalism",
        bg_color="#FFFFFF",
        text_color="#111111",
        accent_color="#111111",
        secondary_accent="#333333",
        font_heading="'Inter','Helvetica Neue',Arial,sans-serif",
        font_body="'Inter','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
    ),
    "yellow_black": ThemeSpec(
        id="yellow_black",
        label="Yellow × Black",
        bg_color="#FFEE00",
        text_color="#111111",
        accent_color="#111111",
        secondary_accent="#000000",
        font_heading="'Inter','Georgia','Times New Roman',serif",
        font_body="'Inter','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
    ),
    "black_orange": ThemeSpec(
        id="black_orange",
        label="Black × Orange",
        bg_color="#FFFFFF",
        text_color="#111111",
        accent_color="#FF4800",
        secondary_accent="#111111",
        font_heading="'Inter','Helvetica Neue','Arial Black',sans-serif",
        font_body="'Inter','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
    ),
    "manga": ThemeSpec(
        id="manga",
        label="Manga",
        bg_color="#FFFFFF",
        text_color="#111111",
        accent_color="#FFE600",
        secondary_accent="#111111",
        font_heading="'Bangers','Arial Black','Impact',sans-serif",
        font_body="'Inter','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Bangers&family=Inter:wght@400;600&display=swap",
    ),
    "magazine": ThemeSpec(
        id="magazine",
        label="Magazine",
        bg_color="#E8C8C0",
        text_color="#2B2B2B",
        accent_color="#7B3F3F",
        secondary_accent="#FFFFFF",
        font_heading="'Playfair Display','Georgia','Times New Roman',serif",
        font_body="'Inter','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Inter:wght@400;600&display=swap",
    ),
    "neo_retro_dev": ThemeSpec(
        id="neo_retro_dev",
        label="Neo-Retro Dev",
        bg_color="#F5F0E8",
        text_color="#111111",
        accent_color="#FF2D88",
        secondary_accent="#FFE600",
        font_heading="'Space Grotesk','Arial Black','Impact',sans-serif",
        font_body="'Space Mono','Courier New',Courier,monospace",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Space+Mono&display=swap",
    ),
    "pink_street": ThemeSpec(
        id="pink_street",
        label="Pink Street",
        bg_color="#FF69B4",
        text_color="#111111",
        accent_color="#FFFFFF",
        secondary_accent="#111111",
        font_heading="'Inter','Arial Black','Impact',sans-serif",
        font_body="'Inter','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
    ),
    "mincho_handwritten": ThemeSpec(
        id="mincho_handwritten",
        label="Mincho + Handwritten",
        bg_color="#FFEE00",
        text_color="#111111",
        accent_color="#111111",
        secondary_accent="#FF4040",
        font_heading="'Inter','Georgia','Times New Roman',serif",
        font_body="'Inter','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
    ),
    "seminar_minimal": ThemeSpec(
        id="seminar_minimal",
        label="Seminar Minimal",
        bg_color="#FFFFFF",
        text_color="#111111",
        accent_color="#E00000",
        secondary_accent="#333333",
        font_heading="'Inter','Helvetica Neue',Arial,sans-serif",
        font_body="'Inter','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
    ),
    "royal_blue_red": ThemeSpec(
        id="royal_blue_red",
        label="Royal Blue × Red",
        bg_color="#E8EEF8",
        text_color="#1A1A2E",
        accent_color="#C0392B",
        secondary_accent="#1A3A7A",
        font_heading="'Inter','Georgia','Times New Roman',serif",
        font_body="'Inter','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
    ),
    "studio_premium": ThemeSpec(
        id="studio_premium",
        label="Studio Premium",
        bg_color="#F5F5F7",
        text_color="#1D1D1F",
        accent_color="#8D59E9",
        secondary_accent="#EBE021",
        font_heading="'Inter','Helvetica Neue',Arial,sans-serif",
        font_body="'Inter','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
    ),
    "sports": ThemeSpec(
        id="sports",
        label="Sports",
        bg_color="#111111",
        text_color="#FFFFFF",
        accent_color="#CCFF00",
        secondary_accent="#FF4500",
        font_heading="'Oswald','Impact','Arial Black',sans-serif",
        font_body="'Inter','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Oswald:wght@600;700&family=Inter:wght@400;600&display=swap",
    ),
    "classic_pop": ThemeSpec(
        id="classic_pop",
        label="Classic Pop",
        bg_color="#FF6EE7",
        text_color="#FFFFFF",
        accent_color="#00FFCC",
        secondary_accent="#FFE600",
        font_heading="'Inter','Helvetica Neue','Arial Black',sans-serif",
        font_body="'Inter','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
    ),
    "tech_neon": ThemeSpec(
        id="tech_neon",
        label="Tech Neon",
        bg_color="#E0E0D0",
        text_color="#333333",
        accent_color="#DFFF00",
        secondary_accent="#333333",
        font_heading="'Inter','Georgia','Times New Roman',serif",
        font_body="'IBM Plex Mono','Courier New',Courier,monospace",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap",
    ),
    "digital_neo_pop": ThemeSpec(
        id="digital_neo_pop",
        label="Digital Neo Pop",
        bg_color="#FFFFFF",
        text_color="#111111",
        accent_color="#FF2D7A",
        secondary_accent="#00D4FF",
        font_heading="'Inter','Arial Black','Impact',sans-serif",
        font_body="'Inter','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
    ),
    "anti_gravity": ThemeSpec(
        id="anti_gravity",
        label="Anti-Gravity",
        bg_color="#FFFFFF",
        text_color="#1A1A1A",
        accent_color="#4A9EE8",
        secondary_accent="#A78BFA",
        font_heading="'Inter','Helvetica Neue',Arial,sans-serif",
        font_body="'Inter','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
    ),
    "deformed_persona": ThemeSpec(
        id="deformed_persona",
        label="Deformed Persona",
        bg_color="#F0E8D8",
        text_color="#2B2B2B",
        accent_color="#7EB8A0",
        secondary_accent="#D4A574",
        font_heading="'Inter','Helvetica Neue',Arial,sans-serif",
        font_body="'Inter','Helvetica Neue',Arial,sans-serif",
        google_fonts_url="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
    ),
}


def get_theme(theme_id: str) -> ThemeSpec:
    if theme_id not in THEMES:
        raise ValueError(f"Unknown theme '{theme_id}'.")
    return THEMES[theme_id]


def list_themes() -> List[dict]:
    return [
        {
            "id": k,
            "label": v.label,
            "bg": v.bg_color,
            "accent": v.accent_color,
            "secondary": v.secondary_accent,
            "text_color": v.text_color,
            "font_heading": v.font_heading,
            "google_fonts_url": v.google_fonts_url or "",
        }
        for k, v in THEMES.items()
    ]

