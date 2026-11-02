"""Read-only Web3 connection; this class has no private-key or signing API."""
import logging
from web3 import Web3


class ReadOnlyRPC:
    def __init__(self, endpoints: list[str], timeout_seconds: int = 15):
        if not endpoints:
            raise ValueError("at least one RPC endpoint is required")
        self.endpoints = tuple(endpoints)
        self.timeout_seconds = timeout_seconds
        self.web3: Web3 | None = None
        self.endpoint: str | None = None
        self.log = logging.getLogger(__name__)

    def connect(self) -> Web3:
        failures = []
        for endpoint in self.endpoints:
            try:
                candidate = Web3(Web3.HTTPProvider(endpoint, request_kwargs={"timeout": self.timeout_seconds}))
                if candidate.is_connected():
                    self.web3 = candidate
                    self.endpoint = endpoint
                    self.log.info("rpc_connected endpoint=%s chain_id=%s block=%s",
                                  endpoint, candidate.eth.chain_id, candidate.eth.block_number)
                    return candidate
                failures.append(f"{endpoint}: not connected")
            except Exception as exc:
                failures.append(f"{endpoint}: {type(exc).__name__}: {exc}")
        raise ConnectionError("No configured read-only RPC endpoint connected: " + " | ".join(failures))

    def get_web3(self) -> Web3:
        if self.web3 is None:
            return self.connect()
        return self.web3
