import json
import os
import logging
from datetime import datetime
import time
import sys
from pathlib import Path
import asyncio
from typing import Dict

import aiohttp
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
env_path = Path('.') / '.env'
if not env_path.exists():
    raise FileNotFoundError("No .env file found. Please create one from .env.example")
load_dotenv(env_path)

# Configuration file path
CONFIG_FILE = Path('.') / 'config.json'

# Default configuration
DEFAULT_CONFIG = {
    'channels': {},  # channel_id -> {'message_id': int, 'refresh_interval_minutes': int}
    'default_refresh_interval_minutes': 5,  # Default interval for new channels
}

def load_config():
    """Load configuration from file or create with defaults if not exists."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                loaded_config = json.load(f)
                
                # Convert string keys to integers for channel IDs
                if 'channels' in loaded_config:
                    # Handle both old and new format
                    new_channels = {}
                    for channel_id, value in loaded_config['channels'].items():
                        channel_id = int(channel_id)
                        if isinstance(value, dict):
                            # New format: already has message_id and refresh_interval
                            new_channels[channel_id] = {
                                'message_id': int(value['message_id']),
                                'refresh_interval_minutes': int(value['refresh_interval_minutes'])
                            }
                        else:
                            # Old format: just message_id
                            new_channels[channel_id] = {
                                'message_id': int(value),
                                'refresh_interval_minutes': loaded_config.get('refresh_interval_minutes', DEFAULT_CONFIG['default_refresh_interval_minutes'])
                            }
                    loaded_config['channels'] = new_channels
                else:
                    # Migrate very old config format if needed
                    if loaded_config.get('channel_id'):
                        channel_id = int(loaded_config['channel_id'])
                        message_id = int(loaded_config['message_id']) if loaded_config.get('message_id') else None
                        loaded_config = {
                            'channels': {
                                channel_id: {
                                    'message_id': message_id,
                                    'refresh_interval_minutes': loaded_config.get('refresh_interval_minutes', DEFAULT_CONFIG['default_refresh_interval_minutes'])
                                }
                            }
                        }
                
                # Ensure default refresh interval exists
                if 'default_refresh_interval_minutes' not in loaded_config:
                    loaded_config['default_refresh_interval_minutes'] = DEFAULT_CONFIG['default_refresh_interval_minutes']
                
                logging.info(f"Loaded config with {len(loaded_config.get('channels', {}))} channels")
                return loaded_config
        except (json.JSONDecodeError, ValueError) as e:
            logging.error(f"Error loading config: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        logging.info("No config file found, creating with defaults")
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG.copy()

def save_config(config):
    """Save configuration to file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        logging.info(f"Saved config with {len(config.get('channels', {}))} channels")
    except Exception as e:
        logging.error(f"Error saving config: {e}")

class ChannelTracker:
    """Manages tracking of channel update times and configuration."""
    def __init__(self):
        self.config_lock = asyncio.Lock()
        self._config = load_config()
        # Initialize last updates from config or with empty dict
        self._last_updates: Dict[int, float] = {
            int(channel_id): self._config['channels'][channel_id].get('last_update_time', 0)
            for channel_id in self._config['channels']
        }
        self._last_openai_status = None
        self._last_anthropic_status = None

    async def get_config(self):
        """Thread-safe access to configuration."""
        async with self.config_lock:
            return self._config.copy()

    async def update_config(self, new_config):
        """Thread-safe configuration update."""
        async with self.config_lock:
            # Preserve last update times when updating config
            for channel_id in new_config['channels']:
                if channel_id in self._last_updates:
                    new_config['channels'][channel_id]['last_update_time'] = self._last_updates[channel_id]
            self._config = new_config
            save_config(new_config)

    async def should_update_channel(self, channel_id: int) -> bool:
        """Thread-safe check if a channel is due for an update."""
        async with self.config_lock:
            current_time = time.time()
            last_update = self._last_updates.get(channel_id, 0)
            elapsed_minutes = (current_time - last_update) / 60
            
            # Get channel-specific refresh interval
            channel_config = self._config['channels'].get(channel_id, {})
            refresh_interval = channel_config.get('refresh_interval_minutes', 
                                                self._config['default_refresh_interval_minutes'])
            
            return elapsed_minutes >= refresh_interval

    async def mark_channel_updated(self, channel_id: int):
        """Thread-safe marking of channel update time."""
        async with self.config_lock:
            current_time = time.time()
            self._last_updates[channel_id] = current_time
            # Update the last update time in config
            if channel_id in self._config['channels']:
                self._config['channels'][channel_id]['last_update_time'] = current_time
                save_config(self._config)

    async def remove_channel(self, channel_id: int):
        """Thread-safe removal of channel from tracking."""
        async with self.config_lock:
            self._last_updates.pop(channel_id, None)
            # No need to update config as the channel will be removed from it

    async def get_channel_interval(self, channel_id: int) -> int:
        """Thread-safe access to channel's refresh interval."""
        async with self.config_lock:
            channel_config = self._config['channels'].get(channel_id, {})
            return channel_config.get('refresh_interval_minutes', 
                                    self._config['default_refresh_interval_minutes'])

    async def set_channel_interval(self, channel_id: int, minutes: int):
        """Thread-safe update of channel's refresh interval."""
        async with self.config_lock:
            if channel_id not in self._config['channels']:
                raise ValueError(f"Channel {channel_id} not found in config")
            
            self._config['channels'][channel_id]['refresh_interval_minutes'] = minutes
            # Preserve last update time when saving
            if channel_id in self._last_updates:
                self._config['channels'][channel_id]['last_update_time'] = self._last_updates[channel_id]
            save_config(self._config)
            # Force an update on next check
            self._last_updates[channel_id] = 0

    @property
    def config(self):
        """Read-only access to config for non-critical operations."""
        return self._config.copy()

    async def should_update_bot_status(self, openai_status: str, anthropic_status: str) -> bool:
        """Check if bot status should be updated based on service status changes."""
        async with self.config_lock:
            should_update = (
                self._last_openai_status != openai_status or 
                self._last_anthropic_status != anthropic_status
            )
            if should_update:
                self._last_openai_status = openai_status
                self._last_anthropic_status = anthropic_status
            return should_update

