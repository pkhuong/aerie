# Nested work automaton matcher based on the set of state trick for NFA.


import itertools
import re


_states = None


def _flat_tuples(values):
    flat = []
    seen = set()

    def push(x):
        if id(x) in seen:
            return
        seen.add(id(x))
        flat.append(x)

    for k in values:
        assert not isinstance(k, tuple)
        if isinstance(k, NWAProxy):
            for x in k.flatten():
                push(x)
        else:
            push(k)
    return tuple(flat)


class NWAProxy(object):
    def __init__(self):
        self.actual = ()
        self.flat = None

    def flatten(self):
        if self.flat is not None:
            return self.flat

        self.flat = _flat_tuples(self.actual)
        return self.flat


class NWAState(object):
    def __init__(self, cont):
        assert isinstance(cont, tuple)
        self.index = len(_states)
        self.cont = cont
        _states.append(self)

    def __repr__(self):
        return "NWAState{%s %d -> %s}" % (type(self), self.index, self.flat_cont)

    def flatten(self):
        self.flat_cont = [x.index for x in _flat_tuples(self.cont)]
        self.cont = None


class NWAStart(NWAState):
    def __init__(self, cont):
        super().__init__(cont)


class NWAAccept(NWAState):
    def __init__(self):
        super().__init__(())

    def match(self, item):
        return None


class NWAFunction(NWAState):
    def __init__(self, function, cont):
        super().__init__(cont)
        self.function = function

    def match(self, item):
        return self.function(item)


def _nwaify(pattern):
    global _states

    old_states = _states
    _states = []

    accept = (NWAAccept(),)
    start = NWAStart(pattern.nwaify(accept))
    for x in _states:
        x.flatten()
    ret = _states

    _states = old_states
    return ret


def _reverse_pairs_to_list(pair):
    stack = []
    while pair != ():
        assert len(pair) == 2
        stack.append(pair[0])
        pair = pair[1]
    return stack


def _flatten(pair):
    if pair is None:
        return None

    stack = _reverse_pairs_to_list(pair)
    ret = dict()

    def force(v):
        if isinstance(v, Result):
            return v.force()
        return v

    def push(k, v):
        if isinstance(v, list):
            v = [ force(x) for x in v ]
            if ret.get(k) is None:
                ret[k] = v
            else:
                ret[k].extend(v)
            return

        v = force(v)
        if isinstance(k, str) and k.endswith('List'):
            if ret.get(k) is None:
                ret[k] = [v]
            else:
                ret[k].append(v)
        elif v is not None:
            ret[k] = v

    for tos in reversed(stack):
        tos = force(tos)
        if hasattr(tos, 'groupdict'):
            for k, v in tos.groupdict().items():
                push(k, v)
        elif isinstance(tos, dict):
            for k, v in tos.items():
                push(k, v)
        elif isinstance(tos, tuple):
            assert len(tos) in (0, 2)
            if tos:
                push(tos[0], tos[1])
        else:
            for k, v in tos:
                push(k, v)
    return ret


def _splat(dst, indices, dict, active):
    for index in indices:
        if dst[index] is None:
            dst[index] = dict
            active.append(index)


class Result(object):
    def __init__(self, values):
        assert values is not None
        self.values = values
        self.evaluated = None

    def force(self):
        if self.evaluated is not None:
            return self.evaluated
        self.evaluated = _flatten(self.values)
        return self.evaluated

    def __getitem__(self, key):
        return self.force()[key]

def _wrap(x):
    return None if x is None else Result(x)


class NWA(object):
    def __init__(self, sregex):
        self.states = _nwaify(sregex)

    def __repr__(self):
        return "NWA(%s)" % self.states

    def match(self, values, anchored = True):
        if not hasattr(values, '__iter__'):
            return None

        last_accept = None
        # active is the list of non-None slots in groups.
        old_groups = [None] * len(self.states)
        old_active = []
        groups = [None] * len(self.states)
        active = []
        _splat(groups, self.states[-1].flat_cont, (), active)

        for value in values:
            if groups[0] is not None:
                last_accept = groups[0]

            if len(active) == 0:
                return _wrap(last_accept)

            new_groups = old_groups
            new_active = old_active

            new_active.clear()
            for index in active:
                state = self.states[index]
                group = groups[index]
                groups[index] = None

                assert group is not None
                ret = state.match(value)
                if ret is None:
                    continue
                _splat(new_groups, state.flat_cont, (ret, group), new_active)

            old_groups = groups
            old_active = active
            groups = new_groups
            active = new_active

        if groups[0] is None:
            return _wrap(last_accept)
        return _wrap(groups[0])
