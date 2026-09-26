/**
 * @file    app_selftest.c
 * @brief   Açılış öz-testleri (test planı §6.2: T19, T20).
 */
#include "app_selftest.h"
#include "app_ts.h"
#include "FreeRTOS.h"
#include "task.h"

volatile app_selftest_t g_selftest;

#define T20_N  1000u

void app_selftest_run(void)
{
    /* --- T19: TIM2 frekansı. Referans: FreeRTOS tick'i (1 kHz, SysTick). */
    vTaskDelay(1);                              /* bir tick sınırına hizalan */
    uint32_t a = ts_now();
    vTaskDelay(pdMS_TO_TICKS(1000));
    uint32_t us = ts_elapsed(a, ts_now());
    g_selftest.t19_tim2_1s_us = us;
    g_selftest.t19_pass = (us >= 999000u && us <= 1001000u);

    /* --- T20: damga maliyeti. Kesmeler kapalı: ölçüm sırasında araya kimse girmesin. */
    static volatile uint32_t sink[16] __attribute__((unused));   /* derleyici döngüyü silmesin diye */
    taskDISABLE_INTERRUPTS();
    uint32_t c0 = DWT->CYCCNT;
    for (uint32_t i = 0; i < T20_N; i++) {
        sink[i & 15u] = ts_now();
    }
    uint32_t cycles = DWT->CYCCNT - c0;
    taskENABLE_INTERRUPTS();

    g_selftest.t20_cycles_x100 = cycles / (T20_N / 100u);
    /* ns = çevrim × (1e9 / SystemCoreClock); 80 MHz'de 12,5 ns/çevrim */
    g_selftest.t20_ns = (uint32_t)(((uint64_t)cycles * 1000000000ull) / ((uint64_t)SystemCoreClock * T20_N));
    g_selftest.t20_pass = (g_selftest.t20_ns <= 1000u);

    g_selftest.done = 1;
}
