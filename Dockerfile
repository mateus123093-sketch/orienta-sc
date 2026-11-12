FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py motor.py ./
COPY dados ./dados
COPY static ./static

EXPOSE 7860

# Usa $PORT quando o host define (Koyeb, Render, Fly) e 7860 como padrão
# (Hugging Face Spaces).
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1"]
