import ast
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from rembg import remove


ROOT = Path(__file__).resolve().parent
ASSET_DIR = ROOT / "assets" / "player_cards"
GAME_FILE = ROOT / "Football Game.py"
USER_AGENT = "FC-Legends-Portrait-Importer/1.0"

TITLE_OVERRIDES = {
    "Andres Iniesta": "Andrés_Iniesta",
    "Cristiano Ronaldo": "Cristiano_Ronaldo",
    "David Beckham": "David_Beckham",
    "Diego Maradona": "Diego_Maradona",
    "Franco Baresi": "Franco_Baresi",
    "Franz Beckenbauer": "Franz_Beckenbauer",
    "George Best": "George_Best",
    "Gianluigi Buffon": "Gianluigi_Buffon",
    "Garrincha": "Garrincha",
    "Johan Cruyff": "Johan_Cruyff",
    "Lev Yashin": "Lev_Yashin",
    "Lionel Messi": "Lionel_Messi",
    "Michel Platini": "Michel_Platini",
    "Paolo Maldini": "Paolo_Maldini",
    "Pele": "Pelé",
    "Roberto Carlos": "Roberto_Carlos",
    "Ronaldo Nazario": "Ronaldo_(Brazilian_footballer)",
    "Ronaldinho": "Ronaldinho",
    "Thierry Henry": "Thierry_Henry",
    "Zinedine Zidane": "Zinedine_Zidane",
}

IMAGE_OVERRIDES = {
    "Xavi": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Xavi%20Hernandez.jpg",
}


def load_player_names():
    tree = ast.parse(GAME_FILE.read_text())
    players = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id not in {"ICON_PLAYERS", "GOAT_PLAYERS"}:
                continue
            value = ast.literal_eval(node.value)
            players.extend(player["name"] for player in value)
    return list(dict.fromkeys(players))


def slugify(name):
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def download_bytes(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def wiki_title_for(name):
    return TITLE_OVERRIDES.get(name, name.replace(" ", "_"))


def fetch_original_image_url(name):
    if name in IMAGE_OVERRIDES:
        return IMAGE_OVERRIDES[name]
    title = wiki_title_for(name)
    url = (
        "https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageimages"
        f"&titles={urllib.parse.quote(title, safe='()_')}&pithumbsize=960"
    )
    data = fetch_json(url)
    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    image = page.get("thumbnail")
    if not image or not image.get("source"):
        raise RuntimeError(f"No image found for {name}")
    return image["source"]


def write_portrait(name, image_bytes):
    slug = slugify(name)
    jpg_path = ASSET_DIR / f"{slug}.jpg"
    png_path = ASSET_DIR / f"{slug}.png"
    jpg_path.write_bytes(image_bytes)
    png_path.write_bytes(remove(image_bytes))
    return jpg_path, png_path


def main():
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    players = load_player_names()

    failures = []
    for name in players:
        try:
            image_url = fetch_original_image_url(name)
            image_bytes = download_bytes(image_url)
            jpg_path, png_path = write_portrait(name, image_bytes)
            print(f"OK  {name}: {jpg_path.name} -> {png_path.name}", flush=True)
            time.sleep(0.5)
        except Exception as exc:
            failures.append((name, str(exc)))
            print(f"ERR {name}: {exc}", flush=True)
            time.sleep(0.5)

    if failures:
        print("\nFailed portraits:")
        for name, error in failures:
            print(f"- {name}: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
