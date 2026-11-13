"""A fictional demo niche, for trying the interface without API keys.

`nichescope demo <folder>` fills an empty data folder with three mapped channels in a
made-up space-science niche: neighbours, breakouts, a topic run with a follow-up, a
conversation and a video project. Avatars and thumbnails are generated images.
"""
from __future__ import annotations

import base64
import random
import re
import uuid
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .util import write_json

SEED = 7
NAMES = """Orbit Notes|Deep Field|Cosmic Ledger|Starlight Lab|Event Horizon Club|Redshift Weekly|Gravity Well|
Nebula Desk|Kepler Street|Apogee|Light Year Lessons|Dark Matter Diaries|The Lagrange Point|Parsec Stories|
Solar Wind|Pulsar Studio|Quasar Explained|Ring System|Heliopause|Astro Atlas|Moonbase Talks|Perihelion|
Cosmos in Ten|Supernova School|Exoplanet Hunter|Galactic Archive|Space Elevator|Stellar Drift|Zenith Science|
Crater Lab|The Orbital|Neutron Notes|Mission Control Room|Telescope Tuesday|Andromeda Daily|Rocket Garage|
Second Sun|Halo Orbit|Cassini Corner|Voyager Tapes|Lunar Theory|Big Bang Breakdown|Comet Tail|Planet Nine Files|
Interstellar Inbox|Wormhole Weekly|Spacetime Shorts|Ion Drive|Star Chart|Asteroid Belt|Gamma Burst|Titan Talks|
Europa Station|Hubble Hour|Sky Survey|Dyson Sphere|Ganymede Guide|Orion Arm|Cosmic Dawn|Mars Logbook|
Physics Fireside|Celestial Maths|Night Sky Notes|Red Dwarf Radio|Solar Sail|Gravity Assist|Starship Science|
Deep Space Digest|Universe Unpacked|Proxima Post|Lightspeed Lab|Kuiper Belt Club|Magnetar Media|Aurora Science|
Exomoon Hour|Cosmic Rays|Spiral Galaxy|Eclipse Explained|Hot Jupiter|Space Weather Desk|Zero G Lab|
Planetary Notes|Star Formation|The Big Freeze|Cosmic Web|Particle Horizon|Retrograde|Space Archaeology|
Astro Bites|Orbital Mechanics Club|Stardust Studio|Ice Giant|Habitable Zone|Neutrino Watch|Dark Energy Desk""".replace(
    "\n", "").split("|")
FIRST = ("Astro", "Cosmic", "Orbital", "Stellar", "Lunar", "Solar", "Galactic", "Quantum", "Nova", "Deep Sky",
         "Planet", "Rocket", "Comet", "Meteor", "Celestial", "Gravity", "Photon", "Infinite", "Atlas", "Vega")
SECOND = ("Lab", "Notes", "Explained", "Hour", "Club", "Studio", "Digest", "Files", "Radio", "Academy", "Daily",
          "Journal", "Minutes", "Channel", "Talks", "Science", "Stories", "Facts", "Lens", "Theory")
OFF_NICHE = ["Weeknight Dinners", "Market Close Live", "Street Food Run", "Late Show Clips"]
SUBJECTS = ["black holes", "Jupiter's moons", "the edge of the universe", "dark matter", "neutron stars",
            "the first stars", "Mars colonies", "time dilation", "rogue planets", "the Big Bang", "Europa's ocean",
            "magnetars", "the James Webb images", "Saturn's rings", "white holes", "the Fermi paradox",
            "Venus clouds", "solar storms", "Pluto", "the heat death of the universe"]
TEMPLATES = ["What happens if you fall into {s}", "I spent 30 days studying {s}", "The terrifying truth about {s}",
             "{s} explained in 12 minutes", "Why scientists are worried about {s}", "Everything we know about {s}",
             "The strangest discovery about {s}", "How big is {s} really", "Nobody expected this from {s}",
             "A journey to {s}"]
