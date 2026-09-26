#!/usr/bin/env python3
"""
hil_check.py — kart üstü (hardware-in-the-loop) otomatik testler.
Test planı: hafta-01/docs/specs/03-test-plan.md §6.

Kullanım (Windows örneği):
    py -m pip install -r interface/requirements.txt
    py interface/tools/hil_check.py --port COM5 --tc adim4
    py interface/tools/hil_check.py --port COM5 --tc T03 --secs 10     # hızlı deneme

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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="ör. COM5; boşsa portlar listelenir")
    ap.add_argument("--tc", default="adim4", choices=["adim4", "T02", "T03", "T11", "T14"])
    ap.add_argument("--secs", type=float, default=60.0, help="koşu süresi (test planı: 60 s)")
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
