/* The online half of the patch, compiled at the end of swap.cpp. These replace the port's answers to the game's sign-in calls; proxy.cpp
   sets them only when the app starts the game with NHL_PUCKPEAK_ONLINE (nhl_online). Our server reads a ticket and checks no signature. */
extern "C" void ps3_hle_call(unsigned, ppu_context*);
void nhl_log(const char*, ...);
extern "C" unsigned long long nhl_now_ms(void);

enum { GOT_TICKET = 255, BAD_ARGUMENT = (int)0x8002aa03, RTC_1970_US = 0 };
static const unsigned long long RTC_EPOCH_US = 62135596800000000ull;       // cellRtc counts microseconds from the year 1

static struct {
    unsigned char serial[20], service[24], raw[512];
    unsigned long long issued, expires, account;
    char name[17];
    int size;
} on_t;
static unsigned on_cb, on_cb_arg;
static volatile long on_pending;

static unsigned char* put16(unsigned char* p, unsigned v) { *p++ = v >> 8; *p++ = v; return p; }
static unsigned char* put_head(unsigned char* p, unsigned type, unsigned size) { return put16(put16(p, type), size); }
static unsigned char* put_bytes(unsigned char* p, unsigned type, const void* d, unsigned size)
{
    p = put_head(p, type, size); memcpy(p, d, size); return p + size;
}
static unsigned char* put_int(unsigned char* p, unsigned type, unsigned long long v, int size)
{
    p = put_head(p, type, size);
    for (int i = size - 1; i >= 0; i--) *p++ = (unsigned char)(v >> (i * 8));
    return p;
}

// A version 2.1 ticket: the fields RPCN's tickets carry, in their order and sizes.
static void make_ticket(const char* name, unsigned service)
{
    memset(&on_t, 0, sizeof on_t);
    for (int i = 0; i < 16 && name[i]; i++) on_t.name[i] = name[i];
    unsigned long long h = 0xcbf29ce484222325ull;
    for (const char* c = on_t.name; *c; c++) h = (h ^ (unsigned char)(*c | 0x20)) * 0x100000001b3ull;
    on_t.account = h & 0x7fffffffffffffffull;
    on_t.issued = nhl_now_ms();
    on_t.expires = on_t.issued + 600000;
    unsigned long long s = on_t.account ^ on_t.issued;
    for (int i = 0; i < 20; i++) { s = s * 0x100000001b3ull + 0x9e37; on_t.serial[i] = (unsigned char)(s >> 40); }
    for (int i = 0; i < 24 && service; i++) { on_t.service[i] = vm_read8(service + i); if (!on_t.service[i]) break; }

    char handle[32] = {0}; memcpy(handle, on_t.name, 16);
    static const char domain[4] = {'u', 'n', 0, 0};
    static const unsigned char region[4] = {'u', 's', 0, 1};
    static const char key[4] = {'P', 'P', 'L', 'U'};
    static const unsigned char signature[56] = {0};
    unsigned char body[256], foot[96], *p = body;
    p = put_bytes(p, 8, on_t.serial, 20);
    p = put_int(p, 1, 0x100, 4);
    p = put_int(p, 7, on_t.issued, 8);
    p = put_int(p, 7, on_t.expires, 8);
    p = put_int(p, 2, on_t.account, 8);
    p = put_bytes(p, 4, handle, 32);
    p = put_bytes(p, 8, region, 4);
    p = put_bytes(p, 4, domain, 4);
    p = put_bytes(p, 8, on_t.service, 24);
    p = put_int(p, 1, 0, 4);
    p = put_head(p, 0, 0);
    p = put_head(p, 0, 0);
    int body_size = p - body;
    p = put_bytes(foot, 8, key, 4);
    p = put_bytes(p, 8, signature, 56);
    int foot_size = p - foot;

    unsigned char* o = on_t.raw;
    *o++ = 0x21; *o++ = 0x01; *o++ = 0; *o++ = 0;
    o = put16(o, 0);
    o = put16(o, 4 + body_size + 4 + foot_size);
    o = put_bytes(o, 0x3000, body, body_size);
    o = put_bytes(o, 0x3002, foot, foot_size);
    on_t.size = o - on_t.raw;
}

