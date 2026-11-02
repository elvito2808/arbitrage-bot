"""Compatibility entry point for the original arbitrage bot."""
from pathlib import Path
import sys
_ROOT=Path(__file__).resolve().parent
_SRC=_ROOT/"src"
if str(_SRC) not in sys.path: sys.path.insert(0,str(_SRC))
from arbitrage_bot.compat import load_legacy_module
_module=load_legacy_module("main_bot","app/main_bot.py")
if __name__=="__main__":
    import asyncio
    asyncio.run(_module.run_bot())
else:
    sys.modules[__name__]=_module
