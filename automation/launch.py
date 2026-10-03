#!/usr/bin/env python3
"""
Launch script for APK rotation automation.
Runs website, Cloudflare tunnel, Telegram bot, and APK rotation concurrently.
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
import shutil
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def setup_logging(config):
    log_config = config.get("logging", {})
    level = getattr(logging, log_config.get("level", "INFO"))
    log_file = log_config.get("file", "automation.log")

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger("automation")


class ProcessManager:
    """Manages subprocesses with health checks and restart logic."""

    def __init__(self, logger):
        self.logger = logger
        self.processes = {}
        self.running = True

    def start(self, name: str, cmd: list, cwd: Optional[str] = None, env: Optional[dict] = None) -> subprocess.Popen:
        self.logger.info(f"Starting {name}: {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env={**os.environ, **(env or {})},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.processes[name] = {
            "proc": proc,
            "cmd": cmd,
            "cwd": cwd,
            "env": env,
            "started": time.time()
        }
        return proc

    def is_alive(self, name: str) -> bool:
        if name not in self.processes:
            return False
        return self.processes[name]["proc"].poll() is None

    def restart(self, name: str):
        if name in self.processes:
            info = self.processes[name]
            self.logger.warning(f"Restarting {name}...")
            self.stop(name)
            time.sleep(1)
            self.start(name, info["cmd"], info["cwd"], info["env"])

    def stop(self, name: str):
        if name in self.processes:
            proc = self.processes[name]["proc"]
            self.logger.info(f"Stopping {name} (PID: {proc.pid})...")
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            del self.processes[name]

    def stop_all(self):
        for name in list(self.processes.keys()):
            self.stop(name)

    def read_output(self, name: str, lines: int = 5) -> list:
        if name not in self.processes:
            return []
        # Note: This only works if we're reading from pipes
        # For real-time logs, use separate log reading threads
        return []


class WebsiteServer:
    """Manages the simple_server.py website server."""

    def __init__(self, config, logger, proc_manager):
        self.config = config
        self.logger = logger
        self.proc_manager = proc_manager
        self.web_config = config["website"]

    def start(self):
        cmd = [
            sys.executable,
            "simple_server.py"
        ]
        self.proc_manager.start("website", cmd, cwd=str(Path(__file__).parent))
        # Wait for server to be ready
        for _ in range(30):
            time.sleep(0.5)
            if self.health_check():
                self.logger.info("Website server is ready")
                return True
        self.logger.error("Website server failed to start")
        return False

    def health_check(self) -> bool:
        import urllib.request
        try:
            url = f"http://127.0.0.1:{self.web_config['port']}/healthz"
            with urllib.request.urlopen(url, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False


class CloudflareTunnel:
    """Manages Cloudflare tunnel."""

    def __init__(self, config, logger, proc_manager):
        self.config = config
        self.logger = logger
        self.proc_manager = proc_manager
        self.cf_config = config["cloudflare_tunnel"]

    def start(self):
        if not self.cf_config.get("enabled", True):
            self.logger.info("Cloudflare tunnel disabled in config")
            return True

        cmd = [
            "cloudflared", "tunnel",
            "--url", f"http://localhost:{self.cf_config['local_port']}"
        ]
        self.proc_manager.start("cloudflare", cmd)
        self.logger.info("Cloudflare tunnel started (check logs for URL)")
        return True


class TelegramBot:
    """Telegram user bot that sends commands to target bot and receives APK files."""

    def __init__(self, config, logger, proc_manager, apk_manager):
        self.config = config
        self.logger = logger
        self.proc_manager = proc_manager
        self.apk_manager = apk_manager
        self.tg_config = config["telegram_bot"]
        self.client = None
        self.pending_apk = None
        self.apk_event = None

    async def ensure_session(self):
        """Ensure session file exists, create if needed."""
        session_name = self.tg_config.get("session_name", "apk_rotator_session")
        session_file = Path(session_name + ".session")

        if session_file.exists():
            self.logger.info(f"Session file found: {session_file}")
            return True

        self.logger.info("No session file found, creating new session...")
        return await self.create_session()

    async def create_session(self):
        """Create Telegram session interactively."""
        try:
            from telethon import TelegramClient
        except ImportError:
            self.logger.error("Telethon not installed")
            return False

        api_id = self.tg_config.get("api_id")
        api_hash = self.tg_config.get("api_hash")
        phone = self.tg_config.get("phone")
        session_name = self.tg_config.get("session_name", "apk_rotator_session")

        if not all([api_id, api_hash, phone]):
            self.logger.error("Missing Telegram credentials in config")
            return False

        client = TelegramClient(session_name, int(api_id), api_hash)

        try:
            await client.connect()

            if not await client.is_user_authorized():
                self.logger.info(f"Sending code to {phone}...")
                await client.send_code_request(phone)

                # In non-interactive mode, we can't prompt for code
                # This will fail - user must run setup.py first for interactive login
                self.logger.error("Session not authorized. Run 'python3 setup.py' to login interactively.")
                return False

            me = await client.get_me()
            self.logger.info(f"Session valid: @{me.username or me.id}")
            return True

        except Exception as e:
            self.logger.error(f"Session check failed: {e}")
            return False
        finally:
            await client.disconnect()

    async def start(self):
        try:
            from telethon import TelegramClient, events
            from telethon.sessions import StringSession
        except ImportError:
            self.logger.error("Telethon not installed. Run: pip install telethon")
            return False

        api_id = self.tg_config.get("api_id")
        api_hash = self.tg_config.get("api_hash")
        phone = self.tg_config.get("phone")
        session_name = self.tg_config.get("session_name", "apk_rotator_session")
        target_bot = self.tg_config.get("bot_username", "")

        if not all([api_id, api_hash, phone, target_bot]):
            self.logger.error("Telegram credentials not fully configured. Run setup.py first.")
            return False

        # Ensure session exists
        if not await self.ensure_session():
            return False

        self.client = TelegramClient(session_name, int(api_id), api_hash)

        @self.client.on(events.NewMessage(from_users=target_bot))
        async def handler(event):
            # Check if this is an APK file response (document or media)
            if event.document or event.media:
                self.logger.info(f"Received file/media from target bot: {event.document}")
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
            """Download APK from bot message and deploy."""
            try:
                self.logger.info("Downloading APK from bot...")
                download_path = Path(self.tg_config.get("download_path", "/tmp/telegram_apk"))
                download_path.mkdir(parents=True, exist_ok=True)
            
                # Log media type
                if event.document:
                    self.logger.info(f"Document mime_type: {event.document.mime_type}, size: {event.document.size}")
                elif event.media:
                    self.logger.info(f"Media type: {type(event.media)}")
            
                file_path = await event.download_media(file=str(download_path / "received.apk"))
            
                if file_path and Path(file_path).exists():
                    self.logger.info(f"APK downloaded to: {file_path}, size: {Path(file_path).stat().st_size}")
                
                    # Validate APK structure
                    if not await self.validate_apk(Path(file_path)):
                        self.logger.error("Downloaded file is not a valid APK")
                        if self.apk_event:
                            self.apk_event.set()
                        return
                
                    success = self.apk_manager.deploy_apk(Path(file_path))
                
                    if success:
                        self.logger.info("APK deployed successfully from bot")
                        if self.apk_event:
                            self.apk_event.set()
                    else:
                        self.logger.error("Failed to deploy APK from bot")
                else:
                    self.logger.error("APK download failed")
                    if self.apk_event:
                        self.apk_event.set()
                    
            except Exception as e:
                self.logger.error(f"Error handling APK file: {e}")
                if self.apk_event:
                    self.apk_event.set()

    async def validate_apk(self, apk_path: Path) -> bool:
        """Validate that the file is a valid APK (ZIP with AndroidManifest.xml)."""
        try:
            import zipfile
            with zipfile.ZipFile(apk_path, 'r') as zf:
                # Check for AndroidManifest.xml
                if 'AndroidManifest.xml' not in zf.namelist():
                    self.logger.error("APK missing AndroidManifest.xml")
                    return False
                # Check it's a valid ZIP
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

    async def request_apk(self):
        """Send command to target bot to generate APK."""
        target_bot = self.tg_config.get("bot_username", "")
        trigger = self.tg_config.get("command_trigger", "/genapk")

        if not target_bot or not self.client:
            return False

        self.apk_event = asyncio.Event()
        self.logger.info(f"Sending command '{trigger}' to @{target_bot}")

        try:
            await self.client.send_message(target_bot, trigger)
            self.logger.info("Command sent, waiting for APK...")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send command: {e}")
            return False

    async def wait_for_apk(self, timeout: int = 120) -> bool:
        """Wait for APK to be received from bot."""
        if not self.apk_event:
            return False

        try:
            await asyncio.wait_for(self.apk_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout waiting for APK from bot ({timeout}s)")
            return False

    def stop(self):
        if self.client:
            self.client.disconnect()


class APKManager:
    """Manages APK rotation and deployment using Telegram bot."""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.web_config = config["website"]
        self.rot_config = config["rotation"]
        self.apk_path = Path(self.web_config["webroot"]) / self.web_config["apk_filename"]
        self.last_rotation = 0
        self.telegram_bot = None

    def set_telegram_bot(self, bot):
        self.telegram_bot = bot

    def deploy_apk(self, source_apk: Path) -> bool:
        """Deploy APK to webroot with backup."""
        try:
            # Backup existing
            if self.apk_path.exists():
                backup_dir = self.apk_path.parent / "apk_backups"
                backup_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"app_{timestamp}.apk"
                shutil.copy2(self.apk_path, backup_path)

                # Clean old backups
                backups = sorted(backup_dir.glob("app_*.apk"))
                while len(backups) > self.rot_config.get("backup_count", 3):
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

    async def rotate_apk(self) -> bool:
        """Rotate APK: request from Telegram bot -> wait for file -> deploy."""
        self.logger.info("Starting APK rotation via Telegram bot...")

        if not self.telegram_bot:
            self.logger.error("Telegram bot not configured")
            return False

        # Request APK from bot
        if not await self.telegram_bot.request_apk():
            self.logger.error("Failed to request APK from bot")
            return False

        # Wait for APK to arrive
        timeout = self.rot_config.get("request_timeout_seconds", 120)
        if not await self.telegram_bot.wait_for_apk(timeout=timeout):
            self.logger.error(f"Timeout waiting for APK from bot ({timeout}s)")
            return False

        self.last_rotation = time.time()
        self.logger.info("APK rotation completed successfully")
        return True


class AutomationOrchestrator:
    """Main orchestrator that runs all components."""

    def __init__(self):
        self.config = load_config()
        self.logger = setup_logging(self.config)
        self.proc_manager = ProcessManager(self.logger)

        self.website = WebsiteServer(self.config, self.logger, self.proc_manager)
        self.cloudflare = CloudflareTunnel(self.config, self.logger, self.proc_manager)
        self.apk_manager = APKManager(self.config, self.logger)
        self.telegram_bot = TelegramBot(self.config, self.logger, self.proc_manager, self.apk_manager)

        # Connect them
        self.apk_manager.set_telegram_bot(self.telegram_bot)

        self.rotation_task = None
        self.running = True

    async def start_all(self):
        self.logger.info("=" * 60)
        self.logger.info("Starting APK Rotation Automation")
        self.logger.info("=" * 60)

        # Website server runs independently (not managed by ProcessManager)
        self.logger.info("Website server runs independently on port 8080")
        
        # Start Cloudflare tunnel
        self.cloudflare.start()

        # Start Telegram bot
        if not await self.telegram_bot.start():
            self.logger.warning("Telegram bot not started (check config)")

        # Initial APK rotation
        await self.apk_manager.rotate_apk()

        # Start rotation scheduler
        self.rotation_task = asyncio.create_task(self.rotation_loop())

        self.logger.info("All services started. Press Ctrl+C to stop.")
        return True

    async def rotation_loop(self):
        interval = self.config["rotation"]["interval_seconds"]
        self.logger.info(f"APK rotation scheduled every {interval} seconds")

        while self.running:
            await asyncio.sleep(interval)
            if not self.running:
                break
            self.logger.info("Scheduled APK rotation triggered")
            await self.apk_manager.rotate_apk()

    async def shutdown(self):
        self.logger.info("Shutting down...")
        self.running = False

        if self.rotation_task:
            self.rotation_task.cancel()
            try:
                await self.rotation_task
            except asyncio.CancelledError:
                pass

        self.telegram_bot.stop()
        self.proc_manager.stop_all()

        self.logger.info("Shutdown complete")

    def handle_signal(self, signum, frame):
        self.logger.info(f"Received signal {signum}")
        self.running = False


async def main():
    orchestrator = AutomationOrchestrator()

    # Signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, orchestrator.handle_signal, sig, None)

    if not await orchestrator.start_all():
        return 1

    # Keep running
    try:
        while orchestrator.running:
            await asyncio.sleep(1)

            # Health checks - only check cloudflare
            if orchestrator.config["cloudflare_tunnel"].get("enabled", True):
                if not orchestrator.proc_manager.is_alive("cloudflare"):
                    orchestrator.logger.warning("Cloudflare process died, restarting...")
                    orchestrator.proc_manager.restart("cloudflare")

    except KeyboardInterrupt:
        pass

    await orchestrator.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))