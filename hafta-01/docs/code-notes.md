# Kod notları

Bu dosya ölçüm zincirinin kodunu adım adım anlatır: ISR → ButtonTask → kuyruk → UartTxTask → UART tamamlanması, ayrıca zaman hesapları ve görev değişimi kancaları. Kod blokları `firmware/FreeRTOS_Kurs/Core` altındaki dosyalardan alınmıştır.

```
 B1 ─► EXTI ISR ──notify──► ButtonTask ──xQueueSend──► [g_txq FIFO] ──► UartTxTask ──DMA──► USART2 ──TC──► TxCplt ISR
       t₀                   t₁          t₂                                 t₃                            t₄
       │◄─ d_EventToRun ─►│◄─ d_ButtonExec ─►│◄──── d_QueueWait ────►│◄──── d_UartTx ────►│
```

## 1. Zaman tabanı (TIM-01)

TIM2, 80 MHz / (79+1) = 1 MHz ile sayan 32 bitlik serbest bir sayaçtır (`main.c`):

```c
htim2.Init.Prescaler = 79;
htim2.Init.Period = 4294967295;
```

`app_ts.h`:

```c
static inline uint32_t ts_now(void) { return TIM2->CNT; }

/** t_start → t_end arası geçen süre [µs]; tek taşmaya dayanıklı (TIM-01). */
static inline uint32_t ts_elapsed(uint32_t t_start, uint32_t t_end)
{
    return (uint32_t)(t_end - t_start);
}
```

> 💡 **Neden işaretsiz çıkarma?** Sayaç 0xFFFFFFFF'ten 0'a döndüğünde `t_end < t_start` olur. İşaretsiz aritmetikte `t_end - t_start` yine doğru farkı verir (mod 2³²). Tek koşul, iki damga arasında sayacın birden fazla tur atmamasıdır (71 dakika).

## 2. Buton ISR'ı: t₀ (ISR-01…04)

`stm32l4xx_it.c`: t₀ adayı, HAL'e girmeden önce handler'ın ilk satırında alınır.

```c
void EXTI15_10_IRQHandler(void)
{
  /* USER CODE BEGIN EXTI15_10_IRQn 0 */
  g_exti_ts = ts_now();          /* t₀ adayı: HAL'den ÖNCE, handler'ın ilk işi (tasarım §7.1) */
  APP_EXTI_TIMING_BEGIN();       /* TC-T09 */
  /* USER CODE END EXTI15_10_IRQn 0 */
  HAL_GPIO_EXTI_IRQHandler(B1_Pin);
  /* USER CODE BEGIN EXTI15_10_IRQn 1 */
  APP_EXTI_TIMING_END();
  /* USER CODE END EXTI15_10_IRQn 1 */
}
```

`app_button.c`: HAL'in çağırdığı callback yalnızca şu işleri yapar:

- **debounce:** 50 ms, TIM2 damgasıyla,
- **olay numarası:** yalnızca koşudayken,
- **görev bildirimi.**

`snprintf` ya da UART yoktur (ISR-02).

```c
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
```

**`portYIELD_FROM_ISR`:** Bildirim, ButtonTask'ı o an koşan görevden daha öncelikli yaptıysa (`hpw = pdTRUE`), ISR biter bitmez PendSV ile bağlam değişir. Görev bir sonraki tick'i beklemez. `d_EventToRun`, bu gecikmeyi ve ButtonTask'tan yüksek öncelikli görevin (TelemetryTask) o sırada yaptığı işi ölçer.

**Kesme önceliği:** EXTI15_10, USART2 ve DMA1_Ch7 kesmeleri 6 önceliğindedir (`main.c`, `stm32l4xx_hal_msp.c`). Bu değer `configMAX_SYSCALL_INTERRUPT_PRIORITY` (5) değerinden sayıca büyük, yani mantıksal olarak daha düşük önceliklidir. Bu yüzden `...FromISR` çağrıları güvenlidir.

