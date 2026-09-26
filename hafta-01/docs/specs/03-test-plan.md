# SPEC-03 · Test ve Kanıt Planı — Hafta 01

| Alan | Değer |
|---|---|
| Doküman | `hafta-01/docs/specs/03-test-plan.md` |
| Sürüm | 1.3 (ONAYLANDI — 2026-09-26) |
| Tarih | 2026-09-25 |
| Girdi | `01-requirements.md` v1.2, `02-design.md` v1.1 |
| Çıktı | `docs/test-results.md` (test sonuçları), `measurements/`, `analysis/` (kanıtlar) |

Bu doküman her gereksinimin **nasıl doğrulanacağını**, testin **ne zaman geçmiş sayılacağını** ve kanıtın **hangi dosyada duracağını** tanımlar. §9'daki izlenebilirlik tablosu, her gereksinimin en az bir testle karşılandığını gösterir.

---

## 1. Temel ilke: doğrulama ile gözlem ayrıdır

Bu projede iki tür sonuç var ve farklı ele alınıyor:

| Tür | Örnek | Geçti/kaldı var mı? |
|---|---|---|
| **Doğrulama:** sistem ve ölçüm aracı doğru çalışıyor mu? | Çerçeve 64 bayt mı, t₀ ≤ t₁ ≤ … ≤ t₄ mü, `d_ButtonExec = exec + preempt` tutuyor mu, 30 olay toplandı mı | **Evet.** Ölçüt açık ve önceden yazılı |
| **Gözlem:** sistem nasıl davranıyor? | `d_Total` kaç µs, S5'te `bt_preempt_us` ne kadar, `tel_dropped` kaç | **Hayır.** Sayılar ne çıkarsa kaydedilir. Yorum `gozlemler.md`'ye aittir |

> 💡 **Neden bu ayrım?** Gecikme değerleri için "şu kadar olmalı" diye ölçüt koysaydık iki sorun olurdu: ya sonuca önceden karar vermiş olurduk, ya da beklentiyi tutturmak için sistemi ayarlamaya başlardık. Doğrulama testleri ise "cetvelin doğru ölçtüğünü" garanti eder. Böylece ne çıkarsa ona güvenebilirsin.

---

## 2. Test seviyeleri

| Seviye | Kod | Nerede | Ne zaman | Araç |
|---|---|---|---|---|
| İnceleme | **R** | Kod, `.ioc`, dokümanlar | Her uygulama adımının sonunda | §4'teki kontrol listeleri |
| Birim testi (kartsız) | **U** | PC | Kod yazıldıkça, her commit'te | `firmware/tests_host/` (gcc + Makefile), `interface/tests/` (pytest) |
| Kart üstü test | **T** | NUCLEO + PC | İlgili uygulama adımı bitince | `interface/tools/hil_check.py` + operatör |
| Gösterim | **D** | Arayüz | Arayüz bitince | Operatör + ekran kaydı/görüntüsü |
| Deney (ölçüm kampanyası) | **E** | NUCLEO + arayüz | Tüm T testleri geçince | Arayüz + `analysis/analyze.py` |

> 💡 **Kartsız birim testi neden var?** Çerçeve biçimlendirme, sıcaklık formülü, debounce kararı ve sayaç taşması gibi saf hesaplar donanıma bağlı değil. Bunları PC'de `gcc` ile derleyip saniyeler içinde yüzlerce durumla test edebilirsin. Hata ararken kartı yükleyip buton basmaktan çok daha hızlı. Bunun için `app_frame.c` ve `app_ts` gibi modüllerde HAL çağrısı olmamalı; tasarım zaten böyle ayrılmıştı.

---

## 3. Test ortamı ve kayıt kuralları

**Donanım:** NUCLEO-L476RG, USB kablo (ST-LINK VCP), başka bağlantı yok.
**Yazılım:** STM32CubeIDE sürümü, Python sürümü ve `requirements.txt` her test raporunda yazılır.

**Derleme yapılandırması:**

