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
static const char REDIRECTOR[] = "gosredirector.ea.com";

extern "C" unsigned long long nhl_now_ms(void)
{
    FILETIME f; GetSystemTimeAsFileTime(&f);
    return (((unsigned long long)f.dwHighDateTime << 32 | f.dwLowDateTime) - 116444736000000000ull) / 10000;
}

typedef int (WINAPI* Lookup)(const char*, const char*, const void*, void**);
typedef int (WINAPI* Bind)(uintptr_t, const void*, int);
static Lookup r_lookup; static Bind r_bind;

static int WINAPI my_lookup(const char* host, const char* port, const void* hints, void** out)
{
    if (host && !_stricmp(host, REDIRECTOR)) { nhl_log("%s goes to %s", host, on_server); host = on_server; }
    return r_lookup(host, port, hints, out);
}
static uint8_t bind_to[4];             // a second copy on one PC: NHL_PUCKPEAK_BIND=127.0.0.5
static int WINAPI my_bind(uintptr_t s, const void* addr, int len)
{
    char here[16];
    if (len >= 16 && !*(const uint32_t*)((const char*)addr + 4)) {
        memcpy(here, addr, 16); memcpy(here + 4, bind_to, 4); addr = here;
    }
    return r_bind(s, addr, len);
}
static FILE* net_file;
extern "C" void nhl_net_line(const char* s)
{
    if (!net_file) return;
    fprintf(net_file, "%llu %s\n", nhl_now_ms(), s);
    fflush(net_file);
}

// The port lists the save folders by name and the game loads the first roster at boot. For a start from a lobby the lobby's
// roster is listed first (NHL_PUCKPEAK_ROSTER): no save is touched, and a normal start sees the usual order.
extern "C" { int nhl_start_online; }    // read by the copy of the main menu's boot question (build.py)
static char first_save[64];
static HANDLE saves_list;
static WIN32_FIND_DATAA held;
static int holding;
static HANDLE (WINAPI* r_first)(const char*, WIN32_FIND_DATAA*);
static BOOL (WINAPI* r_next)(HANDLE, WIN32_FIND_DATAA*);
static HANDLE WINAPI my_first(const char* path, WIN32_FIND_DATAA* out)
{
    HANDLE list = r_first(path, out);
    size_t n = strlen(path);
    if (list == INVALID_HANDLE_VALUE || n < 11 || _stricmp(path + n - 11, "\\savedata\\*")) return list;
    char one[1100];
    snprintf(one, sizeof one, "%.*s%s", (int)(n - 1), path, first_save);
    WIN32_FIND_DATAA want;
    HANDLE found = r_first(one, &want);
    if (found == INVALID_HANDLE_VALUE) return list;
    FindClose(found);
    held = *out; holding = 1; saves_list = list; *out = want;
    return list;
}
static BOOL WINAPI my_next(HANDLE list, WIN32_FIND_DATAA* out)
{
    if (list != saves_list) return r_next(list, out);
    if (holding) { holding = 0; *out = held; return TRUE; }
    while (r_next(list, out))
        if (_stricmp(out->cFileName, first_save)) return TRUE;
    saves_list = nullptr;
    return FALSE;
}

// The exe's calls into WS2_32 go through its import table; ordinals as Windows numbers them.
static void net_hooks(uint8_t* base)
{
    auto* nt = (IMAGE_NT_HEADERS64*)(base + ((IMAGE_DOS_HEADER*)base)->e_lfanew);
    auto* d = (IMAGE_IMPORT_DESCRIPTOR*)(base + nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
    int done = 0;
    for (; d->Name; d++) {
        int files = !_stricmp((char*)base + d->Name, "KERNEL32.dll");
        if (!files && _stricmp((char*)base + d->Name, "WS2_32.dll")) continue;
        auto* names = (IMAGE_THUNK_DATA64*)(base + d->OriginalFirstThunk);
        auto* slots = (IMAGE_THUNK_DATA64*)(base + d->FirstThunk);
        for (; names->u1.AddressOfData; names++, slots++) {
            void* mine = nullptr; void** keep = nullptr;
            if (files) {
                if (IMAGE_SNAP_BY_ORDINAL64(names->u1.Ordinal) || !first_save[0]) continue;
                const char* name = ((IMAGE_IMPORT_BY_NAME*)(base + names->u1.AddressOfData))->Name;
                if (!strcmp(name, "FindFirstFileA")) { mine = (void*)my_first; keep = (void**)&r_first; }
                else if (!strcmp(name, "FindNextFileA")) { mine = (void*)my_next; keep = (void**)&r_next; }
            } else if (IMAGE_SNAP_BY_ORDINAL64(names->u1.Ordinal)) {
                switch (IMAGE_ORDINAL64(names->u1.Ordinal)) {
                case 2: if (bind_to[0]) { mine = (void*)my_bind; keep = (void**)&r_bind; } break;
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

// RPCS3 runs the console's clock at 80 MHz, the port at the real 79.8. The game works constants out of what it is told, and
// lockstep needs them equal, so online the port's clock, SPU timer and reported speed all say 80 (five constants in .text).
static void console_clock(uint8_t* base)
{
    auto* nt = (IMAGE_NT_HEADERS*)(base + ((IMAGE_DOS_HEADER*)base)->e_lfanew);
    auto* text = IMAGE_FIRST_SECTION(nt);
    uint8_t* from = base + text->VirtualAddress;
    size_t size = text->Misc.VirtualSize - 4;
    const uint32_t real = 79800000, ours = 80000000;
    uint8_t* hits[8]; int found = 0;
    for (size_t i = 0; i < size; i++)
        if (from[i] == 0xC0 && !memcmp(from + i, &real, 4)) { if (found < 8) hits[found] = from + i; found++; }
    nhl_log("console clock: %d places", found);
    if (found != 5) return;
    for (int i = 0; i < found; i++) {
        DWORD old;
        VirtualProtect(hits[i], 4, PAGE_EXECUTE_READWRITE, &old);
        memcpy(hits[i], &ours, 4);
        VirtualProtect(hits[i], 4, old, &old);
    }
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
        console_clock(base);
        GetEnvironmentVariableA("NHL_PUCKPEAK_ROSTER", first_save, sizeof first_save);
        nhl_start_online = GetEnvironmentVariableA("NHL_PUCKPEAK_START", nullptr, 0) != 0;
        for (int i = 0; i < nhl_online_count; i++)
            jump_to(base + nhl_online[i].rva, (void*)nhl_online[i].fn, nhl_online[i].name);
        char path[260];
        if (GetEnvironmentVariableA("NHL_PUCKPEAK_INPUTS", path, sizeof path)) net_file = fopen(path, "w");
        if (GetEnvironmentVariableA("NHL_PUCKPEAK_BIND", path, sizeof path)) {
            int p[4];
            if (sscanf(path, "%d.%d.%d.%d", p, p + 1, p + 2, p + 3) == 4) for (int i = 0; i < 4; i++) bind_to[i] = (uint8_t)p[i];
        }
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
