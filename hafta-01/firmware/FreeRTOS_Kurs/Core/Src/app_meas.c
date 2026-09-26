/**
 * @file    app_meas.c
 * @brief   t₀…t₄ ölçüm kayıtları ve görev değişimi muhasebesi — tasarım §8.
 *
 * Çekirdek saf C'dir (PC'de test edilir). Yalnızca en alttaki #ifndef UNIT_TEST
 * bölümü donanıma (TIM2, DWT) ve FreeRTOS'a dokunur.
 */
#include <string.h>
#include "app_meas.h"
#include "app_ts.h"
#include "app_frame.h"

#ifndef UNIT_TEST
#include "FreeRTOS.h"
#include "task.h"
/* Görevden VE kesmeden güvenle çağrılabilen kısa kritik bölge: FreeRTOS API'si
 * kullanan kesmeleri (öncelik ≥ 5) ve PendSV'yi (görev değişimi) maskeler. */
#define MEAS_LOCK()      UBaseType_t _m = portSET_INTERRUPT_MASK_FROM_ISR()
#define MEAS_UNLOCK()    portCLEAR_INTERRUPT_MASK_FROM_ISR(_m)
#else
#define MEAS_LOCK()      do { } while (0)
#define MEAS_UNLOCK()    do { } while (0)
#endif

#define TAG_OTHER  0u
#define TAG_BUTTON 2u
#define TAG_UART   3u

static meas_rec_t        s_rec[MEAS_CAP];      /* statik RAM (heap değil) */
static volatile uint16_t s_events;
static volatile uint16_t s_overflow;

/* ---- Pencereler (kancalar PendSV'de okur/yazar) ------------------------- */
static struct {
    uint8_t  any;             /* herhangi bir pencere açık mı (hızlı çıkış) */
    /* READY: t₀ → t₁ */
    uint8_t  rw_on;  uint16_t rw_id;
    uint32_t rw_acc[4];       /* görev tag'i başına CPU süresi */
    uint32_t cur_in;          /* şu an koşan görevin (pencere içinde) giriş zamanı */
    /* BTN_EXEC: t₁ → t₂ */
    uint8_t  bt_on;  uint16_t bt_id;
    uint8_t  bt_running, bt_out, bt_n;
    uint32_t bt_seg, bt_exec, bt_pre, bt_out_at;
    /* TX_WAIT: t₂ → t₃ */
    uint8_t  tx_on;  uint16_t tx_id;
    uint8_t  tx_out, tx_n;
    uint32_t tx_pre, tx_out_at;
} W;

static void w_update_any(void) { W.any = (uint8_t)(W.rw_on | W.bt_on | W.tx_on); }
static uint8_t sat8(uint32_t v) { return v > 255u ? 255u : (uint8_t)v; }

void meas_reset(void)
{
    MEAS_LOCK();
    memset((void *)s_rec, 0, sizeof s_rec);
    memset(&W, 0, sizeof W);
    s_events = 0;
    s_overflow = 0;
    MEAS_UNLOCK();
}

static meas_rec_t *rec_of(uint16_t id)
{
    return (id == 0u || id > MEAS_CAP) ? 0 : &s_rec[id - 1u];
}

uint16_t meas_event_begin(uint32_t t0, uint8_t scn)
{
    MEAS_LOCK();
    const uint16_t id = (uint16_t)(s_events + 1u);
    s_events = id;
    meas_rec_t *r = rec_of(id);
    if (r == 0) {
        s_overflow++;                       /* TIM-03: say ama kaydetme */
    } else {
        r->event_id = id; r->scn = scn; r->lost_queue = 0;
        r->t[0] = t0; r->have = MEAS_HAVE_T0;
        /* READY penceresini aç: şu an koşan görev t₀'dan itibaren sayılır */
        W.rw_on = 1; W.rw_id = id; memset(W.rw_acc, 0, sizeof W.rw_acc);
        W.cur_in = t0;
        w_update_any();
    }
    MEAS_UNLOCK();
    return id;
}

/* Pencere geçişleri: damga alınırken çağrılır (MEAS_LOCK içinde). */
static void w_at_t1(meas_rec_t *r, uint16_t id, uint32_t t1)
{
    if (W.rw_on && W.rw_id == id) {
        uint32_t sum = 0, best = 0; uint8_t best_tag = TAG_OTHER;
        for (uint8_t k = 0; k < 4u; k++) {
            if (k == TAG_BUTTON) continue;
            sum += W.rw_acc[k];
            if (W.rw_acc[k] > best) { best = W.rw_acc[k]; best_tag = k; }
        }
        r->ready_wait_us = sum; r->ready_wait_tag = best_tag;
        W.rw_on = 0;
    }
    /* BTN_EXEC penceresi: ButtonTask şu an koşuyor */
    W.bt_on = 1; W.bt_id = id; W.bt_running = 1; W.bt_out = 0; W.bt_n = 0;
    W.bt_seg = t1; W.bt_exec = 0; W.bt_pre = 0;
    W.cur_in = t1;
    w_update_any();
}

static void w_at_t2(meas_rec_t *r, uint16_t id, uint32_t t2)
{
    if (W.bt_on && W.bt_id == id) {
        if (W.bt_running) W.bt_exec += ts_elapsed(W.bt_seg, t2);
        r->bt_exec_us = W.bt_exec; r->bt_pre_us = W.bt_pre; r->bt_n_pre = W.bt_n;
        W.bt_on = 0;
    }
    W.tx_on = 1; W.tx_id = id; W.tx_out = 0; W.tx_n = 0; W.tx_pre = 0;
    w_update_any();
}

static void w_at_t3(meas_rec_t *r, uint16_t id)
{
    if (W.tx_on && W.tx_id == id) {
        r->tx_pre_us = W.tx_pre; r->tx_n_pre = W.tx_n;
        W.tx_on = 0;
        w_update_any();
    }
}