PALETTES = [("#1d4ed8", "#38bdf8"), ("#7c3aed", "#f472b6"), ("#0f766e", "#5eead4"), ("#b45309", "#fbbf24"),
            ("#be123c", "#fb7185"), ("#4338ca", "#a5b4fc"), ("#0369a1", "#7dd3fc"), ("#15803d", "#86efac"),
            ("#9333ea", "#c4b5fd"), ("#c2410c", "#fdba74")]


def _svg_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def avatar(name: str, rnd: random.Random) -> str:
    a, b = rnd.choice(PALETTES)
    initials = "".join(w[0] for w in name.split()[:2]).upper()
    angle = rnd.randint(0, 360)
    return _svg_uri(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
        f'<defs><linearGradient id="g" gradientTransform="rotate({angle} .5 .5)"><stop offset="0" stop-color="{a}"/>'
        f'<stop offset="1" stop-color="{b}"/></linearGradient></defs><rect width="128" height="128" fill="url(#g)"/>'
        f'<circle cx="{rnd.randint(20, 108)}" cy="{rnd.randint(20, 108)}" r="{rnd.randint(18, 40)}" fill="#ffffff" '
        f'opacity=".14"/><text x="64" y="78" font-family="Segoe UI,Arial,sans-serif" font-size="44" font-weight="800" '
        f'fill="#fff" text-anchor="middle">{initials}</text></svg>')


def _wrap(text: str, width: int, lines: int) -> list[str]:
    out: list[str] = []
    for word in text.split():
        if out and len(out[-1]) + 1 + len(word) <= width:
            out[-1] += " " + word
        elif len(out) < lines:
            out.append(word)
        else:
            break
    return out


def thumbnail(title: str, rnd: random.Random) -> str:
    a, b = rnd.choice(PALETTES)
    words = re.sub(r"[^\w' ]", "", title).upper()
    lines = _wrap(words, 15, 3)
    left = rnd.random() < 0.5
    x = 16 if left else 304
    anchor = "start" if left else "end"
    cx = rnd.randint(215, 285) if left else rnd.randint(35, 105)
    stars = "".join(f'<circle cx="{rnd.randint(0, 320)}" cy="{rnd.randint(0, 180)}" r="{rnd.random() * 1.4 + .3:.1f}" '
                    f'fill="#fff" opacity="{rnd.random() * .6 + .2:.2f}"/>' for _ in range(40))
    radius = rnd.randint(38, 60)
    cy = rnd.randint(60, 120)
    planet = (f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{b}"/>'
              f'<circle cx="{cx - radius // 3}" cy="{cy - radius // 3}" r="{radius // 2}" fill="#fff" opacity=".18"/>')
    if rnd.random() < 0.4:
        planet += (f'<ellipse cx="{cx}" cy="{cy}" rx="{radius + 22}" ry="{radius // 4}" fill="none" stroke="#fde68a" '
                   f'stroke-width="3" opacity=".8" transform="rotate(-18 {cx} {cy})"/>')
    top = 172 - 30 * len(lines)
    text = "".join(f'<text x="{x}" y="{top + 30 * i}" font-family="Impact,Arial Black,sans-serif" font-size="27" '
                   f'fill="{"#facc15" if i == len(lines) - 1 else "#fff"}" stroke="#000" stroke-width="1.2" '
                   f'text-anchor="{anchor}">{line}</text>' for i, line in enumerate(lines))
    return _svg_uri(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">'
        f'<defs><radialGradient id="g" cx="{.7 if left else .3}" cy=".4" r=".9"><stop offset="0" stop-color="{a}"/>'
        f'<stop offset="1" stop-color="#05070d"/></radialGradient></defs>'
        f'<rect width="320" height="180" fill="url(#g)"/>{stars}{planet}{text}</svg>')


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _channel_id(rnd: random.Random) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
    return "UC" + "".join(rnd.choice(alphabet) for _ in range(22))


