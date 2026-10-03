#!/usr/bin/env python3
"""
APK Rotation Automation - Vercel/GitHub Deploy Version
Runs Telegram bot listener, downloads APK, deploys to dist/, git pushes to trigger Vercel deploy.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def setup_logging(config):
    log_config = config.get("logging", {})
    level = getattr(logging, log_config.get("level", "INFO"))
    log_file = PROJECT_ROOT / log_config.get("file", "automation.log")

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger("automation")


class APKManager:
    """Manages APK rotation and deployment to dist/ + git push."""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.web_config = config["website"]
        self.rot_config = config["rotation"]
        self.github_config = config.get("github", {})
        
        # dist/ is in project root
        self.dist_dir = PROJECT_ROOT / self.web_config["webroot"]
        self.apk_path = self.dist_dir / self.web_config["apk_filename"]
        self.backup_dir = self.dist_dir / "apk_backups"
        self.last_rotation = 0
        self.telegram_bot = None

    def set_telegram_bot(self, bot):
        self.telegram_bot = bot

    def deploy_apk(self, source_apk: Path) -> bool:
        """Deploy APK to webroot with backup."""
        try:
            self.logger.info(f"Deploying APK from {source_apk} to {self.apk_path}")
            
            # Backup existing
            if self.apk_path.exists():
                self.backup_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = self.backup_dir / f"app_{timestamp}.apk"
                shutil.copy2(self.apk_path, backup_path)
                self.logger.info(f"Backed up existing APK to {backup_path}")

                # Clean old backups
                backups = sorted(self.backup_dir.glob("app_*.apk"))
                max_backups = self.rot_config.get("backup_count", 3)
                while len(backups) > max_backups:
                    backups[0].unlink()
                    backups.pop(0)

            # Copy new APK
            shutil.copy2(source_apk, self.apk_path)

            # Verify
            size_mb = self.apk_path.stat().st_size / (1024 * 1024)
            max_mb = self.rot_config.get("max_apk_size_mb", 256)

            if size_mb > max_mb:
                self.logger.error(f"APK too large: {size_mb:.1f}MB > {max_mb}MB")
                self.apk_path.unlink(missing_ok=True)
                return False

            self.logger.info(f"APK deployed: {self.apk_path} ({size_mb:.1f}MB)")
            return True

        except Exception as e:
            self.logger.error(f"Deploy failed: {e}")
            return False

    def git_push(self, commit_msg: str = None) -> bool:
        """Commit and push dist/ changes to GitHub to trigger Vercel deploy."""
        try:
            if not commit_msg:
                commit_msg = f"Auto: APK rotation {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            token = os.getenv(self.github_config.get("token_env", "GITHUB_TOKEN"))
            repo = self.github_config.get("repo")
            branch = self.github_config.get("branch", "main")

            if not token or not repo:
                self.logger.error("GitHub token or repo not configured")
                return False

            self.logger.info("Committing and pushing to GitHub...")

            # Git add
            subprocess.run(
                ["git", "add", "dist/"],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True
            )

            # Git commit
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                if "nothing to commit" in result.stdout.lower():
                    self.logger.info("No changes to commit")
                    return True
                self.logger.error(f"Git commit failed: {result.stderr}")
                return False

            # Git push with token
            remote_url = f"https://{token}@github.com/{repo}.git"
            result = subprocess.run(
                ["git", "push", remote_url, branch],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True
            )

            self.logger.info("Git push successful → Vercel auto-deploy triggered")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git push failed: {e.stderr if e.stderr else e}")
            return False
        except Exception as e:
            self.logger.error(f"Git push error: {e}")
            return False

    async def validate_apk(self, apk_path: Path) -> bool:
        """Validate that the file is a valid APK (ZIP with AndroidManifest.xml)."""
        try:
            with zipfile.ZipFile(apk_path, 'r') as zf:
                if 'AndroidManifest.xml' not in zf.namelist():
                    self.logger.error("APK missing AndroidManifest.xml")
                    return False
                bad_file = zf.testzip()
                if bad_file:
                    self.logger.error(f"APK has corrupted file: {bad_file}")
                    return False
            self.logger.info("APK validation passed")
            return True
        except zipfile.BadZipFile:
            self.logger.error("Downloaded file is not a valid ZIP/APK")
            return False
        except Exception as e:
            self.logger.error(f"APK validation error: {e}")
            return False

    async def rotate_apk(self) -> bool:
        """Rotate APK: request from Telegram bot -> wait for file -> deploy -> git push."""
        self.logger.info("Starting APK rotation via Telegram bot...")

        if not self.telegram_bot:
            self.logger.error("Telegram bot not configured")
            return False

        # Request APK from bot
        if not await self.telegram_bot.request_apk():
            self.logger.error("Failed to request APK from bot")
            return False

        # Wait for APK to arrive
        timeout = self.rot_config.get("request_timeout_seconds", 180)
        apk_path = await self.telegram_bot.wait_for_apk(timeout=timeout)
        if not apk_path:
            self.logger.error(f"Timeout waiting for APK from bot ({timeout}s)")
            return False

        # Validate APK
        if not await self.validate_apk(apk_path):
            self.logger.error("APK validation failed")
            return False

        # Deploy APK
        if not self.deploy_apk(apk_path):
            self.logger.error("Failed to deploy APK")
            return False

        # Git push to trigger Vercel deploy
        if not self.git_push():
            self.logger.error("Failed to push to GitHub")
            # APK is deployed locally, just push failed
            return False

        self.last_rotation = time.time()
        self.logger.info("APK rotation completed successfully + Vercel deploy triggered")
        return True


class TelegramBot:
    """Telegram user bot that sends commands to target bot and receives APK files."""

    def __init__(self, config, logger, apk_manager):
        self.config = config
        self.logger = logger
        self.apk_manager = apk_manager
        self.tg_config = config["telegram_bot"]
        self.client = None
        self.received_apk_path: Optional[Path] = None
        self.apk_event: Optional[asyncio.Event] = None
        self.expected_apk = False

    async def ensure_session(self) -> bool:
        """Ensure session file exists."""
        session_name = self.tg_config.get("session_name", "apk_rotator_session")
        session_file = PROJECT_ROOT / f"{session_name}.session"

        if session_file.exists():
            self.logger.info(f"Session file found: {session_file}")
            return True

        self.logger.info("No session file found")
        return False

    async def start(self) -> bool:
        try:
            from telethon import TelegramClient, events
        except ImportError:
            self.logger.error("Telethon not installed. Run: pip install telethon")
            return False

        api_id = self.tg_config.get("api_id")
        api_hash = self.tg_config.get("api_hash")
        phone = self.tg_config.get("phone")
        session_name = self.tg_config.get("session_name", "apk_rotator_session")
        target_bot = self.tg_config.get("bot_username", "")

        if not all([api_id, api_hash, phone, target_bot]):
            self.logger.error("Telegram credentials not fully configured")
            return False

        if not await self.ensure_session():
            return False

        # Session file is in project root
        session_path = PROJECT_ROOT / session_name
        self.client = TelegramClient(str(session_path), int(api_id), api_hash)

        @self.client.on(events.NewMessage(from_users=target_bot))
        async def handler(event):
            if self.expected_apk and (event.document or event.media):
                self.logger.info(f"Received file/media from target bot")
                await self.handle_apk_file(event)
            elif event.text:
                self.logger.info(f"Bot text response: {event.text[:200]}")

        try:
            await self.client.start(phone=phone)
            me = await self.client.get_me()
            self.logger.info(f"Userbot connected as @{me.username or me.id}")
            self.logger.info(f"Listening for APK from @{target_bot}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start Telegram userbot: {e}")
            return False

    async def handle_apk_file(self, event):
        """Download APK from bot message."""
        try:
            self.logger.info("Downloading APK from bot...")
            download_path = Path(self.tg_config.get("download_path", "/tmp/telegram_apk"))
            download_path.mkdir(parents=True, exist_ok=True)

            file_path = await event.download_media(file=str(download_path / "received.apk"))

            if file_path and Path(file_path).exists():
                self.logger.info(f"APK downloaded to: {file_path}, size: {Path(file_path).stat().st_size}")
                self.received_apk_path = Path(file_path)
                if self.apk_event:
                    self.apk_event.set()
            else:
                self.logger.error("APK download failed")
                if self.apk_event:
                    self.apk_event.set()

        except Exception as e:
            self.logger.error(f"Error handling APK file: {e}")
            if self.apk_event:
                self.apk_event.set()

    async def request_apk(self) -> bool:
        """Send command to target bot to generate APK."""
        target_bot = self.tg_config.get("bot_username", "")
        trigger = self.tg_config.get("command_trigger", "/genapk")

        if not target_bot or not self.client:
            return False

        self.apk_event = asyncio.Event()
        self.received_apk_path = None
        self.expected_apk = True
        self.logger.info(f"Sending command '{trigger}' to @{target_bot}")

        try:
            await self.client.send_message(target_bot, trigger)
            self.logger.info("Command sent, waiting for APK...")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send command: {e}")
            self.expected_apk = False
            return False

    async def wait_for_apk(self, timeout: int = 180) -> Optional[Path]:
        """Wait for APK to be received from bot."""
        if not self.apk_event:
            return None

        try:
            await asyncio.wait_for(self.apk_event.wait(), timeout=timeout)
            self.expected_apk = False
            return self.received_apk_path
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout waiting for APK from bot ({timeout}s)")
            self.expected_apk = False
            return None

    def stop(self):
        if self.client:
            self.client.disconnect()


async def main():
    config = load_config()
    logger = setup_logging(config)

    logger.info("=" * 60)
    logger.info("Starting APK Rotation Automation (Vercel Deploy)")
    logger.info("=" * 60)

    apk_manager = APKManager(config, logger)
    telegram_bot = TelegramBot(config, logger, apk_manager)
    apk_manager.set_telegram_bot(telegram_bot)

    # Start Telegram bot
    if not await telegram_bot.start():
        logger.warning("Telegram bot not started (check config)")

    # Initial APK rotation
    await apk_manager.rotate_apk()

    # Rotation scheduler
    interval = config["rotation"]["interval_seconds"]
    logger.info(f"APK rotation scheduled every {interval} seconds")

    running = True

    async def rotation_loop():
        nonlocal running
        while running:
            await asyncio.sleep(interval)
            if not running:
                break
            logger.info("Scheduled APK rotation triggered")
            await apk_manager.rotate_apk()

    rotation_task = asyncio.create_task(rotation_loop())

    # Keep running
    try:
        while running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass

    running = False
    rotation_task.cancel()
    try:
        await rotation_task
    except asyncio.CancelledError:
        pass

    telegram_bot.stop()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())