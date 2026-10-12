"""Holt Programmer desktop UI. Launch with python app.py, or use packaged app."""
import argparse
import json
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFrame,
                              QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPlainTextEdit,
                              QProgressBar, QPushButton, QScrollArea, QLayout, QVBoxLayout, QWidget)
from backend import Programmer, default_firmware, find_tool, resource_root, run_tool, uart_check


class Worker(QObject):
    line = Signal(str)
    progress = Signal(int, str)
    done = Signal(bool, str, str)

    def __init__(self, action, firmware, port, backups):
        super().__init__()
        self.action, self.firmware, self.port, self.backups = action, firmware, port, backups

    def run(self):
        programmer = None
        try:
            if self.action == "uart":
                uart_check(self.port, self.line.emit)
                message = "UART check passed. Power-cycle Holt again."
            else:
                programmer = Programmer(log=self.line.emit, progress=self.progress.emit,
                                        backup_root=self.backups)
                if self.action == "check":
                    configured = bool(programmer.check()[2] & 0x20)
                    message = "Holt connected. " + ("BOOT-at-power-on enabled." if configured else "Fresh-board setup needed.")
                else:
                    programmer.program(self.firmware)
                    message = "Bootloader verified. Power-cycle Holt."
            self.done.emit(True, message, str(programmer.session or "") if programmer else "")
        except Exception as error:
            self.line.emit("FAILED: " + str(error))
            self.done.emit(False, str(error), str(programmer.session or "") if programmer else "")


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Holt Programmer")
        self.resize(740, 840)
        self.setMinimumSize(700, 620)
        self.thread = None
        self.firmware = default_firmware()
        self.backups = Path.home() / "Documents" / "Holt Programmer Backups"
        self.last_backup = ""
        self.controls = []
        body = QWidget()
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setFrameShape(QFrame.NoFrame)
        scroller.setWidget(body)
        self.setCentralWidget(scroller)
        layout = QVBoxLayout(body)
        layout.setSizeConstraint(QLayout.SetMinimumSize)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)
        title = QLabel("HOLT PROGRAMMER")
        title.setStyleSheet("font-size:26px; font-weight:700; color:#102c46;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Install the TT bootloader with WCH-LinkE over SWIO."))
        wiring = QLabel("Power Holt from USB. Connect SWIO → PD1 and GND → GND.\n"
                        "Leave the programmer’s power outputs disconnected. Close other programming tools.")
        wiring.setWordWrap(True)
        wiring.setStyleSheet("background:#eaf1f6; padding:12px; border-radius:8px; color:#153750;")
        layout.addWidget(wiring)
        self.program = QPushButton("↓\nPROGRAM HOLT\nWITH BOOTLOADER")
        self.program.setMinimumHeight(155)
        self.program.setStyleSheet("QPushButton {background:#146c56;color:white;font-size:23px;"
                                  "font-weight:700;border:0;border-radius:16px;}"
                                  "QPushButton:hover {background:#105944;} QPushButton:disabled {background:#849b93;}")
        self.program.clicked.connect(lambda: self.start("program"))
        self.controls.append(self.program)
        layout.addWidget(self.program)
        self.file_label = QLabel()
        self.file_label.setWordWrap(True)
        self.file_label.setMinimumHeight(40)
        layout.addWidget(self.file_label)
        row = QHBoxLayout()
        self.alternative = QCheckBox("Use alternative firmware")
        self.alternative.toggled.connect(self.choose_firmware)
        row.addWidget(self.alternative)
        row.addStretch()
        check = QPushButton("Check connection")
        check.clicked.connect(lambda: self.start("check"))
        row.addWidget(check)
        self.controls.extend([self.alternative, check])
        layout.addLayout(row)
        note = QLabel("Fresh boards: configure BOOT-at-power-on automatically. This provisioning path awaits hardware validation.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#875612; font-size:12px;")
        layout.addWidget(note)
        self.status = QLabel("Ready. Connect one programmer and one Holt.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("font-weight:600;")
        layout.addWidget(self.status)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addWidget(self.bar)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Menlo" if sys.platform == "darwin" else "Consolas", 10))
        self.log.setMinimumHeight(150)
        self.log.setStyleSheet("background:#112332; color:#d9e6ed; border-radius:8px; padding:8px;")
        layout.addWidget(self.log, 1)
        footer = QHBoxLayout()
        save = QPushButton("Save log…")
        save.clicked.connect(self.save_log)
        footer.addWidget(save)
        self.open_backups = QPushButton("Open backups")
        self.open_backups.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.backups))))
        self.open_backups.setEnabled(False)
        footer.addWidget(self.open_backups)
        footer.addStretch()
        self.backup_button = QPushButton("Backup folder…")
        self.backup_button.clicked.connect(self.choose_backups)
        self.controls.append(self.backup_button)
        footer.addWidget(self.backup_button)
        layout.addLayout(footer)
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        layout.addWidget(separator)
        uart_row = QHBoxLayout()
        uart_row.addWidget(QLabel("Optional UART self-test:"))
        self.ports = QComboBox()
        self.ports.setMinimumWidth(200)
        uart_row.addWidget(self.ports, 1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_ports)
        uart_row.addWidget(refresh)
        self.uart = QPushButton("Test bootloader")
        self.uart.clicked.connect(lambda: self.start("uart"))
        uart_row.addWidget(self.uart)
        self.controls.extend([self.ports, refresh, self.uart])
        layout.addLayout(uart_row)
        uart_note = QLabel("3.3 V UART: adapter TX → PD6, RX → PD5, GND → GND. Test prompts for a power-cycle; it leaves Holt in upload mode.")
        uart_note.setWordWrap(True)
        uart_note.setStyleSheet("font-size:12px; color:#536775;")
        layout.addWidget(uart_note)
        self.update_firmware_label()
        self.refresh_ports()

    def update_firmware_label(self):
        mode = "Alternative BOOT firmware" if self.alternative.isChecked() else "Bundled TT bootloader · v0.4 · 3-second entry"
        self.file_label.setText(f"{mode}\n{self.firmware.name}")
        self.file_label.setToolTip(str(self.firmware))

    def choose_firmware(self, enabled):
        if enabled:
            filename, _ = QFileDialog.getOpenFileName(self, "Choose BOOT firmware (not an application)", "", "BOOT binary (*.bin)")
            if not filename:
                self.alternative.setChecked(False)
                return
            self.firmware = Path(filename)
        else:
            self.firmware = default_firmware()
        self.update_firmware_label()

    def choose_backups(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose backup folder", str(self.backups.parent))
        if folder:
            self.backups = Path(folder)

    def refresh_ports(self):
        from serial.tools import list_ports
        selected = self.ports.currentData()
        self.ports.clear()
        for port in list_ports.comports():
            self.ports.addItem(f"{port.device} — {port.description}", port.device)
        index = self.ports.findData(selected)
        if index >= 0:
            self.ports.setCurrentIndex(index)

    def start(self, action):
        if self.thread is not None:
            return
        if action == "uart" and not self.ports.currentData():
            self.status.setText("Connect a USB-UART adapter and refresh the port list.")
            return
        if action == "uart" and self.alternative.isChecked():
            self.status.setText("The UART self-test uses the TT entry phrase at 460800 baud; select the bundled firmware to use this test.")
            return
        self.log.clear()
        self.status.setText("Power-cycle Holt now to test UART." if action == "uart" else "Working…")
        self.status.setStyleSheet("font-weight:600;color:#153750;")
        self.bar.setRange(0, 100 if action == "program" else 0)
        self.bar.setValue(0)
        for control in self.controls:
            control.setEnabled(False)
        self.thread = QThread(self)
        self.worker = Worker(action, self.firmware, self.ports.currentData(), self.backups)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.line.connect(self.log.appendPlainText)
        self.worker.progress.connect(self.progress)
        self.worker.done.connect(self.complete)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread_finished)
        self.thread.start()

    def progress(self, value, message):
        self.bar.setValue(value)
        self.status.setText(message)

    def complete(self, success, message, backup):
        self.status.setText(message)
        self.status.setStyleSheet("font-weight:600;color:" + ("#146c56;" if success else "#a12626;"))
        self.bar.setRange(0, 100)
        self.bar.setValue(100 if success else 0)
        if backup:
            self.last_backup = backup
            self.open_backups.setEnabled(True)
            try:
                Path(backup, "session.log").write_text(self.log.toPlainText(), encoding="utf-8")
            except OSError as error:
                self.log.appendPlainText(f"Could not save session log: {error}")

    def thread_finished(self):
        self.thread.deleteLater()
        self.thread = None
        for control in self.controls:
            control.setEnabled(True)

    def save_log(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save programmer log", "holt-programmer.log", "Log (*.log)")
        if filename:
            try:
                Path(filename).write_text(self.log.toPlainText(), encoding="utf-8")
            except OSError as error:
                QMessageBox.warning(self, "Log could not be saved", str(error))

    def closeEvent(self, event):
        if self.thread is not None:
            self.status.setText("Wait for the current operation to finish before closing.")
            event.ignore()
        else:
            event.accept()


def main():
    parser = argparse.ArgumentParser(description="Holt Programmer")
    parser.add_argument("--smoke-test", action="store_true", help="Check bundled tools and firmware without connecting hardware")
    parser.add_argument("--preview", metavar="PNG", help="Render the initial window to an image without programming")
    args = parser.parse_args()
    if args.smoke_test:
        firmware = default_firmware().read_bytes()
        assert 4 <= len(firmware) <= 3328
        run_tool(find_tool("wlink"), ["--help"], lambda text: None)
        run_tool(find_tool("holt-options"), ["--help"], lambda text: None)
        manifest_path = resource_root() / "resources" / "manifest.json"
        if manifest_path.exists():
            import hashlib
            manifest = json.loads(manifest_path.read_text())
            for relative, expected in manifest["sha256"].items():
                assert hashlib.sha256((resource_root() / relative).read_bytes()).hexdigest() == expected, relative
        print("PASS: bundled tools and BOOT firmware load without hardware.")
        return
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setStyleSheet("QWidget {font-family: Arial; font-size:13px;} QMainWindow {background:#f8fafb;} "
                      "QPushButton {padding:7px 12px;} QProgressBar {height:12px;}")
    window = Window()
    window.show()
    if args.preview:
        app.processEvents()
        window.grab().save(args.preview)
        return
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