```c
HAL_NVIC_SetPriority(EXTI15_10_IRQn, 6, 0);
HAL_NVIC_SetPriority(DMA1_Channel7_IRQn, 6, 0);
HAL_NVIC_SetPriority(USART2_IRQn, 6, 0);
```

## 3. ButtonTask: t₁, t₂ (TSK-05, QUE-03)

`app_button.c`, görev döngüsü (TC-T18 test kodu çıkarıldı):

```c
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
```

- **Görev bildirimi:** Semafor yerine hafif bir sayaçtır (`ulTaskNotifyTake`). `n > 1` ise görev, bildirimleri alamadan birden fazla basış gelmiş demektir.
- **`d_ButtonExec`:** t₁→t₂ arası yalnızca çerçeveyi biçimlendirme işidir (`frame_build`, `snprintf`). Kancalar bu aralığı `bt_exec` (net CPU) ve `bt_preempt` (TelemetryTask'ın araya girdiği süre) olarak ikiye böler.
- **Kuyruk dolu:** `xQueueSend` en fazla 10 ms bekler. Yer açılmazsa olay `lost = 1` olarak işaretlenir. t₃ ve t₄ hiç alınmaz.

Kuyruk öğesi, çerçeve metnine ek olarak tipini ve olay numarasını da taşır (`app_msg.h`). UartTxTask BTN'i metni ayrıştırarak değil bu alanla tanır (TIM-02b):

```c
typedef struct {
    uint8_t  type;              /* msg_type_t */
    uint8_t  scn;               /* 0..5 */
    uint16_t event_id;          /* BTN için; TEL'de 0 (TIM-02b) */
    char     frame[FRAME_LEN];  /* hazır, dolgulu, '\n' ile biten çerçeve */
} tx_item_t;                    /* 68 bayt */
```

```c
g_txq = xQueueCreate(TXQ_DEPTH, sizeof(tx_item_t));   /* app_run.c; TXQ_DEPTH = 16 */
```

## 4. TelemetryTask (TSK-01…04)

`app_telemetry.c` (ölçüm sayaçları çıkarılarak kısaltıldı):

```c
TickType_t last = xTaskGetTickCount();
uint32_t   seq  = 0;                            /* her koşuda 0'dan (TSK-02) */

for (;;) {
    /* Mutlak periyot: iş süresi periyoda eklenmez (TSK-01). */
    vTaskDelayUntil(&last, pdMS_TO_TICKS(period));
    if (!run_is_running() || g_run_id != run_id) {
        break;                                  /* STOP geldi veya yeni koşu başladı */
    }
    uint32_t a = ts_now();
    const int16_t t_x10 = temp_read_x10();      /* ≈ 623 µs (CAL satırı) */
    ...
    if (load_us) {                              /* S4/S5: ≈2 / ≈5 ms gerçek hesap */
        cpu_load_run(load_us);
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
```

**`vTaskDelay` yerine `vTaskDelayUntil`:** Periyot, bir önceki uyanma anından sayılır. Bu yüzden ADC okuma ve CPU yükü periyodu uzatmaz. **`xQueueSend(…, 0)`:** Telemetri hiç beklemez; kuyruk doluysa çerçeveyi düşürür ve sayar.

## 5. UartTxTask ve UART tamamlanması: t₃, t₄ (TSK-06, TIM-02)

`app_uart_tx.c` (TC-T13 test kodu çıkarıldı):

```c
for (;;) {
    cmd_poll();
    tx_item_t it;
    if (xQueueReceive(g_txq, &it, pdMS_TO_TICKS(UART_RX_POLL_MS)) == pdPASS) {
        uart_send_frame(it.frame, it.type == MSG_BTN ? it.event_id : 0u);   /* FIFO: sırayla */
    }
}

static void uart_send_frame(const char *frame, uint16_t btn_id)
{
    s_tx_btn = btn_id;
    const uint32_t t3 = ts_now();            /* t₃: UART başlatma çağrısından hemen önce */
    if (HAL_UART_Transmit_DMA(&huart2, (uint8_t *)frame, FRAME_LEN) != HAL_OK) {
        s_tx_btn = 0;
        s_tx_errors++;
        return;
    }
    meas_stamp(btn_id, 3, t3);
    if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(UART_TX_TIMEOUT_MS)) == 0u) {
        s_tx_errors++;
    }
}

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *h)
{
    /* HAL bunu DMA bittikten SONRA, son baytın stop biti hattan çıkınca (TC) çağırır. */
    const uint32_t t4 = ts_now();            /* t₄: TC işlenirken, ilk iş */
    if (h->Instance != USART2) return;
    if (s_tx_btn) { meas_stamp(s_tx_btn, 4, t4); s_tx_btn = 0; }
    BaseType_t hpw = pdFALSE;
    vTaskNotifyGiveFromISR(s_self, &hpw);
    portYIELD_FROM_ISR(hpw);
}
```

- **Görev DMA bitene kadar bloklanır:** DMA baytları taşırken CPU'yu kullanmaz. Görev, TC kesmesinden gelen bildirimi bekler; bir sonraki çerçeve ancak öncekinin son biti hattan çıktıktan sonra başlar.
- **t₄ TC anında alınır:** "DMA bitti" anı, son baytın UART'ın kaydırma yazmacına yazıldığı andır; bayt henüz hatta değildir. t₄ ise TC (transmission complete) kesmesinde, yani son bit hattan çıktıktan sonra alınır. Bu yüzden `d_UartTx` ≥ 64 × 10 bit / 115200 = 5556 µs olur (T12'deki fiziksel alt sınır).
- **`d_QueueWait`:** BTN çerçevesinin önünde kuyrukta kaç TEL çerçevesi beklediğini gösterir. Her biri yaklaşık 5,6 ms'dir (B-01).

