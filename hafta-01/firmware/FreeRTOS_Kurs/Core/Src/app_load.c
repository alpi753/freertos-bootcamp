/**
 * @file    app_load.c
 * @brief   Kalibre edilmiş CPU yükü (TSK-03).
 */
#include "app_load.h"
#include "main.h"
#include "FreeRTOS.h"
#include "task.h"

volatile uint32_t g_load_sink = 0x12345678u;   /* derleyici döngüyü silmesin */
static uint32_t   s_iters_per_ms;

static void work(uint32_t n)
{
    uint32_t x = g_load_sink | 1u;
    for (uint32_t i = 0; i < n; i++) {           /* xorshift32: saf aritmetik, bellek yok */
        x ^= x << 13; x ^= x >> 17; x ^= x << 5;
    }
    g_load_sink = x;
}

void cpu_load_calibrate(void)
{
    enum { N = 20000 };
    work(100);                                   /* önbelleği ısıt */
    taskDISABLE_INTERRUPTS();
    const uint32_t c0 = DWT->CYCCNT;
    work(N);
    const uint32_t cycles = DWT->CYCCNT - c0;
    taskENABLE_INTERRUPTS();
    /* tur/ms = N × (çevrim/ms) / çevrim */
    s_iters_per_ms = (uint32_t)(((uint64_t)N * (SystemCoreClock / 1000u)) / cycles);
}

void cpu_load_run(uint32_t target_us)
{
    work((uint32_t)(((uint64_t)target_us * s_iters_per_ms) / 1000u));
}

uint32_t cpu_load_iters_per_ms(void) { return s_iters_per_ms; }
