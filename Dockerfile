FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .

RUN pip install --no-cache-dir \
    "fastapi>=0.111.0" \
    "uvicorn[standard]>=0.29.0" \
    "psycopg[binary,pool]>=3.1.0" \
    "jinja2>=3.1.0" \
    "python-multipart>=0.0.9" \
    "python-dateutil>=2.9.0"

COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
