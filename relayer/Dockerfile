FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
WORKDIR /app/relayer
USER 1000:1000
CMD ["uvicorn","service:app","--host","0.0.0.0","--port","8787","--workers","1","--proxy-headers","--forwarded-allow-ips","172.18.0.0/16","--no-server-header"]
