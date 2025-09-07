#!/bin/bash

# Start dbus first (required for Avahi)
echo "Starting dbus..."
service dbus start
sleep 2

# Create necessary directories and fix permissions
mkdir -p /var/run/avahi-daemon
mkdir -p /var/lib/avahi-autoipd

# Try simple Avahi start without configuration override
echo "Starting Avahi daemon..."
/usr/sbin/avahi-daemon --no-rlimits &
AVAHI_PID=$!
sleep 3

# Check if Avahi is running
if kill -0 $AVAHI_PID 2>/dev/null; then
    echo "Avahi daemon started successfully"
else
    echo "Avahi daemon failed to start, continuing without it..."
    echo "Shairport-sync will try to use built-in mDNS"
fi

# Create named pipes
mkfifo /tmp/shairport-sync-audio 2>/dev/null || true
mkfifo /tmp/shairport-sync-metadata 2>/dev/null || true

# Start nqptp service (required for AirPlay 2)
echo "Starting nqptp service..."
nqptp &
NQPTP_PID=$!
sleep 2

# Check if nqptp is running
if kill -0 $NQPTP_PID 2>/dev/null; then
    echo "nqptp started successfully"
else
    echo "nqptp failed to start"
fi

# Start shairport-sync in foreground mode (but run in background)
echo "Starting shairport-sync..."
shairport-sync -c /etc/shairport-sync.conf -v &
SHAIRPORT_PID=$!

# Wait a moment for shairport-sync to initialize
sleep 5

# Check if shairport-sync is running
if kill -0 $SHAIRPORT_PID 2>/dev/null; then
    echo "shairport-sync started successfully"
    
    # Try to see if our service is being advertised
    echo "Checking if our service is advertised..."
    timeout 5 avahi-browse _raop._tcp -t 2>/dev/null | head -10 || echo "Could not browse _raop._tcp services"
    
    # Check what shairport-sync is doing
    echo "Shairport-sync process info:"
    ps aux | grep shairport-sync | grep -v grep
else
    echo "shairport-sync failed to start"
    echo "Configuration file contents:"
    cat /etc/shairport-sync.conf
    exit 1
fi

# Start the Discord bot
echo "Starting Discord bot..."
python3 main.py