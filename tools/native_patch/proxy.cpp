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

// ---- what the copies need from the exe
extern "C" {
void* x_vm_base; void* x_vm_ld_gate; void* x_vm_st_gate; void* x_ww_hi;
unsigned long* x_tls_index; unsigned long x_tramp_off;
}
#define JUMP(n) extern "C" void* p_h_##n; void* p_h_##n; \
    extern "C" __attribute__((naked)) void n() { __asm__("jmpq *p_h_" #n "(%rip)"); }
JUMP(vm_read8) JUMP(vm_read16) JUMP(vm_read32) JUMP(vm_read64)
JUMP(vm_write8) JUMP(vm_write16) JUMP(vm_write32) JUMP(vm_write64)
JUMP(ppu_ww_note_st16) JUMP(ps3_indirect_call) JUMP(ppu_stdcx64)

struct Helper { void** p; uint32_t rva; uint8_t head[8]; };
static const Helper helpers[] = {
#define H(n) { &p_h_##n, RVA_##n, HEAD_##n },
    H(vm_read8) H(vm_read16) H(vm_read32) H(vm_read64) H(vm_write8) H(vm_write16) H(vm_write32) H(vm_write64)
    H(ppu_ww_note_st16) H(ps3_indirect_call) H(ppu_stdcx64)
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
    return true;
}

static void swap_all(uint8_t* base)
{
    for (auto& h : helpers) *h.p = base + h.rva;
    x_vm_base = base + RVA_vm_base; x_vm_ld_gate = base + RVA_g_vm_ld_gate;
    x_vm_st_gate = base + RVA_g_vm_st_gate; x_ww_hi = base + RVA_g_ww_hi;
    x_tls_index = (unsigned long*)(base + RVA_tls_index); x_tramp_off = TRAMP_OFF;
    for (int i = 0; i < nhl_link_count; i++) *nhl_links[i].p = base + nhl_links[i].rva;
    for (int i = 0; i < nhl_hook_count; i++) {
        uint8_t* at = base + nhl_hooks[i].rva;
        uint8_t jump[14] = { 0xff, 0x25, 0, 0, 0, 0 };
        void* to = (void*)nhl_hooks[i].fn;
        memcpy(jump + 6, &to, 8);
        DWORD old;
        if (!VirtualProtect(at, sizeof jump, PAGE_EXECUTE_READWRITE, &old)) { nhl_log("cannot write %s", nhl_hooks[i].name); ExitProcess(1); }
        memcpy(at, jump, sizeof jump);
        VirtualProtect(at, sizeof jump, old, &old);
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
