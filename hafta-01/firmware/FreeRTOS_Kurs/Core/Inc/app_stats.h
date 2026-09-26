/**
 * @file    app_stats.h
 * @brief   Koşu başına görev çalışma süreleri (TIM-06) ve bellek payı (SYS-04).
 *
 * FreeRTOS görev çalışma sayaçlarını açılıştan beri biriktirir ve sıfırlayamaz.
 * Bu yüzden START ve STOP'ta birer anlık görüntü alınır; RTS çerçeveleri ikisinin
 * farkıdır (tasarım §6). uxTaskGetSystemState scheduler'ı kısa süre durdurur;
 * yalnızca koşu dışında (komut işlenirken) çağrılır.
 */
#ifndef APP_STATS_H
#define APP_STATS_H

#include <stdint.h>
#include <stdbool.h>

#define STATS_MAX_TASKS  8u

typedef struct {
    const char *name;
    uint32_t    run_us;     /* koşu boyunca CPU süresi */
    uint16_t    pct_x10;    /* koşu süresinin binde kaçı */
} stats_task_t;

void     stats_snapshot_start(void);
void     stats_snapshot_stop(void);
/** i. görevin koşu istatistiği (i < görev sayısı ise true). */
bool     stats_task(uint32_t i, stats_task_t *out);

/** MEM: en düşük boş heap [bayt] ve görevlerin hiç kullanılmamış stack'i [word]. */
uint32_t stats_min_free_heap(void);
uint16_t stats_stack_hw_words(void *task_handle);

#endif /* APP_STATS_H */