extern "C" void on_register_callback(ppu_context* c)
{
    on_cb = (unsigned)c->gpr[3]; on_cb_arg = (unsigned)c->gpr[4];
    ps3_hle_call(0xE7DCD3B4u, c);
}

// The game's request sets its "waiting" marks after this returns, and its callback takes the lock the caller holds: the answer waits for
// the next cellSysutilCheckCallback, as on RPCS3.
extern "C" void on_request_ticket(ppu_context* c)
{
    char name[17] = {0};
    for (int i = 0; i < 16 && c->gpr[3]; i++) name[i] = vm_read8((unsigned)c->gpr[3] + i);
    make_ticket(name, (unsigned)c->gpr[5]);
    nhl_log("ticket for %s, account %llx, %d bytes", on_t.name, on_t.account, on_t.size);
    on_pending = 1;
    c->gpr[3] = 0;
}

extern "C" void on_check_callback(ppu_context* c)
{
    ps3_hle_call(0x189A74DAu, c);
    if (!on_pending || !on_cb) return;
    on_pending = 0;
    unsigned long long r1 = c->gpr[1], r2 = c->gpr[2], lr = c->lr, ctr = c->ctr, r3 = c->gpr[3];
    c->gpr[1] = (r1 - 0x100) & ~15ull;
    vm_write64(c->gpr[1], r1);
    c->gpr[3] = GOT_TICKET; c->gpr[4] = on_t.size; c->gpr[5] = on_cb_arg;
    c->gpr[2] = vm_read32(on_cb + 4);
    c->ctr = vm_read32(on_cb);
    ps3_indirect_call(c);
    DRAIN_TRAMPOLINE(c);
    c->gpr[1] = r1; c->gpr[2] = r2; c->lr = lr; c->ctr = ctr; c->gpr[3] = r3;
}

extern "C" void on_get_ticket(ppu_context* c)
{
    unsigned buffer = (unsigned)c->gpr[3], size = (unsigned)c->gpr[4];
    if (!size) { c->gpr[3] = (long long)BAD_ARGUMENT; return; }
    unsigned room = vm_read32(size);
    vm_write32(size, on_t.size);
    if (buffer) {
        if (room < (unsigned)on_t.size) { c->gpr[3] = (long long)BAD_ARGUMENT; return; }
        for (int i = 0; i < on_t.size; i++) vm_write8(buffer + i, on_t.raw[i]);
    }
    c->gpr[3] = 0;
}

extern "C" void on_get_ticket_param(ppu_context* c)
{
    int id = (int)c->gpr[3];
    unsigned out = (unsigned)c->gpr[4];
    const void* d = nullptr; int n = 0;
    switch (id) {
    case 0: d = on_t.serial; n = 20; break;
    case 1: vm_write32(out, 0x100); break;
    case 2: vm_write64(out, on_t.issued); break;
    case 3: vm_write64(out, on_t.expires); break;
    case 4: vm_write64(out, on_t.account); break;
    case 5: d = on_t.name; n = 17; break;
    case 6: d = "us\0\1"; n = 4; break;
    case 7: d = "un\0"; n = 4; break;
    case 8: d = on_t.service; n = 24; break;
    case 9: vm_write32(out, 0); break;
    default: c->gpr[3] = (long long)BAD_ARGUMENT; return;
    }
    for (int i = 0; i < n; i++) vm_write8(out + i, ((const unsigned char*)d)[i]);
    c->gpr[3] = 0;
}

extern "C" void on_get_network_time(ppu_context* c)
{
    vm_write64((unsigned)c->gpr[3], nhl_now_ms() * 1000 + RTC_EPOCH_US);
    c->gpr[3] = 0;
}

extern "C" void on_get_account_region(ppu_context* c)
{
    unsigned country = (unsigned)c->gpr[3], language = (unsigned)c->gpr[4];
    if (country) { vm_write8(country, 'u'); vm_write8(country + 1, 's'); vm_write8(country + 2, 0); vm_write8(country + 3, 0); }
    if (language) vm_write32(language, 1);
    c->gpr[3] = 0;
}
