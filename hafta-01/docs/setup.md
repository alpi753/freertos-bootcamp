# Kurulum

## Firmware

1. **STM32CubeIDE** (CubeMX 6.15.0 ve FW_L4 V1.18.2 ile uyumlu bir sürüm).
2. File → Switch Workspace → `hafta-01/firmware/`. Ardından File → Import → Existing Projects → `FreeRTOS_Kurs`.
3. `.ioc` dosyası CubeMX ile açılabilir. Kod yeniden üretilirse yalnızca `USER CODE` bölümlerindeki eklemeler korunur. Uygulama kodu ayrı `app_*.c/h` dosyalarındadır.
4. Yapılandırmalar:
   - **Debug:** `-O0`, `DEBUG` tanımlı (uygulamanın ek `configASSERT` denetimleri açık).
   - **Release:** `-Os -g3`. Ölçümler bununla alınır.
5. Test bayrakları (Project Properties → C/C++ Build → Settings → MCU GCC Compiler → Preprocessor): `TEST_FORCE_QFULL`, `TEST_MEAS_CAP`, `TEST_LONG_FRAME`, `TEST_STACK_OVF=1|2`. Ölçüm derlemesinde **hiçbiri tanımlı olmamalı**. VER çerçevesindeki bayrak alanı `00` olmalı.

<a id="build-info"></a>
### Derleme öncesi adım: `build_info.h`

VER çerçevesi, kartta hangi kodun çalıştığını git hash'iyle kanıtlar (MSG-09, V6). CubeIDE'de şunu yap:

**Project Properties → C/C++ Build → Settings → Build Steps → Pre-build steps → Command** alanına, Debug ve Release için ayrı ayrı şunu yaz:

```
py "${ProjDirPath}/../tools/gen_build_info.py" "${ProjDirPath}/Core/Inc/build_info.h"
```

- **Temiz çalışma dizini:** `VER,a1b2c3d,Release,00`
- **`hafta-01/firmware/` altında commit edilmemiş değişiklik varsa:** `a1b2c3d+`. Bu hash ölçüm için geçersiz sayılır.
- **git bulunamazsa:** `nogit`. Bu da geçersizdir.

`build_info.h` `.gitignore`'dadır.

### Kartsız birim testleri (firmware)

```
cd hafta-01/firmware/tests_host
make          # PC gcc ile; saf C modülleri (frame, cmd, ts, temp, meas, hooks)
```

## PC tarafı

```
py -m pip install -r hafta-01/interface/requirements.txt
py -m pip install -r hafta-01/analysis/requirements.txt
```

| Komut | Ne yapar |
|---|---|
| `py hafta-01/interface/uart_monitor.py` | Arayüz |
| `py hafta-01/interface/tools/hil_check.py --port COMx --tc <TC>` | Kart üstü otomatik testler (test planı §6) |
| `py hafta-01/interface/tools/compare_dump.py <csv> <ham log>` | CSV ↔ ham döküm karşılaştırması (D05) |
| `py hafta-01/analysis/analyze.py --check S<n>` | Koşu bütünlüğü (V1…V6) |
| `py hafta-01/analysis/analyze.py` | `summary.csv`, grafikler, `report.md` |
| `py -m pytest hafta-01/interface/tests hafta-01/analysis/tests` | PC birim testleri (U07, U08, U09) |

NUCLEO, Windows'ta `STMicroelectronics STLink Virtual COM Port (COMx)` olarak görünür.
