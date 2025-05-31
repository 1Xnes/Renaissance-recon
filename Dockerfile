FROM python:3.9-slim

# Install ffuf
RUN apt-get update && apt-get install -y wget && \
    wget https://github.com/ffuf/ffuf/releases/download/v2.1.0/ffuf_2.1.0_linux_amd64.tar.gz -O ffuf.tar.gz && \
    tar -zxvf ffuf.tar.gz && \
    mv ffuf /usr/local/bin/ && \
    rm ffuf.tar.gz && \
    apt-get remove -y wget && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# Create output directory if it doesn't exist
RUN mkdir -p /app/output

# Set environment variable for tools directory (though Sublist3r and SubDomainizer are now relative to app.py)
# ENV TOOLS_DIR=/app/tools

CMD ["python", "app.py"] 