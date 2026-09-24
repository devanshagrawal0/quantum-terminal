class HyperliquidError(Exception):
    """Base error for anything this package raises."""


class HttpError(HyperliquidError):
    def __init__(self, status: int, body: str, request: dict):
        super().__init__(f"HTTP {status}: {body[:400]}")
        self.status = status
        self.body = body
        self.request = request


class RateLimited(HttpError):
    pass


class WsError(HyperliquidError):
    pass
