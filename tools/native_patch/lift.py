"""Lifts the EBOOT with our patch in it, the port's lifter unchanged: plain words go into a copy of the ELF, each calloc block is
emitted inline at its hook. build.py runs it: py -3.13 -I -B lift.py <patch.json> <port clone> <out dir> <code end>"""
import json
import os
import struct
import sys

ARGS = 'NHL_PUCKPEAK_LIFT'           # the lifter's workers import this file again with the lifter's own argv
PATCH, PORT, OUT, CODE_END = json.loads(os.environ[ARGS]) if ARGS in os.environ else sys.argv[1:5]
os.environ[ARGS] = json.dumps([PATCH, PORT, OUT, CODE_END])
CODE_END = int(CODE_END, 16)
sys.path.insert(0, os.path.join(PORT, 'ps3recomp', 'ps3recomp-master', 'tools'))
import ppu_lifter as L
from ppu_disasm import disassemble_bytes

CAVE_BASE = 0x0F000000
_p = json.load(open(PATCH))
CAVES = {h: (CAVE_BASE + i * 0x1000, ws) for i, (h, ws) in enumerate(_p['caves'])}
_orig = L.PPULifter._translate


def constant_target(ins, k):
    """The address a `lis rN / ori rN / mtctr rN / bctr` builds, for the instruction index k of the bctr."""
    hi = lo = None
    for w in [i.raw for i in ins[max(0, k - 3):k]]:
        if w >> 26 == 15 and not (w >> 16 & 31):
            hi = (w & 0xffff) << 16
        elif w >> 26 == 24:
            lo = w & 0xffff
    return None if hi is None or lo is None else hi | lo


def _translate(self, insn, func):
    cave = CAVES.get(insn.addr)
    if cave is None or getattr(self, '_in_cave', False):
        return _orig(self, insn, func)
    base, ws = cave
    ins = disassemble_bytes(struct.pack('>%dI' % len(ws), *ws), base, True)
    end = base + len(ws) * 4
    fake = L.LiftedFunction(name=func.name, start_addr=base, end_addr=end + 4)
    targets = set()
    for i in ins:
        if i.mnemonic.startswith('b') and i.mnemonic not in ('blr', 'bctr', 'bctrl', 'bl', 'blrl'):
            for op in L._parse_operands(i.operands):
                if op.startswith('0x'):
                    targets.add(int(op, 16))
    keep, self.code_hi, self._in_cave = self.code_hi, None, True
    try:
        for k, i in enumerate(ins):
            if i.addr in targets:
                func.body_lines.append(f'loc_{i.addr:08X}:')
            if i.mnemonic == 'bctr':
                tgt = constant_target(ins, k)
                assert tgt, hex(i.addr)
                self.branch_targets.add(tgt)
                func.body_lines.append(f'    {{ g_trampoline_fn = (void(*)(void*)){self.prefix}func_{tgt:08X}; return; }}')
                continue
            line = _orig(self, i, fake)
            if line:
                func.body_lines.append(f'    {line}')
    finally:
        self.code_hi, self._in_cave = keep, False
    assert all(base <= t <= end for t in targets), hex(insn.addr)
    return f'loc_{end:08X}: ;' if end in targets else ';'


L.PPULifter._translate = _translate


def patched_elf(src, dst, words):
    d = bytearray(open(src, 'rb').read())
    phoff = struct.unpack_from('>Q', d, 0x20)[0]
    phent, phnum = struct.unpack_from('>HH', d, 0x36)
    segs = []
    for k in range(phnum):
        t, _flags, off, va, _pa, fsz, _msz, _al = struct.unpack_from('>IIQQQQQQ', d, phoff + k * phent)
        if t == 1:
            segs.append((va, va + fsz, off))
    n = 0
    for a, w in words.items():
        a = int(a, 16)
        if a >= CODE_END:
            continue
        s = next(s for s in segs if s[0] <= a < s[1])
        struct.pack_into('>I', d, a - s[0] + s[2], w)
        n += 1
    open(dst, 'wb').write(d)
    return n


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    elf = os.path.join(OUT, 'patched.elf')
    print('code words', patched_elf(os.path.join(PORT, 'bin', 'EBOOT_v101.elf'), elf, _p['words']), 'caves', len(CAVES), flush=True)
    n = os.path.join(PORT, 'nhl', 'out', 'EBOOT_v101')
    sys.argv = ['ppu_lifter.py', elf, '--functions', n + '.functions.json', '--hle-stubs', n + '.imports.json',
                '--code-end', hex(CODE_END), '--chunks', '256', '--output', os.path.join(OUT, 'recompiled')]
    L.main()
