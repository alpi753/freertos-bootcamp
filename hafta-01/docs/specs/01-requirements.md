# SPEC-01 · Gereksinimler — Hafta 01

| Alan | Değer |
|---|---|
| Doküman | `hafta-01/docs/specs/01-requirements.md` |
| Sürüm | 1.3 (ONAYLANDI — 2026-09-30) |
| Tarih | 2026-09-24 |
| Süreç | Requirements → Implementation → Test → Evidence |
| Sonraki doküman | `02-design.md` (bu doküman onaylanınca) |

---

## 1. Amaç ve kapsam

STM32L476RG (NUCLEO-L476RG) üzerinde FreeRTOS ile **üç farklı öncelikte görev** çalıştıran bir sistem kurulacak. Görevler **tek bir ortak TX kuyruğunu** paylaşacak. Butona basılmasıyla UART'tan yanıt çıkması arasında geçen süre **t₀…t₄ zaman damgalarıyla** ölçülecek. Ölçüm altı senaryoda (S0–S5) tekrarlanacak, sonuçlar PC arayüzünde gösterilecek, CSV olarak kaydedilecek ve grafiğe dökülecek.

**Kapsam içi:** firmware (3 görev + ISR + ölçüm altyapısı), PC arayüzü (`interface/`), ölçüm verisi (`measurements/`), analiz (`analysis/`), dokümantasyon (`docs/`).
**Kapsam dışı:** `gozlemler.md` (kursiyer doldurur), güç tüketimi, bootloader/OTA.

## 2. Alınmış kararlar

| # | Karar | Gerekçe |
|---|---|---|
| D-01 | Dizin yapısı teslim slaydındaki gibi olacak: `firmware/ interface/ measurements/ analysis/ docs/` + `README.md` + `gozlemler.md` | Tek depoda yeniden üretilebilir teslim |
| D-02 | UART TX, DMA ile yapılacak. Gönderimin bittiği TxCplt callback'inden görev bildirimiyle haber verilecek | t₄ gerçek gönderim sonunu gösterir, CPU gönderim sırasında boşta beklemez |
| D-03 | PC arayüzü Python 3 + PySide6 + pyqtgraph + pyserial ile yazılacak | Windows'ta kolay kurulur, canlı grafik çizer |
| D-04 | Senaryolar kursun S0–S5 tablosundaki gibi olacak (§6) | Kurs tanımı |

## 3. Terimler

| Terim | Anlamı |
|---|---|
| Çerçeve (frame) | MCU→PC yönünde giden, sabit 64 baytlık ASCII mesaj (§7) |
| TX kuyruğu | Üç görevin paylaştığı FIFO. TelemetryTask ve ButtonTask üretir, UartTxTask tüketir |
| Olay (event) | Debounce'tan geçmiş tek bir buton basışı. Her olayın bir olay kimliği (`event_id`) vardır |
| Koşu (run) | Bir senaryoda `START` ile `STOP` arasında geçen ölçüm süresi |
| Kayıp | Kuyruğa sığmadığı için gönderilemeyen mesaj ya da PC'nin sıra numarasındaki boşluktan fark ettiği eksik çerçeve |

## 4. Donanım ve araç bağlamı (mevcut proje)

| Öğe | Değer |
|---|---|
| MCU / kart | STM32L476RGT6, NUCLEO-L476RG |
| Saat | 80 MHz (HSI → PLL) |
| RTOS | FreeRTOS, CMSIS-RTOS v2 sarmalayıcı, tick 1 kHz |
| UART | USART2 115200 8N1, PA2/PA3 → ST-LINK VCP |
| Buton | B1 = PC13, EXTI13, düşen kenar |
| LED | LD2 = PA5 |
| HAL timebase | TIM6 |
| Araçlar | STM32CubeIDE, CubeMX 6.15.0, STM32Cube FW_L4 V1.18.2 |

---

## 5. Gereksinimler

**Yazım kuralı:** her gereksinimin bir ID'si, önceliği ve doğrulama yöntemi var.
- **Öncelik:** **M** = zorunlu (Must), **S** = olursa iyi (Should)
- **Doğrulama:** **T** = test, **A** = analiz/hesap, **I** = kod/konfig incelemesi, **D** = gösterim (demo)

