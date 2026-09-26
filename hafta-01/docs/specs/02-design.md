# SPEC-02 · Tasarım — Hafta 01

| Alan | Değer |
|---|---|
| Doküman | `hafta-01/docs/specs/02-design.md` |
| Sürüm | 1.6 (ONAYLANDI — 2026-09-26) |
| Tarih | 2026-09-25 |
| Girdi | `01-requirements.md` v1.2 |
| Sonraki doküman | `03-test-plan.md` |

Bu doküman gereksinimlerin **nasıl** karşılanacağını anlatır. Her bölümün sonunda hangi gereksinimleri karşıladığı yazar; tam izlenebilirlik tablosu §13'te. `💡` ile başlayan kutular öğrenme notlarıdır: kararın arkasındaki kavramı açıklar.

---

## 1. Mimari genel bakış

```
                ┌────────────── MCU (STM32L476RG, FreeRTOS 10.3.1) ─────────────────┐
  B1 (PC13) ──▶ │ EXTI15_10 ISR ──notify──▶ ButtonTask (orta) ──┐                   │
                │   t₀, debounce                 t₁, t₂          │                   │
                │                                                ▼                   │
  VTS ─ ADC1 ─▶ │ TelemetryTask (yüksek) ─────────────────▶ [ TX kuyruğu, FIFO ]    │
                │   vTaskDelayUntil, CPU yükü                    │                   │
                │                                                ▼                   │
                │                                 UartTxTask (düşük) ─ t₃ ─▶ DMA1 Ch7│──▶ USART2 TX ──▶ PC
                │                                   ▲     ▲                   │      │
                │               notify (TxCplt, t₄) │     │ komut satırları   │      │
                │   USART2 ISR ─────────────────────┘     │                   │      │
                │   (TC + RX baytı) ──▶ RX ring buffer ───┘                   │      │
                │                                                                    │
                │   TIM2 (1 MHz, 32-bit) ◀── ts_now()      trace kancaları ─▶ meas   │
                └────────────────────────────────────────────────────────────────────┘
```

**Temel ilke: UART'ın tek sahibi UartTxTask'tır.** Diğer görevler yalnızca kuyruğa yazar. ACK/NAK, REC, PRE, SUM gibi kontrol ve döküm çerçevelerini de yine UartTxTask kendisi üretip gönderir; bunlar kuyruğa girmez.

> 💡 **Neden kontrol çerçeveleri kuyruğa girmiyor?** Kuyruk ölçtüğümüz nesne. Oraya ACK ya da REC koysaydık BTN çerçevesinin önüne ölçümle ilgisiz çerçeveler girer, `d_QueueWait` bozulurdu. Kuyrukta yalnızca kurs tanımındaki iki üretici (TEL, BTN) bulunur.

Karşıladığı: SYS-01, QUE-01, TSK-06, TIM-05.

---

## 2. Dizin yapısı ve dosya yerleşimi

```
hafta-01/
├── README.md
├── gozlemler.md                 ← kursiyer doldurur (dokunulmaz)
├── firmware/FreeRTOS_Kurs/      ← mevcut project/FreeRTOS_Kurs buraya taşınır
│   └── Core/
│       ├── Inc/  app_config.h  app_ts.h  app_frame.h  app_meas.h  app_run.h  app_cmd.h  app_tasks.h
│       └── Src/  app_ts.c  app_frame.c  app_meas.c  app_run.c  app_cmd.c
│                 app_telemetry.c  app_button.c  app_uart_tx.c
├── interface/                   ← PC arayüzü (Python)
├── measurements/                ← S0.csv … S5.csv, summary.csv
├── analysis/                    ← analyze.py, report.md, plots/
└── docs/                        ← setup.md, code-notes.md, ai-usage.md, specs/
```

**Karar:** Uygulama dosyaları `Core/Inc` ve `Core/Src` altına `app_` önekiyle konacak. Bu klasörler projenin derleme yolunda zaten var, bu yüzden IDE'de include/source yolu ayarı gerekmez. CubeMX yeniden kod üretse de bu dosyalara dokunmaz.

**Taşıma notu:** `project/` → `firmware/` taşıması STM32CubeIDE kapalıyken yapılacak. `.metadata/` bir IDE çalışma alanıdır ve repoya girmez. Taşımadan sonra projeyi IDE'de *File → Import → Existing Projects* ile yeniden açman gerekir.

Karşıladığı: DOC-01, DOC-05, DOC-06.

---

## 3. CubeMX (.ioc) değişiklikleri

