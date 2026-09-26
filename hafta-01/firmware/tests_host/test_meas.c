/* TC-U08 (firmware tarafı): t₀…t₄ kayıt mantığı ve REC değerleri (tasarım §8.1) */
#include "unit.h"
#include "app_meas.h"
#include "app_frame.h"

static void full_event(uint32_t t0, uint32_t step)
{
    uint16_t id = meas_event_begin(t0, 3);
    for (unsigned k = 1; k <= 4; k++) meas_stamp(id, k, t0 + k * step);
}

static void u08_chain(void)
{
    meas_reset();
    full_event(1000, 10);                         /* olay 1: tam zincir */
    uint16_t id2 = meas_event_begin(5000, 3);     /* olay 2: kuyruk kaybı, t₂'de biter */
    meas_stamp(id2, 1, 5020); meas_stamp(id2, 2, 5030); meas_mark_lost(id2);
    uint16_t id3 = meas_event_begin(9000, 3);     /* olay 3: t₄ gelmedi (eksik) */
    meas_stamp(id3, 1, 9001); meas_stamp(id3, 2, 9002); meas_stamp(id3, 3, 9003);

    CHECK_EQ_U(meas_events(), 3); CHECK_EQ_U(meas_count(), 3); CHECK_EQ_U(meas_overflow(), 0);
    meas_rec_view_t v;
    CHECK(meas_view(0, &v));
    CHECK(v.event_id == 1 && v.scn == 3 && v.t0 == 1000 && v.lost == MEAS_OK);
    CHECK(v.d[0] == 10 && v.d[1] == 10 && v.d[2] == 10 && v.d[3] == 10);
    CHECK(meas_view(1, &v));
    CHECK(v.lost == MEAS_LOST_QUEUE && v.d[0] == 20 && v.d[1] == 10 && v.d[2] == 0 && v.d[3] == 0);
    CHECK(meas_view(2, &v));
    CHECK(v.lost == MEAS_INCOMPLETE && v.d[2] == 1 && v.d[3] == 0);
    CHECK(!meas_view(3, &v));                     /* kayıt sayısının ötesi yok */
}

static void u08_ignore_and_wrap(void)
{
    meas_reset();
    meas_stamp(0, 1, 123);                        /* koşu dışı olay (id 0): yok sayılır */
    meas_mark_lost(0);
    CHECK_EQ_U(meas_count(), 0);

    full_event(0xFFFFFFF0u, 8);                   /* TIM2 taşması zincirin ortasında */
    meas_rec_view_t v;
    CHECK(meas_view(0, &v) && v.lost == MEAS_OK && v.d[1] == 8 && v.d[2] == 8 && v.d[3] == 8);

    uint16_t id = meas_event_begin(0, 1);         /* çok büyük fark → REC_DELTA_MAX'a doyar */
    meas_stamp(id, 1, 20000000u); meas_stamp(id, 2, 20000001u);
    meas_stamp(id, 3, 20000002u); meas_stamp(id, 4, 20000003u);
    CHECK(meas_view(1, &v) && v.d[0] == REC_DELTA_MAX && v.d[1] == 1);
}

static void u08_capacity(void)
{
    meas_reset();
    for (unsigned i = 0; i < MEAS_CAP + 2; i++) full_event(i * 100000u, 5);
    CHECK_EQ_U(meas_events(), MEAS_CAP + 2);      /* olaylar numaralanmaya devam eder */
    CHECK_EQ_U(meas_count(), MEAS_CAP);           /* ama kapasite kadar kayıt var (TIM-03) */
    CHECK_EQ_U(meas_overflow(), 2);
    meas_rec_view_t v;
    CHECK(meas_view(MEAS_CAP - 1, &v) && v.event_id == MEAS_CAP);
    meas_reset();
    CHECK_EQ_U(meas_events(), 0); CHECK_EQ_U(meas_overflow(), 0);   /* START sıfırlar */
}

void test_meas_all(void)
{
    run_case("U08", "fw: t0..t4 zinciri, kayip, eksik", u08_chain);
    run_case("U08", "fw: kosu disi, tasma, doyurma", u08_ignore_and_wrap);
    run_case("U08", "fw: kayit kapasitesi (64)", u08_capacity);
}