### 5.1 Sistem ve görevler (SYS, TSK)

| ID | Gereksinim | Ö | D |
|---|---|---|---|
| SYS-01 | Firmware tam olarak üç uygulama görevi oluşturacak: `TelemetryTask`, `ButtonTask`, `UartTxTask`. CubeMX'in ürettiği `defaultTask` kaldırılacak ya da kullanılmayacak. | M | I |
| SYS-02 | Öncelik sırası kesin olacak: `TelemetryTask` > `ButtonTask` > `UartTxTask` > Idle. | M | I, T |
| SYS-03 | Scheduler başladıktan sonra tüm RTOS nesneleri (görevler, kuyruk, bildirimler) başarıyla oluşturulmuş olacak. `configASSERT` açık kalacak. | M | T |
| SYS-04 | En az 10 dk çalıştıktan sonra en düşük boş heap ≥ 1024 B ve her görevin stack high-water-mark değeri ≥ stack boyutunun %20'si olacak. | M | T |
| SYS-05 | Stack taşması algılanacak (`configCHECK_FOR_STACK_OVERFLOW = 2`) ve taşma olursa LD2 hızlı yanıp sönecek. | S | T |
| TSK-01 | `TelemetryTask`, seçili senaryonun periyodunda (§6) mutlak periyotla (`vTaskDelayUntil`) uyanacak, bir TEL çerçevesi üretecek ve TX kuyruğuna bırakacak. | M | T |
| TSK-02 | TEL çerçevesi şunları içerecek: sıra numarası (her koşuda 0'dan başlar, çerçeve başına +1), senaryo kimliği ve sıcaklık değeri (TSK-08). | M | I |
| TSK-03 | S4 ve S5'te `TelemetryTask` her periyotta sırasıyla ≈2 ms ve ≈5 ms'lik bir CPU işi yapacak (kurs tablosundaki ayar değeri). İşin gerçekte kaç µs sürdüğü her koşuda ölçülüp raporlanacak. | M | T |
| TSK-04 | S0'da telemetri kapalı olacak: `TelemetryTask` hiçbir çerçeve üretmeyecek ve CPU kullanmayacak (bloklu bekleyecek). | M | T |
| TSK-05 | `ButtonTask`, buton ISR'ından gelen bildirimle uyanacak. Olay geçerliyse bir BTN çerçevesi üretip TX kuyruğuna bırakacak. | M | T |
| TSK-05a | Butona her basış, koşu durumundan (IDLE / RUNNING / STOPPED) bağımsız olarak algılanacak ve BTN çerçevesi gönderilecek. t₀…t₄ ölçüm kaydı yalnızca koşu (RUNNING) sırasında tutulacak. Koşu dışındaki basışlarda BTN çerçevesi `event_id = 0` taşıyacak. | M | T |
| TSK-06 | `UartTxTask` kuyruktan çerçeveleri sırayla (FIFO) alacak ve her birini USART2 DMA ile gönderecek. Bir DMA gönderimi bitmeden (TxCplt) sıradakini başlatmayacak. | M | T |
| TSK-07 | Hiçbir görev, üzerinde çalıştığı döngüde meşgul bekleme (busy-wait) yapmayacak. Tek istisna TSK-03'teki bilinçli CPU yüküdür. | M | I |
| TSK-08 | Telemetri değeri dahili sıcaklık sensöründen (ADC1, VTS kanalı) okunacak ve fabrika kalibrasyon değerleriyle (TS_CAL1/TS_CAL2) 0,1 °C birimine çevrilecek (ör. `263` = 26,3 °C). ADC okuma süresi ölçülecek ve TelemetryTask çalışma süresine dahil raporlanacak. | M | T |

### 5.2 Kesme ve buton (ISR)

| ID | Gereksinim | Ö | D |
|---|---|---|---|
| ISR-01 | EXTI15_10 kesmesi NVIC'te etkin olacak. EXTI, DMA ve USART2 kesmelerinin öncelik değeri sayısal olarak ≥ `configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY` (5) olacak. | M | I |
| ISR-02 | Buton ISR'ı yalnızca t₀'ı kaydedecek ve `ButtonTask`'a `FromISR` API'siyle bildirim gönderecek. ISR içinde çerçeve biçimlendirme ya da UART işi yapılmayacak. | M | I |
| ISR-03 | Buton sıçraması (bounce) ISR içinde zaman damgasıyla filtrelenecek: son kabul edilen t₀'dan sonraki 50 ms içinde gelen kenarlar reddedilecek ve `ButtonTask`'a bildirim gitmeyecek. t₀ yalnızca kabul edilen kenarın zamanıdır. `event_id` yalnızca kabul edilen olaylarda artacak. | M | T |
| ISR-04 | Buton ISR'ının süresi 5 µs'yi aşmayacak. | S | T |

### 5.3 Kuyruk ve kayıp yönetimi (QUE)

| ID | Gereksinim | Ö | D |
|---|---|---|---|
| QUE-01 | Tek bir ortak TX kuyruğu olacak. Kuyruk öğesi sabit boyutlu bir yapı olacak: 64 baytlık çerçeve + mesaj tipi (TEL/BTN/ACK/...) + `event_id`. | M | I |
| QUE-02 | `TelemetryTask` kuyruğa zaman aşımı 0 ile yazacak ve yüksek öncelikli görev asla bloklanmayacak. Kuyruk doluysa çerçeve düşürülüp `tel_dropped` sayacı artırılacak. | M | T |
| QUE-03 | `ButtonTask` kuyruğa sınırlı bir zaman aşımıyla yazacak. Yazamazsa olay sessizce kaybolmayacak: `btn_dropped` sayacı artacak ve olay kaydında "kayıp" işareti tutulacak. | M | T |
| QUE-04 | Kuyruk derinliği derleme zamanı sabiti olacak; seçilen değer ve gerekçesi tasarım dokümanında yazılacak. Her koşuda `tel_dropped` ölçülüp raporlanacak. | M | I, T |
| QUE-05 | Koşu boyunca kuyruktaki en yüksek doluluk (high-water) izlenecek ve raporlanacak. | S | T |

### 5.4 Mesaj biçimi ve protokol (MSG)

| ID | Gereksinim | Ö | D |
|---|---|---|---|
| MSG-01 | MCU'dan PC'ye giden her çerçeve tam 64 bayt olacak: ASCII içerik + boşlukla 63 bayta tamamlama + bayt 64 = LF (`\n`). | M | T |
| MSG-02 | İçerik 63 baytı aşarsa kesilmeyecek. Hata sayacı artacak, `configASSERT` debug derlemede durduracak, release derlemede çerçeve gönderilmeyip sayılacak. | M | T |
| MSG-03 | TEL biçimi: `TEL,<seq>,S<n>,<value>` (ör. `TEL,1042,S3,726`). | M | I, T |
| MSG-04 | BTN biçimi: `BTN,<event_id>,S<n>,PRESSED` (ör. `BTN,17,S3,PRESSED`). | M | I, T |
| MSG-05 | Koşu bittikten sonra ölçüm kayıtları REC çerçeveleriyle, her olay için bir çerçeve olarak gönderilecek. Alan listesi tasarım dokümanında kesinleşecek; 63 bayta sığması zorunlu. | M | T |
| MSG-06 | Koşu sonunda bir SUM çerçevesi gönderilecek: üretilen/gönderilen TEL sayısı, `tel_dropped`, `btn_dropped`, olay sayısı, kuyruk en yüksek doluluğu. | M | T |
| MSG-07 | PC'den MCU'ya giden komutlar LF ile biten ASCII satırlar olacak (≤ 63 karakter): `CMD,SCN,<0-5>`, `CMD,START`, `CMD,STOP`, `CMD,DUMP`. **DUMP** (döküm): koşu boyunca RAM'de biriken t₀…t₄ kayıtlarını REC çerçeveleri + SUM çerçevesi olarak PC'ye gönderir; PC'de bir kayıp olursa tekrar istenebilir. MCU her komuta `ACK,...` ya da `NAK,...` çerçevesiyle yanıt verecek. | M | T |
| MSG-08 | Koşu sürerken senaryo değiştirilemeyecek (`CMD,SCN` → `NAK,BUSY`). | M | T |
| MSG-09 | Firmware açılışta ve her DUMP'ın başında bir VER çerçevesi gönderecek: `VER,<git kısa hash>,<Debug\|Release>,<test bayrakları>`. Değerler derleme sırasında gömülecek; çalışma anında değiştirilemeyecek. | M | T |

### 5.5 Zaman ölçümü (TIM)

| ID | Gereksinim | Ö | D |
|---|---|---|---|
| TIM-01 | Zaman damgası kaynağı ≤ 1 µs çözünürlükte olacak ve bir koşu içinde (≥ 10 dk) taşmayacak ya da taşma doğru ele alınacak. | M | A, I |
| TIM-02 | Kabul edilen her olay için beş zaman damgası, kursun tanımına göre tutulacak (ayrıntı §5.5.1):<br>• **t₀** buton ISR'ına girişte<br>• **t₁** `ButtonTask` olayı aldıktan hemen sonra<br>• **t₂** yanıt için `xQueueSend` çağrısından hemen önce<br>• **t₃** UART başlatma çağrısından (`HAL_UART_Transmit_DMA`) hemen önce<br>• **t₄** UART TC tamamlanması işlenirken (TxCplt callback) | M | I, T |
| TIM-02a | `xQueueSend` başarısız olursa ölçüm zinciri t₂'de biter: t₃ ve t₄ boş kalır, olay `lost = 1` olarak işaretlenir (QUE-03). | M | T |
| TIM-02b | t₃ ve t₄ yalnızca BTN çerçeveleri için kaydedilecek. `UartTxTask` çerçevenin BTN olduğunu ve hangi `event_id`'ye ait olduğunu kuyruk öğesindeki bir alandan anlayacak; çerçeve metnini ayrıştırmayacak. | M | I |
| TIM-03 | Kayıtlar koşu boyunca yalnızca RAM'de tutulacak; en az 64 olay kapasitesi olacak. Kapasite dolarsa yeni olaylar sayılacak ama kaydedilmeyecek (`rec_overflow`). | M | T |
| TIM-04 | Kayıt tutmak ölçülen yolu belirgin biçimde yavaşlatmayacak: her damga en fazla bir sayaç okuması ve bir RAM yazması olacak, damga başına ≤ 1 µs. | M | A, T |
| TIM-05 | Koşu sırasında UART'tan yalnızca TEL, BTN ve ACK çerçeveleri gidecek. REC dökümü yalnızca `STOP` sonrasında `DUMP` ile yapılacak (ölçüme karışmama ilkesi). | M | T |
| TIM-06 | Görev başına çalışma süresi istatistikleri (FreeRTOS run-time stats) etkinleştirilecek ve koşu sonunda raporlanacak. | M | T |

#### 5.5.1 Ölçüm noktaları (kurs tanımı) ve aralıklar

| Nokta | Nerede kaydedilir | Yorum |
|---|---|---|
| t₀ | Buton ISR girişinde | Filtrenin kabul ettiği kenarın zamanı |
| t₁ | `ButtonTask` olayı aldıktan hemen sonra | Olay aktarımı ve CPU'yu bekleme süresi dahildir |
| t₂ | Yanıt için `xQueueSend` çağrısından hemen önce | Gönderim başarılıysa ölçüm zinciri devam eder |
| t₃ | UART başlatma çağrısından hemen önce | İlk fiziksel bitin çıktığı anla aynı değildir |
| t₄ | UART TC tamamlanması işlenirken | Son bitten sonra ISR/callback'in bunu gördüğü an |

| Aralık | Formül | Neyi ölçer | Neden bu noktada ölçülüyor |
|---|---|---|---|
| `d_EventToRun` | t₁ − t₀ | ISR→görev bildirimi + ButtonTask'ın Ready durumunda CPU'yu bekleme süresi | Olayın görevin koşmaya başlamasına kadar ne kadar geciktiğini, yani öncelik etkisini gösterir |
| `d_ButtonExec` | t₂ − t₁ | ButtonTask'ın yanıtı hazırlama işi + bu sırada gelen araya girmeler | Görevin kendi işinin maliyetini gösterir; TIM-07 ile net süre ve kesilme süresi olarak ikiye ayrılır |
| `d_QueueWait` | t₃ − t₂ | Kuyruğa yazma + FIFO'da önündeki TEL çerçevelerini bekleme + UartTxTask'ın CPU'ya geçmesi | Ortak FIFO'da "başkasının arkasında bekleme" maliyetini gösterir |
| `d_UartTx` | t₄ − t₃ | HAL/DMA başlatma + 64 baytın hatta kalma süresi + TC kesmesinin callback'e ulaşması | Donanımın payını RTOS zamanlamasından ayrı gösterir |
| `d_Total` | t₄ − t₀ | Uçtan uca yanıt süresi | Kullanıcının hissettiği toplam gecikme |

Zaman çizgisi (örnek, ölçek yok):

```
TelemetryTask (yüksek) ──████──────────────████──────────────────────────
ButtonTask    (orta)   ─────── ░░ ▓▓▓▓ ▓▓▓▓──── ...
UartTxTask    (düşük)  ───────────────────────── ~~TEL gidiyor~~ ▶DMA────▶
UART hattı             ═════ TEL ═════════════════════════ BTN (64 B) ═══
                  t₀ ↑        t₁ ↑    ↑ (kesildi)   ↑ t₂       t₃ ↑        ↑ t₄
```
`░` Ready (CPU bekliyor) · `▓` Running · ButtonTask t₁–t₂ arasında TelemetryTask tarafından bir kez kesilmiş.

#### 5.5.2 Görev değişimi (preemption) ölçümleri

t₀…t₄ yalnızca hangi aşamada ne kadar kalındığını gösterir; bir aralığın **neden** uzadığını göstermez. Bu ölçümler FreeRTOS görev değiştirme kancalarıyla (`traceTASK_SWITCHED_IN` / `traceTASK_SWITCHED_OUT`) toplanır ve olay kaydına eklenir.

| ID | Gereksinim | Ö | D |
|---|---|---|---|
| TIM-07 | t₁–t₂ aralığı için ButtonTask'ın net CPU süresi (`bt_exec_us`), araya girilerek kesilme sayısı (`bt_n_preempt`) ve kesik kalınan toplam süre (`bt_preempt_us`) kaydedilecek. Kontrol: `d_ButtonExec = bt_exec_us + bt_preempt_us` (±ölçüm çözünürlüğü). | M | T |
| TIM-08 | t₀–t₁ aralığında başka görevlerin CPU'da geçirdiği toplam süre (`ready_wait_us`) ve bu görevlerin kimliği (en çok süre alan görev) kaydedilecek. | M | T |
| TIM-09 | t₂–t₃ aralığında UartTxTask'ın araya girilerek kesilme sayısı (`tx_n_preempt`) ve kesik kalınan süresi (`tx_preempt_us`) kaydedilecek. | M | T |
| TIM-10 | Görevden çıkışlar ikiye ayrılacak: **kesilme** (görev hâlâ Ready, daha yüksek öncelikli biri CPU'yu aldı) ve **bloklanma** (görev kendisi bekliyor: kuyruk, bildirim, DMA). Yalnızca kesilmeler `*_n_preempt` ve `*_preempt_us` alanlarına sayılacak. | M | I, T |
| TIM-11 | Donanım kesmeleri (SysTick, DMA, EXTI, USART) görev değişimi sayılmaz; süreleri o an koşan görevin `exec` süresine dahil olur. Bu sınırlama `docs/code-notes.md` içinde belirtilecek. | M | I |
| TIM-12 | Kancaların kendi ek yükü (bir giriş+çıkış çifti) ölçülüp raporlanacak; kanca başına iş bir sayaç okuması ve birkaç RAM yazmasıyla sınırlı olacak. | M | T |

### 5.6 Senaryolar (SCN) — ayrıntı §6

| ID | Gereksinim | Ö | D |
|---|---|---|---|
| SCN-01 | S0–S5 senaryoları §6 tablosundaki gibi uygulanacak ve komutla seçilebilecek. | M | T |
| SCN-02 | Her senaryo için en az **N = 30** kabul edilmiş buton olayı ölçülecek. | M | D |
| SCN-03 | Açılıştaki varsayılan senaryo S0 olacak. Seçili senaryo LD2'nin yanıp sönme sayısıyla da gösterilebilir. | S | D |

### 5.7 PC arayüzü (UI) — `interface/`

| ID | Gereksinim | Ö | D |
|---|---|---|---|
| UI-01 | Seri port listelenip seçilebilecek; Bağlan ve Bağlantıyı kes çalışacak; kopan bağlantı kullanıcıya gösterilecek. | M | D |
| UI-02 | Gelen veri 64 baytlık çerçevelere bölünecek. TEL, BTN, ACK/NAK, REC ve SUM çerçeveleri ayrı işlenecek. Bozuk ya da hizası kaymış çerçeveler sayılıp atılacak ve akış bir sonraki LF'de yeniden hizalanacak. | M | T |
| UI-03 | BTN geldiğinde belirgin biçimde "Butona basıldı · Olay N" gösterilecek; `event_id = 0` ise "Butona basıldı · ölçüm dışı" gösterilecek. | M | D |
| UI-04 | Aktif senaryo ve son olay kimliği sürekli görünür olacak. TEL değeri canlı grafikte çizilecek. | M | D |
| UI-05 | Kayıp göstergeleri: TEL sıra numarası boşluklarından hesaplanan PC tarafı kayıp, SUM'daki `tel_dropped`/`btn_dropped`, bozuk çerçeve sayısı. | M | D |
| UI-06 | Senaryo seçimi, START, STOP ve DUMP arayüzden yapılabilecek. Koşu sırasında STOP dışındaki komutlar devre dışı olacak. | M | D |
| UI-07 | DUMP sonrasında kayıtlar `measurements/S<n>.csv` dosyasına yazılacak (§8). | M | T |
| UI-08 | Yanıt süreleri grafiğe dökülecek: olay başına `d_Total` ve bileşenleri (yığılmış çubuk), ayrıca `bt_exec_us`/`bt_preempt_us` ayrımı; kayıp olaylar işaretlenecek. | M | D |
| UI-09 | Arayüz ölçüme karışmayacak: tüm süreler MCU damgalarından hesaplanacak, PC'nin alış zamanı ölçüm olarak kullanılmayacak. | M | I |
| UI-10 | Çevrimdışı analiz betiği `S0..S5.csv` dosyalarından `summary.csv` ve `analysis/plots/*.png` üretecek. | M | T |
| UI-11 | Sonuç grafiğinde `d_Total` için bir deadline çizgisi gösterilecek (varsayılan 20 ms, arayüzden değiştirilebilir). Deadline'ı aşan olaylar işaretlenecek, aşan olay sayısı ve en büyük `d_Total` yazılacak. Deadline bir gözlem aracıdır: koşunun geçerliliğini (V1…V6) etkilemez. | S | D |

### 5.8 Teslim ve dokümantasyon (DOC)

| ID | Gereksinim | Ö | D |
|---|---|---|---|
| DOC-01 | `hafta-01/README.md` şunları içerecek: kart, bağlantılar ve araç sürümleri; derleme, yükleme ve arayüzü başlatma; senaryo seçimi ve ölçüm adımları; timer ve FreeRTOS ayarları; ham veri, grafik ve rapor bağlantıları. | M | I |
| DOC-02 | `docs/code-notes.md`, ISR'ı, görevleri, UART tamamlanmasını ve zaman hesaplarını kod bloklarıyla açıklayacak (yalnızca ekran görüntüsü kabul edilmez). | M | I |
| DOC-03 | `docs/setup.md` ve `docs/ai-usage.md` bulunacak. | M | I |
| DOC-04 | `analysis/report.md` her senaryonun ölçülen sonuçlarını ve grafiklerini içerecek. Yorum ve çıkarımlar kursiyerin `gozlemler.md` dosyasına aittir. | M | I |
| DOC-05 | IDE ve derleme çıktıları (`.metadata/`, `Debug/`, `Release/`) repoya girmeyecek (`.gitignore`). | M | I |
| DOC-06 | `gozlemler.md` yalnızca kursiyer tarafından doldurulacak; otomatik araçlar bu dosyayı değiştirmeyecek. | M | I |

---

## 6. Senaryo tablosu

| ID | Telemetri | Ek CPU işi (TelemetryTask içinde, periyot başına) | Hedef |
|---|---|---|---|
| S0 | Kapalı | Yok | Referans yanıt süresi |
| S1 | 10 Hz · 100 ms | Yok | Düşük telemetri sıklığı |
| S2 | 50 Hz · 20 ms | Yok | Orta telemetri sıklığı |
| S3 | 100 Hz · 10 ms | Yok | Yüksek telemetri sıklığı |
| S4 | 100 Hz · 10 ms | ≈ 2 ms | Ek CPU yükü |
| S5 | 100 Hz · 10 ms | ≈ 5 ms | Daha yüksek CPU yükü |

## 7. Çerçeve örneği

```
"TEL,1042,S3,726" + 48 × ' ' + '\n'   → 15 + 48 + 1 = 64 bayt
"BTN,17,S3,PRESSED" + 46 × ' ' + '\n' → 17 + 46 + 1 = 64 bayt
```

## 8. CSV şeması (öneri)

`measurements/S<n>.csv` — her satır bir olay:

```
event_id,scenario,t0_us,t1_us,t2_us,t3_us,t4_us,lost,
d_EventToRun_us,d_ButtonExec_us,d_QueueWait_us,d_UartTx_us,d_Total_us,
ready_wait_us,ready_wait_task,bt_exec_us,bt_n_preempt,bt_preempt_us,tx_n_preempt,tx_preempt_us
```
Aralıkların tanımı §5.5.1'de, görev değişimi alanlarının tanımı §5.5.2'de. (Satır, okunabilsin diye burada bölündü; dosyada tek satırdır.)

`measurements/summary.csv` — her satır bir senaryo: `scenario,n` + her aralık için `min,mean,p50,p95,max,std` + `tel_sent,tel_dropped,btn_dropped,pc_lost,bad_frames`.

## 9. Varsayımlar ve kararlar

| # | Konu | Önerilen varsayım | Durum |
|---|---|---|---|
| Q-01 | t₀…t₄ tanımı | Kurs tanımı alındı (§5.5.1) | Kapandı |
| Q-02 | S4/S5'teki CPU işi | TelemetryTask içinde, her periyotta çalışır. Sonuç önceden tahmin edilmez; gerçek süreler ölçülüp gösterilir (TSK-03, TIM-06) | Kapandı |
| Q-03 | Olay sayısı N | 30 (SCN-02) | Kapandı |
| Q-04 | Telemetri değeri | Dahili sıcaklık sensörü, ADC1 (TSK-08) | Kapandı |
| Q-05 | Kuyruk disiplini | Saf FIFO; BTN, TEL'lerin önüne geçmez (QUE-01) | Kapandı |
| Q-06 | PC→MCU komut kanalı | 4. görev yok; RX kesmesi + ring buffer, komutlar UartTxTask'ta işlenir (MSG-07) | Kapandı |

## 10. Değişiklik geçmişi

| Sürüm | Tarih | Değişiklik |
|---|---|---|
| 0.1 | 2026-09-24 | İlk taslak |
| 0.2 | 2026-09-24 | t₀…t₄ kurs tanımına göre güncellendi (TIM-02, TIM-02a/b, §5.5.1); debounce ISR'a taşındı (ISR-03); kuyruk öğesi yapısı netleşti (QUE-01) |
| 0.3 | 2026-09-24 | Tahmin içeren "Analitik beklentiler" bölümü kaldırıldı; Q-02…Q-06 kapandı; sıcaklık sensörü (TSK-08); run-time stats zorunlu (TIM-06); DUMP tanımı (MSG-07) |
| 0.4 | 2026-09-25 | Aralık adları değişti (d_EventToRun, d_ButtonExec, d_QueueWait, d_UartTx, d_Total); görev değişimi ölçümleri eklendi (§5.5.2, TIM-07…TIM-12); zaman çizgisi ve "neden bu noktada" açıklaması eklendi; CSV şeması güncellendi |
| 1.0 | 2026-09-25 | Kursiyer onayı; değişiklik yok |
| 1.1 | 2026-09-25 | Tasarım incelemesinden: buton her durumda algılanır, ölçüm kaydı yalnızca koşuda (TSK-05a, UI-03) |
| 1.2 | 2026-09-25 | Test planı incelemesinden: firmware sürüm çerçevesi (MSG-09) |
| 1.3 | 2026-09-30 | Kursiyer isteği: sonuç grafiğinde deadline çizgisi (UI-11) |
