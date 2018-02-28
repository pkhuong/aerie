# Paired lexer.  A lexer that only looks for pairs of delimiters.
# Input is a string and optionally a lexer and an initial state for the lexer.


import itertools
import re


class View(object):
    def __init__(self, string):
        self.string = string
        self.index = 0
        self.length = len(string)

    def has_data(self):
        return self.index < self.length


def _build_re(mappings):
    entries = []
    for i, (regex, handler) in zip(itertools.count(), mappings.items()):
        if handler:
            entries.append(("aeriePlexerDispatchHandler%i" % i, regex, handler))
    regex = re.compile("|".join([ "(?P<%s>%s)" % (name, regex) for name, regex, _ in entries]))
    handlers = [ None ] * (regex.groups + 1)
    for name, _, handler in entries:
        handlers[regex.groupindex[name]] = handler

    return re.compile(regex), tuple(handlers)

        
class Dispatch(object):
    def __init__(self, name, mappings):
        self.name = name
        self.re, self.handlers = _build_re(mappings)
        self.mappings = mappings

    def __repr__(self):
        return "plexer.Dispatch(%s, %s)" % (self.name, self.mappings)

    def extend(self, name, mappings):
        copy = self.mappings.copy()
        copy.update(mappings)
        return Dispatch(name, copy)

    def dispatch(self, view):
        match = self.re.search(view.string, view.index)
        if match is None:
            prefix = view.string[view.index:]
            view.index = len(view.string)
            return (prefix, None, None)

        prefix_end = match.start() # view.string[view.index:prefix_end] has normal characters
        surrounding_group_id = match.lastindex
        handler = self.handlers[surrounding_group_id]
        assert handler
        insert, action = handler(match)

        prefix = None
        if prefix_end != view.index:
            prefix = view.string[view.index : prefix_end]
        view.index = match.end()
        return (prefix, insert, action)


# Take an array of strings/characters and other values.  Smoosh consecutive strings.
def _flatten(values):
    ret = []
    string_acc = []

    def flush():
        if string_acc:
            if len(string_acc) > 1:
                ret.append("".join(string_acc))
            else:
                ret.append(string_acc[0])
            string_acc.clear()

    for x in values:
        if isinstance(x, str):
            string_acc.append(x)
        else:
            flush()
            if isinstance(x, list):
                ret.extend(x)
            else:
                ret.append(x)
    flush()
    return ret


default_dispatch = Dispatch("default, no string",
                             { r'[(]' : lambda _: ('(', paren_dispatch),
                               r'["]' : lambda _: ('"', double_quote_dispatch),
                               r"[']" : lambda _: ("'", single_quote_dispatch),
                               r'\s+' : lambda _: ([], None) })

paren_dispatch = Dispatch("default, in parenthesis",
                             { r'[)]' : lambda _: (')', -1),
                               r'[(]' : lambda _: ('(', paren_dispatch),
                               r'["]' : lambda _: ('"', double_quote_dispatch),
                               r"[']" : lambda _: ("'", single_quote_dispatch),
                               r'\s+' : lambda _: ([], None) })

double_quote_dispatch = Dispatch("default, double_quote",
                                  { r'\\(?P<escaped>.)' : lambda m: (m.groupdict()['escaped'], None),
                                    r'"' : lambda _: ('"', -1) })

single_quote_dispatch = Dispatch("default, single_quote", { r"'" : lambda _: ("'", -1) })


def plex(string, state = default_dispatch, robust = False):
    view = View(string)
    states = [ state ]
    accumulators = [[]]

    while view.has_data():
        prefix, value, delta = states[-1].dispatch(view)
        def push(x = value):
            if x is not None:
                accumulators[-1].append(x)

        push(prefix)
        if isinstance(delta, int) and delta < 0:
            push()
            for i in range(-delta):
                states.pop()
                tos = _flatten(accumulators.pop())
                accumulators[-1].append([tos])
            continue

        if isinstance(delta, list) or isinstance(delta, tuple):
            states.extend(delta)
            accumulators.append([[]] * len(delta))
        elif delta:
            states.append(delta)
            accumulators.append([])
        push()

    assert len(states) == len(accumulators)
    while robust and len(states) > 1:
        states.pop()
        tos = _flatten(accumulators.pop())
        accumulators[-1].append([tos])

    if len(states) != 1:
        print('states: %i for %s' % (len(states), string))
        assert len(states) == 1
    return _flatten(accumulators.pop())
