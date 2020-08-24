from _sexp_parser import Lark_StandAlone as SexpParser, Transformer, inline_args


class SexpToJSON(Transformer):
    def sexp(self, args):
        sym, *values = args
        return {'k': sym, 'v': values}

    @inline_args
    def string(self, s):
        return s[1:-1].replace('\\"', '"')

    symbol = inline_args(str)
    int = inline_args(int)

    list = list

    nil = lambda self, _: None
    true = lambda self, _: True


sexpParser = SexpParser(transformer=SexpToJSON())

def parseSexpression(s: str):
    return sexpParser.parse(s).children[0]
