import argparse
import glob
import os
import os.path

from concurrent.futures import ProcessPoolExecutor, Future

from alive_progress import alive_bar
from PIL import Image

from codequilt.source import CodeSource, PatchSource
from codequilt.formatters import BasicFormatter, XStitchFormatter, STYLES
from codequilt.stitchers import SimpleStitcher, columns_and_height, extend_width


def render_file(inpath: str, outpath: str, formatter: BasicFormatter):
    src = CodeSource.from_file(inpath)
    if not src.txt: return None
    src.expand_tabs()
    lxr, tkns = src.lex()

    formatter.format(tkns, outpath)
    return outpath, formatter


def positive_int(value):
    try:
        v = int(value)
        if v > 0: return v
    except:
        pass
    raise argparse.ArgumentTypeError(f"{repr(value)} is not a positive integer")


def style(value):
    if value in STYLES: return value
    print('Please choose one of:')
    for i in range(0, len(STYLES), 8):
        print('\t', *STYLES[i:i+8])
    raise argparse.ArgumentTypeError(f'Unrecognized style: {value}')


def __main__():
    parser = argparse.ArgumentParser(description='make your code worthy of framing!')
    parser.add_argument('patch_source', nargs='+', help='file path(s), may use glob syntax')
    parser.add_argument('-o', '--output', default=os.path.join('.', 'output', 'quilt.png'), help='A file path for output (default: %(default)s)')
    parser.add_argument('-x', '--x_stitch', action='store_true', help='Use a x-stitch formatter to style your patches')
    parser.add_argument('-s', '--style', type=style, default='one-dark', help='Pick your favorite highlighting style! (default: %(default)s)')
    parser.add_argument('--no_docs', action='store_true', help='Exclude docstrings from your quilt')
    parser.add_argument('--no_comments', action='store_true', help='Exclude comments from your quilt')
    parser.add_argument('--line_width', type=positive_int, default=80, help='Set the max line width in chars (default: %(default)s)')
    args = parser.parse_args()
    if not os.path.isdir('./output'): os.mkdir('./output')
    patch_sources = [p for path in args.patch_source
               for p in glob.iglob(path, recursive=True)
                if os.path.isfile(p)]
    patch_outputs = [os.path.join('.', 'output', p.replace(os.sep, '..').strip('.') + '.png')
              for p in patch_sources]
    with alive_bar(len(patch_sources), title='reading sources  ') as bar:
        fmts = dict()
        def callback(fut: Future):
            res = fut.result()
            bar()
            if not res: return
            o, f = res
            fmts[o] = f
        with ProcessPoolExecutor() as executor:
            formatter = XStitchFormatter if args.x_stitch else BasicFormatter
            for p, out in zip(patch_sources, patch_outputs):
                fmt = formatter(
                    style=args.style,
                    exclude_comments=args.no_comments,
                    exclude_docs=args.no_docs,
                    line_width=args.line_width,
                )
                fut = executor.submit(render_file, p, out, fmt)
                fut.add_done_callback(callback)

    bg_color = list(fmts.values())[0].style.background_color

    maxwidth = 0
    for k in fmts:
        with Image.open(k) as img:
            maxwidth = max(maxwidth, img.width)
    with alive_bar(len(fmts), title='resize patches   ') as bar:
        ptchs: list[PatchSource] = []
        def callback(fut: Future):
            o = fut.result()
            ptchs.append(PatchSource(o))
            bar()
        with ProcessPoolExecutor() as executor:
            for k in fmts:
                executor \
                    .submit(extend_width, k, maxwidth, bg_color) \
                    .add_done_callback(callback)
        ptchs.sort(key=lambda p: patch_outputs.index(p.path))


    with alive_bar(len(ptchs), title='load cut points  ') as bar:
        with ProcessPoolExecutor() as executor:
            def wrapper(p: PatchSource):
                def callback(f: Future):
                    # memoizing doesn't work across processes??
                    p._cut_points = f.result()
                    bar()
                return callback
            for p in ptchs:
                executor \
                    .submit(PatchSource.cut_points, p) \
                    .add_done_callback(wrapper(p))


    ratios = (5,4), (16,10), (4,3), (16,9), (3,2), (2,1), (1,1)
    with alive_bar(len(ratios), title='pick aspect ratio') as bar:
        min_scoring = float('inf'), 0, None
        for alpha in ratios:
            h, cols = columns_and_height(ptchs, alpha[0] / alpha[1])
            score = sum(c.dangling(h) for c in cols)
            if score < min_scoring[0]:
                min_scoring = score, alpha, cols
            bar()
        score, alpha, cols = min_scoring

    stchr = SimpleStitcher(cols, maxwidth)
    with alive_bar(stchr.total_patches(), title='stitch patches   ') as bar:
        img = stchr.stitch_patches(5, bg_color, bar)

    for f in patch_outputs:
        if os.path.isfile(f):
            os.remove(f)
    patch_outputs = args.output
    print('saving to', patch_outputs)
    img.save(patch_outputs)




if __name__ == '__main__':
    # import cProfile
    # cProfile.run('__main__()')
    __main__()
