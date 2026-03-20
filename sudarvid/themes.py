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


THEMES: Dict[str, ThemeSpec] = {
    "modern_newspaper": ThemeSpec(
        id="modern_newspaper",
        label="Modern Newspaper",
        bg_color="#F5F5F5",
        text_color="#111111",
        accent_color="#FFCC00",
        secondary_accent="#FF3333",
        font_heading="'Impact','Arial Black',sans-serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
    "sharp_minimalism": ThemeSpec(
        id="sharp_minimalism",
        label="Sharp Minimalism",
        bg_color="#FFFFFF",
        text_color="#111111",
        accent_color="#111111",
        secondary_accent="#333333",
        font_heading="'Helvetica Neue',Arial,sans-serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
    "yellow_black": ThemeSpec(
        id="yellow_black",
        label="Yellow × Black",
        bg_color="#FFEE00",
        text_color="#111111",
        accent_color="#111111",
        secondary_accent="#000000",
        font_heading="'Georgia','Times New Roman',serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
    "black_orange": ThemeSpec(
        id="black_orange",
        label="Black × Orange",
        bg_color="#FFFFFF",
        text_color="#111111",
        accent_color="#FF4800",
        secondary_accent="#111111",
        font_heading="'Helvetica Neue','Arial Black',sans-serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
    "manga": ThemeSpec(
        id="manga",
        label="Manga",
        bg_color="#FFFFFF",
        text_color="#111111",
        accent_color="#FFE600",
        secondary_accent="#111111",
        font_heading="'Arial Black','Impact',sans-serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
    "magazine": ThemeSpec(
        id="magazine",
        label="Magazine",
        bg_color="#E8C8C0",
        text_color="#2B2B2B",
        accent_color="#7B3F3F",
        secondary_accent="#FFFFFF",
        font_heading="'Georgia','Times New Roman',serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
    "neo_retro_dev": ThemeSpec(
        id="neo_retro_dev",
        label="Neo-Retro Dev",
        bg_color="#F5F0E8",
        text_color="#111111",
        accent_color="#FF2D88",
        secondary_accent="#FFE600",
        font_heading="'Arial Black','Impact',sans-serif",
        font_body="'Courier New',Courier,monospace",
    ),
    "pink_street": ThemeSpec(
        id="pink_street",
        label="Pink Street",
        bg_color="#FF69B4",
        text_color="#111111",
        accent_color="#FFFFFF",
        secondary_accent="#111111",
        font_heading="'Arial Black','Impact',sans-serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
    "mincho_handwritten": ThemeSpec(
        id="mincho_handwritten",
        label="Mincho + Handwritten",
        bg_color="#FFEE00",
        text_color="#111111",
        accent_color="#111111",
        secondary_accent="#FF4040",
        font_heading="'Georgia','Times New Roman',serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
    "seminar_minimal": ThemeSpec(
        id="seminar_minimal",
        label="Seminar Minimal",
        bg_color="#FFFFFF",
        text_color="#111111",
        accent_color="#E00000",
        secondary_accent="#333333",
        font_heading="'Helvetica Neue',Arial,sans-serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
    "royal_blue_red": ThemeSpec(
        id="royal_blue_red",
        label="Royal Blue × Red",
        bg_color="#E8EEF8",
        text_color="#1A1A2E",
        accent_color="#C0392B",
        secondary_accent="#1A3A7A",
        font_heading="'Georgia','Times New Roman',serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
    "studio_premium": ThemeSpec(
        id="studio_premium",
        label="Studio Premium",
        bg_color="#F5F5F7",
        text_color="#1D1D1F",
        accent_color="#8D59E9",
        secondary_accent="#EBE021",
        font_heading="'Helvetica Neue',Arial,sans-serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
    "sports": ThemeSpec(
        id="sports",
        label="Sports",
        bg_color="#111111",
        text_color="#FFFFFF",
        accent_color="#CCFF00",
        secondary_accent="#FF4500",
        font_heading="'Impact','Arial Black',sans-serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
    "classic_pop": ThemeSpec(
        id="classic_pop",
        label="Classic Pop",
        bg_color="#FF6EE7",
        text_color="#FFFFFF",
        accent_color="#00FFCC",
        secondary_accent="#FFE600",
        font_heading="'Helvetica Neue','Arial Black',sans-serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
    "tech_neon": ThemeSpec(
        id="tech_neon",
        label="Tech Neon",
        bg_color="#E0E0D0",
        text_color="#333333",
        accent_color="#DFFF00",
        secondary_accent="#333333",
        font_heading="'Georgia','Times New Roman',serif",
        font_body="'Courier New',Courier,monospace",
    ),
    "digital_neo_pop": ThemeSpec(
        id="digital_neo_pop",
        label="Digital Neo Pop",
        bg_color="#FFFFFF",
        text_color="#111111",
        accent_color="#FF2D7A",
        secondary_accent="#00D4FF",
        font_heading="'Arial Black','Impact',sans-serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
    "anti_gravity": ThemeSpec(
        id="anti_gravity",
        label="Anti-Gravity",
        bg_color="#FFFFFF",
        text_color="#1A1A1A",
        accent_color="#4A9EE8",
        secondary_accent="#A78BFA",
        font_heading="'Helvetica Neue',Arial,sans-serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
    "deformed_persona": ThemeSpec(
        id="deformed_persona",
        label="Deformed Persona",
        bg_color="#F0E8D8",
        text_color="#2B2B2B",
        accent_color="#7EB8A0",
        secondary_accent="#D4A574",
        font_heading="'Helvetica Neue',Arial,sans-serif",
        font_body="'Helvetica Neue',Arial,sans-serif",
    ),
}


def get_theme(theme_id: str) -> ThemeSpec:
    if theme_id not in THEMES:
        raise ValueError(f"Unknown theme '{theme_id}'.")
    return THEMES[theme_id]


def list_themes() -> List[dict]:
    return [{"id": k, "label": v.label} for k, v in THEMES.items()]

