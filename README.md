# Discord Bot Audio Streamer

A Discord bot that streams audio from shairport-sync to Discord voice channels with ultra-high quality audio processing.

## Prerequisites

### Native Installation
1. **FFmpeg**: Install FFmpeg on your system
   - Windows: Download from https://ffmpeg.org/download.html
   - Linux: `sudo apt install ffmpeg` (Ubuntu/Debian) or `sudo yum install ffmpeg` (CentOS/RHEL)
   - macOS: `brew install ffmpeg`

2. **Python 3.8+**: Make sure you have Python 3.8 or higher installed

3. **Discord Bot Token**: Create a bot at https://discord.com/developers/applications

### Docker Installation (Recommended)
1. **Docker & Docker Compose**: Install Docker and Docker Compose
2. **Discord Bot Token**: Create a bot at https://discord.com/developers/applications

## Setup

### Docker Setup (Recommended)

1. Clone/download the project files

2. Create environment file:
   ```bash
   cp .env.example .env
   # Edit .env and add your Discord bot token
   ```

3. Build and run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

4. Check logs:
   ```bash
   docker-compose logs -f
   ```

The Docker setup automatically:
- Builds shairport-sync with all required options (--with-pipe --with-ssl=openssl --with-avahi --with-systemd --with-airplay-2)
- Installs FFmpeg and all dependencies
- Creates the audio pipe
- Starts both shairport-sync and the Discord bot

### Native Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables:
   ```bash
   # Copy the example environment file
   cp .env.example .env
   
   # Edit .env and add your bot token
   DISCORD_BOT_TOKEN=your_actual_bot_token_here
   ```

3. Install and configure shairport-sync:
   ```bash
   # Install shairport-sync with required options
   # This varies by system - see shairport-sync documentation
   
   # Configure shairport-sync to output to pipe:
   # Add this to your shairport-sync.conf
   output = {
       type = "pipe";
       name = "/tmp/shairport-sync-audio";
   };
   ```

## Usage

1. **Docker**: 
   ```bash
   docker-compose up -d
   ```

2. **Native**: 
   ```bash
   python main.py
   ```

3. In Discord, use these commands:
   - `!join` - Bot joins your current voice channel and starts streaming ultra-high quality audio
   - `!leave` - Bot leaves the voice channel
   - `!status` - Check bot connection status

## Audio Quality Features

The bot uses ultra-high quality audio processing:
- **320kbps Opus encoding** (Discord's maximum bitrate)
- **48kHz sample rate** (Discord standard)
- **Ultra-high quality resampling** with 33-bit precision and dithering
- **Audio normalization** for consistent volume levels
- **Frequency filtering** to remove subsonic and ultrasonic noise
- **Optimized for music** rather than voice

## Commands

- **!join**: Join your voice channel and start streaming with ultra-high quality audio
- **!leave**: Leave the voice channel and stop streaming  
- **!status**: Display current connection and streaming status

## Docker Commands

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Rebuild after changes
docker-compose up -d --build

# Shell into container
docker-compose exec discord-audio-bot bash
```

## Network Configuration

### For Docker
The container uses `network_mode: host` to allow AirPlay discovery. Make sure these ports are available:
- **5000**: AirPlay control
- **6000-6005**: AirPlay data
- **35000-65000**: AirPlay streaming (range may vary)

### For Native Installation
Configure your firewall to allow the same ports for AirPlay functionality.

## Troubleshooting

1. **Bot can't join voice channel**: Make sure the bot has proper permissions in your Discord server

2. **No audio in Docker**: 
   - Check logs: `docker-compose logs -f`
   - Ensure the container started properly
   - Verify your Discord bot token is correct

3. **AirPlay not discovered**: 
   - Make sure you're on the same network
   - Check that ports 5000 and 6000-6005 are open
   - For Docker, ensure `network_mode: host` is working

4. **Audio quality issues**: The bot is pre-configured for maximum quality, but you can modify the FFmpeg options in `main.py` if needed

5. **Container won't start**: 
   - Check Docker logs: `docker-compose logs`
   - Ensure your `.env` file has the correct token
   - Make sure Docker has enough resources allocated

## Notes

- The Docker setup is self-contained and handles all dependencies automatically
- Audio streams automatically when the bot joins a channel
- The bot uses AirPlay 2 compatible shairport-sync for best compatibility
- All audio processing is optimized for music streaming rather than voice