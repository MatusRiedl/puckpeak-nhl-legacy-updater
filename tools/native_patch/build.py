"""Builds the game patch of NHL Legacy Native, a stand-in XINPUT1_4.dll (README.md here). Nothing it makes goes into git.

    py -3.13 -B tools/native_patch/build.py <port clone> <NHLLegacy.exe> <work folder> [--skip-lift]

<work>/dll/XINPUT1_4.dll and <work>/portpatch.zip come out; the zip goes into private/packs by hand."""
import bisect
import glob
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from legacy_roster import gamepatch as G

TITLE, VERSION = 'BLUS31540', '01.01'
BASE = 0x140000000
FUNC = re.compile(r'(?m)^void (?:__attribute__\(\(weak\)\) )?(func_[0-9A-F]{8})\(ppu_context\* ctx\) \{\n(.*?)^\}\n', re.S)
EARLY = 'func_00010230'             # the game's entry: runs once the ELF is in guest memory, before anything reads it
SKIP = {'func_0022E160'}            # a host shared by 7 rows; our change there is dead text

# What each build of the exe keeps where: none of it is exported. Found with llvm-objdump, docs: README.md "A new build".
BUILDS = {
    (0x6ae7cb75, 0x1a657000): dict(
        table=0x1429f000 + 746080, code_end=0x1a62e4c, tramp_off=0x4170,
        helpers=dict(vm_read8=0x140010c20, vm_read16=0x144f94b90, vm_read32=0x144f559c0, vm_read64=0x144f5a690,
                     vm_write8=0x1443d4cd0, vm_write16=0x144c5bfe0, vm_write32=0x144c55020, vm_write64=0x1443d47d0,
                     ppu_ww_note_st16=0x144f942f0, ps3_indirect_call=0x1443d49f0, ppu_stdcx64=0x1443d4400),
        data=dict(vm_base=0x154d776e0, g_vm_ld_gate=0x154ecca90, g_vm_st_gate=0x1571ef800, g_ww_hi=0x154ecca6c,
                  tls_index=0x1599410f8)),
}


class Exe:
    def __init__(self, path):
        self.bytes = open(path, 'rb').read()
        d = self.bytes
        pe = struct.unpack_from('<I', d, 0x3c)[0]
        self.id = struct.unpack_from('<I', d, pe + 8)[0], struct.unpack_from('<I', d, pe + 24 + 56)[0]
        count, opt = struct.unpack_from('<H', d, pe + 6)[0], struct.unpack_from('<H', d, pe + 20)[0]
        self.sections = [struct.unpack_from('<8sIIII', d, pe + 24 + opt + 40 * i) for i in range(count)]

    def file_at(self, rva):
        for _, _, va, raw, at in self.sections:
            if va <= rva < va + raw:
                return at + rva - va
        raise ValueError(hex(rva))

    def read(self, rva, n):
        at = self.file_at(rva)
        return self.bytes[at:at + n]

    def rows(self, table):
        """The exe's function table: guest address -> host function."""
        at, rows = self.file_at(table), {}
        while True:
            guest, host, name = struct.unpack_from('<QQQ', self.bytes, at)
            if not host and not name:
                return rows
            rows[guest] = host
            at += 24


def parse(lines):
    """A patch entry of RPCS3's text as plain words and calloc blocks."""
    words, caves, cur = {}, [], None
    for line in lines:
        m = re.match(r'\s*- \[ calloc, 0x([0-9a-f]+), (\d+) \]', line)
        if m:
            cur = [int(m[1], 16), int(m[2]), []]
            caves.append(cur)
            continue
        m = re.match(r'\s*- \[ be32, 0x([0-9a-f]+), 0x([0-9a-f]+) \]', line)
        if m:
            a, w = int(m[1], 16), int(m[2], 16)
            if cur and a == cur[0] and len(cur[2]) < cur[1]:
                cur[2].append(w)
            else:
                cur = None
                words[a] = w
    return words, [[c[0], c[2]] for c in caves]


