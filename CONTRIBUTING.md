# Contributing

Bug reports and pull requests are welcome.

## Setting up

```bash
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -e ".[dev]"
(cd web && npm install && npm run build)
```

Run `nichescope serve` for the app, and `cd web && npm run dev` for the web client with hot
reload on port 5173.

## Before opening a pull request

```bash
ruff check src tests
pytest
(cd web && npm run build)
```

Tests run offline and never call YouTube or the model. Keep it that way: new code that
reaches the network should take its data through a function the tests can replace.

Keep pull requests to one change, and say in the description what it fixes or adds and how
you checked it. Never commit `.env`, `credentials/` or `data/`.

## Reporting a bug

Say what you did, what you expected and what happened, with the log lines from the window
running `nichescope serve`. Remove keys and channel details you would rather not share.
