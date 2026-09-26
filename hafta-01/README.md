# Hafta 01 — FreeRTOS: üç görev, bir kuyruk, ölçülen gecikmeler

NUCLEO-L476RG üzerinde üç FreeRTOS görevi çalışır:

- **TelemetryTask** (yüksek öncelik) periyodik olarak sıcaklık ölçer ve kuyruğa yazar.
- **ButtonTask** (orta öncelik) buton olayına yanıt üretir.
- **UartTxTask** (düşük öncelik) kuyruktaki çerçeveleri sırayla DMA ile gönderir.

Buton basışından UART'ın son bitine kadar geçen süre beş noktada (t₀…t₄) damgalanır ve altı senaryoda (S0–S5) ölçülür.

| Belge | İçerik |
|---|---|
| [docs/specs/01-requirements.md](docs/specs/01-requirements.md) | Gereksinimler |
| [docs/specs/02-design.md](docs/specs/02-design.md) | Tasarım |
| [docs/specs/03-test-plan.md](docs/specs/03-test-plan.md) | Test planı |
| [docs/test-results.md](docs/test-results.md) | Tüm test sonuçları, sapmalar, bulgular |
| [docs/code-notes.md](docs/code-notes.md) | ISR, görevler, UART tamamlanması ve zaman hesapları (kod blokları) |
| [docs/setup.md](docs/setup.md) | Kurulum ayrıntıları |
| [docs/ai-usage.md](docs/ai-usage.md) | Yapay zekâ kullanımı |
| [gozlemler.md](gozlemler.md) | Kursiyerin gözlemleri |

## 1. Kart, bağlantılar, araçlar

| | |
|---|---|
| Kart | NUCLEO-L476RG (STM32L476RG, 80 MHz) |
| Buton | B1 (PC13, EXTI15_10) |
| LED | LD2 (PA5): hata göstergesi (HardFault 1 Hz, stack taşması 10 Hz, malloc hatası 2 Hz) |
| UART | USART2 (PA2/PA3) → ST-LINK sanal COM portu, 115200 8N1, TX DMA1 Kanal 7 |
| Sıcaklık | ADC1 iç sıcaklık sensörü, 640.5 cycle örnekleme, 3,3 V |
| Araçlar | STM32CubeMX 6.15.0 (IDE içinde), STM32Cube FW_L4 V1.18.2, FreeRTOS 10.3.1 (CMSIS-RTOS v2), Python 3.14, PySide6 6.11.2, pyqtgraph 0.14.0, pyserial 3.5, pandas, matplotlib |

Harici bağlantı yok: USB kablosu besleme, programlama ve UART'ı taşır.

## 2. Derleme, yükleme, arayüz

1. STM32CubeIDE'de çalışma alanı olarak `hafta-01/firmware/` seç ve `FreeRTOS_Kurs` projesini içe aktar.
2. Ölçüm için **Release** yapılandırmasıyla derle (Project → Build Configurations → Set Active → Release). Derleme öncesi adım `build_info.h`'ı üretir. Bu dosya, VER çerçevesinde görünen git hash'ini taşır ([setup.md](docs/setup.md#build-info)).
3. `FreeRTOS_Kurs Relase.launch` ile yükle ve çalıştır.
4. Arayüzü başlat:
   ```
   py -m pip install -r hafta-01/interface/requirements.txt
   py hafta-01/interface/uart_monitor.py
   ```
5. Portu seç (`STLink Virtual COM Port`) ve **Bağlan**'a tıkla.

## 3. Senaryolar ve ölçüm adımları

| Senaryo | Telemetri periyodu | Ek CPU yükü (TelemetryTask içinde) |
|---|---|---|
| S0 | kapalı | — |
| S1 | 100 ms | — |
| S2 | 20 ms | — |
| S3 | 10 ms | — |
| S4 | 10 ms | ≈ 2 ms |
| S5 | 10 ms | ≈ 5 ms |

Her senaryo için şu adımlar izlenir (test planı §8):

1. Kartı resetle, arayüzü bağla, senaryoyu seç ve **Başlat**'a tıkla. 5 s bekle.
2. Butona en az 30 kez, 1–3 s arayla, düzensiz bas.
3. **Durdur** → **Döküm al**. Arayüz `measurements/S<n>.csv` ve `measurements/raw/S<n>-<tarih>.log` dosyalarını yazar.
4. `py hafta-01/analysis/analyze.py --check S<n>` komutunu çalıştır. Sonuç GEÇERSİZ çıkarsa logu `measurements/raw/invalid/` altına taşı ve koşuyu tekrarla.

Altı senaryo bitince `py hafta-01/analysis/analyze.py` komutu `summary.csv`, grafikleri ve `report.md`'yi üretir.

**Aralıklar:**

| Ad | Tanım | Başlangıç ve bitiş noktası |
|---|---|---|
| `d_EventToRun` | t₁−t₀ | EXTI ISR'ının ilk satırı → ButtonTask bildirimi aldı |
| `d_ButtonExec` | t₂−t₁ | ButtonTask'ın işi (`bt_exec` + `bt_preempt`) |
| `d_QueueWait` | t₃−t₂ | kuyrukta bekleme → `HAL_UART_Transmit_DMA` |
| `d_UartTx` | t₄−t₃ | 64 bayt hatta (≥ 5556 µs) → TC kesmesi |
| `d_Total` | t₄−t₀ | olaydan son bitin hattan çıkmasına |

## 4. Timer ve FreeRTOS ayarları

| Ayar | Değer | Neden |
|---|---|---|
| TIM2 | PSC 79, ARR 0xFFFFFFFF → 1 MHz, 32 bit | Tüm t₀…t₄ damgaları 1 µs çözünürlükte. 71 dakikada bir taşar; farklar işaretsiz çıkarmayla hesaplandığı için tek taşma zararsızdır |
| DWT CYCCNT | 80 MHz | Yalnızca cycle düzeyindeki öz-testler için (ISR süresi, kanca maliyeti, CPU yükü kalibrasyonu) |
| Tick | 1 kHz | `vTaskDelayUntil` periyotları ms cinsinden |
| Öncelikler | Telemetry 40 (High) > Button 32 (AboveNormal) > UartTx 24 (Normal) | Kesilme etkisini görünür kılmak için |
| Kuyruk | `g_txq`, 16 × 68 B (`tx_item_t`), saf FIFO | Tek tüketici: UartTxTask |
| NVIC | EXTI15_10, USART2, DMA1_Ch7 → 6; `configMAX_SYSCALL_INTERRUPT_PRIORITY` → 5 | ISR'lardan `...FromISR` API'si çağrılabilsin |
| Heap / stack | heap_4 16 KB; görevler statik (Tel 1,5 KB, Btn 1 KB, Tx 2 KB) | Yığın taşması kontrolü yöntem 2 |
| İzleme | `traceTASK_SWITCHED_OUT/IN` kancaları | Kesilme ile bloklanmayı ayırmak için (TIM-10) |

Ayrıntılar: [tasarım §3–§8](docs/specs/02-design.md), [code-notes.md](docs/code-notes.md).

## 5. Veri, grafik, rapor

- Olay başına ölçümler: [measurements/](measurements/) (`S0.csv` … `S5.csv`, `summary.csv`)
- Ham UART kayıtları: [measurements/raw/](measurements/raw/)
- Ölçüm raporu: [analysis/report.md](analysis/report.md)
- Grafikler: [analysis/plots/](analysis/plots/)
- Test kanıtları: [docs/test-results/](docs/test-results/) (ham loglar, birim test çıktıları, ekran görüntüleri)
