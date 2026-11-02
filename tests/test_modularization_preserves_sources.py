"""Verify relocated implementation files are byte-for-byte identical to main."""
from hashlib import sha1
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE_BLOB_SHAS={
 "src/arbitrage_bot/app/main_bot.py":"e93cc09c65e4017e42999c67c891bbc5803a3165",
 "src/arbitrage_bot/app/approve_tokens.py":"ec438efec7d96a47428bb52ff06458e8118dfab2",
 "src/arbitrage_bot/config/constants.py":"f1a4327c4b29f4df519a391f98c4d34ef79f9258",
 "src/arbitrage_bot/cells/dexes/plunderswap/client.py":"44bb8571c044f9db18c9f834a63dcc0ec4ccd681",
 "src/arbitrage_bot/cells/cex/kucoin/client.py":"3ba0a8428eb748eb41db157fc854b806ba7e018f",
 "src/arbitrage_bot/infrastructure/rpc_manager.py":"8db34a9e4d138241503294f56529adde3f678232",
 "src/arbitrage_bot/infrastructure/logging_utils.py":"7e760f96efe4b97f0619ae1e15765ddee9504749",
}

class SourcePreservationTests(unittest.TestCase):
 def test_all_legacy_sources_are_byte_for_byte_unchanged(self):
  for relative_path,expected_blob_sha in SOURCE_BLOB_SHAS.items():
   with self.subTest(path=relative_path):
    data=(ROOT/relative_path).read_bytes()
    git_blob=b"blob "+str(len(data)).encode("ascii")+b"\0"+data
    self.assertEqual(sha1(git_blob).hexdigest(),expected_blob_sha)

if __name__=="__main__":
 unittest.main()
