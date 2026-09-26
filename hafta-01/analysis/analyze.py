#!/usr/bin/env python3
"""
analyze.py — ölçüm kampanyasının çevrimdışı analizi (test planı §8, UI-10, DOC-04).

    py hafta-01/analysis/analyze.py --check S3     # bir koşunun bütünlüğü (V1…V6)
    py hafta-01/analysis/analyze.py                # summary.csv + plots/*.png + report.md

Girdiler (arayüzün yazdığı):
    measurements/S<n>.csv                 olay başına satır (§8 şeması)
    measurements/raw/S<n>-<tarih>.log     koşunun ham kaydı (START → END,DUMP), en yenisi kullanılır

Çıktılar:
    measurements/summary.csv
    analysis/plots/latency_boxplot.png, breakdown_S<n>.png, preemption.png
    analysis/report.md                    yalnızca ölçülen değerler; yorum gozlemler.md'ye aittir

Gecikme değerleri hiçbir ölçütte yer almaz: onlar gözlemdir (test planı §8.2).
"""
import argparse
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import pandas as pd               # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]               # hafta-01/
MEAS = ROOT / "measurements"
PLOTS = ROOT / "analysis" / "plots"
REPORT = ROOT / "analysis" / "report.md"

N_MIN = 30
TOL_US = 2
REC_DELTA_MAX = 9_999_999
INTERVALS = ["d_EventToRun_us", "d_ButtonExec_us", "d_QueueWait_us", "d_UartTx_us", "d_Total_us"]
SHORT = {k: k[2:-3] for k in INTERVALS}                          # d_Total_us → Total
COLORS = ["#4C78A8", "#F58518", "#54A24B", "#B279A2"]
SCN_DESC = {0: "telemetri yok", 1: "100 ms", 2: "20 ms", 3: "10 ms", 4: "10 ms + 2 ms yük", 5: "10 ms + 5 ms yük"}
SUM_KEYS = ["scn", "events", "tel_sent", "tel_dropped", "btn_dropped", "q_hw", "rec_overflow", "bounce_rej", "frame_err"]


# ---------------------------------------------------------------- ham log
def latest_log(scn, meas=MEAS):
    logs = sorted((meas / "raw").glob(f"S{scn}-*.log"))
    return logs[-1] if logs else None


def read_log(path):
    """Ham koşu kaydından VER, SUM, CAL, MEM, RTS, alınan TEL sayısı ve PC sayaçları."""
    out = {"ver": None, "sum": None, "cal": None, "mem": None, "rts": [], "tel_rx": 0, "bad_frames": None, "path": path}
    for line in open(path, encoding="ascii", errors="replace"):
        line = line.strip()
        if line.startswith("# PC"):
            for kv in line[4:].split():
                k, _, v = kv.partition("=")
                if k == "bad_frames":
                    out["bad_frames"] = int(v)
            continue
        x = line.split(",")
        if x[0] == "TEL":
            out["tel_rx"] += 1
        elif x[0] == "VER" and len(x) == 4:
            out["ver"] = {"hash": x[1], "build": x[2], "flags": x[3]}
        elif x[0] == "SUM" and len(x) == 10:
            out["sum"] = dict(zip(SUM_KEYS, [x[1]] + [int(v) for v in x[2:]]))
        elif x[0] == "CAL" and len(x) == 6:
            out["cal"] = dict(zip(["load_target_us", "load_mean_us", "load_max_us", "adc_mean_us", "hook_ns"], map(int, x[1:])))
        elif x[0] == "MEM" and len(x) == 5:
            out["mem"] = dict(zip(["min_free_heap", "hw_tel", "hw_btn", "hw_tx"], map(int, x[1:])))
        elif x[0] == "RTS" and len(x) == 4:
            out["rts"].append({"task": x[1], "run_us": int(x[2]), "pct": int(x[3]) / 10})
    return out


