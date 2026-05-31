FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY policy_terms.json /app/policy_terms.json
COPY test_cases.json /app/test_cases.json
COPY app ./app
COPY eval ./eval
COPY streamlit_app.py ./streamlit_app.py

# Create data directory for SQLite
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONPATH=/app
ENV POLICY_FILE_PATH=/app/policy_terms.json

# Expose ports
EXPOSE 8000 8501

# Default: run FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