def _videos(rnd: random.Random, usual: int, count: int = 40, off_niche: bool = False) -> list[dict]:
    out = []
    for i in range(count):
        if off_niche:
            title = rnd.choice(["Quick pasta for two", "Markets close lower", "Night market noodles",
                                "Best moments this week"]) + f" #{i}"
        else:
            title = rnd.choice(TEMPLATES).format(s=rnd.choice(SUBJECTS))
            title = title[0].upper() + title[1:]
        age = 2 + i * rnd.uniform(3, 7)
        lift = rnd.lognormvariate(0, 0.6) * (rnd.choice([1] * 12 + [4, 6, 9, 14]))
        vid = "".join(rnd.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(11))
        out.append({"id": vid, "title": title, "published_at": _iso(age), "seconds": rnd.randint(9, 40) * 60,
                    "views": int(usual * lift), "thumbnail": thumbnail(title, rnd),
                    "description": f"A look at {rnd.choice(SUBJECTS)} and what it means for us.",
                    "tags": ["space", "astronomy", "science", "universe"] if not off_niche else ["food", "news"],
                    "language": "en"})
    return out


def _measure(videos: list[dict]) -> dict:
    from .research.metrics import measure
    return measure(videos)


def build(folder: Path) -> dict:
    """Write the demo niche into an empty folder. Returns counts."""
    folder = Path(folder)
    if (folder / "maps").exists() and any((folder / "maps").glob("*.json")):
        raise ValueError(f"{folder} already holds maps; choose an empty folder")
    rnd = random.Random(SEED)
    names = list(dict.fromkeys(NAMES + [f"{a} {b}" for a in FIRST for b in SECOND]))
    rnd.shuffle(names)
    names = names[:320]
    channels: dict[str, dict] = {}
    for name in names + OFF_NICHE:
        cid = _channel_id(rnd)
        off = name in OFF_NICHE
        usual = int(rnd.lognormvariate(9.2, 1.1))
        videos = _videos(rnd, usual, off_niche=off)
        channels[cid] = {"title": name, "handle": "@" + name.replace(" ", "").lower(), "avatar": avatar(name, rnd),
                         "subscribers": int(usual * rnd.uniform(8, 40)), "started_at": _iso(rnd.uniform(200, 3200)),
                         "language": "en", "videos": videos, **_measure(videos)}
    ids = list(channels)
    centres = ids[:3]
    maps = []
    for m_index, cid in enumerate(centres):
        me = channels[cid]
        pool = [c for c in ids if c != cid]
        rnd.shuffle(pool)
        direct = pool[:90] + ids[-len(OFF_NICHE):][:2]
        rows: dict[str, dict] = {}
        for c in dict.fromkeys(direct):
            if c == cid:
                continue
            cov = round(min(0.95, rnd.betavariate(1.3, 4.5) * 1.6), 2)
            grade = "close" if cov >= 0.5 else "medium" if cov >= 0.2 else "far"
            src = channels[c]
            rows[c] = {k: src[k] for k in ("title", "handle", "avatar", "subscribers", "started_at", "language",
                                           "usual", "views_30d", "breakouts", "breakout")}
            rows[c].update(appearances=int(cov * 10), coverage=cov, grade=grade, step=0, first_seen=_iso(20),
                           fetched_at=_iso(0.5), topic_samples=[{"title": v["title"], "tags": v["tags"],
                                                                 "description": v["description"]}
                                                                for v in src["videos"][:12]])
        links = []
        expanded = []
        near = [c for c, r in rows.items() if r["grade"] != "far" and channels[c]["title"] not in OFF_NICHE][:14]
        for root in near:
            expanded.append(root)
            for c in rnd.sample(pool[90:] + list(rows), 18):
                if c == cid or c == root:
                    continue
                cov = round(rnd.uniform(0.2, 0.8), 2)
                if c not in rows:
                    src = channels[c]
                    rows[c] = {k: src[k] for k in ("title", "handle", "avatar", "subscribers", "started_at",
                                                   "language", "usual", "views_30d", "breakouts", "breakout")}
                    rows[c].update(appearances=0, coverage=0, via_coverage=cov, grade="far", via=root, step=1,
                                   first_seen=_iso(10), topic_samples=[{"title": v["title"], "tags": v["tags"]}
                                                                       for v in src["videos"][:12]])
                links.append({"a": root, "b": c, "coverage": cov})
        for c, r in rows.items():
            r["seen"] = [v["title"] for v in channels[c]["videos"][:3]]
            if channels[c]["title"] in OFF_NICHE:
                r["fit"] = "unrelated"
            elif r["grade"] == "close":
                r["fit"] = "same"
            else:
                r["fit"] = rnd.choices(("same", "adjacent", "unclear"), (5, 4, 1))[0]
            r["fit_n"] = len(r["seen"])
        m = {"channel_id": cid, "title": me["title"], "handle": me["handle"], "avatar": me["avatar"],
             "subscribers": me["subscribers"], "videos_read": 10, "scanned_at": _iso(0.2 + m_index),
             "first_scan": _iso(30), "videos": me["videos"], "usual": me["usual"], "views_30d": me["views_30d"],
             "breakouts": me["breakouts"], "breakout": me["breakout"], "channels": rows, "links": links,
             "expanded": expanded, "expanded_at": {r: _iso(1) for r in expanded}, "topics": [], "chats": [],
             "saved_topics": [], "marks": {"topics": {}, "titles": {}},
             "settings": {"topics": 5, "titles": 3, "check_youtube": True, "read_descriptions": True}}
        maps.append(m)
    main = maps[0]
    _add_topics(main, rnd)
    _add_chat(main)
    _add_study(folder, main, channels, rnd)
    for m in maps:
        write_json(folder / "maps" / f"{m['channel_id']}.json", m)
    _add_project(folder, main)
    return {"maps": len(maps), "channels": len({c for m in maps for c in m["channels"]})}


