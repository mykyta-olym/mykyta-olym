"""Builds the profile cards from live GitHub data.

    GH_TOKEN=... python scripts/build_profile.py

Standard library only. Static facts live in profile.json and the portrait in
art/portrait.txt. Everything under "GitHub Stats" is measured on each run; if a
request fails the script stops, so a card never shows invented numbers.
"""

import json
import os
import subprocess
import tempfile
import urllib.request
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGIN = "mykyta-olym"
FONT_SIZE = 16
CHAR_WIDTH = 8.8
LINE_HEIGHT = 20
PAD = 18
INFO_WIDTH = 62
GENERATED = ("assets/", "dist/", "docs/example.svg", "profile-dark.svg", "profile-light.svg")
LOCKFILES = ("pnpm-lock.yaml", "package-lock.json", "yarn.lock", "uv.lock", "Cargo.lock", "go.sum")

THEMES = {
    "dark": {"bg": "#161b22", "text": "#c9d1d9", "key": "#ffa657", "value": "#a5d6ff",
             "dots": "#616e7f", "add": "#3fb950", "del": "#f85149"},
    "light": {"bg": "#f6f8fa", "text": "#24292f", "key": "#953800", "value": "#0a3069",
              "dots": "#9aa5b1", "add": "#1a7f37", "del": "#cf222e"},
}


def graphql(query):
    token = os.environ["GH_TOKEN"]
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-card"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


def fetch_account():
    data = graphql(
        f"""{{ user(login: "{LOGIN}") {{
          followers {{ totalCount }}
          repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST]) {{ totalCount }}
          repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {{
            totalCount
            nodes {{ name stargazerCount url }}
          }}
        }} }}"""
    )["user"]
    repos = data["repositories"]
    return {
        "repos": repos["totalCount"],
        "contributed": data["repositoriesContributedTo"]["totalCount"],
        "stars": sum(node["stargazerCount"] for node in repos["nodes"]),
        "followers": data["followers"]["totalCount"],
        "urls": [node["url"] for node in repos["nodes"]],
    }


def counted(path):
    name = path.rsplit("/", 1)[-1]
    return name not in LOCKFILES and not path.startswith(GENERATED)


def measure_history(urls, emails):
    """Counts commits and changed lines by this author, skipping lockfiles and generated files."""
    commits = added = removed = 0
    with tempfile.TemporaryDirectory() as scratch:
        for index, url in enumerate(urls):
            target = Path(scratch) / str(index)
            subprocess.run(["git", "clone", "--quiet", url, str(target)], check=True)
            authors = [f"--author={email}" for email in emails]
            log = subprocess.run(
                ["git", "-C", str(target), "log", *authors, "--numstat", "--format=commit %H"],
                check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
            ).stdout
            for line in log.splitlines():
                if line.startswith("commit "):
                    commits += 1
                    continue
                parts = line.split("\t")
                if len(parts) == 3 and parts[0].isdigit() and counted(parts[2]):
                    added += int(parts[0])
                    removed += int(parts[1])
    return {"commits": commits, "added": added, "removed": removed}


def row(key, value, width=INFO_WIDTH):
    """One 'key: ..... value' line as (text, css class) runs."""
    dots = max(width - len(key) - len(value) - 5, 2)
    return [(". ", "dots"), (key, "key"), (":", "text"), (" " + "." * dots + " ", "dots"), (value, "value")]


def rule(title, width=INFO_WIDTH):
    prefix = f"- {title} "
    return [(prefix, "text"), ("-" * (width - len(prefix)), "dots")]


def info_lines(facts, stats):
    header = facts["header"]
    lines = [[(header + " ", "text"), ("-" * (INFO_WIDTH - len(header) - 1), "dots")]]
    for section in facts["sections"]:
        if section.get("title"):
            lines.append([("", "text")])
            lines.append(rule(section["title"]))
        for key, value in section["rows"]:
            lines.append(row(key, value))
    lines.append([("", "text")])
    lines.append(rule("GitHub Stats"))
    lines.append(row("Repos", f"{stats['repos']} {{Contributed: {stats['contributed']}}}"))
    lines.append(row("Stars", f"{stats['stars']}"))
    lines.append(row("Followers", f"{stats['followers']}"))
    lines.append(row("Commits", f"{stats['commits']:,}"))
    net = stats["added"] - stats["removed"]
    label = "Lines of Code"
    tail = [(f"{net:,}", "value"), (" ( ", "text"), (f"{stats['added']:,}++", "add"),
            (", ", "text"), (f"{stats['removed']:,}--", "del"), (" )", "text")]
    used = len(label) + 5 + sum(len(text) for text, _ in tail)
    lines.append([(". ", "dots"), (label, "key"), (":", "text"),
                  (" " + "." * max(INFO_WIDTH - used, 2) + " ", "dots"), *tail])
    return lines


def render(theme_name, art, info):
    theme = THEMES[theme_name]
    art_cols = max(len(line) for line in art)
    info_x = PAD + (art_cols + 3) * CHAR_WIDTH
    rows = max(len(art), len(info))
    width = round(info_x + INFO_WIDTH * CHAR_WIDTH + PAD)
    height = rows * LINE_HEIGHT + PAD * 2
    art_top = PAD + (rows - len(art)) * LINE_HEIGHT / 2

    style = "".join(
        f".{name}{{fill:{theme[name]}}}" for name in ("text", "key", "value", "dots", "add", "del")
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        f"font-family=\"Consolas,Menlo,'DejaVu Sans Mono',monospace\" font-size=\"{FONT_SIZE}\">",
        "<title>Mykyta Olym, profile card</title>",
        f"<style>{style}text{{white-space:pre}}</style>",
        f'<rect width="{width}" height="{height}" rx="14" fill="{theme["bg"]}"/>',
    ]
    for index, line in enumerate(art):
        if line:
            y = art_top + (index + 0.8) * LINE_HEIGHT
            length = len(line) * CHAR_WIDTH
            parts.append(
                f'<text class="text" x="{PAD}" y="{y:g}" textLength="{length:g}" '
                f'lengthAdjust="spacing" xml:space="preserve">{escape(line)}</text>'
            )
    for index, runs in enumerate(info):
        chars = sum(len(text) for text, _ in runs)
        if not chars:
            continue
        y = PAD + (index + 0.8) * LINE_HEIGHT
        spans = "".join(f'<tspan class="{css}">{escape(text)}</tspan>' for text, css in runs)
        parts.append(
            f'<text x="{info_x:g}" y="{y:g}" textLength="{chars * CHAR_WIDTH:g}" '
            f'lengthAdjust="spacing" xml:space="preserve">{spans}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main():
    facts = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    art = (ROOT / "art" / "portrait.txt").read_text(encoding="ascii").splitlines()
    account = fetch_account()
    stats = {**account, **measure_history(account["urls"], facts["commit_emails"])}
    info = info_lines(facts, stats)
    for name in THEMES:
        with open(ROOT / f"profile-{name}.svg", "w", encoding="utf-8", newline="\n") as handle:
            handle.write(render(name, art, info))
    print({key: value for key, value in stats.items() if key != "urls"})


if __name__ == "__main__":
    main()
