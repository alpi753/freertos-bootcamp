"""
Seri okuma iş parçacığı (tasarım §11, UI-09).

Okuma ayrı bir QThread'de yapılır: grafik çizimi yavaşlasa bile baytlar
işletim sisteminin tamponundan zamanında alınır ve kaybolmaz. Çerçeveler
toplu halde (liste) ana iş parçacığına sinyal ile gönderilir.
"""
import threading

import serial
from serial.tools import list_ports
from PySide6.QtCore import QThread, Signal

from .protocol import FrameSplitter

BAUD = 115200


def available_ports():
    """[(cihaz, açıklama)] — NUCLEO 'STLink Virtual COM Port' olarak görünür."""
    return [(p.device, p.description) for p in list_ports.comports()]


class SerialWorker(QThread):
    frames = Signal(list)          # list[bytes] — her biri 64 B
    lost = Signal(str)             # bağlantı koptu (ör. USB çekildi)

    def __init__(self, port: str, parent=None):
        super().__init__(parent)
        self.port = port
        self.splitter = FrameSplitter()
        self._ser = None
        self._stop = False
        self._wlock = threading.Lock()

    def open(self):
        """Ana iş parçacığında çağrılır; hata olursa SerialException fırlatır."""
        self._ser = serial.serial_for_url(self.port, BAUD, timeout=0.05)   # "loop://" ile test edilebilir
        self._ser.reset_input_buffer()

    def run(self):
        while not self._stop:
            try:
                data = self._ser.read(4096)
            except (serial.SerialException, OSError) as e:
                if not self._stop:
                    self.lost.emit(str(e))
                break
            if data:
                out = self.splitter.feed(data)
                if out:
                    self.frames.emit(out)
        try:
            self._ser.close()
        except Exception:
            pass

    def send(self, line: str) -> bool:
        with self._wlock:
            try:
                self._ser.write((line + "\n").encode("ascii"))
                return True
            except (serial.SerialException, OSError) as e:
                self.lost.emit(str(e))
                return False

    def stop(self):
        self._stop = True
        self.wait(1000)

    @property
    def bad(self):
        return self.splitter.bad