| # | Çevre birimi | Ayar | Neden |
|---|---|---|---|
| C-1 | **NVIC** | EXTI line[15:10] etkin, öncelik **6** | Buton kesmesi şu an kapalı (ISR-01) |
| C-2 | **USART2** | Global kesme etkin, öncelik **6** | TC (t₄) ve RX baytı bu kesmeden gelir |
| C-3 | **USART2 DMA** | `USART2_TX` → **DMA1 Channel 7**, Normal mod, Memory increment, Byte/Byte, öncelik Low; DMA kesmesi öncelik **6** | DMA ile gönderim (D-02) |
| C-4 | **TIM2** | Clock source Internal, Prescaler **79**, Counter period **0xFFFFFFFF**, kesme yok | 1 MHz, 32-bit serbest çalışan zaman sayacı (TIM-01) |
| C-5 | **ADC1** | Temperature Sensor Channel etkin; 12-bit; tek dönüşüm; yazılım tetikleme; örnekleme **640.5 cycles** | Sıcaklık telemetrisi (TSK-08) |
| C-6 | **FREERTOS → Tasks and Queues** | CubeMX son görevin silinmesine izin vermiyor. Bu yüzden `defaultTask` → `TelemetryTask` olarak yeniden adlandırılır, `ButtonTask` ve `UartTxTask` eklenir (§5 tablosundaki öncelik ve stack değerleriyle). *Allocation = **Static***. *Code Generation Option*: TelemetryTask ve ButtonTask **As external**; UartTxTask **As weak** (CubeMX `main.c`'deki ilk görev için *As external* sunmuyor; *As weak* ile CubeMX'in boş gövdesi `__weak` olur ve `app_uart_tx.c`'deki gövde onun yerine bağlanır); giriş fonksiyonları `app_*.c` dosyalarında yazılır. Kuyruk CubeMX'te **tanımlanmaz**, kodda oluşturulur. | SYS-01 |
| C-8 | **FREERTOS → Advanced Settings** | `USE_NEWLIB_REENTRANT` **1** | Üç görev de `vsnprintf` çağırıyor; newlib'in global durumu (errno vb.) görev başına ayrılır |
| C-7 | **FREERTOS config** | `TOTAL_HEAP_SIZE` **16384**, `CHECK_FOR_STACK_OVERFLOW` **2**, `USE_MALLOC_FAILED_HOOK` **1**, `GENERATE_RUN_TIME_STATS` **1**, `USE_APPLICATION_TASK_TAG` **1** | SYS-03/04/05, TIM-06/07 |

> 💡 **Neden kesme önceliği 6?** Cortex-M4'te **küçük sayı = yüksek öncelik**. FreeRTOS'ta `configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY = 5` tanımlı; bu, "FreeRTOS API'sini (`...FromISR`) çağırabilecek en yüksek öncelik 5'tir" demek. 0–4 arası kesmeler RTOS'un kritik bölgelerinde bile kesebilir, ama RTOS fonksiyonu çağıramaz. Üç kesmemiz de `FromISR` çağırdığı için ≥5 olmalı. 6 seçtik ki 5 ileride daha acil bir iş için boş kalsın.

> 💡 **Neden örnekleme 640.5 cycle?** Dahili sıcaklık sensörünün çıkış empedansı yüksektir ve datasheet en az ~5 µs örnekleme süresi ister. ADC saati 64 MHz'de 640.5 cycle ≈ 10 µs eder, güvenli taraftadır. Bu sürenin gerçekte ne kadar tuttuğu TSK-08 gereği ölçülecek.

---

## 4. Zaman sayacı (`app_ts`)

**Karar: TIM2, 1 MHz, 32-bit.** 1 tık = 1 µs, taşma süresi 2³² µs ≈ 71,6 dk.

```c
static inline uint32_t ts_now(void) { return TIM2->CNT; }   // tek bir 32-bit okuma
// Aralık hesabı her zaman işaretsiz çıkarmayla yapılır:
uint32_t d = t_end - t_start;    // sayaç arada bir kez taşsa bile doğru sonuç verir
```

| Seçenek | Çözünürlük | Taşma | Ayar | Değerlendirme |
|---|---|---|---|---|
| **TIM2 @ 1 MHz** | 1 µs | 71,6 dk | CubeMX C-4 | Seçildi. µs birimi doğrudan CSV'ye gider, run-time stats ile aynı saat |
| DWT CYCCNT | 12,5 ns | 53,7 s | Kodla açılır | Koşu boyunca birkaç kez taşar. Yalnızca kanca ek yükünü ölçmek için kullanılacak (TIM-12) |
| FreeRTOS tick | 1 ms | — | — | Yetersiz |

Run-time stats aynı sayacı kullanır:
```c
#define portCONFIGURE_TIMER_FOR_RUN_TIME_STATS()   /* TIM2 main() içinde başlatıldı */
#define portGET_RUN_TIME_COUNTER_VALUE()           (TIM2->CNT)
```

Karşıladığı: TIM-01, TIM-04, TIM-06.

---

## 5. RTOS nesneleri

Görevler CubeMX tarafından `osThreadNew` (CMSIS-v2) ile oluşturulur (C-6). Giriş fonksiyonları (`StartTelemetryTask`, `StartButtonTask`, `StartUartTxTask`) *As external* seçildiği için CubeMX yalnızca bildirimlerini üretir; gövdeleri bizim `app_*.c` dosyalarımızda. Her görev ilk satırında kendi tag'ini `vTaskSetApplicationTaskTag(NULL, tag)` ile ayarlar. Kuyruk, `main.c`'deki `USER CODE BEGIN RTOS_QUEUES` bölümünde **doğal FreeRTOS API'si** (`xQueueCreate`) ile oluşturulur; bu bölüm görevler oluşturulmadan önce çalışır.

> 💡 **"As external" ne demek?** CubeMX görev fonksiyonunun gövdesini üretmez, yalnızca `extern` bildirimini yazar. Fonksiyonu biz yazmazsak derleme bağlama (link) aşamasında hata verir, yani görev gövdesinin unutulması imkânsızdır. "Default" seçilseydi CubeMX `main.c` içine boş bir gövde koyardı ve kodumuz CubeMX'in yönettiği dosyaya karışırdı.

| Nesne | Öncelik | Stack (word) | Not |
|---|---|---|---|
| `TelemetryTask` | 40 (`osPriorityHigh`) | 384 | tag = 1 |
| `ButtonTask` | 32 (`osPriorityAboveNormal`) | 256 | tag = 2 |
| `UartTxTask` | 24 (`osPriorityNormal`) | 512 | tag = 3; `snprintf` ve `uxTaskGetSystemState` kullanır |
| Timer servis görevi | 2 | 256 | CubeMX varsayılanı, kullanılmıyor |
| `txQueue` | — | — | derinlik `TXQ_DEPTH = 16`, öğe `tx_item_t` (68 B) |

```c
typedef enum { MSG_TEL = 1, MSG_BTN = 2 } msg_type_t;
typedef struct {
    uint8_t  type;        // msg_type_t
    uint8_t  scn;         // 0..5
    uint16_t event_id;    // BTN için; TEL'de 0
    char     frame[64];   // hazır, dolgulu, LF ile biten çerçeve
} tx_item_t;              // 68 bayt
```

> 💡 **Öncelik değerleri neden 40/32/24?** Projede `configMAX_PRIORITIES = 56` ve CMSIS-v2 adlandırılmış seviyeler kullanıyor. FreeRTOS'ta **büyük sayı = yüksek öncelik** (kesmelerin tersi!). CMSIS adlarını kullanmak kodu okunur yapar.

> 💡 **Kuyruk derinliği neden 16?** Kuyruğa yalnızca TEL ve BTN girer. 16 öğe × 68 B = 1088 B RAM. Bu bir **başlangıç değeri**; gerçek en yüksek doluluk her koşuda ölçülüp (QUE-05) SUM çerçevesinde raporlanır. Ölçüm küçük bir değer gösterirse ileride düşürülebilir.

**Heap bütçesi (tahmini, SYS-04 ile doğrulanacak):**
Görev stack'leri ve TCB'ler **statik** ayrılır (C-6, *Allocation = Static*): `main.c`'deki `…TaskBuffer[]` dizileri derleme zamanında RAM'e yerleşir, heap'ten alınmaz. Heap'ten yalnızca kuyruk (~1,2 KB) ve CMSIS/kernel nesneleri alınır. Idle ve timer görevlerinin belleği de `configSUPPORT_STATIC_ALLOCATION` sayesinde statiktir. `TOTAL_HEAP_SIZE = 16384` bu yüzden bol pay bırakır; gerçek kullanım MEM çerçevesinde ölçülür.

> 💡 **Statik ayırmanın faydası:** Bellek yerleşimi derlemede belli olur, linker haritasında (`.map`) görünür. Çalışma anında "heap bitti, görev oluşturulamadı" diye bir hata olamaz.

Karşıladığı: SYS-01/02/03/04, QUE-01/04.

---

## 6. Senaryo ve koşu durumu (`app_run`)

```c
typedef struct { uint16_t period_ms; uint16_t load_us; } scn_cfg_t;
static const scn_cfg_t SCN[6] = {
    {   0,    0 },  // S0  telemetri kapalı
    { 100,    0 },  // S1  10 Hz
    {  20,    0 },  // S2  50 Hz
    {  10,    0 },  // S3  100 Hz
    {  10, 2000 },  // S4  100 Hz + ≈2 ms
    {  10, 5000 },  // S5  100 Hz + ≈5 ms
};
```

```
          CMD,SCN,n (yalnızca IDLE/STOPPED)
            ┌──────┐
            ▼      │
 ┌──────┐ START ┌─────────┐ STOP ┌─────────┐
 │ IDLE │──────▶│ RUNNING │─────▶│ STOPPED │──┐ DUMP (tekrar edilebilir)
 └──────┘       └─────────┘      └─────────┘◀─┘
                     ▲                │ START (sayaçlar ve kayıtlar sıfırlanır)
                     └────────────────┘
```

- **START:** sayaçları ve kayıt dizisini sıfırlar, run-time stats anlık görüntüsünü alır, `run_active = true` yapar, TelemetryTask'ı bildirimle uyandırır, `ACK,START,S<n>` gönderir.
- **STOP:** `run_active = false` yapar (ISR ve TelemetryTask artık üretmez), kuyruk boşalana kadar göndermeye devam eder, run-time stats'in ikinci anlık görüntüsünü alır, `ACK,STOP` gönderir.
- **Buton her durumda algılanır** (TSK-05a). Debounce, ISR, ButtonTask ve kuyruk yolu her durumda aynıdır; yalnızca RUNNING'de bir ölçüm kaydı açılır ve `event_id` 1'den sayar. IDLE/STOPPED'daki basışlar `BTN,0,S<n>,PRESSED` olarak gider ve döküme girmez.

> 💡 **Run-time stats neden iki anlık görüntüyle ölçülüyor?** FreeRTOS görev başına toplam çalışma süresini açılıştan beri biriktirir ve sıfırlanamaz. START ve STOP'ta `uxTaskGetSystemState()` ile iki görüntü alıp farkını almak, yalnızca koşunun kendisini verir. Bu çağrı scheduler'ı kısa süre durdurur; bu yüzden koşu dışında yapılıyor.

Karşıladığı: SCN-01/03, MSG-07/08, TIM-06.

---

## 7. Görevler ve ISR'lar

### 7.1 Buton ISR (t₀)

t₀'ın gerçekten ISR girişinde alınması için sayaç, HAL'in kesme yöneticisinden **önce** okunur:

```c
// stm32l4xx_it.c
void EXTI15_10_IRQHandler(void) {
    /* USER CODE BEGIN EXTI15_10_IRQn 0 */
    g_exti_ts = ts_now();                       // t₀ adayı
    /* USER CODE END EXTI15_10_IRQn 0 */
    HAL_GPIO_EXTI_IRQHandler(B1_Pin);           // bayrağı temizler, callback'i çağırır
}

// app_button.c
void HAL_GPIO_EXTI_Callback(uint16_t pin) {
    if (pin != B1_Pin) return;
    uint32_t t0 = g_exti_ts;
    if ((uint32_t)(t0 - s_last_accept) < DEBOUNCE_US) { s_bounce_rejected++; return; }
    s_last_accept = t0;
    if (run_active) meas_event_begin(t0);       // yalnızca koşuda: event_id++, kayıt açılır, "ready" penceresi başlar
    else            meas_event_none();          // koşu dışı: kayıt yok, event_id = 0
    BaseType_t hpw = pdFALSE;
    vTaskNotifyGiveFromISR(h_button, &hpw);
    portYIELD_FROM_ISR(hpw);                    // ButtonTask'ı hemen Ready yap
}
```

`DEBOUNCE_US = 50000`. B1 butonu NUCLEO'da harici pull-up ile aktif-düşük; basış = düşen kenar.

> 💡 **`portYIELD_FROM_ISR` ne yapar?** Bildirim ButtonTask'ı Ready yapar. Bu görev o an koşandan daha yüksek öncelikliyse (ör. UartTxTask koşuyorsa), ISR'dan çıkılır çıkılmaz ona geçilir. Değilse (TelemetryTask koşuyorsa) ButtonTask sırasını bekler. Bekleme süresi tam olarak `ready_wait_us`'tür.

Karşıladığı: ISR-01/02/03/04, TIM-02.

### 7.2 TelemetryTask

```c
for (;;) {
    // S0'da ya da koşu dışında CPU harcamadan bloklu bekle
    while (!run_active || SCN[scn].period_ms == 0) ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
    TickType_t last = xTaskGetTickCount();
    uint32_t seq = 0;
    while (run_active) {
        vTaskDelayUntil(&last, pdMS_TO_TICKS(SCN[scn].period_ms));   // mutlak periyot
        uint32_t a = ts_now();  int16_t t_x10 = adc_read_temp_x10();  stat_add(&adc_us, ts_now() - a);
        if (SCN[scn].load_us) { uint32_t b = ts_now(); cpu_load_run(); stat_add(&load_us, ts_now() - b); }
        tx_item_t it = { MSG_TEL, scn, 0 };
        frame_build(it.frame, "TEL,%lu,S%u,%d", seq++, scn, t_x10);
        if (xQueueSend(txQueue, &it, 0) != pdPASS) tel_dropped++;    // asla bloklanmaz
        else { tel_sent++; qhw_update(); }
    }
}
```

**CPU yükü (`cpu_load_run`)** gerçek bir hesaplama döngüsüdür (bir tamsayı karma fonksiyonu), bekleme döngüsü değildir. Açılışta kalibre edilir: döngü N iterasyonla koşturulup süresi ölçülür ve hedef süreye (`load_us`) karşılık gelen iterasyon sayısı hesaplanır. Her çalıştırmanın gerçek süresi ölçülüp `CAL` çerçevesinde raporlanır (TSK-03). Kalibrasyon bir kere yapılır; kesmeler gerçek süreyi biraz uzatabilir, ölçüm bunu da gösterir.

> 💡 **`vTaskDelayUntil` ile `vTaskDelay` farkı:** `vTaskDelay(10)` "şimdiden itibaren 10 ms uyu" der. Görevin çalışma süresi (ADC + CPU yükü) periyoda eklenir ve frekans kayar. `vTaskDelayUntil(&last, 10)` "bir önceki uyanıştan 10 ms sonra uyan" der. Böylece periyot, iş süresinden bağımsız sabit kalır.

**Sıcaklık hesabı** (fabrika kalibrasyonu 3,0 V VDDA'da yapılmıştır; NUCLEO'da VDDA = 3,3 V):
```c
// Adres ve sıcaklık sabitleri stm32l4xx_ll_adc.h'den alınır; elle yazılmaz.
// STM32L476 için: CAL1 = 30 °C @0x1FFF75A8, CAL2 = 110 °C @0x1FFF75CA (datasheet'ten doğrulanacak)
int32_t cal1 = *TEMPSENSOR_CAL1_ADDR, cal2 = *TEMPSENSOR_CAL2_ADDR;
int32_t raw_cal = raw * 3300 / TEMPSENSOR_CAL_VREFANALOG;       // 3,3 V ölçeğinden 3,0 V ölçeğine
int16_t t_x10 = (int16_t)((raw_cal - cal1) * (TEMPSENSOR_CAL2_TEMP - TEMPSENSOR_CAL1_TEMP) * 10
                          / (cal2 - cal1) + TEMPSENSOR_CAL1_TEMP * 10);
```
> ⚠️ İkinci kalibrasyon noktasının sıcaklığı STM32L4 ailesinde modele göre değişir (110 °C veya 130 °C). Bu yüzden değer elle yazılmıyor, HAL/LL başlığındaki sabit kullanılıyor.
ADC her okumada yazılım tetikli tek dönüşüm + polling (`HAL_ADC_PollForConversion`) ile okunur. Açılışta bir kez `HAL_ADCEx_Calibration_Start` çağrılır.

Karşıladığı: TSK-01/02/03/04/08, QUE-02/05.

### 7.3 ButtonTask

```c
for (;;) {
    ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
    meas_t1();                                   // t₁ — ready penceresi kapanır, exec penceresi açılır (kayıt yoksa işlem yapmaz)
    uint16_t id = meas_current_id();             // koşu dışında 0
    tx_item_t it = { MSG_BTN, scn, id };
    frame_build(it.frame, "BTN,%u,S%u,PRESSED", id, scn);
    meas_t2();                                   // t₂ — exec penceresi kapanır, tx penceresi açılır
    if (xQueueSend(txQueue, &it, pdMS_TO_TICKS(BTN_SEND_TIMEOUT_MS)) != pdPASS) {
        btn_dropped++; meas_mark_lost();         // zincir t₂'de biter (TIM-02a)
    } else qhw_update();
}
```

`BTN_SEND_TIMEOUT_MS = 10`.

**Tek slot yeterli mi?** Debounce iki kabul edilen olay arasında en az 50 ms bırakır. ButtonTask işini bitirmeden ikinci bir olay gelirse `ulTaskNotifyTake`'in sayacı bunu gösterir (>1); bu durum `btn_overrun` olarak sayılır.

Karşıladığı: TSK-05, TSK-05a, QUE-03, TIM-02/02a.

### 7.4 UartTxTask

```c
for (;;) {
    cmd_poll();                                          // RX ring buffer'daki satırları işle
    tx_item_t it;
    if (xQueueReceive(txQueue, &it, pdMS_TO_TICKS(10)) == pdPASS) {
        if (it.type == MSG_BTN) meas_t3(it.event_id);    // t₃ — tx penceresi kapanır
        uart_send_frame(it.frame, it.type == MSG_BTN ? it.event_id : 0);
    }
}

static void uart_send_frame(const char *f, uint16_t btn_event) {
    s_tx_btn_event = btn_event;                          // TC callback'i hangi olaya t₄ yazacağını bilir
    HAL_UART_Transmit_DMA(&huart2, (uint8_t*)f, 64);
    ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(20));         // TC'yi bekle (bloklanma, kesilme değil)
}

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *h) {     // USART2 TC kesmesi
    if (s_tx_btn_event) meas_t4(s_tx_btn_event, ts_now());   // t₄
    BaseType_t hpw = pdFALSE;
    vTaskNotifyGiveFromISR(h_uart_tx, &hpw);
    portYIELD_FROM_ISR(hpw);
}
```

`xQueueReceive`'in 10 ms zaman aşımı, kuyruk boşken bile komutların en geç 10 ms içinde işlenmesini sağlar.

> 💡 **t₄ gerçekten "son bit" anı mı?** HAL'de DMA tamamlandığında (son bayt UART'ın veri kaydına kopyalandığında) henüz iletim bitmemiştir. HAL bu noktada UART'ın **TC** (Transmission Complete) kesmesini açar. TC, son baytın stop biti de hattan çıkınca gelir ve `HAL_UART_TxCpltCallback` o zaman çağrılır. Yani t₄ kurs tanımındaki gibi "son bitten sonra callback'in bunu gördüğü an"dır. Bu yüzden C-2'de USART2 kesmesi açılıyor.

