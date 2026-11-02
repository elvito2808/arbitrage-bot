"""Compatibility entry point for relocated PlunderSwap client."""
from pathlib import Path
import sys
_ROOT=Path(__file__).resolve().parent
_SRC=_ROOT/"src"
if str(_SRC) not in sys.path: sys.path.insert(0,str(_SRC))
from arbitrage_bot.compat import load_legacy_module
sys.modules[__name__]=load_legacy_module("dex_plunderswap","cells/dexes/plunderswap/client.py")
