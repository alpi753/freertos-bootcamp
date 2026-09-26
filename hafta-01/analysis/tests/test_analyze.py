"""TC-U09: analyze.py — sentetik S0…S5 verisiyle özet, grafik, rapor ve bütünlük (V1…V6)."""
import csv
import pathlib
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import analyze as A                                   # noqa: E402

COLS = ["event_id", "scenario", "t0_us", "t1_us", "t2_us", "t3_us", "t4_us", "lost",
        "d_EventToRun_us", "d_ButtonExec_us", "d_QueueWait_us", "d_UartTx_us", "d_Total_us",
        "ready_wait_us", "ready_wait_task", "bt_exec_us", "bt_n_preempt", "bt_preempt_us",
        "tx_n_preempt", "tx_preempt_us"]


def make_rows(scn, n=30, lost_ids=()):
    rows = []
    for e in range(1, n + 1):
        d1, d2, d3, d4 = 16, 40 + e % 5, 30 + 10 * e, 5556
        pre = e % 3                                    # bt_preempt_us
        lost = 1 if e in lost_ids else 0
        t0 = 1000 * e
        r = dict(zip(COLS, [e, f"S{scn}", t0, t0 + d1, t0 + d1 + d2,
                            "" if lost else t0 + d1 + d2 + d3, "" if lost else t0 + d1 + d2 + d3 + d4, lost,
                            d1, d2, "" if lost else d3, "" if lost else d4, "" if lost else d1 + d2 + d3 + d4,
                            5, "T", d2 - pre, 1 if pre else 0, pre, 0, 0]))
        rows.append(r)
    return rows


def write(meas, scn, rows, ver="VER,abc1234,Release,00", sum_=None, bad=0, tel_rx=None):
    meas.mkdir(exist_ok=True)
    (meas / "raw").mkdir(exist_ok=True)
    with open(meas / f"S{scn}.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS); w.writeheader(); w.writerows(rows)
    s = sum_ or f"SUM,S{scn},{len(rows)},100,0,0,2,0,0,0"
    tel = int(s.split(",")[3]) if tel_rx is None else tel_rx
    lines = ["ACK,START,S%d" % scn] + ["TEL,%d,S%d,250" % (i, scn) for i in range(tel)] + \
            ["ACK,STOP", f"ACK,DUMP,{len(rows)}", ver, s, "CAL,0,0,0,623,1513", "MEM,15200,213,88,338",
             "RTS,TelemetryTask,1000,100", "END,DUMP", f"# PC bad_frames={bad}"]
    (meas / "raw" / f"S{scn}-2026-09-27_120000.log").write_text("\n".join(lines) + "\n")


def results(meas, scn):
    return {name.split()[0]: ok for name, ok, _ in A.check_run(A.load_csv(scn, meas), A.read_log(A.latest_log(scn, meas)))}


def test_valid_run_passes_all(tmp_path):
    write(tmp_path, 3, make_rows(3, lost_ids=(7,)))
    assert all(results(tmp_path, 3).values())


@pytest.mark.parametrize("kw, failed", [
    ({"rows": make_rows(1, n=29)}, "V1"),
    ({"sum_": "SUM,S1,30,100,0,0,2,1,0,0"}, "V2"),              # rec_overflow = 1
    ({"sum_": "SUM,S1,30,100,0,0,2,0,0,1"}, "V2"),              # frame_err = 1
    ({"bad": 1}, "V3"),
    ({"tel_rx": 99}, "V3"),                                     # hatta 1 TEL kayboldu
    ({"ver": "VER,abc1234,Debug,00"}, "V6"),
    ({"ver": "VER,abc1234,Release,01"}, "V6"),
    ({"ver": "VER,abc1234+,Release,00"}, "V6"),
    ({"ver": "VER,nogit,Release,00"}, "V6"),
])
def test_each_criterion_fails_alone(tmp_path, kw, failed):
    rows = kw.pop("rows", make_rows(1))
    write(tmp_path, 1, rows, **kw)
    r = results(tmp_path, 1)
    assert [k for k, ok in r.items() if not ok] == [failed]


def test_tel_dropped_is_not_a_criterion(tmp_path):
    write(tmp_path, 5, make_rows(5), sum_="SUM,S5,30,100,40,3,16,0,0,0")   # kart 40 TEL düşürdü
    assert all(results(tmp_path, 5).values())


def test_v4_and_v5_violations(tmp_path):
    rows = make_rows(2)
    rows[3]["d_QueueWait_us"] = A.REC_DELTA_MAX                     # doymuş aralık
    rows[5]["bt_exec_us"] = rows[5]["bt_exec_us"] - 3               # exec + pre, ButtonExec'ten 3 µs kısa
    rows[8]["bt_n_preempt"] = 0; rows[8]["bt_preempt_us"] = 4; rows[8]["bt_exec_us"] -= 4 - (9 % 3)
    write(tmp_path, 2, rows)
    df = A.load_csv(2, tmp_path)
    res = A.check_run(df, A.read_log(A.latest_log(2, tmp_path)))
    r = {n.split()[0]: (ok, det) for n, ok, det in res}
    assert not r["V4"][0] and not r["V5"][0]
    assert "[6, 9]" in r["V5"][1]


def test_summary_plots_report(tmp_path):
    meas, plots, rep = tmp_path / "m", tmp_path / "p", tmp_path / "report.md"
    for s in range(6):
        write(meas, s, make_rows(s, lost_ids=(2,) if s == 5 else ()))
    A.cmd_all(meas, plots, rep)
    sm = pd.read_csv(meas / "summary.csv")
    assert list(sm["scenario"]) == [f"S{s}" for s in range(6)]
    # elle hesap: QueueWait = 30+10e, e=1..30 → medyan 185, en büyük 330, ortalama 185
    s3 = sm[sm["scenario"] == "S3"].iloc[0]
    assert s3["QueueWait_median"] == 185 and s3["QueueWait_max"] == 330 and s3["QueueWait_mean"] == 185
    assert s3["EventToRun_min"] == 16 and s3["n_events"] == 30 and s3["n_lost"] == 0
    s5 = sm[sm["scenario"] == "S5"].iloc[0]
    assert s5["n_lost"] == 1 and s5["QueueWait_max"] == 330      # kayıp olay (e=2) QueueWait'e girmez
    assert s5["QueueWait_min"] == 40
    names = {p.name for p in plots.iterdir()}
    assert {"latency_boxplot.png", "preemption.png"} | {f"breakdown_S{s}.png" for s in range(6)} <= names
    text = rep.read_text(encoding="utf-8")
    assert "S5 (10 ms + 5 ms yük)" in text and "breakdown_S5.png" in text and "abc1234" in text
