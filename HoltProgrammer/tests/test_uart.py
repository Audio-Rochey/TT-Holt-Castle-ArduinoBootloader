import itertools
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import ProgrammingError, uart_check


class FakeSerial:
    def __init__(self, ack):
        self.ack = iter(ack)
        self.writes = []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def reset_input_buffer(self): pass
    def flush(self): pass
    def write(self, data): self.writes.append(data)
    def read(self, size): return bytes([next(self.ack)])


class UartTests(unittest.TestCase):
    def test_success_only_sends_entry_phrase(self):
        port = FakeSerial(b"noise\xaa\x55\x00\x00\x55\xaa")
        serial = types.SimpleNamespace(Serial=lambda **kwargs: port)
        lines = []
        with patch.dict(sys.modules, {"serial": serial}):
            uart_check("TEST", lines.append)
        self.assertEqual(port.writes, [b"TT_ENTER_IAP"])
        self.assertFalse(port.dtr)
        self.assertFalse(port.rts)
        self.assertIn("PASS", lines[-1])
        self.assertIn("Power-cycle", lines[-1])

    def test_silent_target_is_failure(self):
        port = FakeSerial(b"")
        serial = types.SimpleNamespace(Serial=lambda **kwargs: port)
        clock = itertools.count(0, 10)
        with patch.dict(sys.modules, {"serial": serial}), patch("backend.time.monotonic", side_effect=lambda: next(clock)):
            with self.assertRaises(ProgrammingError):
                uart_check("TEST", lambda text: None)


if __name__ == "__main__":
    unittest.main()
