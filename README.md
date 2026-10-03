# NextGen mParivahan App Listing Preview

A responsive React, Vite and Tailwind CSS page based on the supplied dark app-store screenshot. It is identified as an independent preview, not Google Play or an official NIC website.

## Included

- One top metadata row: rating, age rating, Government, then 50M+ Downloads. The duplicate statistics block has been removed.
- A matching split Install control, authentic app icon, seven original screenshot assets and fixed bottom navigation.
- Enlarged screenshot previews, keyboard navigation and high-resolution gallery images.
- Saved apps, local search, native sharing, copy-link fallback and developer contact links.
- Published review excerpts, accurate fractional-star rendering and browser-local Yes/No feedback.
- Direct APK fetching with real byte progress, cancellation, validation and missing-file errors. There are no Google Play navigation links.
- Accessible dialogs with focus trapping, Escape dismissal, background isolation and focus restoration.
- Responsive layouts, safe-area support and reduced-motion handling.

## VPS Preview Launcher

`vps_manager.py` adds a standalone Python 3.9+ menu with **Run Website** and **Setup**. Upload it with the built `dist/` folder, then run `python3 vps_manager.py` on the VPS. The server binds to `0.0.0.0`, and Setup saves a port, displayed VPS IPv4 address and build-directory location. An optional non-root systemd unit can keep the host running after SSH closes.

See `VPS_SETUP.md` for firewall, background-service and phone-browser instructions. This launcher hosts the independent preview only: it blocks APK serving, does not log into Telegram and does not automatically publish unverified files behind government-app branding. Its Python tests are provided at `tests/test_vps_manager.py` but have not been executed in this environment.

## Reference Information

App information, screenshot sources and download settings are in `src/data/app.ts`. Assets were checked against the official `com.nic.mparivahan` listing. Images are CDN-hosted, not bundled local downloads; the icon has a local SVG fallback.

The 3.7 rating, 7L review count, 3+ age rating and requested 50M+ downloads reproduce reference values. They are not live analytics or a count of downloads from this website. The star-distribution chart is illustrative. The current official listing can have different figures.

Reviews are published excerpts. Unknown individual ratings, fabricated positive reviews and invented developer responses are not displayed. Helpful feedback stays in the browser and is not sent to an app store.

## APK Setup

No real APK or verified native-app opening link has been supplied. The old text placeholder named `app.apk` was removed because it was not installable.

1. Supply the authorized, signed APK for the app actually shown on this page.
2. Place that binary file at `public/app.apk`.
3. Rebuild and deploy the public assets with the site.
4. Test saving the APK and completing Android's installation prompt on a physical device.

The Install control fetches `/app.apk` directly. Missing files, HTML fallbacks and invalid APK archive structures produce an error rather than a fake success. Basic archive checks do not verify a publisher's identity or cryptographic signature; Android handles that verification. The in-browser download limit is 256 MB.

Progress describes bytes received by this page. After fetching, the file is handed to the browser to save. The website cannot confirm that a user completed the save dialog, silently install or uninstall an app, or detect native installation. Open APK shows the steps to open the saved file, not a simulated app launch.

## Verification

- The production build passed after the layout and download-flow changes.
- The official listing was consulted to verify the metadata order and image sources.
- Source review confirms that Government and Downloads are adjacent and that no duplicate statistics strip remains.
- Browser visual/interaction testing and physical-device APK installation have not been run in this environment.
- APK download success cannot be verified until the real file is supplied.

## Device Test Checklist

1. Check the layout at 320px, 360px, 390px, tablet and desktop widths. Scroll the metadata row on narrow screens.
2. Swipe through the gallery, enlarge every screenshot, use both arrow keys, and close with Escape.
3. Save the app, reload the page and inspect the saved app in You.
4. Search for mParivahan or vehicle, then check a no-results query.
5. Test Share and its copy-link fallback.
6. With no APK uploaded, confirm Install reports the missing file without pretending to install anything.
7. With a real signed APK uploaded, verify byte progress, cancellation, saving and Open APK instructions.
8. Verify installation and opening separately on an Android device, and check the actual publisher before approving installation.