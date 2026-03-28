#!/usr/bin/env python3
"""
Auto-update player USTA records in index.html from TennisRecord.com.
Fetches Adult-only matches (excludes Mixed and Combo) for 2025 and 2026.
Run every Friday via scheduled task.
"""

import re
import subprocess
import sys
import time
import warnings

warnings.filterwarnings("ignore")

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4", "-q"])
    import requests
    from bs4 import BeautifulSoup

# Player ID → TennisRecord.com URL (adult profile, disambiguation via &s=N where needed)
PLAYER_URLS = {
    "pham":       "https://www.tennisrecord.com/adult/profile.aspx?playername=Christina%20Pham",
    "hoffman":    "https://www.tennisrecord.com/adult/profile.aspx?playername=Sarah%20Hoffman&s=2",
    "javier":     "https://www.tennisrecord.com/adult/profile.aspx?playername=Gina%20Javier",
    "mcgeehan":   "https://www.tennisrecord.com/adult/profile.aspx?playername=Kelly%20Mcgeehan&s=2",
    "thornton":   "https://www.tennisrecord.com/adult/profile.aspx?playername=Kat%20Thornton",
    "wear":       "https://www.tennisrecord.com/adult/profile.aspx?playername=Margarita%20Wear",
    "volpi":      "https://www.tennisrecord.com/adult/profile.aspx?playername=Lauren%20Volpi",
    "burner":     "https://www.tennisrecord.com/adult/profile.aspx?playername=Hayley%20Burner",
    "klein":      "https://www.tennisrecord.com/adult/profile.aspx?playername=Sharon%20Klein&s=3",
    "mcmillan":   "https://www.tennisrecord.com/adult/profile.aspx?playername=Kate%20McMillan",
    "west":       "https://www.tennisrecord.com/adult/profile.aspx?playername=Lauren%20West",
    "rice":       "https://www.tennisrecord.com/adult/profile.aspx?playername=Jennifer%20Rice",
    "vincelette": "https://www.tennisrecord.com/adult/profile.aspx?playername=Melissa%20Vincelette",
    "anderson":   "https://www.tennisrecord.com/adult/profile.aspx?playername=Elizabeth%20Anderson&s=16",
    "pavia":      "https://www.tennisrecord.com/adult/profile.aspx?playername=Meredith%20Pavia",
    "atherton":   "https://www.tennisrecord.com/adult/profile.aspx?playername=Amy%20Atherton",
    "ezcurra":    "https://www.tennisrecord.com/adult/profile.aspx?playername=Dee%20Ann%20Ezcurra",
    "brook":      "https://www.tennisrecord.com/adult/profile.aspx?playername=Joanna%20Brook",
    "liu":        "https://www.tennisrecord.com/adult/profile.aspx?playername=Angela%20Liu",
    "hellyer":    "https://www.tennisrecord.com/adult/profile.aspx?playername=Ashley%20Hellyer",
    "jacobson":   "https://www.tennisrecord.com/adult/profile.aspx?playername=Petra%20Jacobson",
    "finley":     "https://www.tennisrecord.com/adult/profile.aspx?playername=Sarah%20Finley",
    "johnston":   "https://www.tennisrecord.com/adult/profile.aspx?playername=Nhat%20Johnston",
    "ginwala":    "https://www.tennisrecord.com/adult/profile.aspx?playername=Susan%20Ginwala",
    "nardone":    "https://www.tennisrecord.com/adult/profile.aspx?playername=Michelle%20Nardone",
    "forst":      "https://www.tennisrecord.com/adult/profile.aspx?playername=Amanda%20Forst",
    "alba":       "https://www.tennisrecord.com/adult/profile.aspx?playername=Sarah%20Alba",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def fetch_record(player_id, base_url):
    """Fetch 2025 and 2026 Adult-only W/L from TennisRecord.com."""
    # lt=-1 = Adult (excludes Mixed, Combo); mt=0 = All match types; yr=0 = All years
    sep = "&" if "?" in base_url else "?"
    url = base_url + sep + "mt=0&lt=-1&yr=0"
    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        r.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching {player_id}: {e}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table")

    # The stats table (last one) has rows: year, total, win, loss, wpct, ...
    stats_table = tables[-1] if tables else None
    if not stats_table:
        print(f"  ERROR: no table found for {player_id}")
        return None

    records = {}
    for row in stats_table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if not cells:
            continue
        year_str = cells[0]
        if year_str in ("2025", "2026") and len(cells) >= 4:
            try:
                w = int(cells[2])
                l = int(cells[3])
                records[year_str] = (w, l)
            except ValueError:
                pass

    return records


def build_note(w, l):
    """Simple win/loss note."""
    if w + l == 0:
        return "No matches yet"
    pct = round(w / (w + l) * 100)
    return f"{w}-{l} ({pct}%)"


def update_html(path, player_id, r25, r26):
    """Replace record25 and record26 for a player in index.html."""
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    # Pattern matches only the w/l values inside record25 and record26 for this player.
    # We scope to this player's block first to avoid cross-player matches.
    block_start = re.search(r'id:"' + re.escape(player_id) + r'"', html)
    if not block_start:
        print(f"  WARNING: player id '{player_id}' not found in HTML")
        return False

    # Find the next player block boundary so we only edit within this player's object
    next_player = re.search(r'id:"\w+"', html[block_start.end():])
    block_end = block_start.end() + next_player.start() if next_player else len(html)
    segment = html[block_start.start():block_end]

    w25, l25 = r25
    w26, l26 = r26
    note25 = "W 3.5+4.0"
    note26 = "W 3.5+4.0" if w26 + l26 > 0 else "No 2026 matches yet"

    # Replace record25 values
    segment = re.sub(
        r'(record25:\{)w:\d+,l:\d+,note:"[^"]*"(\})',
        rf'\g<1>w:{w25},l:{l25},note:"{note25}"\2',
        segment,
    )
    # Replace record26 values
    segment = re.sub(
        r'(record26:\{)w:\d+,l:\d+,note:"[^"]*"(\})',
        rf'\g<1>w:{w26},l:{l26},note:"{note26}"\2',
        segment,
    )

    new_html = html[:block_start.start()] + segment + html[block_end:]
    count = 1  # signal success
    block_pattern = None  # not used below

    replacement = None  # not used below

    with open(path, "w", encoding="utf-8") as f:
        f.write(new_html)
    return True


def git_push(repo_path, message):
    """Commit and push index.html."""
    cmds = [
        ["git", "-C", repo_path, "add", "index.html"],
        ["git", "-C", repo_path, "commit", "-m", message],
        ["git", "-C", repo_path, "push"],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # Commit may say "nothing to commit" — that's OK
            if "nothing to commit" in result.stdout + result.stderr:
                print("  No changes to commit.")
                return
            print(f"  Git error: {result.stderr.strip()}")
            return
    print("  Pushed to GitHub.")


def main():
    import os
    repo = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(repo, "index.html")

    print(f"Updating USTA records — {__import__('datetime').date.today()}")
    print("=" * 50)

    updated = []
    failed = []

    for player_id, url in PLAYER_URLS.items():
        print(f"Fetching {player_id}...")
        records = fetch_record(player_id, url)
        if not records:
            failed.append(player_id)
            continue

        r25 = records.get("2025", (0, 0))
        r26 = records.get("2026", (0, 0))
        print(f"  2025: {r25[0]}-{r25[1]}  |  2026: {r26[0]}-{r26[1]}")

        ok = update_html(html_path, player_id, r25, r26)
        if ok:
            updated.append(player_id)
        else:
            failed.append(player_id)

        time.sleep(0.5)  # be polite to the server

    print()
    print(f"Updated: {len(updated)} players")
    if failed:
        print(f"Failed:  {', '.join(failed)}")

    from datetime import date
    msg = f"Auto-update USTA records {date.today()} ({len(updated)} players)"
    git_push(repo, msg)


if __name__ == "__main__":
    main()
