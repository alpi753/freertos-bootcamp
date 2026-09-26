"""
measurements/S<n>.csv yazıcı (gereksinim §8, UI-07).

Her satır bir olay. Aralık sütunları (tasarım §5.5.1):
  d_EventToRun = t1-t0, d_ButtonExec = t2-t1, d_QueueWait = t3-t2,
  d_UartTx = t4-t3, d_Total = t4-t0
Zincir eksikse (lost ≠ 0) t3/t4 ve bunlara bağlı aralıklar BOŞ bırakılır.
PRE henüz gelmediyse (adım 7 öncesi) görev değişimi sütunları boştur.
"""
import csv
from .protocol import rec_absolute, LOST_OK

COLUMNS = [
    "event_id", "scenario", "t0_us", "t1_us", "t2_us", "t3_us", "t4_us", "lost",
    "d_EventToRun_us", "d_ButtonExec_us", "d_QueueWait_us", "d_UartTx_us", "d_Total_us",
    "ready_wait_us", "ready_wait_task", "bt_exec_us", "bt_n_preempt", "bt_preempt_us",
    "tx_n_preempt", "tx_preempt_us",
]
PRE_KEYS = COLUMNS[13:]


def row_for(rec: dict, pre: dict | None):
    t = rec_absolute(rec)
    ok = rec["lost"] == LOST_OK
    row = {
        "event_id": rec["event_id"], "scenario": f"S{rec['scn']}",
        "t0_us": t[0], "t1_us": t[1], "t2_us": t[2],
        "t3_us": t[3] if ok else "", "t4_us": t[4] if ok else "",
        "lost": rec["lost"],
        "d_EventToRun_us": rec["d1"], "d_ButtonExec_us": rec["d2"],
        "d_QueueWait_us": rec["d3"] if ok else "", "d_UartTx_us": rec["d4"] if ok else "",
        "d_Total_us": (rec["d1"] + rec["d2"] + rec["d3"] + rec["d4"]) if ok else "",
    }
    for k in PRE_KEYS:
        row[k] = "" if pre is None else pre[k]
    return row


def write_csv(path, recs: list[dict], pres: dict[int, dict] | None = None):
    """recs: REC alan sözlükleri; pres: event_id → PRE alanları."""
    pres = pres or {}
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for r in recs:
            w.writerow(row_for(r, pres.get(r["event_id"])))
