/* TC-U03 (debounce) ve TC-U04 (aralık aritmetiği / taşma) */
#include "unit.h"
#include "app_ts.h"

static void u04_elapsed(void)
{
    CHECK_EQ_U(ts_elapsed(100u, 350u), 250u);                 /* normal */
    CHECK_EQ_U(ts_elapsed(0xFFFFFF00u, 0x00000010u), 0x110u); /* sayaç taştı */
    CHECK_EQ_U(ts_elapsed(0xFFFFFFFFu, 0u), 1u);              /* tam taşma sınırı */
    CHECK_EQ_U(ts_elapsed(5u, 5u), 0u);
}

static void u03_debounce(void)
{
    debounce_t d = {0};
    CHECK(debounce_accept(&d, 1000u));                /* ilk kenar: kabul (açılışa yakın olsa bile) */
    CHECK(!debounce_accept(&d, 1000u + 0u));          /* aynı an: red */
    CHECK(!debounce_accept(&d, 1000u + 49999u));      /* 49 999 µs: red */
    CHECK(debounce_accept(&d, 1000u + 50000u));       /* 50 000 µs: kabul (sınır dahil) */
    CHECK_EQ_U(d.last_accept, 51000u);
    CHECK(!debounce_accept(&d, 51000u + 1u));         /* red, durum DEĞİŞMEMELİ */
    CHECK_EQ_U(d.last_accept, 51000u);
    CHECK(debounce_accept(&d, 51000u + 50001u));      /* 50 001 µs: kabul */

    /* Sayaç taşmasına denk gelen aralık */
    debounce_t w = { .last_accept = 0xFFFFF000u, .has_last = true };
    CHECK(!debounce_accept(&w, 0x00000100u));         /* aradaki fark 4352 µs: red */
    CHECK(debounce_accept(&w, 0xFFFFF000u + 50000u)); /* taşmış hâliyle 50 000 µs: kabul */
}

void test_ts_all(void)
{
    run_case("U03", "debounce karari (sinir + tasma)", u03_debounce);
    run_case("U04", "aralik aritmetigi (tasma)", u04_elapsed);
}