Karşıladığı: TSK-06/07, TIM-02/02b, TIM-05.

### 7.5 UART RX ve komutlar (`app_cmd`)

- `HAL_UART_Receive_IT(&huart2, &rx_byte, 1)` ile tek bayt alınır; `HAL_UART_RxCpltCallback` baytı 128 B'lik ring buffer'a yazar ve alımı yeniden kurar. ISR'da ayrıştırma yapılmaz.
- `cmd_poll()` (UartTxTask) LF'ye kadar satır toplar ve ayrıştırır:

| Komut | Geçerli durum | Yanıt |
|---|---|---|
| `CMD,SCN,<0-5>` | IDLE, STOPPED | `ACK,SCN,S<n>` / `NAK,BUSY` / `NAK,ARG` |
| `CMD,START` | IDLE, STOPPED | `ACK,START,S<n>` / `NAK,BUSY` |
| `CMD,STOP` | RUNNING | `ACK,STOP` / `NAK,STATE` |
| `CMD,DUMP` | STOPPED | `ACK,DUMP,<n_rec>` + döküm çerçeveleri (§9) + `END,DUMP` |
| diğer | — | `NAK,CMD` |

Karşıladığı: MSG-07/08, Q-06 kararı.

---

## 8. Ölçüm altyapısı (`app_meas`)

