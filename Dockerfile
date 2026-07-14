FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the simulation script
COPY gps_telemetry_simulation.py .

# Expose port 8000
EXPOSE 8000

# Run the application
CMD ["uvicorn", "gps_telemetry_simulation:app", "--host", "0.0.0.0", "--port", "8000"]
