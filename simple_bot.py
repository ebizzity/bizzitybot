# Alternative simple bot for testing
import discord
from discord.ext import commands
import asyncio
import os

# Load environment variables
import load_env

# Simple configuration
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
PIPE_PATH = '/tmp/shairport-sync-audio'

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!test_', intents=intents)

@bot.command(name='join')
async def test_join(ctx):
    """Simple join command for testing"""
    try:
        if not ctx.author.voice:
            await ctx.send("You need to be in a voice channel first!")
            return

        channel = ctx.author.voice.channel
        voice_client = await channel.connect()
        
        # Very simple FFmpeg options
        ffmpeg_options = {
            'before_options': '-re -f s16le -ar 44100 -ac 2',
            'options': '-vn -ar 48000 -ac 2 -b:a 128k -f opus'
        }

        # Create simple audio source
        audio_source = discord.FFmpegOpusAudio(PIPE_PATH, **ffmpeg_options)
        
        # Play audio with simple callback
        voice_client.play(audio_source, after=lambda e: print(f'Simple bot audio error: {e}') if e else print('Simple bot audio finished'))
        
        await ctx.send(f"Simple bot joined {channel.name}!")
        
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

@bot.command(name='leave')
async def test_leave(ctx):
    """Simple leave command"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Simple bot left the channel!")
    else:
        await ctx.send("Not in a voice channel!")

@bot.command(name='status')
async def test_status(ctx):
    """Simple status command"""
    if ctx.voice_client:
        await ctx.send(f"Connected: {ctx.voice_client.is_connected()}, Playing: {ctx.voice_client.is_playing()}")
    else:
        await ctx.send("Not connected")

@bot.event
async def on_ready():
    print(f'Simple test bot {bot.user} is ready!')

if __name__ == "__main__":
    asyncio.run(bot.start(TOKEN))