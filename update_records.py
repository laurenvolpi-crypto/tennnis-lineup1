#!/usr/bin/env python3
"""
Auto-update player USTA records, ratings, highlights, and partnership trending
in index.html from TennisRecord.com. Run every Friday via scheduled task.
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


def fetch_dynamic_rating(soup):
    """Extract Estimated Dynamic Rating from a parsed profile page."""
    m = re.search(r'Estimated Dynamic Rating\s+([\d.]+)', soup.get_text())
    if m:
        return round(float(m.group(1)), 2)
    return None


def update_rating(path, player_id, new_rating):
    """Update the rating field for a player in index.html."""
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    pattern = re.compile(r'(id:"' + re.escape(player_id) + r'", name:"[^"]+", rating:)([\d.]+)')
    new_html, count = pattern.subn(rf'\g<1>{new_rating}', html)
    if count == 0:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_html)
    return True


def fetch_record(player_id, base_url):
    """Fetch 2025 and 2026 Adult-only W/L and dynamic rating from TennisRecord.com."""
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

    dynamic_rating = fetch_dynamic_rating(soup)
    return records, dynamic_rating


def build_note(w, l):
    """Simple win/loss note."""
    if w + l == 0:
        return "No matches yet"
    pct = round(w / (w + l) * 100)
    return f"{w}-{l} ({pct}%)"


# Tags that are permanent (never auto-removed)
PERMANENT_TAGS = {
    "pham":       [],
    "hoffman":    ["Captain"],
    "burner":     ["Singles Specialist"],
    "mcmillan":   ["Breakout"],
    "liu":        ["Pair w/ Rice Only"],
}

def compute_tags(player_id, w25, l25, w26, l26):
    """Derive performance tags from records. Permanent tags are always kept."""
    tags = list(PERMANENT_TAGS.get(player_id, []))
    total26 = w26 + l26
    total25 = w25 + l25
    pct26 = round(w26 / total26 * 100) if total26 > 0 else None
    pct25 = round(w25 / total25 * 100) if total25 > 0 else None

    if pct26 is not None and pct26 >= 70 and total26 >= 3:
        tags.append("Hot")
    elif pct26 is not None and pct26 <= 30 and total26 >= 3:
        tags.append("Caution")
    elif total26 == 0 and total25 == 0:
        pass  # no data
    elif pct26 is not None and 55 <= pct26 < 70 and total26 >= 4:
        # trending up only if 2026 is meaningfully better than 2025
        if pct25 is None or pct26 > pct25 + 5:
            tags.append("Trending Up")

    return tags


def update_tags(path, player_id, new_tags):
    """Update the tags array for a player in index.html."""
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    block_start = re.search(r'id:"' + re.escape(player_id) + r'"', html)
    if not block_start:
        return False
    next_player = re.search(r'id:"\w+"', html[block_start.end():])
    block_end = block_start.end() + next_player.start() if next_player else len(html)
    segment = html[block_start.start():block_end]

    tags_js = "[" + ",".join(f'"{t}"' for t in new_tags) + "]"
    segment = re.sub(r'tags:\[[^\]]*\]', f'tags:{tags_js}', segment)
    new_html = html[:block_start.start()] + segment + html[block_end:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_html)
    return True


def update_winpct40(path, player_id, w25, l25, w26, l26):
    """Recalculate and update winPct40 from fresh record totals."""
    total = w25 + l25 + w26 + l26
    pct = round((w25 + w26) / total, 2) if total > 0 else 0.0
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    pattern = re.compile(
        r'(id:"' + re.escape(player_id) + r'".*?winPct40:)([\d.]+)',
        re.DOTALL,
    )
    new_html, count = pattern.subn(rf'\g<1>{pct}', html, count=1)
    if count == 0:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_html)
    return True


def update_singles_reasoning(path, w25, l25, w26, l26):
    """Dynamically update Burner and Pavia's hardcoded singles reasoning text."""
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    # Burner
    total26b = w26 + l26
    pct26b = round(w26 / total26b * 100) if total26b > 0 else 0
    pct25b = round(w25 / (w25 + l25) * 100) if (w25 + l25) > 0 else 0
    if pct26b < 35 and total26b >= 5:
        burner_text = (
            f'<strong>Singles specialist.</strong> Strong 2025 ({w25}-{l25}, {pct25b}%). '
            f'<strong style="color:var(--red)">Caution: {w26}-{l26} in 2026</strong> '
            f'— significant drop in form. Monitor closely before placing.'
        )
    else:
        burner_text = (
            f'<strong>Singles specialist.</strong> '
            f'2025: {w25}-{l25} ({pct25b}%). '
            f'2026: {w26}-{l26} ({pct26b}%).'
        )
    html = re.sub(
        r"(if \(p\.id === 'burner'\) \{\s*reasoning = `)([^`]+)(`)",
        rf'\g<1>{burner_text}\g<3>',
        html,
    )

    # Pavia — uses its own records passed separately, fetch from HTML
    m = re.search(r'id:"pavia".*?record25:\{w:(\d+),l:(\d+).*?record26:\{w:(\d+),l:(\d+)', html, re.DOTALL)
    if m:
        pw25, pl25, pw26, pl26 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        total_p = pw25 + pl25 + pw26 + pl26
        wins_p = pw25 + pw26
        pct_p = round(wins_p / total_p * 100) if total_p > 0 else 0
        pavia_text = (
            f'<strong style="color:var(--red)">WARNING:</strong> '
            f'Meredith is {wins_p}-{total_p - wins_p} at 4.0 across 2025-2026 ({pct_p}% win rate). '
            f'High risk placement.'
        )
        html = re.sub(
            r"(else if \(p\.id === 'pavia'\) \{\s*reasoning = `)([^`]+)(`)",
            rf'\g<1>{pavia_text}\g<3>',
            html,
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def update_partnership_trending(path):
    """Recalculate trending field for each partnership based on W/L ratio."""
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    def trending_from_record(w, l):
        total = w + l
        if total == 0:
            return "neutral"
        pct = w / total
        if pct >= 0.65:
            return "up"
        elif pct <= 0.40:
            return "down"
        return "stable"

    # Find each partnership object and update its trending field
    def replace_trending(m):
        w = int(m.group(1))
        l = int(m.group(2))
        new_trend = trending_from_record(w, l)
        # Preserve everything, just swap the trending value
        return m.group(0).replace(
            f'trending:"{m.group(3)}"', f'trending:"{new_trend}"'
        )

    new_html = re.sub(
        r'\{[^}]*w:(\d+),\s*l:(\d+)[^}]*trending:"(\w+)"[^}]*\}',
        replace_trending,
        html,
    )
    changed = html != new_html
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_html)
    return changed


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
    all_records = {}  # player_id → (r25, r26) for post-loop use

    for player_id, url in PLAYER_URLS.items():
        print(f"Fetching {player_id}...")
        result = fetch_record(player_id, url)
        if not result:
            failed.append(player_id)
            continue

        records, dynamic_rating = result
        r25 = records.get("2025", (0, 0))
        r26 = records.get("2026", (0, 0))
        all_records[player_id] = (r25, r26)
        rating_str = f"{dynamic_rating}" if dynamic_rating else "N/A"
        print(f"  Rating: {rating_str}  |  2025: {r25[0]}-{r25[1]}  |  2026: {r26[0]}-{r26[1]}")

        update_html(html_path, player_id, r25, r26)
        if dynamic_rating:
            update_rating(html_path, player_id, dynamic_rating)
        update_winpct40(html_path, player_id, r25[0], r25[1], r26[0], r26[1])

        new_tags = compute_tags(player_id, r25[0], r25[1], r26[0], r26[1])
        update_tags(html_path, player_id, new_tags)
        updated.append(player_id)

        time.sleep(0.5)  # be polite to the server

    # Update singles reasoning text for Burner using her fresh records
    if "burner" in all_records:
        r25b, r26b = all_records["burner"]
        update_singles_reasoning(html_path, r25b[0], r25b[1], r26b[0], r26b[1])
        print("Updated singles reasoning (Burner/Pavia)")

    # Refresh partnership trending from W/L ratios
    update_partnership_trending(html_path)
    print("Updated partnership trending")

    print()
    print(f"Updated: {len(updated)} players")
    if failed:
        print(f"Failed:  {', '.join(failed)}")

    from datetime import date
    msg = f"Auto-update records, ratings, highlights & partnerships {date.today()} ({len(updated)} players)"
    git_push(repo, msg)


if __name__ == "__main__":
    main()
