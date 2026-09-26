/**
 * @file    app_meas.h
 * @brief   Olay başına t₀…t₄ ölçüm kayıtları (TIM-02, TIM-02a/b, TIM-03; tasarım §8).
 *
 * Kayıtlar koşu boyunca yalnızca RAM'de tutulur; STOP'tan sonra DUMP ile
 * REC çerçeveleri olarak gönderilir (TIM-05). Modül saf C'dir (HAL/FreeRTOS
 * yok) ve PC'de test edilir (tests_host/test_meas.c).
 *
 * Yazanlar: ISR (t₀), ButtonTask (t₁, t₂, kayıp), UartTxTask (t₃),
 * UART TC kesmesi (t₄). Her alanı tek bir yazar değiştirir.
 *
 * Görev değişimi ölçümleri (TIM-07…TIM-10; tasarım §8.2): FreeRTOS'un
 * traceTASK_SWITCHED_OUT/IN kancaları meas_hook_out/in'i çağırır. Üç pencere:
 *   READY    t₀ → t₁ : ButtonTask dışındaki görevlerin CPU süresi (ready_wait)
 *   BTN_EXEC t₁ → t₂ : ButtonTask'ın net çalışma süresi + kesilmeleri
 *   TX_WAIT  t₂ → t₃ : UartTxTask'ın kesilmeleri
 */
#ifndef APP_MEAS_H
#define APP_MEAS_H

#include <stdint.h>
#include <stdbool.h>
#include "app_config.h"

#if TEST_MEAS_CAP
#define MEAS_CAP  4u      /* TC-T15: kapasite taşmasını denemek için */
#else
#define MEAS_CAP  64u     /* TIM-03: en az 64 olay */
#endif

/* Kayıt durumu (REC çerçevesindeki "lost" alanı) */
#define MEAS_OK          0u   /* t₀…t₄ tam */
#define MEAS_LOST_QUEUE  1u   /* xQueueSend başarısız: zincir t₂'de bitti (TIM-02a) */
#define MEAS_INCOMPLETE  2u   /* beklenmeyen: damgalardan biri eksik (ör. TC zaman aşımı) */

/* have bit maskesi */
#define MEAS_HAVE_T0  0x01u
#define MEAS_HAVE_T1  0x02u
#define MEAS_HAVE_T2  0x04u
#define MEAS_HAVE_T3  0x08u
#define MEAS_HAVE_T4  0x10u
#define MEAS_HAVE_ALL 0x1Fu

typedef struct {
    uint16_t event_id;        /* 1'den başlar, her koşuda sıfırlanır */
    uint8_t  scn;
    uint8_t  lost_queue;      /* 1: kuyruğa yazılamadı */
    volatile uint8_t  have;   /* hangi damgalar alındı */
    uint32_t t[5];            /* t₀…t₄ [µs, TIM2] */
    /* görev değişimi (PRE) */
    uint32_t ready_wait_us;   /* t₀–t₁: diğer görevlerin CPU'da geçirdiği süre */
    uint8_t  ready_wait_tag;  /* en çok süre alan görevin tag'i (app_task_tag_t) */
    uint8_t  bt_n_pre;        /* t₁–t₂: ButtonTask kaç kez kesildi */
    uint8_t  tx_n_pre;        /* t₂–t₃: UartTxTask kaç kez kesildi */
    uint32_t bt_exec_us;      /* t₁–t₂: ButtonTask'ın CPU'da geçirdiği süre (bağımsız ölçülür) */
    uint32_t bt_pre_us;       /* t₁–t₂: kesik kaldığı süre */
    uint32_t tx_pre_us;       /* t₂–t₃: UartTxTask'ın kesik kaldığı süre */
} meas_rec_t;

/** REC çerçevesi için hazırlanmış değerler */
typedef struct {
    uint16_t event_id;
    uint8_t  scn;
    uint32_t t0;
    uint32_t d[4];            /* t1-t0, t2-t1, t3-t2, t4-t3; REC_DELTA_MAX'a doyurulmuş */
    uint8_t  lost;            /* MEAS_OK / MEAS_LOST_QUEUE / MEAS_INCOMPLETE */
    /* PRE çerçevesi */
    uint32_t ready_wait_us;
    char     ready_wait_task; /* 'T' Telemetry, 'B' Button, 'U' UartTx, 'O' diğer (idle, timer) */
    uint32_t bt_exec_us;
    uint8_t  bt_n_pre;
    uint32_t bt_pre_us;
    uint8_t  tx_n_pre;
    uint32_t tx_pre_us;
} meas_rec_view_t;

/** START: tüm kayıtları ve sayaçları sıfırlar. */
void     meas_reset(void);

/** ISR (yalnızca koşuda): yeni olay açar ve olay numarasını döndürür (1, 2, …).
 *  Kapasite doluysa olay yine numaralanır ama kaydedilmez (rec_overflow++). */
uint16_t meas_event_begin(uint32_t t0, uint8_t scn);

/** Damga yaz. event_id == 0 (koşu dışı) veya kapasite dışı ise hiçbir şey yapmaz. */
void     meas_stamp(uint16_t event_id, unsigned idx, uint32_t t);
void     meas_mark_lost(uint16_t event_id);

uint16_t meas_events(void);        /* koşuda kabul edilen olay sayısı */
uint16_t meas_count(void);         /* kaydedilen olay sayısı (≤ MEAS_CAP) */
uint16_t meas_overflow(void);      /* kapasite yüzünden kaydedilemeyen olay */

/** i. kaydı REC/PRE çerçevelerine hazır hâle getirir (i < meas_count()). */
bool     meas_view(uint16_t i, meas_rec_view_t *out);

/* ---- Görev değiştirme kancaları (saf çekirdek; PC'de test edilir) ------
 * tag: görevin application task tag'i (0 diğer, 1 Telemetry, 2 Button, 3 UartTx)
 * preempted: görev CPU'yu bırakırken hâlâ Ready listesindeyse 1 (kesildi),
 *            bir şey beklediği için bıraktıysa 0 (bloklandı) — TIM-10.
 * Açık pencere yoksa ikisi de birkaç komutla döner. */
void meas_hook_out(uint32_t tag, uint32_t preempted, uint32_t now);
void meas_hook_in(uint32_t tag, uint32_t now);

#ifndef UNIT_TEST
/* FreeRTOSConfig.h'teki trace makroları bunları çağırır (PendSV içinde). */
void meas_hook_out_now(uint32_t tag, uint32_t preempted);
void meas_hook_in_now(uint32_t tag);
/** TC-T23: bir çıkış+giriş kanca çiftinin ortalama maliyeti [ns] (açılışta, kesmeler kapalı). */
uint32_t meas_hook_cost_ns(void);
#endif

#endif /* APP_MEAS_H */
