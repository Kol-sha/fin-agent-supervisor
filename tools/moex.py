"""Клиент Московской биржи (ISS API). Ключ не нужен, зависимости только стандартные."""
import json
import urllib.parse
import urllib.request

ISS = "https://iss.moex.com/iss"

# Какие типы бумаг считаем «акциями», и приоритет при выборе (меньше = лучше)
SHARE_TYPES = {"common_share": 0, "preferred_share": 1, "depositary_receipt": 2}
CURRENCY = {"SUR": "RUB"}


def _get(path: str, params: dict | None = None) -> dict:
    query = {"iss.meta": "off", **(params or {})}
    url = f"{ISS}/{path}.json?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": "supervisor-demo/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


def _rows(block: dict | None) -> list[dict]:
    """ISS отдаёт {'columns': [...], 'data': [[...]]} — превращаем в список словарей."""
    block = block or {}
    cols = [c.lower() for c in block.get("columns", [])]
    return [dict(zip(cols, row)) for row in block.get("data", [])]


def find_share(query: str, prefer_secid: str | None = None) -> dict | None:
    """Ищет торгуемую акцию по названию или тикеру. Возвращает строку ISS или None."""
    data = _get("securities", {"q": query, "iss.only": "securities"})
    rows = [
        r for r in _rows(data.get("securities"))
        if r.get("type") in SHARE_TYPES and r.get("is_traded") == 1 and r.get("secid")
    ]
    if not rows:
        return None

    want = (prefer_secid or "").upper()
    q = query.lower()

    def rank(r: dict):
        short = (r.get("shortname") or "").lower()
        return (
            r["secid"].upper() != want,        # точное совпадение тикера
            q not in short,                    # «газпром» ближе к «ГАЗПРОМ ао», чем к «Газпрнефть»
            SHARE_TYPES[r["type"]],            # обыкновенные раньше привилегированных
            r.get("primary_boardid") != "TQBR",
            len(short),
        )

    return sorted(rows, key=rank)[0]


def get_share_quote(secid: str, board: str | None = None) -> dict | None:
    """Последняя цена акции. Вне торгов берёт цену закрытия предыдущего дня."""
    data = _get(
        f"engines/stock/markets/shares/securities/{urllib.parse.quote(secid)}",
        {"iss.only": "marketdata,securities"},
    )

    def pick(rows: list[dict]) -> dict:
        for r in rows:
            if board and r.get("boardid") == board:
                return r
        return rows[0] if rows else {}

    md = pick(_rows(data.get("marketdata")))
    sec = pick(_rows(data.get("securities")))

    price, date = md.get("last"), (md.get("systime") or "")[:10]
    if price is None:
        price = md.get("lcurrentprice")
    if price is None:
        price, date = sec.get("prevprice"), sec.get("prevdate") or ""
    if price is None:
        return None

    currency = sec.get("currencyid") or "SUR"
    return {
        "symbol": secid,
        "price": price,
        "currency": CURRENCY.get(currency, currency),
        "date": date,
        "name": sec.get("secname") or sec.get("shortname"),
    }