### 8.1 Kayıt yapısı

```c
typedef struct {
    uint16_t event_id;  uint8_t scn;  uint8_t lost;
    uint32_t t0, t1, t2, t3, t4;
    uint32_t ready_wait_us;   uint8_t ready_wait_task;      // en çok CPU alan görevin tag'i
    uint32_t bt_exec_us;      uint8_t bt_n_preempt;  uint32_t bt_preempt_us;
    uint8_t  tx_n_preempt;    uint32_t tx_preempt_us;
} meas_rec_t;                                                // ~48 B
static meas_rec_t s_rec[MEAS_CAP];                           // MEAS_CAP = 64 → ~3 KB statik RAM
```

Kapasite dolarsa `rec_overflow++` (TIM-03).

### 8.2 Görev değiştirme kancaları

`FreeRTOSConfig.h` içindeki `USER CODE` bölümüne:
```c
#include "app_meas_hooks.h"
#define traceTASK_SWITCHED_OUT()  meas_hook_out(pxCurrentTCB)
#define traceTASK_SWITCHED_IN()   meas_hook_in(pxCurrentTCB)
```
Bu makrolar `tasks.c` içinde açılır. O yüzden `pxCurrentTCB` ve hazır listelerine erişebilirler.

**Görev kimliği:** Her görevin *application task tag*'i (`vTaskSetApplicationTaskTag`) 1/2/3 olarak ayarlanır. Kanca `pxCurrentTCB->pxTaskTag`'e bakar; 0 ise görev "diğer" sayılır (idle, timer).

