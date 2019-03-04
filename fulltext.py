import json
from pathlib import Path
from bottle import template, TEMPLATE_PATH


DR = Path(__file__).parent
# デフォルトのTEMPLATE_PATHは実行ディレクトリの相対パス
TEMPLATE_PATH.append(DR)


class D(dict):
    __getattr__ = dict.__getitem__


class Line:

    def __init__(self, w):
        self.x0 = self.y0 = self.x1 = self.y1 = 0
        self.words = [w]


class HocrPage:

    def __init__(self, page, line_tolerance=5):
        self.last_baseline = -100
        self.line_tolerance = line_tolerance  # これ以下なら同じ行
        if 'property' in page:
            self.lang = page.property.detectedLanguages[0].languageCode
        else:
            self.lang = 'en'
        self.blocks = page.blocks
        self.width = page.width
        self.height = page.height
        self.bi = self.pi = self.wi = 1
        for block in self.blocks:
            self.bi = self.newattrs(block, self.bi)

            for par in block.paragraphs:
                self.pi = self.newattrs(par, self.pi)
                par.lines = []

                for w in par.words:
                    w.text = ''
                    self.wi = self.newattrs(w, self.wi)

                    for sym in w.symbols:
                        w.text += sym.text

                    diff = abs(self.last_baseline - w.y1)
                    if diff >= self.line_tolerance:
                        par.lines.append(Line(w))
                    else:
                        par.lines[-1].words.append(w)
                    self.last_baseline = w.y1

                [
                    self.maximize_bbox(line, line.words)
                    for line in par.lines
                ]
                self.last_baseline = -100
                self.maximize_bbox(par, par.words)
            self.maximize_bbox(block, block.paragraphs)

    def newattrs(self, e, ei):
        if 'confidence' in e:
            e.conf = int(e.confidence * 100)
        else:
            e.conf = 0
        v = e.boundingBox.vertices
        e.x0 = v[0].x if 'x' in v[0] and v[0].x > 0 else 0
        e.y0 = v[0].y if 'y' in v[0] and v[0].y > 0 else 0
        e.x1 = v[2].x if 'x' in v[2] and v[2].x > 0 else 0
        e.y1 = v[2].y if 'y' in v[2] and v[2].y > 0 else 0
        e.id = ei
        return ei + 1

    def maximize_bbox(self, e, elist):
        e.x0 = min([ee.x0 for ee in elist])
        e.y0 = min([ee.y0 for ee in elist])
        e.x1 = max([ee.x1 for ee in elist])
        e.y1 = max([ee.y1 for ee in elist])


class FullText:

    def __init__(self, jp, line_tolerance=5):
        self.jp = jp
        self.j = json.loads(jp.read_text(), object_hook=D)
        if not self.j.responses[0]:
            self.pages = []
        else:
            self.pages = self.j.responses[0].fullTextAnnotation.pages
        self.hocrpages = [
            HocrPage(page, line_tolerance) for page in self.pages
        ]

    def print_symbols(self):
        for page in self.pages:
            for block in page.blocks:  # ocr_carea
                for par in block.paragraphs:  # ocr_par
                    # yの位置でocr_line設定? => いらない？
                    for w in par.words:
                        for sym in w.symbols:
                            print(sym.text)

    def to_hocr(self):
        multiple = len(self.hocrpages) > 1

        for i, hocrpage in enumerate(self.hocrpages):
            if multiple:
                hp = self.jp.with_suffix('.%s.hocr' % i)
            else:
                hp = self.jp.with_suffix('.hocr')
            s = template(
                'page.html',
                blocks=hocrpage.blocks,
                title=hp.name,
                lang=hocrpage.lang,
                page_width=hocrpage.width,
                page_height=hocrpage.height
            )
            hp.write_text(s)


def main():
    """Main."""
    from argparse import ArgumentParser
    parser = ArgumentParser(
        description='full_gcv2hocr converts from fullTextAnnotation of Google Cloud Vision API to hOCR.'
    )
    parser.add_argument(
        'jp_strs', type=str, nargs='+',
        help='json file path strings'
    )
    parser.add_argument(
        '--line_tolerance', type=int, nargs='?',
        action='store', default=5,
        help='base line tolerance'
    )
    args = parser.parse_args()

    for jp_str in args.jp_strs:
        fp = Path(jp_str)
        fulltext = FullText(fp, args.line_tolerance)
        fulltext.to_hocr()


if __name__ == '__main__':
    main()
