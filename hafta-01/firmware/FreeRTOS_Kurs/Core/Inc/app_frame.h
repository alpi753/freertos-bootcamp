/**
 * @file    app_frame.h
 * @brief   64 baytlık sabit çerçeveler ve tüm çerçeve biçimleri (tasarım §9).
 *
 * Çerçeve = ASCII içerik (≤ 63 karakter) + boşluk dolgusu + bayt 64 = '\n' (MSG-01).
 * İçerik 63'ü aşarsa çerçeve KESİLMEZ: üretilmez ve frame_err artar (MSG-02).
 *
 * Tüm biçimler burada, tek yerde tanımlıdır; en uzun hâllerinin 63 karaktere
 * sığdığı PC'de birim testiyle doğrulanır (TC-U06).
 * PRIu32 kullanılır: uint32_t ARM'da "unsigned long", PC'de "unsigned int"tir.
 */
#ifndef APP_FRAME_H
#define APP_FRAME_H

#include <stdint.h>
#include <stdbool.h>
#include <inttypes.h>
#include <stdarg.h>

#define FRAME_LEN      64u     /* toplam bayt */
#define FRAME_PAYLOAD  63u     /* en fazla içerik karakteri */

/* REC çerçevesindeki aralıklar en fazla 7 hane taşır (≈ 10 s). Daha büyük bir
 * değer ölçüm hatası demektir; doyurulur ve PC tarafında görülebilir kalır. */
#define REC_DELTA_MAX  9999999u

/* ---- Koşu sırasında ---------------------------------------------------- */
/* TEL,<seq>,S<n>,<temp_x10> */
#define FMT_TEL  "TEL,%" PRIu32 ",S%u,%d"
/* BTN,<event_id>,S<n>,PRESSED */
#define FMT_BTN  "BTN,%u,S%u,PRESSED"

/* ---- DUMP ile -------------------------------------------------------- */
/* VER,<git_hash>,<Debug|Release>,<test_flags_hex> */
#define FMT_VER  "VER,%s,%s,%02X"
/* REC,<id>,S<n>,<t0>,<t1-t0>,<t2-t1>,<t3-t2>,<t4-t3>,<lost> */
#define FMT_REC  "REC,%u,S%u,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%u"
/* PRE,<id>,<ready_wait_us>,<rw_task>,<bt_exec_us>,<bt_n_pre>,<bt_pre_us>,<tx_n_pre>,<tx_pre_us> */
#define FMT_PRE  "PRE,%u,%" PRIu32 ",%c,%" PRIu32 ",%u,%" PRIu32 ",%u,%" PRIu32
/* SUM,S<n>,<events>,<tel_sent>,<tel_dropped>,<btn_dropped>,<q_hw>,<rec_overflow>,<bounce_rej>,<frame_err> */
#define FMT_SUM  "SUM,S%u,%u,%" PRIu32 ",%" PRIu32 ",%u,%u,%u,%u,%u"
/* CAL,<load_target_us>,<load_mean_us>,<load_max_us>,<adc_mean_us>,<hook_ns> */
#define FMT_CAL  "CAL,%u,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%" PRIu32
/* MEM,<min_free_heap>,<hw_tel>,<hw_btn>,<hw_tx>  (high-water: word) */
#define FMT_MEM  "MEM,%" PRIu32 ",%u,%u,%u"
/* RTS,<task_name>,<run_us>,<pct_x10> */
#define FMT_RTS  "RTS,%s,%" PRIu32 ",%u"

/** frame_build'in reddettiği (63'ü aşan) içerik sayısı. SUM'da raporlanır. */
extern volatile uint32_t g_frame_err;

/**
 * printf biçimiyle 64 baytlık çerçeve üretir.
 * @return true: out tam 64 bayt, içerik + boşluk dolgusu + '\n'.
 *         false: içerik 63'ü aştı (veya biçim hatası); out DEĞİŞMEZ, g_frame_err++.
 *         Debug derlemede (DEBUG tanımlı) configASSERT ile durur.
 */
bool frame_build(char out[FRAME_LEN], const char *fmt, ...)
    __attribute__((format(printf, 2, 3)));

/** frame_build ile aynı; va_list alan sürüm (başka değişken argümanlı fonksiyonlardan çağırmak için). */
bool frame_vbuild(char out[FRAME_LEN], const char *fmt, va_list ap)
    __attribute__((format(printf, 2, 0)));

#endif /* APP_FRAME_H */
