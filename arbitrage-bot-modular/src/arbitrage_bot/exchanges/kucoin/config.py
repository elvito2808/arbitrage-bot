"""KuCoin-specific API and market data configuration."""

EXCHANGE_ID = "kucoin"
KUCOIN_BASE_URL = "https://api.kucoin.com"
KUCOIN_BALANCE_ENDPOINT = "/api/v1/accounts"
KUCOIN_TIME_ENDPOINT = "/api/v1/timestamp"
KUCOIN_PRICE_ENDPOINT = "/api/v1/market/orderbook/level1?symbol={symbol}"
KUCOIN_ORDER_ENDPOINT = "/api/v1/orders"
KUCOIN_SYMBOL = "ZIL-USDT"
PRICE_CACHE_TIMEOUT = 8
