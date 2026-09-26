#!/usr/bin/env python3
"""
compare_dump.py — TC-D05: arayüzün yazdığı CSV, ham dökümle birebir aynı mı?

    py interface/tools/compare_dump.py measurements/S2.csv docs/test-results/raw/UI-DUMP-S2-<tarih>.log

Ham logdaki REC/PRE satırları bağımsız olarak yeniden CSV'ye çevrilir ve iki
dosya satır satır karşılaştırılır.
"""
import csv
import io
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from uart_monitor.protocol import parse, FRAME_LEN            # noqa: E402
from uart_monitor.csv_writer import COLUMNS, row_for           # noqa: E402


def main(csv_path, raw_path):
    recs, pres = [], {}
    for line in open(raw_path, encoding="ascii", errors="replace"):
        text = line.rstrip("\r\n").split("\t")[-1]            # hil_check logunda "ms\tçerçeve"
        fr = text.encode().ljust(FRAME_LEN - 1)[:FRAME_LEN - 1] + b"\n"
        kind, f = parse(fr)
        if kind == "REC":
            recs.append(f)
        elif kind == "PRE":
            pres[f["event_id"]] = f
    want = io.StringIO()
    w = csv.DictWriter(want, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in recs:
        w.writerow(row_for(r, pres.get(r["event_id"])))
    exp = want.getvalue().splitlines()
    got = open(csv_path, encoding="utf-8").read().splitlines()
    diff = [(i, a, b) for i, (a, b) in enumerate(zip(exp, got)) if a != b]
    ok = not diff and len(exp) == len(got)
    print(f"[{'GECTI' if ok else 'KALDI'}] D05: CSV {len(got) - 1} satır, ham dökümde {len(recs)} REC / {len(pres)} PRE")
    for i, a, b in diff[:5]:
        print(f"  satır {i}: beklenen {a}\n          CSV      {b}")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
