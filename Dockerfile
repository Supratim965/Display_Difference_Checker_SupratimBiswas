# Use the official Playwright Docker image which comes with all OS dependencies pre-installed!
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Start the application using Gunicorn, binding to the port Render provides
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} app:app"]
