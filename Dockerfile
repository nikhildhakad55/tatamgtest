# Use Python 3.11 slim debian image
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Install system dependencies (git, curl, unzip, gnupg)
RUN apt-get update && apt-get install -y \
    git \
    curl \
    unzip \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Terraform CLI binary (v1.5.7)
RUN curl -LO https://releases.hashicorp.com/terraform/1.5.7/terraform_1.5.7_linux_amd64.zip \
    && unzip terraform_1.5.7_linux_amd64.zip \
    && mv terraform /usr/local/bin/ \
    && rm terraform_1.5.7_linux_amd64.zip

# Install Infracost CLI
RUN curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh

# Copy and install python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy all application code
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI app with Uvicorn bound to 0.0.0.0
CMD ["uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]
