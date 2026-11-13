"""Builds the game patch of NHL Legacy Native, a stand-in XINPUT1_4.dll (README.md here). Nothing it makes goes into git.

    py -3.13 -B tools/native_patch/build.py <port clone> <NHLLegacy.exe> <work folder> [--skip-lift]
    py -3.13 -B tools/native_patch/build.py --merge <out.zip> <work 1.0.0>/portpatch.zip <work 1.0.1>/portpatch.zip

<work>/dll/XINPUT1_4.dll and <work>/portpatch.zip (one build) come out; --merge makes the pack of every build, which goes into
private/packs by hand."""
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
# The lifter makes frsqrte the true root; the chip and RPCS3 give a rough table value. The game refines it, and a different
# start ends a few last digits off, which is enough to fall out of step online. Every function holding one is swapped.
ROOT = re.compile(r'(?<!\(double\)\(float\)\()1\.0 / sqrt\((ctx->fpr\[\d+\])\)')
ROOT_CODE = '''static inline double nhl_frsqrte(double b) {
    static const unsigned man[16] = {0xf1000, 0xd8000, 0xc0000, 0xa8000, 0x98000, 0x88000, 0x80000, 0x70000,
                                     0x60000, 0x4c000, 0x3c000, 0x30000, 0x20000, 0x18000, 0x10000, 0x8000};
    uint64_t u; memcpy(&u, &b, 8);
    unsigned i = (unsigned)(u >> 49), sign = i >> 14, e = (i >> 3) & 0x7ff, v;
    if (e == 0) v = 0x7ff00000u | sign << 31;
    else if (e == 0x7ff) v = i == 0x7ff << 3 ? 0 : 0x7ff80000u;
    else if (sign) v = 0x7ff80000u;
    else v = man[8 ^ (i & 15)] | (0x3fe00000u - (((e + 0x1c01) >> 1) << 20));
    u = (uint64_t)v << 32; memcpy(&b, &u, 8); return b;
}
'''
# Online only (online.inc, proxy.cpp): what the DLL answers in the port's place, and the functions with the online entry's words.
SIGN_IN = {'on_register_callback': 0xE7DCD3B4, 'on_request_ticket': 0x8297F1EC, 'on_get_ticket': 0x0968AA36,
           'on_get_ticket_param': 0x58FA4FCD, 'on_get_network_time': 0xBDC07FD5, 'on_get_account_region': 0xB1E0718B,
           'on_check_callback': 0x189A74DA}
ONLINE_WORDS = {a: new for a, new, _ in G.ONLINE_101}   # each is a `cmpwi r3,0` straight after a call, made `cmpwi r3,1`

