# Security

Nichescope is meant to run on your own machine. The web app and its MCP endpoint listen on
`127.0.0.1` and have no login, so anyone who can reach the port can use your keys. Do not
bind it to another address or put it behind a public proxy.

Keys live in `.env`, uploaded credential files in `credentials/`, and research in `data/`.
All three are ignored by git.

## Reporting a vulnerability

Please report security problems privately, not in a public issue: message Discord `sc0341`
or Telegram [@albertwsker2](https://t.me/albertwsker2). Include the steps to reproduce it
and the version you ran.
