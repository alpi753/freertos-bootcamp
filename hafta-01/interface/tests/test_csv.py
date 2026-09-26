"""TC-U07 (kısmi) ve TC-U08 (PC tarafı): çerçeve ayrıştırma ve REC → CSV."""
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from uart_monitor.protocol import parse, rec_absolute          # noqa: E402
from uart_monitor.csv_writer import write_csv, COLUMNS          # noqa: E402


def fr(text: str) -> bytes:
    b = text.encode()
    return b + b" " * (63 - len(b)) + b"\n"


def test_parse_types():
    assert parse(fr("TEL,1042,S3,263")) == ("TEL", {"seq": 1042, "scn": 3, "temp_x10": 263})
    assert parse(fr("BTN,17,S3,PRESSED"))[1]["event_id"] == 17
    k, f = parse(fr("REC,1,S2,4294967290,120,35,5600,5660,0"))
    assert k == "REC" and f["t0"] == 4294967290 and f["d3"] == 5600
    assert parse(fr("ACK,START,S3")) == ("ACK", {"args": ["START", "S3"]})


def test_parse_bad():
    assert parse(b"TEL,1,S3,263\n")[0] == "BAD"                 # 64 bayt değil
    assert parse(fr("TEL,1,S3"))[0] == "BAD"                    # eksik alan
    assert parse(fr("TEL,x,S3,263"))[0] == "BAD"                # sayı değil
    assert parse(fr("XYZ,1"))[0] == "BAD"                       # bilinmeyen tip


def test_rec_absolute_wraps():
    rec = {"t0": 4294967290, "d1": 10, "d2": 5, "d3": 7, "d4": 3, "lost": 0}
    assert rec_absolute(rec) == [4294967290, 4, 9, 16, 19]      # TIM2 taşması


def test_csv_columns_and_lost(tmp_path: pathlib.Path):
    ok = parse(fr("REC,1,S2,1000,120,35,5600,5660,0"))[1]
    lost = parse(fr("REC,2,S2,90000,200,40,0,0,1"))[1]
    out = tmp_path / "S2.csv"
    write_csv(out, [ok, lost])
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    assert list(rows[0].keys()) == COLUMNS                        # gereksinim §8 şeması
    assert rows[0]["t4_us"] == str(1000 + 120 + 35 + 5600 + 5660)
    assert rows[0]["d_Total_us"] == str(120 + 35 + 5600 + 5660)
    assert rows[0]["bt_exec_us"] == ""                            # PRE yok → boş
    assert rows[1]["lost"] == "1"
    assert rows[1]["t3_us"] == "" and rows[1]["t4_us"] == "" and rows[1]["d_Total_us"] == ""
    assert rows[1]["t2_us"] == str(90000 + 200 + 40)              # t₂'ye kadar zincir var