## 6. Görev değişimi kancaları: kesilme mi, bloklanma mı? (TIM-07…10)

`FreeRTOSConfig.h` (`USER CODE Defines`):

```c
#define traceTASK_SWITCHED_OUT()                                                         \
    meas_hook_out_now((uint32_t)(uintptr_t)pxCurrentTCB->pxTaskTag,                     \
                      (uint32_t)listIS_CONTAINED_WITHIN(&pxReadyTasksLists[pxCurrentTCB->uxPriority], \
                                                        &pxCurrentTCB->xStateListItem))
#define traceTASK_SWITCHED_IN()                                                          \
    meas_hook_in_now((uint32_t)(uintptr_t)pxCurrentTCB->pxTaskTag)
```

Çekirdek bir görevi CPU'dan indirirken, görev hâlâ kendi öncelik seviyesinin **Ready listesindeyse** onu daha öncelikli bir görev kesmiştir (**kesilme**). Listede değilse görev kendisi bir şey bekliyordur: kuyruk, bildirim ya da gecikme (**bloklanma**). Yalnızca kesilmeler `*_n_preempt` ve `*_preempt_us` alanlarına sayılır. Her görev kendi kimliğini `vTaskSetApplicationTaskTag` ile TCB'ye yazar (`APP_SET_OWN_TAG`).

`app_meas.c`:

```c
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
```

Üç pencere vardır:

