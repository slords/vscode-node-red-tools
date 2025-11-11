
FROM python:3.11-slim

# Install Node.js, npm, and Prettier for plugin support
RUN apt-get update \
	&& apt-get install -y nodejs npm \
	&& npm install -g prettier \
	&& rm -rf /var/lib/apt/lists/*

# Install app code and dependencies in /app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app

# Set working directory for user/project files
WORKDIR /data

# Entrypoint runs the tool from /app, with /data as cwd
ENTRYPOINT ["python3", "/app/vscode-node-red-tools.py"]
