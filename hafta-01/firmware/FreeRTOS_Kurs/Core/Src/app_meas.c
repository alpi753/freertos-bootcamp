/**
 * @file    app_meas.c
 * @brief   t₀…t₄ ölçüm kayıtları (saf C) — tasarım §8.1.
 */
#include <string.h>
#include "app_meas.h"
#include "app_ts.h"
#include "app_frame.h"

static meas_rec_t        s_rec[MEAS_CAP];      /* statik RAM (heap değil) */
static volatile uint16_t s_events;
static volatile uint16_t s_overflow;

void meas_reset(void)
{
    memset((void *)s_rec, 0, sizeof s_rec);
    s_events = 0;
    s_overflow = 0;
}

uint16_t meas_event_begin(uint32_t t0, uint8_t scn)
{
    const uint16_t id = (uint16_t)(s_events + 1u);
    s_events = id;
    if (id > MEAS_CAP) {
        s_overflow++;                       /* TIM-03: say ama kaydetme */
        return id;
    }
    meas_rec_t *r = &s_rec[id - 1u];
    r->event_id   = id;
    r->scn        = scn;
    r->lost_queue = 0;
    r->t[0]       = t0;
    r->have       = MEAS_HAVE_T0;
    return id;
}

static meas_rec_t *rec_of(uint16_t id)
{
    return (id == 0u || id > MEAS_CAP) ? 0 : &s_rec[id - 1u];
}

void meas_stamp(uint16_t id, unsigned idx, uint32_t t)
{
    meas_rec_t *r = rec_of(id);
    if (r == 0 || idx > 4u) return;
    r->t[idx] = t;
    r->have  |= (uint8_t)(1u << idx);
}

void meas_mark_lost(uint16_t id)
{
    meas_rec_t *r = rec_of(id);
    if (r) r->lost_queue = 1;
}

uint16_t meas_events(void)   { return s_events; }
uint16_t meas_overflow(void) { return s_overflow; }
uint16_t meas_count(void)    { return s_events < MEAS_CAP ? s_events : (uint16_t)MEAS_CAP; }

static uint32_t sat(uint32_t v) { return v > REC_DELTA_MAX ? REC_DELTA_MAX : v; }

bool meas_view(uint16_t i, meas_rec_view_t *o)
{
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
    return true;
}
