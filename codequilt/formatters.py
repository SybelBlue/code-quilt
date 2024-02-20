from pygments.formatters import ImageFormatter
from pygments.token import String, Comment, is_token_subtype
from pygments.styles._mapping import STYLES

STYLES = sorted({
    min((x for x in v if type(x) is str), key=len)
        for _, v in STYLES.items()
})

def clamp(low, v, hi): return max(low, min(v, hi))

class BasicFormatter(ImageFormatter):
    """
    `line_width`
        The character limit cut off of the source.

        Default: 80

    `exclude_docs`
        Will not paint docstrings into the quilt

        Default: False

    `exclude_comments`
        Will not paint comments into the quilt

        Default: False

    Additional options accepted:

    `image_format`
        An image format to output to that is recognised by PIL, these include:

        * "PNG" (default)
        * "JPEG"
        * "BMP"
        * "GIF"

    `line_pad`
        The extra spacing (in pixels) between each line of text.

        Default: 2

    `font_name`
        The font name to be used as the base font from which others, such as
        bold and italic fonts will be generated.  This really should be a
        monospace font to look sane.
        If a filename or a file-like object is specified, the user must
        provide different styles of the font.

        Default: "Courier New" on Windows, "Menlo" on Mac OS, and
                 "DejaVu Sans Mono" on \\*nix

    `font_size`
        The font size in points to be used.

        Default: 14

    `image_pad`
        The padding, in pixels to be used at each edge of the resulting image.

        Default: 10

    `hl_lines`
        Specify a list of lines to be highlighted.

        .. versionadded:: 1.2

        Default: empty list

    `hl_color`
        Specify the color for highlighting lines.

        .. versionadded:: 1.2

        Default: highlight color of the selected style
    """
    def __init__(self, exclude_comments=False, exclude_docs=False, line_width=80, **options):
        options['line_numbers'] = False
        super().__init__(**options)
        self.line_char_width = line_width
        self.exclude_comments = exclude_comments
        self.exclude_docs = exclude_docs

    def _create_drawables(self, tokensource):
        """
        Create drawables for the token content.
        """
        lineno = charno = maxcharno = 0
        maxlinelength = linelength = 0
        for ttype, value in tokensource:
            if self.exclude_comments and ttype in Comment:
                    continue
            if self.exclude_docs and ttype in String.Doc:
                    continue
            while ttype not in self.styles:
                ttype = ttype.parent
            style = self.styles[ttype]
            value = value.expandtabs(4)
            lines = value.splitlines(True)
            for line in lines:
                temp = line.rstrip('\n')
                temp_chars = len(temp)
                limit = clamp(0, temp_chars, self.line_char_width - charno)
                temp = temp[:limit]
                if temp:
                    self._draw_text(
                        self._get_text_pos(linelength, lineno),
                        temp,
                        font = self._get_style_font(style),
                        text_fg = self._get_text_color(style),
                        text_bg = self._get_text_bg_color(style),
                    )
                    temp_width, _ = self.fonts.get_text_size(temp)
                    linelength += temp_width
                    maxlinelength = max(maxlinelength, linelength)
                    charno += len(temp)
                    maxcharno = max(maxcharno, charno)
                if line.endswith('\n'):
                    # add a line for each extra line in the value
                    linelength = 0
                    charno = 0
                    lineno += 1
        self.maxlinelength = maxlinelength
        self.maxcharno = maxcharno
        self.maxlineno = lineno


class XStitchFormatter(BasicFormatter):
    def _draw_text(self, pos, text, font, text_fg, text_bg, mapping=('X', 'x', '+')):
        def map_char(c: str):
            if c.isnumeric():
                return mapping[2]
            if c.islower():
                return mapping[1]
            if c.isupper():
                return mapping[0]
            return c
        text = ''.join(map(map_char, text))
        return super()._draw_text(pos, text, font, text_fg, text_bg)
