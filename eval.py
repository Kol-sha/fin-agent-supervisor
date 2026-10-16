from graph import build_graph


TEST_CASES = [
    # --- Stock Agent ---
    {"query": "Какая цена акции AAPL?", "expected": "stock"},
    {"query": "Сколько стоит GOOG?", "expected": "stock"},
    {"query": "Покажи цену MSFT", "expected": "stock"},
    {"query": "Какая сейчас цена TSLA?", "expected": "stock"},
    {"query": "Хочу узнать стоимость акции Apple", "expected": "stock"},
    {"query": "Цена акции Microsoft на сегодня", "expected": "stock"},
    {"query": "Сколько стоит одна акция Tesla?", "expected": "stock"},

    # --- FX Agent ---
    {"query": "Какой курс USD/RUB?", "expected": "fx"},
    {"query": "Сколько стоит евро в рублях?", "expected": "fx"},
    {"query": "Курс EUR/RUB на сегодня", "expected": "fx"},
    {"query": "Какой сейчас курс USD/EUR?", "expected": "fx"},
    {"query": "Переведи GBP в USD", "expected": "fx"},
    {"query": "Курс доллара к рублю", "expected": "fx"},
    {"query": "Сколько рублей за один доллар?", "expected": "fx"},

    # --- Не по теме ---
    {"query": "Что такое квантовая физика?", "expected": "finish"},
    {"query": "Как приготовить борщ?", "expected": "finish"},
    {"query": "Расскажи про историю Древнего Рима", "expected": "finish"},
    {"query": "Какая погода в Москве?", "expected": "finish"},
    {"query": "Посоветуй книгу по машинному обучению", "expected": "finish"},
    {"query": "Как дела?", "expected": "finish"},
]


def classify_query(app, query: str) -> str:
    """Прогоняет запрос через граф и возвращает ПЕРВОЕ решение Supervisor."""
    result = app.invoke({
        "question": query,
        "messages": [],
        "next": "",
        "done": False,
        "first_decision": "",
    })
    return result.get("first_decision") or "finish"


def evaluate():
    app = build_graph()

    correct = 0
    total = len(TEST_CASES)

    labels = ["stock", "fx", "finish"]
    confusion = {exp: {pred: 0 for pred in labels} for exp in labels}

    print(f"{'Запрос':<45} {'Ожидали':>10} {'Получили':>10} {'':>4}")
    print("-" * 74)

    for case in TEST_CASES:
        query = case["query"]
        expected = case["expected"]

        predicted = classify_query(app, query)

        is_correct = predicted == expected
        correct += int(is_correct)
        mark = "✅" if is_correct else "❌"

        q = query[:42]
        print(f"{q:<45} {expected:>10} {predicted:>10} {mark:>4}")

        if expected in confusion and predicted in confusion[expected]:
            confusion[expected][predicted] += 1

    accuracy = correct / total

    print("-" * 74)
    print(f"\nAccuracy маршрутизации: {accuracy:.2f} ({correct}/{total})\n")

    print("Confusion matrix (строки — ожидали, столбцы — получили):")
    print(f"{'':>10} " + " ".join(f"{l:>8}" for l in labels))
    for exp in labels:
        row = " ".join(f"{confusion[exp][pred]:>8}" for pred in labels)
        print(f"{exp:>10} {row}")

    print("\nМетрики по классам:")
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in labels if other != label)
        fn = sum(confusion[label][other] for other in labels if other != label)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        print(f"  {label:>8}: precision={precision:.2f}  recall={recall:.2f}  f1={f1:.2f}")


if __name__ == "__main__":
    evaluate()