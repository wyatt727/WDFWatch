FROM node:20-slim as node-base

# Install gemini-cli globally (provides 'gemini' command)
RUN npm install -g @google/gemini-cli

# Install TypeScript and build tools
COPY package.json tsconfig.json ./
RUN npm install
COPY scripts/*.ts ./scripts/
RUN npm run build

FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy Node.js binaries and modules from node-base
COPY --from=node-base /usr/local/bin/node /usr/local/bin/
COPY --from=node-base /usr/local/bin/npm /usr/local/bin/
COPY --from=node-base /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=node-base /dist/scripts/ ./scripts/

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    git \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Copy poetry configuration
COPY pyproject.toml ./
COPY poetry.lock ./

# Install poetry
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-dev --no-interaction --no-ansi

# Copy source code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY main.py ./

# Create necessary directories
RUN mkdir -p transcripts artefacts logs

# Make scripts executable
RUN chmod +x scripts/gemini_summarize.js main.py

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Run the pipeline
CMD ["python", "main.py"] 