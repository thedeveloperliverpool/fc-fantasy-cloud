# FC Fantasy Cloud Backend

This backend provides:

- account creation and login
- cloud saves for `CAREER` and `FANTASY`
- developer/admin user listing

## Run

From the project root:

```bash
python3 backend/server.py
```

By default it runs on:

```text
http://127.0.0.1:8080
```

You can change host or port:

```bash
FC_CLOUD_HOST=0.0.0.0 FC_CLOUD_PORT=8080 python3 backend/server.py
```

## Connect the game

Start the game with:

```bash
FC_CLOUD_API_URL=http://127.0.0.1:8080 python3 "Football Game.py"
```

If `FC_CLOUD_API_URL` is not set, the game falls back to local `accounts.json`.

You can also open `Cloud Settings` inside the game and save the API URL there. The launcher-style app reads that same saved setting on startup.

## Weekly Fantasy live stats

The `Weekly Fantasy Five` mode uses live real-world player events from `football-data.org`.

Set this on the cloud server before starting `server.py`:

```bash
FC_FOOTBALL_DATA_TOKEN=your_token_here python3 server.py
```

Optional overrides:

```bash
FC_WEEKLY_FANTASY_COMPETITION=PL
FC_FOOTBALL_DATA_BASE=https://api.football-data.org/v4
```

Without `FC_FOOTBALL_DATA_TOKEN`, the Weekly Fantasy mode still appears in the game but score sync will stay unavailable.

## Live launcher app

To build the editable launcher-style app:

```bash
chmod +x build_live_app.sh
./build_live_app.sh
```

That creates:

- `dist-live/FC Fantasy Live.app`
- `dist-live/Football Game.py`

The app runs the external `dist-live/Football Game.py`, so editing that file updates the app behavior without rebuilding.

## Deploy online

This repo includes `render.yaml` for Render deployment.

Basic flow:

1. Push this project to GitHub.
2. Create a new Render Blueprint service from the repo.
3. Deploy the `fc-fantasy-cloud` web service.
4. Copy the public service URL.
5. Put that URL into the game's `Cloud Settings` page.

## Replit setup

This is the simplest hosting path.

Files prepared for Replit:

- `backend/server.py`
- `backend/replit_main.py`
- `backend/.replit`
- `backend/replit.nix`
- `backend/requirements.txt`

Steps:

1. Create a new Python Repl on Replit.
2. Upload the contents of the `backend` folder into the Repl root.
3. Make sure these files are present in the Repl root:
   - `server.py`
   - `replit_main.py`
   - `.replit`
   - `replit.nix`
   - `requirements.txt`
4. Click `Run`.
5. Replit will give you a public URL.
6. Put that public URL into the game's `Cloud Settings` page.

Example cloud URL:

```text
https://your-repl-name.your-user.repl.co
```

## Auto-update hosting

The live launcher can auto-update the external `Football Game.py` file.

Host these two files somewhere public:

- `Football Game.py`
- `version.json`

Example `version.json`:

```json
{
  "version": "1.0.1",
  "script_url": "https://your-domain.example/Football%20Game.py"
}
```

Then set the launcher environment variable before building or running:

```bash
FC_UPDATE_URL=https://your-domain.example/version.json
```

The launcher compares the hosted version against the local `version.json`, downloads the new script if needed, saves it, and then runs the updated game.

## API

- `POST /api/register`
- `POST /api/login`
- `GET /api/profile`
- `GET /api/save?mode=CAREER`
- `GET /api/save?mode=FANTASY`
- `PUT /api/save`
- `GET /api/admin/users`
- `GET /health`

## Notes

- Developer access still uses the same code: `Reve1@+ion`
- Data is stored in `backend/data/cloud_accounts.db`
- Session tokens are bearer tokens stored in SQLite
- Passwords are stored as PBKDF2 hashes, not plaintext
