import ast
import inspect
import re
import shlex
import sys
from typing import Iterator


class Splitter(Iterator[str]):
    s: str
    use_shlex: bool
    _shlex: shlex.shlex
    _data: str

    def _make_shlex(self, s: str):
        self._shlex = shlex.shlex(s, posix=True)
        self._shlex.whitespace_split = True
        self._shlex.commenters = ''

    def __init__(self, s: str, use_shlex: bool):
        self.use_shlex = use_shlex
        if use_shlex:
            self._make_shlex(s)
        else:
            self._data = s

    def __next__(self):
        if self.use_shlex:
            return next(self._shlex)
        else:
            if not self._data:
                raise StopIteration
            spl = self._data.split(maxsplit=1)
            if len(spl) == 1:
                self._data = ''
                return spl[0]
            res, self._data = spl
            return res

    @property
    def remaining_data(self):
        if self.use_shlex:
            res = self._shlex.instream.read()
            self._make_shlex(res)
            return res
        else:
            return self._data

    @remaining_data.setter
    def remaining_data(self, s: str):
        if self.use_shlex:
            self._make_shlex(s)
        else:
            self._data = s


CMD_REGEX = re.compile(r'!(?P<name>\w+)(?:\s+(?P<args>.*?))?\s*(?P<end>\)|\+|-|$)', flags=re.MULTILINE)


def convert_code(code: str) -> str:
    return CMD_REGEX.sub(r'_run_smoked(locals(), \g<name>, "\g<args>")\g<end>', code)


_ast_parse = ast.parse


def _patched_ast_parse(code: str, *args):
    return _ast_parse(convert_code(code), *args)


ast.parse = _patched_ast_parse


def _run_smoked(locs, function, args: str):
    sig = inspect.signature(function)
    params = list(sig.parameters.values())
    data = Splitter(args.strip(), True)
    res = []
    for i, param in enumerate(params):
        try:
            if i == len(params) - 1:
                arg = data.remaining_data
            else:
                arg = next(data)
            if not arg:
                raise StopIteration
            try:
                arg = eval(arg, {}, locs)
            except NameError:
                pass
            res.append(arg)
        except StopIteration:
            if param.default == param.empty:
                raise ValueError(f'Missing argument {param.name}')
            else:
                res.append(param.default)
    return function(*res)


from app.run_code.variables import variables

variables['_run_smoked'] = _run_smoked
