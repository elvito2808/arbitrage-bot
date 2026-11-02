"""Notification port with a safe no-op default.""" 
import logging


class Notifier:
    async def send(self, message: str) -> None:
        logging.getLogger(__name__).info("notification (no external sender configured): %s", message)