# Create global tracker instance
tracker = ChannelTracker()

# Load and validate environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', '').strip()
CLIENT_ID = os.getenv('CLIENT_ID')

if not DISCORD_TOKEN:
    logging.error("No Discord token found")

# Initialize bot with required intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents, application_id=CLIENT_ID)
bot.launch_time = time.time()  # Track when the bot started

# Track the last status message
last_status_message = None

async def retry_connect(max_retries: int = 5, initial_delay: float = 1.0) -> None:
    """Attempt to connect to Discord with exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
    
    This function handles various Discord connection exceptions and implements
    exponential backoff for retries. It will attempt to reconnect on transient
    network errors and connection issues.
    """
    # Define which exceptions should trigger a retry
    RETRY_EXCEPTIONS = (
        discord.ConnectionClosed,  # WebSocket connection closed
        discord.HTTPException,     # HTTP request failed
        discord.GatewayNotFound,  # Discord API gateway not found
        aiohttp.ClientError,      # General aiohttp client errors
        asyncio.TimeoutError,     # Connection timeout
    )
    
    for attempt in range(max_retries):
        try:
            await bot.start(DISCORD_TOKEN)
            logging.info("Successfully connected to Discord")
            return  # Successfully connected
            
        except RETRY_EXCEPTIONS as e:
            if attempt == max_retries - 1:  # Last attempt
                logging.error(f"Failed to connect after {max_retries} attempts: {type(e).__name__}: {str(e)}")
                raise  # Re-raise the last exception
            
            delay = initial_delay * (2 ** attempt)  # Exponential backoff
            logging.warning(
                f"Connection attempt {attempt + 1} failed with {type(e).__name__}: {str(e)}. "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)
            
        except discord.LoginFailure as e:
            # Don't retry on authentication failures
            logging.error(f"Authentication failed: {str(e)}")
            raise
            
        except Exception as e:
            # Log unexpected exceptions but don't retry
            logging.error(f"Unexpected error during connection: {type(e).__name__}: {str(e)}")
            raise