# ------------------------------------------------------------- bütünlük
def check_run(df, log):
    """V1…V6 (test planı §8.2). [(ad, geçti mi, ayrıntı)] döndürür."""
    res = []
    n = len(df)
    res.append(("V1 olay sayısı ≥ 30", n >= N_MIN, f"{n} olay"))

    s = log["sum"]
    if s is None:
        res.append(("V2 rec_overflow = 0, frame_err = 0", False, "SUM yok"))
    else:
        res.append(("V2 rec_overflow = 0, frame_err = 0", s["rec_overflow"] == 0 and s["frame_err"] == 0,
                    f"rec_overflow {s['rec_overflow']}, frame_err {s['frame_err']}"))

    bad = log["bad_frames"]
    if s is None or bad is None:
        res.append(("V3 USB hattında kayıp yok", False, "SUM ya da '# PC' satırı yok"))
    else:
        line_lost = s["tel_sent"] - log["tel_rx"]
        res.append(("V3 USB hattında kayıp yok", bad == 0 and line_lost == 0,
                    f"bozuk çerçeve {bad}, tel_sent {s['tel_sent']} − alınan TEL {log['tel_rx']} = {line_lost}"
                    f" (kartın düşürdüğü {s['tel_dropped']} TEL gözlemdir, ölçüt değil)"))

    ok = df[df["lost"] == 0]
    d = ok[INTERVALS[:4]]
    v4 = bool(((d >= 0) & (d < REC_DELTA_MAX)).all().all())
    res.append(("V4 t₀ ≤ t₁ ≤ t₂ ≤ t₃ ≤ t₄ (lost = 0)", v4, f"{len(ok)} tam olay, {n - len(ok)} kayıp olay"))

    pre = df.dropna(subset=["bt_exec_us"])
    e1 = (pre["d_ButtonExec_us"] - pre["bt_exec_us"] - pre["bt_preempt_us"]).abs() > TOL_US
    e2 = (pre["bt_preempt_us"] > 0) & (pre["bt_n_preempt"] == 0)
    e3 = pre["ready_wait_us"] > pre["d_EventToRun_us"]
    pok = pre[pre["lost"] == 0]
    e4 = pok["tx_preempt_us"] > pok["d_QueueWait_us"]
    bad_ids = sorted(set(pre[e1 | e2 | e3]["event_id"]) | set(pok[e4]["event_id"]))
    res.append(("V5 T21 denklemleri", len(pre) == n and not bad_ids,
                f"PRE {len(pre)}/{n}" + (f", tutmayan olaylar {bad_ids}" if bad_ids else ", hepsi tutuyor")))

    v = log["ver"]
    if v is None:
        res.append(("V6 VER: Release, bayrak 00, hash temiz", False, "VER yok"))
    else:
        v6 = v["build"] == "Release" and v["flags"] == "00" and not v["hash"].endswith("+") and v["hash"] != "nogit"
        res.append(("V6 VER: Release, bayrak 00, hash temiz", v6, f"VER,{v['hash']},{v['build']},{v['flags']}"))
    return res


def load_csv(scn, meas=MEAS):
    p = meas / f"S{scn}.csv"
    return pd.read_csv(p) if p.exists() else None


def cmd_check(scn, meas=MEAS):
    df, log = load_csv(scn, meas), latest_log(scn, meas)
    if df is None or log is None:
        print(f"S{scn}: {'CSV' if df is None else 'ham log'} bulunamadı")
        return False
    print(f"== S{scn} bütünlük | {df.shape[0]} olay | log: {log.name} ==")
    res = check_run(df, read_log(log))
    for name, ok, det in res:
        print(f"  [{'GECTI' if ok else 'KALDI'}] {name}: {det}")
    ok = all(r[1] for r in res)
    print(f"== {'GEÇERLİ' if ok else 'GEÇERSİZ: koşuyu tekrarla, bu logu measurements/raw/invalid/ altına taşı'} ==")
    return ok


