FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY service/requirements.txt /app/service/requirements.txt
RUN pip install --no-cache-dir -r /app/service/requirements.txt
COPY service /app/service
COPY research /app/research
WORKDIR /app/service
EXPOSE 8080
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8080","--proxy-headers"]
