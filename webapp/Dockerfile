FROM --platform=linux/amd64 python:3.11-slim
WORKDIR /app
COPY webapp/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV TZ=Asia/Kolkata
CMD ["uvicorn", "webapp.main:app", "--host", "0.0.0.0", "--port", "8000"]
