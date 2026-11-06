"""Nested early exits flattened, so the MSL stays within the Metal front end's bracket depth (bounded, a step of dmsh_build.py).

Metal's front end (clang) stops at 256 levels of nested brackets, counting ( [ { together: "fatal error: bracket nesting level exceeded maximum of 256".
The translator's structurizer writes each forward branch to a common join as an if around the rest of the code, so a Maxwell / Ampere program that leaves an
unrolled loop early from each of its steps becomes one if inside the next. agl's particle allocator (agl_technique_pfx.sharcb, Ocarina of Time's compute
shaders 1f78730053feb036 and e172bd7ec218ab8e) takes from 256 bins in turn and stops when its count reaches zero:

    if (!_260)
    {
        ... take from bin 34 ...
        if (!_280)
        {
            ... take from bin 35 ...
            if (!_296)
            {
                ... 254 more levels ...

Here such a chain, an if with no else whose body ends with another such if, and so on, becomes one region the steps leave with a break:

    do
    {
        if (!(!_260)) break;
        ... take from bin 34 ...
        if (!(!_280)) break;
        ... take from bin 35 ...
        ...
    } while (false);

This is the same program: each break goes where the false condition went, to the end of the outermost if, as nothing follows an inner if in its block.
A step that holds a break or continue of its own, outside a loop or switch nested in it, would rebind it to the new region, so the steps down to it stay
nested (a chain that starts below it is flattened on its own); a
variable declared in a step moves to the region's scope, which the unique SPIR-V names allow, and a break that leaves a scope past its later declarations is
valid C++. Only a source deeper than the limit is rewritten (every other shader's MSL, and so its cache entries, stays as it was), and a rewrite that does
not bring it under the limit leaves it unchanged, for the compile to report.
"""
import re

LIMIT = 256   # clang's default -fbracket-depth, which the Metal compile convention keeps
_IF = re.compile(r'^if \((.*)\)$')
_LOOP = re.compile(r'^(do|for|while)\b')
_SWITCH = re.compile(r'^switch\b')
_JUMP = re.compile(r'^(break|continue);$')


_SKIP = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'', re.S)   # comments, string and character literals: their brackets do not nest
_OPEN, _CLOSE = '([{', ')]}'


def _lines(src): return (_SKIP.sub(' ', src) if '//' in src or '/*' in src or '"' in src or "'" in src else src).split('\n')


def depth(src):
    """The deepest nesting of ( [ { in src, outside comments and string / character literals, as the front end counts it"""
    d = top = 0
    for ln in _lines(src):
        for c in ln:
            if c in _OPEN:
                d += 1
                if d > top: top = d
            elif c in _CLOSE: d -= 1
    return top


def deeper(src, limit=None):
    """Whether src nests deeper than limit (default LIMIT). Each line's opening brackets added to the depth it starts at bound its deepest point, so only a line
    that could pass the limit is walked: dmsh_build.py asks this of every shader, about a millisecond for a 7,000-line one"""
    limit = LIMIT if limit is None else limit
    if src.count('(') + src.count('[') + src.count('{') <= limit: return False   # not that many brackets in all
    d = 0
    for ln in _lines(src):
        o = ln.count('(') + ln.count('[') + ln.count('{')
        if d + o > limit:
            e = d
            for c in ln:
                if c in _OPEN:
                    e += 1
                    if e > limit: return True
                elif c in _CLOSE: e -= 1
        d += o - ln.count(')') - ln.count(']') - ln.count('}')
    return False


class Block:   # a braced block as SPIRV-Cross writes it: its header line(s), the line with { alone, its items (lines or blocks), the line that starts with }
    __slots__ = ('head', 'open', 'items', 'close')
    def __init__(self, head: list, open_: 'str | None'):
        self.head, self.open = head, open_
        self.items: list = []
        self.close: 'str | None' = None


