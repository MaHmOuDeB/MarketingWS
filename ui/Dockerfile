FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY streamlit_app.py .
COPY .streamlit ./.streamlit

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8501
CMD ["sh", "-c", "streamlit run streamlit_app.py --server.port=${PORT} --server.address=0.0.0.0 --server.headless=true"]
