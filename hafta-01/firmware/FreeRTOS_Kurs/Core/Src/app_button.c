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
#if TEST_STACK_OVF == 1
/* TC-T18a — BÜYÜK taşma: ButtonTask stack'i 1 KB; 1 KB'lık yerel dizi onu, görevin
 * o an kullandığı kadar aşar ve stack'in hemen altındaki TCB'nin üzerine yazar.
 * AYRI ve noinline fonksiyon: derleyici yerel değişkenlerin yerini fonksiyon
 * GİRİŞİNDE ayırır. volatile öğelere tek tek yazılır: yoksa -Os diziyi siler.
 * Gözlenen (2026-09-26): FreeRTOS kontrolüne varmadan HardFault (bulgu B-02). */
static void __attribute__((noinline)) overflow_stack(void)
{
    volatile uint8_t big[1024];
    for (uint32_t i = 0; i < sizeof big; i++) {
        big[i] = (uint8_t)i;
    }
}
#elif TEST_STACK_OVF == 2
/* TC-T18b — KÜÇÜK taşma: özyinelemeyle stack gerçekten tüketilir, stack tabanına
 * 64 bayt kalınca kalan bölge taban+4'e kadar doldurulur. Böylece FreeRTOS'un
 * dipteki 16 baytlık koruma deseni (yöntem 2) bozulur ama TCB'ye dokunulmaz.
 * Bir sonraki görev değişiminde vApplicationStackOverflowHook → LD2 10 Hz (SYS-05). */
static void __attribute__((noinline)) eat_stack(uint8_t *base)
{
    volatile uint32_t pad[4];
    pad[0] = (uint32_t)(uintptr_t)&pad[0];
    if ((uint32_t)((uint8_t *)&pad[0] - base) > 64u) {
        eat_stack(base);
    } else {
        for (volatile uint8_t *p = (uint8_t *)&pad[0] - 1; p >= base + 4; p--) {
            *p = 0;
        }
    }
    pad[1] = pad[0];              /* çağrıdan sonra iş: kuyruk-çağrı optimizasyonunu engeller */
}

static void __attribute__((noinline)) overflow_stack(void)
{
    TaskStatus_t st;
    vTaskGetInfo(NULL, &st, pdFALSE, eRunning);
    eat_stack((uint8_t *)st.pxStackBase);
}
#endif

void StartButtonTask(void *argument)
{
    (void)argument;
    APP_SET_OWN_TAG(APP_TAG_BUTTON);
    s_btn_task = xTaskGetCurrentTaskHandle();

    for (;;) {
        const uint32_t n  = ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        const uint32_t t1 = ts_now();          /* t₁: olayı aldıktan hemen sonra */
        if (n > 1u) g_btn_diag.overrun += n - 1u;

#if TEST_STACK_OVF
        overflow_stack();                      /* TC-T18: yalnızca basışta */
#endif
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