def _parse(lines):
    """The lines as a tree: a { alone on its line opens a block whose header is the line before it (SPIRV-Cross's layout); None when the braces do not pair"""
    root = Block([], None); stack = [root]
    for ln in lines:
        s = ln.strip()
        if s == '{':
            cur = stack[-1]
            head = [cur.items.pop()] if cur.items and isinstance(cur.items[-1], str) and cur.items[-1].strip() else []
            b = Block(head, ln); cur.items.append(b); stack.append(b)
        elif s.startswith('}') and len(stack) > 1:
            stack.pop().close = ln
        else: stack[-1].items.append(ln)
    return root if len(stack) == 1 else None


def _emit(b, out):
    out.extend(b.head)
    if b.open is not None: out.append(b.open)
    for it in b.items:
        if isinstance(it, Block): _emit(it, out)
        else: out.append(it)
    if b.close is not None: out.append(b.close)


def _kind(b):   # the header's statement: 'if <cond>', 'else ...', 'do', ...
    return b.head[-1].strip() if b.head else ''


def _plain_if(b):   # the condition of a block that is an if with no else of its own; None otherwise
    m = isinstance(b, Block) and b.close is not None and b.close.strip() == '}' and _IF.match(_kind(b))
    return m.group(1) if m else None


def _jumps(items, in_loop=False, in_switch=False):
    """Whether these items hold a break or continue that binds outside them (one in a loop or switch nested in them binds there)"""
    for it in items:
        if isinstance(it, Block):
            k = _kind(it)
            if _jumps(it.items, in_loop or bool(_LOOP.match(k)), in_switch or bool(_SWITCH.match(k))): return True
        else:
            m = _JUMP.match(it.strip())
            if m and not (in_loop or (m.group(1) == 'break' and in_switch)): return True
    return False


def _following_else(items, i):   # whether the block items[i] is followed by an else (the next item that is not a blank line)
    for it in items[i + 1:]:
        if isinstance(it, str) and not it.strip(): continue
        return isinstance(it, Block) and _kind(it).startswith('else')
    return False


def _chain(b):
    """The steps of the chain that starts at block b: [(condition, items before the next if)], the last step with all its items; None when b starts none"""
    steps = []
    while True:
        cond = _plain_if(b)
        if cond is None: return None
        body = b.items
        tail = next((k for k in range(len(body) - 1, -1, -1) if not (isinstance(body[k], str) and not body[k].strip())), None)
        nxt = body[tail] if tail is not None else None
        if isinstance(nxt, Block) and _plain_if(nxt) is not None:
            steps.append((cond, body[:tail])); b = nxt
        else:
            steps.append((cond, body)); break
    return steps if len(steps) > 1 else None


def _flatten(items, made):
    for i, it in enumerate(items):
        if not isinstance(it, Block): continue
        steps = None if _following_else(items, i) else _chain(it)
        if steps and not any(_jumps(s) for _, s in steps):
            h = it.head[-1]; ind = h[:len(h) - len(h.lstrip())]; step_ind = ind + '    '
            region = Block([ind + 'do'], ind + '{'); region.close = ind + '} while (false);'
            for k, (cond, body) in enumerate(steps):
                region.items.append(f'{step_ind}if (!({cond})) break;')
                region.items.extend(_shift(body, 4 * k))
            items[i] = region; made[0] += 1
            it = region
        _flatten(it.items, made)


def _shift(items, n):   # the items with n spaces less indentation (a step moves n spaces left, to its depth in the region; layout only)
    out = []
    for it in items:
        if isinstance(it, Block):
            b = Block([_shift_line(h, n) for h in it.head], _shift_line(it.open, n)); b.close = _shift_line(it.close, n); b.items = _shift(it.items, n); out.append(b)
        else: out.append(_shift_line(it, n))
    return out


def _shift_line(ln, n):
    return ln[n:] if ln is not None and ln[:n].isspace() else ln


def bounded(src, limit=LIMIT):
    """src with its chains of nested early exits flattened when it is deeper than limit; unchanged when it is not, or when the rewrite does not bring it under"""
    if not deeper(src, limit): return src
    root = _parse(src.split('\n'))
    if root is None: return src
    made = [0]; _flatten(root.items, made)
    if not made[0]: return src
    out = []; _emit(root, out)
    new = '\n'.join(out)
    return src if deeper(new, limit) else new
