"""
Evals для StudyFlow.
Запуск: python evals/run_evals.py
"""
import httpx
import json
import time

BASE_URL = "http://localhost:8000"
TIMEOUT  = 180  # увеличен — модель думает до 130s на сложных запросах
LATENCY_THRESHOLD_SEC = 120  # реалистичная цель для локальных моделей

TEST_CASES = [
    (
        "Python дедлайн завтра, история через неделю",
        "planner",
        ["python", "история", "мин", "раздел"],
    ),
    (
        "Объясни что такое JOIN в SQL простыми словами",
        "tutor",
        ["join", "таблиц", "данн", "sql", "объедин"],  # разные формы слов
    ),
    (
        "Застрял на алгоритмах, дай микрозадачу на 10 минут",
        "planner",
        ["алгоритм", "минут", "задач", "тема"],
    ),
    (
        "Python завтра и объясни мне что такое список",
        "both",
        ["python", "список", "элемент"],
    ),
    (
        "Что такое нейронная сеть",
        "tutor",
        ["нейрон", "сет", "обучен", "слой"],
    ),
]


def run_evals():
    results = []
    print(f"\n{'='*60}")
    print("StudyFlow Evals")
    print(f"{'='*60}\n")

    for i, (message, expected_route, keywords) in enumerate(TEST_CASES, 1):
        print(f"[{i}/{len(TEST_CASES)}] {message[:50]}...")
        t0 = time.time()
        try:
            resp = httpx.post(
                f"{BASE_URL}/chat",
                json={"message": message, "session_id": f"eval_{i}"},
                timeout=TIMEOUT,
            )
            latency = time.time() - t0
            data    = resp.json()

            answer = data.get("answer", "").lower()
            route  = data.get("route", "")
            score  = data.get("quality_score", 0)

            route_ok    = route == expected_route
            # Ищем хотя бы частичное совпадение (начало слова)
            keywords_ok = sum(
                1 for k in keywords if any(k in word for word in answer.split())
            ) / len(keywords)
            latency_ok  = latency < LATENCY_THRESHOLD_SEC

            passed = route_ok and keywords_ok >= 0.4 and latency_ok
            result = {
                "test":           i,
                "message":        message[:40],
                "expected_route": expected_route,
                "actual_route":   route,
                "route_ok":       route_ok,
                "keywords_hit":   f"{keywords_ok:.0%}",
                "quality_score":  score,
                "latency_sec":    round(latency, 1),
                "latency_ok":     latency_ok,
                "status":         "PASS" if passed else "FAIL",
            }
        except httpx.TimeoutException:
            result = {
                "test": i, "message": message[:40],
                "status": "TIMEOUT",
                "error": f"No response in {TIMEOUT}s",
                "latency_sec": TIMEOUT,
            }
        except Exception as e:
            result = {
                "test": i, "message": message[:40],
                "status": "ERROR", "error": str(e),
            }

        results.append(result)
        icon = "V" if result["status"] == "PASS" else "X"
        print(f"  [{icon}] {result['status']:7} "
              f"route={result.get('actual_route','?'):7} "
              f"kw={result.get('keywords_hit','?'):4} "
              f"score={result.get('quality_score','?')} "
              f"latency={result.get('latency_sec','?')}s")

    passed_n  = sum(1 for r in results if r["status"] == "PASS")
    total     = len(results)
    valid     = [r for r in results if "latency_sec" in r and r["status"] != "ERROR"]
    avg_lat   = sum(r["latency_sec"] for r in valid) / len(valid) if valid else 0
    scored    = [r for r in results if isinstance(r.get("quality_score"), float)]
    avg_sc    = sum(r["quality_score"] for r in scored) / len(scored) if scored else 0

    print(f"\n{'='*60}")
    print(f"Результат:         {passed_n}/{total} тестов прошло ({passed_n/total:.0%})")
    print(f"Avg latency:       {avg_lat:.1f}s  (цель < {LATENCY_THRESHOLD_SEC}s)")
    print(f"Avg quality_score: {avg_sc:.2f}   (цель > 0.8)")
    print(f"Task Completion:   {passed_n/total:.0%}  (цель > 80%)")

    with open("evals/results.json", "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "passed": passed_n, "total": total,
                "tcr": f"{passed_n/total:.0%}",
                "avg_latency_sec": round(avg_lat, 1),
                "avg_quality_score": round(avg_sc, 2),
                "latency_threshold": LATENCY_THRESHOLD_SEC,
            },
            "tests": results,
        }, f, ensure_ascii=False, indent=2)
    print("\nОтчёт: evals/results.json")


if __name__ == "__main__":
    run_evals()