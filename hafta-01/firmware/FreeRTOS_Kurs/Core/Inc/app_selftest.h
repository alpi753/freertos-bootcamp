/**
 * @file    app_selftest.h
 * @brief   Açılış öz-testleri: TC-T19 (sayaç frekansı) ve TC-T20 (damga ek yükü).
 *
 * Sonuçlar g_selftest'e yazılır. UART hazır olana kadar (adım 4) CubeIDE
 * Debug → Live Expressions penceresinde "g_selftest" yazılarak okunur.
 */
#ifndef APP_SELFTEST_H
#define APP_SELFTEST_H

#include <stdint.h>

typedef struct {
    uint32_t done;              /* 1 = testler bitti */
    /* T19: vTaskDelay(1000 ms) boyunca TIM2'nin saydığı µs.
     * Geçme: 999 000 … 1 001 000 (±1 tick) → TIM2 gerçekten 1 MHz. */
    uint32_t t19_tim2_1s_us;
    uint32_t t19_pass;
    /* T20: ts_now() + RAM yazması, 1000 tekrarın ortalaması (DWT ile ölçülür).
     * Geçme: <= 1000 ns (80 çevrim @ 80 MHz). Döngü yükü de dahil (kötümser ölçüm). */
    uint32_t t20_cycles_x100;   /* ortalama çevrim × 100 */
    uint32_t t20_ns;            /* ortalama süre [ns] */
    uint32_t t20_pass;
} app_selftest_t;

extern volatile app_selftest_t g_selftest;

/** Görev bağlamında çağrılmalı (vTaskDelay kullanır). */
void app_selftest_run(void);

#endif /* APP_SELFTEST_H */