| Yapılandırma | Kullanım | Test bayrakları |
|---|---|---|
| `Debug` (-O0) | Geliştirme, adım adım hata ayıklama, TC-T09/T16 | İsteğe bağlı |
| `Release` (-Os) | **Tüm ölçüm koşuları (E)** ve T testlerinin resmi sonuçları | **Hepsi kapalı** |
| `Release` + test bayrağı | Hata enjeksiyonu testleri (§5.4) | Tek bir bayrak açık |

> 💡 **Ölçüm neden Release'te yapılıyor?** -O0 derleme kodu birkaç kat yavaşlatır ve süreleri çarpıtır. Ölçtüğümüz şeyin, çalışacak gerçek kod olması gerekir. Hangi derlemeyle ölçtüğünü her kayıtta yazman şart: aynı deney Debug'da farklı sonuç verir.

**Test bayrakları** (`app_config.h`, varsayılan hepsi `0`):

| Bayrak | Etkisi | Kullanan test |
|---|---|---|
| `TEST_FORCE_QFULL` | Kuyruk derinliği 2, UartTxTask her çerçeveden sonra 50 ms bekler | TC-T13 |
| `TEST_MEAS_CAP` | Kayıt kapasitesi 64 yerine 4 | TC-T15 |
| `TEST_LONG_FRAME` | START'ta bir kez 70 karakterlik çerçeve üretmeye çalışır | TC-T16 |
| `TEST_STACK_OVF` | ButtonTask'ta bilerek büyük yerel dizi | TC-T18 |

**Her test kaydında bulunacaklar:** tarih, git commit kısa hash'i, derleme yapılandırması + açık test bayrakları, sonuç (GEÇTİ/KALDI), kanıt dosyası bağlantısı.

---

## 4. İnceleme (R) testleri

### TC-R01 · Firmware kod incelemesi
Kontrol listesi (her madde için `docs/test-results.md`'ye ✓/✗ + dosya:satır):

1. Yalnızca 3 uygulama görevi var; `defaultTask` oluşturulmuyor. *(SYS-01)*
2. Öncelikler 40 > 32 > 24. *(SYS-02)*
3. TEL formatı sıra no + senaryo + sıcaklık içeriyor. *(TSK-02, MSG-03)*
4. BTN formatı `BTN,<id>,S<n>,PRESSED`. *(MSG-04)*
5. Görev döngülerinde `while(flag);` türü meşgul bekleme yok; tek istisna `cpu_load_run`. *(TSK-07)*
6. ISR yalnızca damga + debounce + `vTaskNotifyGiveFromISR` yapıyor; `snprintf`/UART yok. *(ISR-02)*
7. Kuyruk öğesi `tx_item_t` (tip + event_id + 64 B). Derinlik `TXQ_DEPTH` sabitinden geliyor. *(QUE-01, QUE-04)*
8. t₀…t₄ tam olarak §5.5.1'deki noktalarda alınıyor (t₂ `xQueueSend`'den önce, t₃ `HAL_UART_Transmit_DMA`'dan önce, t₄ `TxCpltCallback`'te). *(TIM-02)*
9. UartTxTask BTN'i `it.type` alanından tanıyor, çerçeve metnini ayrıştırmıyor. *(TIM-02b)*
10. Kesilme/bloklanma ayrımı Ready listesi kontrolüyle yapılıyor. *(TIM-10)*
11. PC arayüzünde hiçbir süre alış zamanından hesaplanmıyor. *(UI-09)*

### TC-R02 · CubeMX / NVIC incelemesi
`.ioc` ve üretilen `stm32l4xx_it.c`/`main.c` kontrolü: EXTI15_10, USART2, DMA1_Channel7 kesmeleri etkin ve öncelikleri ≥ 5 (tasarımda 6). TIM2 PSC = 79, ARR = 0xFFFFFFFF. ADC1 sıcaklık kanalı, örnekleme 640.5 cycle. FreeRTOS config C-7 değerleri. *(ISR-01, TIM-01)*
**Kanıt:** kontrol listesi + ilgili satırların kod bloğu olarak `code-notes.md`'de yer alması.

