# freertos-bootcamp

FreeRTOS kursu projelerimin ve çalışmalarımın bulunduğu repodur.

Kurs 10 hafta sürüyor. Her hafta kendi klasöründe, aynı düzenle ve aynı sırayla ilerliyor: **Gereksinimler → Tasarım → Uygulama → Test → Kanıt**.

## Donanım ve araçlar

| | |
|---|---|
| Kart | NUCLEO-L476RG (STM32L476RG, Cortex-M4F, 80 MHz) |
| RTOS | FreeRTOS 10.3.1 (CMSIS-RTOS v2 sarmalayıcısı) |
| IDE | STM32CubeIDE + STM32CubeMX 6.15.0, STM32Cube FW_L4 V1.18.2 |
| PC tarafı | Python 3.14: PySide6, pyqtgraph, pyserial, pandas, matplotlib |

## Haftalar

| Hafta | Konu | Durum |
|---|---|---|
| [hafta-01](hafta-01/README.md) | Üç görev (Telemetry / Button / UartTx), paylaşılan kuyruk, UART DMA; buton olayından UART'ın son bitine kadar gecikmenin t₀…t₄ noktalarında ölçülmesi (S0–S5) ve kesilme/bloklanma ayrımı | Firmware, arayüz ve testler tamam; ölçüm kampanyası sürüyor |
| hafta-02 … hafta-10 | — | — |

## Bir haftanın düzeni

```
hafta-XX/
├── README.md          ← haftanın özeti: kart, derleme, ölçüm adımları, sonuç bağlantıları
├── firmware/          ← STM32CubeIDE çalışma alanı + proje (+ kartsız birim testleri)
├── interface/         ← PC arayüzü ve kart üstü test araçları
├── measurements/      ← ölçüm CSV'leri ve ham UART kayıtları
├── analysis/          ← analiz betiği, rapor, grafikler
├── docs/
│   ├── specs/         ← 01-requirements, 02-design, 03-test-plan
│   ├── test-results.md
│   ├── code-notes.md, setup.md, ai-usage.md
│   └── test-results/  ← test kanıtları (ham loglar, ekran görüntüleri)
└── gozlemler.md       ← kendi gözlemlerim (yalnızca ben yazarım)
```

## Kurallar

- IDE ve derleme çıktıları (`.metadata/`, `Debug/`, `Release/`) repoya girmez ([.gitignore](.gitignore)).
- Ölçümler Release derlemesiyle, test bayrakları kapalıyken ve commit edilmiş kodla alınır. Kartın gönderdiği VER çerçevesi git hash'ini gösterir.
- `gozlemler.md` dosyalarını yalnızca ben yazarım. Yapay zekâ kullanımı her haftanın `docs/ai-usage.md` dosyasında anlatılır.
