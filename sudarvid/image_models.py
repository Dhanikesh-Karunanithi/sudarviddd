from __future__ import annotations

from typing import List, Optional


IMAGE_MODELS: List[dict] = [
    {
        "id": "black-forest-labs/FLUX.1-schnell",
        "label": "FLUX.1 schnell",
        "family": "FLUX.1",
        "description": "FLUX.1 [schnell] is a 12B rectified flow transformer for fast text-to-image generation.",
        "pricing": "$0.003 per 1 million pixels @ 4 steps",
        "recommended_steps": 4,
    },
    {
        "id": "black-forest-labs/FLUX.1-krea-dev",
        "label": "FLUX.1 krea dev",
        "family": "FLUX.1",
        "description": "FLUX.1 variant tuned for higher quality composition.",
        "pricing": "$0.025 per 1 million pixels @ 30 steps",
        "recommended_steps": 30,
    },
    {
        "id": "black-forest-labs/FLUX.1-kontext-pro",
        "label": "FLUX.1 kontext pro",
        "family": "FLUX.1",
        "description": "FLUX.1 Kontext Pro for stronger consistency and prompt fidelity.",
        "pricing": "$0.040 per 1 million pixels",
        "recommended_steps": None,
    },
    {
        "id": "black-forest-labs/FLUX.1-kontext-max",
        "label": "FLUX.1 kontext max",
        "family": "FLUX.1",
        "description": "FLUX.1 Kontext Max for highest quality in the Kontext line.",
        "pricing": "$0.080 per 1 million pixels",
        "recommended_steps": None,
    },
    {
        "id": "Rundiffusion/Juggernaut-Lightning-Flux",
        "label": "Juggernaut Lightning Flux",
        "family": "Juggernaut",
        "description": "Blazing-fast, high-quality model for mood boards and mass ideation.",
        "pricing": "$0.0017 per 1 million pixels",
        "recommended_steps": None,
    },
    {
        "id": "black-forest-labs/FLUX.2-dev",
        "label": "FLUX.2 dev",
        "family": "FLUX.2",
        "description": "Production-focused FLUX.2 model for complex generation/editing with realistic details.",
        "pricing": "$0.0154 estimate per image (actual price may vary)",
        "recommended_steps": None,
    },
    {
        "id": "black-forest-labs/FLUX.2-flex",
        "label": "FLUX.2 flex",
        "family": "FLUX.2",
        "description": "Production FLUX.2 model for fast generation/editing with up to 4MP synthesis.",
        "pricing": "$0.03 estimate per text-to-image output (actual price may vary)",
        "recommended_steps": None,
    },
    {
        "id": "black-forest-labs/FLUX.2-pro",
        "label": "FLUX.2 pro",
        "family": "FLUX.2",
        "description": "High-fidelity FLUX.2 production model for realistic detail and consistency.",
        "pricing": "$0.03 estimate per text-to-image output (actual price may vary)",
        "recommended_steps": None,
    },
    {
        "id": "black-forest-labs/FLUX.2-max",
        "label": "FLUX.2 max",
        "family": "FLUX.2",
        "description": "Highest consistency for editing colors, lighting, faces, text, and objects in FLUX.2.",
        "pricing": "$0.070 per 1 million pixels @ 50 steps",
        "recommended_steps": 50,
    },
    {
        "id": "black-forest-labs/FLUX.1.1-pro",
        "label": "FLUX.1.1 pro",
        "family": "FLUX.1.1",
        "description": "Faster and higher-quality successor to FLUX.1 pro with stronger prompt adherence.",
        "pricing": "$0.040 per 1 million pixels",
        "recommended_steps": None,
    },
    {
        "id": "openai/gpt-image-1.5",
        "label": "GPT Image 1.5",
        "family": "OpenAI",
        "description": "OpenAI flagship model for detail-preserving image generation and edits.",
        "pricing": "$0.034 estimate per image (actual price may vary)",
        "recommended_steps": None,
    },
    {
        "id": "Wan-AI/Wan2.6-image",
        "label": "Wan2.6 image",
        "family": "Wan",
        "description": "Wan2.6 image model focused on prompt adherence and coherent spatial structure.",
        "pricing": "$0.03 estimate per output image (actual price may vary)",
        "recommended_steps": None,
    },
    {
        "id": "ByteDance-Seed/Seedream-3.0",
        "label": "Seedream 3.0",
        "family": "Seedream",
        "description": "Bilingual Chinese-English model with strong photorealism and text rendering.",
        "pricing": "$0.018 estimate at 720x1280 (actual price may vary)",
        "recommended_steps": None,
    },
    {
        "id": "ByteDance-Seed/Seedream-4.0",
        "label": "Seedream 4.0",
        "family": "Seedream",
        "description": "Next-gen multimodal model for fast 2K-4K generation, editing, and coherent batches.",
        "pricing": "$0.03 estimate at 720x1280 (actual price may vary)",
        "recommended_steps": None,
    },
    {
        "id": "ideogram/ideogram-3.0",
        "label": "Ideogram 3.0",
        "family": "Ideogram",
        "description": "Design-centric generation with sharper text rendering and stronger composition control.",
        "pricing": "$0.06 estimate at 720x1280 (actual price may vary)",
        "recommended_steps": None,
    },
]

DEFAULT_IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell"


def allowed_image_model_ids() -> set[str]:
    return {m["id"] for m in IMAGE_MODELS}


def normalize_image_model(value: Optional[str]) -> Optional[str]:
    v = (value or "").strip()
    return v or None