### TC-R03 · Dokümantasyon incelemesi
- `README.md` DOC-01'deki 5 başlığı içeriyor.
- `code-notes.md` ISR, görevler, UART tamamlanması ve zaman hesaplarını kod bloklarıyla anlatıyor, TIM-11 sınırlamasını yazıyor.
- `setup.md` ve `ai-usage.md` var.
- `report.md` 6 senaryonun sonuçlarını ve grafiklerini içeriyor.
- `.gitignore` `.metadata/ Debug/ Release/` içeriyor ve `git status` bunları göstermiyor.
- `git log --format='%an %s' -- hafta-01/gozlemler.md` yalnızca senin commit'lerini gösteriyor.

*(DOC-01…06, TIM-11)*

---

## 5. Birim testleri (U) — kartsız

`firmware/tests_host/` altında firmware'in saf C modülleri PC'de derlenir. `make test` tüm testleri çalıştırır ve özet yazar. Python tarafı `pytest interface/tests`.

| TC | Test edilen | Durumlar | Geçme ölçütü | Karşılar |
|---|---|---|---|---|
| **U01** | `frame_build` | 0, 1, 62, 63, 64, 70 karakter içerik | ≤63: çıktı tam 64 B, dolgu boşluk, `[63]=='\n'`. >63: `false` döner, `frame_err` +1, çıktı tamponu değişmez | MSG-01, MSG-02 |
| **U02** | Sıcaklık dönüşümü | Bilinen CAL1/CAL2 ve ham değerlerle 3 nokta | Elle hesaplanan değerle ±1 (0,1 °C) aynı | TSK-08 |
| **U03** | Debounce kararı | Aralık 0, 49 999, 50 000, 50 001 µs; sayaç taşmasına denk gelen aralık | <50 000 red, ≥50 000 kabul; taşmada da doğru karar | ISR-03, TIM-01 |
| **U04** | Aralık aritmetiği | `t_end < t_start` (taşma) | İşaretsiz çıkarma doğru farkı verir | TIM-01 |
| **U05** | Komut ayrıştırıcı + durum makinesi | §7.5 tablosundaki her satır + bozuk girdiler | Her girdi için beklenen ACK/NAK | MSG-07, MSG-08 |
| **U06** | En uzun çerçeveler | REC/PRE/SUM/CAL/MEM/RTS, tüm alanlar en büyük değerde | Hepsi ≤ 63 karakter | MSG-05, MSG-06 |
| **U07** | PC çerçeve ayrıştırıcı | Her tip; 63/65 baytlık bozuk çerçeve; ortada kesilmiş akış; TEL sırasında boşluk | Doğru tip ve alanlar; bozuklar sayılır; akış bir sonraki LF'de hizalanır; boşluk `pc_lost`'a eklenir | UI-02, UI-05 |
| **U08** | REC/PRE → CSV | Örnek döküm | Sütunlar §8 şemasında; t₁…t₄ geri kurulumu doğru; `lost=1` satırında t₃/t₄ boş | UI-07, TIM-02a |
| **U09** | `analyze.py` | Sentetik S0…S5 CSV'leri | `summary.csv` ve tüm PNG'ler üretilir; istatistikler elle hesapla aynı | UI-10 |

**Kanıt:** `make test` ve `pytest` çıktısı `docs/test-results/unit-<tarih>.txt` dosyasına kaydedilir.

---

## 6. Kart üstü testler (T)

Otomatik olanlar `hil_check.py --tc <ID>` ile çalışır. Betik komutları gönderir, çerçeveleri doğrular ve ham UART kaydını `docs/test-results/raw/<TC>-<tarih>.log` dosyasına yazar. **(Op)** işaretli adımları operatör yapar (buton basma, LED gözleme).

### 6.1 Temel işlev

