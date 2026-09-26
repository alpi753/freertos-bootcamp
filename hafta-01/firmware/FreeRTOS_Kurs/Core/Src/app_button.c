/**
 * @file    app_button.c
 * @brief   Buton kesmesi ve ButtonTask (orta öncelik) — tasarım §7.1, §7.3.
 *
 * ISR: yalnızca t₀ + debounce + bildirim (ISR-02). Biçimlendirme/UART yok.
 * ButtonTask: bildirimle uyanır, BTN çerçevesini üretir ve TX kuyruğuna bırakır.
 * Buton HER durumda algılanır (TSK-05a); koşu dışındaki basışlarda event_id = 0.
 *
 * Ölçüm: t₀ ISR'da (meas_event_begin), t₁ ve t₂ ButtonTask'ta (tasarım §7.3).
 */
#include "main.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "app_tasks.h"
#include "app_config.h"
#include "app_ts.h"
#include "app_msg.h"
#include "app_run.h"
#include "app_button.h"
#include "app_meas.h"

volatile uint32_t   g_exti_ts;
volatile btn_diag_t g_btn_diag;
volatile uint32_t   g_isr_c0;

static TaskHandle_t      s_btn_task;
static debounce_t        s_debounce;
/* ISR → ButtonTask aktarımı. Debounce iki olay arasında ≥ 50 ms bıraktığı için
 * tek slot yeter; yetmezse overrun sayılır. */
static volatile uint16_t s_pending_id;
static volatile uint8_t  s_pending_scn;

/* ---- ISR (EXTI15_10 → HAL → burası) ------------------------------------ */
void HAL_GPIO_EXTI_Callback(uint16_t pin)
{
    if (pin != B1_Pin) return;

    const uint32_t t0 = g_exti_ts;              /* handler'ın ilk satırında alındı */
    if (!debounce_accept(&s_debounce, t0)) {
        g_cnt.bounce_rej++;                     /* sıçrama: bildirim yok (ISR-03) */
        return;
    }
    g_btn_diag.accepted++;

    /* Koşudaysa olay numarası ver ve kaydı aç; değilse 0, kayıt yok (TSK-05a). */
    s_pending_scn = g_run_scn;
    s_pending_id  = run_is_running() ? meas_event_begin(t0, s_pending_scn) : 0u;

    if (s_btn_task == NULL) return;             /* görev henüz başlamadı (açılış) */
    BaseType_t hpw = pdFALSE;
    vTaskNotifyGiveFromISR(s_btn_task, &hpw);
    portYIELD_FROM_ISR(hpw);                    /* ButtonTask'ı hemen Ready yap */
}

/* ---- ButtonTask -------------------------------------------------------- */
void StartButtonTask(void *argument)
{
    (void)argument;
    APP_SET_OWN_TAG(APP_TAG_BUTTON);
    s_btn_task = xTaskGetCurrentTaskHandle();

    for (;;) {
        const uint32_t n  = ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        const uint32_t t1 = ts_now();          /* t₁: olayı aldıktan hemen sonra */
        if (n > 1u) g_btn_diag.overrun += n - 1u;

        const uint16_t id  = s_pending_id;
        const uint8_t  scn = s_pending_scn;
        meas_stamp(id, 1, t1);

        tx_item_t it = { .type = MSG_BTN, .scn = scn, .event_id = id };
        if (!frame_build(it.frame, FMT_BTN, (unsigned)id, (unsigned)scn)) {
            continue;
        }
        /* Sınırlı zaman aşımı: yazılamazsa olay sessizce kaybolmaz (QUE-03). */
        meas_stamp(id, 2, ts_now());           /* t₂: xQueueSend'den hemen önce */
        if (xQueueSend(g_txq, &it, pdMS_TO_TICKS(BTN_SEND_TIMEOUT_MS)) == pdPASS) {
            run_qhw_update();
        } else {
            g_cnt.btn_dropped++;
            meas_mark_lost(id);                /* zincir t₂'de biter (TIM-02a) */
        }
    }
}
