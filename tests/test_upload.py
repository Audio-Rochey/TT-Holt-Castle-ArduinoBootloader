import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from SerialUploader.upload import frame, read_ack
class FakePort:
    def __init__(self, data): self.data=bytearray(data)
    def read(self, n):
        result=bytes(self.data[:n]); del self.data[:n]; return result
class ProtocolTests(unittest.TestCase):
    def test_program(self):
        self.assertEqual(frame(0x80,b"abc"), b"\xaa\x55\x80\x03abc\xa9\x01\x55\xaa")
    def test_erase(self):
        self.assertEqual(frame(0x81), b"\xaa\x55\x81\x00\x00\x00\x00\x00\x81\x00\x55\xaa")
    def test_verify(self):
        self.assertEqual(frame(0x82,b"A"),b"\xaa\x55\x82\x01\x00\x00\x00\x00A\xc4\x00\x55\xaa")
    def test_length_limit(self):
        with self.assertRaises(ValueError): frame(0x80,b"x"*65)
    def test_ack_with_noise(self): read_ack(FakePort(b"noise\xaa\x55\x00\x00\x55\xaa"),0.01)
    def test_error_ack(self):
        with self.assertRaises(RuntimeError): read_ack(FakePort(b"\xaa\x55\x00\x01\x55\xaa"),0.01)
    def test_partial_ack_timeout(self):
        with self.assertRaises(TimeoutError): read_ack(FakePort(b"\xaa\x55"),0.001)
if __name__=='__main__': unittest.main()
