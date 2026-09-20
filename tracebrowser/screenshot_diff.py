from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def difference_score(first: str | Path, second: str | Path) -> float:
    """Return a simple normalized pixel difference in [0, 1]."""
    a = Image.open(first).convert("RGB").resize((64, 64))
    b = Image.open(second).convert("RGB").resize((64, 64))
    diff = ImageChops.difference(a, b)
    mean = sum(ImageStat.Stat(diff).mean) / 3
    return round(mean / 255, 6)


def changed(first: str | Path, second: str | Path, threshold: float = 0.05) -> bool:
    return difference_score(first, second) >= threshold


def compare_images(first: str | Path, second: str | Path, threshold: float = 0.05) -> dict:
    """Return a JSON-ready comparison result for dashboard and CI consumers."""
    first_path = Path(first)
    second_path = Path(second)
    if not first_path.exists() or not second_path.exists():
        return {
            "status": "unavailable",
            "score": None,
            "changed": None,
            "threshold": threshold,
        }
    score = difference_score(first_path, second_path)
    return {
        "status": "compared",
        "score": score,
        "changed": score >= threshold,
        "threshold": threshold,
    }
