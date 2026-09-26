#!/usr/bin/env python3
"""
UART Monitor — hafta-01 PC arayüzü (tasarım §11).

Çalıştırma (Windows, depo kökünden):
    py -m pip install -r hafta-01/interface/requirements.txt
    py hafta-01/interface/uart_monitor.py
"""
import sys

import pyqtgraph as pg
from PySide6.QtWidgets import QApplication

from uart_monitor.main_window import MainWindow     # aynı klasördeki paket (dosyadan önce bulunur)


def main():
    app = QApplication(sys.argv)
    pg.setConfigOptions(antialias=True, background="w", foreground="#333")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
