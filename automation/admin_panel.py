#!/usr/bin/env python3
"""
Admin Panel for APK Rotation Automation
Flask-based web interface to monitor and control the system
"""

from flask import Flask, render_template_string, jsonify, request, redirect, url_for
import json
import os
import subprocess
import psutil
from datetime import datetime
from pathlib import Path

app = Flask(__name__)

BASE_DIR = Path("/home/aakash/parivahan-app")
CONFIG_FILE = BASE_DIR / "config.json"
LOG_FILE = BASE_DIR / "automation.log"
APK_FILE = BASE_DIR / "dist" / "app.apk"
BACKUP_DIR = BASE_DIR / "dist" / "apk_backups"
SESSION_FILE = BASE_DIR / "apk_rotator_session.session"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>APK Rotation Admin Panel</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Monospace', monospace; background: #0d1117; color: #c9d1d9; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #58a6ff; margin-bottom: 20px; border-bottom: 1px solid #30363d; padding-bottom: 10px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }
        .card h2 { color: #58a6ff; margin-bottom: 15px; font-size: 1.1rem; }
        .status { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #21262d; }
        .status:last-child { border-bottom: none; }
        .label { color: #8b949e; }
        .value { font-weight: bold; }
        .value.ok { color: #3fb950; }
        .value.warn { color: #d29922; }
        .value.error { color: #f85149; }
        .btn { background: #238636; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; margin: 5px; font-family: inherit; }
        .btn:hover { background: #2ea043; }
        .btn.danger { background: #da3633; }
        .btn.danger:hover { background: #f85149; }
        .btn.secondary { background: #1f6feb; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .log-container { max-height: 400px; overflow-y: auto; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 15px; font-size: 0.85rem; }
        .log-line { margin: 2px 0; font-family: monospace; }
        .log-line.error { color: #f85149; }
        .log-line.warn { color: #d29922; }
        .log-line.info { color: #58a6ff; }
        .log-line.success { color: #3fb950; }
        .apk-list { max-height: 200px; overflow-y: auto; }
        .apk-item { display: flex; justify-content: space-between; padding: 8px; border-bottom: 1px solid #21262d; }
        .refresh-btn { float: right; background: #1f6feb; }
        .section { margin-bottom: 30px; }
        .metric { text-align: center; padding: 15px; }
        .metric-value { font-size: 2rem; font-weight: bold; color: #58a6ff; }
        .metric-label { color: #8b949e; font-size: 0.9rem; }
    </style>
    <script>
        async function refreshStatus() {
            const res = await fetch('/api/status');
            const data = await res.json();
            updateUI(data);
        }
        function updateUI(data) {
            document.getElementById('http-status').textContent = data.http_server ? 'RUNNING' : 'STOPPED';
            document.getElementById('http-status').className = 'value ' + (data.http_server ? 'ok' : 'error');
            document.getElementById('tunnel-status').textContent = data.cloudflare_tunnel ? 'ACTIVE' : 'INACTIVE';
            document.getElementById('tunnel-status').className = 'value ' + (data.cloudflare_tunnel ? 'ok' : 'error');
            document.getElementById('automation-status').textContent = data.automation ? 'RUNNING' : 'STOPPED';
            document.getElementById('automation-status').className = 'value ' + (data.automation ? 'ok' : 'error');
            document.getElementById('telegram-status').textContent = data.telegram_session ? 'AUTHORIZED' : 'NOT AUTHORIZED';
            document.getElementById('telegram-status').className = 'value ' + (data.telegram_session ? 'ok' : 'error');
            document.getElementById('apk-size').textContent = data.apk_size || 'N/A';
            document.getElementById('apk-modified').textContent = data.apk_modified || 'N/A';
            document.getElementById('backup-count').textContent = data.backup_count || '0';
            document.getElementById('last-rotation').textContent = data.last_rotation || 'N/A';
            document.getElementById('next-rotation').textContent = data.next_rotation || 'N/A';
            document.getElementById('tunnel-url').textContent = data.tunnel_url || 'N/A';
        }
        async function triggerRotation() {
            const btn = document.getElementById('rotate-btn');
            btn.disabled = true;
            btn.textContent = 'Rotating...';
            try {
                await fetch('/api/rotate', { method: 'POST' });
                alert('Rotation triggered!');
            } catch (e) {
                alert('Failed: ' + e.message);
            }
            btn.disabled = false;
            btn.textContent = 'Trigger Rotation Now';
            refreshStatus();
        }
        async function refreshLogs() {
            const res = await fetch('/api/logs');
            const data = await res.json();
            const container = document.getElementById('log-container');
            container.innerHTML = data.logs.map(l => `<div class="log-line ${l.level}">${l.time} | ${l.msg}</div>`).join('');
            container.scrollTop = container.scrollHeight;
        }
        async function refreshBackups() {
            const res = await fetch('/api/backups');
            const data = await res.json();
            const container = document.getElementById('backup-list');
            container.innerHTML = data.backups.map(b => `<div class="apk-item"><span>${b.name}</span><span>${b.size} | ${b.date}</span></div>`).join('');
        }
        setInterval(refreshStatus, 10000);
        setInterval(refreshLogs, 15000);
        setInterval(refreshBackups, 30000);
        window.onload = () => { refreshStatus(); refreshLogs(); refreshBackups(); };
    </script>
</head>
<body>
    <div class="container">
        <h1>⚙️ APK Rotation Admin Panel</h1>
        
        <div class="grid">
            <div class="card">
                <h2>System Status</h2>
                <div class="status"><span class="label">HTTP Server (port 8080)</span><span id="http-status" class="value">CHECKING...</span></div>
                <div class="status"><span class="label">Cloudflare Tunnel</span><span id="tunnel-status" class="value">CHECKING...</span></div>
                <div class="status"><span class="label">Automation (launch.py)</span><span id="automation-status" class="value">CHECKING...</span></div>
                <div class="status"><span class="label">Telegram Session</span><span id="telegram-status" class="value">CHECKING...</span></div>
                <div class="status"><span class="label">Tunnel URL</span><span id="tunnel-url" class="value" style="font-size: 0.8rem; word-break: break-all;">CHECKING...</span></div>
            </div>
            
            <div class="card">
                <h2>APK Status</h2>
                <div class="status"><span class="label">Current APK Size</span><span id="apk-size" class="value">CHECKING...</span></div>
                <div class="status"><span class="label">Last Modified</span><span id="apk-modified" class="value">CHECKING...</span></div>
                <div class="status"><span class="label">Backups Count</span><span id="backup-count" class="value">CHECKING...</span></div>
                <div class="status"><span class="label">Last Rotation</span><span id="last-rotation" class="value">CHECKING...</span></div>
                <div class="status"><span class="label">Next Rotation</span><span id="next-rotation" class="value">CHECKING...</span></div>
            </div>
        </div>
        
        <div class="section">
            <div class="card">
                <h2>Actions</h2>
                <button id="rotate-btn" class="btn" onclick="triggerRotation()">Trigger Rotation Now</button>
                <button class="btn secondary" onclick="refreshStatus()">Refresh Status</button>
                <button class="btn secondary" onclick="refreshLogs()">Refresh Logs</button>
                <button class="btn secondary" onclick="refreshBackups()">Refresh Backups</button>
                <button class="btn danger" onclick="if(confirm('Stop automation?')) fetch('/api/stop', {method:'POST'})">Stop Automation</button>
                <button class="btn danger" onclick="if(confirm('Restart automation?')) fetch('/api/restart', {method:'POST'})">Restart Automation</button>
            </div>
        </div>
        
        <div class="grid">
            <div class="card">
                <h2>Recent Logs</h2>
                <div id="log-container" class="log-container">Loading...</div>
            </div>
            
            <div class="card">
                <h2>APK Backups</h2>
                <div id="backup-list" class="apk-list">Loading...</div>
            </div>
        </div>
    </div>
</body>
</html>
"""

def get_system_status():
    status = {
        "http_server": False,
        "cloudflare_tunnel": False,
        "automation": False,
        "telegram_session": False,
        "apk_size": None,
        "apk_modified": None,
        "backup_count": 0,
        "last_rotation": None,
        "next_rotation": None,
        "tunnel_url": None
    }
    
    # Check HTTP server
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if 'simple_server.py' in cmdline and '8080' in cmdline:
                status["http_server"] = True
            if 'launch.py' in cmdline:
                status["automation"] = True
            if 'cloudflared' in cmdline:
                status["cloudflare_tunnel"] = True
        except:
            pass
    
    # Check Telegram session
    if SESSION_FILE.exists():
        status["telegram_session"] = True
    
    # APK info
    if APK_FILE.exists():
        stat = APK_FILE.stat()
        status["apk_size"] = f"{stat.st_size / 1024 / 1024:.1f} MB"
        status["apk_modified"] = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    
    # Backups
    if BACKUP_DIR.exists():
        backups = list(BACKUP_DIR.glob("*.apk"))
        status["backup_count"] = len(backups)
    
    # Last rotation from logs
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, 'r') as f:
                lines = f.readlines()
            for line in reversed(lines):
                if 'APK rotation' in line and 'deployed' in line:
                    status["last_rotation"] = line.split('|')[0].strip()
                    break
        except:
            pass
    
    # Next rotation (approximate)
    if status["last_rotation"]:
        try:
            last = datetime.strptime(status["last_rotation"], "%Y-%m-%d %H:%M:%S")
            from datetime import timedelta
            next_rot = last + timedelta(minutes=5)
            status["next_rotation"] = next_rot.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
    
    # Try to get tunnel URL from cloudflared metrics
    try:
        import requests
        resp = requests.get('http://127.0.0.1:20242/metrics', timeout=2)
        import re
        match = re.search(r'https://[a-zA-Z0-9-]*\.trycloudflare\.com', resp.text)
        if match:
            status["tunnel_url"] = match.group(0)
    except:
        pass
    
    return status

def get_logs(limit=50):
    logs = []
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, 'r') as f:
                lines = f.readlines()[-limit:]
            for line in lines:
                parts = line.strip().split('|', 2)
                if len(parts) >= 3:
                    time_part = parts[0].strip()
                    level = parts[1].strip()
                    msg = parts[2].strip()
                    logs.append({"time": time_part, "level": level.lower(), "msg": msg})
        except:
            pass
    return logs

def get_backups():
    backups = []
    if BACKUP_DIR.exists():
        for f in sorted(BACKUP_DIR.glob("*.apk"), key=lambda x: x.stat().st_mtime, reverse=True):
            stat = f.stat()
            backups.append({
                "name": f.name,
                "size": f"{stat.st_size / 1024 / 1024:.1f} MB",
                "date": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
    return backups

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def api_status():
    return jsonify(get_system_status())

@app.route('/api/logs')
def api_logs():
    return jsonify({"logs": get_logs()})

@app.route('/api/backups')
def api_backups():
    return jsonify({"backups": get_backups()})

@app.route('/api/rotate', methods=['POST'])
def api_rotate():
    # Trigger rotation by touching a flag file or sending signal
    try:
        # Create trigger file that launch.py can check
        trigger_file = BASE_DIR / ".trigger_rotation"
        trigger_file.write_text(str(datetime.now()))
        return jsonify({"success": True, "message": "Rotation triggered"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/stop', methods=['POST'])
def api_stop():
    try:
        subprocess.run(['pkill', '-f', 'launch.py'], capture_output=True)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/restart', methods=['POST'])
def api_restart():
    try:
        subprocess.run(['pkill', '-f', 'launch.py'], capture_output=True)
        subprocess.Popen(['python3', 'launch.py'], cwd=BASE_DIR, 
                        stdout=open(BASE_DIR / 'automation.log', 'a'),
                        stderr=subprocess.STDOUT)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=False)