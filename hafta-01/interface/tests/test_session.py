"""TC-U07: çerçeve ayırıcı + oturum (UI-02, UI-05, UI-06)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from uart_monitor.protocol import FrameSplitter, parse              # noqa: E402
from uart_monitor.session import Session, RUNNING, STOPPED, UNKNOWN  # noqa: E402


def fr(text: str) -> bytes:
    b = text.encode()
    return b + b" " * (63 - len(b)) + b"\n"


# ---- UI-02: hizalama ------------------------------------------------------

def test_split_normal_and_chunked():
    sp = FrameSplitter()
    sp.synced = True
    stream = fr("TEL,1,S3,250") + fr("TEL,2,S3,251")
    out = []
    for i in range(0, len(stream), 7):          # parça parça gelen akış
        out += sp.feed(stream[i:i + 7])
    assert out == [fr("TEL,1,S3,250"), fr("TEL,2,S3,251")] and sp.bad == 0


def test_split_first_partial_frame_is_sync_not_bad():
    sp = FrameSplitter()
    out = sp.feed(fr("TEL,1,S3,250")[20:] + fr("TEL,2,S3,251"))
    assert out == [fr("TEL,2,S3,251")] and sp.bad == 0


def test_split_63_and_65_byte_frames_counted_and_realigned():
    sp = FrameSplitter()
    sp.synced = True
    short = fr("TEL,1,S3,250")[1:]               # 63 B
    long_ = b"X" + fr("TEL,2,S3,250")            # 65 B
    out = sp.feed(short + long_ + fr("TEL,3,S3,252"))
    assert out == [fr("TEL,3,S3,252")] and sp.bad == 2


def test_split_cut_in_the_middle():
    sp = FrameSplitter()
    sp.synced = True
    a = fr("TEL,1,S3,250")
    out = sp.feed(a[:30] + fr("TEL,2,S3,251"))   # yarıda kesilmiş + tam
    assert out == [] and sp.bad == 1             # birleşik 30+64 B tek bozuk çerçeve
    assert sp.feed(fr("TEL,3,S3,252")) == [fr("TEL,3,S3,252")]


def test_split_garbage_without_lf():
    sp = FrameSplitter()
    sp.synced = True
    sp.feed(b"\x00" * 200)
    assert sp.bad == 1 and sp.buf == b""


def test_parse_all_types():
    cases = {
        "TEL,5,S3,263": "TEL", "BTN,0,S0,PRESSED": "BTN", "VER,abc1234,Release,00": "VER",
        "ACK,START,S3": "ACK", "NAK,BUSY": "NAK", "END,DUMP": "END",
        "REC,1,S2,100,16,44,32,5600,0": "REC", "PRE,1,5,T,40,1,4,0,0": "PRE",
        "SUM,S2,1,50,0,0,2,0,0,0": "SUM", "CAL,0,0,0,623,1513": "CAL",
        "MEM,15200,213,88,338": "MEM", "RTS,TelemetryTask,1000,572": "RTS",
    }
    for text, kind in cases.items():
        assert parse(fr(text))[0] == kind, text
    assert parse(fr("XYZ,1,2"))[0] == "BAD"
    assert parse(fr("TEL,1,S3"))[0] == "BAD"          # eksik alan
    assert parse(fr("TEL,a,S3,1"))[0] == "BAD"        # sayı değil


# ---- UI-05: TEL sıra boşluğu ------------------------------------------------

def test_seq_gap_counts_pc_lost_and_resets_on_start():
    s = Session()
    s.handle(fr("ACK,START,S3"))
    for seq in (0, 1, 2, 5, 6, 10):                  # 3,4 ve 7,8,9 eksik
        s.handle(fr(f"TEL,{seq},S3,250"))
    assert s.pc_lost == 5 and s.state == RUNNING
    s.handle(fr("ACK,STOP"))
    s.handle(fr("SUM,S3,0,11,5,0,16,0,0,0"))
    assert s.uart_lost_estimate() == 0               # boşlukların hepsi kartta düşürülmüş
    s.handle(fr("ACK,START,S3"))
    s.handle(fr("TEL,0,S3,250"))
    assert s.pc_lost == 0


def test_bad_frame_counted():
    s = Session()
    s.handle(fr("QQQ,1"))
    assert s.bad_frames == 1


# ---- UI-03 / UI-06: durum ve düğme kilitleri --------------------------------

def test_button_states_and_locks():
    s = Session()
    assert s.state == UNKNOWN and s.allowed("START")
    s.handle(fr("BTN,0,S0,PRESSED"))
    assert s.last_btn == (0, 0)
    s.handle(fr("ACK,SCN,S2")); s.handle(fr("ACK,START,S2"))
    assert s.state == RUNNING
    assert [c for c in ("SCN", "START", "STOP", "DUMP") if s.allowed(c)] == ["STOP"]
    s.handle(fr("BTN,1,S2,PRESSED"))
    assert s.last_btn == (1, 2)
    s.handle(fr("ACK,STOP"))
    assert s.state == STOPPED and s.allowed("DUMP") and not s.allowed("STOP")


def test_nak_infers_state_after_connect():
    s = Session()
    s.sent("CMD,START"); s.handle(fr("NAK,BUSY"))
    assert s.state == RUNNING
    s2 = Session()
    s2.sent("CMD,STOP"); s2.handle(fr("NAK,STATE"))
    assert s2.state == STOPPED


def test_tel_while_unknown_means_running():
    s = Session()
    s.handle(fr("TEL,40,S1,250"))
    assert s.state == RUNNING and s.run_scn == 1


# ---- Döküm birleştirme -------------------------------------------------------

def test_dump_assembly():
    s = Session()
    for t in ["ACK,DUMP,2", "VER,abc,Release,00",
              "REC,1,S2,100,16,44,32,5600,0", "PRE,1,5,T,40,1,4,0,0",
              "REC,2,S2,900,16,44,0,0,1", "PRE,2,5,T,44,0,0,0,0",
              "SUM,S2,2,50,0,1,2,0,0,0", "CAL,0,0,0,623,1513", "MEM,15200,213,88,338",
              "RTS,TelemetryTask,1000,572", "RTS,IDLE,9000,400", "END,DUMP"]:
        s.handle(fr(t))
    d = s.last_dump
    assert s.dump is None and d.complete and d.expected == 2
    assert [r["event_id"] for r in d.recs] == [1, 2] and set(d.pres) == {1, 2}
    assert d.sum["btn_dropped"] == 1 and d.mem["hw_btn"] == 88 and len(d.rts) == 2
