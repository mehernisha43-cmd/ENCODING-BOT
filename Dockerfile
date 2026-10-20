
FROM python:3.10-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ="Asia/Kolkata"

# Install system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git wget ca-certificates \
    mediainfo gcc libsm6 libxext6 libfontconfig1 libxrender1 libgl1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN chmod +x extract run.sh

# Install Python dependencies
RUN python3 -m pip install --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Run the bot
CMD ["python", "-m", "VideoEncoder"]
