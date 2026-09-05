FROM hyperledger/fabric-tools:2.5.16 AS fabric-tools

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=fabric-tools /usr/local/bin/peer /usr/local/bin/peer
COPY --from=fabric-tools /etc/hyperledger/fabric /etc/hyperledger/fabric
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
