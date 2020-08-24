#!/usr/bin/env bash
python -m lark.tools.standalone sexp.lark > _sexp_parser.py
python -m compileall _sexp_parser.py
