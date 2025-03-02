FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*


# Copy the wheel file and requirements first for better caching
COPY library/ ./library/
COPY requirements.txt .

# Install the custom multi_agent_orchestrator package from wheel file
RUN pip install --no-cache-dir ./library/multi_agent_orchestrator-0.1.9-py3-none-any.whl

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["chainlit", "run", "main_rx_system.py", "--host", "0.0.0.0", "--port", "8000"]