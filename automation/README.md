# APK Rotation Automation

This folder contains the automation scripts for rotating APKs via Telegram bot and deploying to Vercel via GitHub push.

## Structure

```
automation/
├── config.json          # Configuration (edit with your values)
├── rotate_apk.py        # Main automation script
├── launch.py            # Original complex orchestrator (archived)
├── simple_server.py     # Local test server
├── minimal_server.py    # Minimal test server
├── admin_panel.py       # Admin panel (archived)
├── vps_manager.py       # VPS manager (archived)
├── vps_manager_simple.py # Simple VPS manager (archived)
├── setup.py             # Interactive setup (archived)
└── test_server.py       # Test server (archived)
```

## Configuration

Edit `config.json` with your values:

```json
{
  "website": {
    "port": 8080,
    "webroot": "../dist",
    "apk_filename": "app.apk"
  },
  "telegram_bot": {
    "api_id": "YOUR_API_ID",
    "api_hash": "YOUR_API_HASH",
    "phone": "+91XXXXXXXXXX",
    "session_name": "apk_rotator_session",
    "bot_username": "ZERODAY_COOKBOT",
    "command_trigger": "/generate mparivahanv2",
    "download_path": "/tmp/telegram_apk"
  },
  "cloudflare_tunnel": {
    "enabled": false
  },
  "rotation": {
    "interval_seconds": 600,
    "max_apk_size_mb": 256,
    "backup_count": 3,
    "request_timeout_seconds": 180
  },
  "logging": {
    "level": "INFO",
    "file": "../automation.log"
  },
  "github": {
    "repo": "YOUR_USER/parivahan-app",
    "branch": "main",
    "token_env": "GITHUB_TOKEN"
  }
}
```

## Setup

1. **Install dependencies:**
   ```bash
   pip install telethon
   ```

2. **Set GitHub token:**
   ```bash
   export GITHUB_TOKEN=your_github_personal_access_token
   # Add to ~/.bashrc or ~/.profile for persistence
   ```

3. **Create Telegram session (one-time):**
   ```bash
   cd /home/aakash/parivahan-app
   python3 -c "
   from telethon import TelegramClient
   import asyncio
   async def main():
       client = TelegramClient('apk_rotator_session', 32269114, 'c1e8ba6651460dbf43291c7d4c5a8a31')
       await client.start(phone='+918****1473')
       print('Session created!')
       await client.disconnect()
   asyncio.run(main())
   "
   ```

4. **Initialize Git repo (if not done):**
   ```bash
   cd /home/aakash/parivahan-app
   git init
   git remote add origin https://github.com/YOUR_USER/parivahan-app.git
   git add .
   git commit -m "Initial commit"
   git push -u origin main
   ```

5. **Deploy to Vercel:**
   - Go to vercel.com → Import Project → Select your GitHub repo
   - Framework: Vite, Output: dist
   - Deploy → Get your `xxx.vercel.app` URL

## Running

```bash
# Run automation (foreground)
cd /home/aakash/parivahan-app/automation
python3 rotate_apk.py

# Or run in background with tmux
tmux new-session -d -s apk_rotation "cd /home/aakash/parivahan-app/automation && python3 rotate_apk.py"
```

## Flow

```
1. Automation starts → connects to Telegram
2. Every 10 min (configurable):
   a. Sends "/generate mparivahanv2" to @ZERODAY_COOKBOT
   b. Waits for APK file response
   c. Validates APK (ZIP + AndroidManifest.xml)
   d. Copies to ../dist/app.apk (with backup)
   e. Git commits & pushes dist/ to GitHub
   f. Vercel detects push → rebuilds → deploys
3. APK available at: https://your-app.vercel.app/app.apk
```

## Logs

- Automation log: `/home/aakash/parivahan-app/automation.log`
- Check for: "APK rotation completed successfully + Vercel deploy triggered"

## Stopping

```bash
tmux kill-session -t apk_rotation
# Or Ctrl+C if running in foreground
```

## Files in dist/ (tracked by Git)

- `index.html` - Main page
- `assets/` - JS/CSS bundles (hashed filenames)
- `app.apk` - Current APK (updated by automation)
- `apk_backups/` - Previous APKs (last 3)
- `mparivahan-icon.svg` - App icon
- `APK_SETUP.txt` - Setup instructions