**Kesilme mi, bloklanma mı (TIM-10)?** Kanca SWITCHED_OUT anında görevin durum liste öğesinin hangi listede olduğuna bakar:
```c
bool preempted = listLIST_ITEM_CONTAINER(&tcb->xStateListItem)
               == &pxReadyTasksLists[tcb->uxPriority];   // hâlâ Ready listesinde → kesildi
```
Görev bir kuyruk, bildirim veya gecikme beklediği için CPU'yu bıraktıysa bu öğe gecikme listesinde ya da askı listesindedir, yani bloklanmıştır.

> ⚠️ Bu yöntem FreeRTOS'un iç yapılarına (10.3.1) dayanır. Kernel sürümü değişirse kontrol edilmesi gerekir. Bu not `code-notes.md`'ye de yazılacak.

**Üç ölçüm penceresi:**

| Pencere | Açılır | Kapanır | Kancada ne yapılır |
|---|---|---|---|
| READY | t₀ (ISR) | t₁ | ButtonTask dışındaki bir görev SWITCHED_IN olunca giriş zamanı tutulur; SWITCHED_OUT olunca süresi o görevin tag'ine eklenir. t₀ anında zaten koşan görev için giriş zamanı = t₀. |
| BTN_EXEC | t₁ | t₂ | ButtonTask *kesilerek* çıkarsa `pre_start` tutulur, `bt_n_preempt++`; geri girince `bt_preempt_us += now − pre_start`. Kapanışta `bt_exec_us = (t₂−t₁) − bt_preempt_us`. |
| TX_WAIT | t₂ | t₃ | Aynı mantık UartTxTask için: yalnızca *kesilerek* çıkışlar sayılır; DMA/kuyruk beklemesi (bloklanma) sayılmaz. |

