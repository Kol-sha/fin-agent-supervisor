# main.py
import sys
from graph import build_graph


def run_query(app, query: str) -> str:
    """Прогоняет один запрос через граф и возвращает ответ."""
    result = app.invoke({
        "question": query,
        "messages": [],
        "next": "",
        "done": False,
        "first_decision": "",
    })

    # Собираем ответ из сообщений агента
    answer = ""
    for msg in result["messages"]:
        if msg["role"] == "assistant":
            answer = msg["content"]

    return answer


def interactive_mode(app):
    """Интерактивный режим: читает вопросы из stdin."""
    print("=" * 60)
    print("Мультиагентная система (Supervisor)")
    print("Агенты: Stock Agent (акции), FX Agent (валюты)")
    print("Введите 'exit' или 'quit' для выхода.")
    print("=" * 60)

    while True:
        try:
            query = input("\nВаш вопрос: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break

        if not query:
            continue

        if query.lower() in ("exit", "quit", "выход"):
            print("До встречи!")
            break

        try:
            answer = run_query(app, query)
            if answer:
                print(f"\n{answer}")
            else:
                print("\n[Система] Вопрос не по теме — ни один агент не смог ответить.")
        except Exception as e:
            print(f"\n[Ошибка] {e}")


def demo_mode(app):
    """Демо-режим с заранее заданными запросами."""
    queries = [
        "Какая цена акции AAPL?",
        "Какой курс USD/RUB?",
        "Что такое квантовая физика?",
    ]

    for q in queries:
        print(f"\n{'='*60}")
        print(f"Запрос: {q}")
        print("=" * 60)
        answer = run_query(app, q)
        print(answer if answer else "[Система] Не по теме.")


if __name__ == "__main__":
    app = build_graph()

    # Если передан аргумент --demo — запускаем демо, иначе интерактив
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo_mode(app)
    else:
        interactive_mode(app)