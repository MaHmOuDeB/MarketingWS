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

# Cloud Run will inject PORT (8080), but we set a default for local runs
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "streamlit run streamlit_ui.py --server.port=$PORT --server.address=0.0.0.0"]
