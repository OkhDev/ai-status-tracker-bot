import discord
from discord.ext import tasks
import aiohttp
import os
from datetime import datetime
import json

# Bot configuration
CHANNEL_ID = 1329254541245550712
MESSAGE_FILE = "message_id.json"

# Initialize bot with required intents
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

# Store message ID
def save_message_id(message_id):
    with open(MESSAGE_FILE, 'w') as f:
        json.dump({'message_id': message_id}, f)

def load_message_id():
    try:
        with open(MESSAGE_FILE, 'r') as f:
            data = json.load(f)
            return data.get('message_id')
    except (FileNotFoundError, json.JSONDecodeError):
        return None

# Status check function
async def check_status():
    async with aiohttp.ClientSession() as session:
        # Check OpenAI status
        try:
            async with session.get('https://status.openai.com/api/v2/status.json') as resp:
                openai_status = 'Operational' if resp.status == 200 else 'Issues Detected'
        except:
            openai_status = 'Status Check Failed'

        # Check Anthropic status
        try:
            async with session.get('https://status.anthropic.com/api/v2/status.json') as resp:
                anthropic_status = 'Operational' if resp.status == 200 else 'Issues Detected'
        except:
            anthropic_status = 'Status Check Failed'

        return openai_status, anthropic_status

# Create embed message
def create_status_embed(openai_status, anthropic_status):
    embed = discord.Embed(
        title="AI Services Status Monitor",
        description="Current operational status of AI services",
        color=discord.Color.blue() if all(status == 'Operational' for status in [openai_status, anthropic_status]) else discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    
    # Add status fields
    embed.add_field(
        name="OpenAI Status", 
        value=f"```{openai_status}```", 
        inline=True
    )
    embed.add_field(
        name="Anthropic Status", 
        value=f"```{anthropic_status}```", 
        inline=True
    )
    
    embed.set_footer(text="Last updated")
    return embed

# Create buttons
class StatusButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
        # Add buttons
        self.add_item(discord.ui.Button(
            label="OpenAI Status",
            url="https://status.openai.com/",
            style=discord.ButtonStyle.link
        ))
        self.add_item(discord.ui.Button(
            label="Anthropic Status",
            url="https://status.anthropic.com/",
            style=discord.ButtonStyle.link
        ))

@bot.event
async def on_ready():
    print(f'Bot is ready: {bot.user}')
    status_update.start()

@tasks.loop(minutes=5)  # Update every 5 minutes
async def status_update():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print(f"Cannot find channel {CHANNEL_ID}")
        return

    # Check services status
    openai_status, anthropic_status = await check_status()
    
    # Create embed and buttons
    embed = create_status_embed(openai_status, anthropic_status)
    view = StatusButtons()
    
    # Get stored message ID
    message_id = load_message_id()
    
    try:
        if message_id:
            try:
                # Try to edit existing message
                message = await channel.fetch_message(message_id)
                await message.edit(embed=embed, view=view)
                return
            except discord.NotFound:
                # Message was deleted, create new one
                pass
        
        # Create new message if none exists or previous was deleted
        new_message = await channel.send(embed=embed, view=view)
        save_message_id(new_message.id)
        
    except Exception as e:
        print(f"Error updating status message: {e}")

# Run the bot
if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_TOKEN')) 