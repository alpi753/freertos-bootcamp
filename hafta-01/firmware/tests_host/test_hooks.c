/* TC-U10: görev değiştirme kancalarının muhasebesi (TIM-07…TIM-10; tasarım §8.2).
 * Gerçek bir görev değişimi dizisi elle "oynatılır" ve PRE değerleri elle hesaplananla karşılaştırılır. */
#include "unit.h"
#include "app_meas.h"

enum { O = 0, TEL = 1, BTN = 2, UART = 3 };
#define PRE 1u   /* kesildi */
#define BLK 0u   /* bloklandı */

static void u10_idle_s0(void)
{
    /* S0: t₀ geldiğinde idle koşuyor; ButtonTask hemen CPU'yu alır, kimse kesmez. */
    meas_reset();
    uint16_t id = meas_event_begin(1000, 0);
    meas_hook_out(O, PRE, 1005);   meas_hook_in(BTN, 1006);       /* ISR çıkışı → ButtonTask */
    meas_stamp(id, 1, 1006);
    meas_stamp(id, 2, 1050);
    meas_hook_out(BTN, BLK, 1060); meas_hook_in(UART, 1061);      /* ButtonTask beklemeye geçti */
    meas_stamp(id, 3, 1062);
    meas_hook_out(UART, BLK, 1063); meas_hook_in(O, 1064);        /* UartTx TC'yi bekliyor: BLOKLANMA */
    meas_stamp(id, 4, 6620);
    meas_rec_view_t v; CHECK(meas_view(0, &v));
    CHECK_EQ_U(v.ready_wait_us, 5);  CHECK(v.ready_wait_task == 'O');
    CHECK_EQ_U(v.bt_exec_us, 44);    CHECK_EQ_U(v.bt_n_pre, 0); CHECK_EQ_U(v.bt_pre_us, 0);
    CHECK_EQ_U(v.tx_n_pre, 0);       CHECK_EQ_U(v.tx_pre_us, 0);          /* T22'nin mantığı */
    CHECK_EQ_U(v.d[1], v.bt_exec_us + v.bt_pre_us);                       /* T21 denklemi */
}

static void u10_button_preempted(void)
{
    /* t₀'da TelemetryTask koşuyor (300 µs daha); t₁'den 20 µs sonra tekrar gelip 2 ms koşuyor. */
    meas_reset();
    uint16_t id = meas_event_begin(0, 5);
    meas_hook_out(TEL, BLK, 300);  meas_hook_in(BTN, 300);
    meas_stamp(id, 1, 300);
    meas_hook_out(BTN, PRE, 320);  meas_hook_in(TEL, 320);        /* ButtonTask KESİLDİ */
    meas_hook_out(TEL, BLK, 2320); meas_hook_in(BTN, 2320);
    meas_stamp(id, 2, 2340);
    meas_rec_view_t v; CHECK(meas_view(0, &v));
    CHECK_EQ_U(v.ready_wait_us, 300); CHECK(v.ready_wait_task == 'T');
    CHECK_EQ_U(v.bt_exec_us, 40);     CHECK_EQ_U(v.bt_pre_us, 2000); CHECK_EQ_U(v.bt_n_pre, 1);
    CHECK_EQ_U(v.d[1], v.bt_exec_us + v.bt_pre_us);
    CHECK(v.ready_wait_us <= v.d[0]);
}

static void u10_uart_preempted_vs_blocked(void)
{
    meas_reset();
    uint16_t id = meas_event_begin(0, 3);
    meas_stamp(id, 1, 10); meas_stamp(id, 2, 50);                 /* TX_WAIT açıldı */
    meas_hook_out(BTN, BLK, 60);  meas_hook_in(UART, 60);
    meas_hook_out(UART, BLK, 70); meas_hook_in(O, 70);            /* önceki TEL'in TC'sini bekliyor: sayılmaz */
    meas_hook_out(O, PRE, 5000);  meas_hook_in(UART, 5000);
    meas_hook_out(UART, PRE, 5010); meas_hook_in(TEL, 5010);      /* TelemetryTask kesti: sayılır */
    meas_hook_out(TEL, BLK, 5110); meas_hook_in(UART, 5110);
    meas_stamp(id, 3, 5120);
    meas_rec_view_t v; CHECK(meas_view(0, &v));
    CHECK_EQ_U(v.tx_n_pre, 1); CHECK_EQ_U(v.tx_pre_us, 100);
    CHECK(v.tx_pre_us <= v.d[2]);
}

static void u10_lost_and_idle_hooks(void)
{
    meas_reset();
    meas_hook_out(UART, PRE, 1); meas_hook_in(UART, 2);            /* pencere yok: etkisiz */
    uint16_t id = meas_event_begin(100, 3);
    meas_stamp(id, 1, 110); meas_stamp(id, 2, 120);
    meas_mark_lost(id);                                           /* TX_WAIT kapanmalı */
    meas_hook_out(UART, PRE, 200); meas_hook_in(UART, 900);
    meas_rec_view_t v; CHECK(meas_view(0, &v));
    CHECK(v.lost == MEAS_LOST_QUEUE && v.tx_n_pre == 0 && v.tx_pre_us == 0);
}

void test_hooks_all(void)
{
    run_case("U10", "S0: kesilme yok, bloklanma sayilmaz", u10_idle_s0);
    run_case("U10", "ButtonTask kesildi: exec+pre = t2-t1", u10_button_preempted);
    run_case("U10", "UartTx: kesilme sayilir, bloklanma sayilmaz", u10_uart_preempted_vs_blocked);
    run_case("U10", "kayip olayda TX penceresi kapanir", u10_lost_and_idle_hooks);
}
