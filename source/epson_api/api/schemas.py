from dataclasses import dataclass
from ipaddress import IPv4Address
from pathlib import Path
from typing import Annotated, Literal

from fastapi import File, Form, UploadFile
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from epson_api.domain.printing import Document, PrintSettings
from epson_api.domain.scanning import MAX_HEIGHT_MM, MAX_WIDTH_MM, PAPER_SIZES_MM, ScanArea, ScanSettings

OPTION_VALUE = r"^[A-Za-z0-9_.+-]+$"
PAGE_RANGES = r"^(all|\d+(-\d*)?(,\d+(-\d*)?)*)$"
NUMBER_UP = {1, 2, 4, 6, 9, 16}
PRINTER_IP_DESCRIPTION = (
    "Private LAN IPv4 address of the printer. Public, loopback and link-local addresses are rejected."
)
ADJUSTMENT_RANGE = "Adjustment from -25 to 25, where 0 leaves the output unchanged."


def check_printer_ip(ip: IPv4Address) -> IPv4Address:
    if not ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified:
        raise ValueError("must be a private LAN address")
    return ip


def check_number_up(value: int) -> int:
    if value not in NUMBER_UP:
        raise ValueError(f"must be one of {sorted(NUMBER_UP)}")
    return value


PrinterIp = Annotated[IPv4Address, AfterValidator(check_printer_ip)]
Orientation = Literal["auto", "portrait", "landscape", "reverse_landscape", "reverse_portrait"]


class ScanRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"printer_ip": "192.168.0.64", "resolution": 300, "format": "pdf", "paper_size": "A4"},
                {"printer_ip": "192.168.0.64", "paper_size": "custom", "width_mm": 100, "height_mm": 150},
            ]
        }
    )

    printer_ip: PrinterIp = Field(description=PRINTER_IP_DESCRIPTION)
    resolution: Literal[75, 150, 300, 600, 1200] = Field(300, description="Scan resolution in dots per inch.")
    mode: Literal["Color", "Gray", "Lineart"] = Field("Color", description="Color mode of the scan.")
    format: Literal["png", "jpeg", "tiff", "pdf"] = Field("png", description="File format of the returned scan.")
    paper_size: Literal["full", "A4", "A5", "B5", "Letter", "custom"] = Field(
        "full",
        description=(
            "Area to scan, measured from the top-left corner of the glass. `full` is the whole flatbed. "
            "`B5` is the ISO size, 176 x 250 mm. `custom` requires `width_mm` and `height_mm`."
        ),
    )
    width_mm: Annotated[float, Field(gt=0, le=MAX_WIDTH_MM)] | None = Field(
        None, description="Scan width in millimetres. Required when `paper_size` is `custom`, and rejected otherwise."
    )
    height_mm: Annotated[float, Field(gt=0, le=MAX_HEIGHT_MM)] | None = Field(
        None, description="Scan height in millimetres. Required when `paper_size` is `custom`, and rejected otherwise."
    )

    @model_validator(mode="after")
    def check_custom_size(self) -> "ScanRequest":
        sizes = [size for size in (self.width_mm, self.height_mm) if size is not None]
        if self.paper_size == "custom" and len(sizes) < 2:
            raise ValueError("custom paper_size needs width_mm and height_mm")
        if self.paper_size != "custom" and sizes:
            raise ValueError("width_mm and height_mm are only valid with custom paper_size")
        return self

    def to_settings(self) -> ScanSettings:
        return ScanSettings(self.resolution, self.mode, self.format, self._area())

    def _area(self) -> ScanArea | None:
        if self.width_mm is not None and self.height_mm is not None:
            return ScanArea(self.width_mm, self.height_mm)
        if self.paper_size == "full":
            return None
        return ScanArea(*PAPER_SIZES_MM[self.paper_size])


@dataclass
class PrintForm:
    file: Annotated[
        UploadFile,
        File(
            description=(
                "Document to print, identified by its content. Supported types are PDF, PostScript, plain text, "
                "PNG, JPEG, TIFF, GIF, BMP, PNM and SVG. Convert anything else to PDF first."
            )
        ),
    ]
    printer_ip: Annotated[PrinterIp, Form(description=PRINTER_IP_DESCRIPTION)]
    model: Annotated[
        str,
        Form(
            pattern=OPTION_VALUE,
            description="Epson model name from an installed driver file, as in `Epson-<model>-*.ppd.gz`.",
        ),
    ] = "L3250_Series"
    copies: Annotated[int, Form(ge=1, le=99, description="Number of copies.")] = 1
    paper_type: Annotated[
        str,
        Form(
            pattern=OPTION_VALUE,
            description=(
                "Driver paper code. For the L3250: `PLAIN`, `SFINE`, `PMMATT`, `PLATINA`, `PMPHOTO`, `PSGLOS`, "
                "`LCPP` or `ENV`."
            ),
        ),
    ] = "PLAIN"
    quality: Annotated[
        Literal["HIGH", "NORMAL", "DRAFT"],
        Form(description="Print quality. `DRAFT` exists only for `PMPHOTO`, `PSGLOS` and `LCPP` on the L3250."),
    ] = "NORMAL"
    ink: Annotated[Literal["COLOR", "MONO"], Form(description="Color or black-only printing.")] = "COLOR"
    page_size: Annotated[
        str,
        Form(
            pattern=OPTION_VALUE,
            description=(
                "Driver page size code. For the L3250: `A4`, `A5`, `A6`, `B5`, `B6`, `Letter`, `Legal`, `16K`, "
                "`8x10`, `L`, `2L`, `TL`, `INDEX5`, `4X6FULL`, `T4X6FULL`, `4X7`, `T4X7`, `Postcard`, `TPostcard`, "
                "`ENV10`, `EnvDL` or `ENVC6`."
            ),
        ),
    ] = "A4"
    brightness: Annotated[int, Form(ge=-25, le=25, description=f"Brightness. {ADJUSTMENT_RANGE}")] = 0
    contrast: Annotated[int, Form(ge=-25, le=25, description=f"Contrast. {ADJUSTMENT_RANGE}")] = 0
    saturation: Annotated[int, Form(ge=-25, le=25, description=f"Saturation. {ADJUSTMENT_RANGE}")] = 0
    page_ranges: Annotated[str, Form(pattern=PAGE_RANGES, description="`all`, or a list such as `1-3,5,8-`.")] = "all"
    orientation: Annotated[Orientation, Form(description="Page orientation. `auto` keeps the document's own.")] = "auto"
    number_up: Annotated[
        int, Form(description="Pages per sheet: 1, 2, 4, 6, 9 or 16."), AfterValidator(check_number_up)
    ] = 1
    fit_to_page: Annotated[bool, Form(description="Scale the content to fit the page.")] = False

    def to_document(self) -> Document:
        return Document(self.file.file, self.file.size or 0, Path(self.file.filename or "upload").name)

    def to_settings(self) -> PrintSettings:
        return PrintSettings(
            model=self.model,
            copies=self.copies,
            paper_type=self.paper_type,
            quality=self.quality,
            ink=self.ink,
            page_size=self.page_size,
            brightness=self.brightness,
            contrast=self.contrast,
            saturation=self.saturation,
            page_ranges=self.page_ranges,
            orientation=self.orientation,
            number_up=self.number_up,
            fit_to_page=self.fit_to_page,
        )
