import codecs
import re
from typing import BinaryIO

SAMPLE_BYTES = 1024 * 1024
BINARY_SIGNATURES = (
    b"%PDF-",
    b"%!",
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"GIF87a",
    b"GIF89a",
    b"II*\x00",
    b"MM\x00*",
    b"BM",
)
PNM_SIGNATURE = re.compile(rb"P[1-6]\s")
UNSUPPORTED_MARKUP = (b"<!doctype html", b"<html", b"{\\rtf")
ALLOWED_CONTROL_CHARACTERS = "\t\n\r\f"


class ContentDocumentInspector:
    def is_supported(self, content: BinaryIO) -> bool:
        sample = content.read(SAMPLE_BYTES)
        content.seek(0)
        start = sample.lstrip(b"\r\n")
        if start.startswith(BINARY_SIGNATURES) or PNM_SIGNATURE.match(start):
            return True
        if not sample or start.lstrip().lower().startswith(UNSUPPORTED_MARKUP):
            return False
        return self._is_text(sample)

    @staticmethod
    def _is_text(sample: bytes) -> bool:
        try:
            text = codecs.getincrementaldecoder("utf-8")().decode(sample)
        except UnicodeDecodeError:
            return False
        return not any(ord(char) < 32 and char not in ALLOWED_CONTROL_CHARACTERS for char in text)
