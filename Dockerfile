FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libasound2t64 libxshmfence1 libxfixes3 libx11-xcb1 libxcb1 libx11-6 libxext6 \
    libpangocairo-1.0-0 libcairo2 libpango-1.0-0 libdbus-1-3 libatspi2.0-0 libwayland-client0 \
    libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info fonts-liberation fontconfig \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && playwright install chromium

COPY . .
RUN mkdir -p storage/pdfs

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
