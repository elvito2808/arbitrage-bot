"""Write boundary placeholder: signing and transaction submission are disabled."""
class TransactionExecutor:
    def __init__(self, enabled: bool = False):
        if enabled:
            raise ValueError("Transaction execution is not implemented/enabled in the refactor preview")
        self.enabled = False

    async def submit(self, *args, **kwargs):
        raise RuntimeError("Transaction submission is disabled in the refactor preview")
