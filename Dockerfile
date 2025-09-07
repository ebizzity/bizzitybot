# Use Ubuntu as base image for better package availability
FROM ubuntu:22.04

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Build tools
    build-essential \
    git \
    cmake \
    autoconf \
    libtool \
    pkg-config \
    xxd \
    vim-common \
    # Python and pip
    python3 \
    python3-pip \
    python3-dev \
    # FFmpeg
    ffmpeg \
    # Shairport-sync dependencies
    libssl-dev \
    libavahi-client-dev \
    libavahi-common-dev \
    libavutil-dev \
    libasound2-dev \
    libpopt-dev \
    libconfig-dev \
    libsoxr-dev \
    libplist-dev \
    libsodium-dev \
    libgcrypt20-dev \
    libsystemd-dev \
    libavcodec-dev \
    libavformat-dev \
    libdaemon-dev \
    uuid-dev \
    # Avahi daemon for AirPlay discovery
    avahi-daemon \
    avahi-utils \
    dbus \
    # Audio libraries
    libasound2-plugins \
    alsa-utils \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy Python requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Build shairport-sync from source with specified options
RUN git clone https://github.com/mikebrady/shairport-sync.git /tmp/shairport-sync && \
    cd /tmp/shairport-sync && \
    autoreconf -i -f && \
    ./configure \
        --with-pipe \
        --with-ssl=openssl \
        --with-avahi \
        --with-airplay-2 \
        --with-alsa \
        --with-soxr \
        --with-metadata \
        --with-libdaemon \
        --without-systemd \
        --prefix=/usr/local \
        --sysconfdir=/etc && \
    make -j$(nproc) && \
    cp shairport-sync /usr/local/bin/ && \
    chmod +x /usr/local/bin/shairport-sync && \
    ldconfig && \
    rm -rf /tmp/shairport-sync

# Build and install nqptp (required for AirPlay 2)
RUN git clone https://github.com/mikebrady/nqptp.git /tmp/nqptp && \
    cd /tmp/nqptp && \
    autoreconf -i -f && \
    ./configure \
        --prefix=/usr/local \
        --sysconfdir=/etc && \
    make -j$(nproc) && \
    make install && \
    ldconfig && \
    rm -rf /tmp/nqptp

# Copy application files
COPY . .

# Copy configuration files
COPY shairport-sync.conf /etc/shairport-sync.conf
COPY avahi-daemon.conf /app/avahi-daemon.conf
COPY start.sh /app/start.sh

# Create named pipe directory and set permissions
RUN mkdir -p /tmp && chmod 777 /tmp && chmod +x /app/start.sh

# Expose port for AirPlay
EXPOSE 5000
EXPOSE 6000-6005
EXPOSE 35000-65000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SHAIRPORT_PIPE_PATH=/tmp/shairport-sync-audio

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "python3 main.py" && pgrep -f "shairport-sync" || exit 1

# Run the startup script
CMD ["/app/start.sh"]