# --------------------------------------------------------------- özet
def summarize(frames):
    """frames: {scn: DataFrame} → özet DataFrame (senaryo × aralık istatistikleri)."""
    rows = []
    for scn, df in sorted(frames.items()):
        ok = df[df["lost"] == 0]
        base = {"scenario": f"S{scn}", "n_events": len(df), "n_lost": int((df["lost"] != 0).sum())}
        for col in INTERVALS + ["ready_wait_us", "bt_exec_us", "bt_preempt_us", "tx_preempt_us"]:
            src = df if col in ("d_EventToRun_us", "d_ButtonExec_us", "ready_wait_us", "bt_exec_us", "bt_preempt_us") else ok
            x = src[col].dropna()
            name = SHORT.get(col, col[:-3])
            if x.empty:
                continue
            base.update({f"{name}_min": x.min(), f"{name}_median": x.median(), f"{name}_mean": round(x.mean(), 1),
                         f"{name}_p95": x.quantile(0.95), f"{name}_max": x.max()})
        base["bt_n_preempt_sum"] = int(df["bt_n_preempt"].sum()) if "bt_n_preempt" in df else 0
        rows.append(base)
    return pd.DataFrame(rows)


def plot_all(frames, plots=PLOTS):
    plots.mkdir(parents=True, exist_ok=True)
    scns = sorted(frames)
    labels = [f"S{s}" for s in scns]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    data = [frames[s].loc[frames[s]["lost"] == 0, "d_Total_us"].dropna() / 1000 for s in scns]
    ax.boxplot(data, tick_labels=labels, showfliers=True)
    ax.set_ylabel("d_Total (ms)")
    ax.set_title("Buton olayından UART tamamlanmasına toplam süre (lost = 0)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(plots / "latency_boxplot.png", dpi=120); plt.close(fig)

    for s in scns:
        df = frames[s]
        fig, ax = plt.subplots(figsize=(9, 4))
        bottom = pd.Series(0.0, index=df.index)
        for col, c in zip(INTERVALS[:4], COLORS):
            h = df[col].fillna(0) / 1000
            ax.bar(df["event_id"], h, bottom=bottom, color=c, label=SHORT[col], width=0.75)
            bottom += h
        lost = df[df["lost"] != 0]
        if not lost.empty:
            ax.scatter(lost["event_id"], bottom[lost.index] + 0.2, marker="x", color="#E45756", s=60, label="kayıp (lost≠0)", zorder=3)
        ax.set_xlabel("event_id"); ax.set_ylabel("süre (ms)")
        ax.set_title(f"S{s} ({SCN_DESC.get(s, '')}): olay başına aralıklar")
        ax.legend(loc="upper right", fontsize=8, ncol=5); ax.grid(axis="y", alpha=0.3)
        fig.tight_layout(); fig.savefig(plots / f"breakdown_S{s}.png", dpi=120); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, col, title in zip(axes, ["bt_preempt_us", "ready_wait_us"],
                              ["ButtonExec içinde kesik kalınan süre", "t₀→t₁ arasında başka görevlerin süresi"]):
        ax.boxplot([frames[s][col].dropna() for s in scns], tick_labels=labels)
        ax.set_title(title, fontsize=10); ax.set_ylabel(f"{col} (µs)"); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(plots / "preemption.png", dpi=120); plt.close(fig)


def fmt(v):
    return "—" if pd.isna(v) else (f"{v:.0f}" if float(v).is_integer() else f"{v:.1f}")


def write_report(summary, logs, frames, path=REPORT):
    L = ["# Hafta 01 — ölçüm raporu", "",
         "> Bu dosya `analysis/analyze.py` tarafından üretilir; elle düzenleme. Yalnızca ölçülen değerleri içerir.",
         "> Yorum ve çıkarımlar `gozlemler.md` dosyasındadır.", "",
         "Tüm süreler µs. Kaynak: [summary.csv](../measurements/summary.csv).", ""]
    L += ["## Koşular", "", "| Senaryo | Olay | Kayıp olay | tel_sent | tel_dropped | btn_dropped | q_hw | Firmware | Ham log |",
          "|---|---|---|---|---|---|---|---|---|"]
    for _, r in summary.iterrows():
        s = int(r["scenario"][1:]); lg = logs.get(s)
        su = lg["sum"] if lg else None
        ver = f"`{lg['ver']['hash']}` {lg['ver']['build']} {lg['ver']['flags']}" if lg and lg["ver"] else "—"
        link = f"[{lg['path'].name}](../measurements/raw/{lg['path'].name})" if lg else "—"
        L.append(f"| {r['scenario']} ({SCN_DESC.get(s, '')}) | {r['n_events']} | {r['n_lost']} | "
                 + " | ".join(str(su[k]) if su else "—" for k in ["tel_sent", "tel_dropped", "btn_dropped", "q_hw"])
                 + f" | {ver} | {link} |")
    L += ["", "## Aralıklar (medyan / p95 / en büyük)", "",
          "| Senaryo | EventToRun | ButtonExec | QueueWait | UartTx | Total |", "|---|---|---|---|---|---|"]
    for _, r in summary.iterrows():
        cells = [f"{fmt(r.get(f'{SHORT[c]}_median'))} / {fmt(r.get(f'{SHORT[c]}_p95'))} / {fmt(r.get(f'{SHORT[c]}_max'))}"
                 for c in INTERVALS]
        L.append(f"| {r['scenario']} | " + " | ".join(cells) + " |")
    L += ["", "## Görev değişimi (medyan / en büyük)", "",
          "| Senaryo | ready_wait | bt_exec | bt_preempt | tx_preempt | toplam bt_n_preempt |", "|---|---|---|---|---|---|"]
    for _, r in summary.iterrows():
        cells = [f"{fmt(r.get(f'{k}_median'))} / {fmt(r.get(f'{k}_max'))}" for k in ["ready_wait", "bt_exec", "bt_preempt", "tx_preempt"]]
        L.append(f"| {r['scenario']} | " + " | ".join(cells) + f" | {r['bt_n_preempt_sum']} |")
    L += ["", "## Sistem (DUMP'taki CAL, MEM, RTS)", "",
          "| Senaryo | ADC okuma ort. | Yük hedef / ort. / en büyük | Kanca maliyeti (ns) | En düşük boş heap (B) | Boş stack (word) Tel/Btn/Tx | CPU payı (%) |",
          "|---|---|---|---|---|---|---|"]
    for s, lg in sorted(logs.items()):
        c, m = lg["cal"], lg["mem"]
        rts = ", ".join(f"{t['task']} {t['pct']:.1f}" for t in lg["rts"]) or "—"
        L.append(f"| S{s} | {c['adc_mean_us'] if c else '—'} | "
                 + (f"{c['load_target_us']} / {c['load_mean_us']} / {c['load_max_us']}" if c else "—")
                 + f" | {c['hook_ns'] if c else '—'} | {m['min_free_heap'] if m else '—'} | "
                 + (f"{m['hw_tel']} / {m['hw_btn']} / {m['hw_tx']}" if m else "—") + f" | {rts} |")
    L += ["", "## Grafikler", "", "![d_Total](plots/latency_boxplot.png)", "", "![Görev değişimi](plots/preemption.png)", ""]
    for s in sorted(frames):
        L += [f"![S{s}](plots/breakdown_S{s}.png)", ""]
    path.write_text("\n".join(L), encoding="utf-8")


def cmd_all(meas=MEAS, plots=PLOTS, report=REPORT):
    frames = {s: df for s in range(6) if (df := load_csv(s, meas)) is not None}
    if not frames:
        sys.exit("measurements/S<n>.csv bulunamadı")
    logs = {s: read_log(p) for s in frames if (p := latest_log(s, meas))}
    summary = summarize(frames)
    summary.to_csv(meas / "summary.csv", index=False)
    plot_all(frames, plots)
    write_report(summary, logs, frames, report)
    missing = [f"S{s}" for s in range(6) if s not in frames]
    print(f"summary.csv, {len(frames) + 2} grafik, report.md yazıldı ({', '.join(f'S{s}' for s in sorted(frames))})"
          + (f"; eksik: {', '.join(missing)}" if missing else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", metavar="S<n>", help="tek koşunun bütünlük kontrolü")
    a = ap.parse_args()
    if a.check:
        sys.exit(0 if cmd_check(int(a.check.upper().lstrip("S"))) else 1)
    cmd_all()


if __name__ == "__main__":
    main()
