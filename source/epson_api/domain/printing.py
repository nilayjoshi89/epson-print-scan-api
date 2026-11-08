from dataclasses import dataclass
from ipaddress import IPv4Address
from typing import BinaryIO


def queue_name(printer_ip: IPv4Address) -> str:
    return "epson-" + str(printer_ip).replace(".", "-")


@dataclass(frozen=True)
class Document:
    content: BinaryIO
    size: int
    title: str


@dataclass(frozen=True)
class PrintSettings:
    model: str = "L3250_Series"
    copies: int = 1
    paper_type: str = "PLAIN"
    quality: str = "NORMAL"
    ink: str = "COLOR"
    page_size: str = "A4"
    brightness: int = 0
    contrast: int = 0
    saturation: int = 0
    page_ranges: str = "all"
    orientation: str = "auto"
    number_up: int = 1
    fit_to_page: bool = False

    @property
    def driver_options(self) -> dict[str, str]:
        return {
            "Ink": self.ink,
            "PageSize": self.page_size,
            "MediaType": f"{self.paper_type}_{self.quality}",
            "Brightness": str(self.brightness),
            "Contrast": str(self.contrast),
            "Saturation": str(self.saturation),
        }