void meas_stamp(uint16_t id, unsigned idx, uint32_t t)
{
    meas_rec_t *r = rec_of(id);
    if (r == 0 || idx > 4u) return;
    MEAS_LOCK();
    r->t[idx] = t;
    r->have  |= (uint8_t)(1u << idx);
    if (idx == 1u)      w_at_t1(r, id, t);
    else if (idx == 2u) w_at_t2(r, id, t);
    else if (idx == 3u) w_at_t3(r, id);
    MEAS_UNLOCK();
}

void meas_mark_lost(uint16_t id)
{
    meas_rec_t *r = rec_of(id);
    if (r == 0) return;
    MEAS_LOCK();
    r->lost_queue = 1;
    if (W.tx_on && W.tx_id == id) { W.tx_on = 0; w_update_any(); }   /* t₃ hiç gelmeyecek */
    MEAS_UNLOCK();
}

/* ---- Kancalar ----------------------------------------------------------- */
void meas_hook_out(uint32_t tag, uint32_t preempted, uint32_t now)
{
    if (!W.any) return;                                  /* hızlı yol */
    tag &= 3u;
    if (W.rw_on && tag != TAG_BUTTON) {
        W.rw_acc[tag] += ts_elapsed(W.cur_in, now);
    }
    if (W.bt_on && tag == TAG_BUTTON && W.bt_running) {
        W.bt_exec += ts_elapsed(W.bt_seg, now);
        W.bt_running = 0;
        if (preempted) { W.bt_n = sat8(W.bt_n + 1u); W.bt_out = 1; W.bt_out_at = now; }
    }
    if (W.tx_on && tag == TAG_UART && preempted) {       /* yalnızca KESİLME sayılır (TIM-10) */
        W.tx_n = sat8(W.tx_n + 1u); W.tx_out = 1; W.tx_out_at = now;
    }
}

void meas_hook_in(uint32_t tag, uint32_t now)
{
    if (!W.any) return;
    tag &= 3u;
    W.cur_in = now;
    if (W.bt_on && tag == TAG_BUTTON) {
        if (W.bt_out) { W.bt_pre += ts_elapsed(W.bt_out_at, now); W.bt_out = 0; }
        W.bt_seg = now; W.bt_running = 1;
    }
    if (W.tx_on && tag == TAG_UART && W.tx_out) {
        W.tx_pre += ts_elapsed(W.tx_out_at, now); W.tx_out = 0;
    }
}

/* ---- Okuma --------------------------------------------------------------- */
uint16_t meas_events(void)   { return s_events; }
uint16_t meas_overflow(void) { return s_overflow; }
uint16_t meas_count(void)    { return s_events < MEAS_CAP ? s_events : (uint16_t)MEAS_CAP; }

static uint32_t sat(uint32_t v) { return v > REC_DELTA_MAX ? REC_DELTA_MAX : v; }

bool meas_view(uint16_t i, meas_rec_view_t *o)
{
    static const char TAG_CH[4] = { 'O', 'T', 'B', 'U' };
    if (i >= meas_count()) return false;
    const meas_rec_t *r = &s_rec[i];
    memset(o, 0, sizeof *o);
    o->event_id = r->event_id;
    o->scn      = r->scn;
    o->t0       = r->t[0];

    /* Bir fark yalnızca iki ucu da alındıysa yazılır; yoksa 0 kalır. */
    for (unsigned k = 0; k < 4u; k++) {
        const uint8_t need = (uint8_t)((1u << k) | (1u << (k + 1u)));
        if ((r->have & need) == need) {
            o->d[k] = sat(ts_elapsed(r->t[k], r->t[k + 1u]));
        }
    }
    if (r->lost_queue)                       o->lost = MEAS_LOST_QUEUE;
    else if (r->have != MEAS_HAVE_ALL)       o->lost = MEAS_INCOMPLETE;
    else                                     o->lost = MEAS_OK;

    o->ready_wait_us   = sat(r->ready_wait_us);
    o->ready_wait_task = TAG_CH[r->ready_wait_tag & 3u];
    o->bt_exec_us      = sat(r->bt_exec_us);
    o->bt_n_pre        = r->bt_n_pre;
    o->bt_pre_us       = sat(r->bt_pre_us);
    o->tx_n_pre        = r->tx_n_pre;
    o->tx_pre_us       = sat(r->tx_pre_us);
    return true;
}

/* ---- Donanım tarafı ------------------------------------------------------ */
#ifndef UNIT_TEST
void meas_hook_out_now(uint32_t tag, uint32_t preempted) { meas_hook_out(tag, preempted, ts_now()); }
void meas_hook_in_now(uint32_t tag)                      { meas_hook_in(tag, ts_now()); }

uint32_t meas_hook_cost_ns(void)
{
    /* En pahalı yolu ölç: BTN_EXEC penceresi açıkken ButtonTask'ın kesilip geri gelmesi. */
    enum { N = 1000 };
    meas_reset();
    const uint16_t id = meas_event_begin(ts_now(), 0);
    meas_stamp(id, 1, ts_now());
    taskDISABLE_INTERRUPTS();
    const uint32_t c0 = DWT->CYCCNT;
    for (uint32_t i = 0; i < N; i++) {
        meas_hook_out_now(TAG_BUTTON, 1);
        meas_hook_in_now(TAG_BUTTON);
    }
    const uint32_t cycles = DWT->CYCCNT - c0;
    taskENABLE_INTERRUPTS();
    meas_reset();                                   /* sahte olayı temizle */
    return (uint32_t)(((uint64_t)cycles * 1000000000ull) / ((uint64_t)SystemCoreClock * N));
}
#endif