Pencereler aynı anda en fazla birer olay için açıktır (debounce bunu garanti eder). Kancalar yalnızca pencere açıkken iş yapar; değilse tek bir `if` ile döner.

> 💡 **Bu kancalar nerede çalışıyor?** Görev değişimi Cortex-M'de **PendSV** kesmesinde yapılır ve kancalar da orada çağrılır. Bu yüzden kısa olmaları çok önemli: burada geçen her µs, bütün sistemdeki her görev değişimine eklenir. Kanca işi bir `TIM2->CNT` okuması + birkaç RAM yazmasıyla sınırlı tutuluyor.

### 8.3 Kanca ek yükü (TIM-12)

Açılışta, kesmeler kapalıyken, kanca gövdeleri sahte bir TCB ile 1000 kez çağrılır ve süre **DWT CYCCNT** (12,5 ns çözünürlük) ile ölçülür. Ortalama giriş+çıkış maliyeti ns cinsinden `CAL` çerçevesinde raporlanır.

Karşıladığı: TIM-03/04/07/08/09/10/11/12.

---

## 9. Çerçeve biçimleri

Tüm çerçeveler `frame_build()` ile üretilir:
```c
bool frame_build(char out[64], const char *fmt, ...) {
    char tmp[80];
    int n = vsnprintf(tmp, sizeof tmp, fmt, args);
    if (n < 0 || n > 63) { frame_err++; configASSERT(0); return false; }  // kesme yok (MSG-02)
    memcpy(out, tmp, n);  memset(out + n, ' ', 63 - n);  out[63] = '\n';
    return true;
}
```

**Koşu sırasında giden çerçeveler:**

| Tip | Biçim | Örnek |
|---|---|---|
| TEL | `TEL,<seq>,S<n>,<temp_x10>` | `TEL,1042,S3,263` |
| BTN | `BTN,<event_id>,S<n>,PRESSED` | `BTN,17,S3,PRESSED` |
| ACK/NAK | `ACK,<cmd>[,<arg>]` / `NAK,<reason>` | `ACK,START,S3` |

**Sürüm çerçevesi (MSG-09):** açılışta UartTxTask'ın ilk işi ve her DUMP'ta `ACK,DUMP`'tan hemen sonra:

| Tip | Biçim | Örnek |
|---|---|---|
| VER | `VER,<git_hash>,<Debug\|Release>,<test_flags_hex>` | `VER,a1b2c3d,Release,00` |

