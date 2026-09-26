#!/usr/bin/env python3
"""
hil_check.py — kart üstü (hardware-in-the-loop) otomatik testler.
Test planı: hafta-01/docs/specs/03-test-plan.md §6.

Kullanım (Windows örneği):
    py -m pip install -r interface/requirements.txt
    py interface/tools/hil_check.py --port COM5 --tc adim4
    py interface/tools/hil_check.py --port COM5 --tc T03 --secs 10     # hızlı deneme
    py interface/tools/hil_check.py --port COM5 --tc T07               # etkileşimli: butona sen basarsın
    py interface/tools/hil_check.py --port COM5 --tc T08
    py interface/tools/hil_check.py --port COM5 --tc T12               # etkileşimli: 5 basış
    py interface/tools/hil_check.py --port COM5 --tc T13               # TEST_FORCE_QFULL=1 derlemesi
    py interface/tools/hil_check.py --port COM5 --tc T15               # TEST_MEAS_CAP=1 derlemesi
    py interface/tools/hil_check.py --port COM5 --tc T16               # TEST_LONG_FRAME=1 derlemesi (Release)
    py interface/tools/hil_check.py --port COM5 --tc T21 --scn 3       # etkileşimli: 10 basış
    py interface/tools/hil_check.py --port COM5 --tc T22               # etkileşimli: 10 basış (S0)
    py interface/tools/hil_check.py --port COM5 --tc adim8 --secs 30   # T04, T05, T06, T24 (otomatik)
    py interface/tools/hil_check.py --port COM5 --tc T17 --secs 600    # etkileşimli: 10 dk S5, 30 basış
    py interface/tools/hil_check.py --port COM5 --tc T18 --ovf 1       # TEST_STACK_OVF=1 derlemesi (T18a)
    py interface/tools/hil_check.py --port COM5 --tc T18 --ovf 2       # TEST_STACK_OVF=2 derlemesi (T18b)

Her koşu ham UART kaydını docs/test-results/raw/<TC>-<tarih>.log dosyasına yazar.
Satır biçimi:  <PC ms>\t<çerçeve>   (PC zamanı yalnızca hata ayıklama içindir;
ölçüm değildir — UI-09.)
"""
import argparse
import datetime as dt
import pathlib
import sys
import time

try:
    import serial                    # pyserial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial yok:  py -m pip install -r interface/requirements.txt")

FRAME_LEN = 64
TXQ_DEPTH = 16                       # app_config.h ile aynı olmalı
PERIOD_MS = {0: 0, 1: 100, 2: 20, 3: 10, 4: 10, 5: 10}
RUN_TYPES = {"TEL", "BTN", "ACK"}    # TIM-05: koşu sırasında izinli tipler
ROOT = pathlib.Path(__file__).resolve().parents[2]          # hafta-01/
RAW_DIR = ROOT / "docs" / "test-results" / "raw"


