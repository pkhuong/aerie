#!/usr/bin/env python3


import aerie
from aerie.sregex import *


black = (0, 30)
red = (0, 31)
green = (0, 32)
yellow = (0, 33)
blue = (0, 34)
magenta = (0, 35)
cyan = (0, 36)
white = (0, 37)

bright_black = (0, 1, 30)
bright_red = (0, 1, 31)
bright_green = (0, 1, 32)
bright_yellow = (0, 1, 33)
bright_blue = (0, 1, 34)
bright_magenta = (0, 1, 35)
bright_cyan = (0, 1, 36)
bright_white = (0, 1, 37)


def colorized(state, view):
    if state == 'esc':
        if view.match(br'\x1b\[0m'):
            return None, -1
    if state == "'":
        if view.match(b"'"):
            return "'", -1
    elif state == '"':
        r = view.match(br'\\.')
        if r:
            return r[1], None
        if view.match(br'"'):
            return '"', -1
    else:
        if view.match(b"'"):
            return "'", "'"
        if view.match(br'"'):
            return '"', '"'

    # Always be on the lookout for ANSI escape codes.
    r, matches = view.match_groups(br'\x1b\[(?P<A>\d+)?(;(?P<B>\d+))?(;(?P<C>\d+))?(;\d+)*m')
    if r:
        ret = tuple()
        for k in ['A', 'B', 'C']:
            if matches.get(k):
                ret += (int(matches.get(k)),)
        return ret, 'esc'
    return view.advance(1)[0], None


def plex_clang(string):
    return aerie.plex(string, colorized)


def parse_attributes(string):
    if not isinstance(string, str):
        return None
    if not re.match(r'(?P<Attributes>( [A-Za-z0-9]+)*)', string):
        return None
    return {'attributes' : string.split()}



def address(name):
    return Nest(yellow, r'^ 0x(?P<%s>[0-9a-fA-F]+)$' % name)


def sloc(name):
    string = r'^(?P<%s>.*)$' % name
    # todo: split the fields up
    return Nest(yellow, string)


def _type(name):
    return Nest(green, Nest(r"^'(?P<%s>.*)'$" % name))


def identifier(name):
    return Nest(bright_cyan, ' ', Nest(r"'(?P<%s>(\w|\s)+)'" % name))

source_range = Seq('^ <$', sloc('RangeBegin'), Maybe(', ', sloc('RangeEnd')), '^> $')
source_loc = sloc('SourceLoc')
node_type = Nest(bright_magenta, r'^(?P<NodeType>[A-Za-z_0-9]+)$')
attributes = Nest(cyan, parse_attributes)
kind = Nest(bright_green, r'^(?P<Kind>(\w|\d)*)')


pattern = aerie.compile(node_type, address("Address"), source_range, _type("Type"), attributes, Nest(cyan), ' ',
                    kind, address("TargetAddress"), identifier('Name'), ' ', _type('TargetType'),
                    Maybe('\n'))
