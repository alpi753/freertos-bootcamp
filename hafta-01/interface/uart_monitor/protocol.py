"""
Çerçeve ayrıştırıcıları (tasarım §9). Her çerçeve 64 bayt: ASCII içerik + boşluk + '\\n'.

parse(frame) → (tip, alanlar sözlüğü) ya da geçersizse ("BAD", {}).
"""
FRAME_LEN = 64
U32 = 1 << 32

# tip → alan adları (virgülle ayrılmış, tipten sonrası)
FIELDS = {
    "TEL": ["seq", "scn", "temp_x10"],
    "BTN": ["event_id", "scn", "state"],
    "VER": ["git_hash", "build", "test_flags"],
    "REC": ["event_id", "scn", "t0", "d1", "d2", "d3", "d4", "lost"],
    "PRE": ["event_id", "ready_wait_us", "ready_wait_task", "bt_exec_us", "bt_n_preempt",
            "bt_preempt_us", "tx_n_preempt", "tx_preempt_us"],
    "SUM": ["scn", "events", "tel_sent", "tel_dropped", "btn_dropped", "q_hw",
            "rec_overflow", "bounce_rej", "frame_err"],
    "CAL": ["load_target_us", "load_mean_us", "load_max_us", "adc_mean_us", "hook_ns"],
    "MEM": ["min_free_heap", "hw_tel", "hw_btn", "hw_tx"],
    "RTS": ["task", "run_us", "pct_x10"],
}
TEXT_FIELDS = {"scn", "state", "git_hash", "build", "test_flags", "ready_wait_task", "task"}

LOST_OK, LOST_QUEUE, LOST_INCOMPLETE = 0, 1, 2


def parse(frame: bytes):
    if len(frame) != FRAME_LEN or not frame.endswith(b"\n"):
        return "BAD", {}
    try:
        text = frame[:-1].decode("ascii").rstrip(" ")
    except UnicodeDecodeError:
        return "BAD", {}
    parts = text.split(",")
    kind = parts[0]
    if kind in ("ACK", "NAK", "END"):
        return kind, {"args": parts[1:]}
    names = FIELDS.get(kind)
    if names is None or len(parts) - 1 != len(names):
        return "BAD", {}
    out = {}
    for name, val in zip(names, parts[1:]):
        if name in TEXT_FIELDS:
            out[name] = val.lstrip("S") if name == "scn" else val
        else:
            try:
                out[name] = int(val)
            except ValueError:
                return "BAD", {}
    if "scn" in out:
        out["scn"] = int(out["scn"])
    return kind, out


def rec_absolute(rec: dict):
    """REC farklarından mutlak t₀…t₄ (32-bit taşmaya dayanıklı).
    Zincir eksikse (lost ≠ 0) yalnızca güvenilir damgalar döner, diğerleri None."""
    t = [rec["t0"], None, None, None, None]
    for k, key in enumerate(["d1", "d2", "d3", "d4"], start=1):
        if rec["lost"] != LOST_OK and k >= 3:          # t₃/t₄ yok
            break
        t[k] = (t[k - 1] + rec[key]) % U32
    return t


class FrameSplitter:
    """Bayt akışını LF'de böler (UI-02).

    - Bağlantı akışın ortasında açıldıysa ilk LF'ye kadar gelen yarım çerçeve
      bozuk sayılmadan atılır (senkronlanma).
    - Uzunluğu 64 olmayan çerçeve `bad` sayacına eklenir ve atılır; bir
      sonraki LF'den itibaren akış kendiliğinden yeniden hizalanır.
    - LF gelmeden 2×64 bayt birikirse (çöp veri) tampon atılır ve bozuk sayılır.
    """

    MAX_PENDING = 2 * FRAME_LEN

    def __init__(self):
        self.buf = b""
        self.synced = False
        self.bad = 0

    def reset(self):
        self.buf, self.synced = b"", False

    def feed(self, data: bytes) -> list[bytes]:
        self.buf += data
        out = []
        while b"\n" in self.buf:
            raw, self.buf = self.buf.split(b"\n", 1)
            raw += b"\n"
            if not self.synced:
                self.synced = True
                if len(raw) != FRAME_LEN:
                    continue
            if len(raw) != FRAME_LEN:
                self.bad += 1
                continue
            out.append(raw)
        if len(self.buf) > self.MAX_PENDING:
            self.buf = b""
            self.bad += 1
        return out
