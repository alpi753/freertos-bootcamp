"""
Ana pencere (tasarım §11). Düzen:

  ┌ Port [▾] [↻] [Bağlan] ── Senaryo [▾] [Başlat] [Durdur] [Döküm al] ── ● durum ┐
  │ Canlı telemetri (sol)                 │ Buton + kayıp göstergeleri (sağ)     │
  │ Sonuçlar: olay başına yığılmış çubuk + ButtonExec exec/preempt ayrımı         │
  └──────────────────────────────────────────────────────────────────────────────┘

UI-09: Grafiklerin x ekseni PC saati DEĞİLDİR.
  - Telemetri: x = seq × periyot (kartın ürettiği sıra numarasından).
  - Sonuçlar: x = event_id; süreler DUMP'taki REC/PRE alanlarından.
"""
import datetime as dt
import pathlib
from collections import deque

import pyqtgraph as pg
import serial
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from .csv_writer import row_for, write_csv
from .serial_worker import SerialWorker, available_ports
from .session import PERIOD_MS, RUNNING, Session

MEAS_DIR = pathlib.Path(__file__).resolve().parents[2] / "measurements"   # hafta-01/measurements
RAW_DIR = pathlib.Path(__file__).resolve().parents[2] / "docs" / "test-results" / "raw"
PLOT_POINTS = 3000

# Aralık renkleri (EventToRun, ButtonExec, QueueWait, UartTx)
COLORS = ["#4C78A8", "#F58518", "#54A24B", "#B279A2"]
NAMES = ["EventToRun", "ButtonExec", "QueueWait", "UartTx"]
KEYS = ["d_EventToRun_us", "d_ButtonExec_us", "d_QueueWait_us", "d_UartTx_us"]