def patch_words():
    """What RPCS3 ticks for this game: the 32-team entry (the year is in it) and the news entry."""
    words, caves = parse(G.player_entry_lines(TITLE, VERSION))
    news = next(e for e in G.INTRO_ENTRIES if e[0] == G.NEWS_ENTRY)
    more, more_caves = parse(G.intro_entry_lines(news, TITLE, VERSION))
    assert not more_caves
    return {'words': {hex(a): w for a, w in {**words, **more}.items()}, 'caves': caves}


def functions(folder):
    out = {}
    for p in glob.glob(os.path.join(folder, 'ppu_recomp_[0-9]*.cpp')):
        for m in FUNC.finditer(open(p, encoding='latin-1').read()):
            out[m[1]] = m[2]
    return out


def changed(port, work):
    a, b = functions(os.path.join(port, 'nhl', 'port', 'recompiled')), functions(os.path.join(work, 'recompiled'))
    swap = dict(changed=sorted(k for k in a if k in b and a[k] != b[k]), new=sorted(k for k in b if k not in a),
                gone=sorted(k for k in a if k not in b))
    assert not swap['gone'], swap['gone'][:9]
    return swap


def uncovered(patch, swap, rows, code_end, elf):
    """Addresses of the patch that change an instruction in no function we swap: each would be a word the port does not get."""
    d = open(elf, 'rb').read()
    phoff, phent, phnum = struct.unpack_from('>Q', d, 0x20)[0], *struct.unpack_from('>HH', d, 0x36)
    segs = []
    for k in range(phnum):
        kind, _, off, va, _, size, _, _ = struct.unpack_from('>IIQQQQQQ', d, phoff + k * phent)
        if kind == 1:
            segs.append((va, va + size, off))

    def word(a):
        s = next(s for s in segs if s[0] <= a < s[1])
        return struct.unpack_from('>I', d, a - s[0] + s[2])[0]

    want = {int(n[5:], 16) for n in set(swap['changed']) | set(swap['new']) | SKIP}
    starts = sorted(set(rows) | want)
    bad = []
    for a, w in [(int(a, 16), w) for a, w in patch['words'].items()] + [(h, None) for h, _ in patch['caves']]:
        if a < code_end and w != word(a) and starts[bisect.bisect_right(starts, a) - 1] not in want:
            bad.append(a)
    return sorted(bad)


def carr(b):
    return '{' + ','.join(str(x) for x in b) + '}'


