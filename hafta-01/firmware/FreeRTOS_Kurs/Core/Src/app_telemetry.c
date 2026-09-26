/**
 * @file    app_telemetry.c
 * @brief   TelemetryTask (en yüksek öncelik) — tasarım §7.2.
 *
 * Koşu RUNNING iken seçili senaryonun periyodunda uyanır, sıcaklığı okur,
 * bir TEL çerçevesi üretir ve TX kuyruğuna zaman aşımı 0 ile bırakır.
 * Kuyruk doluysa çerçeveyi düşürür ve sayar; ASLA bloklanmaz (QUE-02).
 *
 * S4/S5'te her periyotta kalibre edilmiş CPU işi yapılır (TSK-03); ADC ve CPU
 * işinin gerçek süreleri ölçülür ve CAL çerçevesinde raporlanır.
 */
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "app_tasks.h"
#include "app_config.h"
#include "app_msg.h"
#include "app_run.h"
#include "app_temp.h"
#include "app_load.h"
#include "app_ts.h"

void StartTelemetryTask(void *argument)
{
    (void)argument;
    APP_SET_OWN_TAG(APP_TAG_TELEMETRY);
    run_register_telemetry(xTaskGetCurrentTaskHandle());
    temp_init();

    for (;;) {
        /* START gelene kadar CPU harcamadan bekle (TSK-04: S0'da da burada kalır). */
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);

        const uint32_t run_id = g_run_id;
        const uint8_t  scn    = g_run_scn;
        const uint16_t period = SCN_TABLE[scn].period_ms;
        if (period == 0u || !run_is_running()) {
            continue;                                   /* S0: telemetri kapalı */
        }

        TickType_t last = xTaskGetTickCount();
        uint32_t   seq  = 0;                            /* her koşuda 0'dan (TSK-02) */

        for (;;) {
            /* Mutlak periyot: iş süresi periyoda eklenmez (TSK-01). */
            vTaskDelayUntil(&last, pdMS_TO_TICKS(period));
            if (!run_is_running() || g_run_id != run_id) {
                break;                                  /* STOP geldi veya yeni koşu başladı */
            }

            uint32_t a = ts_now();
            const int16_t t_x10 = temp_read_x10();
            g_cnt.adc_sum_us += ts_elapsed(a, ts_now());
            g_cnt.adc_n++;

            const uint16_t load_us = SCN_TABLE[scn].load_us;
            if (load_us) {                              /* S4/S5: ≈2 / ≈5 ms gerçek hesap */
                a = ts_now();
                cpu_load_run(load_us);
                const uint32_t d = ts_elapsed(a, ts_now());
                g_cnt.load_sum_us += d;
                g_cnt.load_n++;
                if (d > g_cnt.load_max_us) g_cnt.load_max_us = d;
            }

            tx_item_t it = { .type = MSG_TEL, .scn = scn, .event_id = 0 };
            if (!frame_build(it.frame, FMT_TEL, seq, (unsigned)scn, (int)t_x10)) {
                continue;                               /* g_frame_err zaten sayıldı */
            }
            seq++;   /* üretim sayacı: düşürülen çerçeve de numara tüketir → PC boşluğu görür */

            if (xQueueSend(g_txq, &it, 0) == pdPASS) {
                g_cnt.tel_sent++;
                run_qhw_update();
            } else {
                g_cnt.tel_dropped++;
            }
        }
    }
}
