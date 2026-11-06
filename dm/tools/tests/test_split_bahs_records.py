"""BAHS shader discovery must distinguish binary records from matching metadata words."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'fuzz'))
import fuzzlib

split = fuzzlib.import_shader_split()


def archive():
    region = 0x3000
    d = bytearray(region + 0x300)
    d[:4] = b'BAHS'
    struct.pack_into('<II', d, 0x18, 0x300, region)
    struct.pack_into('<II', d, 0x40, 0x48, 2)
    for i, c in enumerate((0x500, 0x700)):
        r = 0x48 + i * 0x20
        a = r + 0x10
        struct.pack_into('<4I', d, r, 0x20, 3, 0, 0)
        struct.pack_into('<IIIi', d, a, i * 0x100, 0, 0xe0, c - a)
        struct.pack_into('<II', d, c, 0x98761234, 0xc9)
        struct.pack_into('<I', d, c + 0x44, 0x100)
        d[c + 0x56] = 5
        struct.pack_into('<3I', d, c + 0x58, 1, 1, 1)
        d[region + i * 0x100:region + (i + 1) * 0x100] = bytes([i + 1]) * 0x100
    struct.pack_into('<6I', d, 0x88, 24, 1, 16, 0, 0x20, 0)
    # These words look like a shader entry and reference a real control section,
    # but are not a member of the binary array. They point at data, not code.
    struct.pack_into('<IIIi', d, 0x180, 0x200, 0, 0x1100, 0x500 - 0x180)
    return d


class BahsRecords(unittest.TestCase):
    def test_only_declared_binary_records_are_shaders(self):
        found = split.bahs_shaders(archive(), '/synthetic')
        self.assertEqual([x[0] for x in found], ['/synthetic#BAHS@0x58', '/synthetic#BAHS@0x78'])
        self.assertEqual([x[3] for x in found], [bytes([1]) * 0x100, bytes([2]) * 0x100])

    def test_unrecognized_array_layout_keeps_discovery(self):
        d = archive()
        struct.pack_into('<I', d, 0x40, 0)
        self.assertEqual(len(split.bahs_shaders(d, '/synthetic')), 3)

    def test_large_control_sections_are_not_excluded_by_size(self):
        d = archive()
        struct.pack_into('<I', d, 0x58 + 8, 0x1100)
        self.assertEqual(len(split.bahs_shaders(d, '/synthetic')), 2)

    def test_metadata_inside_a_binary_record_is_not_an_entry(self):
        d = archive()
        second, program = bytes(d[0x68:0x88]), bytes(d[0x88:0xa0])
        d[0x180:0x190] = bytes(0x10)
        d[0x68:0xa0] = bytes(0x38)
        struct.pack_into('<I', d, 0x40, 0xa8)
        struct.pack_into('<I', d, 0x48, 0x80)
        d[0xc8:0xe8], d[0xe8:0x100] = second, program
        struct.pack_into('<i', d, 0xd8 + 12, 0x700 - 0xd8)
        struct.pack_into('<IIIi', d, 0x80, 0x200, 0, 0x1100, 0x500 - 0x80)
        found = split.bahs_shaders(d, '/synthetic')
        self.assertEqual([x[0] for x in found], ['/synthetic#BAHS@0x58', '/synthetic#BAHS@0xd8'])


if __name__ == '__main__':
    unittest.main()
