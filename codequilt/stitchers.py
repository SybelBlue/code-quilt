from dataclasses import dataclass, field
from math import sqrt
from operator import truediv
from typing import Callable

from PIL import Image

from codequilt.source import PatchSource


def extend_width(path: str, new_width: int, bg_color):
    with Image.open(path) as im:
        assert im.width <= new_width, f'error with {path}: has size {im.width}, resising to {new_width}'
        if im.width == new_width: return path
        new = Image.new('RGBA', (new_width, im.height), bg_color)
        new.paste(im, (0,0))
    new.save(path)
    return path


@dataclass(frozen=True, slots=True)
class SimpleStitcher:
    cols: list['ColumnData']
    column_width: int

    def total_patches(self):
        return sum(len(ptches.chunks) for ptches in self.cols)

    def stitch_patches(self, margin: int, bg_color, onprogress=None):
        h = max(col.padded_height(margin) for col in self.cols) + 2 * margin
        w = len(self.cols) * (self.column_width + margin) + margin
        img = Image.new('RGBA', (w, h), bg_color)
        img.resize((w, h))
        x = margin
        y = margin
        for ptches in self.cols:
            for ptch_chunk in ptches.chunks:
                p_len = len(ptch_chunk)
                bbox = x, y
                ptch_chunk.paste_into(img, bbox)
                if callable(onprogress): onprogress()
                y += p_len + margin

            x += self.column_width + margin
            y = margin
        return img


@dataclass(frozen=True)
class PatchChunk:
    colno: int
    patch: PatchSource
    start: int
    stop: int

    def __len__(self): return self.stop - self.start

    def paste_into(self, img: Image, box):
        with self.patch as src:
            cropped = src.crop((0, self.start, src.width, self.stop))
            img.paste(cropped, box)


@dataclass(frozen=True)
class ColumnData:
    height: int
    chunks: list[PatchChunk]

    def dangling(self, h: int):
        return h - sum(len(c) for c in self.chunks)

    def padded_height(self, margin: int):
        return sum(len(c) for c in self.chunks) + (max(0, len(self.chunks) - 1)) * margin


def columns_and_height(ptchs: list[PatchSource], alpha):
    if not ptchs: raise ValueError('Cannot stitch empty patch list')
    column_width = ptchs[0].size[0]
    if not all(column_width == im.size[0] for im in ptchs):
        raise ValueError(f"requires equal width sources: detected {column_width} px" )

    src_len = sum(src.size[1] for src in ptchs)
    h = round(sqrt(src_len * column_width / alpha))
    return h, columns(h, ptchs)


def columns(h: int, patches: list[PatchSource]) -> list[ColumnData]:
    last_col = -1
    columns = []
    col_height = 0
    for chunk in patch_chunking(h, patches):
        if chunk.colno != last_col:
            if last_col >= 0:
                columns[last_col] = ColumnData(col_height, columns[last_col])
            last_col += 1
            col_height = 0
            columns.append([])
        columns[chunk.colno].append(chunk)
        col_height += chunk.stop - chunk.start
    if last_col >= 0:
        columns[last_col] = ColumnData(col_height, columns[last_col])
    return columns

def patch_chunking(h: int, patches: list[PatchSource]):
    ps = iter(patches)
    curr = next(ps, None)
    colno = start = 0
    remaining_space = h
    while curr:
        if remaining_space == 0:
            remaining_space = h
            colno += 1

        remaining_height = curr.size[1] - start
        if remaining_height <= remaining_space:
            remaining_space -= remaining_height
            yield PatchChunk(colno, curr, start, start + remaining_height)
            curr = next(ps, None)
            start = 0
            continue

        # seeker = iter(cp for cp in reversed(curr.cut_points()) if cp - start <= remaining_space)
        # cut_point = next(seeker, remaining_space)
        cut_point = min(curr.cut_points(), key=lambda cp: abs(cp - start - remaining_space))
        if cut_point > start:
            remaining_space = 0
            yield PatchChunk(colno, curr, start, cut_point)
            start = cut_point
