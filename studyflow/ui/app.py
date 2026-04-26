"""
StudyFlow — Streamlit UI
"""
import os
import httpx
import streamlit as st

BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="StudyFlow", page_icon="📚", layout="wide")
st.title("📚 StudyFlow — AI планировщик обучения")

# ── Сайдбар ──────────────────────────────────────────────────
with st.sidebar:
    st.header("Настройки")
    session_id = st.text_input("Session ID", value="user1")

    st.divider()
    st.subheader("📎 Загрузить материалы в память")
    st.caption("Загруженные файлы сохраняются в ChromaDB и используются при следующих вопросах через RAG-поиск. Например: загрузи конспект по Python → спроси 'что в моих материалах про функции?'")

    uploaded = st.file_uploader("PDF или TXT", type=["pdf", "txt"])
    if uploaded and st.button("Загрузить в память"):
        with st.spinner("Загружаю..."):
            try:
                resp = httpx.post(
                    f"{BACKEND}/upload",
                    params={"session_id": session_id},
                    files={"file": (uploaded.name, uploaded.read(), uploaded.type)},
                    timeout=60,
                )
                data = resp.json()
                st.success(f"Загружено {data.get('chunks_saved', 0)} чанков из {uploaded.name}")
                st.info("Теперь можешь спросить: 'что в моих материалах про ...'")
            except Exception as e:
                st.error(f"Ошибка: {e}")

    st.divider()
    if st.button("🔍 Проверить статус"):
        try:
            h = httpx.get(f"{BACKEND}/health", timeout=5).json()
            for k, v in h.items():
                icon = "🟢" if v == "ok" else "🔴"
                st.write(f"{icon} {k}: {v}")
        except Exception as e:
            st.error(f"Backend недоступен: {e}")

# ── Быстрые примеры — вставляют в поле ввода, не отправляют ──
st.subheader("Быстрые примеры")
st.caption("Нажми чтобы вставить шаблон в поле ввода")

EXAMPLES = [
    ("📅 План дня",        "Python дедлайн завтра, история через неделю"),
    ("📖 Объяснение",      "Объясни что такое JOIN в SQL простыми словами"),
    ("⚡ Микрозадача",     "Застрял на алгоритмах, дай микрозадачу на 10 минут"),
    ("🔗 Из материалов",   "Что в моих материалах про функции Python?"),
    ("📝 Оба агента",      "Python завтра и объясни что такое список"),
]

cols = st.columns(len(EXAMPLES))
for col, (label, text) in zip(cols, EXAMPLES):
    if col.button(label, use_container_width=True):
        st.session_state["prefill"] = text

# ── Чат ──────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("meta"):
            m = msg["meta"]
            st.caption(f"route: {m.get('route')} | score: {m.get('score', 0):.2f} | {m.get('latency', '')}")

# Вставляем prefill в поле — НЕ отправляем автоматически
prefill = st.session_state.get("prefill", "")
if prefill:
    edited = st.text_area("Редактируй и отправь:", value=prefill, height=80)
    if st.button("Отправить", type="primary"):
        st.session_state.pop("prefill", None)
        user_input = edited
    else:
        user_input = None
else:
    user_input = st.chat_input(placeholder="Напиши запрос...", key="chat_input")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Думаю..."):
            try:
                resp = httpx.post(
                    f"{BACKEND}/chat",
                    json={"message": user_input, "session_id": session_id},
                    timeout=180,
                )
                data   = resp.json()
                answer = data.get("answer", "Ошибка")
                score  = data.get("quality_score", 0)
                route  = data.get("route", "?")
                lat    = data.get("latency_seconds", 0)

                # Очищаем артефакты — убираем если промпт попал в ответ
                PROMPT_ARTIFACTS = [
                    "Формат для каждой темы (срочное первым):",
                    "Только план, без вступлений и итогов:",
                    "Срочное первым. Только план:",
                ]
                for artifact in PROMPT_ARTIFACTS:
                    if artifact in answer:
                        answer = answer[:answer.index(artifact)].strip()

                st.markdown(answer)
                st.caption(f"route: {route} | quality: {score:.2f} | {lat:.1f}s")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "meta": {"route": route, "score": score, "latency": f"{lat:.1f}s"},
                })
            except httpx.TimeoutException:
    # Модель ответила но Streamlit не дождался — спрашиваем напрямую
                try:
                    resp2 = httpx.post(
                        f"{BACKEND}/chat",
                        json={"message": user_input, "session_id": session_id},
                        timeout=300,  # даём 5 минут
                    )
                    data = resp2.json()
                    answer = data.get("answer", "Нет ответа")
                    st.markdown(answer)
                    st.caption(f"route: {data.get('route')} | score: {data.get('quality_score', 0):.2f}")
                    st.session_state.messages.append({
                        "role":  "assistant", "content": answer,
                        "meta": {"route": data.get("route"), "score": data.get("quality_score", 0), "latency": ""},
                    })
                except Exception:
                    st.warning("Модель всё ещё думает. Подожди 30 секунд и обнови страницу.")
            except Exception as e:
                st.error(f"Ошибка: {e}")