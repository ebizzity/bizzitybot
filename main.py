import discord
from discord.ext import commands
import asyncio
import os
import json
import base64
import xml.etree.ElementTree as ET
import logging
import traceback
import threading
import time
from discord import FFmpegPCMAudio, FFmpegOpusAudio

# Set up comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/bot.log', mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
import load_env

# Bot configuration
TOKEN = os.getenv('DISCORD_BOT_TOKEN')  # Set your bot token as environment variable
PIPE_PATH = os.getenv('SHAIRPORT_PIPE_PATH', '/tmp/shairport-sync-audio')  # Use env var or default
METADATA_PIPE_PATH = '/tmp/shairport-sync-metadata'

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

class AudioBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_client = None
        self.audio_source = None
        self.current_channel = None
        self.metadata_task = None
        self.keepalive_task = None
        self.heartbeat_task = None
        self.metadata_thread = None
        self.metadata_stop_event = None
        self.current_song = {"title": None, "artist": None, "album": None}
        self.last_heartbeat = asyncio.get_event_loop().time()

    @commands.command(name='join')
    async def join_channel(self, ctx):
        """Join the voice channel and start streaming ultra-high quality audio from shairport-sync"""
        try:
            # Check if user is in a voice channel
            if not ctx.author.voice:
                await ctx.send("You need to be in a voice channel first!")
                return

            channel = ctx.author.voice.channel
            
            # Disconnect from current channel if already connected
            if self.voice_client and self.voice_client.is_connected():
                await self.voice_client.disconnect()

            # Join the voice channel
            self.voice_client = await channel.connect()
            self.current_channel = ctx.channel  # Store text channel for announcements
            await ctx.send(f"Joined {channel.name} with ultra-high quality audio!")

            # Start streaming ultra-high quality audio
            await self.start_audio_stream()
            
            # Start metadata monitoring (now with non-blocking implementation)
            await self.start_metadata_monitoring()
            
            # Start keepalive task
            await self.start_keepalive()
            
            # Start heartbeat monitoring
            await self.start_heartbeat()

        except Exception as e:
            await ctx.send(f"Error joining channel: {str(e)}")

    @commands.command(name='leave')
    async def leave_channel(self, ctx):
        """Leave the voice channel and stop streaming"""
        try:
            if self.voice_client and self.voice_client.is_connected():
                # Stop any playing audio
                if self.voice_client.is_playing():
                    self.voice_client.stop()
                
                # Stop metadata monitoring
                if self.metadata_task:
                    self.metadata_task.cancel()
                    self.metadata_task = None
                
                # Stop metadata thread
                if self.metadata_thread:
                    if self.metadata_stop_event:
                        self.metadata_stop_event.set()
                    if self.metadata_thread.is_alive():
                        self.metadata_thread.join(timeout=2)
                
                # Stop keepalive
                if self.keepalive_task:
                    self.keepalive_task.cancel()
                    self.keepalive_task = None
                
                # Stop heartbeat
                if self.heartbeat_task:
                    self.heartbeat_task.cancel()
                    self.heartbeat_task = None
                
                # Disconnect from voice channel
                await self.voice_client.disconnect()
                self.voice_client = None
                self.current_channel = None
                await ctx.send("Left the voice channel!")
            else:
                await ctx.send("I'm not in a voice channel!")

        except Exception as e:
            await ctx.send(f"Error leaving channel: {str(e)}")

    async def start_audio_stream(self):
        """Start streaming ultra-high quality audio with advanced processing"""
        try:
            logger.info("Starting audio stream...")
            if not self.voice_client:
                logger.warning("No voice client available")
                return

            # Check if audio pipe exists and has data
            if not os.path.exists(PIPE_PATH):
                logger.error(f"Audio pipe {PIPE_PATH} does not exist!")
                return

            # Simpler, more stable FFmpeg options
            ffmpeg_options = {
                'before_options': '-re -f s16le -ar 44100 -ac 2',
                'options': '-vn -ar 48000 -ac 2 -b:a 128k -f opus'
            }

            logger.info(f"Creating audio source from {PIPE_PATH}")
            # Create audio source
            audio_source = FFmpegOpusAudio(
                source=PIPE_PATH,
                **ffmpeg_options
            )

            # Start playing the audio with a callback to handle disconnections
            logger.info("Starting playback...")
            self.voice_client.play(
                audio_source, 
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self.handle_audio_finished(e), 
                    self.bot.loop
                )
            )
            logger.info(f"Audio stream started successfully from {PIPE_PATH}")

        except Exception as e:
            logger.error(f"Error starting audio stream: {str(e)}")
            logger.error(traceback.format_exc())
            if self.current_channel:
                try:
                    await self.current_channel.send(f"❌ Failed to start audio stream: {str(e)}")
                except:
                    pass

    async def handle_audio_finished(self, error):
        """Handle when audio stream finishes or errors"""
        logger.info(f"Audio finished callback triggered. Error: {error}")
        if error:
            logger.error(f'Audio stream error: {error}')
            print(f'Audio stream error: {error}')
            # Notify about the error in Discord
            if self.current_channel:
                try:
                    await self.current_channel.send(f"⚠️ Audio stream error: {str(error)}")
                except Exception as e:
                    logger.error(f"Failed to send error message: {e}")
            
            # Try to restart the audio stream after a brief delay
            await asyncio.sleep(3)
            if self.voice_client and self.voice_client.is_connected():
                logger.info("Attempting to restart audio stream after error...")
                print("Attempting to restart audio stream...")
                try:
                    await self.start_audio_stream()
                    if self.current_channel:
                        try:
                            await self.current_channel.send("✅ Audio stream restarted automatically")
                        except:
                            pass
                except Exception as e:
                    logger.error(f"Failed to restart audio stream: {e}")
                    print(f"Failed to restart audio stream: {e}")
                    if self.current_channel:
                        try:
                            await self.current_channel.send("❌ Auto-restart failed. Use `!restart` or `!reconnect`")
                        except:
                            pass
        else:
            logger.info("Audio stream finished normally")
            print("Audio stream finished normally")

    async def start_metadata_monitoring(self):
        """Start monitoring metadata from shairport-sync using a background thread"""
        # Stop any existing monitoring
        if self.metadata_thread:
            if self.metadata_stop_event:
                self.metadata_stop_event.set()
            if self.metadata_thread.is_alive():
                self.metadata_thread.join(timeout=2)
        
        # Create new thread with stop event
        self.metadata_stop_event = threading.Event()
        self.metadata_thread = threading.Thread(
            target=self.metadata_thread_worker,
            daemon=True
        )
        self.metadata_thread.start()
        print("Started metadata monitoring thread")

    def metadata_thread_worker(self):
        """Background thread worker for metadata monitoring"""
        try:
            print("Metadata thread started")
            xml_buffer = ""
            
            while not self.metadata_stop_event.is_set():
                try:
                    # Check if metadata pipe exists
                    if not os.path.exists(METADATA_PIPE_PATH):
                        print(f"Metadata pipe {METADATA_PIPE_PATH} does not exist, waiting...")
                        time.sleep(5)
                        continue
                    
                    print(f"Opening metadata pipe: {METADATA_PIPE_PATH}")
                    
                    # Open the pipe for reading
                    with open(METADATA_PIPE_PATH, 'r') as pipe:
                        print("Metadata pipe opened, waiting for data...")
                        
                        while not self.metadata_stop_event.is_set():
                            try:
                                line = pipe.readline()
                                if not line:
                                    time.sleep(0.1)
                                    continue
                                    
                                line = line.strip()
                                if not line:
                                    continue
                                
                                xml_buffer += line
                                print(f"Received metadata line: {line}")
                                
                                # Check if we have a complete XML item
                                if line.endswith('</item>'):
                                    try:
                                        # Schedule the processing in the async event loop
                                        asyncio.run_coroutine_threadsafe(
                                            self.process_xml_metadata(xml_buffer),
                                            self.bot.loop
                                        )
                                    except Exception as e:
                                        print(f"Error processing XML metadata: {e}")
                                    finally:
                                        xml_buffer = ""
                                        
                            except Exception as e:
                                print(f"Error reading from pipe: {e}")
                                break
                                
                except FileNotFoundError:
                    print("Metadata pipe not found, waiting...")
                    time.sleep(5)
                    continue
                except Exception as e:
                    print(f"Error in metadata thread: {e}")
                    time.sleep(5)
                    continue
                    
        except Exception as e:
            print(f"Metadata thread exception: {e}")
        finally:
            print("Metadata thread stopped")

    async def monitor_metadata(self):
        """Monitor the metadata pipe for song information"""
        try:
            print("Starting metadata monitoring...")
            xml_buffer = ""
            
            while True:
                try:
                    # Check if metadata pipe exists
                    if not os.path.exists(METADATA_PIPE_PATH):
                        print(f"Metadata pipe {METADATA_PIPE_PATH} does not exist, waiting...")
                        await asyncio.sleep(5)
                        continue
                    
                    print(f"Opening metadata pipe: {METADATA_PIPE_PATH}")
                    
                    # Use a simpler approach - read file in chunks with timeout
                    while True:
                        try:
                            # Read the file in a non-blocking way using asyncio
                            proc = await asyncio.create_subprocess_shell(
                                f'timeout 1 cat {METADATA_PIPE_PATH}',
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.DEVNULL
                            )
                            
                            stdout, _ = await proc.wait()
                            
                            if proc.stdout:
                                data = await proc.stdout.read()
                                if data:
                                    lines = data.decode('utf-8', errors='ignore').strip().split('\n')
                                    for line in lines:
                                        if not line.strip():
                                            continue
                                            
                                        xml_buffer += line.strip()
                                        print(f"Received metadata line: {line.strip()}")
                                        
                                        # Check if we have a complete XML item
                                        if line.strip().endswith('</item>'):
                                            try:
                                                await self.process_xml_metadata(xml_buffer)
                                            except Exception as e:
                                                print(f"Error processing XML metadata: {e}")
                                            finally:
                                                xml_buffer = ""
                            
                            await asyncio.sleep(0.1)  # Short delay between reads
                            
                        except asyncio.TimeoutError:
                            await asyncio.sleep(1)  # Wait a bit if no data
                        except Exception as e:
                            print(f"Error in metadata read loop: {e}")
                            await asyncio.sleep(2)
                            break
                    
                except FileNotFoundError:
                    print("Metadata pipe not found, waiting...")
                    await asyncio.sleep(5)
                    continue
                except Exception as e:
                    print(f"Error reading metadata pipe: {e}")
                    await asyncio.sleep(5)
                    continue
                    
        except asyncio.CancelledError:
            print("Metadata monitoring cancelled")

    async def process_xml_metadata(self, xml_data):
        """Process XML metadata and extract song information"""
        try:
            # Parse XML
            root = ET.fromstring(xml_data)
            
            # Extract metadata type and code
            metadata_type = root.find('type')
            metadata_code = root.find('code')
            data_element = root.find('data')
            
            if metadata_type is None or metadata_code is None or data_element is None:
                return
            
            # Convert hex codes to readable strings
            type_hex = metadata_type.text
            code_hex = metadata_code.text
            
            # Convert hex to ASCII
            type_str = bytes.fromhex(type_hex).decode('ascii', errors='ignore')
            code_str = bytes.fromhex(code_hex).decode('ascii', errors='ignore')
            
            # Only process core metadata
            if type_str != 'core':
                return
            
            # Decode base64 data
            if data_element.get('encoding') == 'base64':
                decoded_data = base64.b64decode(data_element.text).decode('utf-8', errors='ignore')
            else:
                decoded_data = data_element.text or ''
            
            print(f"Metadata: type={type_str}, code={code_str}, data={decoded_data}")
            
            # Track different metadata types
            song_changed = False
            
            if code_str == 'minm':  # Song title
                if self.current_song['title'] != decoded_data:
                    self.current_song['title'] = decoded_data
                    song_changed = True
                    print(f"Song title: {decoded_data}")
            elif code_str == 'asar':  # Artist
                if self.current_song['artist'] != decoded_data:
                    self.current_song['artist'] = decoded_data
                    song_changed = True
                    print(f"Artist: {decoded_data}")
            elif code_str == 'asal':  # Album
                if self.current_song['album'] != decoded_data:
                    self.current_song['album'] = decoded_data
                    song_changed = True
                    print(f"Album: {decoded_data}")

            # Announce new song if we have title and artist
            if song_changed and self.current_song['title'] and self.current_song['artist']:
                print("Song changed! Announcing...")
                await self.announce_song()

        except Exception as e:
            print(f"Error processing XML metadata: {e}")

    async def start_keepalive(self):
        """Start keepalive task to monitor connection health"""
        if self.keepalive_task:
            self.keepalive_task.cancel()
        
        self.keepalive_task = asyncio.create_task(self.keepalive_monitor())

    async def keepalive_monitor(self):
        """Monitor connection and restart if needed"""
        try:
            while True:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                if not self.voice_client or not self.voice_client.is_connected():
                    print("Voice client disconnected, stopping keepalive")
                    break
                
                # Check if audio is playing
                if not self.voice_client.is_playing():
                    print("Audio not playing, attempting restart...")
                    try:
                        await self.start_audio_stream()
                        print("Audio stream restarted by keepalive")
                    except Exception as e:
                        print(f"Keepalive restart failed: {e}")
                        if self.current_channel:
                            try:
                                await self.current_channel.send("🔄 Connection lost. Use `!reconnect` to restore audio.")
                            except:
                                pass
                        break
                
        except asyncio.CancelledError:
            print("Keepalive monitoring cancelled")

    async def start_heartbeat(self):
        """Start heartbeat monitoring to detect bot freezes"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        
        self.heartbeat_task = asyncio.create_task(self.heartbeat_monitor())

    async def heartbeat_monitor(self):
        """Send heartbeat messages to detect if bot is frozen"""
        try:
            while True:
                await asyncio.sleep(60)  # Heartbeat every minute
                current_time = asyncio.get_event_loop().time()
                self.last_heartbeat = current_time
                logger.info(f"Heartbeat: Bot is alive at {current_time}")
                print(f"Heartbeat: Bot is alive at {current_time}")
                
                # Also check voice client status
                if self.voice_client:
                    logger.info(f"Voice status: connected={self.voice_client.is_connected()}, playing={self.voice_client.is_playing()}")
                    print(f"Voice status: connected={self.voice_client.is_connected()}, playing={self.voice_client.is_playing()}")
                
        except asyncio.CancelledError:
            print("Heartbeat monitoring cancelled")
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            print(f"Heartbeat error: {e}")

    async def process_metadata(self, data):
        """Legacy JSON metadata processor - kept for compatibility"""
        # This method is now unused but kept for compatibility
        pass

    async def announce_song(self):
        """Announce the current song in the text channel"""
        try:
            if not self.current_channel:
                return

            title = self.current_song['title'] or 'Unknown Title'
            artist = self.current_song['artist'] or 'Unknown Artist'
            album = self.current_song['album'] or 'Unknown Album'

            # Create a rich embed for the song announcement
            embed = discord.Embed(
                title="🎵 Now Playing",
                color=0x1DB954  # Spotify green
            )
            embed.add_field(name="Track", value=title, inline=False)
            embed.add_field(name="Artist", value=artist, inline=True)
            if album != 'Unknown Album':
                embed.add_field(name="Album", value=album, inline=True)
            
            embed.set_footer(text="Via AirPlay • Ultra-HQ Audio")

            await self.current_channel.send(embed=embed)

        except Exception as e:
            print(f"Error announcing song: {e}")

    @commands.command(name='song')
    async def current_song(self, ctx):
        """Display the currently playing song"""
        try:
            title = self.current_song['title'] or 'Unknown Title'
            artist = self.current_song['artist'] or 'Unknown Artist'
            album = self.current_song['album'] or 'Unknown Album'

            embed = discord.Embed(
                title="🎵 Current Song",
                color=0x1DB954
            )
            embed.add_field(name="Track", value=title, inline=False)
            embed.add_field(name="Artist", value=artist, inline=True)
            if album != 'Unknown Album':
                embed.add_field(name="Album", value=album, inline=True)
            
            embed.set_footer(text="Via AirPlay • Ultra-HQ Audio")

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"Error getting current song: {str(e)}")

    @commands.command(name='debug')
    async def debug_status(self, ctx):
        """Debug audio and metadata status"""
        try:
            debug_info = []
            
            # Check if pipes exist
            audio_exists = os.path.exists(PIPE_PATH)
            metadata_exists = os.path.exists(METADATA_PIPE_PATH)
            
            debug_info.append(f"Audio pipe exists: {audio_exists}")
            debug_info.append(f"Metadata pipe exists: {metadata_exists}")
            
            # Check voice client status
            if self.voice_client:
                debug_info.append(f"Voice client connected: {self.voice_client.is_connected()}")
                debug_info.append(f"Voice client playing: {self.voice_client.is_playing()}")
            else:
                debug_info.append("Voice client: None")
            
            # Check metadata monitoring
            metadata_running = self.metadata_task and not self.metadata_task.done()
            debug_info.append(f"Metadata monitoring running: {metadata_running}")
            
            await ctx.send("```\n" + "\n".join(debug_info) + "\n```")
            
        except Exception as e:
            await ctx.send(f"Debug error: {str(e)}")

    @commands.command(name='reconnect')
    async def reconnect(self, ctx):
        """Fully reconnect to voice channel and restart everything"""
        try:
            # Store the current voice channel
            if ctx.author.voice:
                target_channel = ctx.author.voice.channel
            elif self.voice_client and self.voice_client.channel:
                target_channel = self.voice_client.channel
            else:
                await ctx.send("No voice channel to reconnect to!")
                return

            # Clean disconnect
            if self.voice_client:
                if self.voice_client.is_playing():
                    self.voice_client.stop()
                await self.voice_client.disconnect()
                self.voice_client = None

            # Stop metadata monitoring
            if self.metadata_task:
                self.metadata_task.cancel()
                self.metadata_task = None

            await asyncio.sleep(2)

            # Reconnect
            self.voice_client = await target_channel.connect()
            self.current_channel = ctx.channel
            
            # Restart everything
            await self.start_audio_stream()
            await self.start_metadata_monitoring()
            
            await ctx.send(f"Reconnected to {target_channel.name}!")

        except Exception as e:
            await ctx.send(f"Error reconnecting: {str(e)}")

    @commands.command(name='restart')
    async def restart_audio(self, ctx):
        """Restart the audio stream"""
        try:
            if not self.voice_client or not self.voice_client.is_connected():
                await ctx.send("Not connected to a voice channel!")
                return

            # Stop current audio if playing
            if self.voice_client.is_playing():
                self.voice_client.stop()
                await asyncio.sleep(1)

            # Restart audio stream
            await self.start_audio_stream()
            await ctx.send("Audio stream restarted!")

        except Exception as e:
            await ctx.send(f"Error restarting audio: {str(e)}")

    @commands.command(name='status')
    async def status(self, ctx):
        """Check bot status"""
        if self.voice_client and self.voice_client.is_connected():
            channel_name = self.voice_client.channel.name
            is_playing = self.voice_client.is_playing()
            monitoring = self.metadata_task and not self.metadata_task.done()
            
            status_msg = f"Connected to: {channel_name}\nPlaying audio: {is_playing}\nMetadata monitoring: {monitoring}"
            
            if any(self.current_song.values()):
                title = self.current_song['title'] or 'Unknown'
                artist = self.current_song['artist'] or 'Unknown'
                status_msg += f"\nCurrent song: {artist} - {title}"
            
            await ctx.send(status_msg)
        else:
            await ctx.send("Not connected to any voice channel")

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    logger.info(f'{bot.user} has connected to Discord!')

@bot.event
async def on_command_error(ctx, error):
    logger.error(f"Command error: {error}")
    logger.error(traceback.format_exc())
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Use `!help` to see available commands.")
    else:
        await ctx.send(f"An error occurred: {str(error)}")

@bot.event 
async def on_error(event, *args, **kwargs):
    logger.error(f"Bot error in event {event}: {args}")
    logger.error(traceback.format_exc())
    print(f"Bot error in event {event}: {args}")
    print(traceback.format_exc())

# Global exception handler
def handle_exception(loop, context):
    logger.error(f"Caught exception: {context}")
    print(f"Caught exception: {context}")
    if 'exception' in context:
        logger.error(f"Exception details: {context['exception']}")
        print(f"Exception details: {context['exception']}")

# Add the cog to the bot
async def main():
    # Set up exception handler
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)
    
    async with bot:
        await bot.add_cog(AudioBot(bot))
        await bot.start(TOKEN)

if __name__ == "__main__":
    if not TOKEN:
        print("Please set the DISCORD_BOT_TOKEN environment variable")
        exit(1)
    
    asyncio.run(main())