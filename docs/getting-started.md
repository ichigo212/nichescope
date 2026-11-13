# Getting started

<p align="center"><img src="images/map.jpg" alt="A mapped channel and the channels around it" width="860"></p>

## What you need

- Python 3.10 or newer
- Node.js 20.19 or newer, to build the web app once
- A Gemini API key from Google AI Studio

## Install and run

On Windows, double-click `start.bat`. The first run creates the Python environment, builds
the web app and opens it at <http://127.0.0.1:8765>. Later runs just start it. Close the
window to stop it.

On macOS or Linux:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
(cd web && npm install && npm run build)
nichescope serve
```

## Add your key

Open **Settings**. Paste the Gemini key under *Language model* and press **Save**. The four
tiles at the top show *Ready* as each part is set up, and **Test connection** checks
each one.

<p align="center"><img src="images/setup.jpg" alt="The setup panel" width="520"></p>

Keys are saved to `.env` in the project folder and are only sent to the service they belong
to. Gemini use beyond the free tier is billed by Google.

## Map your first channel

On **Channels**, paste a channel name, link or @handle and press **Add a channel**. Choose how
far out to map. *This channel only* finds the channels YouTube shows beside its videos;
each step out also reads the channels beside the nearest of those. One or two steps is
plenty to start; you can go further later.

A channel under 1,000 subscribers gets a warning first: its recommendations are mostly
noise, so a larger competitor makes a better centre.

Mapping runs in the background. The bar at the bottom shows progress, and the map opens
when it is done.

## Next

- [Guide](guide.md): reading a map, breakouts, topic ideas, the study, chat and video projects
- [AI clients](ai-clients.md): use Nichescope from Claude and other MCP clients
- [Settings](settings.md): every option

## Command line

```bash
nichescope map @somechannel --steps 2   # map a channel
nichescope refresh                      # refresh the most overdue map
nichescope demo demo-data               # write a made-up niche to try the app with
```

To look around without a key, write the demo niche and point the app at it:
`NICHESCOPE_DATA_DIR=demo-data nichescope serve`. `nichescope --help` lists every command.

## Working on Nichescope

```bash
pip install -e ".[dev]"
ruff check src tests
pytest
cd web && npm run dev        # hot reload on :5173 while `nichescope serve` runs
```

Tests run offline and never call YouTube or the model.
