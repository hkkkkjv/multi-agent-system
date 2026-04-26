# StudyFlow

> **Мультиагентная система для управления параллельным обучением**  
> *Перовская Ольга, группа 11-302* | Апрель 2026

---

## Что это?

**StudyFlow** помогает студентам и самоучкам изучать несколько тем одновременно (например, Python + История + SQL), не теряя фокус и успевая к дедлайнам.

```
Пользователь: "Python дедлайн завтра, объясни что такое список"
↓
StudyFlow:
  ✓ Planner → план изучения Python с приоритетом на завтра
  ✓ Tutor → объяснение списков простыми словами + пример
  ✓ Оценка качества → 0.87/1.0
```

---

## Ключевые возможности

| Фича | Описание |
|------|----------|
| Умная маршрутизация | Supervisor определяет: нужен план, объяснение или оба агента |
| Планирование с дедлайнами | Planner строит расписание, приоритезируя срочные темы |
| Адаптивные объяснения | Tutor объясняет темы под уровень пользователя (простыми словами → технические детали) |
| Контроль качества | Evaluator проверяет ответы; при score < 0.8 — автоматический retry |
| RAG-память | Поиск по загруженным конспектам и PDF через ChromaDB |
| Observability | Трейсы в Langfuse, метрики в Prometheus/Grafana |

---

## Стек технологий

```
Backend:  Python · FastAPI · LangGraph · LangChain
LLM:      Qwen 2.5 (1.5b/3b/7b) via Ollama + Kimi K2.5 Cloud
Memory:   ChromaDB (vector) + in-process session buffer
Infra:    Docker Compose · Prometheus · Grafana · Langfuse
UI:       Streamlit
```

**Почему Qwen 2.5?** Открытые веса, отличный русский, линейка размеров под задачу.  
**Почему не Qwen 3.5?** При тестировании часто не отвечал на базовые промпты — оставлен как cloud fallback.

---

## Быстрый старт

```bash
# 1. Клонировать
git clone https://github.com/hkkkkjv/studyflow
cd studyflow

# 2. Запустить всё одной командой
docker-compose -f studyflow/infra/docker-compose.yml up -d

# 3. Проверить статус
dodocker-compose -f studyflow/infra/docker-compose.yml ps  # все сервисы должны быть "Up"

# 4. Открыть интерфейс
# Streamlit UI: http://localhost:8501
# Langfuse:     http://localhost:3000
# Prometheus:   http://localhost:9090
# Grafana:      http://localhost:3001 (admin/studyflow)
```

---

## Архитектура (упрощённо)

```
Пользователь
    │
    ▼
┌─────────────┐
│  Supervisor │ → маршрутизация: planner / tutor / both
└──────┬──────┘
       │
   ┌───┴───┐
   ▼       ▼
┌─────┐ ┌─────┐
│Planner│ │Tutor│ → объяснение тем
└──┬──┘ └──┬──┘
   │       │
   ▼       ▼
┌─────────────┐
│  Evaluator  │ → score 0.0–1.0, retry при <0.8
└──────┬──────┘
       ▼
   Ответ пользователю
```

**Агенты и модели:**

| Агент | Задача | Модель |
|-------|--------|--------|
| Supervisor | Маршрутизация запроса | `qwen2.5:7b` |
| Planner | Учебный план с дедлайнами | `qwen2.5:3b` |
| Tutor | Объяснение тем | `kimi-k2.5:cloud` |
| Evaluator | Оценка качества ответа | `qwen2.5:1.5b` |

---

## Структура проекта

```
.
├── studyflow/
│   ├── backend/          # FastAPI + LangGraph агенты
│   │   ├── agents/       # supervisor, planner, tutor, evaluator
│   │   ├── prompts/      # AGENT_CONTEXT.md, SKILLS_REFERENCE.md
│   │   └── main.py       # entry point
│   ├── ui/               # Streamlit интерфейс
│   ├── evals/            # автотесты качества
│   └── infra/            # docker-compose, prometheus.yml
├── models-comparison/    # тесты и сравнение LLM
└── README.md
```

---

## Результаты evals

| Метрика | Цель | Достигнуто |
|---------|------|------------|
| Task Completion Rate | > 80% | ~80% |
| Avg Quality Score | > 0.80 | ~0.84 |
| P95 Latency | < 120s | < 120s |
| Route Accuracy | > 90% | ~90% |

*Тестировалось на 5 сценариях: планирование, объяснение, микрозадачи, комбо-запросы, теория.*

---

## Полезные ссылки

- [Полный отчёт](report/StudyFlow_Report.pdf) — детальное описание архитектуры, промптов, проблем и решений
- [Сравнение моделей](models-comparison/models-comparison.md) — как выбирали LLM под каждого агента
- [Docker Compose](studyflow/infra/docker-compose.yml) — конфигурация инфраструктуры

---

## Разработка

```bash
# Запуск только backend (для отладки)
cd studyflow/backend
pip install -r requirements.txt
python main.py

# Запуск evals
cd studyflow/evals
python run_evals.py

# Просмотр трейсов
# Откройте http://localhost:3000 → Traces
```

---

> **Совет**: Для ускорения инференса локальных моделей запустите Ollama с поддержкой GPU (CUDA). На CPU `qwen2.5:7b` может отвечать до 90 секунд на сложные запросы.

---

*StudyFlow — учебный проект по дисциплине «Разработка интеллектуальных агентных систем». Все модели, кроме Tutor, работают локально без интернета.*