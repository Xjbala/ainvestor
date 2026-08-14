"""Stock code normalization for financial query tools."""


def normalize_stock_code(stock_code: str | int) -> str:
    """Return a six-digit stock code suitable for VARCHAR database columns."""
    if isinstance(stock_code, bool):
        raise ValueError("stock_code must be a six-digit string or integer")

    if isinstance(stock_code, int):
        normalized = str(stock_code).zfill(6)
    elif isinstance(stock_code, str):
        normalized = stock_code.strip()
    else:
        raise ValueError("stock_code must be a six-digit string or integer")

    if (
        len(normalized) != 6
        or not normalized.isascii()
        or not normalized.isdigit()
    ):
        raise ValueError("stock_code must contain exactly six digits")

    return normalized
