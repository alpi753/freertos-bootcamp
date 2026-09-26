"""
Oturum durumu (tasarım §11) — Qt'den bağımsız, birim testlenebilir.

Session.handle(frame) her 64 baytlık çerçeveyi işler ve arayüzün ne
göstereceğini tutar: koşu durumu, son olay, sayaçlar, TEL sıra boşlukları,
döküm (DUMP) birleştirme.

UI-09: Burada hiçbir süre PC'nin alış zamanından hesaplanmaz. Süreler
yalnızca DUMP'taki REC/PRE alanlarından (MCU damgaları) gelir.
"""
from dataclasses import dataclass, field
from .protocol import parse

IDLE, RUNNING, STOPPED = "IDLE", "RUNNING", "STOPPED"
UNKNOWN = "?"          # bağlanınca: kartın durumu henüz bilinmiyor
PERIOD_MS = {0: 0, 1: 100, 2: 20, 3: 10, 4: 10, 5: 10}


@dataclass
class Dump:
    expected: int = 0
    ver: dict | None = None
    recs: list = field(default_factory=list)
    pres: dict = field(default_factory=dict)       # event_id → PRE
    sum: dict | None = None
    cal: dict | None = None
    mem: dict | None = None
    rts: list = field(default_factory=list)
    complete: bool = False


class Session:
    def __init__(self):
        self.state = UNKNOWN
        self.pending = None          # son gönderilen komut (NAK yorumlamak için)
        self.scn = 0                 # seçili/aktif senaryo (kartın ACK'ine göre)
        self.run_scn = None          # son START'ın senaryosu
        self.last_btn = None         # (event_id, scn)
        self.btn_count = 0
        self.last_tel = None         # TEL alanları
        self.tel_n = 0
        self.pc_lost = 0             # TEL sıra boşluklarının toplamı (bu koşu)
        self._last_seq = None
        self.bad_frames = 0          # ayrıştırılamayan 64 B çerçeveler (splitter'ınki ayrıca eklenir)
        self.ver = None
        self.last_sum = None
        self.last_reply = None       # ("ACK"|"NAK", args)
        self.dump: Dump | None = None
        self.last_dump: Dump | None = None

    # --- yardımcı: koşu başlangıcında sayaçları sıfırla
    def _run_started(self, scn):
        self.state, self.run_scn, self.scn = RUNNING, scn, scn
        self.pc_lost, self._last_seq, self.tel_n = 0, None, 0
        self.last_sum = None

    def handle(self, frame: bytes):
        """Çerçeveyi işler; (tip, alanlar) döndürür. Bozuksa ("BAD", {})."""
        kind, f = parse(frame)
        if kind == "BAD":
            self.bad_frames += 1
            return kind, f

        if kind == "TEL":
            if self.state != RUNNING:          # arayüz koşu ortasında bağlandı
                self._run_started(f["scn"])
            if self._last_seq is not None and f["seq"] > self._last_seq + 1:
                self.pc_lost += f["seq"] - self._last_seq - 1
            self._last_seq = f["seq"]
            self.last_tel = f
            self.tel_n += 1
        elif kind == "BTN":
            self.last_btn = (f["event_id"], f["scn"])
            self.btn_count += 1
        elif kind in ("ACK", "NAK"):
            self.last_reply = (kind, f["args"])
            if kind == "ACK":
                self._on_ack(f["args"])
            else:
                self._on_nak(f["args"])
        elif kind == "VER":
            self.ver = f
            if self.dump is not None:
                self.dump.ver = f
        elif kind == "REC" and self.dump is not None:
            self.dump.recs.append(f)
        elif kind == "PRE" and self.dump is not None:
            self.dump.pres[f["event_id"]] = f
        elif kind == "SUM":
            self.last_sum = f
            if self.dump is not None:
                self.dump.sum = f
        elif kind == "CAL" and self.dump is not None:
            self.dump.cal = f
        elif kind == "MEM" and self.dump is not None:
            self.dump.mem = f
        elif kind == "RTS" and self.dump is not None:
            self.dump.rts.append(f)
        elif kind == "END" and self.dump is not None:
            self.dump.complete = True
            self.last_dump, self.dump = self.dump, None
        return kind, f

    def _on_ack(self, args):
        cmd = args[0] if args else ""
        if cmd == "SCN" and len(args) > 1:
            self.scn = int(args[1].lstrip("S"))
        elif cmd == "START":
            scn = int(args[1].lstrip("S")) if len(args) > 1 else self.scn
            self._run_started(scn)
        elif cmd == "STOP":
            self.state = STOPPED
        elif cmd == "DUMP":
            self.dump = Dump(expected=int(args[1]) if len(args) > 1 else 0)

    def _on_nak(self, args):
        why = args[0] if args else ""
        if why == "BUSY":                           # kart koşuda
            self.state = RUNNING
        elif why == "STATE" and self.pending == "STOP" and self.state in (UNKNOWN, RUNNING):
            self.state = STOPPED                    # koşuda değil (IDLE da olabilir; DUMP NAK verir, zararsız)

    def sent(self, line: str):
        """Gönderilen komutu not eder: 'CMD,STOP' → 'STOP'."""
        parts = line.split(",")
        self.pending = parts[1] if len(parts) > 1 else line

    # --- UI-06: hangi komut şu an izinli?
    def allowed(self, cmd: str) -> bool:
        if self.state == UNKNOWN:
            return True                             # kart NAK ile düzeltir
        if self.state == RUNNING:
            return cmd == "STOP"
        if cmd == "STOP":
            return False
        if cmd == "DUMP":
            return self.state == STOPPED
        return True

    def uart_lost_estimate(self):
        """SUM geldiyse: kartın UART'a verdiği TEL (tel_sent) − PC'nin aldığı TEL.

        Not: "sıra boşluğu − tel_dropped" KULLANILMAZ. Koşunun sonunda düşürülen
        TEL'lerden sonra hiç TEL gelmediği için onlar boşluk olarak görünmez
        (D03'te −2 çıkmıştı). Arayüz koşu ortasında bağlandıysa sonuç anlamsızdır.
        """
        if self.last_sum is None:
            return None
        return self.last_sum["tel_sent"] - self.tel_n
