# Link-share

Link-share has two separate parts: a Flask/Socket.IO app for sharing links and messages across a local network, and a website progressive web app that can sync links through a PHP/MySQL cloud workspace.

## Components

- `app.py` and `template/index.html`: Flask app for instant LAN sharing, local link history, and local messages.
- `cloud/`: PHP API, MySQL schema and configuration example for PHP-capable hosting such as InfinityFree.
- Static files in your website folder: upload `link-share-online.html`, `link-share-service-worker.js`, and `link-share-manifest.webmanifest` to the website document root.

The Flask LAN app does not connect to the cloud. Its link and message histories stay on the host computer. The separate website/PWA cloud workspace uses a shared passphrase that permits reading, adding, and clearing links; use a long random passphrase and keep it private.

## Set up the cloud workspace on InfinityFree

1. In the hosting control panel, create a MySQL database and note its host, database name, username and password.
2. In phpMyAdmin, select that database and import `cloud/schema.sql`.
3. In the website document root, create a `cloud` directory. Upload `api.php` and `.htaccess` from the repository's `cloud` directory into it. Do not upload `config.example.php` as the live config.
4. Make a copy of `cloud/config.example.php` named `config.php` in the website's `cloud` directory. Fill in the MySQL details and set `workspace_passphrase` to a long random secret. Keep `config.php` private; the included `.htaccess` blocks web access to it.
5. Upload `link-share-online.html`, `link-share-service-worker.js`, and `link-share-manifest.webmanifest` to the website document root. The online app URL is `https://your-domain/link-share-online.html`. Open it over HTTPS and unlock it once while online so the app shell and workspace are available offline on that browser.
6. The static website file manager can publish the PWA and PHP API, but it does not run the Python LAN server. To make the website product card point to the PWA, set its link to `link-share-online.html`.

## Run the LAN app

Set `LINK_CLEAR_KEY` in the private `.env` file next to `app.py`. This key is required to clear links; clearing messages does not require it. Run the Flask server with `python app.py`. Connected LAN devices can share links and messages while the host is running. The app does not need internet access.

The LAN app keeps the 50 most recent links and messages on the Flask host in `links.json` and `messages.json`. They are not uploaded to or synchronized with the website/PWA cloud workspace.

## Offline behavior and limits

- The website PWA queues links and clear requests in IndexedDB on each browser. It syncs after a share, when the page returns to the foreground, and checks for cloud updates about every 30 seconds.
- The Flask LAN host saves links and messages in local JSON files and shares them instantly over Socket.IO. It does not sync history to the cloud.
- The website/PWA cloud workspace keeps up to 50 recent links. Clearing it affects the online workspace, not LAN history.
- The PWA needs to be opened online once on each device before its app shell and cloud data can be used offline. Browser storage can be removed by clearing that browser's site data.
- This is one shared passphrase workspace, not separate user accounts. Anyone with the passphrase can read, add and clear its links.

## Local development

Install the packages in `requirements.txt`, then run:

```powershell
python app.py
```

The host prints its local network address. Its link and message histories are stored in `links.json` and `messages.json` next to `app.py`; these files and `.env` are excluded from version control.
