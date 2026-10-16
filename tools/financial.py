import os
import re
import json
import subprocess
import datetime as dt

from langchain_core.tools import tool

import xfinlink as xfl

from . import moex

# --- Настройка Xfinlink ---
XFINLINK_API_KEY = os.environ.get("XFINLINK_API_KEY")
if XFINLINK_API_KEY:
    xfl.set_api_key(XFINLINK_API_KEY)


# --- Алиасы популярных компаний ---
TICKER_ALIASES = {
    "APPLE": "AAPL",
    "GOOGLE": "GOOG",
    "MICROSOFT": "MSFT",
    "TESLA": "TSLA",
    "NVIDIA": "NVDA",
    "AMAZON": "AMZN",
    "META": "META",
    "FACEBOOK": "META",
    "NETFLIX": "NFLX",
    "INTEL": "INTC",
    "AMD": "AMD",
    "IBM": "IBM",
    "ORACLE": "ORCL",
    "ALPHABET": "GOOG",
}


# --- Алиасы валют (русские и английские названия → ISO-код) ---
CURRENCY_ALIASES = {
    # Русские
    "РУБЛЬ": "RUB",
    "РУБЛЯ": "RUB",
    "РУБЛЕЙ": "RUB",
    "ДОЛЛАР": "USD",
    "ДОЛЛАРА": "USD",
    "ДОЛЛАРОВ": "USD",
    "ЕВРО": "EUR",
    "ФУНТ": "GBP",
    "ФУНТОВ": "GBP",
    "ЙЕНА": "JPY",
    "ЙЕНЫ": "JPY",
    "ЮАНЬ": "CNY",
    "ЮАНЯ": "CNY",
    "ФРАНК": "CHF",
    "ФРАНКА": "CHF",
    # Английские
    "DOLLAR": "USD",
    "DOLLARS": "USD",
    "RUBLE": "RUB",
    "RUBLES": "RUB",
    "EURO": "EUR",
    "EUROS": "EUR",
    "POUND": "GBP",
    "POUNDS": "GBP",
    "YEN": "JPY",
    "YUAN": "CNY",
    "FRANC": "CHF",
}


EXCHANGE_NAMES = {"MOEX": "Мосбиржа", "US": "США"}

# Слова, которые не могут быть названием компании (для запасного поиска без LLM)
STOPWORDS = {
    "какая", "какой", "цена", "цены", "акции", "акций", "акция", "сколько", "стоит",
    "сейчас", "сегодня", "покажи", "хочу", "узнать", "стоимость", "одна", "одной",
    "компании", "компания", "пожалуйста", "расскажи", "подскажи", "текущая",
}

# Заглавные латинские слова, которые не являются тикерами акций
NOT_TICKERS = {"USD", "EUR", "RUB", "GBP", "JPY", "CNY", "CHF", "ETF", "IPO", "CEO"}

EXTRACT_PROMPT = """Из вопроса пользователя выдели компанию, акции которой его интересуют.
Верни ТОЛЬКО JSON без пояснений и без markdown:
{"company": "название компании в именительном падеже, как её называют дома (Газпром, Сбербанк, Apple)",
 "company_en": "официальное английское название или null",
 "ticker": "тикер, только если ты в нём уверен, иначе null",
 "exchange": "MOEX, US или OTHER (где компания торгуется основной бумагой)"}
Если в вопросе нет конкретной компании, верни {"company": null}."""


def _explicit_ticker(text: str) -> str | None:
    """Тикер, написанный в вопросе заглавными латинскими буквами (AAPL, GAZP)."""
    for m in re.finditer(r"(?<![A-Za-z])([A-Z]{2,5})(?![A-Za-z])", text):
        if m.group(1) not in NOT_TICKERS:
            return m.group(1)
    return None


def _fallback_queries(text: str) -> list[str]:
    """Запасной вариант без LLM: русские слова вопроса без падежных окончаний."""
    out: list[str] = []
    for word in re.findall(r"[А-Яа-яЁё]{4,}", text):
        word = word.lower()
        if word in STOPWORDS:
            continue
        out += [word, word[:-1], word[:-2]]
    return [w for w in dict.fromkeys(out) if len(w) >= 4]


def _identify_with_llm(question: str) -> dict:
    try:
        from config import llm  # импорт здесь, чтобы tools не требовали ключ при импорте

        raw = llm.invoke([
            {"role": "system", "content": EXTRACT_PROMPT},
            {"role": "user", "content": question},
        ]).content
        match = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(match.group(0)) if match else {}
    except Exception:
        data = {}

    def clean(value):
        return None if value in (None, "", "null", "None") else str(value).strip()

    ticker = clean(data.get("ticker"))
    return {
        "company": clean(data.get("company")),
        "company_en": clean(data.get("company_en")),
        "ticker": ticker.upper() if ticker else None,
        "exchange": clean(data.get("exchange")),
    }


def _identify(question: str) -> dict:
    """Определяет компанию: сначала быстрые правила, потом LLM."""
    upper = question.upper()
    for alias, ticker in TICKER_ALIASES.items():
        if re.search(rf"\b{alias}\b", upper):
            return {"ticker": ticker, "company": alias.title(), "exchange": "US"}

    ticker = _explicit_ticker(question)
    if ticker:
        return {"ticker": ticker, "company": None, "exchange": None}

    return _identify_with_llm(question)


