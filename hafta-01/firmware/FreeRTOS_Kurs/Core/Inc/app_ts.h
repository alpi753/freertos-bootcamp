/**
 * @file    app_ts.h
 * @brief   Zaman damgası: TIM2, 1 MHz, 32-bit serbest sayaç (tasarım §4).
 *
 * 1 tık = 1 µs, taşma 2^32 µs ≈ 71,6 dk.
 * Aralıklar HER ZAMAN ts_elapsed() ile (işaretsiz çıkarma) hesaplanır;
 * böylece sayaç iki damga arasında bir kez taşsa bile sonuç doğrudur.
 *
 * Saf fonksiyonlar (ts_elapsed, debounce_accept) donanıma bağlı değildir
 * ve PC'de birim testiyle sınanır (tests_host, TC-U03/U04).
 */
#ifndef APP_TS_H
#define APP_TS_H

#include <stdint.h>
#include <stdbool.h>

#ifndef UNIT_TEST
#include "stm32l4xx.h"
/** Şu anki zaman damgası [µs]. Tek bir 32-bit okuma (TIM-04). */
static inline uint32_t ts_now(void) { return TIM2->CNT; }
#endif

/** t_start → t_end arası geçen süre [µs]; tek taşmaya dayanıklı (TIM-01). */
static inline uint32_t ts_elapsed(uint32_t t_start, uint32_t t_end)
{
    return (uint32_t)(t_end - t_start);
}

/* ---- Debounce (ISR-03) ------------------------------------------------- */
#define DEBOUNCE_US  50000u

typedef struct {
    uint32_t last_accept;   /* son kabul edilen kenarın zamanı (t₀) */
    bool     has_last;      /* açılıştan beri kabul edilen kenar var mı */
} debounce_t;

/**
 * Kenar kabul edilsin mi? Son kabulden bu yana >= DEBOUNCE_US geçtiyse evet.
 * Kabul edilirse durum güncellenir; reddedilirse değişmez.
 * İlk kenar her zaman kabul edilir.
 */
bool debounce_accept(debounce_t *d, uint32_t now);

#ifndef UNIT_TEST
/** DWT çevrim sayacını açar (12,5 ns çözünürlük; öz-testler ve kanca ek yükü için). */
void ts_dwt_init(void);
#endif

#endif /* APP_TS_H */
