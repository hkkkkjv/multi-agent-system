"""
Evals для StudyFlow.
Запуск: python evals/run_evals.py
Требует: backend запущен на localhost:8000
"""
import httpx
import json
import time

BASE_URL = "http://localhost:8000"

# ── Тест-кейсы ────────────────────────────────────────────────
TEST_CASES = [
    # (запрос, ожидаемый route, ключевые слова в ответе)
    ("Python дедлайн завтра, история через неделю", "planner", ["09:00", "python", "план"]),
    ("Объясни что такое JOIN в SQL простыми словами", "tutor",  ["join", "таблиц", "пример"]),
    ("Застрял на алгоритмах, дай микрозадачу на 10 минут", "planner", ["минут", "задача"]),
    ("Python завтра и объясни мне что такое список", "both",   ["план", "список"]),
    ("Что такое нейронная сеть", "tutor", ["нейрон", "обучени"]),
]

LATENCY_THRESHOLD_SEC = 60  # P95 цель из ТЗ


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
                timeout=120,
            )
            latency = time.time() - t0
            data = resp.json()

            answer = data.get("answer", "").lower()
            route  = data.get("route", "")
            score  = data.get("quality_score", 0)

            route_ok    = route == expected_route or expected_route == "both"
            keywords_ok = sum(1 for k in keywords if k in answer) / len(keywords)
            latency_ok  = latency < LATENCY_THRESHOLD_SEC

            result = {
                "test": i,
                "message": message[:40],
                "expected_route": expected_route,
                "actual_route":   route,
                "route_ok":       route_ok,
                "keywords_hit":   f"{keywords_ok:.0%}",
                "quality_score":  score,
                "latency_sec":    round(latency, 1),
                "latency_ok":     latency_ok,
                "status":         "PASS" if (route_ok and keywords_ok >= 0.5 and latency_ok) else "FAIL",
            }
        except Exception as e:
            result = {
                "test": i, "message": message[:40],
                "status": "ERROR", "error": str(e),
            }

        results.append(result)
        status_icon = "V" if result["status"] == "PASS" else "X"
        print(f"  [{status_icon}] route={result.get('actual_route','?')} "
              f"kw={result.get('keywords_hit','?')} "
              f"score={result.get('quality_score','?')} "
              f"latency={result.get('latency_sec','?')}s")

    # Итог
    passed = sum(1 for r in results if r["status"] == "PASS")
    total  = len(results)
    print(f"\n{'='*60}")
    print(f"Результат: {passed}/{total} тестов прошло ({passed/total:.0%})")

    avg_latency = sum(r.get("latency_sec", 0) for r in results if "latency_sec" in r) / total
    avg_score   = sum(r.get("quality_score", 0) for r in results if "quality_score" in r) / total
    print(f"Avg latency: {avg_latency:.1f}s (цель < {LATENCY_THRESHOLD_SEC}s)")
    print(f"Avg quality_score: {avg_score:.2f} (цель > 0.8)")
    print(f"Task Completion Rate: {passed/total:.0%} (цель > 80%)")

    # Сохраняем JSON-отчёт
    with open("evals/results.json", "w", encoding="utf-8") as f:
        json.dump({"summary": {"passed": passed, "total": total,
                               "avg_latency": avg_latency, "avg_score": avg_score},
                   "tests": results}, f, ensure_ascii=False, indent=2)
    print("\nОтчёт сохранён: evals/results.json")


if __name__ == "__main__":
    run_evals()
