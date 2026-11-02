"""Verify untouched relocated support files remain byte-for-byte stable."""
from hashlib import sha1
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
SOURCE_BLOB_SHAS={"src/arbitrage_bot/app/approve_tokens.py":"ec438efec7d96a47428bb52ff06458e8118dfab2","src/arbitrage_bot/infrastructure/rpc_manager.py":"8db34a9e4d138241503294f56529adde3f678232","src/arbitrage_bot/infrastructure/logging_utils.py":"7e760f96efe4b97f0619ae1e15765ddee9504749"}
class SourcePreservationTests(unittest.TestCase):
 def test_untouched_support_sources_remain_byte_for_byte_unchanged(self):
  for path,expected in SOURCE_BLOB_SHAS.items():
   data=(ROOT/path).read_bytes(); blob=b"blob "+str(len(data)).encode("ascii")+b"\0"+data
   self.assertEqual(sha1(blob).hexdigest(),expected)
if __name__=="__main__": unittest.main()