class Link:
    """Seri port + 64 baytlık çerçeve ayırıcı + ham kayıt."""

    def __init__(self, port):
        self.ser = serial.Serial(port, 115200, timeout=0.05)
        self.t0 = time.monotonic()
        self.buf = b""
        self.synced = False          # bağlantı ortasında açılırsa ilk LF'ye kadar at
        self.frames = []             # (pc_ms, bytes)
        self.bad = 0

    def ms(self):
        return int((time.monotonic() - self.t0) * 1000)

    def send(self, line):
        self.ser.write((line + "\n").encode("ascii"))
        self.frames.append((self.ms(), b">> " + line.encode()))

    def pump(self):
        self.buf += self.ser.read(4096)
        out = []
        while b"\n" in self.buf:
            raw, self.buf = self.buf.split(b"\n", 1)
            raw += b"\n"
            if not self.synced:
                self.synced = True
                if len(raw) != FRAME_LEN:
                    continue         # yarım ilk çerçeve: sayma
            if len(raw) != FRAME_LEN:
                self.bad += 1
            self.frames.append((self.ms(), raw))
            out.append(raw)
        return out

    def wait_for(self, prefix, timeout=3.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            for f in self.pump():
                if f.startswith(prefix.encode()):
                    return self.ms(), f
        raise TimeoutError(f"'{prefix}' gelmedi")

    def drain(self, secs):
        end = time.monotonic() + secs
        while time.monotonic() < end:
            self.pump()

    def save(self, name):
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        path = RAW_DIR / f"{name}-{stamp}.log"
        with open(path, "w", encoding="ascii", errors="replace") as fh:
            for t, f in self.frames:
                fh.write(f"{t}\t{f.decode('ascii', 'replace').rstrip()}\n")
        return path


def fields(frame):
    return frame.decode("ascii", "replace").rstrip().split(",")


def run_once(link, scn, secs):
    """Bir koşu: SCN → START → bekle → STOP → DUMP. Ölçüm için gerekli her şeyi döndürür."""
    link.send("CMD,STOP")                          # kart koşudaysa durdur (değilse NAK,STATE)
    link.drain(0.3)
    link.send(f"CMD,SCN,{scn}")
    link.wait_for(f"ACK,SCN,S{scn}")
    i_start = len(link.frames)
    link.send("CMD,START")
    t_start, _ = link.wait_for(f"ACK,START,S{scn}")
    link.drain(secs)
    link.send("CMD,STOP")
    t_stop, _ = link.wait_for("ACK,STOP")
    i_stop = len(link.frames)
    link.send("CMD,DUMP")
    link.wait_for("END,DUMP")
    dump = [f for _, f in link.frames[i_stop:] if not f.startswith(b">>")]
    run = [f for _, f in link.frames[i_start:i_stop] if not f.startswith(b">>")]
    sum_f = next(fields(f) for f in dump if f.startswith(b"SUM,"))
    # SUM,S<n>,events,tel_sent,tel_dropped,btn_dropped,q_hw,rec_overflow,bounce_rej,frame_err
    s = dict(zip(["scn", "events", "tel_sent", "tel_dropped", "btn_dropped", "q_hw",
                  "rec_overflow", "bounce_rej", "frame_err"], sum_f[1:]))
    s = {k: (v if k == "scn" else int(v)) for k, v in s.items()}
    return {"run": run, "dump": dump, "sum": s, "dur_ms": t_stop - t_start}


def check(name, ok, detail):
    print(f"  [{'GECTI' if ok else 'KALDI'}] {name}: {detail}")
    return ok


def tc_t02_t11(link, r):
    """T02: tüm çerçeveler 64 B + LF.  T11: koşu içinde yalnızca TEL/BTN/ACK."""
    all_rx = [f for _, f in link.frames if not f.startswith(b">>")]
    n_bad_len = sum(1 for f in all_rx if len(f) != FRAME_LEN or not f.endswith(b"\n"))
    ok02 = check("T02 cerceve butunlugu", n_bad_len == 0 and link.bad == 0,
                 f"{len(all_rx)} cerceve, uzunluk hatasi {n_bad_len}, bad_frames {link.bad}")
    types = sorted({fields(f)[0] for f in r["run"]})
    ok11 = check("T11 kosu sirasinda tipler", set(types) <= RUN_TYPES, f"gorulen tipler {types}")
    return ok02, ok11


def tc_t03(r, scn):
    """T03: seq 0'dan kesintisiz; üretilen = süre/periyot ±%1; PC hepsini aldı."""
    tel = [fields(f) for f in r["run"] if f.startswith(b"TEL,")]
    seqs = [int(f[1]) for f in tel]
    s = r["sum"]
    gen = s["tel_sent"] + s["tel_dropped"]
    expected = r["dur_ms"] / PERIOD_MS[scn]
    ok_seq = seqs == list(range(len(seqs))) and s["tel_dropped"] == 0
    ok_rate = abs(gen - expected) <= max(1.0, 0.01 * expected)
    ok_rx = len(tel) == s["tel_sent"]
    return check(f"T03 S{scn} periyot", ok_seq and ok_rate and ok_rx,
                 f"sure {r['dur_ms']} ms, uretilen {gen} (beklenen {expected:.1f}), "
                 f"PC'ye gelen {len(tel)}/{s['tel_sent']}, seq kesintisiz={ok_seq}, "
                 f"tel_dropped {s['tel_dropped']}")


def tc_t14(r):
    q = r["sum"]["q_hw"]
    return check("T14 kuyruk dolulugu", 1 <= q <= TXQ_DEPTH, f"q_hw = {q} (1..{TXQ_DEPTH})")


# ---- Etkileşimli testler (operatör butona basar) ---------------------------

def say(msg):
    print(f"\n>>> {msg}", flush=True)


def collect_btn(link, n, timeout=90.0, settle=1.5):
    """n adet BTN gelene kadar bekler, sonra settle s daha dinler (fazladan BTN = sıçrama)."""
    got = []
    end = time.monotonic() + timeout
    while len(got) < n and time.monotonic() < end:
        for f in link.pump():
            if f.startswith(b"BTN,"):
                got.append(fields(f))
                print(f"    BTN alindi: olay {got[-1][1]} ({len(got)}/{n})", flush=True)
    end = time.monotonic() + settle
    while time.monotonic() < end:
        for f in link.pump():
            if f.startswith(b"BTN,"):
                got.append(fields(f))
                print(f"    FAZLADAN BTN: olay {got[-1][1]}", flush=True)
    return got


def dump_sum(link):
    i = len(link.frames)
    link.send("CMD,DUMP")
    link.wait_for("END,DUMP")
    f = next(fields(f) for _, f in link.frames[i:] if f.startswith(b"SUM,"))
    return dict(zip(["scn", "events", "tel_sent", "tel_dropped", "btn_dropped", "q_hw",
                     "rec_overflow", "bounce_rej", "frame_err"], [f[1]] + [int(x) for x in f[2:]]))


def tc_t07(link):
    """T07: buton IDLE / RUNNING / STOPPED durumlarının hepsinde algılanır (TSK-05, TSK-05a)."""
    ok = True
    say("Karti RESETLE (siyah tus). VER cercevesi bekleniyor...")
    link.wait_for("VER,", timeout=60)
    link.drain(1.5)                                   # öz-testler (~1 s) bitsin
    say("IDLE: butona 2 kez bas (aralarinda 1 sn birak).")
    b = collect_btn(link, 2)
    ok &= check("T07 IDLE", len(b) == 2 and all(x[1] == "0" for x in b),
                f"{len(b)} BTN, olay no'lari {[x[1] for x in b]} (beklenen 2 adet, hepsi 0)")
    link.send("CMD,SCN,0"); link.wait_for("ACK,SCN,S0")
    link.send("CMD,START"); link.wait_for("ACK,START,S0")
    say("RUNNING: butona 3 kez bas.")
    b = collect_btn(link, 3)
    ok &= check("T07 RUNNING", [x[1] for x in b] == ["1", "2", "3"],
                f"olay no'lari {[x[1] for x in b]} (beklenen 1, 2, 3)")
    link.send("CMD,STOP"); link.wait_for("ACK,STOP")
    say("STOPPED: butona 2 kez bas.")
    b = collect_btn(link, 2)
    ok &= check("T07 STOPPED", len(b) == 2 and all(x[1] == "0" for x in b),
                f"{len(b)} BTN, olay no'lari {[x[1] for x in b]} (beklenen 2 adet, hepsi 0)")
    s = dump_sum(link)
    ok &= check("T07 SUM", s["events"] == 3 and s["btn_dropped"] == 0,
                f"events {s['events']} (beklenen 3), btn_dropped {s['btn_dropped']}")
    return ok


def tc_t08(link, presses=20):
    """T08: debounce — operatörün saydığı basış sayısı = kabul edilen olay sayısı (ISR-03)."""
    link.send("CMD,STOP"); link.drain(0.3)
    link.send("CMD,SCN,0"); link.wait_for("ACK,SCN,S0")
    link.send("CMD,START"); link.wait_for("ACK,START,S0")
    say(f"Butona {presses} kez bas. Basislari KENDIN say; ekrana bakmadan saymaya calis.\n"
        "    Hizli, yavas, kisa, uzun basislar karisik olsun. Bitince Enter'a bas.")
    import threading
    done = threading.Event()
    threading.Thread(target=lambda: (input(), done.set()), daemon=True).start()
    n_btn = 0
    while not done.is_set():
        for f in link.pump():
            if f.startswith(b"BTN,"):
                n_btn += 1
    end = time.monotonic() + 0.5                  # son basıştan sonra gelen BTN'leri de say
    while time.monotonic() < end:
        n_btn += sum(1 for f in link.pump() if f.startswith(b"BTN,"))
    counted = int(input("    Kac kez bastin? ").strip())
    link.send("CMD,STOP"); link.wait_for("ACK,STOP")
    s = dump_sum(link)
    return check("T08 debounce", counted == s["events"] == n_btn,
                 f"senin sayimin {counted}, kabul edilen olay {s['events']}, gelen BTN {n_btn}, "
                 f"reddedilen sicrama (bounce_rej) {s['bounce_rej']}")


# ---- Döküm (DUMP) ve adım 6 testleri ----------------------------------------

UART_MIN_US = 5555   # 64 bayt × 10 bit / 115200 bit/s = 5,556 ms: t₄−t₃ bundan kısa OLAMAZ


def full_dump(link):
    """DUMP gönderir; {'ver','recs','sum','frames'} döndürür."""
    i = len(link.frames)
    link.send("CMD,DUMP")
    link.wait_for("END,DUMP", timeout=10)
    frames = [f for _, f in link.frames[i:] if not f.startswith(b">>")]
    recs, pres, s, ver, cal, mem, rts = [], {}, None, None, None, None, []
    for f in frames:
        x = fields(f)
        if x[0] == "REC":
            recs.append(dict(zip(["id", "scn", "t0", "d1", "d2", "d3", "d4", "lost"],
                                 [int(x[1]), x[2]] + [int(v) for v in x[3:]])))
        elif x[0] == "PRE":
            pres[int(x[1])] = dict(zip(["rw_us", "rw_task", "bt_exec", "bt_n", "bt_pre", "tx_n", "tx_pre"],
                                       [int(x[2]), x[3], int(x[4]), int(x[5]), int(x[6]), int(x[7]), int(x[8])]))
        elif x[0] == "SUM":
            s = dict(zip(["scn", "events", "tel_sent", "tel_dropped", "btn_dropped", "q_hw",
                          "rec_overflow", "bounce_rej", "frame_err"], [x[1]] + [int(v) for v in x[2:]]))
        elif x[0] == "VER":
            ver = x
        elif x[0] == "CAL":
            cal = dict(zip(["load_target", "load_mean", "load_max", "adc_mean", "hook_ns"], [int(v) for v in x[1:]]))
        elif x[0] == "MEM":
            mem = dict(zip(["min_free_heap", "hw_tel", "hw_btn", "hw_tx"], [int(v) for v in x[1:]]))
        elif x[0] == "RTS":
            rts.append({"task": x[1], "run_us": int(x[2]), "pct_x10": int(x[3])})
    for r in recs:
        r["pre"] = pres.get(r["id"])
    return {"ver": ver, "recs": recs, "sum": s, "frames": frames, "cal": cal, "mem": mem, "rts": rts}


def require_flags(link, want):
    """Doğru test derlemesi mi yüklü? Kısa bir S0 koşusu + DUMP ile VER'deki bayrak maskesine bakar."""
    start(link, 0)
    stop(link)
    ver = full_dump(link)["ver"]
    flags = int(ver[3], 16) if ver else -1
    ok = flags == want
    check("test derlemesi", ok, f"{','.join(ver) if ver else 'VER yok'} → bayraklar 0x{flags:02X}, "
          f"beklenen 0x{want:02X}" + ("" if ok else "  → dogru derlemeyi yukle"))
    return ok


def start(link, scn):
    link.send("CMD,STOP"); link.drain(0.3)
    link.send(f"CMD,SCN,{scn}"); link.wait_for(f"ACK,SCN,S{scn}")
    link.send("CMD,START"); t, _ = link.wait_for(f"ACK,START,S{scn}")
    return t


def stop(link):
    link.send("CMD,STOP"); t, _ = link.wait_for("ACK,STOP")
    return t


def tc_t12(link, presses=5):
    """T12: döküm bütünlüğü — REC sayısı, sıra, zincir, tekrar edilebilirlik (MSG-05/06, TIM-02)."""
    if not require_flags(link, 0):
        return False
    start(link, 2)
    say(f"S2 kosusu basladi. Butona {presses} kez bas (aralarinda 1-3 sn).")
    collect_btn(link, presses)
    stop(link)
    d1 = full_dump(link)
    d2 = full_dump(link)
    recs, s = d1["recs"], d1["sum"]
    ok = True
    ok &= check("T12 kayit sayisi", len(recs) == presses == s["events"],
                f"REC {len(recs)}, SUM.events {s['events']}, basis {presses}")
    ok &= check("T12 olay sirasi", [r["id"] for r in recs] == list(range(1, presses + 1)),
                f"{[r['id'] for r in recs]}")
    ok &= check("T12 zincir tam", all(r["lost"] == 0 for r in recs),
                f"lost alanlari {[r['lost'] for r in recs]}")
    ok &= check("T12 t0 artan", all(recs[i]["t0"] < recs[i + 1]["t0"] for i in range(len(recs) - 1)),
                "olaylarin t0'lari zaman sirasinda")
    ok &= check("T12 t4-t3 fiziksel alt sinir", all(r["d4"] >= UART_MIN_US for r in recs),
                f"d_UartTx {[r['d4'] for r in recs]} us (>= {UART_MIN_US}: 64 bayt hatta en az bu kadar kalir)")
    same = [f for f in d1["frames"] if f[:3] in (b"REC", b"SUM")] == \
           [f for f in d2["frames"] if f[:3] in (b"REC", b"SUM")]
    ok &= check("T12 tekrar DUMP ayni", same, "iki dokumdeki REC+SUM cerceveleri bayt bayt ayni")
    for r in recs:
        print(f"    olay {r['id']}: EventToRun {r['d1']} | ButtonExec {r['d2']} | "
              f"QueueWait {r['d3']} | UartTx {r['d4']} us")
    return ok


def tc_t13(link, secs=20.0, presses=5):
    """T13: kuyruk dolu (TEST_FORCE_QFULL) — TEL düşer ama TelemetryTask bloklanmaz; BTN kaybı kayda geçer."""
    if not require_flags(link, 0x01):
        return False
    t0 = start(link, 3)
    say(f"S3 kosusu ({secs:.0f} s). Bu surede butona {presses} kez bas.")
    got = collect_btn(link, presses, timeout=secs, settle=0)
    remain = secs - (link.ms() - t0) / 1000
    if remain > 0:
        link.drain(remain)
    t1 = stop(link)
    d = full_dump(link)
    s, recs = d["sum"], d["recs"]
    tel = [int(fields(f)[1]) for _, f in link.frames if f.startswith(b"TEL,")]
    gen = s["tel_sent"] + s["tel_dropped"]
    expected = (t1 - t0) / PERIOD_MS[3]
    n_lost = sum(1 for r in recs if r["lost"] == 1)
    ok = True
    ok &= check("T13 TEL dusuruldu", s["tel_dropped"] > 0, f"tel_dropped {s['tel_dropped']}, tel_sent {s['tel_sent']}")
    ok &= check("T13 TelemetryTask bloklanmadi", abs(gen - expected) <= max(1.0, 0.01 * expected),
                f"uretilen {gen}, beklenen {expected:.1f} (sure {t1 - t0} ms)")
    ok &= check("T13 seq bosluklu", len(tel) > 1 and tel != list(range(tel[0], tel[0] + len(tel))),
                f"PC'ye gelen TEL {len(tel)}, son seq {tel[-1] if tel else '-'}")
    ok &= check("T13 BTN kaybi kayitta", s["btn_dropped"] == n_lost,
                f"btn_dropped {s['btn_dropped']} = lost=1 REC {n_lost}; BTN gelen {len(got)}")
    ok &= check("T13 kayip zincir t2'de biter",
                all(r["d3"] == 0 and r["d4"] == 0 for r in recs if r["lost"] == 1),
                "lost=1 kayitlarda t3-t2 ve t4-t3 = 0")
    return ok


def tc_t15(link, presses=6):
    """T15: kayıt kapasitesi (TEST_MEAS_CAP → 4)."""
    if not require_flags(link, 0x02):
        return False
    start(link, 0)
    say(f"S0 kosusu. Butona {presses} kez bas.")
    got = collect_btn(link, presses)
    stop(link)
    d = full_dump(link)
    s, recs = d["sum"], d["recs"]
    return check("T15 kapasite", len(recs) == 4 and s["rec_overflow"] == presses - 4
                 and s["events"] == presses and [g[1] for g in got] == [str(i) for i in range(1, presses + 1)],
                 f"REC {len(recs)} (4), rec_overflow {s['rec_overflow']} ({presses - 4}), "
                 f"events {s['events']}, gelen BTN no'lari {[g[1] for g in got]}")


def tc_t16(link):
    """T16: 63'ü aşan çerçeve kesilmez, gönderilmez, sayılır (Release; MSG-02)."""
    if not require_flags(link, 0x04):
        return False
    start(link, 0)
    link.drain(0.5)
    stop(link)
    d = full_dump(link)
    rx = [f for _, f in link.frames if not f.startswith(b">>")]
    long_seen = any(f.startswith(b"LONG") for f in rx)
    bad = sum(1 for f in rx if len(f) != FRAME_LEN)
    return check("T16 uzun cerceve", d["sum"]["frame_err"] >= 1 and not long_seen and bad == 0,
                 f"frame_err {d['sum']['frame_err']} (>=1), LONG cercevesi gorundu mu: {long_seen}, "
                 f"64 bayt olmayan cerceve {bad}")


# ---- Adım 7: görev değişimi muhasebesi --------------------------------------

def run_presses(link, scn, presses):
    if not require_flags(link, 0):
        return None
    start(link, scn)
    say(f"S{scn} kosusu basladi. Butona {presses} kez bas (aralarinda 1-3 sn, duzensiz).")
    collect_btn(link, presses)
    stop(link)
    return full_dump(link)


def print_pre(recs):
    print("    olay | EventToRun ready_wait(gorev) | ButtonExec = exec + pre (n) | QueueWait  tx_pre (n)")
    for r in recs:
        p = r["pre"] or {}
        print(f"    {r['id']:>4} | {r['d1']:>9} {p.get('rw_us','-'):>9} ({p.get('rw_task','-')})"
              f" | {r['d2']:>9} = {p.get('bt_exec','-')} + {p.get('bt_pre','-')} ({p.get('bt_n','-')})"
              f" | {r['d3']:>8} {p.get('tx_pre','-'):>8} ({p.get('tx_n','-')})")


def tc_t21(link, scn=3, presses=10):
    """T21: muhasebe denklemleri (TIM-07/08/09). Test planı S5 der; CPU yükü adım 8'de gelince S5'te tekrarlanır."""
    d = run_presses(link, scn, presses)
    if d is None:
        return False
    recs = [r for r in d["recs"] if r["lost"] == 0]
    print_pre(recs)
    ok = True
    ok &= check("T21 PRE her olayda", len(recs) == presses and all(r["pre"] for r in recs),
                f"{sum(1 for r in recs if r['pre'])}/{presses} olayda PRE var")
    if not ok:
        return False
    eq = [abs(r["d2"] - (r["pre"]["bt_exec"] + r["pre"]["bt_pre"])) for r in recs]
    ok &= check("T21 d_ButtonExec = exec + pre", max(eq) <= 2, f"en buyuk fark {max(eq)} us (<= 2)")
    ok &= check("T21 pre>0 => n>0", all(r["pre"]["bt_n"] > 0 for r in recs if r["pre"]["bt_pre"] > 0)
                and all(r["pre"]["tx_n"] > 0 for r in recs if r["pre"]["tx_pre"] > 0), "tutarli")
    ok &= check("T21 ready_wait <= d_EventToRun", all(r["pre"]["rw_us"] <= r["d1"] for r in recs), "tutarli")
    ok &= check("T21 tx_pre <= d_QueueWait", all(r["pre"]["tx_pre"] <= r["d3"] for r in recs), "tutarli")
    return ok


def tc_t22(link, presses=10):
    """T22: S0'da kesilme sebebi yok → hiçbir kesilme sayılmamalı (TIM-10; ölçüm aracının doğrulaması)."""
    d = run_presses(link, 0, presses)
    if d is None:
        return False
    recs = d["recs"]
    print_pre(recs)
    return check("T22 S0'da kesilme yok",
                 len(recs) == presses and all(r["pre"] and r["pre"]["bt_n"] == 0 and r["pre"]["tx_n"] == 0
                                              for r in recs),
                 f"bt_n_pre {[r['pre']['bt_n'] for r in recs if r['pre']]}, "
                 f"tx_n_pre {[r['pre']['tx_n'] for r in recs if r['pre']]}")


# ---- Adım 8: CPU yükü, CAL / MEM / RTS ---------------------------------------

STACK_WORDS = {"hw_tel": 384, "hw_btn": 256, "hw_tx": 512}     # §5 tasarım; ölçüt %20


def timed_run(link, scn, secs):
    i0 = len(link.frames)
    start(link, scn)
    link.drain(secs)
    stop(link)
    d = full_dump(link)
    d["tel"] = [fields(f) for _, f in link.frames[i0:] if f.startswith(b"TEL,")]
    return d


def print_rts(d):
    for r in d["rts"]:
        print(f"    RTS {r['task']:<14} {r['run_us']:>10} us  %{r['pct_x10'] / 10:5.1f}")


def tc_adim8(link, secs=30.0):
    """T04 (S0 sessizlik), T05 (S4/S5 yük), T06 (sıcaklık), T24 (RTS toplamı)."""
    if not require_flags(link, 0):
        return [False]
    res = []
    print(f"-- S0 ({secs:.0f} s) --")
    d = timed_run(link, 0, secs)
    tel_pct = next((r["pct_x10"] for r in d["rts"] if r["task"] == "TelemetryTask"), None)
    res.append(check("T04 S0 sessizligi", not d["tel"] and tel_pct is not None and tel_pct < 1,
                     f"TEL {len(d['tel'])} (0), TelemetryTask payi %{(tel_pct or 0) / 10:.1f} (< %0.1)"))
    for scn, target in ((4, 2000), (5, 5000)):
        print(f"-- S{scn} ({secs:.0f} s) --")
        d = timed_run(link, scn, secs)
        c = d["cal"]
        ok = c["load_target"] == target and abs(c["load_mean"] - target) <= 0.10 * target
        res.append(check(f"T05 S{scn} CPU yuku", ok,
                         f"hedef {c['load_target']} us, ortalama {c['load_mean']} us, en buyuk {c['load_max']} us (±%10)"))
        print_rts(d)
    print(f"-- S1 ({secs:.0f} s) --")
    d = timed_run(link, 1, secs)
    temps = [int(f[3]) for f in d["tel"]]
    jumps = max((abs(a - b) for a, b in zip(temps, temps[1:])), default=0)
    res.append(check("T06 sicaklik", bool(temps) and all(150 <= t <= 450 for t in temps) and jumps <= 20,
                     f"{len(temps)} okuma, aralik {min(temps) / 10 if temps else '-'}…{max(temps) / 10 if temps else '-'} C, "
                     f"ardisik en buyuk fark {jumps / 10} C, ADC ortalama {d['cal']['adc_mean']} us"))
    print(f"-- S3 ({secs:.0f} s) --")
    d = timed_run(link, 3, secs)
    print_rts(d)
    names = {r["task"] for r in d["rts"]}
    total = sum(r["pct_x10"] for r in d["rts"])
    need = {"TelemetryTask", "ButtonTask", "UartTxTask", "IDLE"}
    res.append(check("T24 run-time stats", need <= names and abs(total - 1000) <= 10,
                     f"gorevler {sorted(names)}, yuzde toplami %{total / 10:.1f} (100 ± 1)"))
    return res


def tc_t17(link, secs=600.0, presses=30):
    """T17: 10 dk S5 + 30 basış → bellek payı (SYS-04)."""
    if not require_flags(link, 0):
        return False
    t0 = start(link, 5)
    say(f"S5 kosusu {secs / 60:.0f} dk surecek. Bu surede butona {presses} kez bas (aralikli, duzensiz).")
    collect_btn(link, presses, timeout=secs, settle=0)
    remain = secs - (link.ms() - t0) / 1000
    if remain > 0:
        print(f"    {remain:.0f} s daha bekleniyor...", flush=True)
        link.drain(remain)
    stop(link)
    d = full_dump(link)
    m = d["mem"]
    parts = [f"min_free_heap {m['min_free_heap']} B (>= 1024)"]
    ok = m["min_free_heap"] >= 1024
    for k, words in STACK_WORDS.items():
        need = -(-words * 20 // 100)
        ok &= m[k] >= need
        parts.append(f"{k} {m[k]}/{words} word (>= {need})")
    print_rts(d)
    return check("T17 bellek payi", ok, ", ".join(parts))


def tc_t18(link, level):
    """T18a (büyük taşma → HardFault, LD2 1 Hz) / T18b (küçük taşma → FreeRTOS kancası, LD2 10 Hz)."""
    want_flags, want_hz, name = (0x08, "1", "T18a buyuk tasma") if level == 1 else (0x18, "10", "T18b kucuk tasma")
    if not require_flags(link, want_flags):
        return False
    start(link, 0)
    say("Butona BIR kez bas. Kart yanit vermeyi kesmeli; yesil LED'i (LD2) izle.")
    link.drain(8)
    ans = input("    LD2 nasil yanip soniyor? (1 = yavas ~1 Hz, 10 = hizli ~10 Hz, 0 = yanip sonmuyor): ").strip()
    alive = True
    try:
        link.send("CMD,STOP"); link.wait_for("ACK,STOP", timeout=2)
    except TimeoutError:
        alive = False
    return check(name, ans == want_hz and not alive,
                 f"LD2 {ans} Hz (beklenen {want_hz} Hz: "
                 f"{'HardFault' if level == 1 else 'vApplicationStackOverflowHook'}), kart yanit vermiyor: {not alive}")

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="ör. COM5; boşsa portlar listelenir")
    ap.add_argument("--tc", default="adim4", choices=["adim4", "T02", "T03", "T11", "T14", "T07", "T08", "T12", "T13", "T15", "T16", "T21", "T22", "adim8", "T17", "T18"])
    ap.add_argument("--secs", type=float, default=60.0, help="koşu süresi (test planı: 60 s)")
    ap.add_argument("--scn", type=int, default=3, help="T21 için senaryo (varsayılan S3)")
    ap.add_argument("--ovf", type=int, default=2, choices=[1, 2], help="T18: 1 = büyük taşma (T18a), 2 = küçük (T18b)")
    a = ap.parse_args()

    if not a.port:
        for p in list_ports.comports():
            print(f"{p.device}\t{p.description}")
        sys.exit("--port ile birini seç (NUCLEO: 'STMicroelectronics STLink Virtual COM Port')")

    link = Link(a.port)
    results = []
    scns = [1, 2, 3] if a.tc in ("adim4", "T03") else [3]
    print(f"== hil_check {a.tc} | port {a.port} | {a.secs:.0f} s/senaryo | {dt.datetime.now():%Y-%m-%d %H:%M} ==")
    try:
        if a.tc == "T07":
            results.append(tc_t07(link)); scns = []
        elif a.tc == "T08":
            results.append(tc_t08(link)); scns = []
        elif a.tc in ("T12", "T13", "T15", "T16"):
            fn = {"T12": tc_t12, "T13": tc_t13, "T15": tc_t15, "T16": tc_t16}[a.tc]
            results.append(fn(link)); scns = []
        elif a.tc == "T21":
            results.append(tc_t21(link, a.scn)); scns = []
        elif a.tc == "T22":
            results.append(tc_t22(link)); scns = []
        elif a.tc == "adim8":
            results.extend(tc_adim8(link, a.secs)); scns = []
        elif a.tc == "T17":
            results.append(tc_t17(link, a.secs)); scns = []
        elif a.tc == "T18":
            results.append(tc_t18(link, a.ovf)); scns = []
        for scn in scns:
            print(f"-- S{scn} kosusu ({a.secs:.0f} s) --")
            r = run_once(link, scn, a.secs)
            if a.tc in ("adim4", "T03"):
                results.append(tc_t03(r, scn))
            if scn == 3 and a.tc in ("adim4", "T02", "T11"):
                results.extend(tc_t02_t11(link, r))
            if scn == 3 and a.tc in ("adim4", "T14"):
                results.append(tc_t14(r))
        ver = next((f for _, f in link.frames if f.startswith(b"VER,")), b"VER yok")
        print(f"  firmware: {ver.decode().rstrip()}")
    except TimeoutError as e:
        results.append(check("iletisim", False, str(e)))
    finally:
        path = link.save(a.tc)
        print(f"ham kayit: {path.relative_to(ROOT)}")
        link.ser.close()

    ok = all(results)
    print(f"== SONUC: {'GECTI' if ok else 'KALDI'} ({sum(results)}/{len(results)}) ==")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
