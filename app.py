"""Веб-интерфейс для мультиагентной системы (Supervisor + Stock/FX агенты).

Запуск из корня проекта:
    streamlit run app.py
"""
import html
import re
import time

import streamlit as st

st.set_page_config(page_title="Котировки", page_icon="📈", layout="centered")

# --------------------------------------------------------------------------
# Данные интерфейса
# --------------------------------------------------------------------------
INK = "#0F2433"
STOCK = "#2455A4"
FX = "#A8700A"
OFF = "#6B7782"
ERR = "#B3261E"

AGENTS = {
    "stock": {"label": "Stock Agent", "color": STOCK, "kind": "Акция"},
    "fx": {"label": "FX Agent", "color": FX, "kind": "Валютная пара"},
}

GROUPS = [
    ("Акции", "Stock Agent", STOCK, ["Какая цена акции AAPL?", "Сколько стоит Tesla?"]),
    ("Валюты", "FX Agent", FX, ["Какой курс USD/RUB?", "Сколько рублей за один доллар?"]),
    ("Вне темы", "Supervisor откажет", OFF, ["Как приготовить борщ?"]),
]

OFF_TOPIC_TEXT = (
    "Это не вопрос про акции или валюты, поэтому ни один агент не ответил. "
    "Спросите, например, цену AAPL или курс EUR/RUB."
)

QUOTE_RE = re.compile(
    r"^\[(?P<agent>[^\]]+)\]\s*(?P<label>[^:]+):\s*(?P<value>-?[\d.,]+)\s*"
    r"(?P<unit>[A-Z]{3})?\s*\(на\s+(?P<date>[^)]+)\)\s*$"
)

# --------------------------------------------------------------------------
# Стили
# --------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,600&display=swap');

:root {
  --paper:#F1F3EF; --surface:#FBFCFA; --ink:#0F2433; --muted:#5A6B78; --rule:#D3D9D6;
}
html, body, .stApp, .stApp [class*="st-"] { font-family:'IBM Plex Sans', system-ui, sans-serif; }
.stApp { background: var(--paper); }
#MainMenu, footer, header[data-testid="stHeader"] { visibility:hidden; height:0; }
.block-container { max-width:780px; padding-top:2.6rem; padding-bottom:7rem; }

/* Шапка */
.mast { border-bottom:2px solid var(--ink); padding-bottom:18px; margin-bottom:26px; }
.mast h1 {
  font-family:'Newsreader', Georgia, serif !important; font-weight:600 !important;
  font-size:3.4rem !important; line-height:1 !important; letter-spacing:-.02em;
  margin:0 0 12px !important; padding:0 !important; color:var(--ink);
}
.mast p { margin:0; color:var(--muted); max-width:54ch; line-height:1.55; font-size:1.02rem; }

/* Пустой экран: группы примеров */
.group { border-top:3px solid var(--c); padding-top:10px; margin-bottom:10px; }
.group b { display:block; font-size:1.05rem; color:var(--ink); }
.group small { color:var(--muted); font-size:.85rem; }
.stButton button {
  width:100%; text-align:left; justify-content:flex-start; border-radius:999px;
  border:1px solid var(--rule); background:var(--surface); color:var(--ink);
  padding:.45rem 1rem; font-weight:500; transition:border-color .15s, background .15s;
}
.stButton button:hover { border-color:var(--ink); background:#fff; color:var(--ink); }
.stButton button:focus-visible { outline:2px solid var(--ink); outline-offset:2px; }

/* Вопрос */
.ask { display:flex; justify-content:flex-end; margin:30px 0 16px; }
.ask span {
  background:var(--ink); color:#fff; padding:11px 18px; max-width:82%;
  border-radius:18px 18px 4px 18px; line-height:1.45;
}

/* Маршрут: пустой кружок = маршрутизация, закрашенный = источник данных */
ol.trace { display:flex; list-style:none; padding:0; margin:0 0 18px; }
ol.trace li { flex:1; position:relative; padding-top:24px; min-width:0; }
ol.trace li::before {
  content:""; position:absolute; top:0; left:0; width:14px; height:14px; border-radius:50%;
  box-sizing:border-box; background:var(--paper); border:2px solid var(--ink);
}
ol.trace li.src::before { background:var(--c); border-color:var(--c); width:18px; height:18px; top:-2px; }
ol.trace li:not(:last-child)::after {
  content:""; position:absolute; top:6px; left:24px; right:8px; height:2px;
  background:var(--rule); transform-origin:left;
}
ol.trace b { display:block; font-size:.9rem; font-weight:600; color:var(--ink); }
ol.trace li.src b { color:var(--c); }
ol.trace small { display:block; font-size:.8rem; color:var(--muted); line-height:1.35; padding-right:10px; }

/* Табличка с котировкой */
.plate {
  background:var(--surface); border:1px solid var(--rule); border-top:6px solid var(--c);
  border-radius:10px; padding:18px 24px 22px; display:grid;
  grid-template-columns:1fr auto; gap:14px 36px; align-items:end;
}
.plate .tag { grid-column:1 / -1; display:flex; align-items:center; gap:8px; font-weight:600; font-size:.9rem; color:var(--c); }
.plate .tag::before { content:""; width:8px; height:8px; border-radius:50%; background:var(--c); }
.plate .num {
  font-family:'Newsreader', Georgia, serif; font-size:4.6rem; font-weight:600; line-height:1;
  letter-spacing:-.025em; color:var(--ink); font-variant-numeric:tabular-nums; white-space:nowrap;
}
.plate .num .frac { color:var(--muted); font-weight:400; }
.plate .num .unit {
  font-family:'IBM Plex Sans', sans-serif; font-size:1.15rem; font-weight:500;
  letter-spacing:0; color:var(--muted); margin-left:12px;
}
.plate .sub { color:var(--muted); margin-top:10px; font-size:.95rem; }
.plate .meta { display:grid; gap:8px; min-width:190px; }
.plate .meta div {
  display:flex; justify-content:space-between; gap:20px; border-top:1px solid var(--rule);
  padding-top:7px; font-size:.88rem;
}
.plate .meta span:first-child { color:var(--muted); }
.plate .meta span:last-child { font-weight:600; color:var(--ink); text-align:right; }

.plain {
  background:var(--surface); border:1px solid var(--rule); border-left:5px solid var(--c);
  border-radius:10px; padding:16px 20px; color:var(--ink); line-height:1.55;
}

/* Поле ввода */
[data-testid="stBottom"] > div { background:var(--paper); }
[data-testid="stChatInput"] {
  border:1px solid var(--rule); border-radius:16px; background:var(--surface);
}
[data-testid="stChatInput"]:focus-within { border-color:var(--ink); box-shadow:none; }

/* Появление ответа: один согласованный момент, только для свежего ответа */
@keyframes draw { from { transform:scaleX(0); } to { transform:scaleX(1); } }
@keyframes pop  { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:none; } }
ol.trace.fresh li { animation:pop .3s ease-out both; animation-delay:calc(var(--i) * .32s); }
ol.trace.fresh li::after { animation:draw .32s ease-out both; animation-delay:calc(var(--i) * .32s + .1s); }
.plate.fresh, .plain.fresh { animation:pop .45s ease-out both; animation-delay:calc(var(--n) * .32s); }

