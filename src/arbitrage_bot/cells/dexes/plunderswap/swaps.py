"""Explicitly disabled PlunderSwap write adapter for the preview build."""
class PlunderSwapExecution:
    async def swap(self, *args, **kwargs):
        raise RuntimeError(
            "PlunderSwap swap submission is disabled in the refactor preview; "
            "no transaction will be signed or broadcast"
        )