| Pencere | Aralık | Ölçülen |
|---|---|---|
| READY | t₀→t₁ | Başka görevlerin CPU'da geçirdiği süre (`ready_wait_us`) ve en çok süre alan görev |
| BTN_EXEC | t₁→t₂ | `bt_exec` (ButtonTask'ın net süresi), `bt_n_preempt`, `bt_preempt_us` |
| TX_WAIT | t₂→t₃ | UartTxTask'ın kesilme sayısı ve süresi |

**Bağımsız kontrol (T21, V5):** `bt_exec` doğrudan biriktirilir. Bu yüzden `d_ButtonExec = bt_exec_us + bt_preempt_us` (±2 µs) eşitliği gerçek bir denetimdir, tanım gereği doğru olan bir eşitlik değildir.

**Kanca maliyeti:** Bir çıkış + giriş çifti ≈ 1513 ns sürer (T23, Release). Bu maliyet ölçülen aralıklara dahildir.

> ⚠️ **Sınırlama (TIM-11):** Donanım kesmeleri (SysTick, DMA, EXTI, USART) görev değişimi sayılmaz. Bir kesme, bir görev koşarken gelirse süresi o görevin `exec` süresine eklenir. Örneğin ButtonTask'ın `bt_exec` değeri, t₁→t₂ arasında gelen SysTick ve DMA kesmelerinin süresini de içerir. Kancalar yalnızca FreeRTOS'un görev değiştirdiği anları görür; kesme girişlerini görmez.

> ⚠️ **Kırılganlık:** Makrolar FreeRTOS 10.3.1'in iç yapılarını kullanır (`pxCurrentTCB`, `pxReadyTasksLists`). Çekirdek güncellenirse kontrol edilmelidir.

## 7. Kayıt ve döküm (TIM-02a, MSG-05/06)

Her olay için t₀ ve dört fark saklanır (`app_meas.c`, 64 kayıt). DUMP şu çerçeveleri gönderir:

| Çerçeve | Alanlar |
|---|---|
| `REC,<id>,S<n>,<t0>,<d1>,<d2>,<d3>,<d4>,<lost>` | t₀ ve dört aralık |
| `PRE,…` | Görev değişimi alanları |
| `SUM` | Koşu sayaçları |
| `CAL` | ADC ve yük kalibrasyonu, kanca maliyeti |
| `MEM` | En düşük boş heap, stack kullanımı |
| `RTS` | Görev başına CPU payı |

Mutlak damgalar PC'de `t_k = t_{k−1} + d_k (mod 2³²)` ile geri kurulur (`interface/uart_monitor/protocol.py`, `rec_absolute`).

## 8. PC tarafı (UI-09)

Arayüz ve analiz, süreleri **yalnızca** REC/PRE'deki MCU damgalarından alır:

- **Seri okuma:** Ayrı bir `QThread`'de yapılır (`serial_worker.py`); çizim yavaşlasa da bayt kaybolmaz.
- **Telemetri grafiği:** x ekseni `seq × periyot`'tur, PC saati değildir.
- **Sonuç grafikleri:** x ekseni `event_id`'dir.
- **`hil_check.py` loglarındaki PC ms sütunu:** Yalnızca hata ayıklama içindir.

## 9. CubeMX / NVIC inceleme listesi (TC-R02)

| Ayar | Değer | Kaynak |
|---|---|---|
| EXTI15_10, USART2, DMA1_Ch7 | etkin, öncelik 6 | `main.c`, `stm32l4xx_hal_msp.c` (yukarıdaki kod bloğu) |
| `configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY` | 5 | `FreeRTOSConfig.h` |
| TIM2 | PSC 79, ARR 0xFFFFFFFF | `main.c` (§1) |
| ADC1 | sıcaklık kanalı, `ADC_SAMPLETIME_640CYCLES_5` | `main.c` |
| FreeRTOS | `configTICK_RATE_HZ 1000`, `configUSE_PREEMPTION 1`, `configSUPPORT_STATIC_ALLOCATION 1`, `configTOTAL_HEAP_SIZE 16384`, `configCHECK_FOR_STACK_OVERFLOW 2`, `configGENERATE_RUN_TIME_STATS 1`, `configUSE_NEWLIB_REENTRANT 1` | `FreeRTOSConfig.h` |
| Görevler | UartTx `osPriorityNormal` (24), Button `osPriorityAboveNormal` (32), Telemetry `osPriorityHigh` (40); statik stack 512 / 256 / 384 word | `main.c` |
