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

A Discord bot that monitors and displays the operational status of OpenAI and Anthropic services in real-time.

## Features ✨

- 🔄 Real-time status monitoring of OpenAI and Anthropic services
- 📊 Single, auto-updating embedded message
- 🔵 Color-coded status indicators
- 🔗 Quick access buttons to status pages
- ⏱️ Auto-updates every 5 minutes
- 🔄 Auto-recreates message if deleted

## Preview 👀

The bot maintains a single embedded message that looks like this:

```
AI Services Status Monitor
------------------------
OpenAI Status:    [Operational]
Anthropic Status: [Operational]

[OpenAI Status Page] [Anthropic Status Page]
Last updated: <timestamp>
```

## Setup 🚀

### Prerequisites

- Python 3.8 or higher
- Discord Bot Token
- Discord Server with channel access

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ai-status-tracker-bot.git
cd ai-status-tracker-bot
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
```
Then edit `.env` and add your Discord bot token.

### Configuration ⚙️

1. Create a Discord bot in the [Discord Developer Portal](https://discord.com/developers/applications)
2. Enable necessary bot permissions:
   - Read Messages/View Channels
   - Send Messages
   - Embed Links
   - Use External Emojis
3. Update the `CHANNEL_ID` in `status_bot.py` with your target channel ID

### Running the Bot 🏃‍♂️

```bash
python status_bot.py
```

## How it Works 🔧

The bot:
1. Connects to Discord using your bot token
2. Creates an embedded message in the specified channel
3. Checks OpenAI and Anthropic status pages every 5 minutes
4. Updates the embedded message with current status
5. Automatically recreates the message if deleted
6. Uses color coding to indicate overall status (blue for all operational, red if issues detected)

## Contributing 🤝

Feel free to open issues or submit pull requests if you have suggestions for improvements!

## License 📄

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 