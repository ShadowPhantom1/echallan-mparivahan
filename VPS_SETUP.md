# VPS Preview Hosting

`vps_manager.py` is a Python 3.9+ launcher for the existing independent website preview. It has two main menu choices: Run Website and Setup. It binds to `0.0.0.0`, so a phone can reach it using the VPS IPv4 address and configured port when both firewalls allow access.

This is the hosting portion only. Telegram user-account login, generator commands, timed APK replacement and unverified APK publishing are not implemented. The preview host deliberately does not serve `.apk` files. A different application must use its own accurate name, publisher, logo and release information before distribution, rather than the current government-app identity.

## Files To Upload

Upload `vps_manager.py` and the entire built `dist/` directory to the same directory on the VPS, such as `/srv/website-preview/`. Include this guide for the setup instructions. The runtime needs Python 3.9+ only; Node is not needed when a built `dist/` directory is supplied.

Source files alone are not a built website. After changing frontend source, rebuild the project and upload the new `dist/` contents. The script does not install packages, build source, open firewall rules or deploy to a remote machine automatically.

## One-Command Start

From the directory containing the launcher:

```bash
python3 vps_manager.py
```

Choose **2. Setup** to enter the port, VPS IPv4 address and built-site folder. Settings are saved privately in `.vps-host/settings.json`, outside the served directory. The public IP is used to display the URL; it is not a bind address and does not configure networking.

Choose **1. Run Website**. The script automatically detects the VPS public IPv4 address and prints:

```text
====================================================================
  🚀 WEBSITE IS LIVE & ACCESSIBLE FROM ANY PHONE / BROWSER
====================================================================
  👉 PUBLIC URL:  http://123.45.67.89:8080
--------------------------------------------------------------------
```

Simply copy and open that exact `http://<IP>:<PORT>` link from Chrome, Safari or any browser on your phone. Do not enter `0.0.0.0` or `localhost` on your phone. The server remains in the foreground; Ctrl+C stops it and returns to the menu.

To skip the menu and use saved settings:

```bash
python3 vps_manager.py --serve
```

To override the port for this run:

```bash
python3 vps_manager.py --serve --port 8080
```

## Firewall And Network

Allow inbound TCP traffic for the configured port in the VPS provider's firewall/security group and the operating-system firewall. If Ubuntu UFW is already enabled and 8080 is your selected port:

```bash
sudo ufw allow 8080/tcp
```

Do not enable or reset a firewall without preserving your SSH rule. The launcher does not modify firewall settings. A private/NAT-only VPS also needs appropriate routing or port forwarding from its provider.

If the page is unreachable, check whether the process is running, the port is free, the public IPv4 address is correct, and both firewall layers allow it. Verify from the VPS:

```bash
curl http://127.0.0.1:8080/healthz
```

Then check `http://YOUR_VPS_IP:8080/healthz` from another network. A successful local health check alone does not prove public reachability.

## Keep Running After SSH Closes

Run Setup as a non-root user and select the optional systemd-service file. It is generated at `.vps-host/website-preview.service`. Keep the project in a path readable by that user, such as `/srv/website-preview/`.

Review the generated file, then install it yourself:

```bash
sudo cp .vps-host/website-preview.service /etc/systemd/system/website-preview.service
sudo systemctl daemon-reload
sudo systemctl enable --now website-preview.service
```

Stop the foreground server first to avoid a port conflict. The systemd service uses the settings present when its file was generated. After changing Setup settings, regenerate the file, copy it again, and reload/restart the service.

```bash
sudo systemctl restart website-preview.service
sudo systemctl status website-preview.service
sudo journalctl -u website-preview.service -n 50 --no-pager
```

No root shell command is run by the Python launcher. The generated service runs under the non-root user that created it. It is read-only except for system logging.

## Hosting Limits

- Only built static files are served. Source code, dotfiles, directory listings, APKs and paths outside the build directory are rejected.
- The Install control displays the host's preview-only publishing message, rather than pretending an APK was saved.
- Request logs omit query strings. The setup never asks for a Telegram password, OTP, token, API hash or session file.
- This lightweight server is for preview hosting. For a public production service, put an HTTPS reverse proxy in front of it and restrict the backend port to the proxy at the firewall.
- APK automation needs a separate, authorized release workflow with accurate branding and verified publisher identity. It is not included here.

## Checks

```bash
python3 vps_manager.py --check
python3 -m unittest discover -s tests -p 'test_vps_manager.py'
```

The frontend production build is verified in the coding environment. Python runtime checks, systemd startup and outside-network VPS access have not been executed there. Run the above checks and an external phone-browser test on your VPS before relying on this host.