def make(port, work, exe, build, patch, swap):
    """swap.cpp, ids.h and the compile script in <work>/dll."""
    R, OUT = os.path.join(work, 'recompiled'), os.path.join(work, 'dll')
    os.makedirs(OUT, exist_ok=True)
    data_words = sorted((int(a, 16), v) for a, v in patch['words'].items() if int(a, 16) >= build['code_end'])
    want = set(swap['changed']) | set(swap['new']) | ({EARLY} if data_words else set())
    bodies, preamble = {}, None
    for p in sorted(glob.glob(os.path.join(R, 'ppu_recomp_[0-9]*.cpp'))):
        t = open(p, encoding='latin-1').read()
        if preamble is None:
            preamble = t[:t.index('\nvoid func_') + 1]
        for m in FUNC.finditer(t):
            if m[1] in want:
                bodies[m[1]] = m[0]
    assert set(bodies) == want, want - set(bodies)
    old = 'extern "C" PPU_THREAD_LOCAL void (*g_trampoline_fn)(void*);'
    assert old in preamble
    preamble = preamble.replace(old,
        'extern "C" unsigned long* x_tls_index; extern "C" unsigned long x_tramp_off;\n'
        'static inline __attribute__((always_inline)) void** nhl_tramp(void) { return (void**)(((char**)__readgsqword(0x58))[*x_tls_index] + x_tramp_off); }\n'
        '#define g_trampoline_fn (*(void(**)(void*))nhl_tramp())\n')
    top = '''/* made by build.py: the functions our patch changes, compiled against the exe's own helpers */
#define vm_base (*x_vm_base)
#define g_vm_ld_gate (*x_vm_ld_gate)
#define g_vm_st_gate (*x_vm_st_gate)
#define g_ww_hi (*x_ww_hi)
#define g_ww_lo (*x_ww_lo)
#define vm_inline_ok (*x_vm_inline_ok)
#define ppu_vm_size (*x_ppu_vm_size)
#define ppu_hle_inject_base (*x_ppu_hle_inject_base)
'''
    rows = exe.rows(build['table'])
    hosts = sorted(set(rows.values()))
    share = {}
    for h in rows.values():
        share[h] = share.get(h, 0) + 1
    ext = set()
    for b in bodies.values():
        ext |= set(re.findall(r'func_[0-9A-F]{8}', b))
    ext = sorted(ext - want)
    order = sorted(want)
    hooks, index = [], {}
    for n in order:
        g = int(n[5:], 16)
        if n in SKIP or g not in rows:      # no row: a tail entry only our copies reach
            continue
        h = rows[g]
        assert share[h] == 1, n
        assert hosts[bisect.bisect(hosts, h)] - h >= 14, n
        index[n] = len(hooks)
        hooks.append((n, h - BASE))

    def seen(n, b):
        if n not in index:
            return b
        head, rest = b.split('\n', 1)
        first = 'nhl_data_words(); ' if n == EARLY and data_words else ''
        return f'{head}\n    if (!nhl_was[{index[n]}]) {{ nhl_was[{index[n]}] = 1; {first}nhl_seen({index[n]}); }}\n{rest}'

    L = [top + preamble, 'extern "C" void nhl_seen(int); static volatile char nhl_was[%d];' % max(len(hooks), 1),
         '/* calls out of the copy go to the exe */', 'extern "C" {']
    L += [f'void (*p_{n})(ppu_context*);' for n in ext] + ['}']
    L += ['extern "C" void nhl_word(unsigned, unsigned, unsigned);', 'static void nhl_data_words(void) {']
    L += [f'    {{ unsigned was = vm_read32(0x{a:x}); vm_write32(0x{a:x}, 0x{v:x}u); nhl_word(0x{a:x}, was, vm_read32(0x{a:x})); }}'
          for a, v in data_words] + ['}']
    L += [f'void {n}(ppu_context* c) {{ __attribute__((musttail)) return p_{n}(c); }}' for n in ext]
    L += [seen(n, bodies[n]) for n in order]
    L += ['struct Hook { unsigned rva; void (*fn)(ppu_context*); unsigned char head[16]; const char* name; };',
          'struct Link { void* p; unsigned rva; };', 'extern "C" {',
          f'extern const int nhl_hook_count = {len(hooks)}; extern const int nhl_link_count = {len(ext)};',
          'extern const Hook nhl_hooks[] = {']
    L += [f'  {{ 0x{r:x}, {n}, {carr(exe.read(r, 16))}, "{n}" }},' for n, r in hooks]
    L += ['  { 0 } };', 'extern const Link nhl_links[] = {']
    L += [f'  {{ &p_{n}, 0x{rows[int(n[5:], 16)] - BASE:x} }},' for n in ext]
    L += ['  { 0 } };', '}']
    open(os.path.join(OUT, 'swap.cpp'), 'w', encoding='latin-1', newline='\n').write('\n'.join(L) + '\n')
    stamp, image = exe.id
    I = [f'#define EXE_STAMP 0x{stamp:08x}u', f'#define EXE_IMAGE 0x{image:08x}u', f'#define TRAMP_OFF 0x{build["tramp_off"]:x}']
    for k, v in build['helpers'].items():
        I += [f'#define RVA_{k} 0x{v - BASE:x}', f'#define HEAD_{k} {carr(exe.read(v - BASE, 8))}']
    I += [f'#define RVA_{k} 0x{v - BASE:x}' for k, v in build['data'].items()]
    open(os.path.join(OUT, 'ids.h'), 'w', newline='\n').write('\n'.join(I) + '\n')
    for f in ('proxy.cpp', 'proxy.def'):
        shutil.copy(os.path.join(HERE, f), OUT)
    shutil.copy(os.path.join(R, 'ppu_recomp.h'), OUT)
    RT = os.path.join(port, 'ps3recomp', 'ps3recomp-master')
    FL = '/std:c++20 /EHsc /O1 /Ob1 /w /bigobj /Zc:tlsGuards- /clang:-mfma /clang:-ffp-contract=off /clang:-march=x86-64-v3 /GS- /MT'
    INC = f'/I"{RT}\\runtime\\ppu" /I"{RT}\\include" /I.'
    dev = os.path.join(port, 'tools', 'devenv.cmd')
    open(os.path.join(OUT, 'cc.cmd'), 'w').write(f'''@echo off
call "{dev}" clang-cl /c {FL} {INC} swap.cpp proxy.cpp || exit /b 1
call "{dev}" lld-link /dll /nologo /def:proxy.def /out:XINPUT1_4.dll swap.obj proxy.obj libcmt.lib libvcruntime.lib libucrt.lib kernel32.lib /opt:ref /machine:x64
''')
    return len(hooks), len(ext), len(data_words)


