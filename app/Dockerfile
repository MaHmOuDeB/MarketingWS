# Stage 1: Install dependencies
FROM python:3.9-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Copy app code and only the installed packages
FROM python:3.9-slim

WORKDIR /app
# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy your application code
COPY app.py .

# Expose the Flask/Cloud Run port
EXPOSE 8080

# Run the API
CMD ["python", "app.py"]
