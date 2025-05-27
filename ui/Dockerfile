# Stage 1: Install dependencies
FROM python:3.9-slim as builder

WORKDIR /ui
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Copy code + installed packages
FROM python:3.9-slim

WORKDIR /ui
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY streamlit_ui.py .

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_ui.py", "--server.port=8501", "--server.address=0.0.0.0"]