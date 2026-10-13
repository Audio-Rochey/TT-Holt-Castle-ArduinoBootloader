import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from PySide6.QtWidgets import QApplication
    from app import Window
except ImportError:
    QApplication = None


@unittest.skipUnless(QApplication, "Qt build environment required")
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_worker_failure_restores_controls(self):
        window = Window()
        window.show()
        self.app.processEvents()
        with patch("app.Programmer", side_effect=RuntimeError("TEST failure")):
            window.start("check")
            self.assertFalse(window.program.isEnabled())
            window.close()
            self.assertTrue(window.isVisible())
            deadline = time.monotonic() + 3
            while window.thread is not None and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.01)
        self.assertIsNone(window.thread)
        self.assertTrue(window.program.isEnabled())
        self.assertIn("TEST failure", window.status.text())
        self.assertIn("FAILED", window.log.toPlainText())
        window.close()

    def test_main_controls_do_not_overlap_at_minimum_size(self):
        window = Window()
        window.resize(window.minimumSize())
        window.show()
        self.app.processEvents()
        self.assertLess(window.program.geometry().bottom(), window.file_label.geometry().top())
        self.assertLess(window.file_label.geometry().bottom(), window.alternative.geometry().top())
        self.assertLess(window.log.geometry().bottom(), window.backup_button.geometry().top())
        window.close()


if __name__ == "__main__":
    unittest.main()
