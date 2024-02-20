from dataclasses import dataclass

from PIL import Image
import pygments.lexers as lexers


@dataclass
class CodeSource:
    txt: str
    file: str

    @staticmethod
    def from_file(path: str):
        with open(path) as f:
            return CodeSource(''.join(f), path)

    def guess_lexer(self):
        return lexers.get_lexer_for_filename(self.file) \
                if self.file is not None \
                else lexers.guess_lexer(self.txt)

    def expand_tabs(self, tab_size=4):
        self.txt = self.txt.expandtabs(tab_size)

    def lex(self):
        lx = self.guess_lexer()
        if not lx:
            raise Exception('Unknown lexer!')
        return lx, lx.get_tokens(self.txt, lx)


class PatchSource:
    def __init__(self, path: str) -> None:
        self.path = path
        with Image.open(self.path) as im:
            self.size = im.size

        self._cut_points: list[int] = None
        self.res = None

    def __enter__(self):
        self.res = self.res or Image.open(self.path)
        return self.res

    def __exit__(self, *args):
        if self.res:
            self.res.close()
            self.res = None

    def cut_points(self):
        if self._cut_points is not None: return self._cut_points
        self._cut_points = []

        if self.size[0] * self.size[1] == 0: return self._cut_points

        with Image.open(self.path) as im:
            dat = tuple(im.getdata())
            width, height = im.size
            for y in range(height):
                p = y * width
                row = dat[p : p + width]
                if all(row[0] == p for p in row):
                    self._cut_points.append(y)

        self._cut_points = trim_consecutive(self._cut_points)
        self._cut_points.reverse()
        self._cut_points = trim_consecutive(self._cut_points, delta=-1)
        self._cut_points.reverse()
        return self._cut_points


def trim_consecutive(ns: list[int], delta=+1):
    if not ns: return ns
    ins = enumerate(ns)
    _, last = next(ins)
    for i, n in ins:
        if last + delta != n:
            break
        last = n
    else:
        return []
    return ns[i:]


@dataclass(slots=True)
class Block:
    root: int
    len: int
    rel_size: float = 0


def blocks(cut_points: list[int]):
    if not cut_points: return
    ns = iter(cut_points)
    last = next(ns)
    acc = [last]
    for n in ns:
        if n != last + 1:
            yield Block(acc[0], len(acc))
            acc = []
        last = n
        acc.append(last)
    if acc:
        yield Block(acc[0], len(acc))
