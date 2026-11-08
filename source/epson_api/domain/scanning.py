from dataclasses import dataclass

MAX_WIDTH_MM = 215.9
MAX_HEIGHT_MM = 297.18
PAPER_SIZES_MM = {"A4": (210, 297), "A5": (148, 210), "B5": (176, 250), "Letter": (215.9, 279.4)}


@dataclass(frozen=True)
class ScanArea:
    width_mm: float
    height_mm: float


@dataclass(frozen=True)
class ScanSettings:
    resolution: int = 300
    mode: str = "Color"
    format: str = "png"
    area: ScanArea | None = None
