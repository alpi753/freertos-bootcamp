/**
 * @file    app_stats.c
 * @brief   Run-time stats farkı (TIM-06) ve bellek ölçümleri (SYS-04).
 */
#include <string.h>
#include "app_stats.h"
#include "FreeRTOS.h"
#include "task.h"

typedef struct { TaskHandle_t h; const char *name; uint32_t counter; } snap_t;

static snap_t   s_start[STATS_MAX_TASKS], s_stop[STATS_MAX_TASKS];
static uint32_t s_n_start, s_n_stop;
static uint32_t s_total_start, s_total_stop;
static TaskStatus_t s_tmp[STATS_MAX_TASKS];

static uint32_t take(snap_t *dst, uint32_t *total)
{
    uint32_t tot = 0;
    const UBaseType_t n = uxTaskGetSystemState(s_tmp, STATS_MAX_TASKS, &tot);
    for (UBaseType_t i = 0; i < n; i++) {
        dst[i].h = s_tmp[i].xHandle;
        dst[i].name = s_tmp[i].pcTaskName;
        dst[i].counter = s_tmp[i].ulRunTimeCounter;
    }
    *total = tot;
    return (uint32_t)n;
}

void stats_snapshot_start(void) { s_n_start = take(s_start, &s_total_start); s_n_stop = 0; }
void stats_snapshot_stop(void)  { s_n_stop  = take(s_stop,  &s_total_stop); }

bool stats_task(uint32_t i, stats_task_t *out)
{
    if (i >= s_n_stop) return false;
    uint32_t before = 0;
    for (uint32_t k = 0; k < s_n_start; k++) {
        if (s_start[k].h == s_stop[i].h) { before = s_start[k].counter; break; }
    }
    const uint32_t total = s_total_stop - s_total_start;           /* TIM2 µs; işaretsiz fark */
    out->name    = s_stop[i].name;
    out->run_us  = s_stop[i].counter - before;
    out->pct_x10 = total ? (uint16_t)(((uint64_t)out->run_us * 1000u) / total) : 0u;
    return true;
}

uint32_t stats_min_free_heap(void) { return (uint32_t)xPortGetMinimumEverFreeHeapSize(); }

uint16_t stats_stack_hw_words(void *h)
{
    return (uint16_t)uxTaskGetStackHighWaterMark((TaskHandle_t)h);
}