`git_hash` derleme öncesi adımda üretilen `build_info.h` dosyasından gelir. STM32CubeIDE *Properties → C/C++ Build → Settings → Build Steps → Pre-build* komutu `git rev-parse --short HEAD` çıktısını `#define BUILD_GIT_HASH "..."` olarak yazar; çalışma dizininde commit edilmemiş değişiklik varsa hash'in sonuna `+` eklenir. `build_info.h` repoya girmez (`.gitignore`). Derleme türü `DEBUG` makrosundan, `test_flags` ise §3'teki `TEST_*` bayraklarının bit maskesinden (bit0 QFULL, bit1 MEAS_CAP, bit2 LONG_FRAME, bit3 STACK_OVF) hesaplanır.

**DUMP ile giden çerçeveler** (sıra: `ACK,DUMP` → VER → REC/PRE çiftleri → SUM → CAL → MEM → RTS × görev sayısı → `END,DUMP`):

| Tip | Biçim | En uzun hâli |
|---|---|---|
| REC | `REC,<id>,S<n>,<t0>,<t1−t0>,<t2−t1>,<t3−t2>,<t4−t3>,<lost>` | 57 karakter |
| PRE | `PRE,<id>,<ready_wait_us>,<rw_task>,<bt_exec_us>,<bt_n_pre>,<bt_pre_us>,<tx_n_pre>,<tx_pre_us>` | 51 karakter |
| SUM | `SUM,S<n>,<events>,<tel_sent>,<tel_dropped>,<btn_dropped>,<q_hw>,<rec_overflow>,<bounce_rej>,<frame_err>` | ~50 |
| CAL | `CAL,<load_target_us>,<load_mean_us>,<load_max_us>,<adc_mean_us>,<hook_ns>` | ~40 |
| MEM | `MEM,<min_free_heap>,<hw_tel>,<hw_btn>,<hw_tx>` (high-water word cinsinden) | ~30 |
| RTS | `RTS,<task_name>,<run_us>,<pct_x10>` | ~40 |

Tüm biçim dizgeleri tek yerde, `app_frame.h` içinde `FMT_*` makroları olarak tanımlıdır; `uint32_t` alanlar taşınabilirlik için `PRIu32` ile yazılır. REC'teki her fark en fazla `REC_DELTA_MAX = 9 999 999` µs (7 hane) olabilir; daha büyük bir değer ölçüm hatasıdır ve bu değere doyurulur. SUM'da `tel_sent`/`tel_dropped` 32-bit, diğer sayaçlar 16-bit'tir. Bu sınırlarla her biçimin 63 karaktere sığdığı TC-U06 ile doğrulanır.

REC'te t₁…t₄ mutlak değil, **fark** olarak gönderilir: böylece 63 bayta sığar. PC mutlak değerleri t₀'a farkları ekleyerek geri kurar. `rw_task` tek harf: `T`/`B`/`U`/`O` (other).

Karşıladığı: MSG-01…MSG-06, MSG-09, TIM-06, SYS-04.

---

## 10. Hata ve güvenlik kancaları

| Kanca | Davranış |
|---|---|
| `vApplicationStackOverflowHook` | Kesmeleri kapatır, LD2 10 Hz yanıp söner (SYS-05) |
| `vApplicationMallocFailedHook` | Aynı, 2 Hz |
| `configASSERT` | Mevcut tanım (kesmeleri kapat + sonsuz döngü); debug'da hata anında durur |

---

## 11. PC arayüzü (`interface/`)

**Teknoloji:** Python 3.11+, PySide6, pyqtgraph, pyserial. Sürümler `interface/requirements.txt` içinde sabitlenir.

```
interface/
├── requirements.txt
├── uart_monitor.py          ← giriş noktası
└── uart_monitor/
    ├── serial_worker.py     ← QThread: baytları oku, LF'de böl, 64 B doğrula
    ├── protocol.py          ← çerçeve ayrıştırıcıları (TEL, BTN, ACK, REC, PRE, ...)
    ├── session.py           ← koşu durumu, sayaçlar, TEL sıra boşluğu tespiti, döküm birleştirme
    ├── csv_writer.py        ← measurements/S<n>.csv
    └── main_window.py       ← arayüz
```