def _add_topics(m: dict, rnd: random.Random) -> None:
    from .research.metrics import breakouts

    evidence = [v for v in breakouts(m) if v["on_topic"]][:12]
    ideas = [
        ("What a black hole would do to Earth in one hour",
         "Viewers respond to concrete, time-boxed thought experiments with a single dramatic stake."),
        ("The ocean under Europa's ice, explained with a bath tub",
         "Everyday analogies for alien environments are carrying the strongest recent explainers."),
        ("Thirty days tracking a rogue planet",
         "Challenge-style framing applied to astronomy keeps outperforming plain explainers."),
        ("Why the first stars were nothing like the Sun",
         "Origin stories with a clear 'nothing like you think' contrast hold attention through the middle."),
        ("Ranking every moon you could stand on",
         "Ranked lists of real places draw repeat viewers and comment debates."),
    ]
    topics = []
    for i, (topic, why) in enumerate(ideas):
        cited = evidence[i * 2:i * 2 + 2] or evidence[:1]
        topics.append({
            "topic": topic, "why": why,
            "detail": "Open on the final, most striking moment, then rewind and build up to it in three stages. "
                      "Use one recurring visual scale reference so the numbers stay tangible, and close on the "
                      "open question scientists are still arguing about.",
            "reasons": {"proven": "Two recent videos on this subject beat their channels' usual views several times.",
                        "gap": "No channel nearby has covered it from a first-person, time-boxed angle.",
                        "angle": "Keep it grounded in one physical scenario instead of a list of facts.",
                        "risk": "The subject is popular, so the title has to promise something specific."},
            "evidence": [v["id"] for v in cited], "titles": [topic, f"{topic} (it gets worse)",
                                                             f"I tried to understand {topic.lower()}"][:3],
            "closest_own": m["videos"][i]["id"], "fit": [9, 8, 8, 7, 6][i],
            "expected_views": {"low": int(m["usual"]), "high": int(m["usual"] * (3.5 - i * 0.4))},
            "on_youtube": None if i != 4 else {"video": evidence[0]["id"], "title": evidence[0]["title"],
                                               "channel": evidence[0]["channel"], "views": evidence[0]["views"],
                                               "days": 21, "mine": False}})
    m["topics"] = [{"id": uuid.UUID(int=rnd.getrandbits(128)).hex[:12], "at": _iso(0.1), "instructions": "",
                    "files": [], "learned_from": len({v["channel_id"] for v in evidence}),
                    "analysis": "## Where the channel stands\nSteady long explainers with a loyal core audience; the "
                                "strongest uploads all centre on one vivid scenario.\n\n## What is breaking out now\n"
                                "- Time-boxed thought experiments\n- Everyday analogies for alien places\n"
                                "- Ranked lists of real destinations\n\n## Title formats to use\n- What happens if...\n"
                                "- I spent 30 days...\n- Ranking every...",
                    "topics": topics,
                    "followups": [{"role": "user", "content": "More titles for #1", "at": _iso(0.05), "files": []},
                                  {"role": "model", "content": "Added three titles for #1 that lead with the "
                                   "one-hour clock, which the strongest breakouts all put first.", "at": _iso(0.05),
                                   "added_topics": 0, "titles_for": [1]}]}]
    m["saved_topics"] = [{"id": uuid.UUID(int=rnd.getrandbits(128)).hex[:12], "topic": ideas[0][0], "why": ideas[0][1],
                          "detail": "", "titles": [ideas[0][0]], "status": "working", "note": "Script drafted",
                          "title": "", "at": _iso(0.05), "evidence": []}]


