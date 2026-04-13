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
    st.subheader("Загрузить материалы")
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
            except Exception as e:
                st.error(f"Ошибка: {e}")

    st.divider()
    # Статус системы
    if st.button("Проверить статус"):
        try:
            h = httpx.get(f"{BACKEND}/health", timeout=5).json()
            for k, v in h.items():
                icon = "🟢" if v == "ok" else "🔴"
                st.write(f"{icon} {k}: {v}")
        except Exception as e:
            st.error(f"Backend недоступен: {e}")

# ── Примеры запросов ─────────────────────────────────────────
st.subheader("Быстрые примеры")
cols = st.columns(3)
examples = [
    "Python дедлайн завтра, история через неделю",
    "Объясни что такое JOIN в SQL",
    "Застрял на алгоритмах, дай микрозадачу",
]
for col, ex in zip(cols, examples):
    if col.button(ex[:30] + "...", use_container_width=True):
        st.session_state["prefill"] = ex

# ── Чат ──────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("meta"):
            st.caption(f"route: {msg['meta'].get('route')} | score: {msg['meta'].get('score'):.2f}")

prefill = st.session_state.pop("prefill", "")
user_input = st.chat_input("Напиши запрос...", key="chat_input") or prefill

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
                    timeout=120,
                )
                data = resp.json()
                answer = data.get("answer", "Ошибка")
                score  = data.get("quality_score", 0)
                route  = data.get("route", "?")

                st.markdown(answer)
                st.caption(f"route: {route} | quality: {score:.2f}")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "meta": {"route": route, "score": score},
                })
            except httpx.TimeoutException:
                st.error("Таймаут — модель думает слишком долго. Попробуй ещё раз.")
            except Exception as e:
                st.error(f"Ошибка: {e}")
