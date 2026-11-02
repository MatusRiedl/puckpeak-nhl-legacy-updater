// The patch file for NHL Legacy Native: stands in for XINPUT1_4.dll, passes its calls on to the system's copy, and when the exe is
// the one this was built for, sends the functions our patch changes to the compiled copies in swap.cpp. Any other exe: nothing.
#include <windows.h>
#include <intrin.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "ids.h"

struct Hook { uint32_t rva; void (*fn)(void*); uint8_t head[16]; const char* name; };
struct Link { void** p; uint32_t rva; };
extern "C" const Hook nhl_hooks[];
extern "C" const int nhl_hook_count;
extern "C" const Link nhl_links[];
extern "C" const int nhl_link_count;
extern "C" const Hook nhl_online[];
extern "C" const int nhl_online_count;

// ---- what the copies need from the exe
extern "C" {
void* x_vm_base; void* x_vm_ld_gate; void* x_vm_st_gate; void* x_ww_hi;
unsigned long* x_tls_index; unsigned long x_tramp_off;
}
#define JUMP(n) extern "C" void* p_h_##n; void* p_h_##n; \
    extern "C" __attribute__((naked)) void n() { __asm__("jmpq *p_h_" #n "(%rip)"); }
JUMP(vm_read8) JUMP(vm_read16) JUMP(vm_read32) JUMP(vm_read64)
JUMP(vm_write8) JUMP(vm_write16) JUMP(vm_write32) JUMP(vm_write64)
JUMP(ppu_ww_note_st16) JUMP(ps3_indirect_call) JUMP(ppu_stdcx64) JUMP(ps3_hle_call)

struct Helper { void** p; uint32_t rva; uint8_t head[8]; };
static const Helper helpers[] = {
#define H(n) { &p_h_##n, RVA_##n, HEAD_##n },
    H(vm_read8) H(vm_read16) H(vm_read32) H(vm_read64) H(vm_write8) H(vm_write16) H(vm_write32) H(vm_write64)
    H(ppu_ww_note_st16) H(ps3_indirect_call) H(ppu_stdcx64) H(ps3_hle_call)
};

// ---- the log, next to this file, only with NHL_PUCKPEAK_LOG set
static HANDLE log_file = INVALID_HANDLE_VALUE;
static CRITICAL_SECTION log_lock;
void nhl_log(const char* fmt, ...)
{
    if (log_file == INVALID_HANDLE_VALUE) return;
    char buf[300]; va_list a; va_start(a, fmt);
    int n = vsnprintf(buf, sizeof buf - 2, fmt, a); va_end(a);
    if (n < 0) return;
    if (n > (int)sizeof buf - 3) n = sizeof buf - 3;
    buf[n++] = '\r'; buf[n++] = '\n';
    EnterCriticalSection(&log_lock);
    DWORD w; WriteFile(log_file, buf, n, &w, nullptr);
    LeaveCriticalSection(&log_lock);
}
extern "C" void nhl_seen(int i) { nhl_log("entered %s", nhl_hooks[i].name); }
extern "C" void nhl_word(unsigned a, unsigned was, unsigned now) { nhl_log("word %08x: %08x -> %08x", a, was, now); }

static void open_log(HMODULE self)
{
    wchar_t p[MAX_PATH]; DWORD n = GetModuleFileNameW(self, p, MAX_PATH);
    while (n && p[n - 1] != L'\\') n--;
    wcscpy_s(p + n, MAX_PATH - n, L"puckpeak_patch.log");
    log_file = CreateFileW(p, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
}

// ---- the swap
static bool same_exe(uint8_t* base)
{
    auto* dos = (IMAGE_DOS_HEADER*)base;
    auto* nt = (IMAGE_NT_HEADERS64*)(base + dos->e_lfanew);
    if (nt->FileHeader.TimeDateStamp != EXE_STAMP || nt->OptionalHeader.SizeOfImage != EXE_IMAGE) {
        nhl_log("not the exe this was made for: stamp %08x image %08x", nt->FileHeader.TimeDateStamp, nt->OptionalHeader.SizeOfImage);
        return false;
    }
    for (auto& h : helpers)
        if (memcmp(base + h.rva, h.head, 8)) { nhl_log("helper at %08x differs", h.rva); return false; }
    for (int i = 0; i < nhl_hook_count; i++)
        if (memcmp(base + nhl_hooks[i].rva, nhl_hooks[i].head, 16)) { nhl_log("%s differs", nhl_hooks[i].name); return false; }
    for (int i = 0; i < nhl_online_count; i++)
        if (memcmp(base + nhl_online[i].rva, nhl_online[i].head, 16)) { nhl_log("%s differs", nhl_online[i].name); return false; }
    return true;
}

static void jump_to(uint8_t* at, void* to, const char* name)
{
    uint8_t jump[14] = { 0xff, 0x25, 0, 0, 0, 0 };
    memcpy(jump + 6, &to, 8);
    DWORD old;
    if (!VirtualProtect(at, sizeof jump, PAGE_EXECUTE_READWRITE, &old)) { nhl_log("cannot write %s", name); ExitProcess(1); }
    memcpy(at, jump, sizeof jump);
    VirtualProtect(at, sizeof jump, old, &old);
}

// ---- online: only with NHL_PUCKPEAK_ONLINE=<our server>, set by the app
static char on_server[256];
static uintptr_t p2p_socket = ~(uintptr_t)0;
static volatile long p2p_next;
static unsigned short vport_mine, vport_peer;
static int shown_out, shown_in;
static const char REDIRECTOR[] = "gosredirector.ea.com";
enum { HEADER = 6, P2P_FLAG = 1, MOST = 1600 };

extern "C" void nhl_vports(unsigned mine, unsigned peer)
{
    if (mine) { vport_mine = (unsigned short)mine; p2p_next = 1; }
    if (peer) vport_peer = (unsigned short)peer;
}
extern "C" unsigned long long nhl_now_ms(void)
{
    FILETIME f; GetSystemTimeAsFileTime(&f);
    return (((unsigned long long)f.dwHighDateTime << 32 | f.dwLowDateTime) - 116444736000000000ull) / 10000;
}

typedef int (WINAPI* Lookup)(const char*, const char*, const void*, void**);
typedef int (WINAPI* Bind)(uintptr_t, const void*, int);
typedef int (WINAPI* Send)(uintptr_t, const char*, int, int, const void*, int);
typedef int (WINAPI* Receive)(uintptr_t, char*, int, int, void*, int*);
static Lookup r_lookup; static Bind r_bind; static Send r_send; static Receive r_receive;

static int WINAPI my_lookup(const char* host, const char* port, const void* hints, void** out)
{
    if (host && !_stricmp(host, REDIRECTOR)) { nhl_log("%s goes to %s", host, on_server); host = on_server; }
    return r_lookup(host, port, hints, out);
}
static int WINAPI my_bind(uintptr_t s, const void* addr, int len)
{
    int r = r_bind(s, addr, len);
    if (!r && p2p_next) {               // on_bind saw a virtual port: only the game's P2P socket has one
        p2p_next = 0;
        p2p_socket = s;
        const uint8_t* a = (const uint8_t*)addr;
        nhl_log("game socket on port %u, virtual port %u", a[2] << 8 | a[3], vport_mine);
    }
    return r;
}
// RPCS3's packets start with the virtual ports they go to and come from, and a flag: little-endian words.
static void show(const char* way, const char* d, int n)
{
    char h[50] = {0};
    for (int i = 0; i < n && i < 16; i++) sprintf(h + i * 3, "%02x ", (uint8_t)d[i]);
    nhl_log("%s %d bytes: %s", way, n, h);
}
static int WINAPI my_send(uintptr_t s, const char* buf, int len, int flags, const void* to, int tolen)
{
    if (s != p2p_socket || len > MOST) return r_send(s, buf, len, flags, to, tolen);
    char out[MOST + HEADER];
    memcpy(out, &vport_peer, 2); memcpy(out + 2, &vport_mine, 2);
    unsigned short flag = P2P_FLAG; memcpy(out + 4, &flag, 2);
    memcpy(out + HEADER, buf, len);
    if (shown_out < 4) { shown_out++; show("out", out, len + HEADER); }
    int n = r_send(s, out, len + HEADER, flags, to, tolen);
    return n < HEADER ? n : n - HEADER;
}
static int WINAPI my_receive(uintptr_t s, char* buf, int len, int flags, void* from, int* fromlen)
{
    if (s != p2p_socket) return r_receive(s, buf, len, flags, from, fromlen);
    char in[MOST + HEADER];
    int n = r_receive(s, in, sizeof in, flags, from, fromlen);
    if (n > 0 && shown_in < 4) { shown_in++; show("in", in, n); }
    if (n < HEADER) return n < 0 ? n : 0;
    n -= HEADER;
    if (n > len) n = len;
    memcpy(buf, in + HEADER, n);
    return n;
}

// The exe's calls into WS2_32 go through its import table; ordinals as Windows numbers them.
static void net_hooks(uint8_t* base)
{
    auto* nt = (IMAGE_NT_HEADERS64*)(base + ((IMAGE_DOS_HEADER*)base)->e_lfanew);
    auto* d = (IMAGE_IMPORT_DESCRIPTOR*)(base + nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
    int done = 0;
    for (; d->Name; d++) {
        if (_stricmp((char*)base + d->Name, "WS2_32.dll")) continue;
        auto* names = (IMAGE_THUNK_DATA64*)(base + d->OriginalFirstThunk);
        auto* slots = (IMAGE_THUNK_DATA64*)(base + d->FirstThunk);
        for (; names->u1.AddressOfData; names++, slots++) {
            void* mine = nullptr; void** keep = nullptr;
            if (IMAGE_SNAP_BY_ORDINAL64(names->u1.Ordinal)) {
                switch (IMAGE_ORDINAL64(names->u1.Ordinal)) {
                case 2: mine = (void*)my_bind; keep = (void**)&r_bind; break;
                case 17: mine = (void*)my_receive; keep = (void**)&r_receive; break;
                case 20: mine = (void*)my_send; keep = (void**)&r_send; break;
                }
            } else if (!strcmp(((IMAGE_IMPORT_BY_NAME*)(base + names->u1.AddressOfData))->Name, "getaddrinfo")) {
                mine = (void*)my_lookup; keep = (void**)&r_lookup;
            }
            if (!mine) continue;
            DWORD old;
            VirtualProtect(slots, 8, PAGE_READWRITE, &old);
            *keep = (void*)slots->u1.Function;
            slots->u1.Function = (ULONGLONG)mine;
            VirtualProtect(slots, 8, old, &old);
            done++;
        }
    }
    nhl_log("online to %s, %d network calls taken", on_server, done);
}

static void swap_all(uint8_t* base)
{
    for (auto& h : helpers) *h.p = base + h.rva;
    x_vm_base = base + RVA_vm_base; x_vm_ld_gate = base + RVA_g_vm_ld_gate;
    x_vm_st_gate = base + RVA_g_vm_st_gate; x_ww_hi = base + RVA_g_ww_hi;
    x_tls_index = (unsigned long*)(base + RVA_tls_index); x_tramp_off = TRAMP_OFF;
    for (int i = 0; i < nhl_link_count; i++) *nhl_links[i].p = base + nhl_links[i].rva;
    for (int i = 0; i < nhl_hook_count; i++)
        jump_to(base + nhl_hooks[i].rva, (void*)nhl_hooks[i].fn, nhl_hooks[i].name);
    if (GetEnvironmentVariableA("NHL_PUCKPEAK_ONLINE", on_server, sizeof on_server)) {
        for (int i = 0; i < nhl_online_count; i++)
            jump_to(base + nhl_online[i].rva, (void*)nhl_online[i].fn, nhl_online[i].name);
        net_hooks(base);
    }
    FlushInstructionCache(GetCurrentProcess(), nullptr, 0);
    nhl_log("swapped %d functions, %d calls out; tls index now %lu", nhl_hook_count, nhl_link_count, *x_tls_index);
}

BOOL WINAPI DllMain(HMODULE self, DWORD why, void*)
{
    if (why != DLL_PROCESS_ATTACH) return TRUE;
    DisableThreadLibraryCalls(self);
    InitializeCriticalSection(&log_lock);
    if (GetEnvironmentVariableW(L"NHL_PUCKPEAK_LOG", nullptr, 0)) open_log(self);
    uint8_t* base = (uint8_t*)GetModuleHandleW(nullptr);
    nhl_log("puckpeak patch: exe at %p", base);
    if (GetEnvironmentVariableW(L"NHL_PUCKPEAK_NOSWAP", nullptr, 0)) { nhl_log("switched off"); return TRUE; }
    if (same_exe(base)) swap_all(base);
    return TRUE;
}

// ---- XInput: the system's own, loaded at the first call
static FARPROC real(int ordinal)
{
    static HMODULE sys;
    if (!sys) {
        wchar_t p[MAX_PATH]; UINT n = GetSystemDirectoryW(p, MAX_PATH);
        wcscpy_s(p + n, MAX_PATH - n, L"\\XINPUT1_4.dll");
        sys = LoadLibraryW(p);
        if (!sys) return nullptr;
    }
    return GetProcAddress(sys, MAKEINTRESOURCEA(ordinal));
}
typedef uintptr_t (WINAPI* Five)(uintptr_t, uintptr_t, uintptr_t, uintptr_t, uintptr_t);
#define PASS(n, ord) extern "C" uintptr_t WINAPI n(uintptr_t a, uintptr_t b, uintptr_t c, uintptr_t d, uintptr_t e) \
    { static FARPROC f; if (!f) f = real(ord); return f ? ((Five)f)(a, b, c, d, e) : ERROR_DEVICE_NOT_CONNECTED; }
PASS(XInputGetState, 2) PASS(XInputSetState, 3) PASS(XInputGetCapabilities, 4) PASS(XInputEnable, 5)
PASS(XInputGetBatteryInformation, 7) PASS(XInputGetKeystroke, 8) PASS(XInputGetAudioDeviceIds, 10)
PASS(x100, 100) PASS(x101, 101) PASS(x102, 102) PASS(x103, 103) PASS(x104, 104) PASS(x108, 108) PASS(x109, 109)