def _add_study(folder: Path, m: dict, channels: dict, rnd: random.Random) -> None:
    """A competitor study of the fictional channels, using the real calculations. Thumbnail
    labels are drawn at random, leaning the way real studies tend to read."""
    from .research import study

    near = [c for c, r in m["channels"].items() if r["grade"] != "far" and r.get("fit") != "unrelated"][:study.CHANNELS]
    picked = {c: {"title": channels[c]["title"], "subs": channels[c]["subscribers"], "videos": channels[c]["videos"]}
              for c in near}
    rows = study.scored(picked)
    groups: dict[str, list[str]] = {"winners": [], "losers": [], "ours": [v["id"] for v in m["videos"][:30]]}
    for c in picked:
        vs = sorted((r for r in rows if r["cid"] == c), key=lambda r: -r["lift"])
        groups["winners"] += [v["id"] for v in vs[:4]]
        groups["losers"] += [v["id"] for v in vs[-4:]]

    def label(lean: float) -> dict:
        return {"face": rnd.random() < 0.35 + lean, "faces": rnd.choice([0, 1, 1, 2]),
                "text_words": rnd.choice([2, 3, 3, 4, 5]) - (1 if lean > 0 else 0),
                "background": rnd.choice(["bright", "colourful", "colourful"] if lean > 0
                                         else ["dark", "dark", "colourful"]),
                "arrow_or_circle": rnd.random() < 0.2 + lean, "split_panels": rnd.random() < 0.1,
                "shows_a_situation": rnd.random() < 0.4 + lean, "strong_emotion": rnd.random() < 0.3 + lean}

    labels = {i: label(0.3) for i in groups["winners"]}
    labels.update({i: label(-0.1) for i in groups["losers"]})
    labels.update({i: label(-0.15) for i in groups["ours"]})
    small = sorted(picked, key=lambda c: picked[c]["subs"])[:study.ESCAPE_CHANNELS]
    history = [(picked[c]["title"], picked[c]["subs"], sorted(picked[c]["videos"], key=lambda v: v["published_at"]))
               for c in small]
    gallery, seen = [], set()
    for r in sorted(rows, key=lambda r: -r["lift"]):
        if r["cid"] not in seen:
            seen.add(r["cid"])
            gallery.append({**{k: r[k] for k in ("id", "title", "views", "seconds", "published_at", "thumbnail")},
                            "outlier": round(r["lift"], 1), "channel": picked[r["cid"]]["title"],
                            "channel_id": r["cid"]})
    import statistics
    got = {"at": _iso(1), "channels": len(picked), "videos": len(rows),
           "usual": statistics.median(channels[c]["usual"] or 0 for c in picked),
           "uploads30": 6, "titles": study.title_table(rows), "rising": study.rising(rows),
           "escapes": study.escapes(history), "gallery": gallery[:study.GALLERY], "groups": groups, "own": None}
    write_json(folder / "study" / f"{m['channel_id']}.json", got)
    write_json(folder / "study" / "labels.json", labels)


