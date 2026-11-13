<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/images/logo-light.svg">
    <img src="docs/images/logo-light.svg" alt="Nichescope" width="420">
  </picture>
</p>

<p align="center">
  <strong>Find the channels your viewers also watch and the videos taking off among them.</strong><br>
  Runs on your own machine, from the browser, the command line or an MCP client.
</p>

<p align="center">
  <a href="#get-started">Get started</a> ·
  <a href="docs/guide.md">Guide</a> ·
  <a href="docs/ai-clients.md">AI clients</a> ·
  <a href="docs/settings.md">Settings</a>
</p>

<p align="center">
  <a href="https://t.me/albertwsker2"><img src="https://img.shields.io/badge/Telegram-@albertwsker2-26A5E4?logo=telegram&logoColor=white" alt="Telegram @albertwsker2"></a>
  <a href="#contact"><img src="https://img.shields.io/badge/Discord-sc0341-5865F2?logo=discord&logoColor=white" alt="Discord sc0341"></a>
</p>

<p align="center">
  <img src="docs/images/mesh.jpg" alt="Every mapped channel on rings around the channel in the centre" width="920">
</p>

<table>
  <tr>
    <td width="33%" align="center"><strong>Niche maps</strong><br><sub>The channels YouTube puts next to yours, ring by ring</sub></td>
    <td width="33%" align="center"><strong>Breakouts</strong><br><sub>Videos doing three times their channel's usual or more</sub></td>
    <td width="33%" align="center"><strong>Topic ideas</strong><br><sub>Each one tied to the real videos behind it</sub></td>
  </tr>
</table>

## Map a niche

Paste a channel. Nichescope reads what YouTube recommends beside its videos and builds the
map from that: the channels shown most often sit closest. Off-topic channels that just
share viewers, like sports, news or music, are set aside so the map stays on your subject.

<p align="center"><img src="docs/images/map.jpg" alt="A channel's map with its nearest neighbours" width="860"></p>

## Breakouts

The channels around yours are read in full, and any video far above its channel's usual
views is flagged. Sort by how far it beat the usual, or filter to the last 30 or 90 days.

<p align="center"><img src="docs/images/breakouts.jpg" alt="Breakout videos around a channel" width="860"></p>

## Topic ideas

Ask for topics and each one comes back with the breakouts it builds on, titles ready to
use, an expected range of views and a fit score. Name a subject, say "black holes" or "a
heist arc", and it is searched first so every idea is about it. Ideas already covered on
YouTube are flagged.

<p align="center"><img src="docs/images/topics.jpg" alt="A run of topic ideas with titles and evidence" width="860"></p>

## Competitor study

The study compares your near competitors' best and worst videos with yours: which title
habits go with their breakouts, how their best thumbnails look against yours, and how soon
small channels in the niche broke out. It ends in a short list of what to change first.

<p align="center"><img src="docs/images/study.jpg" alt="A competitor study with findings and title habits" width="860"></p>

## Ask about your niche

Ask the map questions, such as which competitor is growing fastest. Answers name the
channels they lean on, and you can attach screenshots or documents.

<p align="center"><img src="docs/images/chat.jpg" alt="A question about the niche and its answer" width="860"></p>

## The mesh

The mesh puts all your maps on rings around one channel. Point at a channel to light up
its links. Click it to fly there.

<p align="center"><img src="docs/images/mesh-focus.jpg" alt="One channel in focus with its links lit" width="920"></p>

## Use it from your AI client

Maps, breakouts, topic ideas, the study and chat are also available to Claude Desktop,
Claude Code and other MCP clients.
Settings shows the exact command to copy.

<p align="center"><img src="docs/images/mcp.jpg" alt="The MCP setup panel in Settings" width="560"></p>

## Get started

You need Python 3.10 or newer, Node.js 20.19 or newer and a Gemini API key.

**Windows:** double-click `start.bat`. The first run sets everything up, then the app opens
in your browser.

**Anywhere else:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
(cd web && npm install && npm run build)
nichescope serve
```

Then open **Settings** and paste your key. That is all it needs to map channels.

<p align="center"><img src="docs/images/setup.jpg" alt="The setup panel in Settings" width="520"></p>

## Documentation

- [Getting started](docs/getting-started.md)
- [Guide](docs/guide.md)
- [AI clients](docs/ai-clients.md)
- [Settings](docs/settings.md)

## My channels

I make manhwa recaps on YouTube, and Nichescope started as the tool I needed for them.
If it helps you, subscribe to them:

<p>
  <a href="https://www.youtube.com/@BlazeManhwa1?sub_confirmation=1"><img src="https://img.shields.io/badge/Blaze%20Manhwa-Subscribe-FF0000?style=for-the-badge&logo=youtube&logoColor=white&labelColor=1e1f22" alt="Subscribe to Blaze Manhwa"></a>
  <a href="https://www.youtube.com/@SenpaiRecaps2?sub_confirmation=1"><img src="https://img.shields.io/badge/Senpai%20Recaps-Subscribe-FF0000?style=for-the-badge&logo=youtube&logoColor=white&labelColor=1e1f22" alt="Subscribe to Senpai Recaps"></a>
  <a href="https://www.youtube.com/@ManhaveraRecaps?sub_confirmation=1"><img src="https://img.shields.io/badge/Manhavera%20Recaps-Subscribe-FF0000?style=for-the-badge&logo=youtube&logoColor=white&labelColor=1e1f22" alt="Subscribe to Manhavera Recaps"></a>
</p>

## Contact

Questions or ideas? Message me.

<p>
  <a href="https://t.me/albertwsker2"><img src="https://img.shields.io/badge/Telegram-@albertwsker2-26A5E4?logo=telegram&logoColor=white" alt="Telegram @albertwsker2"></a>
  <a href="https://discord.com/app"><img src="https://img.shields.io/badge/Discord-sc0341-5865F2?logo=discord&logoColor=white" alt="Discord sc0341"></a>
</p>

On Discord, add `sc0341` as a friend.

Bugs go in [GitHub issues](https://github.com/ichigo212/nichescope/issues).

## License

MIT. See [LICENSE](LICENSE).

Nichescope is not affiliated with YouTube or Google.