def _dot(color):
    return f"<span style='color:{color}; font-size:16px'>●</span>"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UART Monitor — hafta-01")
        self.resize(1200, 820)
        self.session = Session()
        self.worker: SerialWorker | None = None
        self.tel_x = deque(maxlen=PLOT_POINTS)
        self.tel_y = deque(maxlen=PLOT_POINTS)
        self._dirty = False
        self._dump_raw = None        # DUMP çerçevelerinin ham kopyası (D05 karşılaştırması için)
        self._build()
        self.refresh_ports()
        self._update_controls()

        # Çizim 20 Hz ile sınırlı: gelen her TEL'de yeniden çizmek gereksiz yük.
        self.timer = QTimer(self, interval=50, timeout=self._redraw)
        self.timer.start()

    # ------------------------------------------------------------------ düzen
    def _build(self):
        central = QWidget()
        root = QVBoxLayout(central)

        # Üst çubuk
        bar = QHBoxLayout()
        self.port_box = QComboBox(minimumWidth=260)
        self.btn_refresh = QPushButton("↻", maximumWidth=32, clicked=self.refresh_ports)
        self.btn_connect = QPushButton("Bağlan", clicked=self.toggle_connect)
        self.scn_box = QComboBox()
        for n in range(6):
            p = PERIOD_MS[n]
            self.scn_box.addItem(f"S{n} · " + (f"{1000 // p} Hz" if p else "telemetri yok"), n)
        self.scn_box.setCurrentIndex(3)
        self.btn_start = QPushButton("Başlat", clicked=self.cmd_start)
        self.btn_stop = QPushButton("Durdur", clicked=lambda: self.send("CMD,STOP"))
        self.btn_dump = QPushButton("Döküm al", clicked=lambda: self.send("CMD,DUMP"))
        self.lbl_conn = QLabel(_dot("#999") + " Bağlı değil")
        for w in (QLabel("Port"), self.port_box, self.btn_refresh, self.btn_connect):
            bar.addWidget(w)
        bar.addSpacing(24)
        for w in (QLabel("Senaryo"), self.scn_box, self.btn_start, self.btn_stop, self.btn_dump):
            bar.addWidget(w)
        bar.addStretch(1)
        bar.addWidget(self.lbl_conn)
        root.addLayout(bar)

        split = QSplitter(Qt.Vertical)
        top = QWidget()
        top_l = QHBoxLayout(top)
        top_l.setContentsMargins(0, 0, 0, 0)

        # Sol: canlı telemetri
        left = QGroupBox()
        ll = QVBoxLayout(left)
        self.lbl_run = QLabel("—")
        self.lbl_run.setStyleSheet("font-size:15px; font-weight:600")
        self.tel_plot = pg.PlotWidget()
        self.tel_plot.setLabel("left", "Sıcaklık", units="°C")
        self.tel_plot.setLabel("bottom", "koşu zamanı (seq × periyot, MCU)", units="s")
        self.tel_plot.showGrid(x=True, y=True, alpha=0.3)
        self.tel_curve = self.tel_plot.plot(pen=pg.mkPen("#4C78A8", width=1.5))
        self.lbl_last_tel = QLabel("son: —")
        self.lbl_last_tel.setStyleSheet("font-family:monospace")
        ll.addWidget(self.lbl_run)
        ll.addWidget(self.tel_plot, 1)
        ll.addWidget(self.lbl_last_tel)
        top_l.addWidget(left, 3)

        # Sağ: buton + kayıplar + son yanıt
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        g_btn = QGroupBox("Buton")
        gl = QVBoxLayout(g_btn)
        self.lbl_btn = QLabel("Henüz basılmadı")
        self.lbl_btn.setAlignment(Qt.AlignCenter)
        self.lbl_btn.setMinimumHeight(70)
        self._btn_style(False)
        self.lbl_btn_raw = QLabel("")
        self.lbl_btn_raw.setStyleSheet("font-family:monospace")
        gl.addWidget(self.lbl_btn)
        gl.addWidget(self.lbl_btn_raw)
        self.flash = QTimer(self, singleShot=True, interval=400, timeout=lambda: self._btn_style(False))

        g_loss = QGroupBox("Kayıplar")
        lg = QGridLayout(g_loss)
        self.loss = {}
        rows = [
            ("pc_lost", "PC · TEL sıra boşluğu", "Bu koşuda TEL sıra numarasında atlanan adet (kartta düşürülenler dahil)"),
            ("tel_dropped", "MCU · tel_dropped", "Kuyruk dolu olduğu için kartın gönderemediği TEL (SUM'dan)"),
            ("btn_dropped", "MCU · btn_dropped", "Kuyruk dolu olduğu için kaybolan BTN (SUM'dan)"),
            ("uart_lost", "Hat kaybı (tel_sent − alınan TEL)", "SUM geldikten sonra hesaplanır; 0 olmalı. Koşu ortasında bağlanıldıysa anlamsız."),
            ("bad", "Bozuk çerçeve", "64 bayt olmayan ya da tipi bilinmeyen çerçeve"),
        ]
        for i, (k, name, tip) in enumerate(rows):
            a, b = QLabel(name), QLabel("—")
            a.setToolTip(tip)
            b.setAlignment(Qt.AlignRight)
            b.setStyleSheet("font-family:monospace; font-size:14px")
            lg.addWidget(a, i, 0)
            lg.addWidget(b, i, 1)
            self.loss[k] = b

        g_reply = QGroupBox("Kart yanıtı")
        rlay = QVBoxLayout(g_reply)
        self.lbl_reply = QLabel("—")
        self.lbl_reply.setStyleSheet("font-family:monospace")
        self.lbl_ver = QLabel("VER: —")
        self.lbl_ver.setStyleSheet("font-family:monospace; color:#666")
        rlay.addWidget(self.lbl_reply)
        rlay.addWidget(self.lbl_ver)

        rl.addWidget(g_btn)
        rl.addWidget(g_loss)
        rl.addWidget(g_reply)
        rl.addStretch(1)
        top_l.addWidget(right, 2)
        split.addWidget(top)

        # Alt: sonuçlar
        res = QGroupBox("Sonuçlar (son döküm)")
        resl = QVBoxLayout(res)
        plots = QHBoxLayout()
        self.res_plot = pg.PlotWidget(title="Olay başına süreler (yığılmış)")
        self.res_plot.setLabel("left", "süre", units="ms")
        self.res_plot.setLabel("bottom", "event_id")
        self.res_plot.showGrid(y=True, alpha=0.3)
        self.res_plot.addLegend(offset=(-10, 5))
        self.exec_plot = pg.PlotWidget(title="ButtonExec = exec + preempt")
        self.exec_plot.setLabel("left", "süre", units="µs")
        self.exec_plot.setLabel("bottom", "event_id")
        self.exec_plot.showGrid(y=True, alpha=0.3)
        self.exec_plot.addLegend(offset=(-10, 5))
        plots.addWidget(self.res_plot, 3)
        plots.addWidget(self.exec_plot, 2)
        self.lbl_csv = QLabel("Ölçüm dosyası: —")
        self.lbl_csv.setTextInteractionFlags(Qt.TextSelectableByMouse)
        resl.addLayout(plots, 1)
        resl.addWidget(self.lbl_csv)
        split.addWidget(res)
        split.setSizes([460, 360])
        root.addWidget(split, 1)
        self.setCentralWidget(central)

    def _btn_style(self, hot):
        bg = "#F58518" if hot else "#f3f3f3"
        fg = "white" if hot else "#222"
        self.lbl_btn.setStyleSheet(f"font-size:22px; font-weight:700; border-radius:8px; background:{bg}; color:{fg}")

    # ------------------------------------------------------------- bağlantı
    def refresh_ports(self):
        cur = self.port_box.currentData()
        self.port_box.clear()
        for dev, desc in available_ports():
            self.port_box.addItem(f"{dev} — {desc}", dev)
            if cur is None and "STLink" in desc:
                cur = dev
        i = self.port_box.findData(cur)
        if i >= 0:
            self.port_box.setCurrentIndex(i)

    def toggle_connect(self):
        if self.worker:
            self._disconnect("Bağlantı kesildi", "#999")
            return
        port = self.port_box.currentData()
        if not port:
            self.lbl_conn.setText(_dot("#E45756") + " Port seçilmedi")
            return
        w = SerialWorker(port)
        try:
            w.open()
        except (serial.SerialException, OSError) as e:
            self.lbl_conn.setText(_dot("#E45756") + f" Açılamadı: {e}")
            return
        w.frames.connect(self.on_frames)
        w.lost.connect(lambda msg: self._disconnect(f"Bağlantı koptu ({msg})", "#E45756"))
        self.worker = w
        self.session = Session()
        self.tel_x.clear(); self.tel_y.clear()
        w.start()
        self.lbl_conn.setText(_dot("#54A24B") + f" Bağlı · {port}")
        self._update_controls()
        self._dirty = True

    def _disconnect(self, text, color):
        w, self.worker = self.worker, None
        if w:
            w.stop()
        self.lbl_conn.setText(_dot(color) + " " + text)
        self.refresh_ports()
        self._update_controls()

    # --------------------------------------------------------------- komutlar
    def send(self, line):
        if self.worker and self.worker.send(line):
            self.session.sent(line)
            self.lbl_reply.setText(f">> {line}")

    def cmd_start(self):
        n = self.scn_box.currentData()
        self.send(f"CMD,SCN,{n}")
        self.send("CMD,START")

    def _update_controls(self):
        on = self.worker is not None
        s = self.session
        self.btn_connect.setText("Bağlantıyı kes" if on else "Bağlan")
        self.port_box.setEnabled(not on)
        self.btn_refresh.setEnabled(not on)
        # UI-06: koşu sırasında yalnızca Durdur
        self.scn_box.setEnabled(on and s.allowed("SCN"))
        self.btn_start.setEnabled(on and s.allowed("START"))
        self.btn_stop.setEnabled(on and s.allowed("STOP"))
        self.btn_dump.setEnabled(on and s.allowed("DUMP"))

    # ------------------------------------------------------------ çerçeveler
    def on_frames(self, frames):
        s = self.session
        for fr in frames:
            if fr.startswith(b"ACK,DUMP"):
                self._dump_raw = []
            if self._dump_raw is not None:
                self._dump_raw.append(fr)
            kind, f = s.handle(fr)
            if kind == "TEL":
                p = PERIOD_MS.get(f["scn"], 0) or 1
                self.tel_x.append(f["seq"] * p / 1000.0)
                self.tel_y.append(f["temp_x10"] / 10.0)
                self.lbl_last_tel.setText("son: " + fr.decode("ascii", "replace").rstrip())
            elif kind == "BTN":
                eid = f["event_id"]
                self.lbl_btn.setText(f"Butona basıldı · Olay {eid}" if eid else "Butona basıldı · ölçüm dışı")
                self.lbl_btn_raw.setText(fr.decode("ascii", "replace").rstrip())
                self._btn_style(True)
                self.flash.start()
            elif kind in ("ACK", "NAK", "END"):
                self.lbl_reply.setText(fr.decode("ascii", "replace").rstrip())
                if kind == "ACK" and f["args"][:1] == ["START"]:
                    self.tel_x.clear(); self.tel_y.clear()
                if kind == "END" and s.last_dump is not None:
                    self.on_dump(s.last_dump)
            elif kind == "VER":
                self.lbl_ver.setText(f"VER: {f['git_hash']} · {f['build']} · bayrak 0x{f['test_flags']}")
        self._dirty = True
        self._update_controls()

    def _redraw(self):
        if not self._dirty:
            return
        self._dirty = False
        s = self.session
        self.tel_curve.setData(list(self.tel_x), list(self.tel_y))
        scn = s.run_scn if s.run_scn is not None else s.scn
        p = PERIOD_MS.get(scn, 0)
        rate = f"Telemetri {1000 // p} Hz" if p else "Telemetri yok"
        self.lbl_run.setText(f"S{scn} · {rate} · {s.state}"
                             + (f" · son olay {s.last_btn[0]}" if s.last_btn else ""))
        su = s.last_sum
        bad = s.bad_frames + (self.worker.bad if self.worker else 0)
        vals = {
            "pc_lost": s.pc_lost,
            "tel_dropped": su["tel_dropped"] if su else "—",
            "btn_dropped": su["btn_dropped"] if su else "—",
            "uart_lost": s.uart_lost_estimate() if su else "—",
            "bad": bad,
        }
        for k, v in vals.items():
            self.loss[k].setText(str(v))
            warn = isinstance(v, int) and v > 0
            self.loss[k].setStyleSheet("font-family:monospace; font-size:14px" + ("; color:#E45756; font-weight:700" if warn else ""))

    # ---------------------------------------------------------------- döküm
    def on_dump(self, d):
        scn = d.sum["scn"] if d.sum else (d.recs[0]["scn"] if d.recs else self.session.scn)
        MEAS_DIR.mkdir(parents=True, exist_ok=True)
        path = MEAS_DIR / f"S{scn}.csv"
        if path.exists():                          # eski ölçümü ezme: tarihli ada taşı
            stamp = dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y%m%d_%H%M%S")
            path.rename(path.with_name(f"S{scn}_{stamp}.csv"))
        write_csv(path, d.recs, d.pres)
        if self._dump_raw:                         # ham döküm: CSV'nin kaynağı (D05)
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            raw = RAW_DIR / f"UI-DUMP-S{scn}-{dt.datetime.now():%Y-%m-%d_%H%M%S}.log"
            raw.write_text("".join(f.decode("ascii", "replace").rstrip() + "\n" for f in self._dump_raw),
                           encoding="ascii", errors="replace")
            self._dump_raw = None
        miss = "" if len(d.recs) == d.expected else f"  ⚠ beklenen {d.expected} REC, gelen {len(d.recs)}"
        self.lbl_csv.setText(f"Ölçüm dosyası: {path}  ({len(d.recs)} olay){miss}")
        self.plot_results([row_for(r, d.pres.get(r["event_id"])) for r in d.recs])

    def plot_results(self, rows):
        """UI-08: olay başına yığılmış çubuk + exec/preempt ayrımı; kayıp olaylar kırmızı."""
        for pw in (self.res_plot, self.exec_plot):
            pw.clear()
            if pw.plotItem.legend:
                pw.plotItem.legend.clear()
        if not rows:
            return
        x = [r["event_id"] for r in rows]
        base = [0.0] * len(rows)
        for name, key, col in zip(NAMES, KEYS, COLORS):
            h = [(r[key] if r[key] != "" else 0) / 1000.0 for r in rows]
            self.res_plot.addItem(pg.BarGraphItem(x=x, y0=base, height=h, width=0.7, brush=col, name=name))
            base = [b + v for b, v in zip(base, h)]
        lost = [(r["event_id"], b) for r, b in zip(rows, base) if r["lost"] != 0]
        if lost:
            self.res_plot.plot([e for e, _ in lost], [b + 0.3 for _, b in lost], pen=None,
                               symbol="x", symbolSize=14, symbolPen=pg.mkPen("#E45756", width=3),
                               name="kayıp (lost≠0)")

        have_pre = [r for r in rows if r["bt_exec_us"] != ""]
        if have_pre:
            xe = [r["event_id"] for r in have_pre]
            ex = [r["bt_exec_us"] for r in have_pre]
            pr = [r["bt_preempt_us"] for r in have_pre]
            self.exec_plot.addItem(pg.BarGraphItem(x=xe, y0=[0] * len(ex), height=ex, width=0.7,
                                                   brush="#F58518", name="exec"))
            self.exec_plot.addItem(pg.BarGraphItem(x=xe, y0=ex, height=pr, width=0.7,
                                                   brush="#E45756", name="preempt"))

    def closeEvent(self, ev):
        if self.worker:
            self.worker.stop()
        super().closeEvent(ev)
