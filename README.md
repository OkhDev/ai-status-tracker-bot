<div align="center">

# 🤖 AI Status Tracker Bot

**Real-time Discord Bot for Monitoring OpenAI and Anthropic Service Status**

[![Version](https://img.shields.io/badge/Version-1.0.0-FF4B4B?style=for-the-badge&logo=github&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![OpenAI](https://img.shields.io/badge/OpenAI-black?style=for-the-badge&logo=openai&logoColor=white)](https://status.openai.com/)
[![Anthropic](https://img.shields.io/badge/Anthropic-ebdbbc?style=for-the-badge&logo=anthropic&logoColor=black)](https://status.anthropic.com/)
[![Discord](https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://github.com/Rapptz/discord.py)

</div>

## 🚀 Quick Start

Want to add this bot to your Discord server? Click the button below to get started:

<div align="center">
  <a href="https://discord.com/oauth2/authorize?client_id=1329897514207416360&permissions=355392&integration_type=0&scope=bot+applications.commands">
    <img src="https://img.shields.io/badge/Add%20to%20Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Add AI Status Tracker to Discord" width="200"/>
  </a>
</div>

## Features

- 🔄 Real-time status monitoring for OpenAI and Anthropic services
- 🎯 Single message that updates in place - no spam
- 🌐 Direct links to official status pages
- 🎨 Visual status indicators with color-coded states
- ⚡ Quick-access help guide for understanding status indicators
- 🔒 Admin-only commands for security

## Status Indicators

- ✅ **Operational**: All systems working normally
- 🔸 **Limited**: Some services experiencing limitations
- ❌ **Issues/Failed**: Problems detected or status check failed

Bot's presence also indicates overall status:
- 🟢 Online: All services operational
- 🟡 Idle: Some services limited
- 🔴 DND: Services have issues

## Commands

All commands require administrator permissions:

### `/create [interval]`
Creates a status tracker in the current channel
- Optional `interval`: Update frequency in minutes (default: 5)
- One tracker per channel

### `/refresh`
Force an immediate status update for all trackers

### `/interval <minutes>`
Change how often the tracker updates
- Minimum: 1 minute
- Affects the current channel only

### `/delete`
Removes the tracker from the current channel

### `/list`
Lists all active status trackers and their settings
- Shows server name, channel, refresh interval, and message ID for each tracker
- Displays the default refresh interval

### `/debug`
Get comprehensive debug information
- Bot status (status, latency, uptime)
- Configuration details
- Service status
- Channel details
- System information
- Last update times

### `/default <minutes>`
Set the default refresh interval for new trackers
- Minimum: 1 minute
- Only affects newly created trackers
- Existing trackers maintain their intervals

### `/sync`
Force sync all trackers and verify their status
- Verifies and updates all existing trackers
- Recreates missing messages
- Removes invalid channels
- Provides detailed sync results

## Setup

1. Clone the repository

2. (Optional) Create and activate a virtual environment:
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

3. Create a `.env` file with your Discord bot token and client ID:
```
DISCORD_TOKEN=your_token_here
CLIENT_ID=your_client_id_here
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Run the bot:
```bash
python status_bot.py
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 