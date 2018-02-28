# Structured regex-like notation for nested word automata


import re
from .nwa import *


class Pattern(object):
    def __init__(self):
        self.nwa = None

    def match(self, pattern, **kwargs):
        return self.build().match(pattern, **kwargs)

    def build(self):
        if self.nwa is None:
            self.nwa = NWA(self)

        return self.nwa

    def __add__(self, other):
        return Seq(self, other)

    def __or__(self, other):
        return Alt(self, other)


class Empty(Pattern):
    def nwaify(self, cont):
        return cont


class Function(Pattern):
    def __init__(self, function):
        super().__init__()
        self.function = function

    def nwaify(self, cont):
        return (NWAFunction(self.function, cont),)


# I don't trust Python implementations to have safe-for-space
# closures.
def _make_regex_matcher(regex):
    def match(item):
        if not isinstance(item, str):
            return None
        return re.fullmatch(regex, item)
    def match_no_group(item):
        if not isinstance(item, str):
            return None
        return () if re.fullmatch(regex, item) else None

    return match_no_group if regex.groups == 0 else match


class Regex(Function):
    def __init__(self, regex):
        if isinstance(regex, str):
            regex = re.compile(regex)
        super().__init__(_make_regex_matcher(regex))


class Any(Function):
    def __init__(self):
        super().__init__(lambda item: ())


class Literal(Function):
    def __init__(self, literal):
        super().__init__(lambda item: () if item == literal else None)


def _make_nwa_matcher(nwa):
    def match(item):
        return nwa.match(item)
    return match


class Nest(Function):
    def __init__(self, *nest):
        super().__init__(_make_nwa_matcher(compile(*nest)))


class Plus(Pattern):
    def __init__(self, *subpattern):
        super().__init__()
        self.subpattern = convert(*subpattern)

    def nwaify(self, cont):
        proxy = NWAProxy()
        ret = self.subpattern.nwaify((proxy,) + cont)
        proxy.actual = ret
        return ret


class Alt(Pattern):
    def __init__(self, *options):
        super().__init__()
        self.options = [convert(x) for x in options]

    def nwaify(self, cont):
        ret = []
        for x in self.options:
            ret += list(x.nwaify(cont))
        return tuple(ret)


class Maybe(Alt):
    def __init__(self, *subpattern):
        super().__init__(convert(*subpattern), Empty())


class Star(Maybe):
    def __init__(self, *subpattern):
        super().__init__(Plus(*subpattern))


class Seq(Pattern):
    def __init__(self, *patterns):
        super().__init__()
        self.patterns = _desugar(list(patterns))

    def nwaify(self, cont):
        for pattern in reversed(self.patterns):
            cont = pattern.nwaify(cont)
        return cont


def _desugar(pattern):
    if not isinstance(pattern, list):
        return pattern

    ret = []
    for x in pattern:
        if isinstance(x, Pattern):
            ret.append(x)
        elif isinstance(x, list):
            ret.append(Seq(*x))
        elif isinstance(x, str):
            ret.append(Regex(x))
        elif callable(x):
            ret.append(Function(x))
        else:
            ret.append(Literal(x))
    return ret


class Matcher(object):
    def __init__(self, nwa):
        self.nwa = nwa

    def match(self, values, **kwargs):
        return self.nwa.match(values, **kwargs)


def convert(*patterns):
    if len(patterns) == 1 and isinstance(patterns[0], Pattern):
        return patterns[0]
    return Seq(*patterns)


def compile(*patterns):
    return Matcher(convert(*patterns).build())


def match(pattern, values, **kwargs):
    return pattern.match(values, **kwargs)
