/**
 * @file    app_ts.c
 * @brief   Zaman damgası yardımcıları ve FreeRTOS run-time stats saati (tasarım §4).
 */
#include "app_ts.h"

bool debounce_accept(debounce_t *d, uint32_t now)
{
    if (d->has_last && ts_elapsed(d->last_accept, now) < DEBOUNCE_US) {
        return false;                       /* sıçrama: yok say */
    }
    d->last_accept = now;
    d->has_last    = true;
    return true;
}

#ifndef UNIT_TEST
void ts_dwt_init(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;   /* DWT'ye erişimi aç */
    DWT->CYCCNT = 0;
    DWT->CTRL  |= DWT_CTRL_CYCCNTENA_Msk;             /* çevrim sayacını başlat */
}

/* freertos.c'deki __weak tanımların yerine geçer (configGENERATE_RUN_TIME_STATS).
 * TIM2 main() içinde, scheduler başlamadan önce çalıştırıldı. */
void configureTimerForRunTimeStats(void)
{
}

unsigned long getRunTimeCounterValue(void)
{
    return ts_now();
}
#endif
