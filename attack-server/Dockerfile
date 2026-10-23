FROM python:3.11-slim

WORKDIR /app

# Install g++ for compiling C++ binary
RUN apt-get update && apt-get install -y g++ && rm -rf /var/lib/apt/lists/*

# Copy source
COPY flooder.cpp .
COPY server.py .
COPY requirements.txt .

# Compile C++ binary
RUN g++ -O2 -o flooder flooder.cpp -lpthread && chmod +x flooder

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

CMD ["python3", "server.py"]
