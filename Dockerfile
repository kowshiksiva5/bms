
FROM python:3.11-slim

# Install Chrome and runtime dependencies
RUN apt-get update && apt-get install -y \
    wget gnupg ca-certificates \    fonts-liberation \    libasound2 libatk-bridge2.0-0 libatk1.0-0 \    libc6 libcairo2 libcups2 libdbus-1-3 libexpat1 \    libfontconfig1 libgcc1 libgdk-pixbuf2.0-0 \    libglib2.0-0 libgtk-3-0 libnspr4 libnss3 libpango-1.0-0 \    libpangocairo-1.0-0 libstdc++6 libx11-6 libx11-xcb1 \    libxcb1 libxcomposite1 libxcursor1 libxdamage1 libxext6 \    libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 \    libxtst6 && rm -rf /var/lib/apt/lists/*

RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-linux-signing-keyring.gpg && \    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \    apt-get update && apt-get install -y google-chrome-stable && rm -rf /var/lib/apt/lists/*

ENV CHROME_BINARY=/usr/bin/google-chrome

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "-m", "main"]