async def check_status() -> tuple[str, str]:
    """Check the operational status of OpenAI and Anthropic services.

    Returns:
        A tuple containing the status strings for OpenAI and Anthropic
    """
    timeout = aiohttp.ClientTimeout(total=10)  # 10 second timeout
    retry_attempts = 2
    
    async def check_service_status(session: aiohttp.ClientSession, url: str, service_name: str) -> str:
        """Check status for a single service with retries."""
        for attempt in range(retry_attempts + 1):
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        status = data.get('status', {}).get('description', '').lower()
                        
                        if status == 'all systems operational':
                            return 'Operational'
                        elif 'limited' in status:
                            return 'Limited'
                        else:
                            return 'Issues Detected'
                    elif resp.status == 429:  # Rate limit
                        logging.warning(f"{service_name} status endpoint rate limited")
                        return 'Limited'
                    elif resp.status >= 500:  # Server error
                        logging.warning(f"{service_name} status endpoint server error: {resp.status}")
                        if attempt < retry_attempts:
                            delay = 1 * (2 ** attempt)  # Exponential backoff
                            logging.warning(f"Retrying in {delay}s...")
                            await asyncio.sleep(delay)
                            continue
                        return 'Issues Detected'
                    else:
                        logging.warning(f"{service_name} status endpoint returned {resp.status}")
                        if attempt < retry_attempts:
                            delay = 1 * (2 ** attempt)  # Exponential backoff
                            logging.warning(f"Retrying in {delay}s...")
                            await asyncio.sleep(delay)
                            continue
                        return 'Issues Detected'
                        
            except asyncio.TimeoutError:
                logging.warning(f"{service_name} status check timed out")
                if attempt < retry_attempts:
                    delay = 1 * (2 ** attempt)  # Exponential backoff
                    logging.warning(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                return 'Issues Detected'
                
            except aiohttp.ClientError as e:
                logging.error(f"{service_name} status check failed: {str(e)}")
                if attempt < retry_attempts:
                    delay = 1 * (2 ** attempt)
                    logging.warning(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                return 'Issues Detected'
                
            except Exception as e:
                logging.error(f"Unexpected error checking {service_name} status: {str(e)}")
                return 'Issues Detected'
        
        # If we've exhausted all retries without success, assume there are issues
        logging.error(f"{service_name} status check failed after all retry attempts")
        return 'Issues Detected'
    
    # Fallback URLs in case the primary endpoints fail
    OPENAI_URLS = [
        'https://status.openai.com/api/v2/status.json',
        'https://status.openai.com/api/v2/components.json'  # Fallback endpoint
    ]
    
    ANTHROPIC_URLS = [
        'https://status.anthropic.com/api/v2/status.json',
        'https://status.anthropic.com/api/v2/summary.json',  # Primary fallback
        'https://status.anthropic.com/api/v2/components.json',  # Secondary fallback
        'https://status.anthropic.com/api/v2/incidents.json'  # Tertiary fallback
    ]
    
    # Create a single session for all requests
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Try OpenAI status endpoints
        openai_status = None
        for url in OPENAI_URLS:
            openai_status = await check_service_status(session, url, "OpenAI")
            if openai_status != 'Issues Detected':
                break
        
        # Try Anthropic status endpoints
        anthropic_status = None
        for url in ANTHROPIC_URLS:
            anthropic_status = await check_service_status(session, url, "Anthropic")
            if anthropic_status != 'Issues Detected':
                break
        
        # Use fallback ping check if all status endpoints fail for OpenAI
        if openai_status == 'Issues Detected':
            try:
                async with session.get('https://api.openai.com/v1/models', timeout=5) as resp:
                    if resp.status == 429:  # Rate limit
                        openai_status = 'Limited'
                    elif resp.status < 500:  # Any successful response or client error
                        openai_status = 'Operational'
                    else:  # Server error
                        openai_status = 'Issues Detected'
            except Exception as e:
                logging.error(f"OpenAI fallback check failed: {str(e)}")
                # Keep as 'Issues Detected'
        
        # For Anthropic, we'll keep the status as is since we don't have a reliable fallback endpoint
        
        return openai_status or 'Issues Detected', anthropic_status or 'Issues Detected'


def create_status_embed(openai_status: str, anthropic_status: str, refresh_interval: int) -> discord.Embed:
    """Create an embedded message with current service status.
    
    Args:
        openai_status: Current status of OpenAI services
        anthropic_status: Current status of Anthropic services
        refresh_interval: Refresh interval in minutes for this channel
    """
    # Use local time instead of UTC
    local_time = datetime.fromtimestamp(time.time())
    
    # Determine embed color based on status
    if all(status == 'Operational' for status in [openai_status, anthropic_status]):
        color = discord.Color.green()
    elif any(status == 'Limited' for status in [openai_status, anthropic_status]):
        color = discord.Color.yellow()
    else:
        color = discord.Color.red()
    
    # Format refresh interval text
    if refresh_interval == 1:
        refresh_text = "Refreshes every minute"
    else:
        refresh_text = f"Refreshes every {refresh_interval} minutes"
    
    embed = discord.Embed(
        title="📡 AI Services Status Monitor",
        description=refresh_text,
        color=color,
        timestamp=local_time
    )
    
    # Add status fields with emojis
    def get_status_emoji(status: str) -> str:
        if status == "Operational":
            return "✅"
        elif status == "Limited":
            return "🔸"
        else:
            return "❌"
    
    embed.add_field(
        name="OpenAI Status", 
        value=f"```{get_status_emoji(openai_status)} {openai_status}```", 
        inline=False  # Set to False for vertical layout
    )
    embed.add_field(
        name="Anthropic Status", 
        value=f"```{get_status_emoji(anthropic_status)} {anthropic_status}```", 
        inline=False  # Set to False for vertical layout
    )
    
    embed.set_footer(text="Last updated")
    return embed


class StatusButtons(discord.ui.View):
    """View class for status page buttons."""
    
    def __init__(self):
        """Initialize the view with status page buttons."""
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
        
        # Add guide button with red question mark
        help_button = discord.ui.Button(
            label="🔍 Guide",
            style=discord.ButtonStyle.primary,  # Blue color
            custom_id="status_help"
        )
        help_button.callback = self.help_callback
        self.add_item(help_button)
    
    async def help_callback(self, interaction: discord.Interaction):
        """Handle help button click."""
        help_embed = discord.Embed(
            title="🔍 Quick Guide",
            description="Understanding the status indicators:",
            color=discord.Color.blue()
        )
        
        help_embed.add_field(
            name="Service Status",
            value=(
                "✅ **Operational** - Everything working\n"
                "🔸 **Limited** - Some features affected\n"
                "❌ **Issues** - Problems detected"
            ),
            inline=True
        )
        
        help_embed.add_field(
            name="Bot Status",
            value=(
                "🟢 - All good\n"
                "🟡 - Minor issues\n"
                "🔴 - Major issues"
            ),
            inline=True
        )
        
        await interaction.response.send_message(embed=help_embed, ephemeral=True)


@bot.tree.command(name="refresh", description="Manually refresh the AI services status (Admin only)")
@discord.app_commands.default_permissions(administrator=True)
async def refresh(interaction: discord.Interaction):
    """Manually refresh the status of AI services. Admin only."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        await update_all_channels()
        await interaction.followup.send("✅ Status has been manually refreshed!", ephemeral=True)
    except Exception as e:
        logging.error(f"Error during manual refresh: {e}")
        await interaction.followup.send("❌ Failed to refresh status. Check logs for details.", ephemeral=True)

@bot.event
async def on_ready() -> None:
    """Handle bot ready event and start status updates."""
    logging.info(f'Bot is ready: {bot.user}')
    
    # Set initial activity
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="AI Status"),
        status=discord.Status.online
    )
    
    # Sync commands with Discord
    try:
        synced = await bot.tree.sync()
        logging.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logging.error(f"Failed to sync commands: {e}")
    
    # Start the status update loop with configured interval
    if not status_update.is_running():
        # Get initial config from tracker
        config = tracker.config
        status_update.change_interval(minutes=1)  # Always check every minute
        status_update.start()
        logging.info(f"Started status updates with {config['default_refresh_interval_minutes']} minute refresh interval")


@bot.tree.command(name="create", description="Create a status tracker in this channel (Admin only)")
@discord.app_commands.default_permissions(administrator=True)
async def create(interaction: discord.Interaction, interval: int = 5):
    """Create a status tracker in the current channel. Admin only."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        channel_id = interaction.channel_id
        
        # Validate interval
        if interval < 1:
            await interaction.followup.send("❌ Interval must be at least 1 minute!", ephemeral=True)
            return
        
        # Get current config
        config = await tracker.get_config()
        
        # Check if channel already has a tracker
        if channel_id in config['channels']:
            await interaction.followup.send("❌ This channel already has a status tracker!", ephemeral=True)
            return
        
        # Create initial status message
        openai_status, anthropic_status = await check_status()
        
        # Create embed and view
        embed = create_status_embed(openai_status, anthropic_status, interval)
        view = StatusButtons()
        
        # Send message and store its ID
        message = await interaction.channel.send(embed=embed, view=view)
        
        # Update config with new channel
        config['channels'][channel_id] = {
            'message_id': message.id,
            'refresh_interval_minutes': interval
        }
        await tracker.update_config(config)
        
        # Mark channel as just updated
        await tracker.mark_channel_updated(channel_id)
        
        await interaction.followup.send(
            f"✅ Status tracker created successfully!\n"
            f"• Channel: <#{channel_id}>\n"
            f"• Refresh Interval: {interval} minutes\n"
            f"You can change this channel's refresh interval using `/interval <minutes>`",
            ephemeral=True
        )
        
    except Exception as e:
        logging.error(f"Error creating status tracker: {e}")
        await interaction.followup.send("❌ Failed to create status tracker. Check logs for details.", ephemeral=True)

@bot.tree.command(name="interval", description="Set the refresh interval for this channel's status tracker (Admin only)")
@discord.app_commands.default_permissions(administrator=True)
async def set_interval(interaction: discord.Interaction, minutes: int):
    """Set the refresh interval for this channel's status tracker. Admin only."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        channel_id = interaction.channel_id
        
        # Validate input
        if minutes < 1:
            await interaction.followup.send("❌ Interval must be at least 1 minute!", ephemeral=True)
            return
        
        # Update channel's interval
        try:
            await tracker.set_channel_interval(channel_id, minutes)
            await interaction.followup.send(
                f"✅ Refresh interval updated to {minutes} minutes for this channel!", 
                ephemeral=True
            )
            logging.info(f"Refresh interval updated to {minutes} minutes for channel {channel_id}")
        except ValueError:
            await interaction.followup.send(
                "❌ No status tracker found in this channel! Create one first with `/create`", 
                ephemeral=True
            )
        
    except Exception as e:
        logging.error(f"Error updating refresh interval: {e}")
        await interaction.followup.send("❌ Failed to update refresh interval. Check logs for details.", ephemeral=True)

@tasks.loop(minutes=1)  # Check every minute, but only update channels when needed
async def status_update() -> None:
    """Update status message based on refresh interval from config."""
    await update_all_channels()

async def update_all_channels() -> None:
    """Update all channels that need refreshing. Can be called manually or by the task loop."""
    config = await tracker.get_config()
    
    # Check services status
    openai_status, anthropic_status = await check_status()
    
    # Track channels per server
    servers_with_trackers = {}
    for channel_id_str in config['channels'].keys():
        try:
            # Validate channel ID format
            try:
                channel_id = int(channel_id_str)
            except ValueError:
                logging.error(f"Invalid channel ID format in config: {channel_id_str}")
                continue

            # First try to get the channel from cache
            channel = bot.get_channel(channel_id)
            
            # If not in cache, try to fetch it with proper error handling
            if not channel:
                try:
                    channel = await bot.fetch_channel(channel_id)
                except discord.Forbidden:
                    logging.warning(f"Bot lacks permission to access channel {channel_id}")
                    continue
                except discord.NotFound:
                    logging.warning(f"Channel {channel_id} not found")
                    continue
                except discord.HTTPException as e:
                    logging.error(f"HTTP error fetching channel {channel_id}: {e}")
                    continue
            
            # Verify bot has required permissions in the channel
            if channel and channel.guild:
                permissions = channel.permissions_for(channel.guild.me)
                if not (permissions.view_channel and permissions.send_messages and permissions.embed_links):
                    logging.warning(f"Bot lacks required permissions in channel {channel_id}")
                    continue
                    
                # Add to server tracking if all checks pass
                if channel.guild.id not in servers_with_trackers:
                    servers_with_trackers[channel.guild.id] = set()
                servers_with_trackers[channel.guild.id].add(channel_id)
                
        except Exception as e:
            logging.error(f"Error processing channel {channel_id_str}: {e}")
            continue
    
    # Only update bot status if service status has changed AND we have servers with single channels
    if await tracker.should_update_bot_status(openai_status, anthropic_status):
        # Only change presence if we have any tracked channels
        should_change_presence = bool(servers_with_trackers)
        
        if should_change_presence:
            # Determine status based on service health
            if all(status == 'Operational' for status in [openai_status, anthropic_status]):
                new_status = discord.Status.online
            elif any(status == 'Limited' for status in [openai_status, anthropic_status]):
                new_status = discord.Status.idle
            else:  # Issues Detected or Status Check Failed
                new_status = discord.Status.dnd
            
            # Update presence with appropriate status while maintaining activity
            await bot.change_presence(
                activity=discord.Activity(type=discord.ActivityType.watching, name="AI Status"),
                status=new_status
            )
    
    # First pass: identify invalid channels
    channels_to_remove = set()
    for channel_id in list(config['channels'].keys()):
        try:
            channel = bot.get_channel(channel_id)
            if not channel:
                try:
                    channel = await bot.fetch_channel(channel_id)
                except (discord.NotFound, discord.Forbidden):
                    logging.warning(f"Channel {channel_id} is no longer accessible, removing from config")
                    channels_to_remove.add(channel_id)
                except Exception as e:
                    logging.error(f"Unexpected error fetching channel {channel_id}: {e}")
                    # Don't remove channel for temporary errors
                    continue
        except Exception as e:
            logging.error(f"Error checking channel {channel_id}: {e}")
            if isinstance(e, (discord.Forbidden, discord.NotFound)):
                channels_to_remove.add(channel_id)
    
    # Remove invalid channels all at once
    if channels_to_remove:
        new_config = await tracker.get_config()  # Get fresh config
        for channel_id in channels_to_remove:
            if channel_id in new_config['channels']:  # Add safety check
                new_config['channels'].pop(channel_id)
                await tracker.remove_channel(channel_id)
        await tracker.update_config(new_config)
        logging.info(f"Removed {len(channels_to_remove)} invalid channels from config: {channels_to_remove}")
        config = await tracker.get_config()  # Get updated config for channel processing
    
    # Second pass: update remaining valid channels
    for channel_id, channel_config in list(config['channels'].items()):
        try:
            channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
            if not channel:
                continue  # Skip if channel is not accessible (will be removed in next iteration)
            
            try:
                message = await channel.fetch_message(channel_config['message_id'])
                embed = create_status_embed(openai_status, anthropic_status, channel_config['refresh_interval_minutes'])
                view = StatusButtons()
                await message.edit(embed=embed, view=view)
                await tracker.mark_channel_updated(channel_id)
            except discord.NotFound:
                # Message not found, create new one
                logging.warning(f"Message {channel_config['message_id']} not found in channel {channel_id}, creating new message")
                embed = create_status_embed(openai_status, anthropic_status, channel_config['refresh_interval_minutes'])
                view = StatusButtons()
                new_message = await channel.send(embed=embed, view=view)
                
                # Update message ID in config
                new_config = await tracker.get_config()  # Get fresh config
                if channel_id in new_config['channels']:  # Check if channel still exists
                    new_config['channels'][channel_id]['message_id'] = new_message.id
                    await tracker.update_config(new_config)
                    await tracker.mark_channel_updated(channel_id)
            except discord.Forbidden:
                logging.warning(f"Bot no longer has permission to access messages in channel {channel_id}")
                # Will be removed in next iteration
                continue
            except discord.HTTPException as e:
                logging.error(f"HTTP error updating message in channel {channel_id}: {e}")
                # Don't remove channel for temporary HTTP errors
                continue
            except Exception as e:
                logging.error(f"Error updating message in channel {channel_id}: {e}")
                # Only remove channel if it's a permissions or not found error
                if isinstance(e, (discord.Forbidden, discord.NotFound)):
                    # Will be removed in next iteration
                    continue
                
        except Exception as e:
            logging.error(f"Error processing channel {channel_id}: {e}")
            # Channel errors will be handled in next iteration

@bot.tree.command(name="delete", description="Delete the status tracker from this channel (Admin only)")
@discord.app_commands.default_permissions(administrator=True)
async def delete(interaction: discord.Interaction):
    """Delete the status tracker from the current channel. Admin only."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        channel_id = interaction.channel_id
        
        # Get current config
        config = await tracker.get_config()
        
        # Check if channel has a tracker
        if channel_id not in config['channels']:
            await interaction.followup.send("❌ No status tracker found in this channel!", ephemeral=True)
            return
        
        # Get message ID before removing from config
        message_id = config['channels'][channel_id]['message_id']
        message_deleted = False
        
        # Try to delete the message if it exists
        try:
            message = await interaction.channel.fetch_message(message_id)
            await message.delete()
            message_deleted = True
        except discord.NotFound:
            # Message doesn't exist anymore, that's fine
            logging.info(f"Message {message_id} was already deleted or not found in channel {channel_id}")
            message_deleted = True
        except discord.Forbidden:
            logging.error(f"No permission to delete message {message_id} in channel {channel_id}")
        except Exception as e:
            logging.error(f"Error deleting message {message_id} in channel {channel_id}: {e}")
        
        # Remove from config regardless of message deletion status
        config['channels'].pop(channel_id)
        await tracker.update_config(config)
        
        # Remove channel from tracking
        await tracker.remove_channel(channel_id)
        
        # Prepare status message
        status = "✅ Status tracker configuration removed"
        if message_deleted:
            status += " and message deleted"
        status += "!"
        
        await interaction.followup.send(
            f"{status}\n"
            f"• Channel: <#{channel_id}>\n"
            f"• Message ID: {message_id}",
            ephemeral=True
        )
        
    except Exception as e:
        logging.error(f"Error deleting status tracker: {e}")
        await interaction.followup.send("❌ Failed to delete status tracker. Check logs for details.", ephemeral=True)

@bot.tree.command(name="list", description="List all status trackers and their settings (Admin only)")
@discord.app_commands.default_permissions(administrator=True)
async def list_trackers(interaction: discord.Interaction):
    """List all status trackers and their settings. Admin only."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Get current config
        config = await tracker.get_config()
        
        if not config['channels']:
            await interaction.followup.send("ℹ️ No status trackers are currently deployed.", ephemeral=True)
            return
        
        # Create embed for tracker list
        embed = discord.Embed(
            title="📋 Status Tracker List",
            description=f"Found {len(config['channels'])} active tracker(s)",
            color=discord.Color.blue()
        )
        
        # Add field for each tracker
        for channel_id, channel_config in config['channels'].items():
            channel = bot.get_channel(channel_id)
            channel_name = f"#{channel.name}" if channel else "Unknown Channel"
            guild_name = channel.guild.name if channel else "Unknown Server"
            
            field_value = (
                f"• Server: {guild_name}\n"
                f"• Channel: <#{channel_id}>\n"
                f"• Refresh: {channel_config['refresh_interval_minutes']} minutes\n"
                f"• Message ID: {channel_config['message_id']}"
            )
            
            embed.add_field(
                name=channel_name,
                value=field_value,
                inline=False
            )
        
        # Add default refresh interval to footer
        embed.set_footer(text=f"Default refresh interval: {config['default_refresh_interval_minutes']} minutes")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        logging.error(f"Error listing status trackers: {e}")
        await interaction.followup.send("❌ Failed to list status trackers. Check logs for details.", ephemeral=True)

@bot.tree.command(name="debug", description="Get comprehensive debug information (Admin only)")
@discord.app_commands.default_permissions(administrator=True)
async def debug(interaction: discord.Interaction):
    """Get comprehensive debug information. Admin only."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Get current config and bot info
        config = await tracker.get_config()
        bot_latency = round(bot.latency * 1000)  # Convert to milliseconds
        
        # Create debug embed
        embed = discord.Embed(
            title="🔧 Debug Information",
            description="Comprehensive status and configuration information",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Bot Status
        bot_status = (
            f"• Status: {str(bot.status).title()}\n"
            f"• Latency: {bot_latency}ms\n"
            f"• Uptime: {time.time() - bot.launch_time:.2f}s"
        )
        embed.add_field(name="Bot Status", value=f"```{bot_status}```", inline=False)
        
        # Configuration
        config_status = (
            f"• Total Trackers: {len(config['channels'])}\n"
            f"• Default Refresh: {config['default_refresh_interval_minutes']}m"
        )
        embed.add_field(name="Configuration", value=f"```{config_status}```", inline=False)
        
        # Service Status
        try:
            openai_status, anthropic_status = await check_status()
            service_status = (
                f"• OpenAI: {openai_status}\n"
                f"• Anthropic: {anthropic_status}"
            )
        except Exception as e:
            service_status = f"Error checking services: {str(e)}"
        embed.add_field(name="Service Status", value=f"```{service_status}```", inline=False)
        
        # Channel Details
        if config['channels']:
            channels_status = []
            for channel_id, channel_config in config['channels'].items():
                channel = bot.get_channel(channel_id)
                if channel:
                    try:
                        message = await channel.fetch_message(channel_config['message_id'])
                        message_status = "✓ Message Found"
                    except discord.NotFound:
                        message_status = "✗ Message Missing"
                    except discord.Forbidden:
                        message_status = "✗ No Access"
                    except Exception as e:
                        message_status = f"✗ Error: {str(e)}"
                    
                    channel_status = (
                        f"Channel: #{channel.name} ({channel_id})\n"
                        f"Server: {channel.guild.name}\n"
                        f"Refresh: {channel_config['refresh_interval_minutes']}m\n"
                        f"Message: {message_status}"
                    )
                else:
                    channel_status = f"Channel {channel_id}: Not Found"
                channels_status.append(channel_status)
            
            # Split channel status into chunks if too long
            status_chunks = [channels_status[i:i+5] for i in range(0, len(channels_status), 5)]
            for i, chunk in enumerate(status_chunks, 1):
                embed.add_field(
                    name=f"Channel Details ({i}/{len(status_chunks)})", 
                    value=f"```{chr(10).join(chunk)}```",
                    inline=False
                )
        
        # System Info
        system_info = (
            f"• Python: {sys.version.split()[0]}\n"
            f"• discord.py: {discord.__version__}\n"
            f"• OS: {sys.platform}\n"
            f"• Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        embed.add_field(name="System Information", value=f"```{system_info}```", inline=False)
        
        # Add last update times
        last_updates = []
        for channel_id in config['channels']:
            last_update = tracker._last_updates.get(channel_id, 0)
            if last_update > 0:
                time_diff = time.time() - last_update
                last_updates.append(f"<#{channel_id}>: {time_diff:.1f}s ago")
        
        if last_updates:
            embed.add_field(
                name="Last Updates",
                value="\n".join(last_updates),
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        logging.error(f"Error generating debug information: {e}")
        await interaction.followup.send(
            "❌ Failed to generate debug information. Check logs for details.", 
            ephemeral=True
        )

@bot.tree.command(
    name="default",
    description="Set the default refresh interval for new trackers (Admin only)"
)
@discord.app_commands.default_permissions(administrator=True)
async def set_default_interval(
    interaction: discord.Interaction,
    minutes: int
):
    """Set the default refresh interval for new trackers. Admin only.
    
    Args:
        minutes: The new default refresh interval in minutes (minimum 1)
    """
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Validate input
        if minutes < 1:
            await interaction.followup.send(
                "❌ Default refresh interval must be at least 1 minute!",
                ephemeral=True
            )
            return
        
        # Get current config
        config = await tracker.get_config()
        old_default = config['default_refresh_interval_minutes']
        
        # Update default refresh interval
        config['default_refresh_interval_minutes'] = minutes
        await tracker.update_config(config)
        
        # Create response embed
        embed = discord.Embed(
            title="⚙️ Default Refresh Interval Updated",
            description="The default refresh interval for new trackers has been updated.",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Changes",
            value=(
                f"• Old Default: {old_default} minutes\n"
                f"• New Default: {minutes} minutes"
            ),
            inline=False
        )
        
        # Add note about existing trackers
        if config['channels']:
            embed.add_field(
                name="Note",
                value=(
                    f"This change affects only new trackers.\n"
                    f"Existing trackers ({len(config['channels'])}) maintain their current intervals.\n"
                    f"Use `/interval` to modify existing trackers."
                ),
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        logging.info(f"Default refresh interval updated from {old_default} to {minutes} minutes")
        
    except Exception as e:
        logging.error(f"Error updating default refresh interval: {e}")
        await interaction.followup.send(
            "❌ Failed to update default refresh interval. Check logs for details.",
            ephemeral=True
        )

@bot.tree.command(
    name="sync",
    description="Force sync all trackers and verify their status (Admin only)"
)
@discord.app_commands.default_permissions(administrator=True)
async def sync_trackers(interaction: discord.Interaction):
    """Force sync all trackers and verify their status. Admin only."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Get current config
        config = await tracker.get_config()
        
        if not config['channels']:
            await interaction.followup.send("ℹ️ No status trackers to sync.", ephemeral=True)
            return
        
        # Create progress embed
        embed = discord.Embed(
            title="🔄 Syncing Status Trackers",
            description=f"Syncing {len(config['channels'])} tracker(s)...",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        progress_message = await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Track sync results
        results = {
            'success': 0,
            'recreated': 0,
            'failed': 0,
            'removed': 0,
            'issues': []
        }
        
        # Get current service status once for all updates
        try:
            openai_status, anthropic_status = await check_status()
        except Exception as e:
            logging.error(f"Error checking service status during sync: {e}")
            results['issues'].append("⚠️ Failed to check service status")
            openai_status = anthropic_status = "Status Check Failed"
        
        # Process each channel
        channels_to_remove = set()
        for channel_id, channel_config in list(config['channels'].items()):
            try:
                # Always try to fetch the channel first, regardless of shard
                try:
                    channel = await bot.fetch_channel(channel_id)
                except discord.NotFound:
                    results['issues'].append(f"❌ Channel {channel_id} not found")
                    channels_to_remove.add(channel_id)
                    results['removed'] += 1
                    continue
                except discord.Forbidden:
                    results['issues'].append(f"❌ No access to channel {channel_id}")
                    channels_to_remove.add(channel_id)
                    results['removed'] += 1
                    continue
                except discord.HTTPException as e:
                    if e.code == 50001:  # Missing Access
                        results['issues'].append(f"❌ Missing access to channel {channel_id}")
                        channels_to_remove.add(channel_id)
                        results['removed'] += 1
                        continue
                    elif e.code == 50004:  # Not in Guild
                        results['issues'].append(f"❌ Bot not in guild for channel {channel_id}")
                        channels_to_remove.add(channel_id)
                        results['removed'] += 1
                        continue
                    else:
                        results['issues'].append(f"❌ HTTP error for channel {channel_id}: {e.text}")
                        results['failed'] += 1
                        continue
                except Exception as e:
                    results['issues'].append(f"❌ Unexpected error fetching channel {channel_id}: {str(e)}")
                    results['failed'] += 1
                    continue
                
                try:
                    # Try to get existing message
                    message = await channel.fetch_message(channel_config['message_id'])
                    
                    # Update existing message
                    embed = create_status_embed(
                        openai_status,
                        anthropic_status,
                        channel_config['refresh_interval_minutes']
                    )
                    view = StatusButtons()
                    await message.edit(embed=embed, view=view)
                    results['success'] += 1
                    
                except discord.NotFound:
                    # Message not found, create new one
                    embed = create_status_embed(
                        openai_status,
                        anthropic_status,
                        channel_config['refresh_interval_minutes']
                    )
                    view = StatusButtons()
                    new_message = await channel.send(embed=embed, view=view)
                    
                    # Update config with new message ID
                    config['channels'][channel_id]['message_id'] = new_message.id
                    results['recreated'] += 1
                    results['issues'].append(f"🔄 Recreated tracker in #{channel.name}")
                    
                except discord.Forbidden:
                    results['issues'].append(f"❌ No message permissions in #{channel.name}")
                    channels_to_remove.add(channel_id)
                    results['removed'] += 1
                    
                except discord.HTTPException as e:
                    if e.code == 50001:  # Missing Access
                        results['issues'].append(f"❌ Missing message access in #{channel.name}")
                        channels_to_remove.add(channel_id)
                        results['removed'] += 1
                    else:
                        results['failed'] += 1
                        results['issues'].append(f"❌ HTTP error in #{channel.name}: {e.text}")
                    continue
                    
                except Exception as e:
                    results['failed'] += 1
                    results['issues'].append(f"❌ Error in #{channel.name}: {str(e)}")
                    continue
                
                # Mark channel as just updated if we got this far
                await tracker.mark_channel_updated(channel_id)
                
            except Exception as e:
                results['failed'] += 1
                results['issues'].append(f"❌ Unexpected error with {channel_id}: {str(e)}")
        
        # Remove invalid channels
        if channels_to_remove:
            for channel_id in channels_to_remove:
                config['channels'].pop(channel_id, None)
                await tracker.remove_channel(channel_id)
            await tracker.update_config(config)
        
        # Create final status embed
        status_embed = discord.Embed(
            title="🔄 Sync Complete",
            description=(
                f"Processed {len(config['channels']) + len(channels_to_remove)} tracker(s)\n"
                f"Completed at {datetime.now().strftime('%H:%M:%S')}"
            ),
            color=discord.Color.green() if results['failed'] == 0 else discord.Color.orange(),
            timestamp=datetime.now()
        )
        
        # Add results field
        status_embed.add_field(
            name="Results",
            value=(
                f"✅ Success: {results['success']}\n"
                f"🔄 Recreated: {results['recreated']}\n"
                f"❌ Failed: {results['failed']}\n"
                f"🗑️ Removed: {results['removed']}"
            ),
            inline=False
        )
        
        # Add issues if any
        if results['issues']:
            # Split issues into chunks if too many
            issue_chunks = [results['issues'][i:i+10] for i in range(0, len(results['issues']), 10)]
            for i, chunk in enumerate(issue_chunks, 1):
                status_embed.add_field(
                    name=f"Issues ({i}/{len(issue_chunks)})",
                    value="\n".join(chunk),
                    inline=False
                )
        
        # Update progress message with final status
        await progress_message.edit(embed=status_embed)
        
        # Log sync results
        logging.info(
            f"Sync completed - Success: {results['success']}, "
            f"Recreated: {results['recreated']}, "
            f"Failed: {results['failed']}, "
            f"Removed: {results['removed']}"
        )
        
    except Exception as e:
        logging.error(f"Error during sync operation: {e}")
        await interaction.followup.send(
            "❌ Failed to complete sync operation. Check logs for details.",
            ephemeral=True
        )

if __name__ == "__main__":
    # Validate Discord token
    if not DISCORD_TOKEN:
        raise ValueError("No Discord token found. Make sure DISCORD_TOKEN is set in your .env file")
    
    # Validate Client ID
    if not CLIENT_ID:
        raise ValueError("No Client ID found. Make sure CLIENT_ID is set in your .env file")
    
    try:
        logging.info("Starting bot...")
        asyncio.run(retry_connect())
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt. Shutting down gracefully...")
    except discord.LoginFailure as e:
        logging.error("Failed to login to Discord. Please check your credentials.")
        raise e
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        raise
    finally:
        logging.info("Bot shutdown complete.") 