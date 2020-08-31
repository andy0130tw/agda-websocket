from _sexp_parser import Lark_StandAlone as SexpParser, Transformer, inline_args


class SexpToJSON(Transformer):
    def sexp(self, args):
        sym, *values = args
        return {'k': sym, 'v': values}

    @inline_args
    def string(self, s):
        return (s[1:-1].replace('\\"', '"')
                       .replace('\\n', '\n'))

    symbol = inline_args(str)
    int = inline_args(int)

    list = list

    nil = lambda self, _: None
    true = lambda self, _: True

    '''See https://git.io/JUqbR. We patch it into the command sexp.'''
    @inline_args
    def lastcmd(self, priority, cmd):
        cmd['priority'] = priority[1]
        return cmd


sexpParser = SexpParser(transformer=SexpToJSON())

def parseSexpression(s: str):
    return sexpParser.parse(s).children[0]
