"""Where a PDF draws its pictures, whichever renderer of WeasyPrint service drew an SVG.

WeasyPrint service draws an SVG in one of two ways, as its ``SVG_RENDERER`` states. Chromium rasterizes it
to a PNG, an image XObject like any other picture. The weasysvg plugin draws it as vector, a form XObject of
its own without a transparency group: the forms WeasyPrint itself makes, for a page or for opacity, all carry
one. Both count as a picture here, so a test checks the same number, size and place whichever renderer drew them.
A form counted as a picture is not read further, so a picture inside an SVG is not counted a second time.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pypdf
from pypdf.generic import ArrayObject, ContentStream, DictionaryObject, NameObject, PdfObject


if TYPE_CHECKING:
    from pypdf import PageObject

Matrix = tuple[float, float, float, float, float, float]

IDENTITY: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

# The square an image XObject is drawn into, before the matrix in force scales it to its size
UNIT_SQUARE: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)

# The depth of transparency groups read, which a PDF of WeasyPrint never reaches
MAX_GROUP_DEPTH: int = 16


@dataclass(frozen=True)
class DrawnPicture:
    """A picture as a reader sees it: the page counted from zero, and its box in points from the top left corner of the page."""

    page: int
    x0: float
    y0: float
    width: float
    height: float
    vector: bool


def _multiply(first: Matrix, second: Matrix) -> Matrix:
    """The matrix which applies ``first``, then ``second``."""
    return (
        first[0] * second[0] + first[1] * second[2],
        first[0] * second[1] + first[1] * second[3],
        first[2] * second[0] + first[3] * second[2],
        first[2] * second[1] + first[3] * second[3],
        first[4] * second[0] + first[5] * second[2] + second[4],
        first[4] * second[1] + first[5] * second[3] + second[5],
    )


def _dictionary_of(value: PdfObject | None) -> DictionaryObject | None:
    resolved: PdfObject | None = value.get_object() if value is not None else None
    return resolved if isinstance(resolved, DictionaryObject) else None


def _matrix_of(values: object) -> Matrix:
    if not isinstance(values, list | tuple) or len(values) != 6:
        return IDENTITY
    numbers: list[float] = [float(value) for value in values]
    return (numbers[0], numbers[1], numbers[2], numbers[3], numbers[4], numbers[5])


class _Collector:
    def __init__(self, reader: pypdf.PdfReader, page_index: int, page_height: float) -> None:
        self.reader = reader
        self.page_index = page_index
        self.page_height = page_height
        self.pictures: list[DrawnPicture] = []

    def read(self, stream: object, resources: DictionaryObject | None, ctm: Matrix, depth: int) -> None:
        xobjects: DictionaryObject = (_dictionary_of(resources.get("/XObject")) if resources is not None else None) or DictionaryObject()
        stack: list[Matrix] = []
        content: ContentStream = stream if isinstance(stream, ContentStream) else ContentStream(stream, self.reader)
        for operands, operator in content.operations:
            if operator == b"q":
                stack.append(ctm)
            elif operator == b"Q" and stack:
                ctm = stack.pop()
            elif operator == b"cm":
                ctm = _multiply(_matrix_of(operands), ctm)
            elif operator == b"Do" and isinstance(operands[0], NameObject) and operands[0] in xobjects:
                xobject: DictionaryObject | None = _dictionary_of(xobjects[operands[0]])
                if xobject is not None:
                    self._draw(xobject, ctm, depth)

    def _draw(self, xobject: DictionaryObject, ctm: Matrix, depth: int) -> None:
        subtype: object = xobject.get("/Subtype")
        if subtype == "/Image":
            self._add(UNIT_SQUARE, ctm, vector=False)
        elif subtype == "/Form":
            matrix: Matrix = _multiply(_matrix_of(xobject.get("/Matrix")), ctm)
            if "/Group" not in xobject:
                bbox: PdfObject | None = xobject["/BBox"].get_object()
                if isinstance(bbox, ArrayObject) and len(bbox) == 4:
                    corners: list[float] = [float(value) for value in bbox]
                    self._add((corners[0], corners[1], corners[2], corners[3]), matrix, vector=True)
            elif depth < MAX_GROUP_DEPTH:
                self.read(xobject, _dictionary_of(xobject.get("/Resources")), matrix, depth + 1)

    def _add(self, rectangle: tuple[float, float, float, float], matrix: Matrix, *, vector: bool) -> None:
        """Adds the box the rectangle is drawn in: its four corners through the matrix."""
        corners: list[tuple[float, float]] = [(rectangle[0], rectangle[1]), (rectangle[2], rectangle[1]), (rectangle[0], rectangle[3]), (rectangle[2], rectangle[3])]
        xs: list[float] = [matrix[0] * corner[0] + matrix[2] * corner[1] + matrix[4] for corner in corners]
        ys: list[float] = [matrix[1] * corner[0] + matrix[3] * corner[1] + matrix[5] for corner in corners]
        self.pictures.append(DrawnPicture(self.page_index, min(xs), self.page_height - max(ys), max(xs) - min(xs), max(ys) - min(ys), vector))


def drawn_pictures(pdf_bytes: bytes) -> list[DrawnPicture]:
    """Every picture the document draws, raster or SVG, in the order the pages draw them."""
    reader: pypdf.PdfReader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pictures: list[DrawnPicture] = []
    for page_index, page in enumerate(reader.pages):
        pictures.extend(_pictures_of(reader, page_index, page))
    return pictures


def _pictures_of(reader: pypdf.PdfReader, page_index: int, page: PageObject) -> list[DrawnPicture]:
    contents: object = page.get_contents()
    if contents is None:
        return []
    collector: _Collector = _Collector(reader, page_index, float(page.mediabox.height))
    collector.read(contents, _dictionary_of(page.get("/Resources")), IDENTITY, 0)
    return collector.pictures


def drawn_by_weasysvg(pdf_bytes: bytes) -> bool:
    """Whether the weasysvg plugin drew an SVG of the document, which decides the reference images it is compared with."""
    return any(picture.vector for picture in drawn_pictures(pdf_bytes))
