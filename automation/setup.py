#!/usr/bin/env python3
"""Simple setup for APK rotation - just configure Telegram bot with auto-install."""

import json
import asyncio
import subprocess
import sys
from pathlib import Path
from getpass import getpass

CONFIG_PATH = Path(__file__).parent / "config.json"

def ensure_telethon():
    """Ensure telethon is installed, install if missing."""
    try:
        import telethon
        return True
    except ImportError:
        print("[+] Installing telethon...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "telethon", "--break-system-packages", "-q"])
            print("[+] Telethon installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[!] Failed to install telethon: {e}")
            # Try with pipx as fallback
            try:
                subprocess.check_call(["pipx", "install", "telethon"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("[+] Telethon installed via pipx")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
            print("[!] Failed to install telethon. Please run: pip3 install telethon --break-system-packages")
            return False

async def create_telegram_session(tg_config):
    """Create Telegram session file by logging in."""
    if not ensure_telethon():
        return False
    
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError

    api_id = tg_config.get("api_id")
    api_hash = tg_config.get("api_hash")
    phone = tg_config.get("phone")
    session_name = tg_config.get("session_name", "apk_rotator_session")

    if not all([api_id, api_hash, phone]):
        print("[!] Missing credentials")
        return False

    client = TelegramClient(session_name, int(api_id), api_hash)

    try:
        await client.connect()

        if not await client.is_user_authorized():
            print(f"[+] Sending code to {phone}...")
            await client.send_code_request(phone)

            print("\n[+] Check your Telegram app for the login code")
            code = input("Enter the code you received: ").strip()
            
            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                password = getpass("Two-step verification password: ")
                await client.sign_in(password=password)

        me = await client.get_me()
        print(f"[+] Logged in as @{me.username or me.id} ({me.first_name})")

        # Verify target bot is accessible
        target_bot = tg_config.get("bot_username", "")
        if target_bot:
            try:
                entity = await client.get_entity(target_bot)
                print(f"[+] Target bot found: @{entity.username or entity.id}")
            except Exception as e:
                print(f"[!] Could not resolve target bot @{target_bot}: {e}")

        return True

    except Exception as e:
        print(f"[!] Login failed: {e}")
        return False
    finally:
        await client.disconnect()

def load_config():
    CONFIG_PATH = Path(__file__).parent / "config.json"
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}

def save_config(config):
    CONFIG_PATH = Path(__file__).parent / "config.json"
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    print(f"\n[+] Config saved to {CONFIG_PATH}")

def main():
    print("=== APK Rotation Setup ===")
    config = load_config()

    tg = config.get("telegram_bot", {})
    print("\n=== Telegram Bot Configuration ===")
    print("Get api_id/api_hash from https://my.telegram.org")
    print("bot_username = the TARGET bot that generates APKs (without @)")
    print("This will also login and create session file.\n")

    tg["api_id"] = input(f"API ID [{tg.get('api_id', '')}]: ").strip() or tg.get("api_id", "")
    tg["api_hash"] = input(f"API Hash [{tg.get('api_hash', '')}]: ").strip() or tg.get("api_hash", "")
    tg["phone"] = input(f"Phone (with +country) [{tg.get('phone', '')}]: ").strip() or tg.get("phone", "")
    tg["bot_username"] = input(f"Target bot username (without @) [{tg.get('bot_username', '')}]: ").strip() or tg.get("bot_username", "")
    tg["command_trigger"] = input(f"Command trigger [{tg.get('command_trigger', '/genapk')}]: ").strip() or tg.get("command_trigger", "/genapk")

    if tg["api_id"] and tg["api_hash"] and tg["phone"] and tg["bot_username"]:
        print("\n--- Logging into Telegram to create session ---")
        if asyncio.run(create_telegram_session(tg)):
            print("[+] Session created successfully!")
        else:
            print("[!] Session creation failed. Run 'python3 setup.py' again later.")

    config["telegram_bot"] = tg
    save_config(config)
    print("\n[+] Done! Now run: python3 launch.py")

if __name__ == "__main__":
    main()