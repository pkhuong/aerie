Aerie: a regex-like engine nested word grammars
===============================================

Aerie is a library to match against semi-structured input with nested
word automata.  NWAs are a generalisation of finite state automata
that operate on streams of values *and* nested streams.  Unlike full
context-free languages, NWAs assume that the input is pre-tokenised as
values and open/close brackets (nested stream markers).  In return for
this (often irrelevant) restriction, we get simple operations that are
comparable to regular languages.  In particular, we can match a given
NWA against a stream *without* backtracking and time linear with
respect to the size of the stream.

Logically, Aerie is composed of two independent components: the paired
lexer, aerie.plexer, and the structured streaming regex matcher,
aerie.sregex.

The plexer takes an input string and returns a nest: an array of
(non-array) values and child nest arrays.  In theory, we could do this
with any iteratable, but repeated matches against a stream are
annoying.  The default dispatch table for aerie.plex matches
parentheses, single and double quoted strings.  More on that later.

The structured regex (sregex) matcher works by taking structured
regular expressions, converting them to (nested) NFAs, and executing
NFAs without backtracking, in a set of state representation.  Sregexen
are structured because they are first-class Python objects, and not
just line noise in a string, and because they match structured
(nested) streams of values.  Any sregex Pattern object can be directly
matched against an iteratable.

How to write a plexer
---------------------

Custom plexers are defined by the dispatch function.  Dispatch
functions accept the current state and a ViewString (copy-free string
slice), and return an action.

An action is a pair of:
- value
- stack action.

The value is appended to the topmost stream of items.  A value of
`None` is not added, and a list represents a sequence of values to
adjoin to the end of the topmost stream.  As a special case for
incremental lexing of strings, consecutive strings are smooshed before
entering the stream of items.

