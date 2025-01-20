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

<!-- ## 🚀 Quick Start
Want to add this bot to your Discord server? Click the button below to get started:

<div align="center">
  <a href="https://discord.com/oauth2/authorize?client_id=1329897514207416360&permissions=355392&integration_type=0&scope=bot+applications.commands">
    <img src="https://img.shields.io/badge/Add%20to%20Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Add AI Status Tracker to Discord" width="200"/>
  </a>
</div>
-->

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

Bot's presence reflects overall service status:
- 🟢 Online: All services operational
- 🟡 Idle: Some services experiencing limitations
- 🔴 DND: Services have issues or status checks failed

## Commands

All commands require administrator permissions:

| Command | Description | Parameters |
|---------|-------------|------------|
| `/create` | Creates a status tracker in the current channel | `[interval]`: Update frequency in minutes (default: 5) |
| `/refresh` | Force an immediate status update for all trackers | None |
| `/interval` | Change how often the tracker updates | `<minutes>`: New update frequency (min: 1) |
| `/delete` | Removes the tracker from the current channel | None |
| `/list` | Lists all active status trackers and their settings | None |
| `/debug` | Get comprehensive debug information including bot status, configuration, service status, and system details | None |
| `/default` | Set the default refresh interval for new trackers | `<minutes>`: New default interval (min: 1) |
| `/sync` | Force sync all trackers and verify their status | None |

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

## 📋 Future PotentialIdeas

- [ ] Add support for more AI service providers (e.g., Cohere, Mistral AI)
- [ ] Implement custom status page monitoring for any URL
- [ ] Add webhook integration for instant status notifications
- [ ] Create a web dashboard for managing multiple bot instances
- [ ] Add detailed status history and analytics
- [ ] Implement status alerts via DM for server admins
- [ ] Add custom status message templates
- [ ] Support for role-based access control beyond admin-only

---

<div align="center">

**Made with ❤️ by [OkhDev](https://github.com/OkhDev)**

</div>