# What each build of the exe keeps where: none of it is exported. Found with llvm-objdump, docs: README.md "A new build".
BUILDS = {
    (0x6ae7cb75, 0x1a657000): dict(
        table=0x1429f000 + 746080, code_end=0x1a62e4c, tramp_off=0x4170,
        helpers=dict(vm_read8=0x140010c20, vm_read16=0x144f94b90, vm_read32=0x144f559c0, vm_read64=0x144f5a690,
                     vm_write8=0x1443d4cd0, vm_write16=0x144c5bfe0, vm_write32=0x144c55020, vm_write64=0x1443d47d0,
                     ppu_ww_note_st16=0x144f942f0, ps3_indirect_call=0x1443d49f0, ppu_stdcx64=0x1443d4400,
                     ps3_hle_call=0x1451abdd0),
        data=dict(vm_base=0x154d776e0, g_vm_ld_gate=0x154ecca90, g_vm_st_gate=0x1571ef800, g_ww_hi=0x154ecca6c,
                  tls_index=0x1599410f8)),
    # 1.0.1 (2026-11-11): the same lift (105,841 rows, every lifted function the same instructions), helpers moved, the
    # thread block 0x340 further on (tramp_off). Paired with 1.0.0's by disassembling the same functions: docs/notes/native-101.md.
    (0x6af40f41, 0x1a614000): dict(
        table=0x142e3720, code_end=0x1a62e4c, tramp_off=0x44b0,
        helpers=dict(vm_read8=0x140010850, vm_read16=0x144f723b0, vm_read32=0x144f34020, vm_read64=0x144f37eb0,
                     vm_write8=0x1443b2610, vm_write16=0x144e1bec0, vm_write32=0x144e1bbc0, vm_write64=0x144c35d70,
                     ppu_ww_note_st16=0x144f71b10, ps3_indirect_call=0x1443b2330, ppu_stdcx64=0x1443b1f60,
                     ps3_hle_call=0x14519f3e0),
        data=dict(vm_base=0x154d08820, g_vm_ld_gate=0x154e638c0, g_vm_st_gate=0x157186640, g_ww_hi=0x154e6389c,
                  tls_index=0x1598d7f38)),
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


# --net-log only, never in a pack: the plain match data each side hands over and gets (NHL_PUCKPEAK_INPUTS=<file>)
NET_LOG = {
    'func_00F286E4': ('ctx->lr = 0x00F2871C; func_00A94794(ctx);',
                      'nhl_net_send(ctx); ctx->lr = 0x00F2871C; func_00A94794(ctx);'),
    'func_00F2884C': ('ctx->lr = 0x00F2889C; func_00A95920(ctx); DRAIN_TRAMPOLINE(ctx);',
                      'ctx->lr = 0x00F2889C; func_00A95920(ctx); DRAIN_TRAMPOLINE(ctx); if ((int)ctx->gpr[3] > 0) nhl_net_read(ctx);'),
}
NET_CODE = '''extern "C" void nhl_net_line(const char*);
static unsigned nhl_sends, nhl_pairs;
static void nhl_net(int way, unsigned long long buf, int len) {
    char s[4200]; int n = snprintf(s, 200, "%c%d k%u n%d ", way ? '<' : '>', way, way ? nhl_pairs : nhl_sends, len);
    for (int i = 0; i < len && i < 2000; i++) n += snprintf(s + n, 3, "%02x", (unsigned)vm_read8((uint32_t)buf + i));
    nhl_net_line(s);
}
static void nhl_net_send(ppu_context* ctx) { nhl_net(0, ctx->gpr[4], (int)ctx->gpr[5]); nhl_sends++; }
static void nhl_net_read(ppu_context* ctx) {
    nhl_net(1, ctx->gpr[1] + 0x90, (int)vm_read32(ctx->gpr[1] + 0x70));
    nhl_net(2, (unsigned)ctx->gpr[1] + 0x190, (int)vm_read32(ctx->gpr[1] + 0x74));
    nhl_pairs++;
}
'''


def carr(b):
    return '{' + ','.join(str(x) for x in b) + '}'


def online_copies(folder, bodies):
    """The functions holding the online entry's words, as copies with those words in; the patch's own copy where there is one."""
    out = {}
    for a in sorted(ONLINE_WORDS):
        call = f'ctx->lr = 0x{a:08X}; if (1) {{ ps3_indirect_call(ctx); DRAIN_TRAMPOLINE(ctx); }}\n'
        found = [(n, b) for n, b in bodies.items() if call in b]
        if not found:
            for p in glob.glob(os.path.join(folder, 'ppu_recomp_[0-9]*.cpp')):
                t = open(p, encoding='latin-1').read()
                if call in t:
                    found = [(m[1], m[0]) for m in FUNC.finditer(t) if call in m[0]]
                    break
        (name, text), = found
        text = out.get(name, text)
        at = text.index(call) + len(call)
        line = text[at:text.index('\n', at)]
        zero = '(int64_t)((int32_t)ctx->gpr[3]) == (int64_t)((int64_t)0)'
        assert zero in line, line
        out[name] = text[:at] + line.replace(zero, zero[:-2] + '1)') + text[at + len(line):]
    (place, _, _, _), = G.ONLINE_START_101       # the game asks "Play Now at boot?"; a start from a lobby says no (art/onlinestart.py)
    call = f'ctx->lr = 0x{place + 4:08X}; if (1) {{ ps3_indirect_call(ctx); DRAIN_TRAMPOLINE(ctx); }}\n'
    found = [(n, b) for n, b in {**bodies, **out}.items() if call in b]
    if not found:
        for p in glob.glob(os.path.join(folder, 'ppu_recomp_[0-9]*.cpp')):
            t = open(p, encoding='latin-1').read()
            if call in t:
                found = [(m[1], m[0]) for m in FUNC.finditer(t) if call in m[0]]
                break
    (name, text), = found
    out[name] = out.get(name, text).replace(call, f'if (nhl_start_online) ctx->gpr[3] = 0; else {{ {call.rstrip()} }}\n')
    head = re.compile(r'^void (?:__attribute__\(\(weak\)\) )?func_')
    return {n: head.sub('extern "C" void on_func_', t, 1) for n, t in out.items()}


def make(port, work, exe, build, patch, swap, net_log=False):
    """swap.cpp, ids.h and the compile script in <work>/dll."""
    R, OUT = os.path.join(work, 'recompiled'), os.path.join(work, 'dll')
    os.makedirs(OUT, exist_ok=True)
    data_words = sorted((int(a, 16), v) for a, v in patch['words'].items() if int(a, 16) >= build['code_end'])
    want = set(swap['changed']) | set(swap['new']) | ({EARLY} if data_words else set()) | (set(NET_LOG) if net_log else set())
    bodies, preamble = {}, None
    for p in sorted(glob.glob(os.path.join(R, 'ppu_recomp_[0-9]*.cpp'))):
        t = open(p, encoding='latin-1').read()
        if preamble is None:
            preamble = t[:t.index('\nvoid func_') + 1]
        for m in FUNC.finditer(t):
            if ROOT.search(m[0]):
                want.add(m[1])
    for p in sorted(glob.glob(os.path.join(R, 'ppu_recomp_[0-9]*.cpp'))):
        for m in FUNC.finditer(open(p, encoding='latin-1').read()):
            if m[1] in want:
                bodies[m[1]] = m[0]
    assert set(bodies) == want, want - set(bodies)
    if net_log:
        for n, (old, new) in NET_LOG.items():
            assert bodies[n].count(old) == 1, n
            bodies[n] = bodies[n].replace(old, new)
    online = online_copies(R, bodies)
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
extern "C" int nhl_start_online;
'''
    rows = exe.rows(build['table'])
    hosts = sorted(set(rows.values()))
    share = {}
    for h in rows.values():
        share[h] = share.get(h, 0) + 1
    ext = set()
    for b in list(bodies.values()) + list(online.values()):
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

    L = [top + preamble + ROOT_CODE + ('#include <stdio.h>\n' + NET_CODE if net_log else ''), 'extern "C" void nhl_seen(int); static volatile char nhl_was[%d];' % max(len(hooks), 1),
         '/* calls out of the copy go to the exe */', 'extern "C" {']
    L += [f'void (*p_{n})(ppu_context*);' for n in ext] + ['}']
    L += ['extern "C" void nhl_word(unsigned, unsigned, unsigned);', 'static void nhl_data_words(void) {']
    L += [f'    {{ unsigned was = vm_read32(0x{a:x}); vm_write32(0x{a:x}, 0x{v:x}u); nhl_word(0x{a:x}, was, vm_read32(0x{a:x})); }}'
          for a, v in data_words] + ['}']
    L += [f'void {n}(ppu_context* c) {{ __attribute__((musttail)) return p_{n}(c); }}' for n in ext]
    L += [seen(n, bodies[n]) for n in order]
    L += list(online.values())
    L += ['#include "online.inc"']
    L += ['struct Hook { unsigned rva; void (*fn)(ppu_context*); unsigned char head[16]; const char* name; };',
          'struct Link { void* p; unsigned rva; };', 'extern "C" {',
          f'extern const int nhl_hook_count = {len(hooks)}; extern const int nhl_link_count = {len(ext)};',
          'extern const Hook nhl_hooks[] = {']
    L += [f'  {{ 0x{r:x}, {n}, {carr(exe.read(r, 16))}, "{n}" }},' for n, r in hooks]
    L += ['  { 0 } };', 'extern const Link nhl_links[] = {']
    L += [f'  {{ &p_{n}, 0x{rows[int(n[5:], 16)] - BASE:x} }},' for n in ext]
    L += ['  { 0 } };']
    stubs = {e['nid']: int(e['stub'], 16) for e in json.load(open(os.path.join(port, 'nhl', 'out', 'EBOOT_v101.imports.json')))}
    taken = [(f, rows[stubs[hex(v)]]) for f, v in SIGN_IN.items()]
    taken += [(f'on_{n}', rows[int(n[5:], 16)]) for n in online]
    for f, h in taken:
        assert share[h] == 1 and hosts[bisect.bisect(hosts, h)] - h >= 14, f
    L += [f'extern const int nhl_online_count = {len(taken)};', 'extern const Hook nhl_online[] = {']
    L += [f'  {{ 0x{h - BASE:x}, {f}, {carr(exe.read(h - BASE, 16))}, "{f}" }},' for f, h in taken]
    L += ['  { 0 } };', '}']
    text = ROOT.sub(r'nhl_frsqrte(\1)', '\n'.join(L) + '\n')
    open(os.path.join(OUT, 'swap.cpp'), 'w', encoding='latin-1', newline='\n').write(text)
    stamp, image = exe.id
    I = [f'#define EXE_STAMP 0x{stamp:08x}u', f'#define EXE_IMAGE 0x{image:08x}u', f'#define TRAMP_OFF 0x{build["tramp_off"]:x}']
    for k, v in build['helpers'].items():
        I += [f'#define RVA_{k} 0x{v - BASE:x}', f'#define HEAD_{k} {carr(exe.read(v - BASE, 8))}']
    I += [f'#define RVA_{k} 0x{v - BASE:x}' for k, v in build['data'].items()]
    open(os.path.join(OUT, 'ids.h'), 'w', newline='\n').write('\n'.join(I) + '\n')
    for f in ('proxy.cpp', 'proxy.def', 'online.inc'):
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


FIRST = (0x6ae7cb75, 0x1a657000)   # 1.0.0: its file stays the pack's top-level XINPUT1_4.dll, the one programs before 0.98.0 read


def merge(out, zips):
    """One portpatch.zip from the packs of single builds (each made by `pack`): a file per build listed in `builds`, 1.0.0's
    also under the old top-level names. Every pack must hold the same patch version."""
    files, versions = {}, set()
    for p in zips:
        with zipfile.ZipFile(p) as z:
            index = json.loads(z.read('index.json'))
            files[(int(index['stamp'], 16), int(index['image'], 16))] = z.read('XINPUT1_4.dll')
            versions.add(index['version'])
    assert len(versions) == 1, versions
    assert FIRST in files, 'the 1.0.0 file is needed: older programs read only that one'
    builds = [dict(stamp=f'{s:08x}', image=f'{i:08x}', file=f'XINPUT1_4-{s:08x}.dll') for s, i in sorted(files)]
    index = dict(version=versions.pop(), stamp=f'{FIRST[0]:08x}', image=f'{FIRST[1]:08x}', builds=builds)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('index.json', json.dumps(index, sort_keys=True))
        z.writestr('XINPUT1_4.dll', files[FIRST])
        for b in builds:
            z.writestr(b['file'], files[(int(b['stamp'], 16), int(b['image'], 16))])
    return out


def main():
    if sys.argv[1] == '--merge':                # build.py --merge <out.zip> <pack of a build> <pack of a build> ...
        print(merge(sys.argv[2], sys.argv[3:]))
        return
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
    print('hooks %d, links %d, data words %d' % make(port, work, exe, build, patch, swap, '--net-log' in sys.argv), flush=True)
    subprocess.check_call(['cmd', '/c', '.\\cc.cmd'], cwd=os.path.join(work, 'dll'))
    out = pack(work, exe)
    print(out, os.path.getsize(out))


if __name__ == '__main__':
    main()
