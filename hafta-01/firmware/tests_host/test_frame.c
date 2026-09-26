/* TC-U01 (frame_build) ve TC-U06 (en uzun çerçeveler) */
#include <string.h>
#include "unit.h"
#include "app_frame.h"

static char body[128];

/* n karakterlik içerik üret: "AAAA..." */
static const char *content(unsigned n) { memset(body, 'A', n); body[n] = 0; return body; }

static int frame_ok(const char *f, unsigned content_len)
{
    if (f[FRAME_LEN - 1] != '\n') return 0;
    for (unsigned i = content_len; i < FRAME_PAYLOAD; i++) if (f[i] != ' ') return 0;
    for (unsigned i = 0; i < FRAME_LEN - 1; i++) if (f[i] == '\n' || f[i] == 0) return 0;
    return 1;
}

static void u01_frame_build(void)
{
    char f[FRAME_LEN];
    const unsigned ok_lens[] = {0, 1, 62, 63};
    for (unsigned i = 0; i < 4; i++) {
        memset(f, '#', sizeof f);
        CHECK(frame_build(f, "%s", content(ok_lens[i])));
        CHECK(frame_ok(f, ok_lens[i]));
        CHECK(memcmp(f, body, ok_lens[i]) == 0);
    }

    const unsigned bad_lens[] = {64, 70};
    for (unsigned i = 0; i < 2; i++) {
        uint32_t err0 = g_frame_err;
        memset(f, '#', sizeof f);
        CHECK(!frame_build(f, "%s", content(bad_lens[i])));   /* kesilmez, reddedilir */
        CHECK_EQ_U(g_frame_err, err0 + 1);                    /* sayılır */
        int untouched = 1;
        for (unsigned k = 0; k < FRAME_LEN; k++) if (f[k] != '#') untouched = 0;
        CHECK(untouched);                                     /* çıktı tamponu bozulmaz */
    }

    /* Gerçek bir TEL örneği */
    CHECK(frame_build(f, FMT_TEL, (uint32_t)1042, 3u, 263));
    CHECK(memcmp(f, "TEL,1042,S3,263 ", 16) == 0 && frame_ok(f, 15));
}

/* Her biçim, alanlarının EN BÜYÜK değerleriyle 63 karaktere sığmalı. */
static void u06_longest_frames(void)
{
    char f[FRAME_LEN];
    const uint32_t U32 = 4294967295u, D = REC_DELTA_MAX;
    const unsigned U16 = 65535u, U8 = 255u;

    CHECK(frame_build(f, FMT_TEL, U32, 5u, -32768));
    CHECK(frame_build(f, FMT_BTN, U16, 5u));
    CHECK(frame_build(f, FMT_VER, "0123456789+", "Release", 0xFFu));   /* uzun hash + kirli işareti */
    CHECK(frame_build(f, FMT_REC, U16, 5u, U32, D, D, D, D, 1u));
    CHECK(frame_build(f, FMT_PRE, U16, D, 'T', D, U8, D, U8, D));
    CHECK(frame_build(f, FMT_SUM, 5u, U16, U32, U32, U16, U8, U16, U16, U16));
    CHECK(frame_build(f, FMT_CAL, U16, U32, U32, U32, U32));
    CHECK(frame_build(f, FMT_MEM, U32, U16, U16, U16));
    CHECK(frame_build(f, FMT_RTS, "ABCDEFGHIJKLMNO", U32, 1000u));      /* 15 karakter görev adı */
}

void test_frame_all(void)
{
    run_case("U01", "frame_build: 64 B, dolgu, LF, kesmeme", u01_frame_build);
    run_case("U06", "en uzun cerceveler <= 63 karakter", u06_longest_frames);
}