def _quote_us(info: dict) -> dict | None:
    """Акции, торгуемые в США (xfinlink)."""
    symbol = info.get("ticker")
    if not symbol:
        name = info.get("company_en") or info.get("company")
        if not name:
            return None
        found = xfl.search(q=name)
        if found is None or found.empty:
            return None
        best = found.iloc[0]
        symbol = best.get("symbol", best.get("ticker"))
        if not symbol:
            return None

    start = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    df = xfl.prices(symbol, start=start)
    if df is None or df.empty:
        return None

    row = df.iloc[-1]
    price = row.get("close", row.get("adj_close"))
    if price is None:
        return None
    return {
        "symbol": symbol,
        "price": price,
        "currency": "USD",
        "date": str(row.get("date", ""))[:10],
        "name": info.get("company"),
        "exchange": "US",
    }


def _quote_moex(info: dict) -> dict | None:
    """Акции Московской биржи (ISS)."""
    ticker = info.get("ticker")
    queries = [q for q in (ticker, info.get("company"), info.get("company_en")) if q]
    queries += info.get("fallback", [])

    for q in dict.fromkeys(queries):
        share = moex.find_share(q, prefer_secid=ticker)
        if not share:
            continue
        quote = moex.get_share_quote(share["secid"], share.get("primary_boardid"))
        if quote:
            quote["name"] = info.get("company") or quote.get("name")
            quote["exchange"] = "MOEX"
            return quote
    return None


def _format_quote(q: dict) -> str:
    # Формат разбирает интерфейс (app.py): «ТИКЕР: цена ВАЛЮТА (на дата) — название (биржа)»
    text = f"{q['symbol']}: {q['price']} {q['currency']} (на {q['date']})"
    text += f" — {q.get('name') or q['symbol']} ({EXCHANGE_NAMES[q['exchange']]})"
    return text


def lookup_stock(question: str) -> str:
    """Находит компанию в вопросе и возвращает цену акции с Мосбиржи или из США."""
    info = _identify(question)

    if not (info.get("ticker") or info.get("company") or info.get("company_en")):
        words = _fallback_queries(question)
        if not words:
            return f"Не удалось понять, о какой компании речь: {question}"
        info["fallback"] = words

    order = [("MOEX", _quote_moex), ("US", _quote_us)]
    if info.get("exchange") != "MOEX":
        order.reverse()

    errors = []
    for market, fetch in order:
        try:
            quote = fetch(info)
        except Exception as e:  # сеть, лимиты, неизвестный тикер
            errors.append(f"{EXCHANGE_NAMES[market]}: {e}")
            continue
        if quote:
            return _format_quote(quote)

    what = info.get("company") or info.get("ticker") or question
    msg = f"Не нашёл акции «{what}» ни на Мосбирже, ни среди бумаг, торгуемых в США."
    if errors:
        msg += " Ошибки источников: " + "; ".join(errors)
    return msg


@tool
def get_stock_quote(ticker: str) -> str:
    """Возвращает текущую цену акции по тикеру или названию компании
    (Московская биржа и рынок США)."""
    return lookup_stock(ticker)


def _extract_currency_pair(text: str) -> tuple[str, str] | None:
    """Извлекает валютную пару из текста.

    Поддерживает:
    - Формат USD/RUB, USD-RUB
    - Русские названия: 'рубля относительно доллара'
    - Смешанные: 'курс доллара к рублю'
    """
    text_upper = text.upper()

    # 1. Пробуем формат XXX/YYY или XXX-YYY
    match = re.search(r'\b([A-Z]{3})[/\-]([A-Z]{3})\b', text_upper)
    if match:
        return match.group(1), match.group(2)

    # 2. Ищем названия валют и их порядок в тексте
    found = []
    for alias, code in CURRENCY_ALIASES.items():
        # Ищем позицию каждого алиаса в тексте
        for m in re.finditer(rf'\b{alias}\b', text_upper):
            found.append((m.start(), code))

    if len(found) < 2:
        return None

    # Сортируем по позиции в тексте
    found.sort(key=lambda x: x[0])

    # Убираем дубликаты подряд (например, "рубля рубль")
    unique = []
    for pos, code in found:
        if not unique or unique[-1][1] != code:
            unique.append((pos, code))

    if len(unique) < 2:
        return None

    first_code = unique[0][1]
    second_code = unique[1][1]

    # Определяем порядок: "курс X к Y" означает X/Y
    # "рубля относительно доллара" → RUB/USD? Или USD/RUB?
    # Обычно "курс доллара к рублю" = USD/RUB (сколько рублей за доллар)
    # "курс рубля к доллару" = RUB/USD (сколько долларов за рубль)

    # Проверяем предлоги: "к", "относительно", "в"
    # Если после первого названия идёт "к" или "относительно" — первый это базовая валюта
    between = text_upper[unique[0][0]:unique[1][0]]

    if re.search(r'\b(К|ОТНОСИТЕЛЬНО|В)\b', between):
        # "рубля относительно доллара" → RUB/USD
        return first_code, second_code
    else:
        # По умолчанию: "курс доллара рубль" → USD/RUB
        return first_code, second_code


@tool
def get_fx_rate(pair: str) -> str:
    """Возвращает текущий курс валютной пары (реальные данные).

    Поддерживает форматы: 'USD/RUB', 'курс доллара к рублю',
    'сколько рублей за доллар', 'рубль относительно доллара'.
    """
    extracted = _extract_currency_pair(pair)
    if not extracted:
        return f"Не удалось распознать валютную пару в запросе: {pair}"

    from_curr, to_curr = extracted

    try:
        result = subprocess.run(
            ["exrate", "rate", from_curr, to_curr, "--json"],
            capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        return f"{from_curr}/{to_curr}: {data['rate']} (на {data['date']})"
    except Exception as e:
        return f"Ошибка при получении курса {from_curr}/{to_curr}: {e}"