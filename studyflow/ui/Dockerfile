FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir streamlit==1.44.1 httpx==0.28.1
COPY . .
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]