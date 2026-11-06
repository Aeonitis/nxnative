"""Nested early exits flattened within Metal's bracket depth (dmsh_depth.py bounded): which chains become a region, which are left alone, the compile, and that
the Metal front end makes the same program of both."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from dmsh_depth import LIMIT, bounded, deeper, depth   # noqa: E402

HEAD = '''#include <metal_stdlib>
#include <simd/simd.h>

using namespace metal;

struct _29
{
    uint _m0[1];
};

struct spvDescriptorSetBuffer0
{
    device _29* cp_s0 [[id(0)]];
};

kernel void main0(constant spvDescriptorSetBuffer0& spvDescriptorSet0 [[buffer(0)]], uint3 gl_LocalInvocationID [[thread_position_in_threadgroup]])
{
    uint _31[300];
    int _c = int((*spvDescriptorSet0.cp_s0)._m0[0]);
'''


def allocator(steps, extra=''):
    """agl's particle allocator (agl_technique_pfx.sharcb, Ocarina of Time's 1f78730053feb036) as SPIRV-Cross writes it, cut down: each step takes from its
    bin and leaves when the count reaches zero, one if inside the next. `extra` goes into the middle step"""
    out = [HEAD]
    for k in range(steps):
        ind = '    ' * (k + 1)
        out.append(f'{ind}bool _s{k} = _c == 0;\n{ind}if (!_s{k})\n{ind}{{\n')
        ind += '    '
        out.append(f'{ind}uint _t{k} = min(uint(_c), _31[{k}]);\n{ind}_31[{k}] -= _t{k};\n{ind}_c -= int(_t{k});\n')
        if k == steps // 2 and extra: out.append(''.join(ind + ln + '\n' for ln in extra.split('\n')))
    for k in range(steps, 0, -1): out.append('    ' * k + '}\n')
    out.append('    (*spvDescriptorSet0.cp_s0)._m0[1] = uint(_c);\n}\n\n')
    return ''.join(out)


DEEP = allocator(LIMIT + 4)


class Depth(unittest.TestCase):
    def test_depth_counts_every_bracket_outside_comments_and_literals(self):
        for src, want in (('a(b[c{d}])', 3), ('x("((((") // (((', 1), ('/* {{{{ */ {', 1), ("c = '(';", 0), ('', 0)):
            with self.subTest(src):
                self.assertEqual(depth(src), want)
                self.assertFalse(deeper(src, want))
                if want: self.assertTrue(deeper(src, want - 1))

    def test_deep_allocator(self):
        self.assertTrue(deeper(DEEP))
        self.assertGreater(depth(DEEP), LIMIT)


class Bounded(unittest.TestCase):
    def test_chain_becomes_one_region(self):
        out = bounded(DEEP)
        self.assertLessEqual(depth(out), 4)
        self.assertEqual(out.count('do\n'), 1)
        self.assertEqual(out.count('} while (false);'), 1)
        self.assertEqual(len(re.findall(r'if \(!\(!_s\d+\)\) break;', out)), LIMIT + 4)
        statements = lambda s: [ln.strip() for ln in s.split('\n') if ln.strip().startswith(('uint _t', '_31[', '_c -=', 'bool _s'))]   # noqa: E731
        self.assertEqual(statements(out), statements(DEEP))   # every step's code, in the same order

    def test_shallow_source_unchanged(self):
        shallow = allocator(40)
        self.assertEqual(bounded(shallow), shallow)

    def test_jump_to_an_outer_loop_keeps_the_chain(self):
        # a continue (or break) that binds outside the steps would bind to the new region instead: the steps down to it stay nested, the chain that starts
        # below it (which holds no jump) is flattened
        for jump in ('continue;', 'break;'):
            with self.subTest(jump):
                src = allocator(LIMIT + 4, 'if (_c < 0)\n{\n    ' + jump + '\n}')
                out = bounded(src)
                cut = src.index(jump)
                self.assertEqual(out[:cut], src[:cut])
                self.assertNotIn('do\n', out[:out.index(jump)])
                self.assertEqual(out.count('} while (false);'), 1)
                self.assertFalse(deeper(out))

    def test_jump_inside_a_nested_loop_or_switch_is_kept(self):
        src = allocator(LIMIT + 4, 'for (int _i = 0; _i < 4; _i++)\n{\n    if (_i == _c)\n    {\n        break;\n    }\n}\nswitch (_c)\n{\n    case 1:\n    {\n        _c = 2;\n        break;\n    }\n}')
        out = bounded(src)
        self.assertLessEqual(depth(out), 8)

    def test_if_with_else_is_not_a_step(self):
        src = DEEP.replace('    (*spvDescriptorSet0.cp_s0)._m0[1] = uint(_c);', '    else\n    {\n        _c = 1;\n    }\n    (*spvDescriptorSet0.cp_s0)._m0[1] = uint(_c);')
        out = bounded(src)
        self.assertEqual(out.count('} while (false);'), 1)
        self.assertIn('if (!_s0)', out)   # the head keeps its else, and the chain starts below it
        self.assertLessEqual(depth(out), 6)


METAL = ['xcrun', '-sdk', 'macosx', 'metal', '-O1', '-fpreserve-invariance']


def canonical_ir(path):   # the optimized IR without metadata, a block's predecessors and a phi's incoming values as sets: their order carries no meaning
    out = []
    for line in Path(path).read_text().split('\n'):
        if not line.strip() or line.startswith((';', '!', 'source_filename')): continue
        line = re.sub(r', !\w+ !\d+| #\d+', '', line)
        if m := re.match(r'^(\d+:)\s+; preds = (.*)$', line): line = m.group(1) + ' ' + ','.join(sorted(x.strip() for x in m.group(2).split(',')))
        elif m := re.match(r'^(\s*%\d+ = phi \S+ )(.*)$', line): line = m.group(1) + ','.join(sorted(re.findall(r'\[[^\]]*\]', m.group(2))))
        out.append(line)
    return out


@unittest.skipUnless(shutil.which('xcrun') and sys.platform == 'darwin', 'Metal compiler')
class Compile(unittest.TestCase):
    def test_flattened_compiles_where_the_nested_does_not(self):
        with tempfile.TemporaryDirectory() as d:
            for name, src, ok in (('nested', DEEP, False), ('flat', bounded(DEEP), True)):
                m = os.path.join(d, name + '.metal'); Path(m).write_text(src)
                r = subprocess.run([*METAL, '-c', m, '-o', os.path.join(d, name + '.air')], capture_output=True, text=True)
                self.assertEqual(r.returncode == 0, ok, r.stderr[-400:])
                if not ok: self.assertIn('bracket nesting level exceeded', r.stderr)

    def test_same_program(self):
        # with the limit raised for the nested source, the front end's optimized IR of both is the same
        with tempfile.TemporaryDirectory() as d:
            irs = []
            for name, src, extra in (('nested', DEEP, ['-fbracket-depth=1024']), ('flat', bounded(DEEP), [])):
                m, ll = os.path.join(d, name + '.metal'), os.path.join(d, name + '.ll'); Path(m).write_text(src)
                subprocess.run([*METAL, *extra, '-S', '-emit-llvm', m, '-o', ll], capture_output=True, text=True, check=True)
                irs.append(canonical_ir(ll))
            self.assertEqual(irs[0], irs[1])


if __name__ == '__main__':
    unittest.main()