| TC | Adımlar | Geçme ölçütü | Karşılar |
|---|---|---|---|
| **T01** Açılış | Kartı resetle → `CMD,START` → 5 s → `CMD,STOP` → `CMD,DUMP` | Açılışta tek bir `VER` çerçevesi gelir ve hash `git rev-parse --short HEAD` ile aynıdır. `ACK,START,S0` gelir (varsayılan S0, sistem ayakta, assert'e düşmemiş). DUMP içinde de aynı `VER` var | SYS-03, SCN-03, MSG-09 |
| **T02** Çerçeve bütünlüğü | S3, 60 s koşu | Alınan tüm çerçeveler 64 B ve LF ile bitiyor; `bad_frames = 0` | MSG-01, UI-02 |
| **T03** Telemetri periyodu | S1, S2, S3 için 60'ar s koşu | TEL `seq` 0'dan kesintisiz artıyor. `tel_sent + tel_dropped` = koşu süresi / periyot, **±%1** (süre PC'de ACK START–ACK STOP arasından) | TSK-01, TSK-02, SCN-01 |
| **T04** S0 sessizliği | S0, 30 s koşu, DUMP | Hiç TEL çerçevesi yok; RTS'de TelemetryTask payı < %0,1 | TSK-04 |
| **T05** CPU yükü kalibrasyonu | S4 ve S5, 30 s koşu, DUMP | CAL: `load_mean_us` hedefin (2000 / 5000) **±%10** içinde; `load_max_us` raporlanmış | TSK-03 |
| **T06** Sıcaklık | S1, 30 s | TEL değerleri oda sıcaklığı civarında (150…450, yani 15…45 °C) ve iki ardışık okuma farkı ≤ 2 °C; CAL'da `adc_mean_us` raporlanmış | TSK-08 |
| **T07** Buton her durumda | (Op) IDLE'da 2, RUNNING'de 3, STOPPED'da 2 kez bas | IDLE/STOPPED: `BTN,0,...`. RUNNING: `BTN,1`, `BTN,2`, `BTN,3`. DUMP'ta tam 3 REC | TSK-05, TSK-05a, UI-03 |
| **T08** Debounce | (Op) S0 koşusunda 20 kez, aralıklarla bas; basışları kendin say | Olay sayısı = 20; `bounce_rej` raporlanmış (0 da olabilir) | ISR-03 |
| **T09** ISR süresi | EXTI kesmesinin ilk ve son satırında DWT okuyan ölçüm (`APP_EXTI_TIMING_*`, her derlemede açık). **Release** derleme (-Os, hata ayıklama bilgisi -g3 ile); en az 20 basış; *Live Expressions*'da `g_btn_diag.isr_max_ns`. Debug'da da ölçülür ama yalnızca bilgi amaçlıdır | Release'te en büyük ISR süresi ≤ 5 µs (400 çevrim) | ISR-04 |
| **T10** Komut protokolü | Otomatik dizi: `SCN,3` → `START` → `SCN,2` → `STOP` → `STOP` → `DUMP` → `SCN,9` → `XYZ` | Sırasıyla ACK, ACK, **NAK,BUSY**, ACK, **NAK,STATE**, ACK…END, **NAK,ARG**, **NAK,CMD** | MSG-07, MSG-08 |
| **T11** Koşu sırasında sessizlik | T02'nin kaydı | START ile STOP arasında yalnızca TEL/BTN/ACK tipleri var | TIM-05 |
| **T12** Döküm bütünlüğü | (Op) S2 koşusunda 5 basış → STOP → DUMP → tekrar DUMP | 5 REC + 5 PRE + SUM + CAL + MEM + RTS + END. `SUM.events = 5`. Her olayda t₀ ≤ t₁ ≤ t₂ ≤ t₃ ≤ t₄. İki döküm bayt bayt aynı. Her olayda `t₄−t₃ ≥ 5555 µs` (64 bayt 115200 baud'da hatta en az 5,56 ms kalır; daha kısa bir değer t₃/t₄'ün yanlış çerçeveye bağlandığını gösterir — ölçüm aracının fiziksel tutarlılık kontrolü) | MSG-05, MSG-06, TIM-02 |
| **T14** Kuyruk doluluğu | T03'ün S3 koşusu | SUM'da `q_hw` raporlanmış ve 1 ≤ `q_hw` ≤ `TXQ_DEPTH` | QUE-04, QUE-05 |

### 6.2 Zaman ölçüm aracının doğrulanması

| TC | Adımlar | Geçme ölçütü | Karşılar |
|---|---|---|---|
| **T19** Sayaç frekansı | Açılış öz-testi: `vTaskDelay(1000)` öncesi/sonrası `ts_now()` farkı | 1 000 000 µs ± 1 000 (tick çözünürlüğü) → TIM2 gerçekten 1 MHz | TIM-01 |
| **T20** Damga ek yükü | Açılış öz-testi: `ts_now()` + RAM yazması 1000 kez, DWT ile | Ortalama ≤ 1 µs (80 cycle) | TIM-04 |
| **T21** Görev değişimi muhasebesi | S5 koşusu, (Op) 10 basış, DUMP | Her olay için: \|`d_ButtonExec` − (`bt_exec_us` + `bt_preempt_us`)\| ≤ 2 µs. `bt_preempt_us > 0` ⇒ `bt_n_preempt > 0`. `ready_wait_us` ≤ `d_EventToRun`. `tx_preempt_us` ≤ `d_QueueWait` | TIM-07, TIM-08, TIM-09 |
| **T22** Kesilme ≠ bloklanma | S0 koşusu, (Op) 10 basış, DUMP | Her olayda `tx_n_preempt = 0` ve `bt_n_preempt = 0` | TIM-10 |
| **T23** Kanca ek yükü | Herhangi bir DUMP | CAL'da `hook_ns` > 0 ve < 2000 | TIM-12 |
| **T24** Run-time stats | S3 koşusu, DUMP | Tüm görevler + IDLE için RTS var; yüzdelerin toplamı %100 ± 1 | TIM-06 |
| **T25** Öncelikler | Debug; CubeIDE *FreeRTOS Task List* görünümü | Öncelikler 40/32/24 ve görev adları doğru | SYS-02 |

> 💡 **T22 neden bir doğrulama testi, gözlem değil?** S0'da telemetri kapalı. UartTxTask'tan yüksek öncelikte çalışan tek görev ButtonTask, o da t₂'den hemen sonra bloklanıyor. Bu durumda UartTxTask'ın **kesilmesi** için bir sebep yok: CPU'yu bıraktığı her an DMA'yı ya da kuyruğu **beklediği** içindir. Kancalar bunu kesilme olarak sayıyorsa ölçüm aracında hata vardır. Yani burada sistemin davranışını değil, cetveli test ediyoruz.

> 💡 **T21'deki ±2 µs payı:** Sayaç 1 µs çözünürlükte. Bir aralık iki damganın farkı olduğu için her aralık ±1 µs yuvarlama taşır. Denklemde iki aralık karşılaştırılıyor, o yüzden pay 2 µs.

### 6.3 Bellek ve güvenlik

| TC | Adımlar | Geçme ölçütü | Karşılar |
|---|---|---|---|
| **T17** Bellek payı | S5, **10 dk** koşu, (Op) 30 basış, DUMP | MEM: `min_free_heap ≥ 1024`. Kullanılmayan stack: TelemetryTask ≥ 77, ButtonTask ≥ 52, UartTxTask ≥ 103 word (her biri stack'in %20'si) | SYS-04 |
| **T18** Stack taşması | Bayrak `TEST_STACK_OVF`; RUNNING'de butona bas | LD2 ~10 Hz yanıp sönüyor; sistem durmuş | SYS-05 |

### 6.4 Hata enjeksiyonu

> 💡 **Hata enjeksiyonu nedir?** Kayıp ve kuyruk-dolu yolları normal koşullarda hiç çalışmayabilir. Bu yollardaki bir hata ancak gerçekten kayıp olduğunda ortaya çıkar, yani en kötü anda. Bu yüzden durumu bilerek oluşturup kodun doğru davrandığını görüyoruz.

| TC | Adımlar | Geçme ölçütü | Karşılar |
|---|---|---|---|
| **T13** Kuyruk dolu | Bayrak `TEST_FORCE_QFULL`; S3, 20 s; (Op) 5 basış; DUMP | `tel_dropped > 0`. TEL `seq` atlamalı ama `tel_sent + tel_dropped` periyoda uyuyor (TelemetryTask bloklanmadı). `btn_dropped` = `lost=1` REC sayısı; bu olaylarda t₃/t₄ boş | QUE-02, QUE-03, TIM-02a |
| **T15** Kayıt kapasitesi | Bayrak `TEST_MEAS_CAP`; RUNNING'de (Op) 6 basış; DUMP | 4 REC, `rec_overflow = 2`; BTN çerçevelerinin 6'sı da gönderilmiş | TIM-03 |
| **T16** Uzun çerçeve | Bayrak `TEST_LONG_FRAME`. (a) Release: START. (b) Debug: START | (a) Kesik çerçeve **gönderilmez**, `frame_err = 1` (SUM). (b) Debugger `configASSERT`'te durur | MSG-02 |

---

## 7. Gösterim testleri (D) — arayüz

Her gösterim için kısa bir ekran kaydı ya da görüntü alınır: `docs/test-results/ui/`. Bunlar kanıtın **tamamlayıcısıdır**. Asıl kanıt CSV ve loglardır; slayttaki kural gereği yalnızca ekran görüntüsü yeterli değil.

| TC | Adımlar | Geçme ölçütü | Karşılar |
|---|---|---|---|
| **D01** Bağlantı | Port listesini yenile → bağlan → bağlantıyı kes → bağlan → **USB kabloyu çek** | Port listelenir; durum göstergesi doğru; kablo çekilince "bağlantı koptu" görünür, arayüz çökmez | UI-01 |
| **D02** Canlı görünüm | S3 koşusu, 3 basış | Senaryo ve durum görünür; TEL grafiği akar; her basışta "Butona basıldı · Olay N"; koşu dışında "ölçüm dışı" | UI-03, UI-04 |
| **D03** Kayıp göstergeleri | T13 derlemesiyle koşu | `tel_dropped` ve `btn_dropped` sıfırdan büyük görünür; PC kaybı ve bozuk çerçeve sayaçları ekranda | UI-05 |
| **D04** Düğme kilitleri | Koşu sırasında düğmeleri dene | Yalnızca "Durdur" etkin | UI-06 |
| **D05** CSV kaydı | T12'deki döküm | `S2.csv` oluşur; satırlar ham logdaki REC/PRE ile birebir aynı (betikle karşılaştırılır) | UI-07 |
| **D06** Sonuç grafiği | D05'ten sonra | Olay başına yığılmış çubuk (4 aralık) + exec/preempt ayrımı; `lost` olaylar işaretli | UI-08 |

---

## 8. Ölçüm kampanyası (E) ve kanıt

Tüm T ve D testleri geçtikten sonra, **Release derlemesi, test bayrakları kapalıyken** yapılır.

### 8.1 Her senaryo için prosedür (TC-E00 … TC-E05 = S0 … S5)

1. Kartı resetle, arayüzü bağla, senaryoyu seç.
2. **Başlat.** 5 s bekle (sistem kararlı hâle gelsin).
3. Butona **en az 30 kez** bas. Basışlar arasında **1–3 s, düzensiz** aralık bırak.
4. **Durdur → Döküm al.** Arayüz `measurements/S<n>.csv` dosyasını yazar. Ham log `measurements/raw/S<n>-<tarih>.log` dosyasına kaydedilir.
5. Bütünlük kontrolü: `python analysis/analyze.py --check S<n>`.

> 💡 **Neden düzensiz aralıklarla basıyoruz?** Telemetri kesin bir periyotla (ör. 10 ms) çalışıyor. Butona tam düzenli aralıklarla basmak mümkün olsaydı, basışlar hep telemetri döngüsünün aynı anına denk gelebilir ve tek bir durumu tekrar tekrar ölçmüş olurduk. Düzensiz basış, olayların periyodun farklı anlarına dağılmasını sağlar. İnsan eli zaten yeterince düzensizdir; bilerek ritim tutmaman yeterli.

### 8.2 Bir koşunun geçerli sayılma ölçütleri (bütünlük)

Bir koşu aşağıdakilerin **hepsi** sağlanırsa geçerlidir; biri bile sağlanmazsa koşu tekrarlanır ve geçersiz koşunun logu `measurements/raw/invalid/` altında saklanır (silinmez):

| # | Ölçüt |
|---|---|
| V1 | Kabul edilen olay sayısı ≥ 30 *(SCN-02)* |
| V2 | `rec_overflow = 0`, `frame_err = 0` |
| V3 | PC tarafında `bad_frames = 0` ve `pc_lost = 0` (USB hattı veri kaybetmedi) |
| V4 | `lost = 0` olan her olayda t₀ ≤ t₁ ≤ t₂ ≤ t₃ ≤ t₄ |
| V5 | Her olayda T21'deki kontrol denklemleri tutuyor |
| V6 | Ham logdaki `VER` çerçevesi: `Release`, `test_flags = 00`, hash'te `+` yok (commit edilmemiş kodla ölçüm yapılmamış) |

> ⚠️ `tel_dropped`, `btn_dropped` ve tüm gecikme değerleri bu listede **yok**. Onlar gözlemdir: ne çıkarsa kaydedilir, koşuyu geçersiz yapmaz.

### 8.3 Analiz (TC-E06)

`python analysis/analyze.py` → `measurements/summary.csv`, `analysis/plots/*.png`. `analysis/report.md` bu dosyalara bağlantı verir ve yalnızca ölçülen değerleri tablolar (yorum yok). *(UI-10, DOC-04)*

### 8.4 Kanıt klasörleri

```
hafta-01/
├── measurements/
│   ├── S0.csv … S5.csv          ← E00…E05 (geçerli koşular)
│   ├── summary.csv              ← E06
│   └── raw/                     ← ham UART logları (+ invalid/)
├── analysis/
│   ├── report.md                ← E06
│   └── plots/*.png
└── docs/
    ├── test-results.md          ← tüm TC'lerin sonuç tablosu
    └── test-results/
        ├── unit-<tarih>.txt     ← U testleri
        ├── raw/<TC>-<tarih>.log ← T testleri ham logları
        └── ui/                  ← D testleri görüntü/kayıtları
```

`docs/test-results.md` satır biçimi:
```
| TC-T12 | 2026-10-02 | a1b2c3d | Release | GEÇTİ | [log](test-results/raw/T12-2026-10-02.log) | — |
```

---

## 9. İzlenebilirlik matrisi (gereksinim → test → kanıt)

| Gereksinim | Test(ler) | Kanıt |
|---|---|---|
| SYS-01 | R01 | test-results.md |
| SYS-02 | R01, T25 | test-results.md, ui/ |
| SYS-03 | T01 | raw/T01 |
| SYS-04 | T17 | raw/T17 (MEM) |
| SYS-05 | T18 | test-results.md (gözlem notu) |
| TSK-01 | T03 | raw/T03 |
| TSK-02 | R01, T03 | raw/T03 |
| TSK-03 | T05 | raw/T05 (CAL) |
| TSK-04 | T04 | raw/T04 |
| TSK-05, TSK-05a | T07 | raw/T07 |
| TSK-06 | T02, T12 | raw/T02, raw/T12 |
| TSK-07 | R01 | test-results.md |
| TSK-08 | U02, T06 | unit, raw/T06 |
| ISR-01 | R02 | test-results.md |
| ISR-02 | R01 | test-results.md |
| ISR-03 | U03, T08 | unit, raw/T08 |
| ISR-04 | T09 | test-results.md (ölçülen değer) |
| QUE-01 | R01 | test-results.md |
| QUE-02, QUE-03 | T13 | raw/T13 |
| QUE-04 | R01, T14 | raw/T03 (SUM) |
| QUE-05 | T14 | raw/T03 (SUM) |
| MSG-01 | U01, T02 | unit, raw/T02 |
| MSG-02 | U01, T16 | unit, raw/T16 |
| MSG-03, MSG-04 | R01, T02, T07 | raw/T02, raw/T07 |
| MSG-05, MSG-06 | U06, T12 | unit, raw/T12 |
| MSG-09 | T01, V6 | raw/T01, measurements/raw/ |
| MSG-07, MSG-08 | U05, T10 | unit, raw/T10 |
| TIM-01 | R02, U03, U04, T19 | unit, raw/T19 |
| TIM-02 | R01, T12 | raw/T12 |
| TIM-02a | U08, T13 | unit, raw/T13 |
| TIM-02b | R01 | test-results.md |
| TIM-03 | T15 | raw/T15 |
| TIM-04 | T20 | raw/T20 |
| TIM-05 | T11 | raw/T02 |
| TIM-06 | T24 | raw/T24 |
| TIM-07, TIM-08, TIM-09 | T21, V5 | raw/T21, E00…E05 |
| TIM-10 | R01, T22 | raw/T22 |
| TIM-11 | R03 | code-notes.md |
| TIM-12 | T23 | raw (CAL) |
| SCN-01 | T03, T05 | raw/T03, raw/T05 |
| SCN-02 | E00…E05 (V1) | S0.csv…S5.csv |
| SCN-03 | T01 | raw/T01 |
| UI-01 … UI-06, UI-08 | D01 … D04, D06 | ui/ |
| UI-02, UI-05 | U07 | unit |
| UI-07 | U08, D05 | unit, S2.csv |
| UI-09 | R01 | test-results.md |
| UI-10 | U09, E06 | unit, summary.csv, plots/ |
| DOC-01 … DOC-06 | R03 | test-results.md |

Kapsama: 65 gereksinimin tamamı en az bir teste bağlı.

---

## 10. Uygulama adımı → çıkmadan önce geçmesi gereken testler

Tasarım §12'deki her adım, aşağıdaki testler geçmeden tamamlanmış sayılmaz:

| Adım | Testler |
|---|---|
| 1 Repo düzeni | R03 (`.gitignore` maddesi) |
| 2 CubeMX | R02 |
| 3 `app_ts` + `app_frame` | U01, U03, U04, U06, T19, T20 |
| 4 Kuyruk + UartTxTask + komutlar + TelemetryTask | U02, U05, T02, T03, T11, T14 |
| 5 ButtonTask + ISR | T07, T08, T09 |
| 6 `app_meas` t₀…t₄ | U08, T12, T13, T15, T16 |
| 7 Trace kancaları | T21, T22, T23 |
| 8 CPU yükü, stats, MEM | T04, T05, T06, T17, T18, T24, T25 |
| 9 PC arayüzü | U07, D01…D06, T10 |
| 10 Analiz + dokümanlar | U09, R01, R03, E00…E06 |

---

## 11. Açık konular

| # | Konu | Öneri |
|---|---|---|
| TQ-1 | Hangi firmware'in ölçüldüğünü kanıtlamak | **Kapandı:** VER çerçevesi eklendi (MSG-09, tasarım §9); V6 logdan doğrulanır |
| TQ-2 | T09 hangi derlemede ölçülür? | **Kapandı:** Release'te. İlk varsayım ("Debug'da tutuyorsa Release'te de tutar") yalnızca tek yönde doğru: Debug'da kalan bir süre Release'te geçebilir. Debug ölçümü 9,46 µs çıkınca ölçütün ölçüm derlemesi olan Release'te değerlendirilmesine karar verildi. |

## 12. Değişiklik geçmişi

| Sürüm | Tarih | Değişiklik |
|---|---|---|
| 0.1 | 2026-09-25 | İlk taslak |
| 1.0 | 2026-09-25 | Kursiyer onayı; TQ-1 kabul edildi (VER, MSG-09) |
| 1.1 | 2026-09-26 | §10: U02 ve U05 adım 4'e alındı (komut kanalı ve ADC okuma öne çekildi) |
| 1.2 | 2026-09-26 | T09 Release derlemede değerlendirilir; TQ-2 düzeltildi |
| 1.3 | 2026-09-26 | T12'ye t₄−t₃ fiziksel alt sınır kontrolü eklendi |
