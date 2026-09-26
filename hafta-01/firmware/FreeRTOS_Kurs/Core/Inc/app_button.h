/**
 * @file    app_button.h
 * @brief   Buton kesmesi (t₀, debounce) ve ButtonTask — tasarım §7.1, §7.3.
 */
#ifndef APP_BUTTON_H
#define APP_BUTTON_H

#include <stdint.h>

/** EXTI15_10_IRQHandler'ın İLK satırında yazılır: t₀ adayı (HAL'den önce). */
extern volatile uint32_t g_exti_ts;

/* Tanılama değerleri: CubeIDE Live Expressions'da "g_btn_diag" (TC-T09). */
typedef struct {
    uint32_t isr_last_cycles;   /* EXTI kesmesinin son süresi [çevrim] */
    uint32_t isr_max_cycles;    /* en uzun süresi [çevrim]; 80 çevrim = 1 µs */
    uint32_t isr_max_ns;        /* isr_max_cycles, ns cinsinden (ölçüt ≤ 5000) */
    uint32_t isr_count;         /* toplam EXTI kesmesi (sıçramalar dahil) */
    uint32_t accepted;          /* debounce'tan geçen kenar */
    uint32_t overrun;           /* ButtonTask bir olayı işlemeden yenisi geldi */
} btn_diag_t;
extern volatile btn_diag_t g_btn_diag;

/* EXTI kesmesinin süresini ölçen makrolar (stm32l4xx_it.c; TC-T09).
 * Her derlemede açık: iki DWT okuması + bir karşılaştırma (~10 çevrim), ölçülen
 * yolu belirgin etkilemez. Release'te de açık olması gerekir, çünkü ISR-04
 * ölçütü ölçüm derlemesi olan Release'te değerlendirilir.
 * Ölçüm handler'ın ilk ve son satırı arasıdır; donanımın kesmeye girip
 * çıkarken harcadığı ~12+12 çevrim dahil değildir. */
extern volatile uint32_t g_isr_c0;
#define APP_EXTI_TIMING_BEGIN()  do { g_isr_c0 = DWT->CYCCNT; } while (0)
#define APP_EXTI_TIMING_END()    do { uint32_t _c = DWT->CYCCNT - g_isr_c0;              \
        g_btn_diag.isr_last_cycles = _c; g_btn_diag.isr_count++;                         \
        if (_c > g_btn_diag.isr_max_cycles) { g_btn_diag.isr_max_cycles = _c;            \
            g_btn_diag.isr_max_ns = (_c * 25u) / 2u; } } while (0)   /* 12,5 ns/çevrim */

#endif /* APP_BUTTON_H */