**Ekran düzeni:**
```
┌ Port [COM5 ▾] [↻] [Bağlan] ─── Senaryo [S3 ▾] [Başlat] [Durdur] [Döküm al] ─ ● Bağlı ┐
├──────────────────────────────────────────┬────────────────────────────────────────────┤
│  S3 · Telemetri 100 Hz · RUNNING         │  Butona basıldı · Olay 17                  │
│  ┌ Sıcaklık (°C) — canlı ─────────────┐  │  BTN,17,S3,PRESSED                          │
│  │                                    │  │                                             │
│  └────────────────────────────────────┘  │  Kayıplar                                   │
│  son: TEL,1042,S3,263                    │   PC (sıra boşluğu) 0 · tel_dropped 0       │
│                                          │   btn_dropped 0 · bozuk çerçeve 0           │
├──────────────────────────────────────────┴────────────────────────────────────────────┤
│  [Sonuçlar]  olay başına yığılmış çubuk: EventToRun │ ButtonExec │ QueueWait │ UartTx    │
│              + ButtonExec için exec / preempt ayrımı; kayıp olaylar kırmızı işaret      │
│  Ölçüm dosyası: measurements/S3.csv                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

**"Ölçüme karışmama" kuralları (UI-09):**
- Koşu sırasında arayüz yalnızca `CMD,STOP` gönderebilir; diğer düğmeler kapalıdır.
- Hiçbir süre PC'nin alış zamanından hesaplanmaz; tüm süreler REC/PRE'deki MCU damgalarından gelir.
- Seri okuma ayrı bir iş parçacığında yapılır, böylece grafik çizimi yavaşlasa bile baytlar kaybolmaz.

**Çerçeve hizalama (UI-02):** Okuyucu LF'ye kadar biriktirir. Toplam uzunluk 64 değilse ya da tip bilinmiyorsa çerçeve `bad_frames` olarak sayılır ve atılır; bir sonraki LF'den itibaren akış kendiliğinden yeniden hizalanır.

**Çevrimdışı analiz (`analysis/analyze.py`):** pandas + matplotlib ile `S0..S5.csv` dosyalarını okur ve şunları üretir:
- `summary.csv`
- `plots/latency_boxplot.png` (senaryo başına `d_Total` dağılımı)
- `plots/breakdown_S<n>.png` (aralık bileşenleri)
- `plots/preemption.png` (`bt_preempt_us`, `ready_wait_us`)

Karşıladığı: UI-01…UI-10.

---

## 12. Kod üretimi sırası (Implementation adımları)

Her adım ayrı bir commit ve kendi mini doğrulamasıyla tamamlanacak:

1. **Repo düzeni:** `project/` → `firmware/`, `.gitignore`, iskelet klasörler.
2. **CubeMX değişiklikleri** C-1…C-8 + boş görev gövdeleri (`app_tasks_stub.c`) → derle.
3. **`app_ts` + `app_frame`** → TEL çerçevesini sabit periyotta gönder (DMA'sız bile olur); PC'de 64 B çerçeve görülür.
4. **Kuyruk + UartTxTask (DMA + TC) + komut kanalı (§7.5) + TelemetryTask (ADC sıcaklık dahil)** → S1–S3. Komut kanalı 9. adımdan buraya alındı: kart üstü testler koşuyu komutla başlatıp SUM ile doğrulayabilsin diye.
5. **ButtonTask + ISR + debounce** → BTN çerçeveleri.
6. **`app_meas`:** t₀…t₄ → REC dökümü.
7. **Trace kancaları** → PRE, kanca ek yükü (CAL).
8. **CPU yükü, run-time stats, MEM, CAL** → S4/S5, SUM/CAL/MEM/RTS.
9. **PC arayüzü:** bağlantı + canlı görünüm → komut düğmeleri → döküm + CSV → grafikler.
10. **`analyze.py`**, `README.md`, `docs/*.md`.

---

## 13. İzlenebilirlik (gereksinim → tasarım)

| Gereksinim | Tasarım bölümü |
|---|---|
| SYS-01…05 | §3 (C-6, C-7, C-8), §5, §10 |
| TSK-01…04, TSK-08 | §6, §7.2 |
| TSK-05, TSK-05a | §6, §7.1, §7.3 |
| TSK-06, TSK-07 | §7.4 |
| ISR-01…04 | §3 (C-1), §7.1 |
| QUE-01…05 | §5, §7.2, §7.3 |
| MSG-01…09 | §7.5, §9 |
| TIM-01, TIM-04 | §4 |
| TIM-02, 02a, 02b | §7.1, §7.3, §7.4 |
| TIM-03, TIM-05 | §6, §8.1, §9 |
| TIM-06 | §4, §6 |
| TIM-07…TIM-12 | §8.2, §8.3 |
| SCN-01…03 | §6 |
| UI-01…10 | §11 |
| DOC-01…06 | §2, §12 |

## 14. Açık tasarım soruları

| # | Konu | Öneri |
|---|---|---|
| DQ-1 | Koşu dışında butona basılırsa ne olsun? | **Kapandı:** her basış algılanır ve BTN gönderilir; kayıt yalnızca koşuda (TSK-05a, §6, §7.1) |
| DQ-2 | VDDA 3,3 V varsayımı | **Kapandı:** 3,3 V sabit kabul edilir (§7.2) |
| DQ-3 | Stack boyutları | **Kapandı:** §5'teki değerler onaylandı; MEM çerçevesi gerçek kullanımı gösterecek |

## 15. Değişiklik geçmişi

| Sürüm | Tarih | Değişiklik |
|---|---|---|
| 0.1 | 2026-09-25 | İlk taslak |
| 1.0 | 2026-09-25 | Kursiyer onayı; DQ-1…3 kapandı; buton her durumda algılanır |
| 1.1 | 2026-09-25 | VER çerçevesi ve `build_info.h` (MSG-09) |
| 1.2 | 2026-09-26 | Uygulamadan geri bildirim: görevler CubeMX'te *As external* olarak tanımlanır (CubeMX son görevi sildirmiyor, C-6); `USE_NEWLIB_REENTRANT` (C-8) |
| 1.3 | 2026-09-26 | Görevler statik ayrılır (*Allocation = Static*); heap bütçesi güncellendi |
| 1.4 | 2026-09-26 | UartTxTask *As weak* (CubeMX ilk görev için *As external* sunmuyor) |
| 1.5 | 2026-09-26 | Uygulama adımı 3: biçimler `app_frame.h`'de, REC fark doyurma sınırı, SUM alan genişlikleri (§9) |
| 1.6 | 2026-09-26 | §12: komut kanalı ve ADC okuma adım 4'e alındı |
