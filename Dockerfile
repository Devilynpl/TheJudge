FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt* README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir streamlit plotly && \
    pip install --no-cache-dir ".[dev]" && \
    pip install --no-cache-dir -e .

COPY artifacts/ ./artifacts/
COPY TheJudge_logo.jpg ./

EXPOSE 8504

HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8504/_stcore/health || exit 1

CMD ["streamlit", "run", "src/judgekit/dashboard.py", "--server.port=8504", "--server.address=0.0.0.0", "--server.headless=true"]