def _add_chat(m: dict) -> None:
    names = [r["title"] for r in list(m["channels"].values())[:3]]
    m["chats"] = [{"id": "demochat0001", "at": _iso(0.08), "messages": [
        {"role": "user", "content": "What's working lately in my niche?", "at": _iso(0.08), "files": []},
        {"role": "model", "at": _iso(0.08), "files": [], "content":
            f"Time-boxed thought experiments are pulling the biggest multiples this month, led by **{names[0]}** and "
            f"**{names[1]}**.\n\n## What is breaking out\n- Single-scenario explainers (what happens if...)\n"
            f"- Everyday analogies for alien environments\n- Ranked lists of real places\n\n## What to do next\n"
            f"Pick one scenario from your back catalogue that already did well and rebuild it around a clock."}]}]


def _add_project(folder: Path, m: dict) -> None:
    pid = "demoproject1"
    root = folder / "projects" / pid
    root.mkdir(parents=True, exist_ok=True)
    script = ("Imagine a black hole the mass of the Sun appeared where the Sun is right now. For eight minutes, "
              "nothing would change. Then the light would go out.\n\nThe planets would keep their orbits, because "
              "gravity at our distance stays exactly the same. But the cold would arrive fast.")
    seconds = 18.0
    with wave.open(str(root / "voiceover.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00" * int(24000 * seconds))
    shots = [("Imagine a black hole the mass of the Sun appeared where the Sun is right now.", 0.0, 5.0,
              "The Sun shrinks to a black point, Earth seen from orbit", "Slow push-in on Earth from orbit as the "
              "Sun collapses into a black sphere with a thin glowing ring, cinematic, realistic lighting"),
             ("For eight minutes, nothing would change. Then the light would go out.", 5.0, 11.0,
              "A city at noon goes dark in one instant", "Wide shot of a city skyline at midday, the light fades to "
              "night in one second, street lamps flicker on, cinematic"),
             ("The planets would keep their orbits, because gravity at our distance stays exactly the same. But the "
              "cold would arrive fast.", 11.0, seconds, "Frost spreading across a window", "Macro shot of frost "
              "crystals spreading across a window pane at night, blue light, slow motion")]
    scenes = [{"text": t, "start": a, "end": b, "clip_seconds": 6 if b - a <= 6 else 8, "visual": v, "prompt": p,
               "clip": None} for t, a, b, v, p in shots]
    write_json(root / "project.json", {
        "id": pid, "title": "What a black hole would do to Earth in one hour", "created_at": _iso(0.05),
        "updated_at": _iso(0.04), "source": {"map_id": m["channel_id"], "batch": m["topics"][0]["id"],
                                             "topic": m["topics"][0]["topics"][0]["topic"]},
        "script": script, "voice": "Charon", "visual_instructions": "Realistic, cinematic, no text on screen",
        "prompt_instructions": "", "clip_sound": 30,
        "voiceover": {"file": "voiceover.wav", "seconds": seconds, "sentences": [], "at": _iso(0.04)},
        "scenes": scenes, "render": None})