@media (max-width:640px) {
  .mast h1 { font-size:2.6rem !important; }
  .plate { grid-template-columns:1fr; }
  .plate .num { font-size:3.4rem; }
  ol.trace small { font-size:.75rem; }
}
@media (prefers-reduced-motion:reduce) {
  ol.trace.fresh li, ol.trace.fresh li::after, .plate.fresh, .plain.fresh { animation:none !important; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Граф
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def load_graph():
    from graph import build_graph  # импорт внутри: config.py падает без GROQ_API_KEY

    return build_graph()


def run_query(graph_app, query: str) -> dict:
    """Прогоняет запрос через граф, собирая маршрут, ответ и время."""
    started = time.perf_counter()
    trace, answer, first_decision = [], None, None

    state = {
        "question": query,
        "messages": [],
        "next": "",
        "done": False,
        "first_decision": "",
    }
    for update in graph_app.stream(state, stream_mode="updates"):
        for node, payload in update.items():
            payload = payload or {}
            if node == "supervisor":
                nxt = payload.get("next", "finish")
                if first_decision is None:
                    first_decision = nxt
                if nxt in AGENTS:
                    trace.append(("Supervisor", f"передал {AGENTS[nxt]['label']}", None))
                elif answer:
                    trace.append(("Supervisor", "ответ готов, завершил", None))
                else:
                    trace.append(("Supervisor", "вопрос не по теме, завершил", None))
            elif node in ("stock_agent", "fx_agent"):
                key = "stock" if node == "stock_agent" else "fx"
                for msg in payload.get("messages", []):
                    if msg.get("role") == "assistant":
                        answer = msg["content"]
                trace.append((AGENTS[key]["label"], "получил данные", AGENTS[key]["color"]))

    return {
        "query": query,
        "trace": trace,
        "answer": answer,
        "agent": first_decision if first_decision in AGENTS else None,
        "elapsed": time.perf_counter() - started,
    }


# --------------------------------------------------------------------------
# Форматирование
# --------------------------------------------------------------------------
def split_number(value: str) -> tuple[str, str]:
    """'1234.5' -> ('1 234', '5'): пробел между разрядами, цифры не округляем."""
    v = value.replace(",", ".")
    sign = "-" if v.startswith("-") else ""
    v = v.lstrip("-")
    whole, _, frac = v.partition(".")
    if whole.isdigit():
        whole = f"{int(whole):,}".replace(",", "\u202f")
    return sign + whole, frac


def fmt_date(raw: str) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw.strip())
    return f"{m[3]}.{m[2]}.{m[1]}" if m else raw.strip()


def fmt_elapsed(seconds: float) -> str:
    return f"{seconds:.1f}".replace(".", ",") + " с"


# --------------------------------------------------------------------------
# HTML-блоки (без пустых строк и отступов, иначе markdown сломает разметку)
# --------------------------------------------------------------------------
def question_html(query: str) -> str:
    return f'<div class="ask"><span>{html.escape(query)}</span></div>'


def trace_html(trace, fresh: bool) -> str:
    items = ""
    for i, (name, note, color) in enumerate(trace):
        cls = "src" if color else ""
        style = f"--i:{i};" + (f"--c:{color};" if color else "")
        items += (
            f'<li class="{cls}" style="{style}"><b>{html.escape(name)}</b>'
            f"<small>{html.escape(note)}</small></li>"
        )
    return f'<ol class="trace{" fresh" if fresh else ""}">{items}</ol>'


def result_html(entry: dict, fresh: bool = False) -> str:
    fresh_cls = " fresh" if fresh else ""
    n = len(entry.get("trace", []))

    if entry.get("error"):
        return (
            f'<div class="plain{fresh_cls}" style="--c:{ERR};--n:0">'
            f"{html.escape(entry['error'])}</div>"
        )

    trace = trace_html(entry["trace"], fresh) if entry["trace"] else ""
    agent, answer = entry["agent"], entry["answer"]
    color = AGENTS[agent]["color"] if agent else OFF

    if not answer:
        body = (
            f'<div class="plain{fresh_cls}" style="--c:{OFF};--n:{n}">'
            f"{html.escape(OFF_TOPIC_TEXT)}</div>"
        )
        return trace + body

    m = QUOTE_RE.match(answer)
    if not m:  # сообщение об ошибке инструмента или нестандартный ответ
        text = re.sub(r"^\[[^\]]+\]\s*", "", answer)
        body = (
            f'<div class="plain{fresh_cls}" style="--c:{color};--n:{n}">'
            f"{html.escape(text)}</div>"
        )
        return trace + body

    label, unit = m["label"].strip(), m["unit"]
    sub = "цена одной акции"
    if not unit and "/" in label:
        base, unit = label.split("/", 1)
        sub = f"за 1 {base}"
    whole, frac = split_number(m["value"])
    frac_html = f'<span class="frac">,{html.escape(frac)}</span>' if frac else ""
    unit_html = f'<span class="unit">{html.escape(unit)}</span>' if unit else ""
    kind = AGENTS[agent]["kind"] if agent else "Инструмент"

    body = (
        f'<div class="plate{fresh_cls}" style="--c:{color};--n:{n}">'
        f'<div class="tag">{html.escape(m["agent"])}</div>'
        f'<div><div class="num">{html.escape(whole)}{frac_html}{unit_html}</div>'
        f'<div class="sub">{html.escape(sub)}</div></div>'
        f'<div class="meta">'
        f"<div><span>{html.escape(kind)}</span><span>{html.escape(label)}</span></div>"
        f'<div><span>Данные на</span><span>{html.escape(fmt_date(m["date"]))}</span></div>'
        f'<div><span>Ответ за</span><span>{fmt_elapsed(entry.get("elapsed", 0))}</span></div>'
        f"</div></div>"
    )
    return trace + body


# --------------------------------------------------------------------------
# Страница
# --------------------------------------------------------------------------
st.markdown(
    '<header class="mast"><h1>Котировки</h1>'
    "<p>Цены акций и курсы валют. Supervisor читает вопрос и передаёт его "
    "нужному агенту. Путь запроса виден над каждым ответом.</p></header>",
    unsafe_allow_html=True,
)

try:
    graph_app = load_graph()
except Exception as e:  # noqa: BLE001
    st.error(
        f"Не удалось собрать граф: {e}\n\n"
        "Проверьте, что запускаете `streamlit run app.py` из корня проекта "
        "и что заданы переменные окружения GROQ_API_KEY и XFINLINK_API_KEY."
    )
    st.stop()

history = st.session_state.setdefault("history", [])


def pick_example(text: str):
    st.session_state["pending"] = text


pending = st.session_state.pop("pending", None)
prompt = st.chat_input("Спросите про цену акции или курс валюты") or pending

if history:
    for entry in history:
        st.markdown(question_html(entry["query"]) + result_html(entry), unsafe_allow_html=True)
elif not prompt:
    cols = st.columns(3)
    for col, (title, note, color, examples) in zip(cols, GROUPS):
        with col:
            st.markdown(
                f'<div class="group" style="--c:{color}"><b>{title}</b><small>{note}</small></div>',
                unsafe_allow_html=True,
            )
            for ex in examples:
                st.button(ex, key=f"ex-{ex}", on_click=pick_example, args=(ex,))

if prompt:
    st.markdown(question_html(prompt), unsafe_allow_html=True)
    with st.spinner("Supervisor выбирает агента…"):
        try:
            entry = run_query(graph_app, prompt)
        except Exception as e:  # noqa: BLE001
            entry = {"query": prompt, "error": f"Ошибка при выполнении запроса: {e}"}
    st.markdown(result_html(entry, fresh=True), unsafe_allow_html=True)
    history.append(entry)

if history:
    if st.button("Очистить диалог", key="clear"):
        history.clear()
        st.rerun()