The stack action describes what should happen to the *stack* of plexer
states.  We need to capture nesting, paired delimited, but wish to
restrict complexity, so plexers are simple deterministic pushdown
automata.  Typically, each state in the stack describes the closing
delimiter we're expecting.  A falsish action leaves the state stack
alone.  A negative integer action pops off the corresponding number of
states from the stack (e.g., `-2` means "pop off the two topmost
states").  Any other action is pushed to the stack of state.

When both a value and a stack action are returned, the value is
applied before popping and after pushing.

The hardest part about writing a lexer in Python is probably the
immutable strings.  Aerie avoids quadratic runtime with the ViewString
class: ViewStrings convert strings to byte buffers and traverse the
buffers with memoryview wrappers.  Plexers will mostly interact with
ViewStrings via the `match` and `match_groups` methods.
`ViewString.match` accepts a regex and checks if the regex matches a
prefix of the ViewString's position.  If it does, the method consumes
that prefix and returns it; otherwise, the method returns `None`.  The
`match_group` method is the same, except that is also returns the
dictionary of captures as a second value (or `None` on match failure).

There's a lot of redundancy in plexer dispatch functions.  We'll
probably add more support tools once we have a better grasp of common
patterns.

Also, there's no reason we can't plex arbitrary iteratable
streams...  I've just been too lazy to write a buffering iterator
wrapper and port matchers to use sregex instead of re.

Building sregex
---------------

Aerie.sregex describe patterns with actual Python object trees.  `Seq`
objects represent a sequence of patterns.  `Seq(p1, p2)` builds an
sregex pattern that must first match `p1` and then `p2`.  `Alt` is for
alternation: `Alt(p1, p2, ...)` must match either `p1` or `p2` (or
`p3`, ...).  `Plus(p)` matches `p` at least once.  `Star(p)` matches
`p` any number of times (including none).  `Maybe(p)` maybes `p` 0 or
1 time.

Everything else matches individual items in the input (nested) stream
and builds on top of `Function`: `Function(fun)` accepts an item `x`
if `fun(x)` returns a dictionary of groups (otherwise, we expect
`None` to denote mismatches).  For example, `Any` patterns simply
match any single item and are built as

    class Any(Function):
        def __init__(self):
            super().__init__(lambda item: _empty_dict)

The `Literal` class, which tests items for equality, is equally
simple:

    class Literal(Function):
        def __init__(self, literal):
            super().__init__(lambda item: _empty_dict if item == literal else None)

The `Nest` class is the one thing that separates sregexen from normal
regular expressions.  `Nest(p1, p2, ...)` matches an item if that item
is an iteratable that matches `Seq(p1, p2, ...)`.

The last built-in atomic matcher is `Regex`.  `Regex(re)` accepts an
item `x` if it is a string that matches `re`.  If so, it returns the
regular expression matcher's `groupdict()`.

The object structure is nice at scale, but annoying for small
matchers.  Classes that accept patterns (`Seq`, `Alt`, `Plus`, `Star`,
`Maybe`, and `Nest`) also accept a shorthand based describing
sequences as lists.  Each element in such a list describes a pattern
in a `Seq` object:
- Patterns describe pattern;
- lists are themselves `Seq` object (not nested, i.e., `[a, [b, c],
d]` is equivalent to `[a, b, c, d]`;
- strings are `Regex` patterns;
- callables are `Function` patterns
- anything else is a `Literal` pattern.

For `Alt`, each argument can itself be desugared.

At any moment, a `Pattern` object can be
`pattern.matched(iteratable)`.  The pattern will be converted to a
(nondeterministic) nested word automaton on demand, and automatically
execute the NWA.  `aerie.sregex.build(sweet, patterns)` will build a
pattern from the shorthand (the argument tuple is converted to a
list), and that pattern can then be `match`ed.  `aerie.sregex.compile`
will `build` an sregex, convert it to an NWA, and wrap the NWA in an
`sregex.Matcher` object.  The only method on that object is
`Matcher.match(iteratable)`.  Finally, for convenience,
`aerie.sregex.match(pattern, values)` simply calls
`pattern.match(value)`.

But I thought CFLs were hard!
-----------------------------

In the general case, context-free languages are hard (as hard as
matrix multiplication).  However, not all context-free languages are
hard; as a trivial example, regular languages are also context-free.
Classical parser theory explored restrictions like `LL`, `LR` or
`LALR`; such parsers are honestly not that great to work with,
especially when the generator throws a dreaded shift/reduce conflict
error.

Nested words seem like a much better fit for the kind of
(semi-)structured languages that programmers often encounter, and
certainly jibes better with my intuition of what should be hard.  I
don't have trouble matching parentheses in linear time (and worst case
linear space, granted).

The difference between nested word automata and finite state automata
is that certain input symbols are marked as (mandatory) push stack
/ pop stack points.  This gives us a form of recursion that we need
for a lot of formal languages.  However, since the recursion structure
is fixed ahead of time, we don't hit the same problem as full-blown
context-free parsing.

This marking of push / pop points seems like a cop-out at first: we're
just pushing the non-regularity somewhere else.  The trick is to
notice that, if we *only* want to lex these special symbols, we should
be ok with a deterministic pushdown automaton (equivalently, an
`LL(1)` parser).  That's certainly true for common use cases like
quotes, brackets, or XML tags.

Now that we have these points, we can treat the input stream as a
stream of values that are either symbols or nested streams.  The
nesting is guaranteed to be well behaved and never spill out of its
one slot in the stream.  In other words, the way we accept a nested
stream can never affect the rest of the match because we can only
accept exactly one nested value at a time.  This simplification lets
us apply the classic set of state approach for executing NFAs (it also
means we can compare NWAs for equality, etc., with Brozowski
derivatives without too much memoisation cleverness).

The first step is to convert sregex Patterns to NFAs where some of the
states have arbitrary logic *that only looks at the current input
value*; that logic may include recursively matching that value as a
nested stream of values.  The nice part is that what a state does to
determine whether it accepts or rejects the current value is
irrelevant to the NFA machinery itself.  We can reuse textbook
conversion algorithms.

The conversion from structured regex to NFA is only slightly
complicated by the fact that we don't want epsilon transitions;
Epsilon transitions must be propagated to the predecessor state(s).
The result of converting an sregex pattern to NFA is thus a set of
successor states, not just one state with potential epsilon
transitions.  The reason will become clear when we get to executing
nondeterministic nested word automata (NWAs).

The only non-obvious trick is that we must close a loop for `Plus`
patterns: the continuation for the repeated pattern is the union of
the `Plus` pattern and the `Plus`'s patterns continuation.  We achieve
that by adding a proxy object to the continuation and backpatching in
a later pass.

Finally, when it comes to execution, we avoid backtracking and
memoisation in favor of simply keeping track of all active states at
once and advancing them in lockstep.  An NWA has all the states
numbered in an array, and each state lists its successors (on success)
by their index.  We can associate a dict of match groups with each
active state, and execute active states one after the other.  If a
state fails, we have nothing to do.  If it succeeds, we will mark its
successors as active in the *next* iteration (and bring along an
updated dict of match groups); we know that our NFAs don't contain
epsilon transitions, so we always want to execute successors in the
next iteration.

Matching is now trivially linear-time, without any backtracking,
memoisation or memory allocation (past the match group
dictionaries)...  and it can even work on arbitrary iteratable
objects exactly as well as on lists and strings.
