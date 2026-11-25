"""Read what the tests check in an exported PDF, as a reader sees it.

Backed by pypdfium2. Positions are in pt, with the origin at the top left of the page.
"""

from __future__ import annotations

import ctypes
from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING

import cv2
import pypdf
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from pypdf.generic import DictionaryObject, PdfObject


if TYPE_CHECKING:
    from collections.abc import Generator, Iterator

    import numpy as np
    from numpy.typing import NDArray

Rect = tuple[float, float, float, float]

# A line ends where the next word starts lower than this share of the height of the current one
SAME_LINE_SHARE: float = 0.5

# A span ends where the next character starts further right than this share of the height of the last one:
# PDFium reads the cells of a table row as one line, a reader as one span per cell
SPAN_GAP_SHARE: float = 0.5


@dataclass(frozen=True)
class Box:
    """A rectangle on the page, in pt, measured from the top left corner."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass(frozen=True)
class Word:
    """A run of characters between spaces or line breaks."""

    box: Box
    text: str


@dataclass(frozen=True)
class Span:
    """A run of characters on one line in one font and one fill color, as 0xRRGGBB."""

    box: Box
    text: str
    font: str
    color: int


@dataclass(frozen=True)
class Image:
    """A raster image drawn on the page: its size in pixels and the box it is drawn into."""

    box: Box
    width: int
    height: int


@contextmanager
def open_pdf(data: bytes) -> Generator[pdfium.PdfDocument]:
    """Open PDF bytes and close the document when the block ends."""
    document: pdfium.PdfDocument = pdfium.PdfDocument(data)
    try:
        yield document
    finally:
        document.close()


@contextmanager
def _textpage(page: pdfium.PdfPage) -> Generator[pdfium.PdfTextPage]:
    textpage: pdfium.PdfTextPage = page.get_textpage()
    try:
        yield textpage
    finally:
        textpage.close()


def _box(page: pdfium.PdfPage, left: float, bottom: float, right: float, top: float) -> Box:
    height: float = page.get_height()
    return Box(left, height - top, right, height - bottom)


def _union(boxes: list[Rect]) -> Rect:
    return min(box[0] for box in boxes), min(box[1] for box in boxes), max(box[2] for box in boxes), max(box[3] for box in boxes)


def _objects_on_page(
    page: pdfium.PdfPage,
    form: pdfium.PdfObject | None = None,
    to_page: pdfium.PdfMatrix | None = None,
) -> Iterator[tuple[pdfium.PdfObject, pdfium.PdfMatrix | None]]:
    """Yield each object with the matrix from its form space to page space, None on the page itself.

    PDFium gives the bounds of an object inside a form XObject in the space of that form.
    """
    for obj in page.get_objects(max_depth=0, form=form):
        yield obj, to_page
        if pdfium_c.FPDFPageObj_GetType(obj.raw) == pdfium_c.FPDF_PAGEOBJ_FORM:
            form_to_page: pdfium.PdfMatrix = obj.get_matrix() if to_page is None else obj.get_matrix().multiply(to_page)
            yield from _objects_on_page(page, obj, form_to_page)


def _page_bounds(obj: pdfium.PdfObject, to_page: pdfium.PdfMatrix | None) -> Rect:
    bounds: Rect = obj.get_bounds()
    if to_page is None:
        return bounds
    corners: list[tuple[float, float]] = [to_page.on_point(x, y) for x in (bounds[0], bounds[2]) for y in (bounds[1], bounds[3])]
    return _union([(x, y, x, y) for x, y in corners])


def size(page: pdfium.PdfPage) -> tuple[float, float]:
    """Return the width and the height of the page in pt."""
    return page.get_width(), page.get_height()


def render_png(page: pdfium.PdfPage, dpi: int) -> bytes:
    """Rasterize the page at DPI onto white and return it as PNG bytes.

    PDFium renders BGR, the channel order OpenCV encodes from and the snapshot comparison reads back.
    """
    bitmap: pdfium.PdfBitmap = page.render(scale=dpi / 72, fill_color=(255, 255, 255, 255), may_draw_forms=True)
    pixels: NDArray[np.uint8] = bitmap.to_numpy()
    encoded: bool
    png: NDArray[np.uint8]
    encoded, png = cv2.imencode(".png", pixels)
    if not encoded:
        msg: str = "OpenCV could not encode the rendered page as PNG"
        raise RuntimeError(msg)
    return png.tobytes()


def text(page: pdfium.PdfPage) -> str:
    """Return the text of the page in the order the content stream draws it."""
    with _textpage(page) as textpage:
        return textpage.get_text_bounded()


def words(page: pdfium.PdfPage) -> list[Word]:
    """Return the words of the page in content order. A space or a line break ends a word."""
    found: list[Word] = []
    with _textpage(page) as textpage:
        chars: list[str] = []
        boxes: list[Rect] = []
        for index in range(textpage.count_chars() + 1):
            char: str = textpage.get_text_range(index, 1) if index < textpage.count_chars() else ""
            if char and not char.isspace():
                chars.append(char)
                boxes.append(textpage.get_charbox(index, loose=True))
            elif chars:
                found.append(Word(_box(page, *_union(boxes)), "".join(chars)))
                chars, boxes = [], []
    return found


def sorted_text(page: pdfium.PdfPage) -> str:
    """Return the text of the page in reading order: lines top to bottom, words left to right."""
    lines: list[list[Word]] = []
    for word in sorted(words(page), key=lambda word: (word.box.y0, word.box.x0)):
        line: list[Word] | None = lines[-1] if lines else None
        if line is not None and word.box.y0 - line[0].box.y0 < line[0].box.height * SAME_LINE_SHARE:
            line.append(word)
        else:
            lines.append([word])
    return "\n".join(" ".join(word.text for word in sorted(line, key=lambda word: word.box.x0)) for line in lines)


def _font_name(textpage: pdfium.PdfTextPage, index: int) -> str:
    flags: ctypes.c_int = ctypes.c_int()
    length: int = pdfium_c.FPDFText_GetFontInfo(textpage.raw, index, None, 0, ctypes.byref(flags))
    if length <= 0:
        return ""
    buffer: ctypes.Array[ctypes.c_char] = ctypes.create_string_buffer(length)
    pdfium_c.FPDFText_GetFontInfo(textpage.raw, index, buffer, length, ctypes.byref(flags))
    return buffer.value.decode("utf-8", errors="replace").split("+")[-1]


def _fill_color(textpage: pdfium.PdfTextPage, index: int) -> int:
    red: ctypes.c_uint = ctypes.c_uint()
    green: ctypes.c_uint = ctypes.c_uint()
    blue: ctypes.c_uint = ctypes.c_uint()
    alpha: ctypes.c_uint = ctypes.c_uint()
    if not pdfium_c.FPDFText_GetFillColor(textpage.raw, index, ctypes.byref(red), ctypes.byref(green), ctypes.byref(blue), ctypes.byref(alpha)):
        return 0
    return (red.value << 16) | (green.value << 8) | blue.value


def _starts_apart(last: Rect, box: Rect) -> bool:
    """Tell whether a character box starts a new span: well right of the last one, or on another line."""
    height: float = last[3] - last[1]
    if box[0] - last[2] > height * SPAN_GAP_SHARE:
        return True
    return abs((box[1] + box[3]) - (last[1] + last[3])) / 2 > height * SAME_LINE_SHARE


def spans(page: pdfium.PdfPage) -> list[Span]:
    """Return the runs of characters which share a line, a font and a fill color, in content order.

    A character PDFium generates, a space or a line break it infers, belongs to no span of its own.
    """
    found: list[Span] = []
    with _textpage(page) as textpage:
        current: tuple[str, int] | None = None
        chars: list[str] = []
        boxes: list[Rect] = []

        def flush() -> None:
            if chars and current is not None and "".join(chars).strip():
                found.append(Span(_box(page, *_union(boxes)), "".join(chars), current[0], current[1]))

        for index in range(textpage.count_chars()):
            char: str = textpage.get_text_range(index, 1)
            if char in ("\r", "\n") or pdfium_c.FPDFText_IsGenerated(textpage.raw, index) == 1:
                flush()
                current, chars, boxes = None, [], []
                continue
            style: tuple[str, int] = (_font_name(textpage, index), _fill_color(textpage, index))
            box: Rect = textpage.get_charbox(index, loose=True)
            if style != current or (boxes and _starts_apart(boxes[-1], box)):
                flush()
                current, chars, boxes = style, [], []
            chars.append(char)
            boxes.append(box)
        flush()
    return found


def embedded_fonts(data: bytes) -> set[str]:
    """Return the base names of the fonts the pages of a document carry, forms included, without a subset tag.

    A font a page carries counts even where no glyph of it is drawn, which is what embedding a font twice shows.
    """
    reader: pypdf.PdfReader = pypdf.PdfReader(BytesIO(data))
    names: set[str] = set()
    seen: set[int] = set()

    def dictionary(value: object) -> DictionaryObject:
        resolved: object = value.get_object() if isinstance(value, PdfObject) else value
        return resolved if isinstance(resolved, DictionaryObject) else DictionaryObject()

    def read(resources: DictionaryObject) -> None:
        if id(resources) in seen:
            return
        seen.add(id(resources))
        for font in dictionary(resources.get("/Font")).values():
            names.add(str(dictionary(font).get("/BaseFont", "")).lstrip("/").split("+")[-1])
        for reference in dictionary(resources.get("/XObject")).values():
            xobject: DictionaryObject = dictionary(reference)
            if xobject.get("/Subtype") == "/Form":
                read(dictionary(xobject.get("/Resources")))

    for page in reader.pages:
        read(dictionary(page.get("/Resources")))
    return names


def images(page: pdfium.PdfPage) -> list[Image]:
    """Return the raster images drawn on the page, forms included, with their pixel size and page box."""
    found: list[Image] = []
    for obj, to_page in _objects_on_page(page):
        if pdfium_c.FPDFPageObj_GetType(obj.raw) != pdfium_c.FPDF_PAGEOBJ_IMAGE:
            continue
        width: ctypes.c_uint = ctypes.c_uint()
        height: ctypes.c_uint = ctypes.c_uint()
        pdfium_c.FPDFImageObj_GetImagePixelSize(obj.raw, ctypes.byref(width), ctypes.byref(height))
        found.append(Image(_box(page, *_page_bounds(obj, to_page)), width.value, height.value))
    return found