def pack(work, exe):
    index = dict(version=G.TEAMS_VERSION, stamp=f'{exe.id[0]:08x}', image=f'{exe.id[1]:08x}')
    out = os.path.join(work, 'portpatch.zip')
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('index.json', json.dumps(index, sort_keys=True))
        z.write(os.path.join(work, 'dll', 'XINPUT1_4.dll'), 'XINPUT1_4.dll')
    return out


def main():
    port, exe_path, work = sys.argv[1:4]
    exe = Exe(exe_path)
    build = BUILDS.get(exe.id)
    if build is None:
        raise SystemExit(f'Not a build this knows: stamp {exe.id[0]:08x}, image {exe.id[1]:08x} (README.md, "A new build").')
    os.makedirs(work, exist_ok=True)
    patch, path = patch_words(), os.path.join(work, 'patch.json')
    json.dump(patch, open(path, 'w'))
    print('words', len(patch['words']), 'blocks', len(patch['caves']), flush=True)
    listed = os.path.join(work, 'swap.json')
    if '--skip-lift' in sys.argv:
        swap = json.load(open(listed))
    else:
        subprocess.check_call([sys.executable, '-I', '-B', os.path.join(HERE, 'lift.py'), path, port, work, hex(build['code_end'])])
        swap = changed(port, work)              # before the flags pass: the unchanged lift it compares with had none
        json.dump(swap, open(listed, 'w'))
    rows = exe.rows(build['table'])
    bad = uncovered(patch, swap, rows, build['code_end'], os.path.join(work, 'patched.elf'))
    print('changed', len(swap['changed']), 'new', len(swap['new']), flush=True)
    if bad:
        raise SystemExit('Words in no swapped function: ' + ' '.join(hex(a) for a in bad))
    if '--skip-lift' not in sys.argv:
        R = os.path.join(work, 'recompiled')
        tools = os.path.join(port, 'tools')
        subprocess.check_call([sys.executable, '-I', '-B', os.path.join(tools, 'nhl_restore_preamble.py'), os.path.join(R, 'ppu_recomp.h')], cwd=port)
        subprocess.check_call([sys.executable, '-I', '-B', os.path.join(tools, 'nhl_ppu_flags.py'), os.path.join(R, 'ppu_recomp_*.cpp')], cwd=port)
    print('hooks %d, links %d, data words %d' % make(port, work, exe, build, patch, swap), flush=True)
    subprocess.check_call(['cmd', '/c', '.\\cc.cmd'], cwd=os.path.join(work, 'dll'))
    out = pack(work, exe)
    print(out, os.path.getsize(out))


if __name__ == '__main__':
    main()
