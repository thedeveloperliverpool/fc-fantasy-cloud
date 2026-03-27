import base64
import json
import math
import os
import random
import socket
import sys
import hashlib
from array import array
from dataclasses import dataclass, field
from urllib import error as urllib_error
from urllib import request as urllib_request

import pygame

# --- Config ---
WIDTH, HEIGHT = 1200, 720
FPS = 60
FIELD_MARGIN = 50
GOAL_WIDTH = 120
GOAL_DEPTH = 18
PENALTY_BOX_DEPTH = 180
PENALTY_BOX_HEIGHT = 320
GOAL_BOX_DEPTH = 60
GOAL_BOX_HEIGHT = 180
PENALTY_SPOT_DIST = 120
COMMENTARY_BAR_H = 50

PLAYER_SPEED = 2.6
PLAYER_ACCEL = 0.35
PLAYER_FRICTION = 0.88
BALL_DECAY = 0.985
BALL_GROUND_FRICTION = 0.97
PASS_SPEED = 7.5
SHOT_SPEED = 10.5
CONTROL_RADIUS = 18
TACKLE_RADIUS = 16
KEEPER_RADIUS = 22
PLAYER_RADIUS = 10
KICK_RADIUS = 32
DRIBBLE_PUSH = 0.7
BALL_FOLLOW_STIFFNESS = 0.25
BALL_FOLLOW_DAMP = 0.78
AI_DIFFICULTY = 0.12  # lower = easier for player
DRIBBLE_TENDENCY = 0.75  # higher = more dribbling vs passing
SHOOT_TENDENCY = 0.08  # base chance to shoot when in range
CORNER_ARC_RADIUS = 12

def player_speed_from_rating(rating):
    return PLAYER_SPEED * clamp(0.9 + (rating - 70) / 150, 0.7, 1.2)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    APP_DATA_DIR = os.path.join(os.path.expanduser("~/Library/Application Support"), "FC Legends")
else:
    APP_DATA_DIR = BASE_DIR
os.makedirs(APP_DATA_DIR, exist_ok=True)
RATING_CACHE_FILE = os.path.join(APP_DATA_DIR, "rating_cache.json")
DEFAULT_FANTASY_COINS = 100
DEVELOPER_FANTASY_COINS = 50000
ACCOUNTS_FILE = os.path.join(APP_DATA_DIR, "accounts.json")
SETTINGS_FILE = os.path.join(APP_DATA_DIR, "settings.json")
DEVELOPER_CODE = "Reve1@+ion"
CLOUD_API_BASE = os.environ.get("FC_CLOUD_API_URL", "").rstrip("/")
FANTASY_CLUB_BADGES = ["Falcon", "Crown", "Bolt", "Anchor", "Nova", "Lion"]
FANTASY_CLUB_PALETTES = [
    ("Neon Blue", (54, 136, 255)),
    ("Crimson", (210, 52, 72)),
    ("Emerald", (44, 184, 122)),
    ("Gold", (224, 176, 56)),
    ("Violet", (154, 92, 255)),
    ("Arctic", (196, 226, 255)),
    ("Midnight", (26, 42, 82)),
    ("Coral", (255, 122, 94)),
]
FANTASY_STADIUM_OPTIONS = ["Fantasy Arena", "Legends Dome", "Blue Voltage Park", "Royal Terrace", "Nightwave Ground"]


def load_app_settings():
    defaults = {
        "cloud_enabled": True,
        "cloud_api_url": CLOUD_API_BASE or "http://127.0.0.1:8080",
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                defaults.update({k: data[k] for k in defaults if k in data})
        except Exception:
            pass
    if CLOUD_API_BASE:
        defaults["cloud_api_url"] = CLOUD_API_BASE
    return defaults


def load_app_version():
    version_file = os.path.join(BASE_DIR, "version.json")
    data = {}
    if os.path.exists(version_file):
        try:
            with open(version_file, "r", encoding="utf-8") as fh:
                data = json.load(fh) or {}
        except Exception:
            data = {}
    version = str(os.environ.get("FC_APP_VERSION") or data.get("version") or "1.0.0")
    manifest_url = str(data.get("manifest_url", "")).strip()
    return {"version": version, "manifest_url": manifest_url}


def save_app_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

CARD_POSITIONS = ["GK", "RB", "CB", "LB", "CDM", "CM", "CAM", "RW", "LW", "ST"]
PROMO_TYPES = [
    "Base",
    "TOTW",
    "TOTY",
    "Hero",
    "Future Star",
    "Clutch",
    "Ice",
    "Thunder",
    "Centurions",
    "Shapeshifter",
    "Phantom",
    "Neon",
    "RTTK",
    "Dynasty",
]

ICON_PLAYERS = [
    {"name": "Lev Yashin", "team": "Icons", "rating": 201, "position": "GK"},
    {"name": "Cafu", "team": "Icons", "rating": 202, "position": "RB"},
    {"name": "Franz Beckenbauer", "team": "Icons", "rating": 205, "position": "CB"},
    {"name": "Paolo Maldini", "team": "Icons", "rating": 204, "position": "CB"},
    {"name": "Roberto Carlos", "team": "Icons", "rating": 202, "position": "LB"},
    {"name": "Xavi", "team": "Icons", "rating": 201, "position": "CM"},
    {"name": "Zinedine Zidane", "team": "Icons", "rating": 207, "position": "CM"},
    {"name": "Diego Maradona", "team": "Icons", "rating": 208, "position": "CAM"},
    {"name": "Johan Cruyff", "team": "Icons", "rating": 206, "position": "RW"},
    {"name": "Pele", "team": "Icons", "rating": 210, "position": "ST"},
    {"name": "Ronaldinho", "team": "Icons", "rating": 207, "position": "LW"},
    {"name": "Gianluigi Buffon", "team": "Icons", "rating": 200, "position": "GK"},
    {"name": "Franco Baresi", "team": "Icons", "rating": 202, "position": "CB"},
    {"name": "Carlos Alberto Torres", "team": "Icons", "rating": 203, "position": "RB"},
    {"name": "Sergio Ramos", "team": "Icons", "rating": 201, "position": "CB"},
    {"name": "Andres Iniesta", "team": "Icons", "rating": 203, "position": "CM"},
    {"name": "Michel Platini", "team": "Icons", "rating": 204, "position": "CAM"},
    {"name": "David Beckham", "team": "Icons", "rating": 201, "position": "RW"},
    {"name": "Ronaldo Nazario", "team": "Icons", "rating": 209, "position": "ST"},
    {"name": "Thierry Henry", "team": "Icons", "rating": 205, "position": "ST"},
    {"name": "George Best", "team": "Icons", "rating": 204, "position": "RW"},
    {"name": "Garrincha", "team": "Icons", "rating": 205, "position": "RW"},
]

GOAT_PLAYERS = [
    {"name": "Lionel Messi", "team": "GOAT", "rating": 500, "position": "RW"},
    {"name": "Cristiano Ronaldo", "team": "GOAT", "rating": 500, "position": "ST"},
]

SIGNATURE_PLAYERS = [
    {"name": "Kylian Mbappe", "team": "Real Madrid", "rating": 102, "position": "ST"},
    {"name": "Erling Haaland", "team": "Manchester City", "rating": 101, "position": "ST"},
    {"name": "Jude Bellingham", "team": "Real Madrid", "rating": 100, "position": "CM"},
    {"name": "Vinicius Junior", "team": "Real Madrid", "rating": 100, "position": "LW"},
    {"name": "Neymar", "team": "Al Hilal", "rating": 99, "position": "LW"},
    {"name": "Mohamed Salah", "team": "Liverpool", "rating": 98, "position": "RW"},
    {"name": "Harry Kane", "team": "Bayern Munich", "rating": 98, "position": "ST"},
    {"name": "Jamal Musiala", "team": "Bayern Munich", "rating": 97, "position": "CAM"},
]

WORLD_LEAGUE_PLAYERS = [
    {"name": "Kylian Mbappe", "team": "Real Madrid", "rating": 94, "position": "ST"},
    {"name": "Vinicius Junior", "team": "Real Madrid", "rating": 92, "position": "LW"},
    {"name": "Jude Bellingham", "team": "Real Madrid", "rating": 92, "position": "CM"},
    {"name": "Federico Valverde", "team": "Real Madrid", "rating": 89, "position": "CM"},
    {"name": "Rodrygo", "team": "Real Madrid", "rating": 88, "position": "RW"},
    {"name": "Thibaut Courtois", "team": "Real Madrid", "rating": 89, "position": "GK"},
    {"name": "Antonio Rudiger", "team": "Real Madrid", "rating": 88, "position": "CB"},
    {"name": "Robert Lewandowski", "team": "Barcelona", "rating": 91, "position": "ST"},
    {"name": "Lamine Yamal", "team": "Barcelona", "rating": 87, "position": "RW"},
    {"name": "Pedri", "team": "Barcelona", "rating": 89, "position": "CM"},
    {"name": "Frenkie de Jong", "team": "Barcelona", "rating": 88, "position": "CM"},
    {"name": "Raphinha", "team": "Barcelona", "rating": 86, "position": "RW"},
    {"name": "Ronald Araujo", "team": "Barcelona", "rating": 87, "position": "CB"},
    {"name": "Antoine Griezmann", "team": "Atletico Madrid", "rating": 89, "position": "ST"},
    {"name": "Jan Oblak", "team": "Atletico Madrid", "rating": 90, "position": "GK"},
    {"name": "Julian Alvarez", "team": "Atletico Madrid", "rating": 87, "position": "ST"},
    {"name": "Marcos Llorente", "team": "Atletico Madrid", "rating": 85, "position": "CM"},
    {"name": "Nico Williams", "team": "Athletic Club", "rating": 86, "position": "LW"},
    {"name": "Oihan Sancet", "team": "Athletic Club", "rating": 84, "position": "CAM"},
    {"name": "Takefusa Kubo", "team": "Real Sociedad", "rating": 84, "position": "RW"},
    {"name": "Martin Zubimendi", "team": "Real Sociedad", "rating": 84, "position": "CDM"},
    {"name": "Isco", "team": "Real Betis", "rating": 83, "position": "CAM"},
    {"name": "Alexander Isak", "team": "Newcastle", "rating": 88, "position": "ST"},
    {"name": "Harry Kane", "team": "Bayern Munich", "rating": 92, "position": "ST"},
    {"name": "Jamal Musiala", "team": "Bayern Munich", "rating": 90, "position": "CAM"},
    {"name": "Michael Olise", "team": "Bayern Munich", "rating": 86, "position": "RW"},
    {"name": "Joshua Kimmich", "team": "Bayern Munich", "rating": 88, "position": "CM"},
    {"name": "Florian Wirtz", "team": "Bayer Leverkusen", "rating": 89, "position": "CAM"},
    {"name": "Victor Boniface", "team": "Bayer Leverkusen", "rating": 85, "position": "ST"},
    {"name": "Jeremie Frimpong", "team": "Bayer Leverkusen", "rating": 86, "position": "RB"},
    {"name": "Granit Xhaka", "team": "Bayer Leverkusen", "rating": 85, "position": "CM"},
    {"name": "Serhou Guirassy", "team": "Dortmund", "rating": 86, "position": "ST"},
    {"name": "Gregor Kobel", "team": "Dortmund", "rating": 87, "position": "GK"},
    {"name": "Karim Adeyemi", "team": "Dortmund", "rating": 83, "position": "LW"},
    {"name": "Pascal Gross", "team": "Dortmund", "rating": 83, "position": "CM"},
    {"name": "Lois Openda", "team": "RB Leipzig", "rating": 85, "position": "ST"},
    {"name": "Xavi Simons", "team": "RB Leipzig", "rating": 86, "position": "CAM"},
    {"name": "Benjamin Sesko", "team": "RB Leipzig", "rating": 84, "position": "ST"},
    {"name": "Jonathan Tah", "team": "Bayer Leverkusen", "rating": 85, "position": "CB"},
    {"name": "Victor Osimhen", "team": "Napoli", "rating": 89, "position": "ST"},
    {"name": "Khvicha Kvaratskhelia", "team": "Napoli", "rating": 87, "position": "LW"},
    {"name": "Stanislav Lobotka", "team": "Napoli", "rating": 84, "position": "CM"},
    {"name": "Lautaro Martinez", "team": "Inter", "rating": 91, "position": "ST"},
    {"name": "Nicolo Barella", "team": "Inter", "rating": 88, "position": "CM"},
    {"name": "Marcus Thuram", "team": "Inter", "rating": 86, "position": "ST"},
    {"name": "Hakan Calhanoglu", "team": "Inter", "rating": 87, "position": "CM"},
    {"name": "Alessandro Bastoni", "team": "Inter", "rating": 87, "position": "CB"},
    {"name": "Mike Maignan", "team": "AC Milan", "rating": 89, "position": "GK"},
    {"name": "Rafael Leao", "team": "AC Milan", "rating": 88, "position": "LW"},
    {"name": "Theo Hernandez", "team": "AC Milan", "rating": 87, "position": "LB"},
    {"name": "Christian Pulisic", "team": "AC Milan", "rating": 84, "position": "RW"},
    {"name": "Tijjani Reijnders", "team": "AC Milan", "rating": 83, "position": "CM"},
    {"name": "Dusan Vlahovic", "team": "Juventus", "rating": 87, "position": "ST"},
    {"name": "Kenan Yildiz", "team": "Juventus", "rating": 82, "position": "LW"},
    {"name": "Bremer", "team": "Juventus", "rating": 86, "position": "CB"},
    {"name": "Paulo Dybala", "team": "Roma", "rating": 86, "position": "CAM"},
    {"name": "Artem Dovbyk", "team": "Roma", "rating": 84, "position": "ST"},
    {"name": "Mats Hummels", "team": "Roma", "rating": 83, "position": "CB"},
    {"name": "Gianluigi Donnarumma", "team": "PSG", "rating": 89, "position": "GK"},
    {"name": "Ousmane Dembele", "team": "PSG", "rating": 87, "position": "RW"},
    {"name": "Achraf Hakimi", "team": "PSG", "rating": 87, "position": "RB"},
    {"name": "Joao Neves", "team": "PSG", "rating": 85, "position": "CM"},
    {"name": "Bradley Barcola", "team": "PSG", "rating": 85, "position": "LW"},
    {"name": "Marquinhos", "team": "PSG", "rating": 87, "position": "CB"},
    {"name": "Jonathan David", "team": "Lille", "rating": 85, "position": "ST"},
    {"name": "Alexandre Lacazette", "team": "Lyon", "rating": 83, "position": "ST"},
    {"name": "Rayan Cherki", "team": "Lyon", "rating": 82, "position": "CAM"},
    {"name": "Pierre-Emerick Aubameyang", "team": "Marseille", "rating": 82, "position": "ST"},
    {"name": "Lionel Messi", "team": "Inter Miami", "rating": 92, "position": "RW"},
    {"name": "Luis Suarez", "team": "Inter Miami", "rating": 84, "position": "ST"},
    {"name": "Sergio Busquets", "team": "Inter Miami", "rating": 83, "position": "CDM"},
    {"name": "Jordi Alba", "team": "Inter Miami", "rating": 82, "position": "LB"},
    {"name": "Sergio Canales", "team": "Monterrey", "rating": 83, "position": "CAM"},
    {"name": "Salomon Rondon", "team": "Pachuca", "rating": 81, "position": "ST"},
    {"name": "Karim Benzema", "team": "Al Ittihad", "rating": 87, "position": "ST"},
    {"name": "Neymar", "team": "Al Hilal", "rating": 89, "position": "LW"},
    {"name": "Ruben Neves", "team": "Al Hilal", "rating": 85, "position": "CM"},
    {"name": "Aleksandar Mitrovic", "team": "Al Hilal", "rating": 84, "position": "ST"},
    {"name": "Sadio Mane", "team": "Al Nassr", "rating": 85, "position": "LW"},
    {"name": "Marcelo Brozovic", "team": "Al Nassr", "rating": 84, "position": "CM"},
    {"name": "Aymeric Laporte", "team": "Al Nassr", "rating": 84, "position": "CB"},
    {"name": "N'Golo Kante", "team": "Al Ittihad", "rating": 85, "position": "CM"},
    {"name": "Malcom", "team": "Al Hilal", "rating": 84, "position": "RW"},
]

EXTRA_WORLD_PLAYERS = [
    {"name": "Angel Di Maria", "team": "Benfica", "rating": 83, "position": "RW"},
    {"name": "Nicolas Otamendi", "team": "Benfica", "rating": 82, "position": "CB"},
    {"name": "Kerem Akturkoglu", "team": "Benfica", "rating": 82, "position": "LW"},
    {"name": "Orkun Kokcu", "team": "Benfica", "rating": 83, "position": "CM"},
    {"name": "Diogo Costa", "team": "Porto", "rating": 84, "position": "GK"},
    {"name": "Pepe", "team": "Porto", "rating": 81, "position": "CB"},
    {"name": "Galeno", "team": "Porto", "rating": 81, "position": "LW"},
    {"name": "Evanilson", "team": "Porto", "rating": 82, "position": "ST"},
    {"name": "Viktor Gyokeres", "team": "Sporting CP", "rating": 86, "position": "ST"},
    {"name": "Pedro Goncalves", "team": "Sporting CP", "rating": 83, "position": "RW"},
    {"name": "Morten Hjulmand", "team": "Sporting CP", "rating": 82, "position": "CDM"},
    {"name": "Goncalo Inacio", "team": "Sporting CP", "rating": 82, "position": "CB"},
    {"name": "Brian Brobbey", "team": "Ajax", "rating": 80, "position": "ST"},
    {"name": "Steven Bergwijn", "team": "Ajax", "rating": 81, "position": "LW"},
    {"name": "Jordan Henderson", "team": "Ajax", "rating": 79, "position": "CM"},
    {"name": "Jorrel Hato", "team": "Ajax", "rating": 79, "position": "CB"},
    {"name": "Luuk de Jong", "team": "PSV", "rating": 81, "position": "ST"},
    {"name": "Johan Bakayoko", "team": "PSV", "rating": 81, "position": "RW"},
    {"name": "Joey Veerman", "team": "PSV", "rating": 81, "position": "CM"},
    {"name": "Noa Lang", "team": "PSV", "rating": 80, "position": "LW"},
    {"name": "Santiago Gimenez", "team": "Feyenoord", "rating": 82, "position": "ST"},
    {"name": "Calvin Stengs", "team": "Feyenoord", "rating": 79, "position": "RW"},
    {"name": "Quinten Timber", "team": "Feyenoord", "rating": 79, "position": "CM"},
    {"name": "Dávid Hancko", "team": "Feyenoord", "rating": 80, "position": "CB"},
    {"name": "Mauro Icardi", "team": "Galatasaray", "rating": 82, "position": "ST"},
    {"name": "Dries Mertens", "team": "Galatasaray", "rating": 80, "position": "CAM"},
    {"name": "Lucas Torreira", "team": "Galatasaray", "rating": 80, "position": "CM"},
    {"name": "Davinson Sanchez", "team": "Galatasaray", "rating": 80, "position": "CB"},
    {"name": "Edin Dzeko", "team": "Fenerbahce", "rating": 81, "position": "ST"},
    {"name": "Dusan Tadic", "team": "Fenerbahce", "rating": 81, "position": "LW"},
    {"name": "Fred", "team": "Fenerbahce", "rating": 80, "position": "CM"},
    {"name": "Sebastian Szymanski", "team": "Fenerbahce", "rating": 80, "position": "CAM"},
    {"name": "Ciro Immobile", "team": "Besiktas", "rating": 81, "position": "ST"},
    {"name": "Rafa Silva", "team": "Besiktas", "rating": 81, "position": "CAM"},
    {"name": "Gedson Fernandes", "team": "Besiktas", "rating": 79, "position": "CM"},
    {"name": "Alex Oxlade-Chamberlain", "team": "Besiktas", "rating": 77, "position": "CM"},
    {"name": "Kyogo Furuhashi", "team": "Celtic", "rating": 79, "position": "ST"},
    {"name": "Matt O'Riley", "team": "Celtic", "rating": 79, "position": "CM"},
    {"name": "Callum McGregor", "team": "Celtic", "rating": 78, "position": "CM"},
    {"name": "Cameron Carter-Vickers", "team": "Celtic", "rating": 78, "position": "CB"},
    {"name": "James Tavernier", "team": "Rangers", "rating": 79, "position": "RB"},
    {"name": "Todd Cantwell", "team": "Rangers", "rating": 77, "position": "CAM"},
    {"name": "Danilo", "team": "Rangers", "rating": 77, "position": "ST"},
    {"name": "Jack Butland", "team": "Rangers", "rating": 78, "position": "GK"},
    {"name": "Hans Vanaken", "team": "Club Brugge", "rating": 79, "position": "CM"},
    {"name": "Andreas Skov Olsen", "team": "Club Brugge", "rating": 79, "position": "RW"},
    {"name": "Raphael Onyedika", "team": "Club Brugge", "rating": 77, "position": "CDM"},
    {"name": "Ferran Jutgla", "team": "Club Brugge", "rating": 77, "position": "ST"},
    {"name": "Thorgan Hazard", "team": "Anderlecht", "rating": 78, "position": "LW"},
    {"name": "Jan Vertonghen", "team": "Anderlecht", "rating": 77, "position": "CB"},
    {"name": "Kasper Dolberg", "team": "Anderlecht", "rating": 78, "position": "ST"},
    {"name": "Theo Leoni", "team": "Anderlecht", "rating": 75, "position": "CM"},
    {"name": "Karim Konate", "team": "RB Salzburg", "rating": 78, "position": "ST"},
    {"name": "Oscar Gloukh", "team": "RB Salzburg", "rating": 79, "position": "CAM"},
    {"name": "Amar Dedic", "team": "RB Salzburg", "rating": 78, "position": "RB"},
    {"name": "Mads Bidstrup", "team": "RB Salzburg", "rating": 77, "position": "CM"},
    {"name": "Heorhii Sudakov", "team": "Shakhtar Donetsk", "rating": 80, "position": "CAM"},
    {"name": "Mykola Matviyenko", "team": "Shakhtar Donetsk", "rating": 78, "position": "CB"},
    {"name": "Taras Stepanenko", "team": "Shakhtar Donetsk", "rating": 76, "position": "CDM"},
    {"name": "Danylo Sikan", "team": "Shakhtar Donetsk", "rating": 76, "position": "ST"},
    {"name": "Bruno Petkovic", "team": "Dinamo Zagreb", "rating": 77, "position": "ST"},
    {"name": "Martin Baturina", "team": "Dinamo Zagreb", "rating": 78, "position": "CAM"},
    {"name": "Arijan Ademi", "team": "Dinamo Zagreb", "rating": 75, "position": "CM"},
    {"name": "Stefan Ristovski", "team": "Dinamo Zagreb", "rating": 75, "position": "RB"},
    {"name": "Mohamed Elyounoussi", "team": "Copenhagen", "rating": 78, "position": "LW"},
    {"name": "Viktor Claesson", "team": "Copenhagen", "rating": 77, "position": "RW"},
    {"name": "Diogo Goncalves", "team": "Copenhagen", "rating": 76, "position": "RB"},
    {"name": "Denis Vavro", "team": "Copenhagen", "rating": 76, "position": "CB"},
    {"name": "Endrick", "team": "Palmeiras", "rating": 80, "position": "ST"},
    {"name": "Raphael Veiga", "team": "Palmeiras", "rating": 81, "position": "CAM"},
    {"name": "Gustavo Gomez", "team": "Palmeiras", "rating": 80, "position": "CB"},
    {"name": "Weverton", "team": "Palmeiras", "rating": 79, "position": "GK"},
    {"name": "Pedro", "team": "Flamengo", "rating": 81, "position": "ST"},
    {"name": "Giorgian de Arrascaeta", "team": "Flamengo", "rating": 82, "position": "CAM"},
    {"name": "De La Cruz", "team": "Flamengo", "rating": 80, "position": "CM"},
    {"name": "David Luiz", "team": "Flamengo", "rating": 77, "position": "CB"},
    {"name": "Neymar Jr", "team": "Santos", "rating": 86, "position": "LW"},
    {"name": "Joao Schmidt", "team": "Santos", "rating": 76, "position": "CM"},
    {"name": "Gil", "team": "Santos", "rating": 75, "position": "CB"},
    {"name": "Tomas Rincon", "team": "Santos", "rating": 75, "position": "CDM"},
    {"name": "Miguel Borja", "team": "River Plate", "rating": 79, "position": "ST"},
    {"name": "Franco Mastantuono", "team": "River Plate", "rating": 77, "position": "CAM"},
    {"name": "Ignacio Fernandez", "team": "River Plate", "rating": 78, "position": "CM"},
    {"name": "Paulo Diaz", "team": "River Plate", "rating": 77, "position": "CB"},
    {"name": "Edinson Cavani", "team": "Boca Juniors", "rating": 79, "position": "ST"},
    {"name": "Marcos Rojo", "team": "Boca Juniors", "rating": 76, "position": "CB"},
    {"name": "Cristian Medina", "team": "Boca Juniors", "rating": 77, "position": "CM"},
    {"name": "Kevin Zenon", "team": "Boca Juniors", "rating": 76, "position": "LW"},
]

def load_rating_cache():
    if os.path.exists(RATING_CACHE_FILE):
        try:
            with open(RATING_CACHE_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}

def save_rating_cache(cache):
    try:
        with open(RATING_CACHE_FILE, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, dict):
                    return data
        except Exception:
            return {"users": {}}
    return {"users": {}}

def save_accounts(data):
    try:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def make_tone(freq=440, duration=0.14, volume=0.18, sample_rate=22050):
    frames = int(sample_rate * duration)
    buf = array("h")
    for i in range(frames):
        sample = int(volume * 32767 * math.sin(2 * math.pi * freq * i / sample_rate))
        buf.append(sample)
    return pygame.mixer.Sound(buffer=buf.tobytes())

RATING_OVERRIDES = {
    "Mohamed Salah": 91,
    "Erling Haaland": 90,
    "Rodri": 90,
    "Virgil van Dijk": 90,
    "Bruno Fernandes": 89,
    "Phil Foden": 90,
}

RATING_CACHE = load_rating_cache()

TEAM_RATING_BASE = {
    "Man City": 91,
    "Liverpool": 90,
    "Arsenal": 88,
    "Man United": 86,
    "Chelsea": 85,
    "Tottenham": 84,
    "Newcastle": 82,
    "Aston Villa": 80,
    "Brighton": 79,
    "Brentford": 78,
    "West Ham": 77,
    "Fulham": 76,
    "Everton": 74,
    "Wolves": 73,
    "Leeds United": 72,
    "AFC Bournemouth": 71,
    "Nottingham Forest": 69,
    "Southampton": 68,
    "Burnley": 66,
    "Sunderland": 65,
}

TEAM_OVERALL = {
    "Man City": 94,
    "Liverpool": 93,
    "Arsenal": 91,
    "Man United": 88,
    "Chelsea": 87,
    "Tottenham": 86,
    "Newcastle": 84,
    "Aston Villa": 83,
    "Brighton": 81,
    "Brentford": 80,
    "West Ham": 79,
    "Fulham": 78,
    "Everton": 76,
    "Wolves": 75,
    "Leeds United": 73,
    "AFC Bournemouth": 72,
    "Nottingham Forest": 70,
    "Southampton": 69,
    "Burnley": 67,
    "Sunderland": 66,
}

def normalize_player_name(name):
    if isinstance(name, (list, tuple, set)):
        return " | ".join(normalize_player_name(part) for part in name)
    return str(name)


def probable_rating(name, team, default=70):
    name = normalize_player_name(name)
    if name in RATING_OVERRIDES:
        return RATING_OVERRIDES[name]
    if name in RATING_CACHE:
        return RATING_CACHE[name]
    base = TEAM_RATING_BASE.get(team, 70)
    offset = (abs(hash(name)) % 15) - 7
    rating = int(clamp(base + offset, 50, 95))
    RATING_CACHE[name] = rating
    save_rating_cache(RATING_CACHE)
    return rating

def normalize_entry(entry, idx, team=None):
    if isinstance(entry, (tuple, list)):
        name = normalize_player_name(entry[0])
        num = entry[1] if len(entry) > 1 else idx + 1
        rating = entry[2] if len(entry) > 2 else probable_rating(name, team or "Premier", 70)
    else:
        name = normalize_player_name(entry)
        num = idx + 1
        rating = probable_rating(name, team or "Premier", 70)
    rating = int(max(50, rating))
    return name, num, rating


def lineup_name_number(entry, idx):
    if isinstance(entry, (tuple, list)):
        name = normalize_player_name(entry[0])
        num = entry[1] if len(entry) > 1 else idx + 1
    else:
        name = normalize_player_name(entry)
        num = idx + 1
    return name, num


HALF_SECONDS = 30  # 30 seconds per half (1 minute total)

# Colors
GREEN = (28, 110, 52)
DARK_GREEN = (24, 92, 46)
LIGHT_GREEN = (90, 180, 100)
WHITE = (245, 245, 245)
BLUE = (70, 140, 235)
RED = (230, 80, 80)
YELLOW = (245, 225, 90)
BLACK = (15, 15, 15)
CYAN = (80, 220, 220)
ORANGE = (240, 150, 70)
GRAY = (230, 230, 230)

TEAM_COLORS = {
    "Arsenal": ((200, 0, 0), (240, 240, 240)),
    "Aston Villa": ((120, 0, 90), (160, 200, 240)),
    "AFC Bournemouth": ((160, 0, 0), (20, 20, 20)),
    "Brentford": ((200, 0, 0), (240, 240, 240)),
    "Brighton": ((20, 80, 200), (240, 240, 240)),
    "Burnley": ((120, 0, 90), (160, 200, 240)),
    "Chelsea": ((20, 70, 200), (240, 240, 240)),
    "Crystal Palace": ((200, 0, 0), (20, 70, 200)),
    "Everton": ((20, 60, 160), (240, 240, 240)),
    "Fulham": ((240, 240, 240), (20, 20, 20)),
    "Liverpool": ((180, 0, 0), (240, 240, 240)),
    "Leeds United": ((240, 240, 240), (20, 20, 20)),
    "Man City": ((120, 190, 240), (240, 240, 240)),
    "Man United": ((200, 0, 0), (20, 20, 20)),
    "Newcastle": ((20, 20, 20), (240, 240, 240)),
    "Nottingham Forest": ((180, 0, 0), (240, 240, 240)),
    "Sunderland": ((200, 0, 0), (240, 240, 240)),
    "Tottenham": ((240, 240, 240), (20, 40, 120)),
    "West Ham": ((120, 0, 90), (120, 200, 240)),
    "Wolves": ((230, 170, 40), (20, 20, 20)),
}

TEAM_KITS = {
    "Arsenal": [
        ((200, 0, 0), (240, 240, 240)),
        ((240, 240, 240), (200, 0, 0)),
        ((20, 20, 20), (200, 0, 0)),
    ],
    "Aston Villa": [
        ((120, 0, 90), (160, 200, 240)),
        ((240, 240, 240), (120, 0, 90)),
        ((20, 20, 20), (120, 0, 90)),
    ],
    "AFC Bournemouth": [
        ((160, 0, 0), (20, 20, 20)),
        ((240, 240, 240), (160, 0, 0)),
        ((20, 20, 20), (160, 0, 0)),
    ],
    "Brentford": [
        ((200, 0, 0), (240, 240, 240)),
        ((240, 240, 240), (200, 0, 0)),
        ((20, 20, 20), (200, 0, 0)),
    ],
    "Brighton": [
        ((20, 80, 200), (240, 240, 240)),
        ((240, 240, 240), (20, 80, 200)),
        ((20, 20, 20), (20, 80, 200)),
    ],
    "Burnley": [
        ((120, 0, 90), (160, 200, 240)),
        ((240, 240, 240), (120, 0, 90)),
        ((20, 20, 20), (120, 0, 90)),
    ],
    "Chelsea": [
        ((20, 70, 200), (240, 240, 240)),
        ((240, 240, 240), (20, 70, 200)),
        ((20, 20, 20), (20, 70, 200)),
    ],
    "Crystal Palace": [
        ((200, 0, 0), (20, 70, 200)),
        ((240, 240, 240), (200, 0, 0)),
        ((20, 20, 20), (200, 0, 0)),
    ],
    "Everton": [
        ((20, 60, 160), (240, 240, 240)),
        ((240, 240, 240), (20, 60, 160)),
        ((20, 20, 20), (20, 60, 160)),
    ],
    "Fulham": [
        ((240, 240, 240), (20, 20, 20)),
        ((20, 20, 20), (240, 240, 240)),
        ((200, 0, 0), (240, 240, 240)),
    ],
    "Liverpool": [
        ((180, 0, 0), (240, 240, 240)),
        ((240, 240, 240), (180, 0, 0)),
        ((20, 20, 20), (180, 0, 0)),
    ],
    "Leeds United": [
        ((240, 240, 240), (20, 20, 20)),
        ((20, 20, 20), (240, 240, 240)),
        ((200, 0, 0), (240, 240, 240)),
    ],
    "Man City": [
        ((120, 190, 240), (240, 240, 240)),
        ((240, 240, 240), (120, 190, 240)),
        ((20, 20, 20), (120, 190, 240)),
    ],
    "Man United": [
        ((200, 0, 0), (20, 20, 20)),
        ((240, 240, 240), (200, 0, 0)),
        ((20, 20, 20), (200, 0, 0)),
    ],
    "Newcastle": [
        ((20, 20, 20), (240, 240, 240)),
        ((240, 240, 240), (20, 20, 20)),
        ((20, 20, 20), (200, 0, 0)),
    ],
    "Nottingham Forest": [
        ((180, 0, 0), (240, 240, 240)),
        ((240, 240, 240), (180, 0, 0)),
        ((20, 20, 20), (180, 0, 0)),
    ],
    "Sunderland": [
        ((200, 0, 0), (240, 240, 240)),
        ((240, 240, 240), (200, 0, 0)),
        ((20, 20, 20), (200, 0, 0)),
    ],
    "Tottenham": [
        ((240, 240, 240), (20, 40, 120)),
        ((20, 40, 120), (240, 240, 240)),
        ((20, 20, 20), (240, 240, 240)),
    ],
    "West Ham": [
        ((120, 0, 90), (120, 200, 240)),
        ((240, 240, 240), (120, 0, 90)),
        ((20, 20, 20), (120, 200, 240)),
    ],
    "Wolves": [
        ((230, 170, 40), (20, 20, 20)),
        ((20, 20, 20), (230, 170, 40)),
        ((240, 240, 240), (230, 170, 40)),
    ],
}

def get_team_kits(team):
    if team in TEAM_KITS:
        return TEAM_KITS[team]
    return [TEAM_COLORS.get(team, (BLUE, WHITE))] * 3

TEAM_LEAGUES = {
    "Real Madrid": "La Liga",
    "Barcelona": "La Liga",
    "Atletico Madrid": "La Liga",
    "Athletic Club": "La Liga",
    "Real Sociedad": "La Liga",
    "Real Betis": "La Liga",
    "Bayern Munich": "Bundesliga",
    "Bayer Leverkusen": "Bundesliga",
    "Dortmund": "Bundesliga",
    "RB Leipzig": "Bundesliga",
    "Napoli": "Serie A",
    "Inter": "Serie A",
    "AC Milan": "Serie A",
    "Juventus": "Serie A",
    "Roma": "Serie A",
    "PSG": "Ligue 1",
    "Lille": "Ligue 1",
    "Lyon": "Ligue 1",
    "Marseille": "Ligue 1",
    "Inter Miami": "MLS",
    "Monterrey": "Liga MX",
    "Pachuca": "Liga MX",
    "Al Ittihad": "Saudi Pro League",
    "Al Hilal": "Saudi Pro League",
    "Al Nassr": "Saudi Pro League",
    "Benfica": "Liga Portugal",
    "Porto": "Liga Portugal",
    "Sporting CP": "Liga Portugal",
    "Ajax": "Eredivisie",
    "PSV": "Eredivisie",
    "Feyenoord": "Eredivisie",
    "Galatasaray": "Super Lig",
    "Fenerbahce": "Super Lig",
    "Besiktas": "Super Lig",
    "Celtic": "Scottish Premiership",
    "Rangers": "Scottish Premiership",
    "Club Brugge": "Belgian Pro League",
    "Anderlecht": "Belgian Pro League",
    "RB Salzburg": "Austrian Bundesliga",
    "Shakhtar Donetsk": "Ukrainian Premier League",
    "Dinamo Zagreb": "Croatian League",
    "Copenhagen": "Danish Superliga",
    "Palmeiras": "Brazil Serie A",
    "Flamengo": "Brazil Serie A",
    "Santos": "Brazil Serie A",
    "River Plate": "Argentine Primera",
    "Boca Juniors": "Argentine Primera",
    "Icons": "Icons",
    "GOAT": "GOAT",
}

def get_team_league(team):
    if team in TEAM_LEAGUES:
        return TEAM_LEAGUES[team]
    if team in TEAMS:
        return "Premier League"
    return "World League"


LEAGUE_NATIONS = {
    "Premier League": "England",
    "La Liga": "Spain",
    "Bundesliga": "Germany",
    "Serie A": "Italy",
    "Ligue 1": "France",
    "MLS": "United States",
    "Liga MX": "Mexico",
    "Saudi Pro League": "Saudi Arabia",
    "Liga Portugal": "Portugal",
    "Eredivisie": "Netherlands",
    "Super Lig": "Turkey",
    "Scottish Premiership": "Scotland",
    "Belgian Pro League": "Belgium",
    "Austrian Bundesliga": "Austria",
    "Ukrainian Premier League": "Ukraine",
    "Croatian League": "Croatia",
    "Danish Superliga": "Denmark",
    "Brazil Serie A": "Brazil",
    "Argentine Primera": "Argentina",
    "Icons": "Icons",
    "GOAT": "Legends",
    "World League": "World",
}

PLAYER_NATIONS = {
    "Kylian Mbappe": "France",
    "Erling Haaland": "Norway",
    "Jude Bellingham": "England",
    "Vinicius Junior": "Brazil",
    "Neymar": "Brazil",
    "Mohamed Salah": "Egypt",
    "Harry Kane": "England",
    "Jamal Musiala": "Germany",
    "Lionel Messi": "Argentina",
    "Cristiano Ronaldo": "Portugal",
    "Robert Lewandowski": "Poland",
    "Lamine Yamal": "Spain",
    "Pedri": "Spain",
    "Frenkie de Jong": "Netherlands",
    "Raphinha": "Brazil",
    "Ronald Araujo": "Uruguay",
    "Antoine Griezmann": "France",
    "Jan Oblak": "Slovenia",
    "Julian Alvarez": "Argentina",
    "Nico Williams": "Spain",
    "Takefusa Kubo": "Japan",
    "Alexander Isak": "Sweden",
    "Joshua Kimmich": "Germany",
    "Florian Wirtz": "Germany",
    "Victor Boniface": "Nigeria",
    "Jeremie Frimpong": "Netherlands",
    "Serhou Guirassy": "Guinea",
    "Gregor Kobel": "Switzerland",
    "Victor Osimhen": "Nigeria",
    "Khvicha Kvaratskhelia": "Georgia",
    "Lautaro Martinez": "Argentina",
    "Nicolo Barella": "Italy",
    "Hakan Calhanoglu": "Turkey",
    "Mike Maignan": "France",
    "Rafael Leao": "Portugal",
    "Theo Hernandez": "France",
    "Christian Pulisic": "United States",
    "Dusan Vlahovic": "Serbia",
    "Paulo Dybala": "Argentina",
    "Gianluigi Donnarumma": "Italy",
    "Ousmane Dembele": "France",
    "Achraf Hakimi": "Morocco",
    "Joao Neves": "Portugal",
    "Bradley Barcola": "France",
    "Marquinhos": "Brazil",
    "Karim Benzema": "France",
    "Sadio Mane": "Senegal",
    "Ruben Neves": "Portugal",
    "Aleksandar Mitrovic": "Serbia",
    "Angel Di Maria": "Argentina",
    "Diogo Costa": "Portugal",
    "Lev Yashin": "Icons",
    "Cafu": "Brazil",
    "Franz Beckenbauer": "Germany",
    "Paolo Maldini": "Italy",
    "Roberto Carlos": "Brazil",
    "Xavi": "Spain",
    "Zinedine Zidane": "France",
    "Diego Maradona": "Argentina",
    "Johan Cruyff": "Netherlands",
    "Pele": "Brazil",
    "Ronaldinho": "Brazil",
    "Gianluigi Buffon": "Italy",
    "Franco Baresi": "Italy",
    "Carlos Alberto Torres": "Brazil",
    "Sergio Ramos": "Spain",
    "Andres Iniesta": "Spain",
    "Michel Platini": "France",
    "David Beckham": "England",
    "Ronaldo Nazario": "Brazil",
    "Thierry Henry": "France",
    "George Best": "Northern Ireland",
    "Garrincha": "Brazil",
}


def get_team_nation(team):
    return LEAGUE_NATIONS.get(get_team_league(team), "World")


def get_player_nation(name, team):
    return PLAYER_NATIONS.get(normalize_player_name(name), get_team_nation(team))

STADIUMS = {
    "Arsenal": "Emirates Stadium",
    "Aston Villa": "Villa Park",
    "AFC Bournemouth": "Vitality Stadium",
    "Brentford": "Gtech Community Stadium",
    "Brighton": "Amex Stadium",
    "Burnley": "Turf Moor",
    "Chelsea": "Stamford Bridge",
    "Crystal Palace": "Selhurst Park",
    "Everton": "Goodison Park",
    "Fulham": "Craven Cottage",
    "Liverpool": "Anfield",
    "Leeds United": "Elland Road",
    "Man City": "Etihad Stadium",
    "Man United": "Old Trafford",
    "Newcastle": "St. James' Park",
    "Nottingham Forest": "City Ground",
    "Sunderland": "Stadium of Light",
    "Tottenham": "Tottenham Hotspur Stadium",
    "West Ham": "London Stadium",
    "Wolves": "Molineux",
}

TEAMS = [
    "Arsenal",
    "Aston Villa",
    "AFC Bournemouth",
    "Brentford",
    "Brighton",
    "Burnley",
    "Chelsea",
    "Crystal Palace",
    "Everton",
    "Fulham",
    "Liverpool",
    "Leeds United",
    "Man City",
    "Man United",
    "Newcastle",
    "Nottingham Forest",
    "Sunderland",
    "Tottenham",
    "West Ham",
    "Wolves",
]

DEFAULT_LINEUP = [
    ("GK", 1),
    ("RB", 2),
    ("RCB", 3),
    ("LCB", 4),
    ("LB", 5),
    ("RM", 6),
    ("RCM", 7),
    ("LCM", 8),
    ("LM", 9),
    ("RS", 10),
    ("LS", 11),
]

ROSTER_DATA = {
    "Arsenal": [
        ("David Raya", 1),
        ("Kepa Arrizabalaga", 13),
        ("Tommy Setford", 35),
        ("William Saliba", 2),
        ("Cristhian Mosquera", 3),
        ("Ben White", 4),
        ("Piero Hincapié", 5),
        ("Jurrien Timber", 12),
        ("Riccardo Calafiori", 33),
        ("Myles Lewis-Skelly", 49),
        ("Martin Ødegaard", 8),
        ("Eberechi Eze", 10),
        ("Christian Nørgaard", 16),
        ("Mikel Merino", 23),
        ("Martín Zubimendi", 36),
        ("Declan Rice", 41),
        ("Noni Madueke", 20),
        ("Bukayo Saka", 7),
        ("Gabriel Martinelli", 11),
        ("Viktor Gyökeres", 14),
        ("Leandro Trossard", 19),
        ("Gabriel Jesus", 9),
    ],
    "Aston Villa": [
        ("Emiliano Martínez", 23),
        ("Marco Bizot", 40),
        ("James Wright", 64),
        ("Matty Cash", 2),
        ("Victor Lindelöf", 3),
        ("Ezri Konsa", 4),
        ("Tyrone Mings", 5),
        ("Ross Barkley", 6),
        ("John McGinn", 7),
        ("Youri Tielemans", 8),
        ("Damian Martinez Romero", 15),
        ("Amadou Onana", 17),
        ("Douglas Luiz", 22),
        ("Oliver Watkins", 9),
        ("Andres Garcia Robledo", 10),
        ("Ian Maatsen", 13),
        ("Morgan Rogers", 19),
        ("Jadon Sancho", 20),
    ],
    "AFC Bournemouth": [
        ("Dorđe Petrović", 1),
        ("Fraser Forster", 17),
        ("Will Dennis", 40),
        ("Adrien Truffert", 3),
        ("Marcos Senesi", 5),
        ("Julio Soler", 6),
        ("Adam Smith", 15),
        ("Álex Jiménez", 20),
        ("James Hill", 23),
        ("Veljko Milosavljevic", 44),
        ("Matai Akinmboni", 45),
        ("Lewis Cook", 4),
        ("Alex Scott", 8),
        ("Ryan Christie", 10),
        ("Tyler Adams", 12),
        ("David Brooks", 7),
        ("Ben Gannon-Doak", 11),
        ("Marcus Tavernier", 16),
        ("Amine Adli", 21),
        ("Evanilson", 9),
        ("Eli Kroupi", 22),
        ("Enes Ünal", 26),
        ("Rayan", 37),
    ],
    "Brentford": [
        ("Caoimhín Kelleher", 1),
        ("Hákon Valdimarsson", 12),
        ("Matthew Cox", 13),
        ("Ellery Balcombe", 31),
        ("Julian Eyestone", 41),
        ("Aaron Hickey", 2),
        ("Rico Henry", 3),
        ("Sepp van den Berg", 4),
        ("Ethan Pinnock", 5),
        ("Kristoffer Ajer", 20),
        ("Nathan Collins", 22),
        ("Mads Roerslev", 30),
        ("Jordan Henderson", 6),
        ("Kevin Schade", 7),
        ("Mathias Jensen", 8),
        ("Frank Onyeka", 15),
        ("Antoni Milambo", 17),
        ("Yehor Yarmoliuk", 18),
        ("Keane Lewis-Potter", 23),
        ("Mikkel Damsgaard", 24),
        ("Myles Peart-Harris", 25),
        ("Yunus Emre Konak", 26),
        ("Vitaly Janelt", 27),
        ("Paris Maghoma", 32),
        ("Igor Thiago", 9),
        ("Yoane Wissa", 11),
        ("Dango Ouattara", 19),
        ("Michael Kayode", 33),
        ("Gustavo Nunes", 39),
        ("Benjamin Arthur", 43),
        ("Romelle Donovan", 45),
    ],
    "Brighton": [
        ("Bart Verbruggen", 1),
        ("Jason Steele", 23),
        ("Tom McGill", 38),
        ("Tariq Lamptey", 2),
        ("Igor Julio", 3),
        ("Adam Webster", 4),
        ("Lewis Dunk", 5),
        ("Olivier Boscagli", 21),
        ("Matts Wieffer", 29),
        ("Joel Veltman", 34),
        ("Jan Paul van Hecke", 6),
        ("Solly March", 7),
        ("Brajan Gruda", 8),
        ("Georginio Rutter", 10),
        ("Carlos Baleba", 17),
        ("James Milner", 20),
        ("Kaoru Mitoma", 22),
        ("Ferdi Kadıoğlu", 24),
        ("Yasin Ayari", 26),
        ("Jeremy Sarmiento", 32),
        ("Matt O'Riley", 33),
        ("Andy Moran", 35),
        ("Malick Yalcouye", 36),
        ("Stefanos Tzimas", 9),
        ("Yankuba Minteh", 11),
        ("Charalampos Kostoulas", 19),
        ("Diego Gómez", 25),
        ("Facundo Buonanotte", 40),
        ("Diego Coppola", 42),
    ],
    "Chelsea": [
        ("Robert Sánchez", 1),
        ("Filip Jørgensen", 12),
        ("Gabriel Slonina", 44),
        ("Marc Cucurella", 3),
        ("Tosin Adarabioyo", 4),
        ("Benoît Badiashile", 5),
        ("Levi Colwill", 6),
        ("Jorrel Hato", 21),
        ("Trevoh Chalobah", 23),
        ("Reece James", 24),
        ("Malo Gusto", 27),
        ("Wesley Fofana", 29),
        ("Aaron Anselmino", 30),
        ("Josh Acheampong", 34),
        ("Enzo Fernández", 8),
        ("Andrey Santos", 17),
        ("João Pedro", 20),
        ("Moises Caicedo", 25),
        ("Romeo Lavia", 45),
        ("Tyrique George", 32),
        ("Jamie Gittens", 11),
        ("Pedro Neto", 7),
        ("Liam Delap", 9),
        ("Cole Palmer", 10),
        ("Dario Essugo", 14),
        ("Nicolas Jackson", 15),
        ("Marc Guiu", 38),
    ],
    "Crystal Palace": [
        ("Vicente Guaita", 1),
        ("Sam Johnstone", 12),
        ("Jack Bonham", 22),
        ("Nigel Hoare", 43),
        ("Nathaniel Clyne", 2),
        ("Joachim Andersen", 3),
        ("Cheick Doucouré", 4),
        ("Marc Guéhi", 5),
        ("Tyrick Mitchell", 6),
        ("Radosław Majecki", 13),
        ("Joel Ward", 16),
        ("Conor Gallagher", 17),
        ("Eberechi Eze", 7),
        ("Michael Olise", 10),
        ("Jeffrey Schlupp", 11),
        ("Jairo Riedewald", 14),
        ("Jordan Ayew", 18),
        ("James McArthur", 19),
        ("Luka Milivojević", 20),
        ("Cheick Traoré", 23),
        ("Odsonne Édouard", 9),
        ("Wilfried Zaha", 15),
        ("Nathan Ferguson", 25),
        ("Christian Benteke", 26),
        ("Malcolm Ebiowei", 28),
    ],
    "Everton": [
        ("Jordan Pickford", 1),
        ("Mark Travers", 12),
        ("Tom King", 31),
        ("Harry Tyrer", 38),
        ("Nathan Patterson", 2),
        ("Michael Keane", 5),
        ("James Tarkowski", 6),
        ("Jake O’Brien", 15),
        ("Vitalii Mykolenko", 16),
        ("Seamus Coleman", 23),
        ("Jarrad Branthwaite", 32),
        ("Adam Aznou", 39),
        ("Dwight McNeil", 7),
        ("Kiernan Dewsbury-Hall", 22),
        ("Carlos Alcaraz", 24),
        ("Idrissa Gueye", 27),
        ("Merlin Röhl", 34),
        ("James Garner", 37),
        ("Tim Iroegbunam", 42),
        ("Beto", 9),
        ("Iliman Ndiaye", 10),
        ("Thierno Barry", 11),
        ("Jack Grealish", 18),
        ("Tyrique George", 19),
    ],
    "Fulham": [
        ("Bernd Leno", 1),
        ("Marek Rodák", 12),
        ("Joe McCarthy", 31),
        ("Luke Southwood", 40),
        ("Kenny Tete", 2),
        ("Antonee Robinson", 3),
        ("Joachim Andersen", 4),
        ("Tosin Adarabioyo", 5),
        ("Terence Kongolo", 6),
        ("Kevin Mbabu", 16),
        ("Carlos Vinicius", 17),
        ("Tim Ream", 18),
        ("Ruben Loftus-Cheek", 24),
        ("Andreas Pereira", 7),
        ("Joao Palhinha", 8),
        ("Aleksandar Mitrović", 9),
        ("Willian Arão", 11),
        ("Harrison Reed", 14),
        ("Manor Solomon", 15),
        ("Fabio Carvalho", 20),
        ("Joao Gomes", 29),
        ("Ademola Lookman", 30),
        ("Nathan Tella", 35),
    ],
    "Leeds United": [
        ("Lucas Perri", 1),
        ("Illan Meslier", 16),
        ("Karl Darlow", 26),
        ("Alex Cairns", 21),
        ("Jayden Bogle", 2),
        ("Gabriel Gudmundsson", 3),
        ("Ethan Ampadu", 4),
        ("Pascal Struijk", 5),
        ("Joe Rodon", 6),
        ("James Justin", 24),
        ("Dan James", 7),
        ("Sean Longstaff", 8),
        ("Brenden Aaronson", 11),
        ("Anton Stach", 18),
        ("Noah Okafor", 19),
        ("Jack Harrison", 20),
        ("Ao Tanaka", 22),
        ("Willy Gnonto", 29),
        ("Dominic Calvert-Lewin", 9),
        ("Joel Piroe", 10),
        ("Lukas Nmecha", 14),
    ],
    "Liverpool": [
        ("Alisson Becker", 1),
        ("Caoimhín Kelleher", 13),
        ("Adrián", 12),
        ("Marcelo Pitaluga", 31),
        ("Trent Alexander-Arnold", 2),
        ("Virgil van Dijk", 3),
        ("Ibrahima Konaté", 4),
        ("Joel Matip", 5),
        ("Kostas Tsimikas", 12),
        ("Andy Robertson", 17),
        ("Nat Phillips", 32),
        ("Sepp van den Berg", 34),
        ("Fabinho", 8),
        ("Jordan Henderson", 14),
        ("Alexis Mac Allister", 18),
        ("James Milner", 20),
        ("Thiago Alcântara", 26),
        ("Harvey Elliott", 28),
        ("Stefan Bajcetic", 35),
        ("Luis Díaz", 7),
        ("Darwin Núñez", 9),
        ("Mohamed Salah", 10),
        ("Diogo Jota", 11),
    ],
}

LEGACY_LINEUPS = {
    # Batch: Arsenal, Aston Villa, Brentford, Brighton, Burnley
    "Arsenal": [
        ("David Raya", 1),
        ("William Saliba", 2),
        ("Ben White", 4),
        ("Piero Hincapie", 5),
        ("Riccardo Calafiori", 33),
        ("Martin Odegaard", 8),
        ("Christian Norgaard", 16),
        ("Declan Rice", 41),
        ("Bukayo Saka", 7),
        ("Gabriel Jesus", 9),
        ("Gabriel Martinelli", 11),
    ],
    "Aston Villa": [
        ("Emiliano Martinez", 23),
        ("Matty Cash", 2),
        ("Ezri Konsa", 4),
        ("Tyrone Mings", 5),
        ("Lucas Digne", 12),
        ("John McGinn", 7),
        ("Youri Tielemans", 8),
        ("Boubacar Kamara", 44),
        ("Ollie Watkins", 11),
        ("Jadon Sancho", 19),
        ("Leon Bailey", 31),
    ],
    "Brentford": [
        ("Caoimhin Kelleher", 1),
        ("Aaron Hickey", 2),
        ("Ethan Pinnock", 5),
        ("Nathan Collins", 22),
        ("Rico Henry", 3),
        ("Mathias Jensen", 8),
        ("Vitaly Janelt", 27),
        ("Mikkel Damsgaard", 24),
        ("Kevin Schade", 7),
        ("Yoane Wissa", 11),
        ("Igor Thiago", 9),
    ],
    "Brighton": [
        ("Bart Verbruggen", 1),
        ("Tariq Lamptey", 2),
        ("Lewis Dunk", 5),
        ("Jan Paul van Hecke", 6),
        ("Pervis Estupinan", 30),
        ("James Milner", 20),
        ("Carlos Baleba", 17),
        ("Matt O'Riley", 33),
        ("Stefanos Tzimas", 9),
        ("Georginio Rutter", 10),
        ("Kaoru Mitoma", 22),
    ],
    "Burnley": [
        ("Martin Dubravka", 1),
        ("Kyle Walker", 2),
        ("Quilindschy Hartman", 3),
        ("Joe Worrall", 4),
        ("Maxime Esteve", 5),
        ("Lesley Ugochukwu", 8),
        ("Florentino Luis", 16),
        ("Josh Cullen", 24),
        ("Lyle Foster", 9),
        ("Marcus Edwards", 10),
        ("Jaidon Anthony", 11),
    ],
    # Batch: AFC Bournemouth, Chelsea, Crystal Palace, Everton, Fulham
    "AFC Bournemouth": [
        ("Djorde Petrovic", 1),
        ("Adrien Truffert", 3),
        ("Lewis Cook", 4),
        ("Marcos Senesi", 5),
        ("Julio Soler", 6),
        ("David Brooks", 7),
        ("Alex Scott", 8),
        ("Evanilson", 9),
        ("Ryan Christie", 10),
        ("Ben Doak", 11),
        ("Tyler Adams", 12),
    ],
    "Chelsea": [
        ("Robert Sanchez", 1),
        ("Tosin Adarabioyo", 4),
        ("Levi Colwill", 6),
        ("Marc Cucurella", 3),
        ("Moises Caicedo", 25),
        ("Enzo Fernandez", 8),
        ("Cole Palmer", 10),
        ("Pedro Neto", 7),
        ("Liam Delap", 9),
        ("Joao Pedro", 20),
        ("Reece James", 24),
    ],
    "Crystal Palace": [
        ("Dean Henderson", 1),
        ("Daniel Munoz", 2),
        ("Tyrick Mitchell", 3),
        ("Maxence Lacroix", 5),
        ("Ismaila Sarr", 7),
        ("Jefferson Lerma", 8),
        ("Yeremy Pino", 10),
        ("Brennan Johnson", 11),
        ("Jean-Philippe Mateta", 14),
        ("Adam Wharton", 20),
        ("Chris Richards", 26),
    ],
    "Everton": [
        ("Jordan Pickford", 1),
        ("Nathan Patterson", 2),
        ("Michael Keane", 5),
        ("James Tarkowski", 6),
        ("Vitalii Mykolenko", 16),
        ("James Garner", 37),
        ("Kiernan Dewsbury-Hall", 22),
        ("Carlos Alcaraz", 24),
        ("Iliman Ndiaye", 10),
        ("Beto", 9),
        ("Thierno Barry", 11),
    ],
    "Fulham": [
        ("Bernd Leno", 1),
        ("Kenny Tete", 2),
        ("Calvin Bassey", 3),
        ("Joachim Andersen", 5),
        ("Harrison Reed", 6),
        ("Raul Jimenez", 7),
        ("Harry Wilson", 8),
        ("Rodrigo Muniz", 9),
        ("Sander Berge", 16),
        ("Emile Smith Rowe", 32),
        ("Antonee Robinson", 33),
    ],
    # Batch: Nottingham Forest, Sunderland, Tottenham, West Ham, Wolves
    "Nottingham Forest": [
        ("John Victor", 13),
        ("Neco Williams", 3),
        ("Morato", 4),
        ("Murillo", 5),
        ("Ola Aina", 34),
        ("Ibrahim Sangare", 6),
        ("Elliot Anderson", 8),
        ("Morgan Gibbs-White", 10),
        ("Callum Hudson-Odoi", 7),
        ("Taiwo Awoniyi", 9),
        ("Dan Ndoye", 14),
    ],
    "Sunderland": [
        ("Anthony Patterson", 1),
        ("Dennis Cirkin", 3),
        ("Daniel Ballard", 5),
        ("Lutsharel Geertruida", 6),
        ("Luke O'Nien", 13),
        ("Dan Neil", 4),
        ("Habib Diarra", 19),
        ("Granit Xhaka", 34),
        ("Chemsdine Talbi", 7),
        ("Brian Brobbey", 9),
        ("Romaine Mundle", 14),
    ],
    "Tottenham": [
        ("Guglielmo Vicario", 1),
        ("Pedro Porro", 23),
        ("Cristian Romero", 17),
        ("Micky van de Ven", 37),
        ("Destiny Udogie", 13),
        ("Yves Bissouma", 8),
        ("James Maddison", 10),
        ("Pape Matar Sarr", 29),
        ("Dominic Solanke", 19),
        ("Brennan Johnson", 22),
        ("Dejan Kulusevski", 21),
    ],
    "West Ham": [
        ("Alphonse Areola", 23),
        ("Kyle Walker-Peters", 2),
        ("Maximilian Kilman", 3),
        ("Nayef Aguerd", 5),
        ("Emerson", 33),
        ("Edson Alvarez", 4),
        ("James Ward-Prowse", 8),
        ("Tomas Soucek", 28),
        ("Jarrod Bowen", 20),
        ("Callum Wilson", 9),
        ("Niclas Fullkrug", 11),
    ],
    "Wolves": [
        ("Jose Sa", 1),
        ("Matt Doherty", 2),
        ("Hugo Bueno", 3),
        ("Santiago Bueno", 4),
        ("Toti Gomes", 24),
        ("Andre", 7),
        ("Joao Gomes", 8),
        ("Jean-Ricner Bellegarde", 27),
        ("Adam Armstrong", 9),
        ("Hwang Hee-chan", 11),
        ("Tolu Arokodare", 14),
    ],
    # Batch: Leeds, Liverpool, Man City, Man United, Newcastle
    "Leeds United": [
        ("Illan Meslier", 1),
        ("Jayden Bogle", 2),
        ("Junior Firpo", 3),
        ("Ethan Ampadu", 4),
        ("Pascal Struijk", 5),
        ("Joe Rodon", 6),
        ("Dan James", 7),
        ("Joe Rothwell", 8),
        ("Patrick Bamford", 9),
        ("Joel Piroe", 10),
        ("Brenden Aaronson", 11),
    ],
    "Liverpool": [
        ("Alisson Becker", 1, 88),
        ("Virgil van Dijk", 4, 90),
        ("Ibrahima Konate", 5, 83),
        ("Milos Kerkez", 6, 80),
        ("Andy Robertson", 26, 84),
        ("Florian Wirtz", 7, 86),
        ("Dominik Szoboszlai", 8, 88),
        ("Alexis Mac Allister", 10, 87),
        ("Mohamed Salah", 11, 91),
        ("Alexander Isak", 9, 86),
        ("Hugo Ekitike", 22, 80),
    ],
    "Man City": [
        ("James Trafford", 1, 70),
        ("Ruben Dias", 3, 88),
        ("John Stones", 5, 86),
        ("Nathan Ake", 6, 84),
        ("Rayan Ait-Nouri", 21, 79),
        ("Rodri", 16, 90),
        ("Tijjani Reijnders", 4, 81),
        ("Rayan Cherki", 10, 80),
        ("Jeremy Doku", 11, 86),
        ("Phil Foden", 47, 90),
        ("Erling Haaland", 9, 90),
    ],
    "Man United": [
        ("Altay Bayindir", 1, 75),
        ("Diogo Dalot", 2, 80),
        ("Noussair Mazraoui", 3, 79),
        ("Matthijs de Ligt", 4, 88),
        ("Harry Maguire", 5, 82),
        ("Lisandro Martinez", 6, 86),
        ("Mason Mount", 7, 84),
        ("Bruno Fernandes", 8, 89),
        ("Matheus Cunha", 10, 82),
        ("Joshua Zirkzee", 11, 80),
        ("Tyrell Malacia", 12, 79),
    ],
    "Newcastle": [
        ("Nick Pope", 1),
        ("Kieran Trippier", 2),
        ("Lewis Hall", 3),
        ("Sven Botman", 4),
        ("Fabian Schar", 5),
        ("Joelinton", 7),
        ("Sandro Tonali", 8),
        ("Anthony Gordon", 10),
        ("Harvey Barnes", 11),
        ("Will Osula", 18),
        ("Anthony Elanga", 20),
    ],
}

TEAM_LINEUPS = LEGACY_LINEUPS
BASE_FANTASY_LINEUPS = json.loads(json.dumps(LEGACY_LINEUPS))
BASE_FANTASY_ROSTERS = json.loads(json.dumps(ROSTER_DATA))





def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def get_team_overall(team):
    return TEAM_OVERALL.get(team, 72)


@dataclass
class Player:
    name: str
    x: float
    y: float
    team: str  # "H" or "A"
    role: str
    speed: float
    vx: float = 0.0
    vy: float = 0.0
    number: int = 0
    rating: int = 70
    target_x: float = None
    target_y: float = None
    has_ball: bool = False
    home_x: float = 0
    home_y: float = 0
    traits: tuple = field(default_factory=tuple)
    chemistry: int = 0

    def move_toward(self, tx, ty, spd=None):
        if spd is None:
            spd = self.speed
        dx = tx - self.x
        dy = ty - self.y
        d = math.hypot(dx, dy)
        if d < 0.01:
            self.vx *= PLAYER_FRICTION
            self.vy *= PLAYER_FRICTION
            self.x += self.vx
            self.y += self.vy
            return
        desired_vx = (dx / d) * spd
        desired_vy = (dy / d) * spd
        self.vx += (desired_vx - self.vx) * PLAYER_ACCEL
        self.vy += (desired_vy - self.vy) * PLAYER_ACCEL
        self.x += self.vx
        self.y += self.vy


@dataclass
class Ball:
    x: float
    y: float
    vx: float = 0
    vy: float = 0

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= BALL_DECAY
        self.vy *= BALL_DECAY
        if abs(self.vx) < 0.02:
            self.vx = 0
        if abs(self.vy) < 0.02:
            self.vy = 0


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("FC Legends")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 20)
        self.big = pygame.font.SysFont("Arial", 26)
        self.small = pygame.font.SysFont("Arial", 14)

        self.state = "ACCOUNT_HOME"  # ACCOUNT_HOME | ACCOUNT_CREATE | ACCOUNT_LOGIN | ACCOUNT_DEV_LOGIN | CLOUD_SETTINGS | MODE_SELECT | TEAM_SELECT | PLAYER_SELECT | LEAGUE | LINEUP | MATCH_SCENE | LIVE | ACADEMY | FANTASY_BUILDER | FANTASY_TEAM_NAME | PACK_SHOP | MY_PACKS | PACK_ODDS | PACK_OPENING | PACK_SUMMARY | FANTASY_SBC | FANTASY_OBJECTIVES | FANTASY_SBC_BUILD | FANTASY_COLLECTION | FANTASY_COMPETITIONS | FANTASY_PLAYER_PICK | FANTASY_EVOLUTIONS | FANTASY_CHAMPIONS_BRACKET | FANTASY_MARKET | FANTASY_DRAFT | FANTASY_CLUB | DEV_REGISTERED_USERS | ONLINE_TOURNAMENTS
        self.game_mode = "CAREER"
        self.active_teams = TEAMS[:]
        self.fantasy_team_name = "Fantasy FC"
        self.accounts_data = load_accounts()
        self.active_account = None
        self.account_storage_mode = "CLOUD"
        self.app_settings = load_app_settings()
        self.app_version_info = load_app_version()
        self.app_version = self.app_version_info.get("version", "1.0.0")
        self.cloud_api_base = self.app_settings["cloud_api_url"].rstrip("/")
        self.cloud_token = None
        self.cloud_user_cache = None
        self.cloud_registered_users = []
        self.cloud_runtime_config = {"announcement": "", "maintenance_mode": False, "disabled_modes": {}}
        self.dev_admin_status = {"ok": False, "settings": {}, "metrics": {}}
        self.cloud_status_label = "Connected to Cloud" if self.cloud_api_base else "Cloud Not Configured"
        self.reconnect_button_rect = None
        self.cloud_settings_inputs = {
            "cloud_enabled": True,
            "cloud_api_url": self.app_settings.get("cloud_api_url", "http://127.0.0.1:8080"),
        }
        self.cloud_settings_index = 0
        self.account_auth_mode = "HOME"
        self.account_menu_index = 0
        self.account_field_index = 0
        self.account_message = ""
        self.account_inputs = {"display_name": "", "username": "", "password": "", "developer_code": ""}
        self.mode_select_index = 0
        self.registered_users_index = 0
        self.dev_console_tab = 0
        self.dev_search_query = ""
        self.dev_action_message = ""
        self.dev_coin_delta_index = 1
        self.dev_pack_index = 0
        self.dev_card_index = 0
        self.dev_announcement_input = ""
        self.profile_autosave_timer = 0.0
        self.fantasy_budget = 400
        self.fantasy_roster = []
        self.fantasy_pool = []
        self.fantasy_index = 0
        self.fantasy_replaced_team = None
        self.fantasy_coins = 3000
        self.last_pack = []
        self.show_pack_shop = False
        self.pack_shop_index = 0
        self.pack_shop_return_state = "LEAGUE"
        self.my_packs = []
        self.my_packs_index = 0
        self.pack_detail_pack_id = "gold"
        self.pack_detail_return_state = "PACK_SHOP"
        self.pack_open_return_state = "LEAGUE"
        self.walkout_timer = 0.0
        self.walkout_index = 0
        self.pack_summary_timer = 0.0
        self.fantasy_competitions = {}
        self.fantasy_objectives = {}
        self.fantasy_season_xp = 0
        self.fantasy_season_claimed = 0
        self.fantasy_sbc_index = 0
        self.fantasy_objective_index = 0
        self.fantasy_sbc_active = None
        self.fantasy_sbc_slots = []
        self.fantasy_sbc_col = 0
        self.fantasy_sbc_idx = 0
        self.fantasy_collection_index = 0
        self.fantasy_collection_filter = 0
        self.fantasy_collection_sort = 0
        self.fantasy_favorites = []
        self.fantasy_evolution_index = 0
        self.fantasy_evolution_choice = 0
        self.fantasy_fixture_label = "Division Match"
        self.fantasy_competition_index = 0
        self.fantasy_active_competition = "division"
        self.fantasy_match_competition = "division"
        self.online_division_data = {"entry": {}, "leaderboard": []}
        self.online_division_index = 0
        self.online_division_message = ""
        self.online_tournament_data = {"entry": {}, "leaderboard": []}
        self.online_tournament_index = 0
        self.online_tournament_message = ""
        self.fantasy_player_pick_options = []
        self.fantasy_player_pick_index = 0
        self.fantasy_player_pick_title = "Player Pick"
        self.fantasy_chemistry_total = 0
        self.fantasy_chemistry_map = {}
        self.fantasy_chemistry_breakdown = {}
        self.fantasy_chemistry_links = []
        self.fantasy_club_custom = {"badge": 0, "primary": 0, "secondary": 5, "stadium": 0}
        self.fantasy_club_cursor = 0
        self.fantasy_share_input = ""
        self.fantasy_share_message = ""
        self.fantasy_market_offers = []
        self.fantasy_market_index = 0
        self.pack_event_index = -1
        self.current_pack_event = {}
        self.fantasy_draft_round = 0
        self.fantasy_draft_index = 0
        self.fantasy_draft_options = []
        self.fantasy_draft_roster = []
        self.fantasy_draft_active = False
        self.fantasy_draft_saved_roster = []
        self.fantasy_draft_saved_lineup = []
        self.fantasy_draft_saved_reserves = []
        self.fantasy_draft_saved_player_index = 0
        self.event_evo_tokens = 0
        self.current_theme = "Open"
        self.sound_enabled = False
        self.walkout_sounds = {}
        self.user_team = None
        self.user_player_index = None
        self.selected_index = 0
        self.selected_player_index = 0
        self.show_tactics_board = True
        self.show_lineups = False
        self.show_stats_panel = False
        self.home_kit_index = 0
        self.away_kit_index = 1
        self.league_page = "HOME"
        self.press_level = 2
        self.line_level = 2
        self.tempo_level = 2
        self.full_time_pending = False
        self.full_time_timer = 0.0
        self.match_scene_title = ""
        self.match_scene_subtitle = ""
        self.match_scene_moment = ""
        self.match_scene_continue = "LIVE"
        self.match_scene_timer = 0.0
        self.match_scene_total = 0.0
        self.match_player_stats = {}
        self.show_calendar = False
        self.show_cup_bracket = False
        self.show_academy = False
        self.academy_intake_done = False
        self.academy_index = 0
        self.user_squad = []
        self.user_starting = []
        self.user_bench = []
        self.user_reserves = []
        self.lineup_col = 0
        self.lineup_idx = 0
        self.lineup_pick = None
        self.pending_fixture = None
        self.dragging_lineup = None
        self.lineup_rects = {}
        self.match_probabilities = None
        # career
        self.season = 1
        self.user_budget = 120
        self.user_form = 1.0
        self.user_injuries = 0
        self.user_match_form = 1.0
        self.career_trophies = {"LEAGUE": 0, "FA": 0, "LC": 0}
        # cups
        self.cups = {}
        self.cup_schedule = {}
        self.current_competition = "LEAGUE"
        self.cup_round_winners = None
        # transfers
        self.transfer_window = False
        self.transfer_pool = []
        self.transfer_offers = []
        self.week_index = 0
        self.fixtures = []
        self.table = {}

        self.season_stats = {}
        self.player_awards = {}
        self.last_season_awards = {}
        self.last_assist_candidate = None
        self.last_assist_team = None
        self.half_season_boosted = False
        self.academy = []

        self.score_h = 0
        self.score_a = 0
        self.message = ""
        self.tactic = 1
        self.tackle_cooldown = 0
        self.ai_pass_cooldown = 0
        self.last_touch_team = "H"
        self.last_touch_name = "Home"
        self.kickoff_pending = True
        self.kickoff_team = "H"
        self.kickoff_player = None
        self.set_piece_pending = False
        self.set_piece_taker = None
        self.set_piece_type = None
        self.ball_free_ticks = 0
        self.half = 1
        self.match_time = 0.0
        self.last_ticks = pygame.time.get_ticks()

        self.commentary = []
        self.commentary_flash = ""
        self.commentary_timer = 0
        self.next_insight_time = 15.0

        self.home = []
        self.away = []
        self.ball = Ball(WIDTH / 2, HEIGHT / 2)
        self.controlled = None

        self.current_home = ""
        self.current_away = ""
        self.user_is_home = True

        self.stats = {
            "H": {"pos_time": 0.0, "shots": 0, "pass_att": 0, "pass_cmp": 0},
            "A": {"pos_time": 0.0, "shots": 0, "pass_att": 0, "pass_cmp": 0},
        }
        self.next_insight_time = 15.0
        self.commentary_insight("pre")
        self.pending_pass_team = None

        self.reset_positions(kickoff=True)
        self.add_commentary("Select a mode to start")
        self.init_audio()
        self.init_fantasy_objectives()

    # --- League ---
    def init_league(self):
        self.reset_season_stats()
        self.academy_intake_done = False
        teams = self.active_teams if self.active_teams else TEAMS
        self.table = {
            t: {"P": 0, "W": 0, "D": 0, "L": 0, "GF": 0, "GA": 0, "GD": 0, "PTS": 0}
            for t in teams
        }
        self.fixtures = self.build_schedule(teams)
        self.week_index = 0
        self.init_cups()
        self.build_transfer_pool()
        self.refresh_transfer_market()
        self.build_user_squad()

    def hash_password(self, password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def reset_account_inputs(self):
        self.account_inputs = {"display_name": "", "username": "", "password": "", "developer_code": ""}
        self.account_field_index = 0
        self.account_message = ""

    def auth_fields_for_state(self, state=None):
        state = state or self.state
        if state == "ACCOUNT_CREATE":
            return ["display_name", "username", "password", "developer_code"]
        if state == "ACCOUNT_DEV_LOGIN":
            return ["username", "password", "developer_code"]
        if state == "ACCOUNT_LOGIN":
            return ["username", "password"]
        return []

    def using_cloud_accounts(self):
        return True

    def local_account_record(self, username=None):
        username = (username or self.active_account or "").strip().lower()
        if not username:
            return None
        users = self.accounts_data.get("users", {})
        record = users.get(username)
        if isinstance(record, dict):
            return record
        return None

    def serialize_local_account(self, record, include_snapshots=False):
        if not record:
            return None
        fantasy_snapshot = record.get("fantasy_snapshot") if include_snapshots else None
        fantasy_roster = fantasy_snapshot.get("fantasy_roster", []) if isinstance(fantasy_snapshot, dict) else []
        cloud_state = record.get("cloud_state", "LOCAL_ONLY")
        payload = {
            "display_name": record.get("display_name", ""),
            "username": record.get("username", ""),
            "is_developer": bool(record.get("is_developer")),
            "last_mode": record.get("last_mode", "CAREER"),
            "storage_mode": "LOCAL",
            "cloud_state": cloud_state,
            "fantasy_summary": {
                "has_save": bool(record.get("fantasy_snapshot")),
                "team_name": fantasy_snapshot.get("fantasy_team_name") if isinstance(fantasy_snapshot, dict) else None,
                "cards": len(fantasy_roster) if isinstance(fantasy_roster, list) else 0,
                "coins": fantasy_snapshot.get("fantasy_coins", 0) if isinstance(fantasy_snapshot, dict) else 0,
            },
        }
        if include_snapshots:
            payload["career_snapshot"] = record.get("career_snapshot")
            payload["fantasy_snapshot"] = record.get("fantasy_snapshot")
        return payload

    def persist_local_accounts(self):
        save_accounts(self.accounts_data)

    def sync_record_to_local(self, record=None, password=None):
        record = record or {}
        username = str(record.get("username") or self.active_account or "").strip().lower()
        if not username:
            return None
        users = self.accounts_data.setdefault("users", {})
        existing = users.get(username, {}) if isinstance(users.get(username), dict) else {}
        local = dict(existing)
        local["display_name"] = record.get("display_name", local.get("display_name", username))
        local["username"] = username
        local["is_developer"] = bool(record.get("is_developer", local.get("is_developer", False)))
        local["last_mode"] = record.get("last_mode", local.get("last_mode", "CAREER"))
        local["cloud_state"] = "SYNCED"
        if "career_snapshot" in record and record.get("career_snapshot") is not None:
            local["career_snapshot"] = record.get("career_snapshot")
        if "fantasy_snapshot" in record and record.get("fantasy_snapshot") is not None:
            local["fantasy_snapshot"] = record.get("fantasy_snapshot")
        if password:
            local["password_hash"] = self.hash_password(password)
            local["sync_password"] = password
        users[username] = local
        self.persist_local_accounts()
        return local

    def register_local_account(self, display_name, username, password, developer_code=""):
        username = username.strip().lower()
        users = self.accounts_data.setdefault("users", {})
        if username in users:
            raise RuntimeError("Username already exists locally")
        local = {
            "display_name": display_name.strip(),
            "username": username,
            "password_hash": self.hash_password(password),
            "sync_password": password,
            "is_developer": developer_code == DEVELOPER_CODE,
            "developer_code": developer_code.strip(),
            "cloud_state": "PENDING_CREATE",
            "last_mode": "CAREER",
            "career_snapshot": None,
            "fantasy_snapshot": None,
        }
        users[username] = local
        self.persist_local_accounts()
        return self.serialize_local_account(local, include_snapshots=True)

    def login_local_account(self, username, password, require_dev=False, developer_code=""):
        record = self.local_account_record(username)
        if not record:
            raise RuntimeError("Local fallback account not found")
        if record.get("password_hash") != self.hash_password(password):
            raise RuntimeError("Invalid username or password.")
        if require_dev and (not record.get("is_developer") or developer_code != DEVELOPER_CODE):
            raise RuntimeError("Developer code required.")
        record["sync_password"] = password
        if developer_code:
            record["developer_code"] = developer_code.strip()
        self.persist_local_accounts()
        return self.serialize_local_account(record, include_snapshots=True)

    def save_local_snapshot(self, mode, snapshot):
        local = self.local_account_record()
        if not local:
            base_record = self.cloud_user_cache or {
                "username": self.active_account,
                "display_name": self.active_account,
                "is_developer": False,
                "last_mode": mode,
            }
            local = self.sync_record_to_local(base_record)
        if not local:
            return False
        if mode == "CAREER":
            local["career_snapshot"] = snapshot
        elif mode == "FANTASY":
            local["fantasy_snapshot"] = snapshot
        local["last_mode"] = mode
        self.persist_local_accounts()
        return True

    def local_snapshot_for_mode(self, mode):
        record = self.local_account_record()
        if not record:
            return None
        if mode == "CAREER":
            return record.get("career_snapshot")
        if mode == "FANTASY":
            return record.get("fantasy_snapshot")
        return None

    def apply_cloud_settings(self):
        url = self.cloud_settings_inputs.get("cloud_api_url", "").strip().rstrip("/")
        if not url:
            self.account_message = "Cloud URL required"
            return False
        self.app_settings["cloud_enabled"] = True
        self.app_settings["cloud_api_url"] = url or "http://127.0.0.1:8080"
        save_app_settings(self.app_settings)
        self.cloud_api_base = url
        os.environ["FC_CLOUD_API_URL"] = self.cloud_api_base
        self.cloud_token = None
        self.cloud_user_cache = None
        self.cloud_registered_users = []
        self.active_account = None
        self.account_message = "Cloud settings saved"
        self.state = "ACCOUNT_HOME"
        return True

    def fantasy_palette_color(self, idx):
        if not FANTASY_CLUB_PALETTES:
            return (54, 136, 255)
        return FANTASY_CLUB_PALETTES[idx % len(FANTASY_CLUB_PALETTES)][1]

    def fantasy_club_badge_name(self):
        return FANTASY_CLUB_BADGES[self.fantasy_club_custom.get("badge", 0) % len(FANTASY_CLUB_BADGES)]

    def ensure_fantasy_club_defaults(self):
        custom = self.fantasy_club_custom if isinstance(self.fantasy_club_custom, dict) else {}
        custom["badge"] = int(custom.get("badge", 0)) % len(FANTASY_CLUB_BADGES)
        custom["primary"] = int(custom.get("primary", 0)) % len(FANTASY_CLUB_PALETTES)
        custom["secondary"] = int(custom.get("secondary", 5)) % len(FANTASY_CLUB_PALETTES)
        if custom["secondary"] == custom["primary"]:
            custom["secondary"] = (custom["primary"] + 1) % len(FANTASY_CLUB_PALETTES)
        custom["stadium"] = int(custom.get("stadium", 0)) % len(FANTASY_STADIUM_OPTIONS)
        self.fantasy_club_custom = custom
        return custom

    def apply_fantasy_club_identity(self):
        if self.game_mode != "FANTASY" or not self.user_team:
            return
        custom = self.ensure_fantasy_club_defaults()
        primary = self.fantasy_palette_color(custom["primary"])
        secondary = self.fantasy_palette_color(custom["secondary"])
        keeper = tuple(max(18, int((primary[i] + 20) * 0.45)) for i in range(3))
        TEAM_KITS[self.user_team] = [
            (primary, secondary),
            (secondary, primary),
            (keeper, primary),
        ]
        STADIUMS[self.user_team] = FANTASY_STADIUM_OPTIONS[custom["stadium"]]

    def restore_fantasy_club_state(self):
        if self.game_mode != "FANTASY":
            return
        fantasy_name = (self.fantasy_team_name or "").strip()
        current_team = (self.user_team or "").strip()
        if fantasy_name:
            team_name = fantasy_name
        else:
            team_name = current_team
        if not team_name:
            return
        self.user_team = team_name
        if not isinstance(self.active_teams, list) or not self.active_teams:
            self.active_teams = TEAMS[:]
        if team_name not in self.active_teams:
            replaced = self.fantasy_replaced_team if self.fantasy_replaced_team in self.active_teams else None
            if replaced is None and self.active_teams:
                replaced = self.active_teams[-1]
            if replaced and replaced in self.active_teams:
                idx = self.active_teams.index(replaced)
                self.active_teams[idx] = team_name
                self.fantasy_replaced_team = replaced
            elif team_name not in self.active_teams:
                self.active_teams.append(team_name)
        if team_name not in STADIUMS:
            STADIUMS[team_name] = FANTASY_STADIUM_OPTIONS[self.ensure_fantasy_club_defaults()["stadium"]]
        self.apply_fantasy_club_identity()
        if self.user_player_index is None:
            self.user_player_index = 9 if len(self.fantasy_roster) > 9 else 0

    def fantasy_share_payload(self):
        custom = self.ensure_fantasy_club_defaults()
        lineup = []
        for idx, entry in enumerate(self.user_starting):
            name, number, rating = entry
            meta = self.get_fantasy_card_meta(name, number, rating) or self.get_fantasy_card_meta(name)
            if not meta:
                continue
            lineup.append(meta.get("card_key") or self.fantasy_card_key(meta))
        return {
            "team_name": self.fantasy_team_name.strip() or "Fantasy FC",
            "badge": custom["badge"],
            "primary": custom["primary"],
            "secondary": custom["secondary"],
            "stadium": custom["stadium"],
            "lineup": lineup,
        }

    def export_squad_share_code(self):
        if self.game_mode != "FANTASY" or not self.fantasy_roster:
            self.fantasy_share_message = "Build a fantasy squad first"
            return ""
        raw = json.dumps(self.fantasy_share_payload(), separators=(",", ":")).encode("utf-8")
        code = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        self.fantasy_share_input = code
        self.fantasy_share_message = "Share code ready"
        return code

    def import_squad_share_code(self, code):
        code = (code or "").strip()
        if not code:
            self.fantasy_share_message = "Paste a share code first"
            return False
        padding = "=" * (-len(code) % 4)
        try:
            payload = json.loads(base64.urlsafe_b64decode((code + padding).encode("ascii")).decode("utf-8"))
        except Exception:
            self.fantasy_share_message = "Invalid share code"
            return False
        lineup_keys = payload.get("lineup", [])
        if not isinstance(lineup_keys, list) or not lineup_keys:
            self.fantasy_share_message = "Share code has no lineup"
            return False
        matched = []
        used = set()
        for card_key in lineup_keys:
            for idx, card in enumerate(self.fantasy_roster):
                candidate_key = card.get("card_key") or self.fantasy_card_key(card)
                if idx in used:
                    continue
                if candidate_key == card_key or card.get("name") == card_key:
                    matched.append(card.copy())
                    used.add(idx)
                    break
        if len(matched) < min(11, len(lineup_keys)):
            self.fantasy_share_message = f"Only matched {len(matched)} of {min(11, len(lineup_keys))} starters"
            return False
        ordered = matched + [card.copy() for idx, card in enumerate(self.fantasy_roster) if idx not in used]
        self.fantasy_roster = ordered
        self.fantasy_team_name = payload.get("team_name", self.fantasy_team_name)[:16] or self.fantasy_team_name
        self.fantasy_club_custom = {
            "badge": int(payload.get("badge", self.fantasy_club_custom.get("badge", 0))),
            "primary": int(payload.get("primary", self.fantasy_club_custom.get("primary", 0))),
            "secondary": int(payload.get("secondary", self.fantasy_club_custom.get("secondary", 5))),
            "stadium": int(payload.get("stadium", self.fantasy_club_custom.get("stadium", 0))),
        }
        self.ensure_fantasy_club_defaults()
        if self.user_team:
            self.apply_roster_to_team(self.fantasy_roster)
            self.apply_fantasy_club_identity()
        self.fantasy_share_message = f"Imported lineup with {len(matched)} matched starters"
        return True

    def cloud_request(self, method, path, payload=None, needs_auth=False):
        if not self.cloud_api_base:
            self.cloud_status_label = "Cloud Not Configured"
            raise RuntimeError("Cloud backend not configured")
        url = f"{self.cloud_api_base}{path}"
        body = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        if needs_auth and self.cloud_token:
            headers["Authorization"] = f"Bearer {self.cloud_token}"
        req = urllib_request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib_request.urlopen(req, timeout=5) as response:
                raw = response.read().decode("utf-8")
                self.cloud_status_label = "Connected to Cloud"
                return json.loads(raw) if raw else {}
        except urllib_error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                data = json.loads(raw) if raw else {}
            except Exception:
                data = {}
            self.cloud_status_label = "Cloud Auth Required" if exc.code == 401 else "Cloud Error"
            raise RuntimeError(data.get("error") or f"HTTP {exc.code}")
        except (urllib_error.URLError, socket.timeout, TimeoutError):
            self.cloud_status_label = "Cloud Unavailable"
            raise RuntimeError("Cloud server unavailable")

    def reconnect_cloud(self):
        try:
            self.fetch_cloud_runtime_config()
            if self.cloud_token:
                data = self.cloud_request("GET", "/api/profile", needs_auth=True)
                self.cloud_user_cache = data.get("user")
                self.sync_record_to_local(self.cloud_user_cache)
                self.account_storage_mode = "CLOUD"
                self.account_message = "Cloud session restored"
            elif self.try_sync_active_account_to_cloud():
                self.account_storage_mode = "CLOUD"
                self.cloud_status_label = "Connected to Cloud"
                return True
            else:
                self.cloud_request("GET", "/health")
                self.account_message = "Cloud server reachable. Sign in to sync."
            self.cloud_status_label = "Connected to Cloud"
            return True
        except RuntimeError as exc:
            self.account_message = str(exc)
            return False

    def fetch_cloud_runtime_config(self):
        try:
            data = self.cloud_request("GET", "/api/config")
            if isinstance(data, dict):
                self.cloud_runtime_config = {
                    "announcement": data.get("announcement", ""),
                    "maintenance_mode": bool(data.get("maintenance_mode")),
                    "disabled_modes": data.get("disabled_modes", {}) if isinstance(data.get("disabled_modes"), dict) else {},
                }
            return self.cloud_runtime_config
        except RuntimeError:
            return self.cloud_runtime_config

    def developer_tabs(self):
        return ["Users", "Economy", "Tournaments", "Live Ops", "Support"]

    def developer_coin_amounts(self):
        return [100, 1000, 10000, 50000]

    def developer_pack_ids(self):
        packs = [
            "bronze", "silver", "gold", "platinum", "elite", "elite_pick",
            "diamond", "mythic", "ascended", "legend", "legend_pick",
            "transcendent", "celestial", "eternal", "immortal", "omega",
            "goat", "icon", "signature", "promo", "ultimate", "supreme",
            "premier_league", "la_liga", "bundesliga", "serie_a", "ligue_1", "saudi",
        ]
        event_pack = self.active_event_pack_entry()
        if event_pack and event_pack["id"] not in packs:
            packs.append(event_pack["id"])
        return packs or ["gold"]

    def developer_card_catalog(self):
        pool = self.fantasy_pool or []
        cards = sorted(pool, key=lambda card: (-card.get("rating", 0), card.get("name", "")))
        return cards[:120]

    def filtered_registered_users(self):
        users = self.cloud_registered_users or []
        query = self.dev_search_query.strip().lower()
        if not query:
            return users
        return [
            user for user in users
            if query in str(user.get("username", "")).lower() or query in str(user.get("display_name", "")).lower()
        ]

    def selected_registered_user(self):
        users = self.filtered_registered_users()
        if not users:
            return None
        self.registered_users_index = max(0, min(self.registered_users_index, len(users) - 1))
        return users[self.registered_users_index]

    def refresh_dev_user(self, user):
        if not user:
            return
        username = user.get("username")
        replaced = False
        for idx, existing in enumerate(self.cloud_registered_users):
            if existing.get("username") == username:
                self.cloud_registered_users[idx] = user
                replaced = True
                break
        if not replaced:
            self.cloud_registered_users.append(user)
            self.cloud_registered_users.sort(key=lambda item: item.get("username", ""))
        if username == self.active_account:
            self.cloud_user_cache = user
            local = self.sync_record_to_local(user)
            if local is not None and self.account_storage_mode == "LOCAL":
                self.account_storage_mode = "CLOUD"

    def fetch_admin_status(self):
        try:
            data = self.cloud_request("GET", "/api/admin/status", needs_auth=True)
            if isinstance(data, dict):
                self.dev_admin_status = data
                self.dev_announcement_input = data.get("settings", {}).get("announcement", self.dev_announcement_input)
            return self.dev_admin_status
        except RuntimeError as exc:
            self.dev_action_message = str(exc)
            return self.dev_admin_status

    def admin_user_action(self, username, action, **payload):
        try:
            data = self.cloud_request(
                "POST",
                "/api/admin/user-action",
                {"username": username, "action": action, **payload},
                needs_auth=True,
            )
            user = data.get("user")
            self.refresh_dev_user(user)
            self.dev_action_message = f"{action.replace('_', ' ').title()} complete for {username}"
            return user
        except RuntimeError as exc:
            self.dev_action_message = str(exc)
            return None

    def admin_tournament_action(self, username, action, **payload):
        try:
            self.cloud_request(
                "POST",
                "/api/admin/tournament-action",
                {"username": username, "action": action, **payload},
                needs_auth=True,
            )
            self.fetch_registered_users()
            self.dev_action_message = f"{action.replace('_', ' ').title()} complete for {username}"
            return True
        except RuntimeError as exc:
            self.dev_action_message = str(exc)
            return False

    def admin_update_settings(self, **payload):
        try:
            data = self.cloud_request("PUT", "/api/admin/settings", payload, needs_auth=True)
            settings = data.get("settings", {})
            self.dev_admin_status["settings"] = settings
            self.cloud_runtime_config.update(
                {
                    "announcement": settings.get("announcement", ""),
                    "maintenance_mode": bool(settings.get("maintenance_mode")),
                    "disabled_modes": settings.get("disabled_modes", {}),
                }
            )
            self.dev_action_message = "Developer settings updated"
            return settings
        except RuntimeError as exc:
            self.dev_action_message = str(exc)
            return None

    def try_sync_active_account_to_cloud(self):
        local = self.local_account_record()
        if not local:
            return False
        password = local.get("sync_password")
        if not password:
            self.account_message = "Local account needs a fresh sign-in before cloud sync"
            return False
        username = local.get("username", "")
        developer_code = local.get("developer_code", "")
        register_payload = {
            "display_name": local.get("display_name", username),
            "username": username,
            "password": password,
            "developer_code": developer_code,
        }
        login_payload = {
            "username": username,
            "password": password,
            "developer_code": developer_code,
            "require_dev": False,
        }
        data = None
        cloud_state = local.get("cloud_state", "LOCAL_ONLY")
        if cloud_state == "PENDING_CREATE":
            try:
                data = self.cloud_request("POST", "/api/register", register_payload)
                self.account_message = "Local account promoted to cloud"
            except RuntimeError as exc:
                if "already exists" not in str(exc).lower():
                    raise
        if data is None:
            data = self.cloud_request("POST", "/api/login", login_payload)
            if cloud_state != "SYNCED":
                self.account_message = "Local account linked to cloud"
        self.cloud_token = data.get("token")
        self.cloud_user_cache = data.get("user")
        synced = self.sync_record_to_local(self.cloud_user_cache, password=password)
        if synced is not None:
            synced["cloud_state"] = "SYNCED"
            if developer_code:
                synced["developer_code"] = developer_code
            self.persist_local_accounts()
        self.migrate_local_snapshots_to_cloud()
        return True

    def online_divisions_available(self):
        if self.account_storage_mode == "LOCAL" or not self.cloud_token:
            self.online_division_message = "Online Divisions requires a cloud account session"
            self.account_message = "Sign in with cloud access to use Online Divisions"
            self.cloud_status_label = "Using Local Fallback" if self.account_storage_mode == "LOCAL" else "Cloud Auth Required"
            return False
        return True

    def enter_account_state(self, state):
        self.state = state
        self.reset_account_inputs()

    def active_account_record(self):
        if not self.active_account:
            return None
        if self.cloud_user_cache and self.cloud_user_cache.get("username") == self.active_account:
            merged = dict(self.cloud_user_cache)
            local = self.local_account_record()
            if local:
                if merged.get("career_snapshot") is None and local.get("career_snapshot") is not None:
                    merged["career_snapshot"] = local.get("career_snapshot")
                if merged.get("fantasy_snapshot") is None and local.get("fantasy_snapshot") is not None:
                    merged["fantasy_snapshot"] = local.get("fantasy_snapshot")
                if not merged.get("fantasy_summary"):
                    merged["fantasy_summary"] = self.serialize_local_account(local, include_snapshots=True).get("fantasy_summary", {})
                merged["storage_mode"] = "CLOUD"
            return merged
        local = self.local_account_record()
        if local:
            return self.serialize_local_account(local, include_snapshots=True)
        return None

    def refresh_accounts_data(self):
        if self.cloud_token:
            try:
                data = self.cloud_request("GET", "/api/profile", needs_auth=True)
                self.cloud_user_cache = data.get("user")
                self.sync_record_to_local(self.cloud_user_cache)
            except RuntimeError:
                self.cloud_user_cache = None

    def migrate_local_snapshots_to_cloud(self):
        if not self.cloud_token or self.account_storage_mode != "CLOUD":
            return
        local = self.local_account_record()
        cloud = self.cloud_user_cache or {}
        if not local:
            return
        migrated_modes = []
        for mode, key in (("CAREER", "career_snapshot"), ("FANTASY", "fantasy_snapshot")):
            local_snapshot = local.get(key)
            cloud_snapshot = cloud.get(key)
            if local_snapshot is None or cloud_snapshot is not None:
                continue
            try:
                data = self.cloud_request(
                    "PUT",
                    "/api/save",
                    {"mode": mode, "snapshot": local_snapshot},
                    needs_auth=True,
                )
                self.cloud_user_cache = data.get("user", self.cloud_user_cache)
                self.sync_record_to_local(self.cloud_user_cache)
                migrated_modes.append(mode.title())
            except RuntimeError:
                continue
        if migrated_modes:
            self.account_message = f"Migrated {' & '.join(migrated_modes)} save to cloud"

    def fetch_registered_users(self):
        local_users = []
        seen = set()
        for username, record in sorted(self.accounts_data.get("users", {}).items()):
            if not isinstance(record, dict):
                continue
            local_payload = self.serialize_local_account(record, include_snapshots=True)
            if not local_payload:
                continue
            local_users.append(local_payload)
            seen.add(username)
        try:
            data = self.cloud_request("GET", "/api/admin/users", needs_auth=True)
            cloud_users = data.get("users", [])
            if isinstance(data.get("settings"), dict):
                self.dev_admin_status = {
                    "ok": True,
                    "settings": data.get("settings", {}),
                    "metrics": data.get("health", {}),
                }
                self.dev_announcement_input = data.get("settings", {}).get("announcement", self.dev_announcement_input)
            merged = list(cloud_users)
            seen = {item.get("username") for item in cloud_users if isinstance(item, dict)}
            for user in local_users:
                if user.get("username") not in seen:
                    merged.append(user)
            self.cloud_registered_users = merged
            filtered = self.filtered_registered_users()
            self.registered_users_index = max(0, min(self.registered_users_index, max(0, len(filtered) - 1)))
            return self.cloud_registered_users
        except RuntimeError as exc:
            if local_users:
                self.account_message = f"{str(exc)} | showing local fallback accounts"
            else:
                self.account_message = str(exc)
            self.cloud_registered_users = local_users
            return local_users

    def update_online_division_cache(self, data):
        self.online_division_data = {
            "entry": data.get("entry", {}) if isinstance(data, dict) else {},
            "leaderboard": data.get("leaderboard", []) if isinstance(data, dict) else [],
        }
        leaderboard = self.online_division_data.get("leaderboard", [])
        self.online_division_index = max(0, min(self.online_division_index, max(0, len(leaderboard) - 1)))

    def fetch_online_division_status(self):
        if not self.online_divisions_available():
            return None
        try:
            data = self.cloud_request("GET", "/api/online-divisions", needs_auth=True)
            self.update_online_division_cache(data)
            entry = self.online_division_data.get("entry", {})
            self.online_division_message = f"Division {entry.get('division_tier', 10)} | {entry.get('points', 0)} pts"
            return data
        except RuntimeError as exc:
            self.online_division_message = str(exc)
            return None

    def submit_online_division_squad(self):
        if not self.online_divisions_available():
            return
        self.save_active_profile()
        try:
            data = self.cloud_request("PUT", "/api/online-divisions/submit", {}, needs_auth=True)
            entry = data.get("entry", {})
            self.online_division_data["entry"] = entry
            self.fetch_online_division_status()
            self.online_division_message = f"Submitted {entry.get('squad_name', 'your squad')} at {entry.get('squad_rating', 0)} OVR"
        except RuntimeError as exc:
            self.online_division_message = str(exc)

    def play_online_division_match(self):
        if not self.online_divisions_available():
            return
        self.save_active_profile()
        try:
            data = self.cloud_request("POST", "/api/online-divisions/play", {}, needs_auth=True)
            self.update_online_division_cache(data)
            match = data.get("match", {})
            result = match.get("result", "D")
            outcome = "won" if result == "W" else "drew" if result == "D" else "lost"
            opponent = match.get("opponent", "opponent")
            opponent_team = match.get("opponent_team") or opponent
            opponent_tag = " (AI)" if match.get("opponent_is_ai") else ""
            rating = match.get("opponent_rating")
            rating_text = f" {int(rating)} OVR" if rating is not None else ""
            self.online_division_message = (
                f"You {outcome} {match.get('user_goals', 0)}-{match.get('opponent_goals', 0)} vs {opponent_team}{rating_text}{opponent_tag}"
            )
            if match.get("cycle_message"):
                self.add_commentary(match.get("cycle_message"))
        except RuntimeError as exc:
            self.online_division_message = str(exc)

    def claim_online_division_rewards(self):
        if not self.online_divisions_available():
            return
        try:
            data = self.cloud_request("POST", "/api/online-divisions/claim", {}, needs_auth=True)
            reward = int(data.get("reward_coins", 0))
            self.fantasy_coins += reward
            self.update_online_division_cache(data)
            self.online_division_message = f"Claimed {reward} online division coins"
            self.save_active_profile()
        except RuntimeError as exc:
            self.online_division_message = str(exc)

    def online_tournaments_available(self):
        return self.online_divisions_available()

    def fetch_online_tournament_status(self):
        if not self.online_tournaments_available():
            return None
        try:
            data = self.cloud_request("GET", "/api/online-tournaments", needs_auth=True)
            self.online_tournament_data = {
                "entry": data.get("entry", {}) if isinstance(data, dict) else {},
                "leaderboard": data.get("leaderboard", []) if isinstance(data, dict) else [],
            }
            leaderboard = self.online_tournament_data.get("leaderboard", [])
            self.online_tournament_index = max(0, min(self.online_tournament_index, max(0, len(leaderboard) - 1)))
            entry = self.online_tournament_data.get("entry", {})
            self.online_tournament_message = f"Round {entry.get('round', 1)} | {entry.get('wins', 0)}W/{entry.get('losses', 0)}L | Reward {entry.get('reward_coins', 0)}"
            return data
        except RuntimeError as exc:
            self.online_tournament_message = str(exc)
            return None

    def play_online_tournament_match(self):
        if not self.online_tournaments_available():
            return
        self.save_active_profile()
        try:
            data = self.cloud_request("POST", "/api/online-tournaments/play", {}, needs_auth=True)
            self.online_tournament_data = {
                "entry": data.get("entry", {}) if isinstance(data, dict) else {},
                "leaderboard": data.get("leaderboard", []) if isinstance(data, dict) else [],
            }
            match = data.get("match", {})
            self.online_tournament_message = f"Tournament {match.get('result', 'play')} {match.get('user_goals', 0)}-{match.get('opponent_goals', 0)} vs {match.get('opponent', 'opponent')}"
            if match.get("opponent_display"):
                self.add_commentary(f"Played {match['opponent_display']} in the tournament.")
        except RuntimeError as exc:
            self.online_tournament_message = str(exc)

    def submit_online_tournament_squad(self):
        if not self.online_divisions_available():
            return
        self.submit_online_division_squad()
        self.fetch_online_tournament_status()

    def claim_online_tournament_rewards(self):
        if not self.online_tournaments_available():
            return
        try:
            data = self.cloud_request("POST", "/api/online-tournaments/claim", {}, needs_auth=True)
            reward = int(data.get("reward_coins", 0))
            self.fantasy_coins += reward
            self.online_tournament_data = {
                "entry": data.get("entry", {}) if isinstance(data, dict) else {},
                "leaderboard": data.get("leaderboard", []) if isinstance(data, dict) else [],
            }
            self.online_tournament_message = f"Claimed {reward} tournament coins"
            self.save_active_profile()
        except RuntimeError as exc:
            self.online_tournament_message = str(exc)

    def logout_account(self):
        self.save_active_profile()
        self.active_account = None
        self.cloud_token = None
        self.cloud_user_cache = None
        self.account_storage_mode = "CLOUD"
        self.cloud_status_label = "Connected to Cloud" if self.cloud_api_base else "Cloud Not Configured"
        self.cloud_registered_users = []
        self.account_message = ""
        self.state = "ACCOUNT_HOME"

    def build_full_snapshot(self):
        def sanitize(value):
            if isinstance(value, (set, frozenset)):
                return list(value)
            if isinstance(value, dict):
                return {k: sanitize(v) for k, v in value.items()}
            if isinstance(value, tuple):
                return [sanitize(v) for v in value]
            if isinstance(value, list):
                return [sanitize(v) for v in value]
            return value

        snapshot = {
            "game_mode": self.game_mode,
            "user_team": self.user_team,
            "user_player_index": self.user_player_index,
            "season": self.season,
            "week_index": self.week_index,
            "table": self.table,
            "fixtures": self.fixtures,
            "cups": self.cups,
            "cup_schedule": self.cup_schedule,
            "current_competition": self.current_competition,
            "career_trophies": self.career_trophies,
            "user_budget": self.user_budget,
            "user_form": self.user_form,
            "user_injuries": self.user_injuries,
            "user_match_form": self.user_match_form,
            "season_stats": self.season_stats,
            "player_awards": {k: list(v) for k, v in self.player_awards.items()},
            "last_season_awards": self.last_season_awards,
            "team_lineups": TEAM_LINEUPS,
            "roster_data": ROSTER_DATA,
            "rating_cache": RATING_CACHE,
            "transfer_pool": self.transfer_pool,
            "transfer_offers": self.transfer_offers,
            "transfer_window": self.transfer_window,
            "home_kit_index": self.home_kit_index,
            "away_kit_index": self.away_kit_index,
            "academy": self.academy,
            "academy_intake_done": self.academy_intake_done,
            "active_teams": self.active_teams,
            "fantasy_team_name": self.fantasy_team_name,
            "fantasy_budget": self.fantasy_budget,
            "fantasy_roster": self.fantasy_roster,
            "fantasy_replaced_team": self.fantasy_replaced_team,
            "fantasy_coins": self.fantasy_coins,
            "my_packs": self.my_packs,
            "last_pack": self.last_pack,
            "fantasy_competitions": self.fantasy_competitions,
            "fantasy_objectives": self.fantasy_objectives,
            "fantasy_season_xp": self.fantasy_season_xp,
            "fantasy_season_claimed": self.fantasy_season_claimed,
            "fantasy_active_competition": self.fantasy_active_competition,
            "fantasy_match_competition": self.fantasy_match_competition,
            "fantasy_competition_index": self.fantasy_competition_index,
            "current_theme": self.current_theme,
            "fantasy_club_custom": self.fantasy_club_custom,
            "fantasy_favorites": self.fantasy_favorites,
            "pack_event_index": self.pack_event_index,
            "current_pack_event": self.current_pack_event,
            "fantasy_draft_round": self.fantasy_draft_round,
            "fantasy_draft_index": self.fantasy_draft_index,
            "fantasy_draft_options": self.fantasy_draft_options,
            "fantasy_draft_roster": self.fantasy_draft_roster,
            "fantasy_draft_active": self.fantasy_draft_active,
            "fantasy_draft_saved_roster": self.fantasy_draft_saved_roster,
            "fantasy_draft_saved_lineup": self.fantasy_draft_saved_lineup,
            "fantasy_draft_saved_reserves": self.fantasy_draft_saved_reserves,
            "fantasy_draft_saved_player_index": self.fantasy_draft_saved_player_index,
            "event_evo_tokens": self.event_evo_tokens,
        }
        return sanitize(snapshot)

    def apply_full_snapshot(self, data):
        self.game_mode = data.get("game_mode", "CAREER")
        self.user_team = data.get("user_team")
        self.user_player_index = data.get("user_player_index")
        self.season = data.get("season", 1)
        self.week_index = data.get("week_index", 0)
        self.table = data.get("table", {})
        self.fixtures = data.get("fixtures", [])
        self.cups = data.get("cups", {})
        self.cup_schedule = data.get("cup_schedule", {})
        self.current_competition = data.get("current_competition", "LEAGUE")
        self.career_trophies = data.get("career_trophies", {"LEAGUE": 0, "FA": 0, "LC": 0})
        self.user_budget = data.get("user_budget", 120)
        self.user_form = data.get("user_form", 1.0)
        self.user_injuries = data.get("user_injuries", 0)
        self.user_match_form = data.get("user_match_form", self.user_form)
        self.season_stats = data.get("season_stats", {})
        self.player_awards = {k: set(v) for k, v in data.get("player_awards", {}).items()}
        self.last_season_awards = data.get("last_season_awards", {})
        team_lineups = data.get("team_lineups")
        if isinstance(team_lineups, dict):
            TEAM_LINEUPS.clear()
            TEAM_LINEUPS.update(team_lineups)
        roster_data = data.get("roster_data")
        if isinstance(roster_data, dict):
            ROSTER_DATA.clear()
            ROSTER_DATA.update(roster_data)
        rating_cache = data.get("rating_cache")
        if isinstance(rating_cache, dict):
            RATING_CACHE.clear()
            RATING_CACHE.update(rating_cache)
            save_rating_cache(RATING_CACHE)
        self.transfer_pool = data.get("transfer_pool", [])
        self.transfer_offers = data.get("transfer_offers", [])
        self.transfer_window = data.get("transfer_window", False)
        self.home_kit_index = data.get("home_kit_index", 0)
        self.away_kit_index = data.get("away_kit_index", 1)
        self.academy = data.get("academy", [])
        self.academy_intake_done = data.get("academy_intake_done", False)
        self.active_teams = data.get("active_teams", TEAMS[:])
        self.fantasy_team_name = data.get("fantasy_team_name", self.fantasy_team_name)
        self.fantasy_budget = data.get("fantasy_budget", self.fantasy_budget)
        self.fantasy_roster = data.get("fantasy_roster", [])
        if self.game_mode == "FANTASY" and self.fantasy_team_name:
            self.user_team = self.fantasy_team_name
        self.fantasy_replaced_team = data.get("fantasy_replaced_team", self.fantasy_replaced_team)
        self.fantasy_coins = data.get("fantasy_coins", self.fantasy_coins)
        self.my_packs = data.get("my_packs", [])
        self.last_pack = data.get("last_pack", [])
        self.fantasy_competitions = data.get("fantasy_competitions", {})
        self.fantasy_objectives = data.get("fantasy_objectives", {})
        self.fantasy_season_xp = data.get("fantasy_season_xp", 0)
        self.fantasy_season_claimed = data.get("fantasy_season_claimed", 0)
        self.fantasy_active_competition = data.get("fantasy_active_competition", "division")
        self.fantasy_match_competition = data.get("fantasy_match_competition", "division")
        self.fantasy_competition_index = data.get("fantasy_competition_index", 0)
        self.current_theme = data.get("current_theme", self.current_theme)
        self.fantasy_club_custom = data.get("fantasy_club_custom", self.fantasy_club_custom)
        self.fantasy_favorites = data.get("fantasy_favorites", [])
        self.pack_event_index = data.get("pack_event_index", -1)
        self.current_pack_event = data.get("current_pack_event", {})
        self.fantasy_draft_round = data.get("fantasy_draft_round", 0)
        self.fantasy_draft_index = data.get("fantasy_draft_index", 0)
        self.fantasy_draft_options = data.get("fantasy_draft_options", [])
        self.fantasy_draft_roster = data.get("fantasy_draft_roster", [])
        self.fantasy_draft_active = data.get("fantasy_draft_active", False)
        self.fantasy_draft_saved_roster = data.get("fantasy_draft_saved_roster", [])
        self.fantasy_draft_saved_lineup = data.get("fantasy_draft_saved_lineup", [])
        self.fantasy_draft_saved_reserves = data.get("fantasy_draft_saved_reserves", [])
        self.fantasy_draft_saved_player_index = data.get("fantasy_draft_saved_player_index", 0)
        self.event_evo_tokens = data.get("event_evo_tokens", 0)
        if self.game_mode == "FANTASY":
            self.restore_fantasy_club_state()
            self.build_fantasy_pool()
            if not self.fantasy_competitions:
                self.init_fantasy_competitions()
            self.apply_fantasy_club_identity()
            if not self.fantasy_objectives:
                self.init_fantasy_objectives()
            if not self.current_pack_event:
                self.roll_pack_event()
        self.build_user_squad()
        self.pending_fixture = None
        self.match_probabilities = None
        self.kickoff_pending = True

    def save_active_profile(self):
        record = self.active_account_record()
        if not record or self.game_mode not in ("CAREER", "FANTASY"):
            return
        snapshot = self.build_full_snapshot()
        local_saved = self.save_local_snapshot(self.game_mode, snapshot)
        cloud_saved = False
        try:
            data = self.cloud_request(
                "PUT",
                "/api/save",
                {"mode": self.game_mode, "snapshot": snapshot},
                needs_auth=True,
            )
            self.cloud_user_cache = data.get("user", self.cloud_user_cache)
            self.sync_record_to_local(self.cloud_user_cache)
            cloud_saved = True
        except RuntimeError as exc:
            self.account_message = "Saved locally; cloud sync unavailable" if local_saved else str(exc)
        if cloud_saved and self.account_storage_mode == "LOCAL":
            self.account_message = "Cloud sync restored"
            self.account_storage_mode = "CLOUD"
            self.cloud_status_label = "Connected to Cloud"

    def load_profile_mode(self, mode):
        record = self.active_account_record()
        if not record:
            return
        snapshot = None
        try:
            data = self.cloud_request("GET", f"/api/save?mode={mode}", needs_auth=True)
            snapshot = data.get("snapshot")
            self.refresh_accounts_data()
            record = self.active_account_record() or record
        except RuntimeError as exc:
            self.account_message = str(exc)
            snapshot = None
        if snapshot is None:
            local_snapshot = self.local_snapshot_for_mode(mode)
            if local_snapshot:
                snapshot = local_snapshot
                self.account_storage_mode = "LOCAL"
                self.account_message = "Using local fallback save"
                self.cloud_status_label = "Using Local Fallback"
        if snapshot:
            self.apply_full_snapshot(snapshot)
            self.game_mode = mode
            if mode == "FANTASY":
                self.restore_fantasy_club_state()
            self.state = "LEAGUE"
        elif mode == "CAREER":
            self.game_mode = "CAREER"
            self.active_teams = TEAMS[:]
            self.user_team = None
            self.selected_index = 0
            self.state = "TEAM_SELECT"
        else:
            self.game_mode = "FANTASY"
            self.active_teams = TEAMS[:]
            self.user_team = None
            self.fantasy_roster = []
            self.fantasy_club_custom = {"badge": 0, "primary": 0, "secondary": 5, "stadium": 0}
            self.fantasy_share_input = ""
            self.fantasy_share_message = ""
            self.fantasy_draft_roster = []
            self.fantasy_draft_options = []
            self.fantasy_draft_round = 0
            self.fantasy_draft_active = False
            self.last_pack = []
            self.fantasy_coins = DEVELOPER_FANTASY_COINS if record.get("is_developer") else DEFAULT_FANTASY_COINS
            self.fantasy_season_xp = 0
            self.fantasy_season_claimed = 0
            self.fantasy_sbc_index = 0
            self.fantasy_objective_index = 0
            self.show_pack_shop = False
            self.build_fantasy_pool()
            self.init_fantasy_competitions()
            self.init_fantasy_objectives()
            self.fantasy_team_name = ""
            self.state = "FANTASY_TEAM_NAME"
        record["last_mode"] = mode
        if self.cloud_user_cache is None:
            self.cloud_user_cache = {}
        self.cloud_user_cache["last_mode"] = mode
        local = self.local_account_record()
        if local:
            local["last_mode"] = mode
            self.persist_local_accounts()
        self.profile_autosave_timer = 8.0

    def begin_account_session(self, username, record=None, storage_mode="CLOUD"):
        self.active_account = username
        self.account_storage_mode = storage_mode
        self.cloud_status_label = "Using Local Fallback" if storage_mode == "LOCAL" else "Connected to Cloud"
        if record is not None and storage_mode == "CLOUD":
            self.cloud_user_cache = record
        elif storage_mode == "LOCAL":
            self.cloud_user_cache = None
            self.cloud_token = None
        prior_message = self.account_message
        if storage_mode == "CLOUD":
            self.migrate_local_snapshots_to_cloud()
        record = self.active_account_record() or record or {}
        self.mode_select_index = 0
        local = self.local_account_record(username)
        if storage_mode == "LOCAL":
            cloud_state = (local or {}).get("cloud_state", "LOCAL_ONLY")
            if cloud_state == "SYNCED":
                suffix = " (offline mirror)"
            elif cloud_state == "PENDING_CREATE":
                suffix = " (awaiting cloud sync)"
            else:
                suffix = " (local fallback)"
        else:
            suffix = ""
        if not self.account_message or self.account_message == prior_message:
            self.account_message = f"Welcome {record.get('display_name', username)}{suffix}"
        self.state = "MODE_SELECT"
        self.profile_autosave_timer = 8.0

    def create_account(self):
        display_name = self.account_inputs["display_name"].strip()
        username = self.account_inputs["username"].strip().lower()
        password = self.account_inputs["password"]
        developer_code = self.account_inputs["developer_code"].strip()
        if not display_name or not username or not password:
            self.account_message = "Fill in name, username, and password"
            return
        try:
            data = self.cloud_request(
                "POST",
                "/api/register",
                {
                    "display_name": display_name,
                    "username": username,
                    "password": password,
                    "developer_code": developer_code,
                },
            )
            self.cloud_token = data.get("token")
            self.fetch_cloud_runtime_config()
            self.sync_record_to_local(data.get("user"), password=password)
            self.begin_account_session(username, data.get("user"), storage_mode="CLOUD")
        except RuntimeError as exc:
            if "Cloud server unavailable" in str(exc) or "Cloud backend not configured" in str(exc):
                try:
                    local_record = self.register_local_account(display_name, username, password, developer_code)
                    self.begin_account_session(username, local_record, storage_mode="LOCAL")
                    self.account_message = "Created local fallback account"
                except RuntimeError as local_exc:
                    self.account_message = str(local_exc)
            else:
                self.account_message = str(exc)

    def login_account(self, require_dev=False):
        username = self.account_inputs["username"].strip().lower()
        password = self.account_inputs["password"]
        developer_code = self.account_inputs["developer_code"].strip()
        try:
            data = self.cloud_request(
                "POST",
                "/api/login",
                {
                    "username": username,
                    "password": password,
                    "developer_code": developer_code,
                    "require_dev": require_dev,
                },
            )
            self.cloud_token = data.get("token")
            self.fetch_cloud_runtime_config()
            self.sync_record_to_local(data.get("user"), password=password)
            self.begin_account_session(username, data.get("user"), storage_mode="CLOUD")
        except RuntimeError as exc:
            try:
                local_record = self.login_local_account(username, password, require_dev=require_dev, developer_code=developer_code)
                self.begin_account_session(username, local_record, storage_mode="LOCAL")
                self.account_message = "Signed in with local fallback"
            except RuntimeError:
                self.account_message = str(exc)

    def onboarding_starter_pulls(self):
        record = self.active_account_record() or {}
        is_developer = record.get("is_developer")
        normal_pool = [
            p for p in self.fantasy_pool
            if self.rarity_rank(p.get("rarity", "Bronze")) <= self.rarity_rank("Diamond")
            and p.get("rarity") not in ("Icon", "GOAT")
            and p.get("promo") != "Signature"
        ]
        higher_pool = [
            p for p in self.fantasy_pool
            if self.rarity_rank(p.get("rarity", "Bronze")) > self.rarity_rank("Diamond")
            and p.get("rarity") not in ("Icon", "GOAT")
            and p.get("promo") != "Signature"
        ]
        gk_pool = [p for p in normal_pool if p.get("position") == "GK"] or normal_pool[:]
        diamond_pool = [p for p in normal_pool if p.get("rarity") == "Diamond"] or normal_pool[:]
        elite_pool = [p for p in self.fantasy_pool if p.get("rarity") in ("Elite", "Icon", "GOAT") or p.get("promo") == "Signature"]
        pulls = []
        used_names = set()

        def take(pool):
            choices = [p for p in pool if p.get("name") not in used_names] or pool
            pick = random.choice(choices).copy()
            used_names.add(pick.get("name"))
            return pick

        if gk_pool:
            pulls.append(take(gk_pool))
        while len(pulls) < 14 and normal_pool:
            pulls.append(take(normal_pool))
        if is_developer and elite_pool:
            pulls.append(take(elite_pool))
        elif random.random() < 0.01 and higher_pool:
            pulls.append(take(higher_pool))
        else:
            pulls.append(take(diamond_pool))
        if is_developer and higher_pool and len(pulls) < 15:
            pulls.append(take(higher_pool))
        return pulls[:15]

    def finish_fantasy_team_setup(self):
        self.fantasy_team_name = self.fantasy_team_name.strip() or "Fantasy FC"
        pulls = self.onboarding_starter_pulls()
        self.fantasy_roster = []
        self.last_pack = []
        for player in pulls:
            self.add_fantasy_player(player)
        self.last_pack = pulls
        featured = max(pulls, key=lambda p: (p["rating"], self.rarity_rank(p.get("rarity", "Bronze"))))
        self.walkout_timer = self.walkout_duration_for_player(featured, len(pulls))
        self.walkout_index = 0
        self.pack_summary_timer = 0.0
        self.pack_open_return_state = "FANTASY_BUILDER"
        self.state = "PACK_OPENING"
        self.add_commentary(f"{self.fantasy_team_name} starter pack opened")
        self.save_active_profile()

    def visible_fantasy_packs(self):
        packs = self.fantasy_pack_catalog()
        record = self.active_account_record() or {}
        if record.get("is_developer"):
            return packs
        hidden = {"goat", "icon", "signature"}
        return [pack for pack in packs if pack.get("id") not in hidden]

    def generate_youth_player(self):
        first = ["Liam", "Noah", "Mason", "Ethan", "Theo", "Lucas", "Kai", "Julian", "Arthur", "Felix", "Oscar"]
        last = ["Hayes", "Morrow", "Dalton", "Reed", "Carter", "Fletcher", "Keane", "Walters", "Briggs", "Holloway"]
        positions = ["GK", "RB", "LB", "CB", "CM", "DM", "AM", "RW", "LW", "CF"]
        name = f"{random.choice(first)} {random.choice(last)}"
        age = random.randint(16, 18)
        rating = random.randint(50, 68)
        potential = random.randint(70, 92)
        pos = random.choice(positions)
        return {"name": name, "age": age, "rating": rating, "potential": potential, "pos": pos}

    def run_youth_intake(self):
        if self.academy_intake_done:
            self.add_commentary("Youth intake already completed")
            return
        self.academy_intake_done = True
        intake = [self.generate_youth_player() for _ in range(5)]
        self.academy.extend(intake)
        self.add_commentary("Youth intake complete")

    def promote_academy_player(self, idx):
        if idx < 0 or idx >= len(self.academy):
            return
        prospect = self.academy.pop(idx)
        name = prospect["name"]
        rating = prospect["rating"]
        number = self.assign_unique_number(self.user_team, random.randint(30, 99))
        player_tuple = (name, number, rating)
        self.user_reserves.append(player_tuple)
        TEAM_LINEUPS.setdefault(self.user_team, []).append(player_tuple)
        self.add_commentary(f"Promoted {name} to first team")

    def reset_season_stats(self):
        self.season_stats = {}
        self.last_assist_candidate = None
        self.last_assist_team = None
        self.half_season_boosted = False

    def register_stat(self, name, stat, amount=1):
        if not name:
            return
        entry = self.season_stats.setdefault(
            name, {"goals": 0, "assists": 0, "clean_sheets": 0, "tackles": 0}
        )
        entry[stat] = entry.get(stat, 0) + amount
        if self.state == "LIVE":
            live_entry = self.match_player_stats.setdefault(
                name, {"goals": 0, "assists": 0, "clean_sheets": 0, "tackles": 0}
            )
            live_entry[stat] = live_entry.get(stat, 0) + amount

    def get_player_stat(self, name, stat):
        return self.season_stats.get(name, {}).get(stat, 0)

    def get_user_stat_names(self):
        if self.game_mode == "FANTASY":
            names = [card["name"] for card in self.fantasy_roster]
            return names if names else [name for name, _, _ in self.user_starting]
        return [name for name, _, _ in self.user_starting]

    def get_user_stat_total(self, stat):
        return sum(self.get_player_stat(name, stat) for name in self.get_user_stat_names())

    def match_standout(self):
        if not self.match_player_stats:
            return None
        def score(item):
            name, stats = item
            return (
                stats.get("goals", 0) * 5
                + stats.get("assists", 0) * 3
                + stats.get("clean_sheets", 0) * 4
                + stats.get("tackles", 0) * 1.5
            )
        name, stats = max(self.match_player_stats.items(), key=score)
        return name, stats

    def set_match_scene(self, moment):
        self.match_scene_moment = moment
        standout = self.match_standout()
        if moment == "pre":
            self.match_scene_title = "MATCH INTRO"
            if self.current_competition and self.current_competition not in ("LEAGUE", "Division Match"):
                self.match_scene_subtitle = f"{self.current_competition}: {self.current_home} vs {self.current_away}"
            else:
                self.match_scene_subtitle = f"{self.current_home} vs {self.current_away}"
            self.match_scene_continue = "LIVE"
            self.match_scene_total = 6.4
        elif moment == "half":
            self.match_scene_title = "HALFTIME"
            self.match_scene_subtitle = "Reset, tweak the shape, and push the key man."
            if standout:
                self.match_scene_subtitle = f"Standout so far: {standout[0]}"
            self.match_scene_continue = "LIVE"
            self.match_scene_total = 4.2
        elif moment == "full":
            user_goals = self.score_h if self.user_is_home else self.score_a
            opp_goals = self.score_a if self.user_is_home else self.score_h
            if user_goals > opp_goals:
                self.match_scene_title = "FULL TIME WIN"
            elif user_goals == opp_goals:
                self.match_scene_title = "FULL TIME DRAW"
            else:
                self.match_scene_title = "FULL TIME LOSS"
            if standout:
                stats = standout[1]
                self.match_scene_subtitle = f"Player of the Match: {standout[0]}  G{stats.get('goals',0)} A{stats.get('assists',0)} T{stats.get('tackles',0)}"
            else:
                self.match_scene_subtitle = f"{self.current_home} {self.score_h} - {self.score_a} {self.current_away}"
            self.match_scene_continue = "FINISH_MATCH"
            self.match_scene_total = 4.6
        else:
            self.match_scene_title = ""
            self.match_scene_subtitle = ""
            self.match_scene_continue = "LIVE"
            self.match_scene_total = 0.0
        self.match_scene_timer = self.match_scene_total

    def match_scene_lineup(self, team):
        lineup = TEAM_LINEUPS.get(team, DEFAULT_LINEUP)
        if self.user_team and team == self.user_team and self.user_starting:
            return self.user_starting
        return [normalize_entry(entry, i, team) for i, entry in enumerate(lineup[:11])]

    def draw_match_scene(self):
        if not self.match_scene_title:
            return
        self.screen.fill((10, 14, 24))
        panel = pygame.Rect(120, 86, WIDTH - 240, HEIGHT - 200)
        pygame.draw.rect(self.screen, (12, 18, 28), panel, 0, border_radius=24)
        pygame.draw.rect(self.screen, (244, 206, 84), panel, 2, border_radius=24)
        self.screen.blit(self.big.render(self.match_scene_title, True, WHITE), (panel.x + 30, panel.y + 26))
        self.screen.blit(self.font.render(self.match_scene_subtitle[:72], True, (214, 222, 236)), (panel.x + 30, panel.y + 68))
        comp_text = self.current_competition if self.current_competition else "Match"
        self.screen.blit(self.small.render(comp_text, True, (190, 200, 215)), (panel.x + 32, panel.y + 104))

        score_line = f"{self.current_home} {self.score_h} - {self.score_a} {self.current_away}"
        self.screen.blit(self.big.render(score_line, True, WHITE), (panel.x + 30, panel.y + 146))

        if self.match_scene_moment == "pre":
            progress = 0.0 if self.match_scene_total <= 0 else max(0.0, min(1.0, 1.0 - (self.match_scene_timer / self.match_scene_total)))
            home_lineup = self.match_scene_lineup(self.current_home)
            away_lineup = self.match_scene_lineup(self.current_away)
            lineup_positions = self.get_home_positions()
            phase = "home" if progress < 0.5 else "away"
            phase_progress = min(1.0, progress / 0.5) if phase == "home" else min(1.0, (progress - 0.5) / 0.5)
            active_team = self.current_home if phase == "home" else self.current_away
            active_lineup = home_lineup if phase == "home" else away_lineup
            reveal_value = phase_progress * 11
            shown_count = min(11, int(reveal_value))
            flip_index = min(10, shown_count)
            flip_progress = 1.0 if shown_count >= 11 else max(0.0, reveal_value - shown_count)
            info_panel = pygame.Rect(panel.x + 22, panel.y + 198, 220, 250)
            pitch_rect = pygame.Rect(panel.x + 262, panel.y + 190, panel.w - 286, panel.h - 118)
            pygame.draw.rect(self.screen, (18, 24, 36), info_panel, 0, border_radius=18)
            pygame.draw.rect(self.screen, (72, 92, 132), info_panel, 2, border_radius=18)
            pygame.draw.rect(self.screen, (18, 56, 34), pitch_rect, 0, border_radius=22)
            pygame.draw.rect(self.screen, (225, 230, 235), pitch_rect, 2, border_radius=22)
            for stripe in range(8):
                stripe_y = pitch_rect.y + stripe * (pitch_rect.h // 8)
                color = (20, 66, 38) if stripe % 2 == 0 else (18, 60, 34)
                pygame.draw.rect(self.screen, color, (pitch_rect.x + 2, stripe_y, pitch_rect.w - 4, pitch_rect.h // 8))
            pygame.draw.line(self.screen, (235, 235, 235), (pitch_rect.centerx, pitch_rect.y + 18), (pitch_rect.centerx, pitch_rect.bottom - 18), 2)
            pygame.draw.circle(self.screen, (235, 235, 235), pitch_rect.center, 56, 2)
            pygame.draw.rect(self.screen, (235, 235, 235), (pitch_rect.x + 18, pitch_rect.centery - 106, 96, 212), 2)
            pygame.draw.rect(self.screen, (235, 235, 235), (pitch_rect.right - 114, pitch_rect.centery - 106, 96, 212), 2)
            pygame.draw.rect(self.screen, (235, 235, 235), (pitch_rect.x + 18, pitch_rect.centery - 52, 42, 104), 2)
            pygame.draw.rect(self.screen, (235, 235, 235), (pitch_rect.right - 60, pitch_rect.centery - 52, 42, 104), 2)

            tactic_name = {
                1: "4-4-2",
                2: "4-3-3",
                3: "3-5-2",
                4: "4-2-3-1",
                5: "5-3-2",
                6: "4-1-4-1",
                7: "4-2-2-2",
                8: "3-4-3",
            }.get(self.tactic, "4-3-3")
            avg_rating = int(sum(entry[2] for entry in active_lineup) / max(1, len(active_lineup)))
            rating_stars = max(1, min(5, round(avg_rating / 20)))
            self.screen.blit(self.font.render("Starting XI", True, (214, 222, 236)), (info_panel.x + 16, info_panel.y + 16))
            self.screen.blit(self.big.render(active_team[:16], True, WHITE), (info_panel.x + 16, info_panel.y + 42))
            self.screen.blit(self.font.render(f"Rating  {avg_rating}", True, WHITE), (info_panel.x + 16, info_panel.y + 88))
            self.screen.blit(self.font.render("".join(["*"] * rating_stars), True, (244, 206, 84)), (info_panel.x + 16, info_panel.y + 114))
            side_lines = [
                "Card flip reveal",
                f"Formation  {tactic_name}",
                f"{'Home' if phase == 'home' else 'Away'} XI  {min(11, shown_count + (1 if flip_progress > 0 and shown_count < 11 else 0))}/11",
            ]
            side_y = info_panel.y + 160
            for line in side_lines:
                self.screen.blit(self.small.render(line, True, (205, 215, 228)), (info_panel.x + 16, side_y))
                side_y += 30

            card_w = 84
            card_h = 106
            field_left = FIELD_MARGIN
            field_width = WIDTH - 2 * FIELD_MARGIN
            field_height = HEIGHT - 2 * FIELD_MARGIN

            def draw_flipping_lineup_card(entry, card_x, card_y, role, flip_norm):
                flip_norm = max(0.0, min(1.0, flip_norm))
                back_rect = pygame.Rect(int(card_x), int(card_y), card_w, card_h)
                if flip_norm < 0.5:
                    width_scale = max(0.08, 1.0 - flip_norm * 1.84)
                    draw_w = max(8, int(card_w * width_scale))
                    draw_x = int(card_x + (card_w - draw_w) / 2)
                    pygame.draw.rect(self.screen, (18, 24, 38), (draw_x, int(card_y), draw_w, card_h), 0, border_radius=14)
                    pygame.draw.rect(self.screen, (244, 206, 84), (draw_x, int(card_y), draw_w, card_h), 2, border_radius=14)
                    pygame.draw.line(self.screen, (244, 206, 84), (draw_x + draw_w // 2, int(card_y) + 10), (draw_x + draw_w // 2, int(card_y) + card_h - 10), 2)
                else:
                    width_scale = max(0.08, (flip_norm - 0.5) * 2.0)
                    draw_w = max(8, int(card_w * width_scale))
                    draw_x = int(card_x + (card_w - draw_w) / 2)
                    temp_surface = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
                    prev_screen = self.screen
                    self.screen = temp_surface
                    self.draw_squad_card(0, 0, card_w, card_h, entry, role=role, selected=True)
                    self.screen = prev_screen
                    scaled = pygame.transform.smoothscale(temp_surface, (draw_w, card_h))
                    self.screen.blit(scaled, (draw_x, int(card_y)))

            for idx, entry in enumerate(active_lineup[:11]):
                px, py, role = lineup_positions[idx]
                rel_x = (px - field_left) / field_width
                rel_y = (py - FIELD_MARGIN) / field_height
                card_x = pitch_rect.x + rel_x * pitch_rect.w - card_w / 2
                card_y = pitch_rect.y + rel_y * pitch_rect.h - card_h / 2
                label_y = card_y + card_h + 8
                if idx < shown_count:
                    self.draw_squad_card(card_x, card_y, card_w, card_h, entry, role=role, selected=False)
                    self.screen.blit(self.small.render(role, True, (190, 220, 255)), (card_x + card_w / 2 - 14, label_y))
                elif idx == flip_index and shown_count < 11:
                    draw_flipping_lineup_card(entry, card_x, card_y, role, flip_progress)
                    if flip_progress > 0.55:
                        self.screen.blit(self.small.render(role, True, (190, 220, 255)), (card_x + card_w / 2 - 14, label_y))

            phase_text = f"Now showing: {'Home XI' if phase == 'home' else 'Away XI'}"
            reveal_text = f"{self.current_home} first  |  {self.current_away} next" if phase == "home" else f"{self.current_away} reveal  |  Kickoff next"
            self.screen.blit(self.small.render(phase_text, True, (190, 200, 215)), (panel.x + 30, panel.bottom - 64))
            self.screen.blit(self.small.render(reveal_text, True, (190, 200, 215)), (panel.x + 30, panel.bottom - 42))
            return

        total_pos = self.stats["H"]["pos_time"] + self.stats["A"]["pos_time"]
        if total_pos <= 0:
            pos_h = pos_a = 50
        else:
            pos_h = int((self.stats["H"]["pos_time"] / total_pos) * 100)
            pos_a = 100 - pos_h
        def pass_pct(team):
            att = self.stats[team]["pass_att"]
            cmp = self.stats[team]["pass_cmp"]
            return int((cmp / att) * 100) if att > 0 else 0
        lines = [
            f"Possession: {pos_h}% - {pos_a}%",
            f"Shots: {self.stats['H']['shots']} - {self.stats['A']['shots']}",
            f"Pass %: {pass_pct('H')}% - {pass_pct('A')}%",
        ]
        y = panel.y + 206
        for line in lines:
            self.screen.blit(self.font.render(line, True, WHITE), (panel.x + 30, y))
            y += 36

        standout = self.match_standout()
        if standout:
            name, stats = standout
            self.screen.blit(self.font.render("Standout", True, (244, 206, 84)), (panel.x + 520, panel.y + 206))
            detail = [
                name,
                f"Goals: {stats.get('goals', 0)}",
                f"Assists: {stats.get('assists', 0)}",
                f"Tackles: {stats.get('tackles', 0)}",
                f"Clean Sheets: {stats.get('clean_sheets', 0)}",
            ]
            sy = panel.y + 246
            for line in detail:
                self.screen.blit(self.font.render(line[:26], True, WHITE), (panel.x + 520, sy))
                sy += 34
        if self.match_scene_moment == "full" and self.game_mode == "FANTASY":
            self.screen.blit(self.small.render("+50 coins match reward locked", True, LIGHT_GREEN), (panel.x + 30, panel.bottom - 64))
        self.screen.blit(self.small.render("ENTER or SPACE continue", True, (190, 200, 215)), (panel.x + 30, panel.bottom - 34))

    def award_player(self, name, award):
        if not name:
            return
        awards = self.player_awards.setdefault(name, set())
        awards.add(award)

    def build_user_squad(self):
        if not self.user_team:
            return
        lineup = TEAM_LINEUPS.get(self.user_team)
        if self.game_mode == "FANTASY":
            needs_rebuild = (
                not isinstance(lineup, list)
                or len(lineup) < min(11, len(self.fantasy_roster))
            )
            if needs_rebuild and self.fantasy_roster:
                used_numbers = set()
                rebuilt_lineup = []
                rebuilt_reserves = []
                for i, card in enumerate(self.fantasy_roster):
                    suggested = card.get("number", random.randint(1, 99))
                    number = suggested
                    while number in used_numbers:
                        number += 1
                    used_numbers.add(number)
                    card["number"] = number
                    entry = (card["name"], number, card["rating"])
                    if i < 11:
                        rebuilt_lineup.append(entry)
                    else:
                        rebuilt_reserves.append(entry)
                TEAM_LINEUPS[self.user_team] = rebuilt_lineup
                ROSTER_DATA[self.user_team] = rebuilt_reserves
                self.apply_fantasy_club_identity()
        lineup = TEAM_LINEUPS.get(self.user_team, DEFAULT_LINEUP)
        starters = [
            normalize_entry(entry, i, self.user_team) for i, entry in enumerate(lineup[:11])
        ]
        bench = []
        reserves = []
        used = {(name, num, rating) for name, num, rating in starters}
        extra = lineup[11:]
        roster = ROSTER_DATA.get(self.user_team, [])
        for entry in extra:
            n, num, rating = normalize_entry(entry, 0, self.user_team)
            if (n, num, rating) in used:
                continue
            if len(bench) < 10:
                bench.append((n, num, rating))
            else:
                reserves.append((n, num, rating))
            used.add((n, num, rating))
        for entry in roster:
            n, num, rating = normalize_entry(entry, 0, self.user_team)
            if (n, num, rating) in used:
                continue
            if len(bench) < 10:
                bench.append((n, num, rating))
            else:
                reserves.append((n, num, rating))
            used.add((n, num, rating))
        self.user_starting = starters
        self.user_bench = bench
        self.user_reserves = reserves

    def persist_user_squad_layout(self):
        if not self.user_team:
            return
        TEAM_LINEUPS[self.user_team] = self.user_starting[:] + self.user_bench[:]
        ROSTER_DATA[self.user_team] = self.user_reserves[:]

    def sync_fantasy_card_rating(self, card):
        if not self.user_team or not card:
            return
        self.update_team_lineup_rating(self.user_team, card["name"], card.get("number", 0), card["rating"])
        roster = ROSTER_DATA.get(self.user_team, [])
        for i, entry in enumerate(roster):
            name, num, rating = normalize_entry(entry, i, self.user_team)
            if name == card["name"] and num == card.get("number", num):
                roster[i] = (name, num, card["rating"])
                break
        self.persist_user_squad_layout()
        self.build_user_squad()

    def fantasy_evolution_paths(self, card):
        position = card.get("position", "ST")
        goals = self.get_player_stat(card["name"], "goals")
        assists = self.get_player_stat(card["name"], "assists")
        tackles = self.get_player_stat(card["name"], "tackles")
        clean = self.get_player_stat(card["name"], "clean_sheets")
        paths = [
            {
                "name": "Performance Boost",
                "delta": 2,
                "cost": 70 + card.get("evo_level", 0) * 20,
                "need_label": "5 goals or assists",
                "ready": goals >= 5 or assists >= 5,
                "trait": "Playmaker" if position in ("CM", "AM", "LM", "RM", "LW", "RW", "CF") else "Finesse Shot",
            },
            {
                "name": "Role Upgrade",
                "delta": 3,
                "cost": 110 + card.get("evo_level", 0) * 25,
                "need_label": "6 tackles / 3 clean sheets / 4 goals",
                "ready": tackles >= 6 or clean >= 3 or goals >= 4,
                "trait": "Interceptor" if position in ("GK", "CB", "LB", "RB", "DM") else "Aerial",
            },
            {
                "name": "Finisher Craft",
                "delta": 4,
                "cost": 145 + card.get("evo_level", 0) * 30,
                "need_label": "8 goals or 5 assists",
                "ready": goals >= 8 or assists >= 5,
                "trait": "Finesse Shot" if position not in ("GK", "CB") else "Press Resist",
            },
            {
                "name": "Engine Room",
                "delta": 3,
                "cost": 130 + card.get("evo_level", 0) * 25,
                "need_label": "10 tackles / 6 assists / 4 clean sheets",
                "ready": tackles >= 10 or assists >= 6 or clean >= 4,
                "trait": "Playmaker" if position not in ("GK", "CB", "LB", "RB") else "Interceptor",
            },
        ]
        event = self.get_pack_event_by_id(card.get("event_source"))
        if event and self.event_evo_tokens > 0:
            paths.append(
                {
                    "name": f"{event.get('name', 'Event')} Evolution",
                    "delta": 3,
                    "cost": 90,
                    "need_label": "Open an event pack and spend 1 event evo token",
                    "ready": self.event_evo_tokens > 0 and self.fantasy_coins >= 90,
                    "trait": "Playmaker" if position in ("CM", "AM", "LM", "RM", "LW", "RW", "CF") else "Interceptor",
                    "requires_event_token": True,
                    "promo": event.get("evo_promo", event.get("promo", card.get("promo", "Base"))),
                    "event_name": event.get("name", "Event"),
                    "event_colors": event.get("colors"),
                }
            )
            paths.append(
                {
                    "name": f"{event.get('name', 'Event')} Mastery",
                    "delta": 5,
                    "cost": 150,
                    "need_label": "Open an event pack, spend 1 token, and have 1 evo level",
                    "ready": self.event_evo_tokens > 0 and self.fantasy_coins >= 150 and card.get("evo_level", 0) >= 1,
                    "trait": "Aerial" if position in ("ST", "CB", "GK") else "Press Resist",
                    "requires_event_token": True,
                    "promo": event.get("evo_promo", event.get("promo", card.get("promo", "Base"))),
                    "event_name": event.get("name", "Event"),
                    "event_colors": event.get("colors"),
                }
            )
        return paths

    def apply_fantasy_evolution(self, card_idx, choice_idx):
        if card_idx < 0 or card_idx >= len(self.fantasy_roster):
            return
        card = self.fantasy_roster[card_idx]
        paths = self.fantasy_evolution_paths(card)
        if choice_idx < 0 or choice_idx >= len(paths):
            return
        path = paths[choice_idx]
        if path.get("requires_event_token") and self.event_evo_tokens <= 0:
            self.add_commentary("Acquire an event evolution token first")
            return
        if card.get("evo_level", 0) >= 5:
            self.add_commentary("This card has reached the evolution cap")
            return
        if not path["ready"]:
            self.add_commentary("Evolution requirements not met")
            return
        if self.fantasy_coins < path["cost"]:
            self.add_commentary("Not enough coins for this evolution")
            return
        self.fantasy_coins -= path["cost"]
        if path.get("requires_event_token"):
            self.event_evo_tokens -= 1
            card["promo"] = path.get("promo", card.get("promo", "Base"))
            card["event_evolution"] = path.get("event_name", "Event")
            if path.get("event_colors"):
                card["event_evo_colors"] = [tuple(path["event_colors"][0]), tuple(path["event_colors"][1])]
        card["rating"] += path["delta"]
        card["evo_level"] = card.get("evo_level", 0) + 1
        traits = list(card.get("traits", []))
        if path["trait"] not in traits:
            traits.append(path["trait"])
        card["traits"] = traits[:3]
        card["rarity"] = self.card_rarity_from_rating(card["rating"], card.get("promo", "Base"))
        card["card_key"] = f"{card['name']}|{card.get('promo', 'Base')}|{card['rating']}|{card.get('position', 'ST')}"
        self.sync_fantasy_card_rating(card)
        self.add_commentary(f"Evolution applied: {card['name']} +{path['delta']}")
        self.user_squad = starters + bench + reserves
        self.update_fantasy_chemistry()

    def build_fantasy_pool(self):
        pool = []
        seen = set()

        def normalize_rating_name(value):
            if isinstance(value, (list, tuple)):
                return "|".join(str(v) for v in value)
            return value

        def normalize_name_key(name):
            if isinstance(name, (list, tuple, set)):
                return tuple(name)
            return name

        def add_special_variants(name, team, rating, num, idx):
            variants = []
            position = self.infer_card_position(idx)
            if rating >= 84 and random.random() < 0.002:
                if rating >= 92:
                    variants.append((random.choice(["TOTY", "Dynasty", "Phantom"]), rating + random.randint(18, 28)))
                elif rating >= 90:
                    variants.append((random.choice(["Neon", "Thunder", "Ice", "RTTK"]), rating + random.randint(12, 20)))
                elif rating >= 88:
                    variants.append((random.choice(["Future Star", "Shapeshifter", "Centurions"]), rating + random.randint(8, 14)))
                else:
                    variants.append((random.choice(["TOTW", "Hero"]), rating + random.randint(3, 8)))

            for promo, promo_rating in variants:
                forged = {
                    "name": name,
                    "team": team,
                    "league": get_team_league(team),
                    "nation": get_player_nation(name, team),
                    "rating": promo_rating,
                    "base_rating": rating,
                    "price": max(5, int(promo_rating * 0.6)),
                    "number": num,
                    "position": position,
                    "rarity": self.card_rarity_from_rating(promo_rating, promo),
                    "promo": promo,
                    "evo_level": 0,
                    "milestone_level": 0,
                    "form_boost": 0,
                    "pull_count": 1,
                    "duplicate_protected": False,
                    "traits": self.generate_card_traits(position, self.card_rarity_from_rating(promo_rating, promo), promo),
                }
                forged["card_key"] = f"{name}|{promo}|{forged['rating']}|{position}"
                pool.append(forged)

        for team, lineup in BASE_FANTASY_LINEUPS.items():
            for idx, entry in enumerate(lineup):
                name, num = lineup_name_number(entry, idx)
                key = normalize_name_key(name)
                if key in seen:
                    continue
                rating = entry[2] if isinstance(entry, (tuple, list)) and len(entry) > 2 else probable_rating(normalize_rating_name(name), team, 70)
                pool.append(self.make_fantasy_card(name, team, rating, num, idx))
                add_special_variants(name, team, rating, num, idx)
                seen.add(key)
        for team, roster in BASE_FANTASY_ROSTERS.items():
            for idx, entry in enumerate(roster):
                name, num = lineup_name_number(entry, idx)
                key = normalize_name_key(name)
                if key in seen:
                    continue
                rating = entry[2] if isinstance(entry, (tuple, list)) and len(entry) > 2 else probable_rating(normalize_rating_name(name), team, 70)
                pool.append(self.make_fantasy_card(name, team, rating, num, idx))
                add_special_variants(name, team, rating, num, idx)
                seen.add(key)
        for idx, icon in enumerate(ICON_PLAYERS):
            card = {
                "name": icon["name"],
                "team": icon["team"],
                "league": get_team_league(icon["team"]),
                "nation": get_player_nation(icon["name"], icon["team"]),
                "rating": icon["rating"],
                "base_rating": icon["rating"],
                "price": max(5, int(icon["rating"] * 0.6)),
                "number": 80 + idx,
                "position": icon["position"],
                "rarity": "Icon",
                "promo": "Base",
                "evo_level": 0,
                "milestone_level": 0,
                "form_boost": 0,
                "pull_count": 1,
                "duplicate_protected": True,
                "traits": self.generate_card_traits(icon["position"], "Icon", "Base"),
            }
            card["card_key"] = f"{card['name']}|ICON|{card['rating']}|{card['position']}"
            pool.append(card)
        for idx, player in enumerate(WORLD_LEAGUE_PLAYERS):
            name = player["name"]
            team = player["team"]
            rating = player["rating"]
            position = player["position"]
            if name in seen:
                continue
            card = {
                "name": name,
                "team": team,
                "league": get_team_league(team),
                "nation": get_player_nation(name, team),
                "rating": rating,
                "base_rating": rating,
                "price": max(5, int(rating * 0.6)),
                "number": 30 + idx,
                "position": position,
                "rarity": self.card_rarity_from_rating(rating, "Base"),
                "promo": "Base",
                "evo_level": 0,
                "milestone_level": 0,
                "form_boost": 0,
                "pull_count": 1,
                "duplicate_protected": False,
                "traits": self.generate_card_traits(position, self.card_rarity_from_rating(rating, "Base"), "Base"),
            }
            card["card_key"] = f"{name}|Base|{rating}|{position}"
            pool.append(card)
            seen.add(name)
        for idx, player in enumerate(EXTRA_WORLD_PLAYERS):
            name = player["name"]
            team = player["team"]
            rating = player["rating"]
            position = player["position"]
            if name in seen:
                continue
            card = {
                "name": name,
                "team": team,
                "league": get_team_league(team),
                "nation": get_player_nation(name, team),
                "rating": rating,
                "base_rating": rating,
                "price": max(5, int(rating * 0.6)),
                "number": 140 + idx,
                "position": position,
                "rarity": self.card_rarity_from_rating(rating, "Base"),
                "promo": "Base",
                "evo_level": 0,
                "milestone_level": 0,
                "form_boost": 0,
                "pull_count": 1,
                "duplicate_protected": False,
                "traits": self.generate_card_traits(position, self.card_rarity_from_rating(rating, "Base"), "Base"),
            }
            card["card_key"] = f"{name}|Base|{rating}|{position}"
            pool.append(card)
            seen.add(name)
        for idx, goat in enumerate(GOAT_PLAYERS):
            card = {
                "name": goat["name"],
                "team": goat["team"],
                "league": get_team_league(goat["team"]),
                "nation": get_player_nation(goat["name"], goat["team"]),
                "rating": goat["rating"],
                "base_rating": goat["rating"],
                "price": max(5, int(goat["rating"] * 0.6)),
                "number": 95 + idx,
                "position": goat["position"],
                "rarity": "GOAT",
                "promo": "Base",
                "evo_level": 0,
                "milestone_level": 0,
                "form_boost": 0,
                "pull_count": 1,
                "duplicate_protected": True,
                "traits": self.generate_card_traits(goat["position"], "GOAT", "Base"),
            }
            card["card_key"] = f"{card['name']}|GOAT|{card['rating']}|{card['position']}"
            pool.append(card)
        for idx, player in enumerate(SIGNATURE_PLAYERS):
            card = {
                "name": player["name"],
                "team": player["team"],
                "league": get_team_league(player["team"]),
                "nation": get_player_nation(player["name"], player["team"]),
                "rating": player["rating"],
                "base_rating": player["rating"],
                "price": max(5, int(player["rating"] * 0.6)),
                "number": 170 + idx,
                "position": player["position"],
                "rarity": self.card_rarity_from_rating(player["rating"], "Signature"),
                "promo": "Signature",
                "evo_level": 0,
                "milestone_level": 0,
                "form_boost": 0,
                "pull_count": 1,
                "duplicate_protected": True,
                "traits": self.generate_card_traits(player["position"], self.card_rarity_from_rating(player["rating"], "Signature"), "Signature"),
            }
            card["card_key"] = f"{card['name']}|Signature|{card['rating']}|{card['position']}"
            pool.append(card)
        fantasy_team_names = {name.strip() for name in (self.user_team, self.fantasy_team_name) if isinstance(name, str) and name.strip()}
        if fantasy_team_names:
            pool = [card for card in pool if card.get("team") not in fantasy_team_names]
        pool.sort(key=lambda p: (-p["rating"], p["name"]))
        self.fantasy_pool = pool
        self.fantasy_index = 0

    def init_audio(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1)
            self.walkout_sounds = {
                "Bronze": make_tone(280, 0.10, 0.16),
                "Silver": make_tone(420, 0.12, 0.17),
                "Gold": make_tone(620, 0.15, 0.18),
                "Platinum": make_tone(700, 0.17, 0.18),
                "Elite": make_tone(760, 0.18, 0.18),
                "Diamond": make_tone(820, 0.20, 0.19),
                "Mythic": make_tone(880, 0.21, 0.19),
                "Ascended": make_tone(905, 0.215, 0.19),
                "Icon": make_tone(840, 0.20, 0.19),
                "GOAT": make_tone(990, 0.32, 0.22),
                "Legend": make_tone(920, 0.22, 0.19),
            }
            self.sound_enabled = True
        except Exception:
            self.sound_enabled = False
            self.walkout_sounds = {}

    def init_fantasy_competitions(self):
        self.current_theme = random.choice(["Premier Pulse", "Counter Kings", "Clean Sheet Club", "North London Heat", "Power Finish"])
        self.fantasy_competitions = {
            "division": {"tier": 10, "points": 0, "played": 0, "wins": 0, "reward": 120, "reward_type": "coins"},
            "ladder": {"week": 1, "points": 0, "played": 0, "wins": 0, "streak": 0, "target": 6, "reward_pack": "elite", "reward_coins": 160, "reward_type": "hybrid"},
            "cup": {"round": 1, "alive": True, "wins": 0, "reward_pack": "elite", "reward_type": "pack"},
            "weekend": {"played": 0, "wins": 0, "target": 5, "reward_pack": "gold", "reward_coins": 80, "active": True, "reward_type": "hybrid"},
            "theme": {"name": self.current_theme, "progress": 0, "target": 3, "reward_type": "pick", "pick_count": 3, "pick_band": "Mythic"},
            "draft": {"wins": 0, "losses": 0, "target": 4, "max_losses": 2, "reward_type": "bundle", "reward_pack": "omega", "reward_coins": 260, "pick_count": 3, "pick_band": "Legend", "ready": False},
            "champions": {
                "round": 0,
                "reward_pack": "transcendent",
                "reward_coins": 240,
                "reward_type": "hybrid",
                "bracket": ["Round of 16", "Quarter Final", "Semi Final", "Final", "Champions"],
                "pairings": [[], [], [], []],
                "winners": [[], [], [], []],
                "champion": None,
            },
            "silver": {"wins": 0, "target": 3, "reward_pack": "silver", "reward_type": "pack", "alive": True},
            "promo": {"wins": 0, "target": 3, "reward_pack": "event", "reward_type": "pack", "alive": True},
            "signature": {"wins": 0, "target": 2, "reward_type": "pick", "pick_count": 2, "pick_band": "signature", "alive": True},
        }
        if self.user_team:
            self.reset_champions_bracket()
        self.roll_pack_event()

    def pack_event_catalog(self):
        promo_entries = [
            ("TOTW", "TOTW Flash", "Stacked TOTW release"),
            ("TOTY", "TOTY Frenzy", "Higher TOTY odds this week"),
            ("Hero", "Hero Spotlight", "Hero cards boosted"),
            ("Future Star", "Future Star Showcase", "Future Stars get the spotlight"),
            ("Centurions", "Centurion Surge", "Centurions pick weight"),
            ("Shapeshifter", "Shapeshifter Shift", "Shapeshifter cards up"),
            ("Phantom", "Phantom Pulse", "Phantom cards glow"),
            ("Dynasty", "Dynasty Wave", "Dynasty icons thrive"),
            ("RTTK", "RTTK Rush", "RTTK heads up"),
            ("Neon", "Neon Night", "Neon cards shine"),
            ("Clutch", "Clutch Run", "Clutch boosts"),
        ]
        events = [
            {
                "id": "premier_spotlight",
                "name": "Premier Spotlight",
                "subtitle": "Premier League cards boosted in normal packs",
                "league": "Premier League",
                "featured_pack": "premier_league",
                "signature_names": ["Mohamed Salah"],
                "colors": ((20, 42, 92), (86, 170, 255)),
            },
            {
                "id": "galactico_wave",
                "name": "Galactico Wave",
                "subtitle": "La Liga stars and signature elites boosted",
                "league": "La Liga",
                "featured_pack": "la_liga",
                "signature_names": ["Kylian Mbappe", "Jude Bellingham", "Vinicius Junior"],
                "colors": ((58, 20, 92), (255, 214, 112)),
            },
            {
                "id": "signature_series",
                "name": "Signature Series",
                "subtitle": "Signature stars first pick",
                "league": None,
                "featured_pack": "signature",
                "signature_names": ["Kylian Mbappe", "Erling Haaland", "Jude Bellingham", "Vinicius Junior"],
                "colors": ((16, 18, 24), (255, 214, 112)),
            },
            {
                "id": "saudi_flash",
                "name": "Saudi Flash",
                "subtitle": "Saudi Pro League event with boosted stars",
                "league": "Saudi Pro League",
                "featured_pack": "saudi",
                "signature_names": ["Neymar"],
                "colors": ((10, 78, 52), (96, 255, 156)),
            },
        ]
        for promo, name, subtitle in promo_entries:
            events.append(
                {
                    "id": f"promo_{promo.lower()}",
                    "name": name,
                    "subtitle": subtitle,
                    "league": None,
                    "featured_pack": "promo",
                    "promo": promo,
                    "colors": ((30, 18, 64), (192, 96, 255)),
                }
            )
        return events

    def pack_event_catalog(self):
        events = [
            {
                "id": "premier_spotlight",
                "name": "Premier Spotlight",
                "subtitle": "Premier League cards boosted in normal packs",
                "league": "Premier League",
                "featured_pack": "premier_league",
                "signature_names": ["Mohamed Salah"],
                "colors": ((20, 42, 92), (86, 170, 255)),
                "evo_promo": "RTTK",
            },
            {
                "id": "galactico_wave",
                "name": "Galactico Wave",
                "subtitle": "La Liga stars and signature elites boosted",
                "league": "La Liga",
                "featured_pack": "la_liga",
                "signature_names": ["Kylian Mbappe", "Jude Bellingham", "Vinicius Junior"],
                "colors": ((58, 20, 92), (255, 214, 112)),
                "evo_promo": "Dynasty",
            },
            {
                "id": "bundes_fire",
                "name": "Bundes Fire",
                "subtitle": "Bundesliga attackers get extra pack weight",
                "league": "Bundesliga",
                "featured_pack": "bundesliga",
                "signature_names": ["Harry Kane", "Jamal Musiala"],
                "colors": ((92, 18, 24), (255, 120, 120)),
                "evo_promo": "Thunder",
            },
            {
                "id": "signature_series",
                "name": "Signature Series",
                "subtitle": "Featured signatures get the brightest banner",
                "league": None,
                "featured_pack": "signature",
                "signature_names": ["Kylian Mbappe", "Erling Haaland", "Jude Bellingham", "Vinicius Junior"],
                "colors": ((16, 18, 24), (255, 214, 112)),
                "evo_promo": "Signature",
            },
            {
                "id": "saudi_flash",
                "name": "Saudi Flash",
                "subtitle": "Saudi Pro League event with boosted stars",
                "league": "Saudi Pro League",
                "featured_pack": "saudi",
                "signature_names": ["Neymar"],
                "colors": ((10, 78, 52), (96, 255, 156)),
                "evo_promo": "Neon",
            },
        ]
        promo_entries = [
            ("TOTW", "TOTW Flash", "Stacked TOTW release"),
            ("TOTY", "TOTY Frenzy", "Higher TOTY odds this week"),
            ("Hero", "Hero Spotlight", "Hero cards boosted"),
            ("Future Star", "Future Star Showcase", "Future Stars get the spotlight"),
            ("Centurions", "Centurion Surge", "Centurions pick weight"),
            ("Shapeshifter", "Shapeshifter Shift", "Shapeshifter cards up"),
            ("Phantom", "Phantom Pulse", "Phantom cards glow"),
            ("Dynasty", "Dynasty Wave", "Dynasty cards thrive"),
            ("RTTK", "RTTK Rush", "RTTK heads up"),
            ("Neon", "Neon Night", "Neon cards shine"),
            ("Clutch", "Clutch Run", "Clutch boosts"),
            ("Ice", "Ice Storm", "Ice cards boosted"),
            ("Thunder", "Thunder Clash", "Thunder cards boosted"),
        ]
        for promo, name, subtitle in promo_entries:
            events.append(
                {
                    "id": f"promo_{promo.lower().replace(' ', '_')}",
                    "name": name,
                    "subtitle": subtitle,
                    "league": None,
                    "featured_pack": "promo",
                    "promo": promo,
                    "colors": ((30, 18, 64), (192, 96, 255)),
                    "evo_promo": promo,
                }
            )
        return events

    def roll_pack_event(self, advance=False):
        catalog = self.pack_event_catalog()
        if not catalog:
            self.current_pack_event = {}
            self.pack_event_index = -1
            return
        if advance or self.pack_event_index < 0:
            self.pack_event_index = (self.pack_event_index + 1) % len(catalog)
        self.current_pack_event = catalog[self.pack_event_index].copy()

    def get_pack_event_by_id(self, event_id):
        if not event_id:
            return None
        for event in self.pack_event_catalog():
            if event.get("id") == event_id:
                return event
        return None

    def event_pack_boost_cards(self):
        event = self.current_pack_event or {}
        boosted = []
        league = event.get("league")
        if league:
            boosted.extend(
                [
                    p for p in self.fantasy_pool
                    if p.get("league") == league and p.get("rarity") not in ("Icon", "GOAT")
                ]
            )
        signature_names = set(event.get("signature_names", []))
        if signature_names:
            boosted.extend(
                [
                    p for p in self.fantasy_pool
                    if p.get("name") in signature_names and p.get("rarity") not in ("Icon", "GOAT")
                ]
            )
        promo_type = event.get("promo")
        if promo_type:
            boosted.extend(
                [
                    p for p in self.fantasy_pool
                    if p.get("promo") == promo_type and p.get("rarity") not in ("Icon", "GOAT")
                ]
            )
        unique = []
        seen = set()
        for card in boosted:
            key = card.get("card_key")
            if key in seen:
                continue
            seen.add(key)
            unique.append(card)
        return unique

    def fantasy_competition_menu(self):
        theme_name = self.fantasy_competitions.get("theme", {}).get("name", self.current_theme)
        return [
            ("division", "Division Match", "Win for points and coin promotions"),
            ("ladder", "Weekly Ladder", "Six-match form race with rolling rewards"),
            ("online_tournament", "Online Tournament", "Automatic bracket runs with your live squad"),
            ("cup", "Knockout Cup", "Progress for an Elite Pack reward"),
            ("weekend", "Weekend Challenge", "String wins together for pack and coin rewards"),
            ("theme", theme_name, "Play themed matches for a featured player reward"),
            ("silver", "Silver Cup", "Win three matches for a Silver Pack and coins"),
            ("promo", "Promo Cup", "Clear wins boost promo packs"),
            ("signature", "Signature Showdown", "Earn a signature pick by winning twice"),
            ("draft", "Draft Run", "Build a temporary squad and chase a four-win reward run"),
            ("champions", "Champions Clash", "Straight knockout bracket for top rewards"),
        ]

    def reset_champions_bracket(self):
        champs = self.fantasy_competitions.get("champions")
        if not champs or not self.user_team:
            return
        opponents = [team for team in self.fantasy_opponents() if team != self.user_team]
        if len(opponents) < 15:
            return
        selected = random.sample(opponents, 15)
        teams = [self.user_team] + selected
        random.shuffle(teams)
        if self.user_team not in teams[:2]:
            user_idx = teams.index(self.user_team)
            teams[0], teams[user_idx] = teams[user_idx], teams[0]
        pairings = []
        for i in range(0, 16, 2):
            pairings.append((teams[i], teams[i + 1]))
        champs["round"] = 0
        champs["pairings"] = [pairings, [], [], []]
        champs["winners"] = [[], [], [], []]
        champs["champion"] = None

    def champions_current_pair(self):
        champs = self.fantasy_competitions.get("champions", {})
        round_idx = champs.get("round", 0)
        pairings = champs.get("pairings", [[], [], [], []])
        current_pairs = pairings[round_idx] if round_idx < len(pairings) else []
        for pair in current_pairs:
            if self.user_team in pair:
                return pair
        return None

    def grant_featured_player(self):
        candidates = [
            p for p in self.fantasy_pool
            if (p.get("rarity") in ("Diamond", "Mythic", "Legend") or p.get("promo") != "Base")
            and p.get("rarity") not in ("Icon", "GOAT")
            and p.get("promo") != "Signature"
        ]
        candidates = [p for p in candidates if not any(self.fantasy_card_key(r) == self.fantasy_card_key(p) for r in self.fantasy_roster)] or candidates
        if not candidates:
            return
        player = random.choice(candidates).copy()
        self.add_fantasy_player(player)
        self.last_pack = [player]
        self.walkout_timer = self.walkout_duration_for_player(player, 1)
        self.pack_summary_timer = 0.0
        self.pack_open_return_state = "LEAGUE"
        self.state = "PACK_OPENING"
        self.add_commentary(f"Featured reward: {player['name']}")

    def role_accepts_position(self, role, position):
        mapping = {
            "GK": {"GK"},
            "DF": {"RB", "LB", "CB"},
            "MF": {"CM", "DM", "AM", "LM", "RM"},
            "FW": {"ST", "CF", "LW", "RW"},
        }
        return position in mapping.get(role, set())

    def update_fantasy_chemistry(self):
        self.fantasy_chemistry_map = {}
        self.fantasy_chemistry_breakdown = {}
        self.fantasy_chemistry_total = 0
        self.fantasy_chemistry_links = []
        if self.game_mode != "FANTASY":
            return
        positions = self.get_home_positions()
        team_counts = {}
        league_counts = {}
        nation_counts = {}
        preferred_positions = []
        clubs = []
        leagues = []
        nations = []
        roles = []
        rarities = []
        for name, num, rating in self.user_starting:
            meta = self.get_fantasy_card_meta(name, num, rating) or self.get_fantasy_card_meta(name)
            club = meta.get("team", "") if meta else ""
            league = meta.get("league", get_team_league(club)) if meta else ""
            nation = meta.get("nation", get_player_nation(name, club)) if meta else get_player_nation(name, club)
            team_counts[club] = team_counts.get(club, 0) + 1
            league_counts[league] = league_counts.get(league, 0) + 1
            nation_counts[nation] = nation_counts.get(nation, 0) + 1
        for i, (name, num, rating) in enumerate(self.user_starting):
            meta = self.get_fantasy_card_meta(name, num, rating) or self.get_fantasy_card_meta(name)
            preferred = meta.get("position", "ST") if meta else "ST"
            club = meta.get("team", "") if meta else ""
            league = meta.get("league", get_team_league(club)) if meta else ""
            nation = meta.get("nation", get_player_nation(name, club)) if meta else get_player_nation(name, club)
            rarity = meta.get("rarity", "Bronze") if meta else "Bronze"
            role = positions[i][2] if i < len(positions) else "FW"
            chem = 0
            tags = []
            if self.role_accepts_position(role, preferred):
                chem += 1
                tags.append("POS")
            if team_counts.get(club, 0) >= 2:
                chem += 1
                tags.append("CLUB")
            elif nation_counts.get(nation, 0) >= 2 and nation not in ("World", "Icons", "Legends"):
                chem += 1
                tags.append("NATION")
            elif league_counts.get(league, 0) >= 2:
                chem += 1
                tags.append("LEAGUE")
            if rarity in ("Icon", "GOAT"):
                chem += 1
                tags.append("UNIQUE")
            elif any(r in ("Icon", "GOAT") for r in rarities):
                chem += 1
                tags.append("LINK+")
            if any(self.are_rival_teams(club, other_club) for other_club in clubs):
                chem -= 1
                tags.append("RIVAL")
            chem = min(3, chem)
            chem = max(0, chem)
            self.fantasy_chemistry_map[(name, num, rating)] = chem
            self.fantasy_chemistry_breakdown[(name, num, rating)] = tags
            self.fantasy_chemistry_total += chem
            preferred_positions.append(preferred)
            clubs.append(club)
            leagues.append(league)
            nations.append(nation)
            roles.append(role)
            rarities.append(rarity)
        seen_links = set()
        for i in range(len(self.user_starting)):
            if i >= len(positions):
                continue
            px, py, _ = positions[i]
            near = []
            for j in range(len(self.user_starting)):
                if i == j or j >= len(positions):
                    continue
                qx, qy, _ = positions[j]
                dist = math.hypot(px - qx, py - qy)
                if dist <= 255:
                    near.append((dist, j))
            near.sort(key=lambda item: item[0])
            for _, j in near[:3]:
                edge = tuple(sorted((i, j)))
                if edge in seen_links:
                    continue
                seen_links.add(edge)
                same_club = clubs[i] and clubs[i] == clubs[j]
                same_league = leagues[i] and leagues[i] == leagues[j]
                same_nation = nations[i] and nations[i] == nations[j] and nations[i] not in ("World", "Icons", "Legends")
                unique_anchor = rarities[i] in ("Icon", "GOAT") or rarities[j] in ("Icon", "GOAT")
                rivalry = self.are_rival_teams(clubs[i], clubs[j])
                both_fit = self.role_accepts_position(roles[i], preferred_positions[i]) and self.role_accepts_position(roles[j], preferred_positions[j])
                if rivalry:
                    strength = -1
                    label = "RIVAL"
                elif same_club:
                    strength = 3
                    label = "CLUB"
                elif same_nation:
                    strength = 2
                    label = "NATION"
                elif same_league:
                    strength = 2
                    label = "LEAGUE"
                elif unique_anchor:
                    strength = 2
                    label = "UNIQUE"
                elif both_fit:
                    strength = 1
                    label = "FIT"
                else:
                    strength = 0
                    label = "WEAK"
                self.fantasy_chemistry_links.append((edge[0], edge[1], strength, label))

    def chemistry_multiplier(self, chemistry):
        return 0.9 + chemistry * 0.05

    def are_rival_teams(self, team_a, team_b):
        if not team_a or not team_b or team_a == team_b:
            return False
        rivalries = {
            frozenset(("Liverpool", "Manchester City")),
            frozenset(("Liverpool", "Manchester United")),
            frozenset(("Arsenal", "Tottenham")),
            frozenset(("Chelsea", "Arsenal")),
            frozenset(("Real Madrid", "Barcelona")),
            frozenset(("Real Madrid", "Atletico Madrid")),
            frozenset(("Inter", "Milan")),
            frozenset(("Juventus", "Inter")),
            frozenset(("Bayern Munich", "Borussia Dortmund")),
            frozenset(("PSG", "Marseille")),
            frozenset(("Al Nassr", "Al Hilal")),
            frozenset(("Celtic", "Rangers")),
            frozenset(("Boca Juniors", "River Plate")),
        }
        return frozenset((team_a, team_b)) in rivalries

    def reward_summary(self, reward_type, reward_pack=None, reward_coins=0, pick_band=None, pick_count=0, featured=False):
        if reward_type == "pack":
            return self.reward_pack_label(reward_pack)
        if reward_type == "pick":
            return f"{pick_count}-Player Pick ({pick_band})"
        if reward_type == "hybrid":
            return f"{self.reward_pack_label(reward_pack)} + {reward_coins} coins"
        if reward_type == "bundle":
            return f"{self.reward_pack_label(reward_pack)} + {reward_coins} coins + {pick_count}-Player Pick"
        if featured:
            return "Featured player"
        return f"{reward_coins} coins"

    def resolve_reward_pack_id(self, reward_pack):
        if reward_pack == "event":
            event_pack = self.active_event_pack_entry()
            if event_pack:
                return event_pack["id"]
            return "promo"
        return reward_pack or "gold"

    def reward_pack_label(self, reward_pack):
        pack = self.get_pack_by_id(self.resolve_reward_pack_id(reward_pack))
        return pack.get("name", "Gold Pack")

    def grant_reward(self, reward_type, reward_pack=None, reward_coins=0, pick_band=None, pick_count=0, title="Reward", source="Reward"):
        if reward_type == "pack":
            self.store_pack(self.resolve_reward_pack_id(reward_pack), source=source)
        elif reward_type == "pick":
            self.open_player_pick(title, pick_band or "Elite", pick_count or 3)
        elif reward_type == "hybrid":
            self.fantasy_coins += reward_coins
            self.store_pack(self.resolve_reward_pack_id(reward_pack), source=source)
        elif reward_type == "bundle":
            self.fantasy_coins += reward_coins
            self.store_pack(self.resolve_reward_pack_id(reward_pack), source=source)
            self.open_player_pick(title, pick_band or "Elite", pick_count or 3)
        else:
            self.fantasy_coins += reward_coins

    def collection_filter_options(self):
        return ["All", "Favorites", "Promo", "Elite+", "Unique", "Evolved"]

    def collection_sort_options(self):
        return ["OVR", "Name", "Rarity"]

    def is_favorite_card(self, card):
        return card.get("card_key") in self.fantasy_favorites

    def toggle_favorite_card(self, card):
        key = card.get("card_key")
        if not key:
            return
        if key in self.fantasy_favorites:
            self.fantasy_favorites.remove(key)
        else:
            self.fantasy_favorites.append(key)

    def filtered_collection_cards(self):
        cards = self.fantasy_roster[:]
        filter_name = self.collection_filter_options()[self.fantasy_collection_filter]
        if filter_name == "Favorites":
            cards = [c for c in cards if self.is_favorite_card(c)]
        elif filter_name == "Promo":
            cards = [c for c in cards if c.get("promo", "Base") != "Base"]
        elif filter_name == "Elite+":
            cards = [c for c in cards if self.rarity_rank(c.get("rarity", "Bronze")) >= self.rarity_rank("Elite")]
        elif filter_name == "Unique":
            cards = [c for c in cards if c.get("rarity") in ("Icon", "GOAT")]
        elif filter_name == "Evolved":
            cards = [c for c in cards if c.get("evo_level", 0) > 0]
        sort_name = self.collection_sort_options()[self.fantasy_collection_sort]
        if sort_name == "Name":
            cards.sort(key=lambda c: (c.get("name", ""), -c.get("rating", 0)))
        elif sort_name == "Rarity":
            cards.sort(key=lambda c: (-self.rarity_rank(c.get("rarity", "Bronze")), -c.get("rating", 0), c.get("name", "")))
        else:
            cards.sort(key=lambda c: (-c.get("rating", 0), c.get("name", "")))
        return cards

    def fantasy_market_price(self, card):
        rarity = card.get("rarity", "Bronze")
        rarity_mult = {
            "Bronze": 1.0,
            "Silver": 1.05,
            "Gold": 1.15,
            "Platinum": 1.22,
            "Elite": 1.35,
            "Diamond": 1.5,
            "Mythic": 1.7,
            "Ascended": 1.9,
            "Legend": 2.2,
            "Transcendent": 2.7,
            "Celestial": 3.2,
            "Eternal": 3.9,
            "Immortal": 4.8,
            "Omega": 5.8,
        }.get(rarity, 1.0)
        promo_mult = 1.2 if card.get("promo", "Base") != "Base" else 1.0
        evo_mult = 1.0 + card.get("evo_level", 0) * 0.1
        return max(20, int(card.get("rating", 50) * rarity_mult * promo_mult * evo_mult))

    def apply_roster_to_team(self, roster):
        if not self.user_team:
            return
        used_numbers = set()
        lineup = []
        reserves = []
        for i, card in enumerate(roster):
            suggested = card.get("number", random.randint(1, 99))
            number = suggested
            while number in used_numbers:
                number += 1
            used_numbers.add(number)
            card["number"] = number
            entry = (card["name"], number, card["rating"])
            if i < 11:
                lineup.append(entry)
            else:
                reserves.append(entry)
        TEAM_LINEUPS[self.user_team] = lineup
        ROSTER_DATA[self.user_team] = reserves
        self.build_user_squad()
        self.update_fantasy_chemistry()

    def draft_round_floor(self, round_idx):
        floors = [75, 76, 78, 80, 82, 83, 84, 85, 86, 88, 89, 90, 91, 93, 94]
        return floors[min(round_idx, len(floors) - 1)]

    def draft_position_group(self, position):
        if position == "GK":
            return "GK"
        if position in ("RB", "LB", "CB"):
            return "DF"
        if position in ("CM", "DM", "AM", "LM", "RM"):
            return "MF"
        return "FW"

    def draft_target_counts(self):
        return {"GK": 2, "DF": 5, "MF": 5, "FW": 3}

    def draft_group_counts(self, roster=None):
        counts = {"GK": 0, "DF": 0, "MF": 0, "FW": 0}
        for card in (roster or self.fantasy_draft_roster):
            counts[self.draft_position_group(card.get("position", "ST"))] += 1
        return counts

    def draft_needed_groups(self):
        counts = self.draft_group_counts()
        targets = self.draft_target_counts()
        rounds_left = max(0, 15 - self.fantasy_draft_round)
        need_map = {}
        for group, target in targets.items():
            missing = max(0, target - counts.get(group, 0))
            urgent = rounds_left <= missing if missing > 0 else False
            need_map[group] = {"missing": missing, "urgent": urgent}
        return need_map

    def draft_priority_groups(self):
        need_map = self.draft_needed_groups()
        ordered = sorted(
            need_map.items(),
            key=lambda item: (
                0 if item[1]["urgent"] else 1,
                -item[1]["missing"],
                0 if item[0] == "GK" else 1,
            ),
        )
        return [group for group, meta in ordered if meta["missing"] > 0]

    def sort_draft_roster_for_lineup(self, roster):
        groups = {"GK": [], "DF": [], "MF": [], "FW": []}
        for card in roster:
            groups[self.draft_position_group(card.get("position", "ST"))].append(card.copy())
        for cards in groups.values():
            cards.sort(key=lambda c: (-c.get("rating", 0), c.get("name", "")))
        starters = []
        starters.extend(groups["GK"][:1])
        starters.extend(groups["DF"][:4])
        starters.extend(groups["MF"][:3])
        starters.extend(groups["FW"][:3])
        used = {card.get("card_key") for card in starters}
        leftovers = []
        for group in ("GK", "DF", "MF", "FW"):
            leftovers.extend([card for card in groups[group] if card.get("card_key") not in used])
        if len(starters) < 11:
            starters.extend(leftovers[: 11 - len(starters)])
            used = {card.get("card_key") for card in starters}
            leftovers = [card for card in leftovers if card.get("card_key") not in used]
        return starters + leftovers

    def build_draft_options(self):
        floor = self.draft_round_floor(self.fantasy_draft_round)
        pool = [
            p.copy() for p in self.fantasy_pool
            if p.get("rarity") not in ("Icon", "GOAT")
            and p.get("rating", 0) >= floor
            and not any(c.get("card_key") == p.get("card_key") for c in self.fantasy_draft_roster)
        ]
        if len(pool) < 3:
            pool = [
                p.copy() for p in self.fantasy_pool
                if p.get("rarity") not in ("Icon", "GOAT")
                and not any(c.get("card_key") == p.get("card_key") for c in self.fantasy_draft_roster)
            ]
        random.shuffle(pool)
        need_map = self.draft_needed_groups()
        priority_groups = self.draft_priority_groups()

        def candidate_score(card):
            group = self.draft_position_group(card.get("position", "ST"))
            need = need_map.get(group, {"missing": 0, "urgent": False})
            return (
                100 if need["urgent"] else 0,
                need["missing"] * 10,
                card.get("rating", 0),
                random.random(),
            )

        pool.sort(key=candidate_score, reverse=True)
        options = []
        seen = set()

        def take_for_group(group):
            for card in pool:
                key = card.get("card_key")
                if key in seen:
                    continue
                if self.draft_position_group(card.get("position", "ST")) != group:
                    continue
                seen.add(key)
                options.append(card)
                return True
            return False

        for group in priority_groups[:2]:
            take_for_group(group)

        for card in pool:
            key = card.get("card_key")
            if key in seen:
                continue
            seen.add(key)
            options.append(card)
            if len(options) >= 3:
                break
        self.fantasy_draft_options = options
        self.fantasy_draft_index = 0

    def open_fantasy_draft(self, reset=False):
        if self.fantasy_draft_active and not reset:
            self.add_commentary("Draft squad already locked")
            self.state = "LEAGUE"
            return
        if reset or not self.fantasy_draft_options and not self.fantasy_draft_roster:
            self.fantasy_draft_round = 0
            self.fantasy_draft_roster = []
            self.fantasy_draft_active = False
            self.fantasy_competitions.setdefault("draft", {}).update({"wins": 0, "losses": 0, "ready": False})
            self.build_draft_options()
        self.state = "FANTASY_DRAFT"

    def complete_draft_pick(self):
        if not self.fantasy_draft_options:
            return
        chosen = self.fantasy_draft_options[max(0, min(self.fantasy_draft_index, len(self.fantasy_draft_options) - 1))].copy()
        self.fantasy_draft_roster.append(chosen)
        self.fantasy_draft_round += 1
        if self.fantasy_draft_round >= 15:
            self.activate_draft_run()
            return
        self.build_draft_options()

    def activate_draft_run(self):
        if not self.user_team or len(self.fantasy_draft_roster) < 11:
            return
        self.fantasy_draft_saved_roster = [card.copy() for card in self.fantasy_roster]
        self.fantasy_draft_saved_lineup = TEAM_LINEUPS.get(self.user_team, [])[:]
        self.fantasy_draft_saved_reserves = ROSTER_DATA.get(self.user_team, [])[:]
        self.fantasy_draft_saved_player_index = self.user_player_index or 0
        self.fantasy_roster = self.sort_draft_roster_for_lineup(self.fantasy_draft_roster)
        self.apply_roster_to_team(self.fantasy_roster)
        self.fantasy_draft_active = True
        self.fantasy_draft_options = []
        self.fantasy_competitions.setdefault("draft", {}).update({"wins": 0, "losses": 0, "ready": True})
        self.fantasy_active_competition = "draft"
        self.fantasy_fixture_label = "Draft Run"
        self.state = "LEAGUE"
        self.add_commentary("Draft squad locked in")

    def finish_draft_run(self):
        if self.fantasy_draft_saved_roster:
            self.fantasy_roster = [card.copy() for card in self.fantasy_draft_saved_roster]
        if self.user_team:
            TEAM_LINEUPS[self.user_team] = self.fantasy_draft_saved_lineup[:]
            ROSTER_DATA[self.user_team] = self.fantasy_draft_saved_reserves[:]
        self.user_player_index = self.fantasy_draft_saved_player_index
        self.build_user_squad()
        self.update_fantasy_chemistry()
        self.fantasy_draft_active = False
        self.fantasy_draft_round = 0
        self.fantasy_draft_options = []
        self.fantasy_draft_roster = []
        self.fantasy_competitions.setdefault("draft", {}).update({"wins": 0, "losses": 0, "ready": False})
        if self.fantasy_active_competition == "draft":
            self.fantasy_active_competition = "division"
            self.fantasy_fixture_label = "Division Match"

    def pack_odds_lines(self, pack):
        band = pack.get("band", "mixed")
        if band == "GOAT":
            return ["GOAT: 100%", "Unique pool only"]
        if band == "Icon":
            return ["Icon: 100%", "Unowned icons only"]
        if band == "signature":
            return ["Signature: 100%", "Unique stars only"]
        if band == "promo":
            return ["Promo: 100%", "Signature 0.5% | TOTY 1.5%"]
        if pack.get("open_mode") == "pick":
            return [f"Player Pick: 1 of {pack.get('pick_count', 3)}", f"Pool: {pack.get('pick_band', band)}"]
        if band.startswith("league:"):
            league_name = band.split(":", 1)[1]
            return [league_name, "Signature: 1% | Promo: 1%"]
        if band in ("ultimate", "supreme"):
            return ["Signature: 1% | Promo: 1%", "Icon: 0.01% | GOAT: 0.001%"]
        if band in self.rarity_order():
            upgrades = self.pack_upgrade_targets(band)
            if upgrades:
                jump_text = " | ".join(f"{target} {int(chance * 1000) / 10:.1f}%" for target, chance in upgrades[:3])
            else:
                jump_text = "No higher-tier jumps"
            return [f"Signature: 1% | Promo: 1% | Icon: 0.01%", f"GOAT: 0.001% | {jump_text}"]
        return ["Mixed pool", "Signature: 1% | Promo: 1% | Icon: 0.01% | GOAT: 0.001%"]

    def pack_odds_breakdown(self, pack):
        band = pack.get("band", "mixed")
        if band == "GOAT":
            return ["GOAT cards only", "Unique pool", "No duplicates once owned"]
        if band == "Icon":
            return ["Icon cards only", "Unique pool", "No duplicates once owned"]
        if band == "signature":
            return ["Signature stars only", "Unique one-off cards", "Special walkout active"]
        if band == "promo":
            lines = ["Promo cards guaranteed", "Icon jackpot: 0.01%", "GOAT jackpot: 0.001%"]
            for promo_name, chance in self.promo_pack_weights():
                lines.append(f"{promo_name}: {chance:.1f}%")
            return lines
        if pack.get("open_mode") == "pick":
            return [
                f"Choose 1 of {pack.get('pick_count', 3)} cards",
                f"Pool floor: {pack.get('pick_band', band)}",
                "Unique cards excluded",
            ]
        if band.startswith("league:"):
            league_name = band.split(":", 1)[1]
            return [
                f"League pool: {league_name}",
                "Signature chance: 1%",
                "Promo chance: 1%",
                "Icon jackpot: 0.01%",
                "GOAT jackpot: 0.001%",
            ]
        lines = ["Signature chance: 1%", "Promo chance: 1%", "Icon jackpot: 0.01%", "GOAT jackpot: 0.001%"]
        if band in self.rarity_order():
            lines.append(f"Base floor: {band}")
            upgrades = self.pack_upgrade_targets(band)
            if upgrades:
                for target, chance in upgrades[:4]:
                    lines.append(f"{target} spike: {chance * 100:.1f}%")
            else:
                lines.append("No higher-tier spikes")
        elif band == "ultimate":
            lines.append("High-end mixed pool")
            lines.append("Elite+ weighted")
        elif band == "supreme":
            lines.append("Top-end mixed pool")
            lines.append("Mythic+ weighted")
        else:
            lines.append("Mixed fantasy pool")
        return lines

    def promo_pack_weights(self):
        return [
            ("Signature", 0.5),
            ("TOTY", 1.5),
            ("Phantom", 5.0),
            ("Dynasty", 6.0),
            ("RTTK", 7.0),
            ("Shapeshifter", 7.5),
            ("Future Star", 8.0),
            ("Centurions", 8.0),
            ("Neon", 9.0),
            ("Ice", 10.0),
            ("Thunder", 10.0),
            ("Hero", 10.0),
            ("Clutch", 8.5),
            ("TOTW", 9.0),
        ]

    def choose_weighted_promo(self):
        available = []
        for promo_name, chance in self.promo_pack_weights():
            if promo_name == "Signature":
                pool = self.cards_for_pack_band("signature")
            else:
                pool = [p for p in self.fantasy_pool if p.get("promo") == promo_name and p.get("rarity") not in ("Icon", "GOAT")]
            if pool:
                available.append((promo_name, chance))
        if not available:
            return None
        total = sum(chance for _, chance in available)
        roll = random.uniform(0, total)
        running = 0.0
        for promo_name, chance in available:
            running += chance
            if roll <= running:
                return promo_name
        return available[-1][0]

    def apply_pack_event_boost(self, candidates, band="mixed"):
        if not candidates:
            return candidates
        if band in ("GOAT", "Icon", "signature", "promo"):
            return candidates
        event_cards = self.event_pack_boost_cards()
        if not event_cards:
            return candidates
        candidate_keys = {card.get("card_key") for card in candidates}
        boosted = [card for card in event_cards if card.get("card_key") in candidate_keys]
        if not boosted:
            return candidates
        if random.random() < 0.42:
            return boosted
        return candidates + random.sample(boosted, min(len(boosted), max(1, len(candidates) // 2)))

    def refresh_fantasy_market(self):
        pool = [
            p.copy()
            for p in self.fantasy_pool
            if p.get("rarity") not in ("Icon", "GOAT")
            and p.get("promo") != "Signature"
            and not any(self.fantasy_card_key(r) == self.fantasy_card_key(p) for r in self.fantasy_roster)
        ]
        random.shuffle(pool)
        offers = []
        seen = set()
        for card in pool:
            key = card.get("card_key")
            if key in seen:
                continue
            seen.add(key)
            card["market_price"] = self.fantasy_market_price(card)
            offers.append(card)
            if len(offers) >= 10:
                break
        self.fantasy_market_offers = offers
        self.fantasy_market_index = 0

    def buy_market_card(self, idx):
        if idx < 0 or idx >= len(self.fantasy_market_offers):
            return
        card = self.fantasy_market_offers[idx]
        price = card.get("market_price", self.fantasy_market_price(card))
        if self.fantasy_coins < price:
            self.add_commentary("Not enough coins")
            return
        self.fantasy_coins -= price
        if self.add_fantasy_player(card):
            self.fantasy_market_offers.pop(idx)
            self.fantasy_market_index = max(0, min(self.fantasy_market_index, len(self.fantasy_market_offers) - 1))
            self.add_commentary(f"Market signing: {card['name']}")

    def open_player_pick(self, title, band="Elite", count=3, return_state=None):
        if band == "signature":
            pool = [p for p in self.cards_for_pack_band("signature") if p.get("promo") == "Signature"]
        else:
            pool = [
                p for p in self.cards_for_pack_band(band)
                if p.get("rarity") not in ("Icon", "GOAT")
                and p.get("promo") != "Signature"
            ]
        if not pool:
            if band == "signature":
                pool = [p for p in self.fantasy_pool if p.get("promo") == "Signature" and p.get("rarity") not in ("Icon", "GOAT")]
            else:
                pool = [
                    p for p in self.fantasy_pool
                    if p.get("rarity") not in ("Icon", "GOAT")
                    and p.get("promo") != "Signature"
                ]
        options = []
        tries = 0
        while len(options) < count and tries < 40 and pool:
            pick = random.choice(pool).copy()
            key = pick.get("card_key")
            if any(card.get("card_key") == key for card in options):
                tries += 1
                continue
            options.append(pick)
            tries += 1
        if not options:
            return
        self.fantasy_player_pick_title = title
        self.fantasy_player_pick_options = options
        self.fantasy_player_pick_index = 0
        self.player_pick_return_state = return_state or "LEAGUE"
        self.state = "FANTASY_PLAYER_PICK"

    def claim_player_pick(self):
        if not self.fantasy_player_pick_options:
            return
        idx = max(0, min(self.fantasy_player_pick_index, len(self.fantasy_player_pick_options) - 1))
        player = self.fantasy_player_pick_options[idx].copy()
        self.add_fantasy_player(player)
        self.last_pack = [player]
        self.walkout_timer = self.walkout_duration_for_player(player, 1)
        self.pack_summary_timer = 0.0
        self.pack_open_return_state = getattr(self, "player_pick_return_state", "LEAGUE")
        self.fantasy_player_pick_options = []
        self.state = "PACK_OPENING"
        self.add_commentary(f"Player Pick: {player['name']}")

    def init_fantasy_objectives(self):
        self.fantasy_objectives = {
            "daily": [
                {"label": "Play 1 match", "stat": "matches", "target": 1, "progress": 0, "reward": 30, "claimed": False},
                {"label": "Score 2 goals", "stat": "goals", "target": 2, "progress": 0, "reward": 35, "claimed": False},
            ],
            "weekly": [
                {"label": "Win 3 matches", "stat": "wins", "target": 3, "progress": 0, "reward": 80, "claimed": False},
                {"label": "Open 2 packs", "stat": "packs", "target": 2, "progress": 0, "reward": 60, "claimed": False},
                {"label": "Make 12 tackles", "stat": "tackles", "target": 12, "progress": 0, "reward": 75, "claimed": False},
            ],
            "milestones": [
                {"label": "Reach Division 7", "stat": "division_tier", "target": 7, "progress": 10, "reward": 100, "claimed": False, "reverse": True},
                {"label": "Earn 500 season XP", "stat": "season_xp", "target": 500, "progress": 0, "reward_type": "pick", "pick_count": 3, "pick_band": "Elite", "claimed": False},
                {"label": "Score 20 season goals", "stat": "season_goals", "target": 20, "progress": 0, "reward": 120, "claimed": False},
            ],
        }

    def fantasy_sbc_catalog(self):
        return [
            {"name": "Silver Upgrade", "requirements": [("Silver", 3)], "reward_type": "pack", "reward_pack": "gold"},
            {"name": "Elite Exchange", "requirements": [("Gold", 2), ("Platinum", 2)], "reward_type": "pack", "reward_pack": "elite"},
            {"name": "Promo Gamble", "requirements": [("Elite", 2), ("Diamond", 1)], "reward_type": "pack", "reward_pack": "promo"},
            {"name": "Coin Boost", "requirements": [("Silver", 2), ("Gold", 2)], "reward_type": "coins", "reward_coins": 90},
            {"name": "Diamond Climb", "requirements": [("Elite", 3), ("Diamond", 1)], "reward_type": "pack", "reward_pack": "diamond"},
            {"name": "Mythic Chase", "requirements": [("Diamond", 2), ("Elite", 2)], "reward_type": "pack", "reward_pack": "mythic"},
            {"name": "Legend Forge", "requirements": [("Mythic", 1), ("Diamond", 2), ("Elite", 2)], "reward_type": "pack", "reward_pack": "legend"},
            {"name": "Promo Furnace", "requirements": [("Gold", 3), ("Platinum", 2), ("Elite", 1)], "reward_type": "pack", "reward_pack": "promo"},
            {"name": "Coin Overflow", "requirements": [("Platinum", 3), ("Gold", 2)], "reward_type": "coins", "reward_coins": 180},
            {"name": "Captain's Pick", "requirements": [("Diamond", 1), ("Elite", 2)], "reward_type": "pick", "pick_count": 3, "pick_band": "Diamond"},
            {"name": "Ascended Rise", "requirements": [("Legend", 1), ("Ascended", 2), ("Mythic", 2)], "reward_type": "pack", "reward_pack": "transcendent"},
            {"name": "Celestial Lift", "requirements": [("Transcendent", 1), ("Legend", 2), ("Ascended", 2)], "reward_type": "pack", "reward_pack": "celestial"},
            {"name": "Eternal Engine", "requirements": [("Celestial", 1), ("Transcendent", 2), ("Legend", 2)], "reward_type": "pack", "reward_pack": "eternal"},
            {"name": "Immortal Core", "requirements": [("Eternal", 1), ("Celestial", 2), ("Transcendent", 2)], "reward_type": "pack", "reward_pack": "immortal"},
            {"name": "Omega Project", "requirements": [("Immortal", 1), ("Eternal", 2), ("Celestial", 2)], "reward_type": "pack", "reward_pack": "omega"},
            {"name": "Star Captain Pick", "requirements": [("Legend", 1), ("Transcendent", 1), ("Celestial", 1)], "reward_type": "pick", "pick_count": 3, "pick_band": "Eternal"},
            {"name": "Ultra Coin Crash", "requirements": [("Diamond", 2), ("Mythic", 2), ("Ascended", 1)], "reward_type": "coins", "reward_coins": 420},
            {"name": "League Drip", "requirements": [("Gold", 2), ("Silver", 2), ("Platinum", 1)], "reward_type": "pack", "reward_pack": "premier_league"},
            {"name": "Signature Spark", "requirements": [("Legend", 1), ("Transcendent", 1), ("Eternal", 1)], "reward_type": "pick", "pick_band": "signature", "pick_count": 2},
            {"name": "Event Starfire", "requirements": [("Diamond", 1), ("Elite", 2), ("Platinum", 2)], "reward_type": "pack", "reward_pack": "event"},
            {"name": "Coin Cascade", "requirements": [("Platinum", 2), ("Gold", 2), ("Silver", 2)], "reward_type": "coins", "reward_coins": 240},
        ]

    def infer_card_position(self, idx):
        pos_map = ["GK", "RB", "CB", "CB", "LB", "RM", "CM", "CM", "LM", "ST", "ST"]
        if idx < len(pos_map):
            return pos_map[idx]
        return random.choice(CARD_POSITIONS[1:])

    def card_rarity_from_rating(self, rating, promo="Base"):
        if rating >= 500:
            return "GOAT"
        if rating >= 130:
            return "Omega"
        if rating >= 120:
            return "Immortal"
        if rating >= 110:
            return "Eternal"
        if rating >= 105:
            return "Celestial"
        if rating >= 100:
            return "Transcendent"
        if promo == "TOTY":
            return "Ascended"
        if promo != "Base" and rating >= 94:
            return "Legend"
        if promo != "Base" or rating >= 91:
            return "Legend"
        if rating >= 89:
            return "Ascended"
        if rating >= 88:
            return "Mythic"
        if rating >= 86:
            return "Diamond"
        if rating >= 83:
            return "Elite"
        if rating >= 79:
            return "Platinum"
        if rating >= 73:
            return "Gold"
        if rating >= 67:
            return "Silver"
        return "Bronze"

    def rarity_order(self):
        return [
            "Bronze",
            "Silver",
            "Gold",
            "Platinum",
            "Elite",
            "Diamond",
            "Mythic",
            "Ascended",
            "Legend",
            "Transcendent",
            "Celestial",
            "Eternal",
            "Immortal",
            "Omega",
            "Icon",
            "GOAT",
        ]

    def rarity_rank(self, rarity):
        order = self.rarity_order()
        return order.index(rarity) if rarity in order else -1

    def rarity_rating_floor(self, rarity):
        floors = {
            "Bronze": 50,
            "Silver": 67,
            "Gold": 73,
            "Platinum": 79,
            "Elite": 83,
            "Diamond": 86,
            "Mythic": 88,
            "Ascended": 89,
            "Legend": 91,
            "Icon": 200,
            "GOAT": 500,
            "Transcendent": 100,
            "Celestial": 105,
            "Eternal": 110,
            "Immortal": 120,
            "Omega": 130,
        }
        return floors.get(rarity, 50)

    def rarity_rating_bonus(self, rarity, promo="Base"):
        bonus = {
            "Bronze": 0,
            "Silver": 1,
            "Gold": 2,
            "Platinum": 3,
            "Elite": 4,
            "Diamond": 6,
            "Mythic": 8,
            "Ascended": 9,
            "Legend": 10,
            "Icon": 12,
            "GOAT": 40,
            "Transcendent": 14,
            "Celestial": 16,
            "Eternal": 18,
            "Immortal": 22,
            "Omega": 26,
        }.get(rarity, 0)
        if promo == "TOTY":
            bonus += 2
        elif promo != "Base":
            bonus += 1
        return bonus

    def pack_upgrade_targets(self, band):
        upgrade_map = {
            "Bronze": [("Silver", 0.08), ("Gold", 0.02)],
            "Silver": [("Gold", 0.10), ("Platinum", 0.03)],
            "Gold": [("Platinum", 0.10), ("Elite", 0.035), ("Diamond", 0.01)],
            "Platinum": [("Elite", 0.12), ("Diamond", 0.04), ("Mythic", 0.012)],
            "Elite": [("Diamond", 0.12), ("Mythic", 0.04), ("Legend", 0.012)],
            "Diamond": [("Mythic", 0.10), ("Ascended", 0.025)],
            "Mythic": [("Ascended", 0.08), ("Legend", 0.02)],
            "Ascended": [("Legend", 0.08), ("Transcendent", 0.01)],
            "Legend": [("Transcendent", 0.06), ("Celestial", 0.01)],
            "Transcendent": [("Celestial", 0.05), ("Eternal", 0.01)],
            "Celestial": [("Eternal", 0.05), ("Immortal", 0.01)],
            "Eternal": [("Immortal", 0.05), ("Omega", 0.01)],
            "Immortal": [("Omega", 0.05)],
        }
        return upgrade_map.get(band, [])

    def goat_card_profile(self, player):
        if player.get("name") == "Lionel Messi":
            return {
                "base": (10, 10, 14),
                "accent": (244, 206, 84),
                "stripes": [(128, 210, 255), (248, 248, 252), (128, 210, 255), (255, 134, 196), (38, 74, 168), (164, 34, 44)],
                "flag": [(128, 210, 255), (248, 248, 252), (128, 210, 255)],
                "title": "GOAT",
            }
        return {
            "base": (10, 10, 14),
            "accent": (244, 206, 84),
            "stripes": [(188, 26, 42), (24, 138, 74), (255, 214, 84), (60, 102, 196), (244, 244, 244), (32, 32, 32)],
            "flag": [(24, 138, 74), (188, 26, 42)],
            "title": "GOAT",
        }

    def signature_card_profile(self, player):
        name = player.get("name", "")
        profiles = {
            "Kylian Mbappe": {"base": (16, 18, 24), "accent": (255, 214, 112), "glow": (120, 210, 255), "streaks": [(24, 76, 160), (255, 214, 112), (214, 42, 68)]},
            "Erling Haaland": {"base": (18, 20, 26), "accent": (255, 214, 112), "glow": (126, 218, 255), "streaks": [(76, 196, 255), (255, 214, 112), (236, 244, 255)]},
            "Jude Bellingham": {"base": (16, 18, 24), "accent": (255, 214, 112), "glow": (255, 196, 112), "streaks": [(252, 252, 252), (255, 214, 112), (102, 164, 255)]},
            "Vinicius Junior": {"base": (16, 18, 24), "accent": (255, 214, 112), "glow": (255, 138, 138), "streaks": [(36, 82, 188), (214, 42, 68), (255, 214, 112)]},
            "Neymar": {"base": (16, 18, 24), "accent": (255, 214, 112), "glow": (102, 214, 162), "streaks": [(242, 206, 88), (58, 124, 255), (78, 214, 154)]},
            "Mohamed Salah": {"base": (16, 18, 24), "accent": (255, 214, 112), "glow": (255, 102, 102), "streaks": [(192, 28, 44), (255, 214, 112), (242, 242, 242)]},
            "Harry Kane": {"base": (16, 18, 24), "accent": (255, 214, 112), "glow": (154, 180, 255), "streaks": [(242, 242, 242), (70, 88, 166), (255, 214, 112)]},
            "Jamal Musiala": {"base": (16, 18, 24), "accent": (255, 214, 112), "glow": (255, 102, 102), "streaks": [(214, 22, 42), (242, 242, 242), (255, 214, 112)]},
        }
        return profiles.get(name, {"base": (16, 18, 24), "accent": (255, 214, 112), "glow": (126, 214, 255), "streaks": [(86, 128, 224), (255, 214, 112), (242, 242, 242)]})

    def draw_flag_chip(self, x, y, w, h, stripes, border_color):
        chip = pygame.Rect(int(x), int(y), int(w), int(h))
        pygame.draw.rect(self.screen, (12, 14, 20), chip, 0, border_radius=7)
        total = max(1, len(stripes))
        for idx, color in enumerate(stripes):
            stripe_w = chip.w / total
            stripe_rect = pygame.Rect(int(chip.x + idx * stripe_w), chip.y + 2, int(math.ceil(stripe_w)), chip.h - 4)
            pygame.draw.rect(self.screen, color, stripe_rect)
        pygame.draw.rect(self.screen, border_color, chip, 2, border_radius=7)

    def card_theme_colors(self, player):
        promo = player.get("promo", "Base")
        rarity = player.get("rarity") or self.card_rarity_from_rating(player.get("rating", 70), promo)
        if rarity == "GOAT":
            profile = self.goat_card_profile(player)
            base, accent = profile["base"], profile["accent"]
        elif promo == "Signature":
            profile = self.signature_card_profile(player)
            base, accent = profile["base"], profile["accent"]
        elif promo == "TOTY":
            base, accent = (10, 28, 92), (244, 206, 84)
        elif promo == "TOTW":
            base, accent = (24, 24, 24), (235, 195, 70)
        elif promo == "Hero":
            base, accent = (118, 42, 24), (255, 178, 92)
        elif promo == "Future Star":
            base, accent = (49, 12, 96), (120, 220, 255)
        elif promo == "Clutch":
            base, accent = (90, 16, 22), (255, 110, 110)
        elif promo == "Ice":
            base, accent = (20, 92, 124), (178, 246, 255)
        elif promo == "Thunder":
            base, accent = (70, 42, 8), (255, 208, 68)
        elif promo == "Centurions":
            base, accent = (28, 78, 58), (178, 255, 166)
        elif promo == "Shapeshifter":
            base, accent = (14, 86, 72), (98, 255, 208)
        elif promo == "Phantom":
            base, accent = (34, 26, 78), (184, 144, 255)
        elif promo == "Neon":
            base, accent = (22, 22, 22), (78, 255, 120)
        elif promo == "RTTK":
            base, accent = (18, 42, 108), (80, 176, 255)
        elif promo == "Dynasty":
            base, accent = (88, 40, 18), (255, 170, 108)
        elif rarity == "Icon":
            base, accent = (244, 244, 240), (244, 206, 84)
        elif rarity == "Legend":
            base, accent = (86, 34, 10), (255, 154, 52)
        elif rarity == "Omega":
            base, accent = (98, 10, 18), (255, 84, 84)
        elif rarity == "Immortal":
            base, accent = (96, 10, 96), (255, 92, 214)
        elif rarity == "Eternal":
            base, accent = (6, 116, 72), (96, 255, 156)
        elif rarity == "Celestial":
            base, accent = (8, 88, 136), (102, 240, 255)
        elif rarity == "Transcendent":
            base, accent = (12, 50, 132), (86, 170, 255)
        elif rarity == "Ascended":
            base, accent = (108, 18, 76), (255, 86, 170)
        elif rarity == "Mythic":
            base, accent = (58, 18, 112), (192, 96, 255)
        elif rarity == "Diamond":
            base, accent = (10, 82, 120), (48, 228, 255)
        elif rarity == "Elite":
            base, accent = (16, 44, 118), (68, 132, 255)
        elif rarity == "Platinum":
            base, accent = (120, 130, 152), (216, 228, 244)
        elif rarity == "Gold":
            base, accent = (108, 82, 18), (245, 200, 68)
        elif rarity == "Silver":
            base, accent = (70, 82, 104), (172, 188, 212)
        else:
            base, accent = (98, 58, 24), (178, 116, 62)
        event_colors = player.get("event_evo_colors")
        if event_colors and len(event_colors) >= 2:
            base = self.blend_color(base, tuple(event_colors[0]), 0.62)
            accent = self.blend_color(accent, tuple(event_colors[1]), 0.86)
        evo_level = player.get("evo_level", 0)
        if evo_level > 0:
            evo_base = [
                ((20, 96, 78), (92, 255, 198)),
                ((18, 118, 92), (132, 255, 214)),
                ((12, 132, 108), (176, 255, 232)),
                ((18, 86, 132), (120, 228, 255)),
                ((74, 28, 128), (236, 152, 255)),
            ][min(4, evo_level - 1)]
            base = self.blend_color(base, evo_base[0], 0.58)
            accent = self.blend_color(accent, evo_base[1], 0.82)
        return base, accent

    def fantasy_card_key(self, player):
        return (
            player.get("name"),
            player.get("promo", "Base"),
            player.get("rating"),
            player.get("position", "ST"),
        )

    def open_pack_shop(self, return_state):
        self.pack_shop_return_state = return_state
        self.show_pack_shop = False
        self.state = "PACK_SHOP"

    def close_pack_shop(self):
        self.state = self.pack_shop_return_state or "LEAGUE"

    def open_my_packs(self, return_state):
        self.pack_shop_return_state = return_state
        self.my_packs_index = max(0, min(self.my_packs_index, max(0, len(self.my_packs) - 1)))
        self.state = "MY_PACKS"

    def open_pack_odds(self, pack_id, return_state):
        self.pack_detail_pack_id = pack_id
        self.pack_detail_return_state = return_state
        self.state = "PACK_ODDS"

    def open_fantasy_market(self):
        if not self.fantasy_market_offers:
            self.refresh_fantasy_market()
        self.fantasy_market_index = max(0, min(self.fantasy_market_index, max(0, len(self.fantasy_market_offers) - 1)))
        self.state = "FANTASY_MARKET"

    def store_pack(self, pack_id, source=""):
        pack = self.get_pack_by_id(pack_id)
        self.my_packs.append(pack["id"])
        self.my_packs_index = max(0, len(self.my_packs) - 1)
        label = pack["name"]
        if source:
            self.add_commentary(f"{label} added to My Packs")
        else:
            self.add_commentary(f"{label} stored in My Packs")

    def open_owned_pack(self):
        if not self.my_packs:
            self.add_commentary("No packs in My Packs")
            return
        idx = max(0, min(self.my_packs_index, len(self.my_packs) - 1))
        pack_id = self.my_packs.pop(idx)
        if self.my_packs:
            self.my_packs_index = min(idx, len(self.my_packs) - 1)
        else:
            self.my_packs_index = 0
        self.open_pack(pack_id, free=True)

    def get_fantasy_card_meta(self, name, number=None, rating=None):
        for card in self.fantasy_roster:
            if card.get("name") != name:
                continue
            if number is not None and card.get("number") != number:
                continue
            if rating is not None and card.get("rating") != rating:
                continue
            return card
        return None

    def generate_card_traits(self, position, rarity, promo="Base"):
        pools = {
            "GK": ["Press Resist", "Interceptor"],
            "RB": ["Interceptor", "Playmaker", "Press Resist"],
            "LB": ["Interceptor", "Playmaker", "Press Resist"],
            "CB": ["Interceptor", "Aerial", "Press Resist"],
            "CM": ["Playmaker", "Press Resist", "Interceptor"],
            "DM": ["Interceptor", "Press Resist", "Aerial"],
            "AM": ["Playmaker", "Finesse Shot", "Press Resist"],
            "LM": ["Playmaker", "Press Resist", "Finesse Shot"],
            "RM": ["Playmaker", "Press Resist", "Finesse Shot"],
            "LW": ["Finesse Shot", "Playmaker", "Press Resist"],
            "RW": ["Finesse Shot", "Playmaker", "Press Resist"],
            "ST": ["Finesse Shot", "Aerial", "Press Resist"],
            "CF": ["Finesse Shot", "Playmaker", "Aerial"],
        }
        choices = pools.get(position, ["Press Resist", "Playmaker"])
        count = 1
        if rarity in ("Diamond", "Mythic", "Legend", "Icon") or promo != "Base":
            count = 2
        return random.sample(choices, min(count, len(choices)))

    def card_has_trait(self, player, trait):
        if self.game_mode != "FANTASY" or not player:
            return False
        meta = self.get_fantasy_card_meta(player.name, player.number, player.rating)
        if not meta:
            meta = self.get_fantasy_card_meta(player.name)
        return bool(meta and trait in meta.get("traits", []))

    def make_fantasy_card(self, name, team, rating, number, idx=0):
        original_rating = rating
        promo = "Base"
        roll = random.random()
        if roll < 0.001:
            promo = "TOTY"
            rating = max(95, rating + random.randint(8, 12))
        elif roll < 0.005:
            promo = random.choice(PROMO_TYPES[2:])
            rating = rating + random.randint(4, 7)
        elif roll < 0.01:
            promo = "TOTW"
            rating = rating + random.randint(2, 4)
        position = self.infer_card_position(idx)
        rarity = self.card_rarity_from_rating(rating, promo)
        rating = rating + self.rarity_rating_bonus(rarity, promo)
        rarity = self.card_rarity_from_rating(rating, promo)
        traits = self.generate_card_traits(position, rarity, promo)
        card = {
            "name": name,
            "team": team,
            "league": get_team_league(team),
            "nation": get_player_nation(name, team),
            "rating": rating,
            "base_rating": original_rating,
            "price": max(5, int(rating * 0.6)),
            "number": number,
            "position": position,
            "rarity": rarity,
            "promo": promo,
            "evo_level": 0,
            "milestone_level": 0,
            "form_boost": 0,
            "pull_count": 1,
            "duplicate_protected": False,
            "traits": traits,
        }
        card["card_key"] = f"{name}|{promo}|{rating}|{position}"
        return card

    def play_walkout_sound(self, player):
        if not self.sound_enabled:
            return
        tier = player.get("rarity") or self.card_tier(player["rating"])[0]
        sound = self.walkout_sounds.get(tier)
        if sound:
            try:
                sound.play()
            except Exception:
                pass

    def walkout_duration_for_player(self, player, pack_size=1):
        duration = max(6.6, min(10.2, 4.6 + pack_size * 0.65))
        if not player:
            return duration
        rarity = player.get("rarity") or self.card_tier(player.get("rating", 70))[0]
        if player.get("promo") == "Signature":
            return duration + 2.8
        if rarity == "GOAT":
            return duration + 5.2
        if rarity == "Icon":
            return duration + 3.6
        if rarity in ("Omega", "Immortal", "Eternal"):
            return duration + 2.4
        if rarity in ("Celestial", "Transcendent", "Legend"):
            return duration + 1.4
        return duration

    def apply_fantasy_form_boosts(self):
        if self.game_mode != "FANTASY":
            return
        wins = self.fantasy_competitions.get("division", {}).get("wins", 0)
        for card in self.fantasy_roster:
            boost = 0
            if wins >= 10:
                boost = 2
            elif wins >= 4:
                boost = 1
            card["form_boost"] = boost

    def apply_fantasy_progression(self):
        if self.game_mode != "FANTASY":
            return
        upgraded = []
        for card in self.fantasy_roster:
            name = card["name"]
            goals = self.get_player_stat(name, "goals")
            assists = self.get_player_stat(name, "assists")
            tackles = self.get_player_stat(name, "tackles")
            clean = self.get_player_stat(name, "clean_sheets")
            milestone = goals // 5 + assists // 5 + tackles // 8 + clean // 3
            if milestone > card.get("milestone_level", 0):
                delta = min(2, milestone - card.get("milestone_level", 0))
                card["milestone_level"] = milestone
                card["evo_level"] = card.get("evo_level", 0) + delta
                card["rating"] = card["rating"] + delta
                upgraded.append(card["name"])
                self.update_team_lineup_rating(self.user_team, card["name"], card.get("number", 0), card["rating"])
        if upgraded:
            self.build_user_squad()
            self.add_commentary("Evolutions: " + ", ".join(upgraded[:4]))

    def record_fantasy_competition_result(self, competition, won, drew, user_goals, opp_goals):
        if not competition:
            return
        competition["played"] = competition.get("played", 0) + 1
        competition["goals_for"] = competition.get("goals_for", 0) + user_goals
        competition["goals_against"] = competition.get("goals_against", 0) + opp_goals
        if won:
            competition["wins"] = competition.get("wins", 0) + 1
        elif drew:
            competition["draws"] = competition.get("draws", 0) + 1
        else:
            competition["losses"] = competition.get("losses", 0) + 1

    def update_fantasy_competitions(self, won, drew, competition_key=None, user_goals=0, opp_goals=0):
        if self.game_mode != "FANTASY":
            return
        comps = self.fantasy_competitions
        if competition_key == "division":
            div = comps.get("division", {})
            self.record_fantasy_competition_result(div, won, drew, user_goals, opp_goals)
            if won:
                div["points"] += 3
            elif drew:
                div["points"] += 1
            if div["points"] >= 12:
                div["points"] -= 12
                div["tier"] = max(1, div["tier"] - 1)
                self.fantasy_coins += div.get("reward", 120)
                self.add_commentary(f"Division promotion. Tier {div['tier']}")
            self.update_objective_progress("division_tier", absolute=div.get("tier", 10))
        elif competition_key == "ladder":
            ladder = comps.get("ladder", {})
            self.record_fantasy_competition_result(ladder, won, drew, user_goals, opp_goals)
            if won:
                ladder["points"] = ladder.get("points", 0) + 3
                ladder["streak"] = ladder.get("streak", 0) + 1
            elif drew:
                ladder["points"] = ladder.get("points", 0) + 1
                ladder["streak"] = 0
            else:
                ladder["streak"] = 0
            if ladder.get("played", 0) >= ladder.get("target", 6):
                if ladder.get("points", 0) >= 10:
                    self.grant_reward(
                        ladder.get("reward_type", "hybrid"),
                        reward_pack=ladder.get("reward_pack", "elite"),
                        reward_coins=ladder.get("reward_coins", 160),
                        title=f"Weekly Ladder {ladder.get('week', 1)}",
                        source="Weekly Ladder",
                    )
                    self.add_commentary(f"Weekly Ladder {ladder.get('week', 1)} cleared")
                else:
                    fallback = 40 + ladder.get("points", 0) * 8
                    self.fantasy_coins += fallback
                    self.add_commentary(f"Weekly Ladder paid {fallback} fallback coins")
                ladder["week"] = ladder.get("week", 1) + 1
                ladder["points"] = 0
                ladder["played"] = 0
                ladder["wins"] = 0
                ladder["draws"] = 0
                ladder["losses"] = 0
                ladder["goals_for"] = 0
                ladder["goals_against"] = 0
                ladder["streak"] = 0
        elif competition_key == "cup":
            cup = comps.get("cup", {})
            self.record_fantasy_competition_result(cup, won, drew, user_goals, opp_goals)
            if cup.get("alive", True):
                if won:
                    cup["round"] += 1
                    if cup["round"] > 4:
                        self.store_pack(cup.get("reward_pack", "elite"), source="Knockout Cup")
                        cup["round"] = 1
                        cup["wins"] = 0
                        self.add_commentary("Knockout Cup reward claimed")
                else:
                    cup["alive"] = False
            else:
                cup["alive"] = True
                cup["round"] = 1
        elif competition_key == "weekend":
            weekend = comps.get("weekend", {})
            if weekend.get("active", True):
                self.record_fantasy_competition_result(weekend, won, drew, user_goals, opp_goals)
                if weekend["played"] >= weekend.get("target", 5):
                    if weekend["wins"] >= 3:
                        self.fantasy_coins += weekend.get("reward_coins", 80)
                        self.store_pack(weekend.get("reward_pack", "gold"), source="Weekend Challenge")
                        self.add_commentary("Weekend challenge rewards claimed")
                    weekend["played"] = 0
                    weekend["wins"] = 0
                    weekend["active"] = True
        elif competition_key == "theme":
            theme = comps.get("theme", {})
            self.record_fantasy_competition_result(theme, won, drew, user_goals, opp_goals)
            if won:
                theme["progress"] += 1
            if theme.get("progress", 0) >= theme.get("target", 3):
                self.grant_reward("pick", pick_band=theme.get("pick_band", "Mythic"), pick_count=theme.get("pick_count", 3), title=theme.get("name", "Theme Reward"), source="Theme Event")
                self.current_theme = random.choice(["Wing Wizard", "Midfield Engine", "Low Block", "Quick Break", "Target Man"])
                theme["name"] = self.current_theme
                theme["progress"] = 0
                self.add_commentary(f"Theme event cleared: {theme['name']}")
        elif competition_key == "silver":
            silver = comps.get("silver", {})
            self.record_fantasy_competition_result(silver, won, drew, user_goals, opp_goals)
            if won:
                if silver["wins"] >= silver.get("target", 3):
                    self.store_pack(silver.get("reward_pack", "silver"), source="Silver Cup")
                    self.fantasy_coins += 70
                    silver["wins"] = 0
                    self.add_commentary("Silver Cup rewards claimed")
            else:
                silver["wins"] = 0
                silver["alive"] = False
            silver["alive"] = silver.get("wins", 0) > 0 or silver.get("alive", True)
        elif competition_key == "promo":
            promo = comps.get("promo", {})
            self.record_fantasy_competition_result(promo, won, drew, user_goals, opp_goals)
            if won:
                if promo["wins"] >= promo.get("target", 3):
                    self.store_pack(self.resolve_reward_pack_id(promo.get("reward_pack", "event")), source="Promo Cup")
                    self.fantasy_coins += 90
                    promo["wins"] = 0
                    self.add_commentary("Promo Cup rewards claimed")
            else:
                promo["wins"] = 0
                promo["alive"] = False
            promo["alive"] = promo.get("wins", 0) > 0 or promo.get("alive", True)
        elif competition_key == "signature":
            signature = comps.get("signature", {})
            self.record_fantasy_competition_result(signature, won, drew, user_goals, opp_goals)
            if won:
                if signature["wins"] >= signature.get("target", 2):
                    self.grant_reward("pick", pick_band="signature", pick_count=2, title="Signature Showdown Reward", source="Signature Showdown")
                    signature["wins"] = 0
                    signature["alive"] = False
                    self.add_commentary("Signature Showdown cleared")
            else:
                signature["wins"] = 0
                signature["alive"] = False
        elif competition_key == "draft":
            draft = comps.get("draft", {})
            self.record_fantasy_competition_result(draft, won, drew, user_goals, opp_goals)
            if draft.get("wins", 0) >= draft.get("target", 4):
                self.grant_reward(
                    draft.get("reward_type", "bundle"),
                    reward_pack=draft.get("reward_pack", "omega"),
                    reward_coins=draft.get("reward_coins", 260),
                    pick_band=draft.get("pick_band", "Legend"),
                    pick_count=draft.get("pick_count", 3),
                    title="Draft Run Reward",
                    source="Draft Run",
                )
                self.add_commentary("Draft run cleared")
                self.finish_draft_run()
            elif draft.get("losses", 0) >= draft.get("max_losses", 2):
                self.add_commentary("Draft run ended")
                self.finish_draft_run()
        elif competition_key == "champions":
            champs = comps.get("champions", {})
            self.record_fantasy_competition_result(champs, won, drew, user_goals, opp_goals)
            round_idx = champs.get("round", 0)
            pairings = champs.get("pairings", [[], [], [], []])
            winners = champs.get("winners", [[], [], [], []])
            current_pairs = pairings[round_idx] if round_idx < len(pairings) else []
            if not current_pairs:
                self.reset_champions_bracket()
                champs = comps.get("champions", champs)
                pairings = champs.get("pairings", [[], [], [], []])
                winners = champs.get("winners", [[], [], [], []])
                current_pairs = pairings[round_idx] if round_idx < len(pairings) else []
            round_winners = []
            user_won_round = False
            for pair in current_pairs:
                home, away = pair
                if self.user_team in pair:
                    if drew:
                        winner = random.choice([self.user_team, away if home == self.user_team else home])
                    else:
                        winner = self.user_team if won else (away if home == self.user_team else home)
                    user_won_round = winner == self.user_team
                else:
                    winner = random.choice(pair)
                round_winners.append(winner)
            if round_idx < len(winners):
                winners[round_idx] = round_winners
            if not user_won_round:
                self.add_commentary("Champions Clash run ended")
                self.reset_champions_bracket()
            else:
                if round_idx >= 3:
                    champs["champion"] = self.user_team
                    self.grant_reward(
                        champs.get("reward_type", "hybrid"),
                        reward_pack=champs.get("reward_pack", "transcendent"),
                        reward_coins=champs.get("reward_coins", 240),
                        title="Champions Clash",
                        source="Champions Clash",
                    )
                    self.add_commentary("Champions Clash won")
                    self.reset_champions_bracket()
                else:
                    next_pairs = []
                    for i in range(0, len(round_winners), 2):
                        next_pairs.append((round_winners[i], round_winners[i + 1]))
                    pairings[round_idx + 1] = next_pairs
                    champs["round"] = round_idx + 1
                    self.add_commentary(f"Champions Clash advanced to {champs.get('bracket', ['Quarter Final'])[champs['round']]}")
        self.apply_fantasy_form_boosts()

    def build_event_pack_entry(self, event):
        if not event or not event.get("id") or not event.get("featured_pack"):
            return None
        return {
            "id": f"event_{event['id']}",
            "name": f"{event['name']} Pack",
            "cost": event.get("pack_cost", 380),
            "count": event.get("pack_count", 3),
            "band": event.get("featured_pack", "promo"),
            "guaranteed": event.get("guaranteed", 90),
            "event_id": event["id"],
            "pack_evo_tokens": event.get("evo_tokens", 1),
        }

    def active_event_pack_entry(self):
        return self.build_event_pack_entry(self.current_pack_event or {})

    def average_fantasy_rating(self):
        if not self.fantasy_roster:
            return 65
        sample = self.fantasy_roster[:11] if len(self.fantasy_roster) >= 11 else self.fantasy_roster
        total = sum(card.get("rating", 65) for card in sample)
        return int(total / max(1, len(sample)))

    def fantasy_competition_progress_text(self, active_key, current):
        if active_key == "division":
            return f"Tier {current.get('tier', 10)} | {current.get('points', 0)}/12 pts | Reward {current.get('reward', 120)} coins"
        if active_key == "ladder":
            return f"Week {current.get('week', 1)} | {current.get('points', 0)} pts in {current.get('played', 0)}/{current.get('target', 6)} matches | Streak {current.get('streak', 0)}"
        if active_key == "cup":
            return f"Round {current.get('round', 1)} | {'Alive' if current.get('alive', True) else 'Reset next match'} | Reward {self.reward_pack_label(current.get('reward_pack', 'elite'))}"
        if active_key == "weekend":
            return f"{current.get('wins', 0)}/{current.get('target', 5)} wins in {current.get('played', 0)} matches | GF {current.get('goals_for', 0)}"
        if active_key == "draft":
            return f"{current.get('wins', 0)}/{current.get('target', 4)} wins | {current.get('losses', 0)}/{current.get('max_losses', 2)} losses | GF {current.get('goals_for', 0)}"
        if active_key == "champions":
            stages = current.get("bracket", ["Round of 16", "Quarter Final", "Semi Final", "Final", "Champions"])
            return f"{stages[min(current.get('round', 0), len(stages) - 1)]} | {current.get('wins', 0)} wins | GF {current.get('goals_for', 0)}"
        if active_key == "theme":
            return f"{current.get('progress', 0)}/{current.get('target', 3)} wins | GF {current.get('goals_for', 0)} | Reward Player Pick"
        if active_key in ("silver", "promo", "signature"):
            reward_text = "Reward Player Pick" if active_key == "signature" else f"Reward {self.reward_pack_label(current.get('reward_pack', 'gold'))}"
            return f"{current.get('wins', 0)}/{current.get('target', 3 if active_key != 'signature' else 2)} wins | GF {current.get('goals_for', 0)} | {reward_text}"
        return f"{current.get('wins', 0)} wins | GF {current.get('goals_for', 0)}"

    def card_tier(self, rating):
        if rating >= 500:
            return "GOAT", (255, 220, 120)
        if rating >= 130:
            return "Omega", (255, 84, 84)
        if rating >= 120:
            return "Immortal", (255, 92, 214)
        if rating >= 110:
            return "Eternal", (96, 255, 156)
        if rating >= 105:
            return "Celestial", (102, 240, 255)
        if rating >= 100:
            return "Transcendent", (86, 170, 255)
        if rating >= 94:
            return "Legend", (255, 154, 52)
        if rating >= 89:
            return "Ascended", (255, 86, 170)
        if rating >= 88:
            return "Mythic", (192, 96, 255)
        if rating >= 86:
            return "Diamond", (48, 228, 255)
        if rating >= 83:
            return "Elite", (68, 132, 255)
        if rating >= 79:
            return "Platinum", (216, 228, 244)
        if rating >= 73:
            return "Gold", (245, 200, 68)
        if rating >= 67:
            return "Silver", (172, 188, 212)
        return "Bronze", (178, 116, 62)

    def fantasy_pack_catalog(self):
        base = [
            {"id": "bronze", "name": "Bronze Pack", "cost": 25, "count": 3, "band": "Bronze", "guaranteed": 62},
            {"id": "silver", "name": "Silver Pack", "cost": 55, "count": 3, "band": "Silver", "guaranteed": 70},
            {"id": "gold", "name": "Gold Pack", "cost": 100, "count": 3, "band": "Gold", "guaranteed": 76},
            {"id": "platinum", "name": "Platinum Pack", "cost": 150, "count": 3, "band": "Platinum", "guaranteed": 81},
            {"id": "elite", "name": "Elite Pack", "cost": 220, "count": 3, "band": "Elite", "guaranteed": 84},
            {"id": "elite_pick", "name": "Elite Pick Pack", "cost": 260, "count": 1, "band": "Elite", "guaranteed": 84, "open_mode": "pick", "pick_count": 3, "pick_band": "Elite"},
            {"id": "diamond", "name": "Diamond Pack", "cost": 290, "count": 3, "band": "Diamond", "guaranteed": 87},
            {"id": "mythic", "name": "Mythic Pack", "cost": 360, "count": 3, "band": "Mythic", "guaranteed": 89},
            {"id": "ascended", "name": "Ascended Pack", "cost": 410, "count": 3, "band": "Ascended", "guaranteed": 90},
            {"id": "legend", "name": "Legend Pack", "cost": 460, "count": 3, "band": "Legend", "guaranteed": 92},
            {"id": "legend_pick", "name": "Legend Pick Pack", "cost": 540, "count": 1, "band": "Legend", "guaranteed": 92, "open_mode": "pick", "pick_count": 3, "pick_band": "Legend"},
            {"id": "transcendent", "name": "Transcendent Pack", "cost": 720, "count": 3, "band": "Transcendent", "guaranteed": 100},
            {"id": "celestial", "name": "Celestial Pack", "cost": 880, "count": 3, "band": "Celestial", "guaranteed": 105},
            {"id": "eternal", "name": "Eternal Pack", "cost": 1050, "count": 3, "band": "Eternal", "guaranteed": 110},
            {"id": "immortal", "name": "Immortal Pack", "cost": 1250, "count": 3, "band": "Immortal", "guaranteed": 120},
            {"id": "omega", "name": "Omega Pack", "cost": 1500, "count": 3, "band": "Omega", "guaranteed": 130},
            {"id": "goat", "name": "GOAT Pack", "cost": 1000, "count": 1, "band": "GOAT", "guaranteed": 500},
            {"id": "icon", "name": "Icon Pack", "cost": 3000, "count": 1, "band": "Icon", "guaranteed": 200},
            {"id": "signature", "name": "Signature Pack", "cost": 1800, "count": 1, "band": "signature", "guaranteed": 97},
            {"id": "promo", "name": "Promo Pack", "cost": 300, "count": 3, "band": "promo", "guaranteed": 90},
            {"id": "ultimate", "name": "Ultimate Pack", "cost": 420, "count": 5, "band": "ultimate", "guaranteed": 92},
            {"id": "supreme", "name": "Supreme Pack", "cost": 650, "count": 5, "band": "supreme", "guaranteed": 94},
            {"id": "ultimate_pick", "name": "Ultimate 5 Pick", "cost": 760, "count": 1, "band": "supreme", "guaranteed": 94, "open_mode": "pick", "pick_count": 5, "pick_band": "supreme"},
            {"id": "premier_league", "name": "Premier League Pack", "cost": 210, "count": 3, "band": "league:Premier League", "guaranteed": 80},
            {"id": "la_liga", "name": "La Liga Pack", "cost": 210, "count": 3, "band": "league:La Liga", "guaranteed": 80},
            {"id": "bundesliga", "name": "Bundesliga Pack", "cost": 210, "count": 3, "band": "league:Bundesliga", "guaranteed": 80},
            {"id": "serie_a", "name": "Serie A Pack", "cost": 210, "count": 3, "band": "league:Serie A", "guaranteed": 80},
            {"id": "ligue_1", "name": "Ligue 1 Pack", "cost": 210, "count": 3, "band": "league:Ligue 1", "guaranteed": 80},
            {"id": "saudi", "name": "Saudi League Pack", "cost": 190, "count": 3, "band": "league:Saudi Pro League", "guaranteed": 82},
        ]
        event_pack = self.active_event_pack_entry()
        if event_pack:
            return [event_pack] + base
        return base

    def get_pack_by_id(self, pack_id):
        event_pack = self.active_event_pack_entry()
        if event_pack and pack_id == event_pack["id"]:
            return event_pack
        if pack_id.startswith("event_"):
            event = self.get_pack_event_by_id(pack_id.split("event_", 1)[1])
            event_pack = self.build_event_pack_entry(event)
            if event_pack:
                return event_pack
        for pack in self.fantasy_pack_catalog():
            if pack["id"] == pack_id:
                return pack
        return self.fantasy_pack_catalog()[0]

    def add_fantasy_player(self, player):
        if player.get("rarity") == "GOAT" and any(p.get("name") == player.get("name") and p.get("rarity") == "GOAT" for p in self.fantasy_roster):
            self.add_commentary(f"GOAT already owned: {player['name']}")
            return False
        if player.get("rarity") == "Icon" and any(p.get("name") == player.get("name") and p.get("rarity") == "Icon" for p in self.fantasy_roster):
            self.add_commentary(f"Icon already owned: {player['name']}")
            return False
        if player.get("promo") == "Signature" and any(p.get("name") == player.get("name") and p.get("promo") == "Signature" for p in self.fantasy_roster):
            self.add_commentary(f"Signature already owned: {player['name']}")
            return False
        if any(self.fantasy_card_key(p) == self.fantasy_card_key(player) for p in self.fantasy_roster):
            duplicate_reward = max(8, player["rating"] // 4)
            self.fantasy_coins += duplicate_reward
            self.add_commentary(f"Duplicate {player['promo']} {player['name']} converted to {duplicate_reward} coins")
            return False
        self.fantasy_roster.append(player.copy())
        if self.user_team and self.game_mode == "FANTASY":
            assigned_number = self.assign_unique_number(self.user_team, player.get("number", random.randint(1, 99)))
            player_tuple = (player["name"], assigned_number, player["rating"])
            if len(TEAM_LINEUPS.setdefault(self.user_team, [])) < 11:
                TEAM_LINEUPS[self.user_team].append(player_tuple)
            else:
                ROSTER_DATA.setdefault(self.user_team, []).append(player_tuple)
            self.build_user_squad()
        return True

    def add_fantasy_xp(self, amount):
        self.fantasy_season_xp += amount
        self.update_objective_progress("season_xp", amount)
        self.update_season_track_rewards()

    def update_season_track_rewards(self):
        while self.fantasy_season_claimed * 100 < self.fantasy_season_xp:
            self.fantasy_season_claimed += 1
            if self.fantasy_season_claimed % 3 == 0:
                self.open_pack("gold", free=True, grant_xp=False)
                self.add_commentary(f"Season track tier {self.fantasy_season_claimed}: Gold Pack")
            else:
                reward = 40 + self.fantasy_season_claimed * 10
                self.fantasy_coins += reward
                self.add_commentary(f"Season track tier {self.fantasy_season_claimed}: {reward} coins")

    def update_objective_progress(self, stat, amount=1, absolute=None):
        if self.game_mode != "FANTASY":
            return
        for group in self.fantasy_objectives.values():
            for objective in group:
                if objective.get("stat") != stat:
                    continue
                if absolute is not None:
                    objective["progress"] = absolute
                else:
                    objective["progress"] = objective.get("progress", 0) + amount

    def claim_objective(self, section, idx):
        group = self.fantasy_objectives.get(section, [])
        if idx < 0 or idx >= len(group):
            return
        objective = group[idx]
        progress = objective.get("progress", 0)
        target = objective.get("target", 0)
        if objective.get("reverse"):
            complete = progress <= target
        else:
            complete = progress >= target
        if objective.get("claimed") or not complete:
            return
        objective["claimed"] = True
        reward_type = objective.get("reward_type", "coins")
        if reward_type == "pack":
            pack_id = objective.get("pack_id", "gold")
            self.store_pack(pack_id, source="Objective")
        elif reward_type == "pick":
            self.open_player_pick(objective["label"], objective.get("pick_band", "Elite"), objective.get("pick_count", 3))
        else:
            self.fantasy_coins += objective.get("reward", 0)
        self.add_fantasy_xp(40)
        self.add_commentary(f"Objective claimed: {objective['label']}")

    def flat_objectives(self):
        flat = []
        for section in ("daily", "weekly", "milestones"):
            for idx, _ in enumerate(self.fantasy_objectives.get(section, [])):
                flat.append((section, idx))
        return flat

    def available_sbc_cards(self):
        active_names = {name for name, _, _ in self.user_starting}
        return [
            card for card in self.fantasy_roster
            if card.get("name") not in active_names and card.get("rarity") not in ("Icon", "GOAT") and card.get("promo") != "Signature"
        ]

    def can_complete_sbc(self, sbc):
        pool = self.available_sbc_cards()
        for rarity, needed in sbc.get("requirements", []):
            count = len([card for card in pool if card.get("rarity") == rarity])
            if count < needed:
                return False
        return True

    def complete_sbc(self, idx):
        catalog = self.fantasy_sbc_catalog()
        if idx < 0 or idx >= len(catalog):
            return
        sbc = catalog[idx]
        if not self.can_complete_sbc(sbc):
            self.add_commentary("Not enough spare cards for this SBC")
            return
        pool = self.available_sbc_cards()
        consumed_keys = []
        for rarity, needed in sbc.get("requirements", []):
            matches = [card for card in pool if card.get("rarity") == rarity]
            matches.sort(key=lambda card: (card.get("rating", 0), card.get("name", "")))
            chosen = matches[:needed]
            consumed_keys.extend(card.get("card_key") for card in chosen)
            pool = [card for card in pool if card.get("card_key") not in consumed_keys]
        self.fantasy_roster = [card for card in self.fantasy_roster if card.get("card_key") not in consumed_keys]
        self.build_user_squad()
        if sbc.get("reward_type") == "pack":
            self.store_pack(self.resolve_reward_pack_id(sbc.get("reward_pack", "gold")), source="SBC")
        else:
            self.fantasy_coins += sbc.get("reward_coins", 0)
        self.add_fantasy_xp(60)
        self.add_commentary(f"SBC completed: {sbc['name']}")

    def entry_card_key(self, entry):
        if not entry:
            return None
        name, num, rating = entry
        meta = self.get_fantasy_card_meta(name, num, rating) or self.get_fantasy_card_meta(name)
        if meta:
            return meta.get("card_key")
        return f"{name}|{num}|{rating}"

    def start_sbc_build(self, idx):
        catalog = self.fantasy_sbc_catalog()
        if idx < 0 or idx >= len(catalog):
            return
        self.fantasy_sbc_active = idx
        slot_count = sum(count for _, count in catalog[idx].get("requirements", []))
        self.fantasy_sbc_slots = [None] * max(1, slot_count)
        self.fantasy_sbc_col = 0
        self.fantasy_sbc_idx = 0
        self.state = "FANTASY_SBC_BUILD"

    def sbc_assigned_keys(self):
        return {self.entry_card_key(entry) for entry in self.fantasy_sbc_slots if entry}

    def get_sbc_source_list(self, col):
        assigned = self.sbc_assigned_keys()
        source = self.user_bench if col == 1 else self.user_reserves
        return [entry for entry in source if self.entry_card_key(entry) not in assigned]

    def add_card_to_sbc(self, entry):
        if not entry:
            return
        if self.entry_card_key(entry) in self.sbc_assigned_keys():
            return
        for i, slot in enumerate(self.fantasy_sbc_slots):
            if slot is None:
                self.fantasy_sbc_slots[i] = entry
                return

    def remove_card_from_sbc(self, idx):
        if 0 <= idx < len(self.fantasy_sbc_slots):
            self.fantasy_sbc_slots[idx] = None

    def sbc_build_requirements_met(self):
        if self.fantasy_sbc_active is None:
            return False
        sbc = self.fantasy_sbc_catalog()[self.fantasy_sbc_active]
        assigned_cards = []
        for entry in self.fantasy_sbc_slots:
            if not entry:
                continue
            meta = self.get_fantasy_card_meta(entry[0], entry[1], entry[2]) or self.get_fantasy_card_meta(entry[0])
            if meta:
                assigned_cards.append(meta)
        if len(assigned_cards) != sum(count for _, count in sbc.get("requirements", [])):
            return False
        for rarity, needed in sbc.get("requirements", []):
            count = len([card for card in assigned_cards if card.get("rarity") == rarity])
            if count < needed:
                return False
        return True

    def submit_active_sbc(self):
        if self.fantasy_sbc_active is None or not self.sbc_build_requirements_met():
            self.add_commentary("SBC requirements not met")
            return
        sbc = self.fantasy_sbc_catalog()[self.fantasy_sbc_active]
        consumed_keys = self.sbc_assigned_keys()
        self.fantasy_roster = [card for card in self.fantasy_roster if card.get("card_key") not in consumed_keys]
        self.fantasy_sbc_slots = []
        self.build_user_squad()
        reward_type = sbc.get("reward_type")
        if reward_type == "pack":
            self.store_pack(self.resolve_reward_pack_id(sbc.get("reward_pack", "gold")), source="SBC")
        elif reward_type == "pick":
            self.open_player_pick(sbc["name"], sbc.get("pick_band", "Elite"), sbc.get("pick_count", 3))
        else:
            self.fantasy_coins += sbc.get("reward_coins", 0)
        self.add_fantasy_xp(60)
        self.add_commentary(f"SBC completed: {sbc['name']}")
        if reward_type != "pick":
            self.state = "FANTASY_SBC"

    def cards_for_pack_band(self, band):
        if band.startswith("league:"):
            league_name = band.split(":", 1)[1]
            return [
                p for p in self.fantasy_pool
                if p.get("league") == league_name and p.get("rarity") not in ("Icon", "GOAT") and p.get("promo") != "Signature"
            ]
        if band == "Bronze":
            return [p for p in self.fantasy_pool if p.get("rarity") == "Bronze"]
        if band == "Silver":
            return [p for p in self.fantasy_pool if p.get("rarity") == "Silver"]
        if band == "Gold":
            return [p for p in self.fantasy_pool if p.get("rarity") == "Gold"]
        if band == "Platinum":
            return [p for p in self.fantasy_pool if p.get("rarity") == "Platinum"]
        if band == "Elite":
            return [p for p in self.fantasy_pool if p.get("rarity") == "Elite"]
        if band == "Diamond":
            return [p for p in self.fantasy_pool if p.get("rarity") == "Diamond"]
        if band == "Mythic":
            return [p for p in self.fantasy_pool if p.get("rarity") == "Mythic"]
        if band == "Ascended":
            return [p for p in self.fantasy_pool if p.get("rarity") == "Ascended"]
        if band == "Legend":
            return [p for p in self.fantasy_pool if p.get("rarity") == "Legend"]
        if band == "Transcendent":
            return [p for p in self.fantasy_pool if p.get("rarity") == "Transcendent"]
        if band == "Celestial":
            return [p for p in self.fantasy_pool if p.get("rarity") == "Celestial"]
        if band == "Eternal":
            return [p for p in self.fantasy_pool if p.get("rarity") == "Eternal"]
        if band == "Immortal":
            return [p for p in self.fantasy_pool if p.get("rarity") == "Immortal"]
        if band == "Omega":
            return [p for p in self.fantasy_pool if p.get("rarity") == "Omega"]
        if band == "GOAT":
            owned_goats = {p.get("name") for p in self.fantasy_roster if p.get("rarity") == "GOAT"}
            return [p for p in self.fantasy_pool if p.get("rarity") == "GOAT" and p.get("name") not in owned_goats]
        if band == "Icon":
            owned_icons = {p.get("name") for p in self.fantasy_roster if p.get("rarity") == "Icon"}
            return [p for p in self.fantasy_pool if p.get("rarity") == "Icon" and p.get("name") not in owned_icons]
        if band == "signature":
            owned_signatures = {p.get("name") for p in self.fantasy_roster if p.get("promo") == "Signature"}
            return [p for p in self.fantasy_pool if p.get("promo") == "Signature" and p.get("name") not in owned_signatures]
        if band == "promo":
            return [p for p in self.fantasy_pool if p.get("promo") != "Base" and p.get("rarity") != "GOAT" and p.get("promo") != "Signature"]
        if band == "ultimate":
            return [
                p
                for p in self.fantasy_pool
                if p.get("promo") != "Signature" and (p.get("rarity") in ("Elite", "Diamond", "Mythic", "Ascended", "Legend", "Transcendent", "Celestial", "Eternal", "Immortal", "Omega") or p.get("promo") != "Base")
            ]
        if band == "supreme":
            return [
                p
                for p in self.fantasy_pool
                if p.get("promo") != "Signature" and (p.get("rarity") in ("Mythic", "Ascended", "Legend", "Transcendent", "Celestial", "Eternal", "Immortal", "Omega") or p.get("promo") != "Base")
            ]
        return self.fantasy_pool[:]

    def cards_for_min_rarity(self, rarity):
        floor = self.rarity_rank(rarity)
        return [
            p for p in self.fantasy_pool
            if (
                p.get("rarity", self.card_rarity_from_rating(p.get("rating", 70), p.get("promo", "Base"))) not in ("Icon", "GOAT")
                or rarity in ("Icon", "GOAT")
            )
            and self.rarity_rank(p.get("rarity", self.card_rarity_from_rating(p.get("rating", 70), p.get("promo", "Base")))) >= floor
        ]

    def forged_pack_candidate(self, band, allow_promo=False):
        if not self.fantasy_pool:
            return None
        top_pool = sorted(
            [p for p in self.fantasy_pool if p.get("rarity") not in ("Icon", "GOAT")],
            key=lambda p: (-p.get("base_rating", p.get("rating", 70)), -p.get("rating", 70), p.get("name", "")),
        )[:40]
        if not top_pool:
            return None
        base = random.choice(top_pool).copy()
        floors = {
            "Transcendent": (100, 104, "Centurions"),
            "Celestial": (105, 109, "RTTK"),
            "Eternal": (110, 119, "Dynasty"),
            "Immortal": (120, 129, "Phantom"),
            "Omega": (130, 138, "TOTY"),
        }
        low, high, promo = floors.get(band, (self.rarity_rating_floor(band), self.rarity_rating_floor(band) + 3, "Base"))
        forged = base.copy()
        if allow_promo and (band in ("Immortal", "Omega") or random.random() < 0.75):
            forged["promo"] = promo
        else:
            forged["promo"] = "Base"
        forged["rating"] = random.randint(low, high)
        forged["rarity"] = self.card_rarity_from_rating(forged["rating"], forged["promo"])
        forged["traits"] = self.generate_card_traits(forged.get("position", "ST"), forged["rarity"], forged["promo"])
        forged["price"] = max(5, int(forged["rating"] * 0.6))
        forged["duplicate_protected"] = True
        forged["card_key"] = f"{forged['name']}|{forged['promo']}|{forged['rating']}|{forged.get('position', 'ST')}"
        return forged

    def open_pack(self, pack_id="silver", free=False, grant_xp=True):
        pack = self.get_pack_by_id(pack_id)
        cost = 0 if free else pack["cost"]
        if self.fantasy_coins < cost:
            self.add_commentary("Not enough coins")
            return
        if not self.fantasy_pool:
            self.add_commentary("No players available")
            return
        fantasy_team_names = {name.strip() for name in (self.user_team, self.fantasy_team_name) if isinstance(name, str) and name.strip()}
        self.fantasy_coins -= cost
        band = pack.get("band", "mixed")
        is_event_pack = bool(pack.get("event_id"))
        if band == "GOAT" and not self.cards_for_pack_band("GOAT"):
            self.fantasy_coins += cost
            self.add_commentary("All GOAT cards already owned")
            return
        if band == "Icon" and not self.cards_for_pack_band("Icon"):
            self.fantasy_coins += cost
            self.add_commentary("All Icon cards already owned")
            return
        if band == "signature" and not self.cards_for_pack_band("signature"):
            self.fantasy_coins += cost
            self.add_commentary("All Signature cards already owned")
            return
        if pack.get("open_mode") == "pick":
            self.update_objective_progress("packs", 1)
            if grant_xp:
                self.add_fantasy_xp(15)
            self.open_player_pick(
                pack["name"],
                pack.get("pick_band", band),
                pack.get("pick_count", 3),
                return_state=self.pack_open_return_state if self.pack_open_return_state else "LEAGUE",
            )
            self.add_commentary(f"{pack['name']} opened")
            return
        band_pool = self.cards_for_pack_band(band)
        if band.startswith("league:") and not band_pool:
            self.fantasy_coins += cost
            self.add_commentary("No players available for that league pack")
            return
        if not band_pool and band in self.rarity_order():
            band_pool = self.cards_for_min_rarity(band)
        if not band_pool:
            band_pool = self.fantasy_pool[:]
        pulls = []
        for pull_idx in range(pack["count"]):
            roll = random.random()
            allow_promo = band == "promo" or random.random() < 0.01
            allow_signature = band == "signature" or (band not in ("promo", "signature") and random.random() < 0.01)
            allow_goat = band == "GOAT" or (band != "GOAT" and random.random() < 0.00001)
            allow_icon = band == "Icon" or (band != "Icon" and random.random() < 0.0001)
            if band in self.rarity_order():
                min_rating = max(pack["guaranteed"], self.rarity_rating_floor(band))
                exact_band = self.cards_for_pack_band(band)
                candidates = [p for p in exact_band if p["rating"] >= min_rating] or exact_band[:]
                same_or_higher = self.cards_for_min_rarity(band)
                if not candidates:
                    candidates = [p for p in same_or_higher if p["rating"] >= min_rating] or same_or_higher[:]
                if not candidates and band in ("Transcendent", "Celestial", "Eternal", "Immortal", "Omega"):
                    forged = self.forged_pack_candidate(band, allow_promo=allow_promo)
                    candidates = [forged] if forged else []
                if not candidates:
                    candidates = band_pool[:]
                if band not in ("Legend", "Omega", "Icon", "GOAT"):
                    upgrade_pool = []
                    for upgrade_band, chance in self.pack_upgrade_targets(band):
                        if random.random() < chance:
                            upgrade_cards = self.cards_for_pack_band(upgrade_band)
                            upgrade_floor = self.rarity_rating_floor(upgrade_band)
                            upgrade_cards = [p for p in upgrade_cards if p["rating"] >= upgrade_floor] or upgrade_cards
                            if upgrade_cards:
                                upgrade_pool.extend(upgrade_cards)
                    if upgrade_pool:
                        candidates = upgrade_pool
            elif band == "promo":
                target_promo = self.choose_weighted_promo()
                if target_promo == "Signature":
                    candidates = self.cards_for_pack_band("signature")
                else:
                    candidates = [
                        p for p in self.fantasy_pool
                        if p.get("promo") == target_promo and p.get("rarity") not in ("Icon", "GOAT")
                    ]
                if not candidates:
                    candidates = [
                        p for p in self.fantasy_pool
                        if p.get("promo") != "Base" and p.get("rarity") not in ("Icon", "GOAT")
                    ]
                if pull_idx == 0:
                    candidates = [p for p in candidates if p["rating"] >= pack["guaranteed"]] or candidates
                elif roll < 0.35:
                    candidates = [p for p in candidates if p["rating"] >= 94] or candidates
                else:
                    candidates = [p for p in candidates if p["rating"] >= 88] or candidates
            elif band == "ultimate":
                if pull_idx == 0:
                    candidates = [p for p in band_pool if p["rating"] >= pack["guaranteed"]] or band_pool
                elif roll < 0.55:
                    candidates = [p for p in band_pool if p["rating"] >= 90] or band_pool
                else:
                    candidates = band_pool[:]
            elif band == "supreme":
                if pull_idx == 0:
                    candidates = [p for p in band_pool if p["rating"] >= pack["guaranteed"]] or band_pool
                elif roll < 0.25:
                    candidates = [p for p in band_pool if p.get("rarity") in ("Legend", "Icon", "Transcendent", "Celestial", "Eternal", "Immortal", "Omega")] or band_pool
                else:
                    candidates = band_pool[:]
            elif band == "signature":
                candidates = [p for p in band_pool if p["rating"] >= pack["guaranteed"]] or band_pool[:]
            elif band.startswith("league:"):
                league_pool = [p for p in band_pool if p["rating"] >= pack["guaranteed"]] or band_pool[:]
                if pull_idx == 0:
                    candidates = league_pool
                elif roll < 0.10:
                    candidates = [p for p in league_pool if p["rating"] >= 88] or league_pool
                elif roll < 0.30:
                    candidates = [p for p in league_pool if p["rating"] >= 84] or league_pool
                else:
                    candidates = band_pool[:]
            else:
                if pull_idx == 0:
                    candidates = [p for p in self.fantasy_pool if p["rating"] >= pack["guaranteed"]] or self.fantasy_pool
                elif roll < 0.08:
                    candidates = [p for p in self.fantasy_pool if p["rating"] >= 90] or self.fantasy_pool
                elif roll < 0.25:
                    candidates = [p for p in self.fantasy_pool if p["rating"] >= 84] or self.fantasy_pool
                elif roll < 0.6:
                    candidates = [p for p in self.fantasy_pool if p["rating"] >= 72] or self.fantasy_pool
                else:
                    candidates = self.fantasy_pool[:]
            candidates = [card for card in candidates if card.get("team") not in fantasy_team_names] or candidates
            if allow_goat:
                goat_candidates = self.cards_for_pack_band("GOAT")
                if goat_candidates:
                    candidates = goat_candidates
            elif allow_icon:
                icon_candidates = self.cards_for_pack_band("Icon")
                if icon_candidates:
                    candidates = icon_candidates
            elif allow_signature:
                signature_candidates = self.cards_for_pack_band("signature")
                if signature_candidates:
                    candidates = signature_candidates
            elif band == "signature":
                signature_candidates = self.cards_for_pack_band("signature")
                if signature_candidates:
                    candidates = signature_candidates
            elif allow_promo and band != "promo":
                promo_candidates = [p for p in candidates if p.get("promo", "Base") != "Base"]
                if promo_candidates:
                    candidates = promo_candidates
            elif band != "promo":
                non_special_candidates = [p for p in candidates if p.get("rarity") not in ("Icon", "GOAT")]
                if non_special_candidates:
                    candidates = non_special_candidates
                non_promo_candidates = [p for p in candidates if p.get("promo", "Base") == "Base" or p.get("promo") == "Signature"]
                if band not in ("signature",):
                    non_promo_candidates = [p for p in non_promo_candidates if p.get("promo") != "Signature"]
                if non_promo_candidates:
                    candidates = non_promo_candidates
                elif band in ("Transcendent", "Celestial", "Eternal", "Immortal", "Omega"):
                    forged = self.forged_pack_candidate(band, allow_promo=False)
                    if forged:
                        candidates = [forged]
            candidates = self.apply_pack_event_boost(candidates, band)
            used_keys = {self.fantasy_card_key(p) for p in pulls}
            used_names = {p.get("name") for p in pulls}
            unique_candidates = [
                p for p in candidates
                if self.fantasy_card_key(p) not in used_keys and p.get("name") not in used_names
            ]
            if unique_candidates:
                candidates = unique_candidates
            fresh_candidates = [
                p for p in candidates
                if not any(self.fantasy_card_key(card) == self.fantasy_card_key(p) for card in self.fantasy_roster)
            ]
            if fresh_candidates:
                candidates = fresh_candidates
            pick = random.choice(candidates).copy()
            rerolls = 0
            while any(self.fantasy_card_key(p) == self.fantasy_card_key(pick) for p in self.fantasy_roster) and rerolls < 8:
                alt_candidates = [p for p in candidates if self.fantasy_card_key(p) != self.fantasy_card_key(pick)]
                if not alt_candidates:
                    break
                pick = random.choice(alt_candidates).copy()
                rerolls += 1
            if rerolls >= 3 or unique_candidates:
                pick["duplicate_protected"] = True
            if is_event_pack:
                pick["event_source"] = pack.get("event_id")
            pulls.append(pick)
            self.add_fantasy_player(pick)
        self.last_pack = pulls
        featured = max(pulls, key=lambda p: (p["rating"], p.get("rarity", ""), p.get("promo", ""))) if pulls else None
        self.walkout_timer = self.walkout_duration_for_player(featured, len(pulls))
        self.walkout_index = 0
        self.pack_summary_timer = 0.0
        self.update_objective_progress("packs", 1)
        if grant_xp:
            self.add_fantasy_xp(15)
        if pulls:
            self.play_walkout_sound(max(pulls, key=lambda p: p["rating"]))
        if is_event_pack:
            self.event_evo_tokens += pack.get("pack_evo_tokens", 1)
            self.add_commentary("Event evolution token gained")
        self.state = "PACK_OPENING"
        self.add_commentary(f"{pack['name']} opened")

    def blend_color(self, a, b, t):
        t = max(0.0, min(1.0, t))
        return (
            int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t),
        )

    def draw_card_art_layers(self, rect, base_color, accent, rarity="Gold", promo="Base"):
        x, y, w, h = rect
        dark = self.blend_color(base_color, (12, 14, 22), 0.32)
        light = self.blend_color(base_color, WHITE, 0.18)
        bg = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
        for i in range(int(h)):
            mix = 0 if h <= 1 else i / max(1, h - 1)
            row = self.blend_color(light, dark, mix)
            pygame.draw.line(bg, row, (0, i), (w, i))
        self.screen.blit(bg, (x, y))

        gloss = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
        pygame.draw.polygon(gloss, (255, 255, 255, 26), [(0, 0), (w * 0.62, 0), (w * 0.28, h), (0, h)])
        pygame.draw.ellipse(gloss, (*accent, 26), (w * 0.12, h * 0.08, w * 0.76, h * 0.20))
        self.screen.blit(gloss, (x, y))

        edge = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
        pygame.draw.rect(edge, (*accent, 46), (8, 8, w - 16, h - 16), 1, border_radius=16)
        self.screen.blit(edge, (x, y))
        if rarity == "GOAT":
            shine = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
            for idx in range(6):
                band_y = int(h * (0.08 + idx * 0.11))
                pygame.draw.polygon(
                    shine,
                    (*accent, max(16, 70 - idx * 8)),
                    [(0, band_y), (w * 0.70, band_y - h * 0.07), (w, band_y + h * 0.06), (w * 0.32, band_y + h * 0.14)],
                )
            pygame.draw.ellipse(shine, (255, 255, 255, 58), (w * 0.08, h * 0.04, w * 0.84, h * 0.18))
            for star_idx in range(14):
                sx = int(w * (0.12 + (star_idx % 4) * 0.20) + (star_idx // 4) * 7)
                sy = int(h * (0.18 + (star_idx // 4) * 0.12))
                pygame.draw.circle(shine, (255, 235, 170, 70), (sx, sy), 2)
            pygame.draw.rect(shine, (255, 220, 120, 60), (12, 12, w - 24, h - 24), 2, border_radius=18)
            pygame.draw.rect(shine, (255, 255, 255, 36), (18, 18, w - 36, h - 36), 1, border_radius=16)
            self.screen.blit(shine, (x, y))
        elif promo == "Signature":
            shine = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
            pygame.draw.rect(shine, (255, 218, 120, 54), (12, 12, w - 24, h - 24), 2, border_radius=18)
            pygame.draw.rect(shine, (255, 255, 255, 26), (18, 18, w - 36, h - 36), 1, border_radius=16)
            for idx in range(5):
                band_y = int(h * (0.16 + idx * 0.12))
                pygame.draw.polygon(
                    shine,
                    (*accent, max(18, 68 - idx * 10)),
                    [(0, band_y), (w * 0.48, band_y - h * 0.08), (w, band_y + h * 0.04), (w * 0.54, band_y + h * 0.14)],
                )
            for star_idx in range(10):
                sx = int(w * (0.14 + (star_idx % 5) * 0.16))
                sy = int(h * (0.14 + (star_idx // 5) * 0.12))
                pygame.draw.circle(shine, (255, 232, 172, 80), (sx, sy), 2)
            self.screen.blit(shine, (x, y))

    def draw_icon_star(self, center_x, center_y, color):
        points = []
        for i in range(10):
            angle = -math.pi / 2 + i * math.pi / 5
            radius = 10 if i % 2 == 0 else 4
            points.append((center_x + math.cos(angle) * radius, center_y + math.sin(angle) * radius))
        pygame.draw.polygon(self.screen, color, points)

    def draw_card(self, x, y, w, h, player):
        name = player["name"]
        rating = player["rating"]
        team = player["team"]
        league = player.get("league", get_team_league(team))
        tier = player.get("rarity") or self.card_tier(rating)[0]
        base_color, accent = self.card_theme_colors(player)
        promo = player.get("promo", "Base")
        form_boost = player.get("form_boost", 0)
        evo_level = player.get("evo_level", 0)
        goat_profile = self.goat_card_profile(player) if tier == "GOAT" else None
        signature_profile = self.signature_card_profile(player) if promo == "Signature" else None
        card = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, base_color, card, 0, border_radius=18)
        self.draw_card_art_layers((x, y, w, h), base_color, accent, tier, promo)
        if goat_profile:
            overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            stripe_h = max(16, int(h * 0.085))
            for idx, color in enumerate(goat_profile["stripes"]):
                top = int(h * 0.18) + idx * max(12, stripe_h - 6)
                pygame.draw.polygon(
                    overlay,
                    (*color, 88 if idx < 3 else 66),
                    [(0, top), (w * 0.24, top - 8), (w * 0.58, top + stripe_h // 2), (0, top + stripe_h + 6)],
                )
                pygame.draw.polygon(
                    overlay,
                    (*color, 80 if idx < 3 else 56),
                    [(w, top + 12), (w * 0.72, top - 6), (w * 0.42, top + stripe_h // 2), (w, top + stripe_h + 10)],
                )
            pygame.draw.ellipse(overlay, (255, 255, 255, 58), (w * 0.10, h * 0.04, w * 0.80, h * 0.20))
            pygame.draw.rect(overlay, (255, 220, 120, 46), (10, 10, w - 20, h - 20), 2, border_radius=18)
            self.screen.blit(overlay, (x, y))
        elif signature_profile:
            overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            for idx, color in enumerate(signature_profile["streaks"]):
                top = int(h * 0.22) + idx * max(16, int(h * 0.10))
                pygame.draw.polygon(
                    overlay,
                    (*color, 74 if idx == 1 else 52),
                    [(0, top), (w * 0.18, top - 10), (w * 0.64, top + 8), (0, top + 24)],
                )
                pygame.draw.polygon(
                    overlay,
                    (*color, 68 if idx == 1 else 46),
                    [(w, top + 18), (w * 0.84, top - 6), (w * 0.36, top + 14), (w, top + 34)],
                )
            pygame.draw.ellipse(overlay, (*signature_profile["glow"], 42), (w * 0.10, h * 0.08, w * 0.80, h * 0.16))
            pygame.draw.ellipse(overlay, (255, 255, 255, 36), (w * 0.16, h * 0.05, w * 0.68, h * 0.12))
            self.screen.blit(overlay, (x, y))
        pygame.draw.rect(self.screen, accent, card, 3, border_radius=18)
        if goat_profile or signature_profile:
            pygame.draw.rect(self.screen, (255, 232, 170), (x + 6, y + 6, w - 12, h - 12), 1, border_radius=18)
        if evo_level > 0:
            rim_color = self.blend_color(accent, (220, 255, 235), 0.35)
            for i in range(evo_level):
                inset = 6 + i * 4
                pygame.draw.rect(self.screen, rim_color, (x + inset, y + inset, w - inset * 2, h - inset * 2), 1, border_radius=16)
        glow = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(6):
            alpha = max(0, 66 - i * 10)
            pygame.draw.rect(glow, (*accent, alpha), (8 + i * 4, 10 + i * 3, w - 16 - i * 8, h * 0.22), 0, border_radius=14)
        self.screen.blit(glow, (x, y))
        badge = pygame.Rect(x + 12, y + 12, w - 24, 40)
        badge_fill = (255, 255, 255, 20) if not goat_profile else (8, 10, 16, 210)
        pygame.draw.rect(self.screen, badge_fill, badge, 0, border_radius=12)
        pygame.draw.rect(self.screen, (*accent, 120), badge, 1, border_radius=12)
        if goat_profile:
            goat_font = pygame.font.SysFont("Georgia", 20, bold=True, italic=True)
            goat_word = goat_font.render(goat_profile["title"], True, accent)
            self.screen.blit(goat_word, (x + w / 2 - goat_word.get_width() / 2, y + 17))
        elif signature_profile:
            sig_font = pygame.font.SysFont("Georgia", 18, bold=True, italic=True)
            sig_word = sig_font.render("Signature", True, accent)
            self.screen.blit(sig_word, (x + w / 2 - sig_word.get_width() / 2, y + 18))
        else:
            self.screen.blit(self.small.render(tier.upper(), True, accent), (x + 16, y + 18))
        if tier == "Icon":
            self.draw_icon_star(x + w / 2, y + 28, accent)
        elif goat_profile:
            self.draw_flag_chip(x + 12, y + 12, 44, 20, goat_profile["flag"], accent)
            crown_points = [
                (x + w - 48, y + 30),
                (x + w - 40, y + 18),
                (x + w - 32, y + 28),
                (x + w - 24, y + 16),
                (x + w - 16, y + 30),
            ]
            pygame.draw.lines(self.screen, accent, False, crown_points, 3)
        elif signature_profile:
            star_points = [
                (x + w - 34, y + 20),
                (x + w - 30, y + 28),
                (x + w - 22, y + 30),
                (x + w - 28, y + 36),
                (x + w - 26, y + 44),
                (x + w - 34, y + 40),
                (x + w - 42, y + 44),
                (x + w - 40, y + 36),
                (x + w - 46, y + 30),
                (x + w - 38, y + 28),
            ]
            pygame.draw.polygon(self.screen, accent, star_points)
        if evo_level > 0:
            self.screen.blit(self.small.render(f"EVO {evo_level}", True, rim_color), (x + w - 54, y + 18))
        rating_plate = pygame.Rect(x + 14, y + 60, 70, 56)
        pygame.draw.rect(self.screen, (12, 16, 26), rating_plate, 0, border_radius=12)
        pygame.draw.rect(self.screen, accent, rating_plate, 2, border_radius=12)
        self.screen.blit(self.big.render(str(rating), True, WHITE), (x + 24, y + 68))
        self.screen.blit(self.small.render(team, True, (220, 228, 236)), (x + 16, y + int(h * 0.48)))
        self.screen.blit(self.small.render(league[:18], True, (200, 210, 220)), (x + 16, y + int(h * 0.54)))
        pos_chip = pygame.Rect(x + 14, y + int(h * 0.58), 54, 26)
        pygame.draw.rect(self.screen, (12, 18, 30), pos_chip, 0, border_radius=10)
        pygame.draw.rect(self.screen, accent, pos_chip, 1, border_radius=10)
        self.screen.blit(self.small.render(player.get("position", "ST"), True, WHITE), (x + 22, y + int(h * 0.58) + 4))
        promo_text = promo if len(promo) <= 12 else promo[:11]
        if tier == "GOAT":
            promo_text = "GOAT EDITION"
        elif promo == "Signature":
            promo_text = "SIGNATURE"
        self.screen.blit(self.small.render(promo_text, True, accent), (x + 14, y + int(h * 0.71)))
        traits = player.get("traits", [])
        chem_tags = []
        if self.game_mode == "FANTASY":
            chem_tags = self.fantasy_chemistry_breakdown.get((player.get("name"), player.get("number"), player.get("rating")), [])
        if traits:
            trait_text = "/".join(t.split()[0] for t in traits[:2])
            skill_chip = pygame.Rect(x + 12, y + int(h * 0.77), w - 24, 24)
            pygame.draw.rect(self.screen, (12, 18, 30), skill_chip, 0, border_radius=10)
            pygame.draw.rect(self.screen, (*accent, 120), skill_chip, 1, border_radius=10)
            self.screen.blit(self.small.render(trait_text[:18], True, (220, 230, 240)), (x + 18, y + int(h * 0.77) + 4))
        if chem_tags:
            chem_text = " ".join(chem_tags[:3])
            chem_chip = pygame.Rect(x + 12, y + int(h * 0.84), w - 24, 20)
            pygame.draw.rect(self.screen, (12, 18, 30), chem_chip, 0, border_radius=10)
            pygame.draw.rect(self.screen, (244, 206, 84), chem_chip, 1, border_radius=10)
            self.screen.blit(self.small.render(chem_text[:20], True, (220, 230, 240)), (x + 18, y + int(h * 0.84) + 2))
        if form_boost > 0:
            self.screen.blit(self.small.render(f"+{form_boost} form", True, LIGHT_GREEN), (x + 14, y + int(h * 0.90)))
        short = name if len(name) <= 14 else name[:11] + "..."
        self.screen.blit(self.font.render(short, True, WHITE), (x + 14, y + h - 32))

    def draw_squad_card(self, x, y, w, h, entry, role="", selected=False, picked=False):
        name, num, rating = entry
        card_meta = next((c for c in self.fantasy_roster if c["name"] == name and c.get("number") == num and c["rating"] == rating), None)
        if card_meta:
            base, accent = self.card_theme_colors(card_meta)
            promo = card_meta.get("promo", "Base")
            rarity = card_meta.get("rarity", "Base")
            league = card_meta.get("league", get_team_league(card_meta.get("team", "")))
            traits = card_meta.get("traits", [])
            evo_level = card_meta.get("evo_level", 0)
            goat_profile = self.goat_card_profile(card_meta) if rarity == "GOAT" else None
            signature_profile = self.signature_card_profile(card_meta) if promo == "Signature" else None
        else:
            _, accent = self.card_tier(rating)
            base = (245, 220, 135) if rating >= 78 else (205, 212, 222) if rating >= 70 else (176, 138, 100)
            promo = "Base"
            rarity = "Base"
            league = get_team_league("")
            traits = []
            evo_level = 0
            goat_profile = None
            signature_profile = None
        card = pygame.Rect(int(x), int(y), int(w), int(h))
        pygame.draw.rect(self.screen, base, card, 0, border_radius=16)
        self.draw_card_art_layers((x, y, w, h), base, accent, rarity, promo)
        if goat_profile:
            overlay = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
            for idx, color in enumerate(goat_profile["stripes"][:4]):
                top = int(h * 0.18) + idx * 12
                pygame.draw.polygon(
                    overlay,
                    (*color, 74 if idx < 2 else 56),
                    [(0, top), (w * 0.20, top - 8), (w * 0.52, top + 8), (0, top + 18)],
                )
                pygame.draw.polygon(
                    overlay,
                    (*color, 70 if idx < 2 else 50),
                    [(w, top + 8), (w * 0.78, top - 8), (w * 0.46, top + 8), (w, top + 20)],
                )
            self.screen.blit(overlay, (x, y))
        elif signature_profile:
            overlay = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
            for idx, color in enumerate(signature_profile["streaks"][:3]):
                top = int(h * 0.22) + idx * 14
                pygame.draw.polygon(
                    overlay,
                    (*color, 64 if idx == 1 else 48),
                    [(0, top), (w * 0.22, top - 6), (w * 0.56, top + 8), (0, top + 18)],
                )
                pygame.draw.polygon(
                    overlay,
                    (*color, 56 if idx == 1 else 40),
                    [(w, top + 8), (w * 0.80, top - 6), (w * 0.40, top + 8), (w, top + 22)],
                )
            self.screen.blit(overlay, (x, y))
        pygame.draw.rect(self.screen, accent, card, 3, border_radius=16)
        if goat_profile or signature_profile:
            pygame.draw.rect(self.screen, (255, 232, 170), (x + 4, y + 4, w - 8, h - 8), 1, border_radius=16)
        if evo_level > 0:
            rim_color = self.blend_color(accent, (220, 255, 235), 0.35)
            for i in range(evo_level):
                inset = 6 + i * 3
                pygame.draw.rect(self.screen, rim_color, (x + inset, y + inset, w - inset * 2, h - inset * 2), 1, border_radius=14)
        if selected:
            pygame.draw.rect(self.screen, YELLOW, card.inflate(6, 6), 3, border_radius=16)
        if picked:
            pygame.draw.rect(self.screen, CYAN, card.inflate(10, 10), 3, border_radius=18)
        header = pygame.Rect(x + 8, y + 8, w - 16, 24)
        pygame.draw.rect(self.screen, (255, 255, 255, 220), header, 0, border_radius=8)
        self.screen.blit(self.small.render(str(rating), True, BLACK), (x + 12, y + 10))
        self.screen.blit(self.small.render(role, True, BLACK), (x + w - 34, y + 10))
        if rarity == "Icon":
            self.draw_icon_star(x + w / 2, y + 20, accent)
        elif goat_profile:
            self.draw_flag_chip(x + 8, y + 8, 28, 14, goat_profile["flag"], accent)
            mini_goat = pygame.font.SysFont("Georgia", 11, bold=True, italic=True).render("GOAT", True, accent)
            self.screen.blit(mini_goat, (x + w / 2 - mini_goat.get_width() / 2, y + 10))
        elif signature_profile:
            mini_sig = pygame.font.SysFont("Georgia", 10, bold=True, italic=True).render("SIG", True, accent)
            self.screen.blit(mini_sig, (x + w / 2 - mini_sig.get_width() / 2, y + 10))
        if rarity != "Base":
            rarity_label = rarity[:6].upper()
            rarity_chip = pygame.Rect(x + 8, y + 34, w - 16, 20)
            pygame.draw.rect(self.screen, (10, 12, 20, 170), rarity_chip, 0, border_radius=8)
            self.screen.blit(self.small.render(rarity_label, True, WHITE), (x + 12, y + 36))
        name_label = name if len(name) <= 12 else name[:10] + ".."
        footer = pygame.Rect(x + 8, y + h - 38, w - 16, 30)
        pygame.draw.rect(self.screen, (10, 12, 20, 170), footer, 0, border_radius=8)
        self.screen.blit(self.small.render(name_label, True, WHITE), (x + 10, y + h - 34))
        league_label = league[:8].upper()
        self.screen.blit(self.small.render(f"#{num}", True, (220, 228, 236)), (x + 10, y + h - 18))
        self.screen.blit(self.small.render(league_label, True, (220, 228, 236)), (x + w - 56, y + h - 18))
        if traits:
            trait_label = traits[0][:8].upper()
            self.screen.blit(self.small.render(trait_label, True, WHITE), (x + w - 62, y + h - 34))
        chem_tags = self.fantasy_chemistry_breakdown.get((name, num, rating), []) if self.game_mode == "FANTASY" else []
        if chem_tags:
            self.screen.blit(self.small.render(chem_tags[0][:5], True, accent), (x + 10, y + h - 34))
        if promo != "Base":
            self.screen.blit(self.small.render(promo[:4], True, accent), (x + w - 34, y + h - 18))
        if evo_level > 0:
            self.screen.blit(self.small.render(f"E{evo_level}", True, accent), (x + w - 30, y + 36))
        return card

    def draw_pack_shop(self, x, y, w, h):
        pygame.draw.rect(self.screen, (26, 32, 40), (x, y, w, h), 0)
        pygame.draw.rect(self.screen, (60, 70, 85), (x, y, w, h), 2)
        self.screen.blit(self.font.render("Pack Shop", True, WHITE), (x + 12, y + 8))
        self.screen.blit(self.small.render("UP/DOWN select | ENTER buy | ESC close", True, (200, 210, 220)), (x + 12, y + 32))
        base_y = y + 60
        packs = self.visible_fantasy_packs()
        for i, pack in enumerate(packs):
            row_y = base_y + i * 34
            color = YELLOW if i == self.pack_shop_index else WHITE
            band = pack.get("band", "mixed")
            band_label = band.upper() if band != "mixed" else "MIXED"
            line = f"{pack['name']:<12} {pack['count']} cards {band_label:<9} {pack['cost']} coins"
            self.screen.blit(self.small.render(line, True, color), (x + 12, row_y))
        self.screen.blit(self.small.render("Bronze to Legend packs stay in-tier. Promo and Ultimate can break the cap.", True, (180, 190, 205)), (x + 12, y + h - 28))

    def draw_pack_visual(self, x, y, w, h, pack, selected=False):
        band = pack.get("band", "mixed")
        rarity = band if band not in ("mixed", "promo", "ultimate") else "Legend" if band == "ultimate" else "Gold"
        base_color, accent = self.card_theme_colors({"rating": pack.get("guaranteed", 80), "promo": "Base", "rarity": rarity})
        frame = pygame.Rect(int(x), int(y), int(w), int(h))
        pygame.draw.rect(self.screen, base_color, frame, 0, border_radius=18)
        self.draw_card_art_layers((x, y, w, h), base_color, accent, rarity, "Base")
        pygame.draw.rect(self.screen, accent, frame, 4 if selected else 2, border_radius=18)
        if selected:
            pygame.draw.rect(self.screen, YELLOW, frame.inflate(8, 8), 3, border_radius=22)
        shine = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
        pygame.draw.polygon(shine, (255, 255, 255, 40), [(0, 0), (w * 0.55, 0), (w * 0.2, h), (0, h)])
        pygame.draw.polygon(shine, (*accent, 42), [(w * 0.62, 0), (w, 0), (w, h * 0.65), (w * 0.42, h * 0.25)])
        self.screen.blit(shine, (x, y))
        pygame.draw.rect(self.screen, (255, 255, 255, 24), (x + 14, y + 14, w - 28, 34), 0, border_radius=10)
        badge = pygame.Rect(x + 18, y + 56, 82, 48)
        pygame.draw.rect(self.screen, (12, 16, 26), badge, 0, border_radius=12)
        pygame.draw.rect(self.screen, accent, badge, 2, border_radius=12)
        title = pack["name"] if len(pack["name"]) <= 14 else pack["name"][:13]
        self.screen.blit(self.small.render(title, True, WHITE), (x + 16, y + 18))
        self.screen.blit(self.big.render(str(pack["cost"]), True, WHITE), (x + 28, y + 62))
        self.screen.blit(self.small.render("COINS", True, accent), (x + 28, y + 94))
        band_chip = pygame.Rect(x + 18, y + 120, w - 36, 28)
        pygame.draw.rect(self.screen, (12, 16, 26, 190), band_chip, 0, border_radius=10)
        self.screen.blit(self.font.render(band.upper(), True, WHITE), (x + 24, y + 126))
        self.screen.blit(self.small.render(f"{pack['count']} cards", True, (220, 228, 236)), (x + 18, y + h - 44))
        self.screen.blit(self.small.render(f"{pack['guaranteed']}+ OVR", True, (220, 228, 236)), (x + 18, y + h - 22))

    def draw_pack_shop_page(self):
        self.screen.fill((10, 14, 24))
        self.screen.blit(self.big.render("Fantasy Pack Shop", True, WHITE), (34, 22))
        self.screen.blit(self.small.render("LEFT/RIGHT move | UP/DOWN row scroll | ENTER buy | O odds | M my packs | E refresh event | ESC back", True, (190, 200, 215)), (36, 56))
        self.screen.blit(self.font.render(f"Coins: {self.fantasy_coins}", True, WHITE), (980, 28))

        event = self.current_pack_event or {}
        banner = pygame.Rect(36, 78, 1096, 88)
        if event:
            base_color, accent = event.get("colors", ((16, 24, 42), (96, 170, 255)))
            pygame.draw.rect(self.screen, base_color, banner, 0, border_radius=20)
            pygame.draw.rect(self.screen, accent, banner, 2, border_radius=20)
            glow = pygame.Surface((banner.w, banner.h), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (*accent, 44), (20, -12, banner.w * 0.62, banner.h + 24))
            pygame.draw.polygon(glow, (255, 255, 255, 24), [(0, 0), (banner.w * 0.42, 0), (banner.w * 0.24, banner.h), (0, banner.h)])
            self.screen.blit(glow, (banner.x, banner.y))
            self.screen.blit(self.font.render(event.get("name", "Pack Event"), True, WHITE), (banner.x + 20, banner.y + 14))
            self.screen.blit(self.small.render(event.get("subtitle", "Featured packs active"), True, (220, 228, 236)), (banner.x + 20, banner.y + 42))
            featured_pack = event.get("featured_pack", "").replace("_", " ").title()
            featured_names = ", ".join(event.get("signature_names", [])[:3]) or "League boost active"
            self.screen.blit(self.small.render(f"Featured pack: {featured_pack}", True, WHITE), (banner.x + 620, banner.y + 18))
            self.screen.blit(self.small.render(featured_names[:42], True, (220, 228, 236)), (banner.x + 620, banner.y + 46))
            self.screen.blit(self.small.render(f"Event Evo tokens: {self.event_evo_tokens}", True, (200, 230, 200)), (banner.x + 920, banner.y + 30))

        packs = self.visible_fantasy_packs()
        if not packs:
            return
        self.pack_shop_index = max(0, min(self.pack_shop_index, len(packs) - 1))
        cols = 4
        card_w = 230
        card_h = 190
        gap_x = 28
        gap_y = 26
        start_x = 70
        start_y = 190
        visible_rows = 2
        selected_row = self.pack_shop_index // cols
        max_row = (len(packs) - 1) // cols
        row_start = max(0, min(selected_row - 1, max_row - visible_rows + 1))
        row_end = min(max_row + 1, row_start + visible_rows)
        for i, pack in enumerate(packs):
            row = i // cols
            if row < row_start or row >= row_end:
                continue
            col = i % cols
            px = start_x + col * (card_w + gap_x)
            py = start_y + (row - row_start) * (card_h + gap_y)
            self.draw_pack_visual(px, py, card_w, card_h, pack, i == self.pack_shop_index)

        selected = packs[self.pack_shop_index]
        info = pygame.Rect(70, 620, 1060, 126)
        pygame.draw.rect(self.screen, (22, 28, 40), info, 0, border_radius=18)
        pygame.draw.rect(self.screen, (70, 86, 122), info, 2, border_radius=18)
        self.screen.blit(self.font.render(selected["name"], True, WHITE), (info.x + 18, info.y + 14))
        detail = f"{selected['count']} cards | {selected['guaranteed']}+ OVR | {selected['cost']} coins"
        self.screen.blit(self.small.render(detail, True, (214, 222, 236)), (info.x + 18, info.y + 46))
        odds_lines = self.pack_odds_lines(selected)
        self.screen.blit(self.small.render(odds_lines[0], True, (180, 190, 205)), (info.x + 18, info.y + 76))
        if len(odds_lines) > 1:
            self.screen.blit(self.small.render(odds_lines[1], True, (180, 190, 205)), (info.x + 18, info.y + 98))
        if row_start > 0:
            self.screen.blit(self.small.render("More packs above", True, (180, 190, 205)), (980, 170))
        if row_end < max_row + 1:
            self.screen.blit(self.small.render("More packs below", True, (180, 190, 205)), (980, 590))

    def draw_my_packs_page(self):
        self.screen.fill((10, 14, 24))
        self.screen.blit(self.big.render("My Packs", True, WHITE), (34, 22))
        self.screen.blit(self.small.render("UP/DOWN select | ENTER open | O odds | ESC back", True, (190, 200, 215)), (36, 56))
        self.screen.blit(self.font.render(f"Owned Packs: {len(self.my_packs)}", True, WHITE), (960, 28))
        panel = pygame.Rect(40, 96, 1120, 560)
        pygame.draw.rect(self.screen, (22, 28, 40), panel, 0, border_radius=20)
        pygame.draw.rect(self.screen, (70, 86, 122), panel, 2, border_radius=20)
        if not self.my_packs:
            self.screen.blit(self.font.render("No packs stored", True, WHITE), (panel.x + 24, panel.y + 28))
            self.screen.blit(self.small.render("Buy packs from the shop or earn them from competitions, SBCs, and objectives.", True, (190, 200, 215)), (panel.x + 24, panel.y + 60))
            return
        self.my_packs_index = max(0, min(self.my_packs_index, len(self.my_packs) - 1))
        visible = 4
        start = max(0, min(self.my_packs_index - visible + 1, len(self.my_packs) - visible))
        row_y = panel.y + 26
        for i in range(start, min(len(self.my_packs), start + visible)):
            pack = self.get_pack_by_id(self.my_packs[i])
            row = pygame.Rect(panel.x + 18, row_y, panel.w - 36, 118)
            selected = i == self.my_packs_index
            bg = (42, 52, 72) if selected else (28, 34, 48)
            pygame.draw.rect(self.screen, bg, row, 0, border_radius=16)
            pygame.draw.rect(self.screen, YELLOW if selected else (86, 98, 126), row, 2, border_radius=16)
            self.draw_pack_visual(row.x + 16, row.y + 14, 126, 90, pack, selected)
            self.screen.blit(self.font.render(pack["name"], True, WHITE), (row.x + 164, row.y + 18))
            self.screen.blit(self.small.render(f"{pack['count']} cards | {pack['guaranteed']}+ OVR", True, (214, 222, 236)), (row.x + 164, row.y + 50))
            self.screen.blit(self.small.render(f"Band: {pack.get('band', 'mixed').upper()}", True, (190, 200, 215)), (row.x + 164, row.y + 78))
            self.screen.blit(self.small.render(self.pack_odds_lines(pack)[0][:54], True, (180, 190, 205)), (row.x + 420, row.y + 50))
            row_y += 132
        if start > 0:
            self.screen.blit(self.small.render("More above", True, (180, 190, 205)), (panel.right - 110, panel.y + 10))
        if start + visible < len(self.my_packs):
            self.screen.blit(self.small.render("More below", True, (180, 190, 205)), (panel.right - 110, panel.bottom - 26))

    def draw_pack_odds_page(self):
        pack = self.get_pack_by_id(self.pack_detail_pack_id)
        self.screen.fill((10, 14, 24))
        self.screen.blit(self.big.render(pack["name"], True, WHITE), (34, 22))
        self.screen.blit(self.small.render("ENTER buy/open | ESC back", True, (190, 200, 215)), (36, 56))
        card_panel = pygame.Rect(60, 110, 320, 500)
        detail_panel = pygame.Rect(420, 110, 700, 500)
        pygame.draw.rect(self.screen, (22, 28, 40), card_panel, 0, border_radius=20)
        pygame.draw.rect(self.screen, (70, 86, 122), card_panel, 2, border_radius=20)
        pygame.draw.rect(self.screen, (22, 28, 40), detail_panel, 0, border_radius=20)
        pygame.draw.rect(self.screen, (70, 86, 122), detail_panel, 2, border_radius=20)
        self.draw_pack_visual(card_panel.x + 34, card_panel.y + 34, 250, 210, pack, selected=True)
        self.screen.blit(self.font.render(f"Cost: {pack['cost']} coins", True, WHITE), (card_panel.x + 34, card_panel.y + 276))
        self.screen.blit(self.font.render(f"Cards: {pack['count']}", True, WHITE), (card_panel.x + 34, card_panel.y + 312))
        self.screen.blit(self.font.render(f"Guaranteed: {pack['guaranteed']}+ OVR", True, WHITE), (card_panel.x + 34, card_panel.y + 348))
        self.screen.blit(self.font.render(f"Band: {pack.get('band', 'mixed').upper()}", True, WHITE), (card_panel.x + 34, card_panel.y + 384))

        self.screen.blit(self.font.render("Odds And Rewards", True, WHITE), (detail_panel.x + 18, detail_panel.y + 16))
        y = detail_panel.y + 58
        for line in self.pack_odds_breakdown(pack):
            self.screen.blit(self.font.render(line, True, (214, 222, 236)), (detail_panel.x + 20, y))
            y += 34
        y += 8
        self.screen.blit(self.font.render("Walkout Profile", True, WHITE), (detail_panel.x + 18, y))
        y += 42
        band = pack.get("band", "mixed")
        if band == "GOAT":
            walkout_lines = ["Ultimate crown tunnel", "Longest suspense phase", "Heavy gold flare finish"]
        elif band == "Icon":
            walkout_lines = ["Special suspense tunnel", "Hidden card-back reveal", "Classic gold-white finish"]
        elif band in ("Omega", "Immortal", "Eternal", "Celestial", "Transcendent"):
            walkout_lines = ["Ultra-tier tunnel lights", "Stronger reveal flash", "Top-end flare finish"]
        elif band in ("Legend", "Ascended", "Mythic", "Diamond"):
            walkout_lines = ["High-tier FC-style tunnel", "Extra light lanes", "Enhanced confetti finish"]
        else:
            walkout_lines = ["Standard tunnel reveal", "Tier spikes can trigger bigger scenes", "Pack summary after walkout"]
        for line in walkout_lines:
            self.screen.blit(self.font.render(line, True, (190, 200, 215)), (detail_panel.x + 20, y))
            y += 34

    def draw_pack_summary_page(self):
        self.screen.fill((12, 18, 30))
        self.draw_pack_summary()
        self.screen.blit(self.small.render("ENTER or ESC continue", True, (190, 200, 215)), (36, 56))

    def draw_fantasy_sbc_page(self):
        self.screen.fill((14, 18, 28))
        self.screen.blit(self.big.render("Fantasy SBC Hub", True, WHITE), (34, 22))
        self.screen.blit(self.small.render("UP/DOWN select | ENTER open challenge | ESC back", True, (190, 200, 215)), (36, 56))
        self.screen.blit(self.font.render(f"Spare Cards: {len(self.available_sbc_cards())}", True, WHITE), (930, 28))
        panel = pygame.Rect(40, 96, 1120, 560)
        pygame.draw.rect(self.screen, (22, 28, 40), panel, 0, border_radius=20)
        pygame.draw.rect(self.screen, (70, 86, 122), panel, 2, border_radius=20)
        sbcs = self.fantasy_sbc_catalog()
        row_h = 110
        row_gap = 16
        visible_rows = 4
        total = len(sbcs)
        start = 0
        if total > visible_rows:
            start = max(0, min(self.fantasy_sbc_index - visible_rows + 1, total - visible_rows))
        end = min(total, start + visible_rows)
        row_y = panel.y + 24
        for i in range(start, end):
            sbc = sbcs[i]
            row = pygame.Rect(panel.x + 18, row_y, panel.w - 36, 110)
            bg = (42, 52, 72) if i == self.fantasy_sbc_index else (28, 34, 48)
            pygame.draw.rect(self.screen, bg, row, 0, border_radius=16)
            pygame.draw.rect(self.screen, YELLOW if i == self.fantasy_sbc_index else (86, 98, 126), row, 2, border_radius=16)
            req = ", ".join(f"{count}x {rarity}" for rarity, count in sbc["requirements"])
            if sbc.get("reward_type") == "pack":
                reward = f"{sbc['reward_pack'].title()} Pack"
            elif sbc.get("reward_type") == "pick":
                reward = f"{sbc.get('pick_count', 3)}-Player Pick ({sbc.get('pick_band', 'Elite')})"
            else:
                reward = f"{sbc.get('reward_coins', 0)} Coins"
            status = "Ready" if self.can_complete_sbc(sbc) else "Missing cards"
            self.screen.blit(self.font.render(sbc["name"], True, WHITE), (row.x + 16, row.y + 14))
            self.screen.blit(self.small.render(f"Submit: {req}", True, (212, 220, 232)), (row.x + 16, row.y + 48))
            self.screen.blit(self.small.render(f"Reward: {reward}", True, LIGHT_GREEN), (row.x + 16, row.y + 74))
            self.screen.blit(self.small.render(status, True, YELLOW if status == "Ready" else (220, 170, 170)), (row.right - 120, row.y + 44))
            row_y += row_h + row_gap
        if start > 0:
            self.screen.blit(self.small.render("More above", True, (180, 190, 205)), (panel.right - 110, panel.y + 10))
        if end < total:
            self.screen.blit(self.small.render("More below", True, (180, 190, 205)), (panel.right - 110, panel.bottom - 26))

    def draw_fantasy_sbc_build_page(self):
        self.screen.fill((12, 18, 30))
        self.lineup_rects = {}
        sbc = self.fantasy_sbc_catalog()[self.fantasy_sbc_active]
        self.screen.blit(self.big.render(sbc["name"], True, WHITE), (30, 20))
        self.screen.blit(self.small.render("TAB cycle | ENTER move/remove | SPACE submit | ESC back", True, (190, 200, 215)), (30, 54))

        top_panel = pygame.Rect(30, 90, 1140, 170)
        bench_panel = pygame.Rect(30, 280, 1140, 170)
        reserve_panel = pygame.Rect(30, 470, 1140, 200)
        for panel in (top_panel, bench_panel, reserve_panel):
            pygame.draw.rect(self.screen, (20, 26, 38), panel, 0, border_radius=18)
            pygame.draw.rect(self.screen, (45, 60, 90), panel, 2, border_radius=18)

        req_text = ", ".join(f"{count}x {rarity}" for rarity, count in sbc.get("requirements", []))
        if sbc.get("reward_type") == "pack":
            reward = f"{sbc['reward_pack'].title()} Pack"
        elif sbc.get("reward_type") == "pick":
            reward = f"{sbc.get('pick_count', 3)}-Player Pick ({sbc.get('pick_band', 'Elite')})"
        else:
            reward = f"{sbc.get('reward_coins', 0)} Coins"
        self.screen.blit(self.font.render("Challenge Slots", True, WHITE), (top_panel.x + 14, top_panel.y + 10))
        self.screen.blit(self.small.render(f"Need: {req_text}", True, (210, 220, 232)), (top_panel.x + 14, top_panel.y + 40))
        self.screen.blit(self.small.render(f"Reward: {reward}", True, LIGHT_GREEN), (top_panel.x + 14, top_panel.y + 62))
        status = "Ready to submit" if self.sbc_build_requirements_met() else "Requirements not met"
        self.screen.blit(self.small.render(status, True, YELLOW if self.sbc_build_requirements_met() else (220, 170, 170)), (top_panel.right - 180, top_panel.y + 18))

        slot_w = 92
        slot_h = 112
        gap = 12
        start_x = top_panel.x + 16
        for i, entry in enumerate(self.fantasy_sbc_slots):
            x = start_x + i * (slot_w + gap)
            y = top_panel.y + 88
            slot_rect = pygame.Rect(x, y, slot_w, slot_h)
            selected = self.fantasy_sbc_col == 0 and i == self.fantasy_sbc_idx
            pygame.draw.rect(self.screen, (32, 40, 56), slot_rect, 0, border_radius=14)
            pygame.draw.rect(self.screen, YELLOW if selected else (86, 98, 126), slot_rect, 2, border_radius=14)
            if entry:
                self.draw_squad_card(x, y, slot_w, slot_h, entry, role="SBC", selected=selected)
            else:
                self.screen.blit(self.small.render("EMPTY", True, (180, 190, 205)), (x + 18, y + 44))
                self.lineup_rects[(0, i)] = slot_rect

        self.screen.blit(self.font.render("Bench", True, WHITE), (bench_panel.x + 14, bench_panel.y + 10))
        bench_entries = self.get_sbc_source_list(1)
        bench_visible = 10
        bench_start = 0
        if len(bench_entries) > bench_visible:
            focus = self.fantasy_sbc_idx if self.fantasy_sbc_col == 1 else 0
            bench_start = max(0, min(focus - bench_visible + 1, len(bench_entries) - bench_visible))
        bench_slice = bench_entries[bench_start: bench_start + bench_visible]
        for i, entry in enumerate(bench_slice):
            actual_idx = bench_start + i
            x = bench_panel.x + 16 + i * 108
            y = bench_panel.y + 44
            selected = self.fantasy_sbc_col == 1 and actual_idx == self.fantasy_sbc_idx
            self.draw_squad_card(x, y, 92, 112, entry, role="SUB", selected=selected)
        if bench_start > 0:
            self.screen.blit(self.small.render("More left", True, (180, 190, 205)), (bench_panel.right - 180, bench_panel.y + 14))
        if bench_start + bench_visible < len(bench_entries):
            self.screen.blit(self.small.render("More right", True, (180, 190, 205)), (bench_panel.right - 88, bench_panel.y + 14))

        self.screen.blit(self.font.render("Reserves", True, WHITE), (reserve_panel.x + 14, reserve_panel.y + 10))
        reserve_entries = self.get_sbc_source_list(2)
        rows = 2
        cols = 10
        reserve_visible = rows * cols
        reserve_start = 0
        if len(reserve_entries) > reserve_visible:
            focus = self.fantasy_sbc_idx if self.fantasy_sbc_col == 2 else 0
            reserve_start = max(0, min(focus - reserve_visible + 1, len(reserve_entries) - reserve_visible))
        reserve_slice = reserve_entries[reserve_start: reserve_start + reserve_visible]
        for i, entry in enumerate(reserve_slice):
            actual_idx = reserve_start + i
            row = i // cols
            col = i % cols
            x = reserve_panel.x + 16 + col * 108
            y = reserve_panel.y + 44 + row * 126
            selected = self.fantasy_sbc_col == 2 and actual_idx == self.fantasy_sbc_idx
            self.draw_squad_card(x, y, 92, 112, entry, role="RES", selected=selected)
        if reserve_start > 0:
            self.screen.blit(self.small.render("More above", True, (180, 190, 205)), (reserve_panel.right - 180, reserve_panel.y + 14))
        if reserve_start + reserve_visible < len(reserve_entries):
            self.screen.blit(self.small.render("More below", True, (180, 190, 205)), (reserve_panel.right - 88, reserve_panel.y + 14))

    def draw_fantasy_objectives_page(self):
        self.screen.fill((14, 18, 28))
        self.screen.blit(self.big.render("Fantasy Objectives", True, WHITE), (34, 22))
        self.screen.blit(self.small.render("UP/DOWN select | ENTER claim reward | ESC back", True, (190, 200, 215)), (36, 56))
        self.screen.blit(self.font.render(f"Season XP: {self.fantasy_season_xp}", True, WHITE), (940, 28))

        sections = [("Daily", "daily"), ("Weekly", "weekly"), ("Milestones", "milestones")]
        selected_key, selected_offset = "daily", self.fantasy_objective_index
        running = 0
        base_y = 96
        for title, key in sections:
            panel = pygame.Rect(40, base_y, 1120, 150)
            pygame.draw.rect(self.screen, (22, 28, 40), panel, 0, border_radius=18)
            pygame.draw.rect(self.screen, (70, 86, 122), panel, 2, border_radius=18)
            self.screen.blit(self.font.render(title, True, WHITE), (panel.x + 14, panel.y + 10))
            group = self.fantasy_objectives.get(key, [])
            y = panel.y + 44
            for idx, obj in enumerate(group):
                absolute_idx = running + idx
                selected = absolute_idx == self.fantasy_objective_index
                color = YELLOW if selected else WHITE
                progress = obj.get("progress", 0)
                target = obj.get("target", 0)
                if obj.get("reverse"):
                    prog_text = f"{progress} / {target} tier"
                    complete = progress <= target
                else:
                    prog_text = f"{progress}/{target}"
                    complete = progress >= target
                reward = f"{obj.get('pack_id', 'gold').title()} Pack" if obj.get("reward_type") == "pack" else f"{obj.get('reward', 0)} coins"
                status = "Claimed" if obj.get("claimed") else "Ready" if complete else "In Progress"
                self.screen.blit(self.small.render(f"{obj['label']}  [{prog_text}]  Reward: {reward}  {status}", True, color), (panel.x + 16, y))
                y += 30
            running += len(group)
            base_y += 170

        track_panel = pygame.Rect(40, 620, 1120, 70)
        pygame.draw.rect(self.screen, (22, 28, 40), track_panel, 0, border_radius=16)
        pygame.draw.rect(self.screen, (70, 86, 122), track_panel, 2, border_radius=16)
        self.screen.blit(self.small.render("Season Track", True, WHITE), (track_panel.x + 14, track_panel.y + 8))
        for tier in range(1, 6):
            tier_x = track_panel.x + 22 + (tier - 1) * 210
            needed = tier * 100
            active = self.fantasy_season_xp >= needed
            claimed = self.fantasy_season_claimed >= tier
            color = LIGHT_GREEN if active and not claimed else (200, 200, 210) if claimed else (90, 100, 120)
            pygame.draw.rect(self.screen, color, (tier_x, track_panel.y + 30, 180, 18), 0, border_radius=8)
            label = f"T{tier} {'Claimed' if claimed else 'Ready' if active else f'{needed} XP'}"
            self.screen.blit(self.small.render(label, True, WHITE), (tier_x, track_panel.y + 50))

    def draw_fantasy_collection_page(self):
        self.screen.fill((14, 18, 28))
        self.screen.blit(self.big.render("Fantasy Collection", True, WHITE), (34, 22))
        self.screen.blit(self.small.render("ARROWS move | G filter | TAB sort | F favorite | ESC back", True, (190, 200, 215)), (36, 56))
        cards = self.filtered_collection_cards()
        if not cards:
            self.screen.blit(self.font.render("No cards match the current filter", True, WHITE), (40, 120))
            return
        self.fantasy_collection_index = max(0, min(self.fantasy_collection_index, len(cards) - 1))
        selected = cards[self.fantasy_collection_index]

        grid_panel = pygame.Rect(40, 96, 710, 580)
        detail_panel = pygame.Rect(780, 96, 380, 580)
        pygame.draw.rect(self.screen, (22, 28, 40), grid_panel, 0, border_radius=18)
        pygame.draw.rect(self.screen, (70, 86, 122), grid_panel, 2, border_radius=18)
        pygame.draw.rect(self.screen, (22, 28, 40), detail_panel, 0, border_radius=18)
        pygame.draw.rect(self.screen, (70, 86, 122), detail_panel, 2, border_radius=18)
        filter_text = f"Filter: {self.collection_filter_options()[self.fantasy_collection_filter]}"
        sort_text = f"Sort: {self.collection_sort_options()[self.fantasy_collection_sort]}"
        self.screen.blit(self.small.render(filter_text, True, (210, 220, 235)), (grid_panel.x + 18, grid_panel.y - 26))
        self.screen.blit(self.small.render(sort_text, True, (210, 220, 235)), (grid_panel.x + 220, grid_panel.y - 26))
        self.screen.blit(self.small.render(f"{len(cards)} shown / {len(self.fantasy_roster)} owned", True, (210, 220, 235)), (grid_panel.right - 170, grid_panel.y - 26))

        cols = 4
        card_w = 154
        card_h = 220
        gap_x = 14
        gap_y = 14
        visible_rows = 2
        row = self.fantasy_collection_index // cols
        max_row = max(0, math.ceil(len(cards) / cols) - visible_rows)
        start_row = max(0, min(row - 1, max_row))
        start = start_row * cols
        end = min(len(cards), start + cols * visible_rows)
        for draw_idx, i in enumerate(range(start, end)):
            row = draw_idx // cols
            col = draw_idx % cols
            x = grid_panel.x + 18 + col * (card_w + gap_x)
            y = grid_panel.y + 18 + row * (card_h + gap_y)
            self.draw_card(x, y, card_w, card_h, cards[i])
            if i == self.fantasy_collection_index:
                pygame.draw.rect(self.screen, YELLOW, (x - 4, y - 4, card_w + 8, card_h + 8), 3, border_radius=18)
        if start > 0:
            self.screen.blit(self.small.render("More above", True, (190, 200, 215)), (grid_panel.x + 18, grid_panel.bottom - 30))
        if end < len(cards):
            self.screen.blit(self.small.render("More below", True, (190, 200, 215)), (grid_panel.right - 110, grid_panel.bottom - 30))

        self.draw_card(detail_panel.x + 92, detail_panel.y + 24, 190, 290, selected)
        traits = ", ".join(selected.get("traits", [])) or "None"
        fav_text = "Yes" if self.is_favorite_card(selected) else "No"
        lines = [
            f"Name: {selected['name']}",
            f"Club: {selected['team']}",
            f"League: {selected.get('league', get_team_league(selected.get('team', '')))}",
            f"OVR: {selected['rating']}",
            f"Rarity: {selected.get('rarity', 'Base')}",
            f"Promo: {selected.get('promo', 'Base')}",
            f"Position: {selected.get('position', 'ST')}",
            f"Favorite: {fav_text}",
            f"Skills: {traits}",
        ]
        y = detail_panel.y + 340
        for line in lines:
            self.screen.blit(self.small.render(line[:40], True, WHITE), (detail_panel.x + 18, y))
            y += 28

    def draw_fantasy_market_page(self):
        self.screen.fill((14, 18, 28))
        self.screen.blit(self.big.render("Fantasy Market", True, WHITE), (34, 22))
        self.screen.blit(self.small.render("UP/DOWN browse | ENTER buy | R refresh | ESC back", True, (190, 200, 215)), (36, 56))
        self.screen.blit(self.font.render(f"Coins: {self.fantasy_coins}", True, WHITE), (1000, 28))
        if not self.fantasy_market_offers:
            self.screen.blit(self.font.render("No market offers available", True, WHITE), (40, 120))
            return
        self.fantasy_market_index = max(0, min(self.fantasy_market_index, len(self.fantasy_market_offers) - 1))
        selected = self.fantasy_market_offers[self.fantasy_market_index]
        list_panel = pygame.Rect(40, 96, 420, 580)
        detail_panel = pygame.Rect(500, 96, 660, 580)
        pygame.draw.rect(self.screen, (22, 28, 40), list_panel, 0, border_radius=18)
        pygame.draw.rect(self.screen, (70, 86, 122), list_panel, 2, border_radius=18)
        pygame.draw.rect(self.screen, (22, 28, 40), detail_panel, 0, border_radius=18)
        pygame.draw.rect(self.screen, (70, 86, 122), detail_panel, 2, border_radius=18)
        start = max(0, min(self.fantasy_market_index - 6, max(0, len(self.fantasy_market_offers) - 12)))
        y = list_panel.y + 18
        for i in range(start, min(len(self.fantasy_market_offers), start + 12)):
            card = self.fantasy_market_offers[i]
            row = pygame.Rect(list_panel.x + 12, y, list_panel.w - 24, 38)
            if i == self.fantasy_market_index:
                pygame.draw.rect(self.screen, (70, 82, 110), row, 0, border_radius=10)
            elif i % 2 == 0:
                pygame.draw.rect(self.screen, (28, 34, 46), row, 0, border_radius=10)
            line = f"{card['name'][:18]:<18} {card.get('rarity','Base')[:8]:<8} {card['rating']:>3}  {card.get('market_price', 0)}c"
            self.screen.blit(self.small.render(line, True, WHITE), (row.x + 10, row.y + 11))
            y += 44
        self.draw_card(detail_panel.x + 34, detail_panel.y + 26, 240, 340, selected)
        traits = ", ".join(selected.get("traits", [])) or "None"
        details = [
            f"Name: {selected['name']}",
            f"Club: {selected['team']}",
            f"League: {selected.get('league', get_team_league(selected.get('team', '')))}",
            f"OVR: {selected['rating']}",
            f"Rarity: {selected.get('rarity', 'Base')}",
            f"Promo: {selected.get('promo', 'Base')}",
            f"Position: {selected.get('position', 'ST')}",
            f"Price: {selected.get('market_price', 0)} coins",
            f"Skills: {traits}",
        ]
        dy = detail_panel.y + 40
        for line in details:
            self.screen.blit(self.font.render(line[:42], True, WHITE), (detail_panel.x + 320, dy))
            dy += 42

    def draw_fantasy_evolutions_page(self):
        self.screen.fill((14, 18, 28))
        self.screen.blit(self.big.render("Fantasy Evolutions", True, WHITE), (34, 22))
        self.screen.blit(self.small.render("UP/DOWN browse | LEFT/RIGHT path | ENTER evolve | ESC back", True, (190, 200, 215)), (36, 56))
        self.screen.blit(self.font.render(f"Coins: {self.fantasy_coins}", True, WHITE), (980, 28))
        cards = sorted(self.fantasy_roster, key=lambda c: (-c.get("rating", 0), c.get("name", "")))
        if not cards:
            self.screen.blit(self.font.render("No cards available", True, WHITE), (40, 120))
            return
        self.fantasy_evolution_index = max(0, min(self.fantasy_evolution_index, len(cards) - 1))
        selected = cards[self.fantasy_evolution_index]
        paths = self.fantasy_evolution_paths(selected)
        self.fantasy_evolution_choice = max(0, min(self.fantasy_evolution_choice, len(paths) - 1))

        list_panel = pygame.Rect(40, 96, 330, 580)
        card_panel = pygame.Rect(400, 96, 310, 580)
        path_panel = pygame.Rect(740, 96, 420, 580)
        for panel in (list_panel, card_panel, path_panel):
            pygame.draw.rect(self.screen, (22, 28, 40), panel, 0, border_radius=18)
            pygame.draw.rect(self.screen, (70, 86, 122), panel, 2, border_radius=18)

        start = max(0, min(self.fantasy_evolution_index - 5, max(0, len(cards) - 10)))
        y = list_panel.y + 16
        for i in range(start, min(len(cards), start + 10)):
            card = cards[i]
            row = pygame.Rect(list_panel.x + 12, y, list_panel.w - 24, 48)
            is_selected = i == self.fantasy_evolution_index
            pygame.draw.rect(self.screen, (42, 52, 72) if is_selected else (28, 34, 48), row, 0, border_radius=12)
            pygame.draw.rect(self.screen, YELLOW if is_selected else (86, 98, 126), row, 2, border_radius=12)
            text = f"{card['name'][:14]:<14} {card['rating']:>3}  Evo {card.get('evo_level', 0)}"
            self.screen.blit(self.small.render(text, True, WHITE), (row.x + 10, row.y + 15))
            y += 54

        self.draw_card(card_panel.x + 38, card_panel.y + 26, 234, 330, selected)
        stats = [
            f"Position: {selected.get('position', 'ST')}",
            f"Rarity: {selected.get('rarity', 'Base')}",
            f"Goals: {self.get_player_stat(selected['name'], 'goals')}",
            f"Assists: {self.get_player_stat(selected['name'], 'assists')}",
            f"Tackles: {self.get_player_stat(selected['name'], 'tackles')}",
            f"Clean Sheets: {self.get_player_stat(selected['name'], 'clean_sheets')}",
        ]
        y = card_panel.y + 382
        for line in stats:
            self.screen.blit(self.small.render(line, True, WHITE), (card_panel.x + 18, y))
            y += 28

        self.screen.blit(self.font.render("Upgrade Paths", True, WHITE), (path_panel.x + 14, path_panel.y + 14))
        y = path_panel.y + 56
        for idx, path in enumerate(paths):
            row = pygame.Rect(path_panel.x + 14, y, path_panel.w - 28, 152)
            is_selected = idx == self.fantasy_evolution_choice
            ready = path["ready"] and self.fantasy_coins >= path["cost"] and selected.get("evo_level", 0) < 5
            pygame.draw.rect(self.screen, (42, 52, 72) if is_selected else (28, 34, 48), row, 0, border_radius=16)
            pygame.draw.rect(self.screen, YELLOW if is_selected else (86, 98, 126), row, 2, border_radius=16)
            self.screen.blit(self.font.render(path["name"], True, WHITE), (row.x + 14, row.y + 12))
            self.screen.blit(self.small.render(f"Upgrade: +{path['delta']} OVR", True, LIGHT_GREEN), (row.x + 14, row.y + 46))
            self.screen.blit(self.small.render(f"Cost: {path['cost']} coins", True, WHITE), (row.x + 14, row.y + 70))
            self.screen.blit(self.small.render(f"Needs: {path['need_label']}", True, (212, 220, 232)), (row.x + 14, row.y + 96))
            self.screen.blit(self.small.render(f"Trait: {path['trait']}", True, (190, 200, 215)), (row.x + 14, row.y + 120))
            status = "Ready" if ready else "Need coins" if path["ready"] and self.fantasy_coins < path["cost"] else "Maxed" if selected.get("evo_level", 0) >= 5 else "Locked"
            color = LIGHT_GREEN if status == "Ready" else YELLOW if status == "Need coins" else (220, 170, 170)
            self.screen.blit(self.small.render(status, True, color), (row.right - 84, row.y + 14))
            y += 166

    def draw_fantasy_competitions_page(self):
        self.screen.fill((14, 18, 28))
        self.screen.blit(self.big.render("Fantasy Competitions", True, WHITE), (34, 22))
        self.screen.blit(self.small.render("UP/DOWN select | ENTER choose | D open draft | ESC back", True, (190, 200, 215)), (36, 56))
        panel = pygame.Rect(40, 96, 1120, 560)
        pygame.draw.rect(self.screen, (22, 28, 40), panel, 0, border_radius=20)
        pygame.draw.rect(self.screen, (70, 86, 122), panel, 2, border_radius=20)
        menu = self.fantasy_competition_menu()
        comps = self.fantasy_competitions or {}
        row_h = 112
        row_gap = 16
        visible_rows = 4
        total = len(menu)
        start = 0
        if total > visible_rows:
            start = max(0, min(self.fantasy_competition_index - visible_rows + 1, total - visible_rows))
        end = min(total, start + visible_rows)
        row_y = panel.y + 26
        for i in range(start, end):
            key, title, desc = menu[i]
            row = pygame.Rect(panel.x + 18, row_y, panel.w - 36, 112)
            bg = (42, 52, 72) if i == self.fantasy_competition_index else (28, 34, 48)
            pygame.draw.rect(self.screen, bg, row, 0, border_radius=16)
            pygame.draw.rect(self.screen, YELLOW if key == self.fantasy_active_competition else (86, 98, 126), row, 2, border_radius=16)
            comp = comps.get(key, {})
            if key == "division":
                reward_text = f"Reward: {comp.get('reward', 120)} coins on promotion"
            elif key == "ladder":
                reward_text = self.reward_summary(comp.get("reward_type", "hybrid"), comp.get("reward_pack", "elite"), comp.get("reward_coins", 160))
            elif key == "online":
                entry = self.online_division_data.get("entry", {})
                reward_text = f"Reward ready: {entry.get('reward_coins', 0)} coins | Tier {entry.get('division_tier', 10)}"
            elif key == "cup":
                reward_text = f"Reward: {comp.get('reward_pack', 'elite').title()} Pack on cup win"
            elif key == "weekend":
                reward_text = f"Reward: {comp.get('reward_pack', 'gold').title()} Pack + {comp.get('reward_coins', 80)} coins"
            elif key == "draft":
                reward_text = self.reward_summary(comp.get("reward_type", "bundle"), comp.get("reward_pack", "omega"), comp.get("reward_coins", 260), comp.get("pick_band", "Legend"), comp.get("pick_count", 3))
            elif key == "champions":
                reward_text = f"Reward: {comp.get('reward_pack', 'transcendent').title()} Pack + {comp.get('reward_coins', 240)} coins"
            else:
                reward_text = "Reward: Featured special player"
            self.screen.blit(self.font.render(title, True, WHITE), (row.x + 16, row.y + 14))
            self.screen.blit(self.small.render(desc, True, (212, 220, 232)), (row.x + 16, row.y + 46))
            self.screen.blit(self.small.render(reward_text, True, LIGHT_GREEN), (row.x + 16, row.y + 74))
            if key == "online":
                entry = self.online_division_data.get("entry", {})
                status_text = f"{entry.get('points', 0)} pts | {entry.get('wins', 0)}W-{entry.get('draws', 0)}D-{entry.get('losses', 0)}L"
                self.screen.blit(self.small.render(status_text, True, (190, 200, 215)), (row.x + 16, row.y + 92))
            elif key == "ladder":
                status_text = f"Week {comp.get('week', 1)} | {comp.get('points', 0)} pts | Streak {comp.get('streak', 0)}"
                self.screen.blit(self.small.render(status_text, True, (190, 200, 215)), (row.x + 16, row.y + 92))
            elif key == "draft":
                run_text = f"{comp.get('wins', 0)}W-{comp.get('losses', 0)}L | {'Active draft squad' if self.fantasy_draft_active else 'Build a fresh squad'}"
                self.screen.blit(self.small.render(run_text, True, (190, 200, 215)), (row.x + 16, row.y + 92))
            row_y += row_h + row_gap
        if start > 0:
            self.screen.blit(self.small.render("More above", True, (180, 190, 205)), (panel.right - 110, panel.y + 10))
        if end < total:
            self.screen.blit(self.small.render("More below", True, (180, 190, 205)), (panel.right - 110, panel.bottom - 26))

    def draw_fantasy_club_page(self):
        self.screen.fill((12, 18, 30))
        self.ensure_fantasy_club_defaults()
        self.screen.blit(self.big.render("Fantasy Club Hub", True, WHITE), (34, 22))
        self.screen.blit(self.small.render("UP/DOWN select | LEFT/RIGHT tune | S export squad | ENTER import | ESC back", True, (190, 200, 215)), (36, 56))

        left = pygame.Rect(34, 96, 420, 570)
        center = pygame.Rect(476, 96, 300, 570)
        right = pygame.Rect(798, 96, 368, 570)
        for panel in (left, center, right):
            pygame.draw.rect(self.screen, (22, 28, 40), panel, 0, border_radius=20)
            pygame.draw.rect(self.screen, (70, 86, 122), panel, 2, border_radius=20)

        rows = [
            ("Badge", self.fantasy_club_badge_name()),
            ("Primary", FANTASY_CLUB_PALETTES[self.fantasy_club_custom["primary"]][0]),
            ("Secondary", FANTASY_CLUB_PALETTES[self.fantasy_club_custom["secondary"]][0]),
            ("Stadium", FANTASY_STADIUM_OPTIONS[self.fantasy_club_custom["stadium"]]),
            ("Import Code", self.fantasy_share_input[:26] or "Paste share code"),
        ]
        self.screen.blit(self.font.render("Club Identity", True, WHITE), (left.x + 16, left.y + 18))
        y = left.y + 64
        for idx, (label, value) in enumerate(rows):
            row = pygame.Rect(left.x + 14, y, left.w - 28, 68)
            active = idx == self.fantasy_club_cursor
            pygame.draw.rect(self.screen, (42, 52, 72) if active else (28, 34, 48), row, 0, border_radius=14)
            pygame.draw.rect(self.screen, YELLOW if active else (86, 98, 126), row, 2, border_radius=14)
            self.screen.blit(self.font.render(label, True, WHITE), (row.x + 14, row.y + 10))
            color = WHITE
            if label == "Primary":
                color = self.fantasy_palette_color(self.fantasy_club_custom["primary"])
            elif label == "Secondary":
                color = self.fantasy_palette_color(self.fantasy_club_custom["secondary"])
            self.screen.blit(self.small.render(str(value), True, color), (row.x + 14, row.y + 40))
            y += 82

        self.apply_fantasy_club_identity()
        preview = {
            "name": self.fantasy_team_name.strip() or "Fantasy FC",
            "rating": max(65, self.average_fantasy_rating()),
            "team": self.user_team or self.fantasy_team_name.strip() or "Fantasy FC",
            "league": "Legends League",
            "position": "ST",
            "rarity": "Elite",
            "promo": "Base",
            "nation": self.fantasy_club_badge_name(),
            "form_boost": 0,
            "evo_level": 0,
        }
        self.screen.blit(self.font.render("Club Preview", True, WHITE), (center.x + 18, center.y + 18))
        self.draw_card(center.x + 28, center.y + 60, 244, 350, preview)
        self.screen.blit(self.small.render(f"Badge identity: {self.fantasy_club_badge_name()}", True, (190, 200, 215)), (center.x + 22, center.y + 438))
        self.screen.blit(self.small.render(f"Stadium: {FANTASY_STADIUM_OPTIONS[self.fantasy_club_custom['stadium']]}", True, (190, 200, 215)), (center.x + 22, center.y + 468))
        self.screen.blit(self.small.render(f"Current chemistry: {self.fantasy_chemistry_total}/33", True, WHITE), (center.x + 22, center.y + 498))
        self.screen.blit(self.small.render(f"Starters ready: {min(11, len(self.user_starting))}/11", True, WHITE), (center.x + 22, center.y + 528))

        self.screen.blit(self.font.render("Squad Sharing", True, WHITE), (right.x + 16, right.y + 18))
        code = self.fantasy_share_input or "Press S to generate a squad code"
        wrapped = [code[i:i + 28] for i in range(0, min(len(code), 112), 28)] or [code]
        y = right.y + 60
        self.screen.blit(self.small.render("Share this code with friends to mirror your lineup and club style.", True, (190, 200, 215)), (right.x + 16, y))
        y += 42
        share_box = pygame.Rect(right.x + 16, y, right.w - 32, 140)
        pygame.draw.rect(self.screen, (18, 24, 34), share_box, 0, border_radius=14)
        pygame.draw.rect(self.screen, (86, 98, 126), share_box, 2, border_radius=14)
        line_y = share_box.y + 16
        for line in wrapped[:4]:
            self.screen.blit(self.small.render(line, True, WHITE), (share_box.x + 12, line_y))
            line_y += 28
        y = share_box.bottom + 18
        starters = self.user_starting[:11]
        self.screen.blit(self.small.render("Shared lineup preview", True, WHITE), (right.x + 16, y))
        y += 30
        for idx, entry in enumerate(starters[:8]):
            name, _, rating = entry
            self.screen.blit(self.small.render(f"{idx + 1}. {name[:18]}  {rating}", True, (212, 220, 232)), (right.x + 16, y))
            y += 24
        message = self.fantasy_share_message or "Export copies your lineup order. Import applies matching owned cards."
        self.screen.blit(self.small.render(message[:64], True, YELLOW), (right.x + 16, right.bottom - 34))

    def draw_online_divisions_page(self):
        self.screen.fill((10, 16, 28))
        self.screen.blit(self.big.render("Online Divisions", True, WHITE), (34, 22))
        hint = "S submit squad | SPACE play async match | C claim reward | R refresh | UP/DOWN leaderboard | ESC back"
        self.screen.blit(self.small.render(hint, True, (190, 200, 215)), (36, 56))

        entry = self.online_division_data.get("entry", {})
        leaderboard = self.online_division_data.get("leaderboard", [])

        left = pygame.Rect(34, 96, 470, 590)
        right = pygame.Rect(528, 96, 638, 590)
        for panel in (left, right):
            pygame.draw.rect(self.screen, (22, 28, 40), panel, 0, border_radius=20)
            pygame.draw.rect(self.screen, (70, 86, 122), panel, 2, border_radius=20)

        self.screen.blit(self.font.render("Your Division Entry", True, WHITE), (left.x + 18, left.y + 18))
        info_lines = [
            f"Team: {entry.get('squad_name', self.fantasy_team_name or 'Unsubmitted')}",
            f"Division: {entry.get('division_tier', 10)}",
            f"Submitted: {'Yes' if entry.get('submitted') else 'No'}",
            f"Squad Rating: {entry.get('squad_rating', 0)}",
            f"Record: {entry.get('wins', 0)}W-{entry.get('draws', 0)}D-{entry.get('losses', 0)}L",
            f"Points: {entry.get('points', 0)}",
            f"Goal Difference: {entry.get('goal_difference', 0)}",
            f"Cycle: {entry.get('cycle_played', 0)}/5 matches | {entry.get('cycle_points', 0)} pts",
            f"Reward Coins: {entry.get('reward_coins', 0)}",
            f"Captain: {entry.get('captain', 'None')}",
        ]
        y = left.y + 58
        for line in info_lines:
            self.screen.blit(self.small.render(line[:44], True, (220, 228, 236)), (left.x + 18, y))
            y += 34

        self.screen.blit(self.font.render("Recent Results", True, WHITE), (left.x + 18, y + 8))
        y += 44
        recent = entry.get("recent_results", [])
        if not recent:
            self.screen.blit(self.small.render("No online matches played yet", True, (190, 200, 215)), (left.x + 18, y))
        else:
            for result in recent[:5]:
                line = f"{result.get('result', '-')} vs {result.get('opponent', 'opponent')}  {result.get('score', '0-0')}"
                self.screen.blit(self.small.render(line[:44], True, (220, 228, 236)), (left.x + 18, y))
                y += 28

        self.screen.blit(self.font.render("Division Leaderboard", True, WHITE), (right.x + 18, right.y + 18))
        self.screen.blit(self.small.render("Current tier only. Submit your squad to appear here.", True, (190, 200, 215)), (right.x + 18, right.y + 50))
        list_y = right.y + 92
        if not leaderboard:
            self.screen.blit(self.small.render("No submitted squads in this division yet", True, (190, 200, 215)), (right.x + 18, list_y))
        else:
            self.online_division_index = max(0, min(self.online_division_index, len(leaderboard) - 1))
            start = max(0, min(self.online_division_index - 5, max(0, len(leaderboard) - 10)))
            shown = leaderboard[start:start + 10]
            for idx, row in enumerate(shown, start=start):
                item = pygame.Rect(right.x + 14, list_y, right.w - 28, 46)
                active = idx == self.online_division_index
                pygame.draw.rect(self.screen, (34, 42, 58), item, 0, border_radius=12)
                pygame.draw.rect(self.screen, YELLOW if active else (86, 98, 126), item, 2, border_radius=12)
                label = f"{idx + 1:>2}. {row.get('username', '')[:14]:<14} T{row.get('division_tier', 10)}  {row.get('points', 0):>2} pts  GD {row.get('goal_difference', 0):>3}  OVR {row.get('squad_rating', 0):>3}"
                self.screen.blit(self.small.render(label, True, WHITE), (item.x + 12, item.y + 15))
                list_y += 52

        if self.online_division_message:
            self.screen.blit(self.small.render(self.online_division_message[:120], True, YELLOW), (36, HEIGHT - 28))

    def draw_online_tournament_page(self):
        self.screen.fill((10, 16, 28))
        self.screen.blit(self.big.render("Online Tournament", True, WHITE), (34, 22))
        hint = "SPACE play match | B submit squad | C claim reward | R refresh | UP/DOWN leaderboard | ESC back"
        self.screen.blit(self.small.render(hint, True, (190, 200, 215)), (36, 56))

        entry = self.online_tournament_data.get("entry", {})
        leaderboard = self.online_tournament_data.get("leaderboard", [])

        panel = pygame.Rect(34, 96, 470, 574)
        pygame.draw.rect(self.screen, (22, 28, 40), panel, 0, border_radius=20)
        pygame.draw.rect(self.screen, (70, 86, 122), panel, 2, border_radius=20)
        self.screen.blit(self.font.render("Your Tournament Entry", True, WHITE), (panel.x + 18, panel.y + 18))
        lines = [
            f"Round: {entry.get('round', 1)}",
            f"Record: {entry.get('wins', 0)}W-{entry.get('losses', 0)}L",
            f"Matches played: {entry.get('matches_played', 0)}",
            f"Queued reward: {entry.get('reward_coins', 0)} coins",
        ]
        y = panel.y + 58
        for line in lines:
            self.screen.blit(self.small.render(line, True, (220, 228, 236)), (panel.x + 18, y))
            y += 34
        if leaderboard:
            self.screen.blit(self.font.render("Leaderboard snapshot", True, WHITE), (panel.x + 18, y + 8))
            y += 34
            start = max(0, min(self.online_tournament_index - 4, max(0, len(leaderboard) - 8)))
            shown = leaderboard[start : start + 8]
            for idx, row in enumerate(shown, start=start):
                item = pygame.Rect(panel.x + 18, y, panel.w - 36, 40)
                active = idx == self.online_tournament_index
                pygame.draw.rect(self.screen, (34, 42, 58), item, 0, border_radius=10)
                pygame.draw.rect(self.screen, YELLOW if active else (86, 98, 126), item, 2, border_radius=10)
                label = f"{idx + 1:>2}. {row.get('username', '')[:16]:<16} R{row.get('round', 1)} {row.get('wins', 0)}W-{row.get('losses', 0)}L"
                self.screen.blit(self.small.render(label, True, WHITE), (item.x + 12, item.y + 12))
                y += 48
        else:
            self.screen.blit(self.small.render("No tournament data yet", True, (190, 200, 215)), (panel.x + 18, y))

        if self.online_tournament_message:
            self.screen.blit(self.small.render(self.online_tournament_message[:120], True, YELLOW), (36, HEIGHT - 28))

    def draw_fantasy_draft_page(self):
        self.screen.fill((10, 14, 24))
        self.screen.blit(self.big.render("Fantasy Draft", True, WHITE), (34, 22))
        self.screen.blit(self.small.render("LEFT/RIGHT choose | ENTER draft player | ESC back", True, (190, 200, 215)), (36, 56))
        self.screen.blit(self.font.render(f"Round {min(self.fantasy_draft_round + 1, 15)}/15", True, WHITE), (970, 28))

        info = pygame.Rect(40, 96, 1120, 160)
        pygame.draw.rect(self.screen, (22, 28, 40), info, 0, border_radius=18)
        pygame.draw.rect(self.screen, (70, 86, 122), info, 2, border_radius=18)
        self.screen.blit(self.font.render("Drafted So Far", True, WHITE), (info.x + 16, info.y + 14))
        recent = ", ".join(card["name"] for card in self.fantasy_draft_roster[-8:]) or "No picks yet"
        self.screen.blit(self.small.render(recent[:140], True, (212, 220, 232)), (info.x + 16, info.y + 46))
        self.screen.blit(self.small.render("Finish 15 picks to lock a temporary squad for the Draft Run competition.", True, (190, 200, 215)), (info.x + 16, info.y + 76))
        if self.fantasy_draft_options:
            floor = self.draft_round_floor(self.fantasy_draft_round)
            self.screen.blit(self.small.render(f"Current round floor: {floor}+ OVR", True, LIGHT_GREEN), (info.x + 16, info.y + 104))

        if not self.fantasy_draft_options:
            self.screen.blit(self.font.render("No draft options available", True, WHITE), (60, 320))
            return

        for i, card in enumerate(self.fantasy_draft_options):
            x = 92 + i * 356
            y = 292
            self.draw_card(x, y, 240, 330, card)
            if i == self.fantasy_draft_index:
                pygame.draw.rect(self.screen, YELLOW, (x - 6, y - 6, 252, 342), 3, border_radius=18)
            meta_line = f"{card.get('league', get_team_league(card.get('team', '')))} | {card.get('position', 'ST')}"
            self.screen.blit(self.small.render(meta_line[:38], True, (214, 222, 236)), (x + 18, y + 340))

    def draw_fantasy_champions_bracket_page(self):
        self.screen.fill((8, 14, 30))
        self.screen.blit(self.big.render("Champions Clash Bracket", True, WHITE), (30, 18))
        self.screen.blit(self.small.render("ESC/K back | Full knockout bracket for the current Champions run", True, (196, 206, 220)), (32, 54))

        if self.fantasy_active_competition != "champions":
            self.screen.blit(self.font.render("Bracket available only while Champions Clash is active", True, WHITE), (40, 120))
            return

        panel = pygame.Rect(24, 86, WIDTH - 48, HEIGHT - 120)
        pygame.draw.rect(self.screen, (16, 24, 44), panel, 0, border_radius=24)
        pygame.draw.rect(self.screen, (80, 106, 166), panel, 2, border_radius=24)

        champs = self.fantasy_competitions.get("champions", {})
        pairings = champs.get("pairings", [[], [], [], []])
        winners = champs.get("winners", [[], [], [], []])
        stages = champs.get("bracket", ["Round of 16", "Quarter Final", "Semi Final", "Final", "Champions"])
        active_round = champs.get("round", 0)
        champion = champs.get("champion")

        self.screen.blit(self.font.render(f"Stage: {stages[min(active_round, len(stages) - 1)]}", True, WHITE), (panel.x + 24, panel.y + 18))
        reward_text = f"Reward: {champs.get('reward_pack', 'transcendent').title()} Pack + {champs.get('reward_coins', 240)} coins"
        self.screen.blit(self.small.render(reward_text, True, LIGHT_GREEN), (panel.x + 24, panel.y + 50))

        center_x = panel.centerx
        title_y = panel.y + 94
        round_titles = [
            ("Round of 16", panel.x + 64),
            ("Quarter Final", panel.x + 252),
            ("Semi Final", panel.x + 438),
            ("Final", center_x - 20),
            ("Semi Final", panel.right - 562),
            ("Quarter Final", panel.right - 374),
            ("Round of 16", panel.right - 186),
        ]
        for title, x in round_titles:
            self.screen.blit(self.small.render(title, True, (212, 220, 232)), (x, title_y))

        left_x = [panel.x + 34, panel.x + 222, panel.x + 408]
        right_x = [panel.right - 168, panel.right - 356, panel.right - 542]
        y_left = {
            0: [panel.y + 132, panel.y + 214, panel.y + 296, panel.y + 378],
            1: [panel.y + 173, panel.y + 337],
            2: [panel.y + 255],
        }
        y_right = {
            0: [panel.y + 132, panel.y + 214, panel.y + 296, panel.y + 378],
            1: [panel.y + 173, panel.y + 337],
            2: [panel.y + 255],
        }

        def draw_match_box(x, y, pair, winner, highlight=False):
            box = pygame.Rect(x, y, 134, 54)
            top = pygame.Rect(box.x, box.y, box.w, 24)
            bottom = pygame.Rect(box.x, box.y + 28, box.w, 24)
            border = YELLOW if highlight else (90, 108, 144)
            top_color = (64, 154, 118) if winner == pair[0] else (34, 42, 60)
            bottom_color = (64, 154, 118) if winner == pair[1] else (34, 42, 60)
            pygame.draw.rect(self.screen, top_color, top, 0, border_radius=10)
            pygame.draw.rect(self.screen, bottom_color, bottom, 0, border_radius=10)
            pygame.draw.rect(self.screen, border, top, 2, border_radius=10)
            pygame.draw.rect(self.screen, border, bottom, 2, border_radius=10)
            self.screen.blit(self.small.render(pair[0][:15], True, WHITE), (top.x + 8, top.y + 4))
            self.screen.blit(self.small.render(pair[1][:15], True, WHITE), (bottom.x + 8, bottom.y + 4))
            return box

        def draw_round(round_idx, x_positions, y_map, reverse=False):
            round_pairs = pairings[round_idx] if round_idx < len(pairings) else []
            round_winners = winners[round_idx] if round_idx < len(winners) else []
            if round_idx == 0:
                indices = range(0, 4) if not reverse else range(4, 8)
            elif round_idx == 1:
                indices = range(0, 2) if not reverse else range(2, 4)
            else:
                indices = range(0, 1) if not reverse else range(1, 2)
            drawn = []
            for idx, src_idx in enumerate(indices):
                if src_idx >= len(round_pairs):
                    continue
                pair = round_pairs[src_idx]
                winner = round_winners[src_idx] if src_idx < len(round_winners) else None
                box = draw_match_box(x_positions[round_idx], y_map[round_idx][idx], pair, winner, highlight=(round_idx == active_round))
                drawn.append(box)
            return drawn

        left_r16 = draw_round(0, left_x, y_left)
        left_qf = draw_round(1, left_x, y_left)
        left_sf = draw_round(2, left_x, y_left)
        right_r16 = draw_round(0, right_x, y_right, reverse=True)
        right_qf = draw_round(1, right_x, y_right, reverse=True)
        right_sf = draw_round(2, right_x, y_right, reverse=True)

        def connect_columns(source_boxes, target_boxes, left_to_right=True):
            line_color = (108, 130, 188)
            for idx, target_box in enumerate(target_boxes):
                src_a = source_boxes[idx * 2]
                src_b = source_boxes[idx * 2 + 1]
                if left_to_right:
                    start_x = src_a.right
                    end_x = target_box.x
                else:
                    start_x = src_a.x
                    end_x = target_box.right
                mid_x = (start_x + end_x) // 2
                y1 = src_a.centery
                y2 = src_b.centery
                ty = target_box.centery
                pygame.draw.line(self.screen, line_color, (start_x, y1), (mid_x, y1), 3)
                pygame.draw.line(self.screen, line_color, (start_x, y2), (mid_x, y2), 3)
                pygame.draw.line(self.screen, line_color, (mid_x, y1), (mid_x, y2), 3)
                pygame.draw.line(self.screen, line_color, (mid_x, ty), (end_x, ty), 3)

        if len(left_r16) >= 4 and len(left_qf) >= 2:
            connect_columns(left_r16, left_qf, True)
        if len(left_qf) >= 2 and len(left_sf) >= 1:
            connect_columns(left_qf, left_sf, True)
        if len(right_r16) >= 4 and len(right_qf) >= 2:
            connect_columns(right_r16, right_qf, False)
        if len(right_qf) >= 2 and len(right_sf) >= 1:
            connect_columns(right_qf, right_sf, False)

        final_pairings = pairings[3] if len(pairings) > 3 else []
        final_winners = winners[3] if len(winners) > 3 else []
        final_box = pygame.Rect(center_x - 92, panel.y + 244, 184, 76)
        pygame.draw.rect(self.screen, (30, 40, 64), final_box, 0, border_radius=16)
        pygame.draw.rect(self.screen, YELLOW if active_round >= 3 else (110, 126, 166), final_box, 2, border_radius=16)
        self.screen.blit(self.font.render("FINAL", True, WHITE), (final_box.x + 54, final_box.y - 32))
        if final_pairings:
            final_pair = final_pairings[0]
            final_winner = final_winners[0] if final_winners else None
            self.screen.blit(self.small.render(final_pair[0][:18], True, LIGHT_GREEN if final_winner == final_pair[0] else WHITE), (final_box.x + 14, final_box.y + 16))
            self.screen.blit(self.small.render(final_pair[1][:18], True, LIGHT_GREEN if final_winner == final_pair[1] else WHITE), (final_box.x + 14, final_box.y + 42))

        if left_sf and final_pairings:
            pygame.draw.line(self.screen, (108, 130, 188), (left_sf[0].right, left_sf[0].centery), (final_box.x, final_box.centery), 3)
        if right_sf and final_pairings:
            pygame.draw.line(self.screen, (108, 130, 188), (right_sf[0].x, right_sf[0].centery), (final_box.right, final_box.centery), 3)

        champion_box = pygame.Rect(center_x - 78, panel.bottom - 128, 156, 68)
        pygame.draw.rect(self.screen, (24, 34, 56), champion_box, 0, border_radius=18)
        pygame.draw.rect(self.screen, LIGHT_GREEN if champion else YELLOW, champion_box, 2, border_radius=18)
        self.screen.blit(self.small.render("Champion", True, (214, 222, 236)), (champion_box.x + 44, champion_box.y + 10))
        self.screen.blit(self.small.render((champion or "TBD")[:18], True, WHITE), (champion_box.x + 16, champion_box.y + 36))

    def draw_fantasy_player_pick_page(self):
        self.screen.fill((12, 18, 30))
        self.screen.blit(self.big.render(self.fantasy_player_pick_title, True, WHITE), (34, 22))
        self.screen.blit(self.small.render("LEFT/RIGHT select | ENTER claim", True, (190, 200, 215)), (36, 56))
        if not self.fantasy_player_pick_options:
            self.screen.blit(self.font.render("No options available", True, WHITE), (40, 120))
            return
        max_visible = 3
        total = len(self.fantasy_player_pick_options)
        if total <= max_visible:
            start = 0
            end = total
        else:
            start = max(0, min(self.fantasy_player_pick_index - 1, total - max_visible))
            end = start + max_visible
        visible = self.fantasy_player_pick_options[start:end]
        y = 160
        card_w = 260
        card_h = 360
        gap = 70
        total_width = len(visible) * card_w + max(0, len(visible) - 1) * gap
        start_x = (WIDTH - total_width) // 2
        for offset, card in enumerate(visible):
            i = start + offset
            x = start_x + offset * (card_w + gap)
            self.draw_card(x, y, card_w, card_h, card)
            if i == self.fantasy_player_pick_index:
                pygame.draw.rect(self.screen, YELLOW, (x - 6, y - 6, card_w + 12, card_h + 12), 3, border_radius=18)
        if start > 0:
            self.screen.blit(self.small.render("< More", True, (190, 200, 215)), (80, y + card_h // 2))
        if end < total:
            self.screen.blit(self.small.render("More >", True, (190, 200, 215)), (WIDTH - 150, y + card_h // 2))

    def apply_fantasy_player_traits(self, player):
        if not player:
            return ()
        if self.game_mode != "FANTASY":
            return ()
        return player.traits or ()

    def draw_walkout_overlay(self):
        if self.walkout_timer <= 0 or not self.last_pack:
            return
        player = max(self.last_pack, key=lambda p: (p["rating"], p.get("rarity", ""), p.get("promo", "")))
        total_time = self.walkout_duration_for_player(player, len(self.last_pack))
        progress = max(0.0, min(total_time, self.walkout_timer))
        elapsed = total_time - progress
        base_color, accent = self.card_theme_colors(player)
        tier = player.get("rarity") or self.card_tier(player["rating"])[0]
        is_signature_walkout = player.get("promo") == "Signature"
        is_fc25_walkout = player.get("rating", 0) >= 86 or player.get("promo", "Base") != "Base"
        is_goat_walkout = tier == "GOAT"
        is_suspense_walkout = tier in ("Icon", "GOAT")
        is_ultra_walkout = tier in ("Omega", "Immortal", "Eternal")
        is_elite_walkout = tier in ("Legend", "Transcendent", "Celestial", "Ascended", "Mythic")
        norm = 0 if total_time <= 0 else max(0.0, min(1.0, elapsed / total_time))
        center_x = WIDTH // 2
        center_y = HEIGHT // 2
        suspense_start = 0.42 if is_goat_walkout else 0.44 if is_suspense_walkout else 0.0
        suspense_end = 0.74 if is_goat_walkout else 0.68 if is_suspense_walkout else 0.0
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((4, 8, 16, 228))
        self.screen.blit(overlay, (0, 0))
        tunnel_rect = pygame.Rect(180, 40, WIDTH - 360, HEIGHT - 80)
        pygame.draw.rect(self.screen, (10, 14, 24), tunnel_rect, 0, border_radius=28)
        pygame.draw.rect(self.screen, accent, tunnel_rect, 2, border_radius=28)

        header_text = "SIGNATURE WALKOUT" if is_signature_walkout else "SPECIAL WALKOUT" if is_suspense_walkout else "ULTRA WALKOUT" if is_ultra_walkout else "ELITE WALKOUT" if is_elite_walkout else "PACK WALKOUT"
        self.screen.blit(self.small.render(header_text, True, accent), (center_x - 74, tunnel_rect.y + 18))

        back_glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for i in range(5):
            alpha = max(0, 72 - i * 9) if is_ultra_walkout else max(0, 52 - i * 9)
            pygame.draw.polygon(
                back_glow,
                (*accent, alpha),
                [
                    (center_x - 220 + i * 22, tunnel_rect.y + 40 + i * 12),
                    (center_x + 220 - i * 22, tunnel_rect.y + 40 + i * 12),
                    (center_x + 70 - i * 10, tunnel_rect.y + 220 - i * 8),
                    (center_x - 70 + i * 10, tunnel_rect.y + 220 - i * 8),
                ],
            )
        self.screen.blit(back_glow, (0, 0))

        if is_ultra_walkout or is_elite_walkout or is_signature_walkout:
            pulse = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pulse_alpha = int((42 if is_ultra_walkout else 34 if is_signature_walkout else 26) * (0.5 + 0.5 * math.sin(elapsed * (4.6 if is_ultra_walkout else 3.8 if is_signature_walkout else 3.2))))
            pygame.draw.circle(pulse, (*accent, max(0, pulse_alpha)), (center_x, center_y), 240 if is_ultra_walkout else 210 if is_signature_walkout else 180, 8)
            pygame.draw.circle(pulse, (*accent, max(0, pulse_alpha // 2)), (center_x, center_y), 320 if is_ultra_walkout else 285 if is_signature_walkout else 250, 5)
            self.screen.blit(pulse, (0, 0))

        if is_goat_walkout:
            pack_phase = norm < 0.14
            tear_phase = 0.14 <= norm < 0.26
            door_phase = 0.26 <= norm < 0.40
            suspense_phase = 0.40 <= norm < 0.74
            flip_phase = 0.74 <= norm < 0.84
            reveal_phase = max(0.0, min(1.0, (norm - 0.84) / 0.16))
            flash_phase = max(0.0, 1.0 - abs(norm - 0.80) / 0.05)
        elif is_suspense_walkout:
            pack_phase = norm < 0.16
            tear_phase = 0.16 <= norm < 0.28
            door_phase = 0.28 <= norm < 0.44
            suspense_phase = 0.44 <= norm < 0.68
            flip_phase = 0.68 <= norm < 0.78
            reveal_phase = max(0.0, min(1.0, (norm - 0.78) / 0.22))
            flash_phase = max(0.0, 1.0 - abs(norm - 0.74) / 0.06)
        else:
            pack_phase = norm < 0.20
            tear_phase = 0.20 <= norm < 0.34
            door_phase = 0.34 <= norm < 0.50
            suspense_phase = False
            flip_phase = 0.50 <= norm < 0.64
            reveal_phase = max(0.0, min(1.0, (norm - 0.64) / 0.36))
            flash_phase = max(0.0, 1.0 - abs(norm - 0.58) / 0.08)

        left_panel_x = 210 + int(math.sin(elapsed * 2.7) * 16)
        right_panel_x = WIDTH - 270 - int(math.sin(elapsed * 2.7) * 16)
        for idx in range(4):
            alpha = 22 + idx * 10
            panel_h = 90
            y = 90 + idx * 115
            left = pygame.Surface((42, panel_h), pygame.SRCALPHA)
            right = pygame.Surface((42, panel_h), pygame.SRCALPHA)
            left.fill((*accent, alpha))
            right.fill((*accent, alpha))
            self.screen.blit(left, (left_panel_x, y))
            self.screen.blit(right, (right_panel_x, y))

        beam_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        beam_shift = int(math.sin(elapsed * 1.9) * 45)
        pygame.draw.polygon(
            beam_surface,
            (*accent, 70),
            [(center_x - 210 + beam_shift, 60), (center_x + 210 + beam_shift, 60), (center_x + 88, HEIGHT - 20), (center_x - 88, HEIGHT - 20)],
        )
        pygame.draw.polygon(
            beam_surface,
            (*accent, 42),
            [(center_x - 110 - beam_shift, 60), (center_x + 110 - beam_shift, 60), (center_x + 24, HEIGHT - 20), (center_x - 24, HEIGHT - 20)],
        )
        self.screen.blit(beam_surface, (0, 0))

        floor_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        lane_speed = elapsed * 280
        floor_color = (244, 206, 84) if is_fc25_walkout else accent
        for lane in range(8):
            lane_y = int((lane_speed + lane * 82) % (HEIGHT + 220)) - 110
            width_a = max(10, 54 - lane * 3)
            width_b = max(8, 34 - lane * 2)
            pygame.draw.polygon(
                floor_surface,
                (*floor_color, 42 if is_fc25_walkout else 24),
                [
                    (center_x - 180, lane_y + 90),
                    (center_x - 180 + width_a, lane_y + 90),
                    (center_x - 52 + width_b, lane_y),
                    (center_x - 52, lane_y),
                ],
            )
            pygame.draw.polygon(
                floor_surface,
                (*floor_color, 42 if is_fc25_walkout else 24),
                [
                    (center_x + 180 - width_a, lane_y + 90),
                    (center_x + 180, lane_y + 90),
                    (center_x + 52, lane_y),
                    (center_x + 52 - width_b, lane_y),
                ],
            )
        self.screen.blit(floor_surface, (0, 0))

        if is_ultra_walkout:
            shard_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            for shard in range(10):
                swing = math.sin(elapsed * 2.2 + shard) * 36
                px = center_x + swing + (shard - 5) * 56
                py = 120 + shard * 42
                pygame.draw.polygon(
                    shard_surface,
                    (*accent, 58),
                    [(px, py), (px + 18, py + 36), (px - 8, py + 70), (px - 22, py + 30)],
                )
            self.screen.blit(shard_surface, (0, 0))
        elif is_signature_walkout:
            ribbon_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            for idx in range(7):
                wave = math.sin(elapsed * 2.4 + idx) * 28
                px = center_x - 260 + idx * 84
                pygame.draw.polygon(
                    ribbon_surface,
                    (*accent, 42),
                    [(px, 120 + wave), (px + 34, 148 + wave), (px - 12, 214 + wave), (px - 38, 166 + wave)],
                )
            self.screen.blit(ribbon_surface, (0, 0))

        if is_fc25_walkout:
            triangle = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            gold = (244, 206, 84)
            pygame.draw.line(triangle, (*gold, 180), (center_x - 114, tunnel_rect.y + 178), (center_x, tunnel_rect.y + 78), 6)
            pygame.draw.line(triangle, (*gold, 180), (center_x + 114, tunnel_rect.y + 178), (center_x, tunnel_rect.y + 78), 6)
            pygame.draw.line(triangle, (*gold, 110), (center_x - 70, tunnel_rect.y + 178), (center_x, tunnel_rect.y + 116), 4)
            pygame.draw.line(triangle, (*gold, 110), (center_x + 70, tunnel_rect.y + 178), (center_x, tunnel_rect.y + 116), 4)
            self.screen.blit(triangle, (0, 0))

        if suspense_phase:
            suspense_norm = 0.0 if suspense_end <= suspense_start else (norm - suspense_start) / (suspense_end - suspense_start)
            suspense_norm = max(0.0, min(1.0, suspense_norm))
            suspense = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pulse = 0.5 + 0.5 * math.sin(elapsed * 7.5)
            inner = pygame.Rect(center_x - 90, tunnel_rect.y + 120, 180, 260)
            for i in range(5):
                inset = i * 18
                alpha = max(10, int((60 - i * 10) * (0.6 + pulse * 0.8)))
                pygame.draw.rect(
                    suspense,
                    (*accent, alpha),
                    (inner.x - inset, inner.y - inset, inner.w + inset * 2, inner.h + inset * 2),
                    2,
                    border_radius=18,
                )
            suspense.fill((0, 0, 0, 120 + int(70 * pulse)))
            self.screen.blit(suspense, (0, 0))
            if is_goat_walkout:
                crown = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                crown_glow = int(120 + 70 * pulse)
                for beam in range(6):
                    spread = 54 + beam * 36
                    pygame.draw.polygon(
                        crown,
                        (255, 220, 120, max(18, crown_glow - beam * 16)),
                        [
                            (center_x - spread, tunnel_rect.y + 154),
                            (center_x - spread // 2, tunnel_rect.y + 54 + beam * 5),
                            (center_x, tunnel_rect.y + 112 - beam * 4),
                            (center_x + spread // 2, tunnel_rect.y + 54 + beam * 5),
                            (center_x + spread, tunnel_rect.y + 154),
                        ],
                    )
                self.screen.blit(crown, (0, 0))
            frame_drop = abs(math.sin(elapsed * 11.0))
            if frame_drop > 0.82:
                blink = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                blink.fill((255, 255, 255, int((frame_drop - 0.82) * 240)))
                self.screen.blit(blink, (0, 0))
            hush = self.big.render("GOAT" if is_goat_walkout else "...", True, WHITE)
            self.screen.blit(hush, (center_x - hush.get_width() // 2, 214))
            ring_r = 32 + int(pulse * 18)
            pygame.draw.circle(self.screen, accent, (center_x, 236), ring_r, 3)
            pygame.draw.circle(self.screen, WHITE, (center_x, 236), max(4, int(8 + pulse * 4)))
            suspense_card_h = 312
            suspense_card_w = 216
            fake_rise = int((1.0 - suspense_norm) * 72)
            fake_y = center_y - 26 - fake_rise
            fake_rect = pygame.Rect(center_x - suspense_card_w // 2, fake_y, suspense_card_w, suspense_card_h)
            pygame.draw.rect(self.screen, (18, 22, 34), fake_rect, 0, border_radius=20)
            pygame.draw.rect(self.screen, accent, fake_rect, 4, border_radius=20)
            for i in range(3):
                inset = 14 + i * 18
                pygame.draw.rect(
                    self.screen,
                    (*accent, max(24, 90 - i * 24)),
                    (fake_rect.x + inset, fake_rect.y + inset, fake_rect.w - inset * 2, fake_rect.h - inset * 2),
                    2,
                    border_radius=16,
                )
            card_back = self.big.render("GOAT" if is_goat_walkout else "FC", True, WHITE)
            self.screen.blit(card_back, (center_x - card_back.get_width() // 2, fake_rect.y + 110))
            suspense_glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            for beam in range(4):
                spread = 80 + beam * 42 + int(pulse * 10)
                alpha = max(16, 72 - beam * 14)
                pygame.draw.polygon(
                    suspense_glow,
                    (*accent, alpha),
                    [
                        (center_x - spread, HEIGHT - 24),
                        (center_x + spread, HEIGHT - 24),
                        (center_x + 42, fake_rect.y + 40),
                        (center_x - 42, fake_rect.y + 40),
                    ],
                )
            self.screen.blit(suspense_glow, (0, 0))
            reveal_tag = self.small.render("GOAT CARD INCOMING" if is_goat_walkout else "SPECIAL CARD INCOMING", True, accent)
            self.screen.blit(reveal_tag, (center_x - reveal_tag.get_width() // 2, fake_rect.y + fake_rect.h + 22))

        arch_y = HEIGHT - 100
        for r in range(4):
            pygame.draw.circle(self.screen, accent, (center_x, arch_y), 118 + r * 16, 2)

        headline = "FC STYLE WALKOUT"
        if is_goat_walkout:
            headline = "GOAT WALKOUT"
        elif is_suspense_walkout:
            headline = "SPECIAL WALKOUT"
        elif is_fc25_walkout:
            headline = "WALKOUT"
        elif tier in ("Elite", "Platinum", "Diamond", "Mythic"):
            headline = "BOARDS"
        title = self.big.render(headline, True, WHITE)
        self.screen.blit(title, (center_x - title.get_width() // 2, 72))

        club_phase = norm >= 0.16
        pos_phase = norm >= 0.31
        promo_phase = norm >= 0.46
        card_phase = norm >= 0.52

        pack_w = 220
        pack_h = 320

        if pack_phase or tear_phase:
            shake = int(math.sin(elapsed * 42.0) * 8) if tear_phase else 0
            pulse = 1.0 + math.sin(elapsed * 4.0) * 0.04 + (0.03 if tear_phase else 0.0)
            draw_w = int(pack_w * pulse)
            draw_h = int(pack_h * pulse)
            draw_x = center_x - draw_w // 2 + shake
            draw_y = center_y - draw_h // 2 - 30
            pack_rect = pygame.Rect(draw_x, draw_y, draw_w, draw_h)
            pygame.draw.rect(self.screen, base_color, pack_rect, 0, border_radius=22)
            pygame.draw.rect(self.screen, accent, pack_rect, 4, border_radius=22)
            band_y = draw_y + 56
            pygame.draw.rect(self.screen, (255, 255, 255, 28), (draw_x + 16, draw_y + 16, draw_w - 32, 42), 0, border_radius=10)
            pygame.draw.rect(self.screen, accent, (draw_x + 20, band_y, draw_w - 40, 72), 0, border_radius=12)
            self.screen.blit(self.big.render(tier[:8].upper(), True, WHITE), (draw_x + 26, band_y + 18))
            self.screen.blit(self.font.render("PACK", True, WHITE), (draw_x + 70, draw_y + draw_h - 66))
            self.screen.blit(self.small.render(player["team"], True, (220, 230, 240)), (draw_x + 26, draw_y + draw_h - 34))
            if tear_phase:
                split = max(2, int((norm - 0.20) / 0.14 * 62))
                pygame.draw.line(self.screen, WHITE, (center_x, draw_y + 18), (center_x, draw_y + draw_h - 18), 3)
                spark_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                for i in range(18):
                    sy = draw_y + 24 + i * 14
                    sx = center_x + int(math.sin(elapsed * 9.0 + i) * 12)
                    pygame.draw.circle(spark_surface, (*accent, 170), (sx, sy), 3)
                self.screen.blit(spark_surface, (0, 0))
                left_half = pygame.Surface((draw_w // 2, draw_h), pygame.SRCALPHA)
                right_half = pygame.Surface((draw_w // 2, draw_h), pygame.SRCALPHA)
                pygame.draw.rect(left_half, (*base_color, 210), (0, 0, draw_w // 2, draw_h), 0, border_radius=22)
                pygame.draw.rect(right_half, (*base_color, 210), (0, 0, draw_w // 2, draw_h), 0, border_radius=22)
                pygame.draw.rect(left_half, (*accent, 220), (0, 0, draw_w // 2, draw_h), 3, border_radius=22)
                pygame.draw.rect(right_half, (*accent, 220), (0, 0, draw_w // 2, draw_h), 3, border_radius=22)
                self.screen.blit(left_half, (draw_x - split, draw_y))
                self.screen.blit(right_half, (center_x + split, draw_y))

        if door_phase or flip_phase or reveal_phase > 0:
            open_amount = 0 if norm < 0.34 else min(1.0, (norm - 0.34) / 0.16)
            door_w = 170
            left_door_x = center_x - 170 - int(open_amount * 150)
            right_door_x = center_x + int(open_amount * 150)
            door_y = 130
            door_h = 380
            pygame.draw.rect(self.screen, (18, 24, 34), (left_door_x, door_y, door_w, door_h), 0, border_radius=20)
            pygame.draw.rect(self.screen, (18, 24, 34), (right_door_x, door_y, door_w, door_h), 0, border_radius=20)
            pygame.draw.rect(self.screen, accent, (left_door_x, door_y, door_w, door_h), 2, border_radius=20)
            pygame.draw.rect(self.screen, accent, (right_door_x, door_y, door_w, door_h), 2, border_radius=20)
            if open_amount > 0:
                corridor = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                for i in range(5):
                    alpha = max(0, 40 - i * 6)
                    inset = i * 22
                    pygame.draw.rect(corridor, (*accent, alpha), (center_x - 110 + inset // 2, door_y + inset, 220 - inset, door_h - inset * 2), 2, border_radius=16)
                self.screen.blit(corridor, (0, 0))

        info_y = 134
        if club_phase:
            club_text = self.font.render(player["team"], True, WHITE)
            self.screen.blit(club_text, (center_x - club_text.get_width() // 2, info_y))
            info_y += 34
        if pos_phase:
            pos_text = self.small.render(f"POSITION  {player.get('position', 'ST')}", True, (220, 230, 240))
            self.screen.blit(pos_text, (center_x - pos_text.get_width() // 2, info_y))
            info_y += 28
        if promo_phase:
            promo_label = player.get("promo", "Base")
            promo_text = self.small.render(f"{promo_label.upper()}  {tier.upper()}", True, accent)
            self.screen.blit(promo_text, (center_x - promo_text.get_width() // 2, info_y))

        if (0.44 <= norm < 0.60 and not is_suspense_walkout) or (0.54 <= norm < 0.78 and is_suspense_walkout):
            suspense_window = 0.08 if is_goat_walkout else 0.06 if is_suspense_walkout else 0.053
            suspense_origin = 0.58 if is_goat_walkout else 0.52 if is_suspense_walkout else 0.44
            countdown = max(1, 3 - int(((norm - suspense_origin) / suspense_window)))
            pulse = 1.0 + abs(math.sin(elapsed * 10.0)) * 0.2
            count_text = self.big.render(str(countdown), True, WHITE)
            count_glow = pygame.Surface((count_text.get_width() + 30, count_text.get_height() + 20), pygame.SRCALPHA)
            pygame.draw.rect(count_glow, (*accent, 40), (0, 0, count_glow.get_width(), count_glow.get_height()), 0, border_radius=12)
            cx = center_x - count_text.get_width() // 2
            cy = 278 if is_goat_walkout else 256 if is_suspense_walkout else 214
            self.screen.blit(count_glow, (cx - 15, cy - 10))
            if pulse > 1.05:
                ring_r = int(34 * pulse)
                pygame.draw.circle(self.screen, accent, (center_x, cy + 18), ring_r, 2)
            self.screen.blit(count_text, (cx, cy))

        if card_phase:
            rise = int((1.0 - reveal_phase) * 180)
            card_h = 330
            card_w = int(238 + reveal_phase * 28)
            bounce = int(math.sin(reveal_phase * math.pi) * 20)
            card_y = center_y - 40 - rise - bounce
            if flip_phase and reveal_phase <= 0:
                flip = min(1.0, (norm - 0.50) / 0.14)
                back_w = max(26, int(card_w * abs(math.cos(flip * math.pi))))
                back_rect = pygame.Rect(center_x - back_w // 2, card_y, back_w, card_h)
                pygame.draw.rect(self.screen, (18, 22, 34), back_rect, 0, border_radius=16)
                pygame.draw.rect(self.screen, accent, back_rect, 3, border_radius=16)
                if back_w > 40:
                    pygame.draw.rect(self.screen, (255, 255, 255, 18), (back_rect.x + 10, back_rect.y + 14, back_rect.w - 20, 48), 0, border_radius=10)
                    self.screen.blit(self.font.render("FC", True, WHITE), (center_x - 14, card_y + 126))
            else:
                glow = pygame.Surface((card_w + 80, card_h + 80), pygame.SRCALPHA)
                flare_scale = 1.0 if tier not in ("Legend", "Icon", "Mythic", "Ascended") else 1.35
                for i in range(5):
                    radius = 20 + i * 14
                    alpha = max(10, int((52 - i * 10) * flare_scale))
                    pygame.draw.rect(glow, (*accent, alpha), (radius, radius, card_w + 80 - radius * 2, card_h + 80 - radius * 2), 0, border_radius=24)
                self.screen.blit(glow, (center_x - glow.get_width() // 2, card_y - 40))
                if flash_phase > 0:
                    flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                    flash.fill((*accent, int(110 * flash_phase)))
                    self.screen.blit(flash, (0, 0))
                if is_suspense_walkout and reveal_phase > 0.15:
                    suspense_burst = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                    burst_alpha = int((170 if is_goat_walkout else 120) * min(1.0, reveal_phase * 1.4))
                    for i in range(7 if is_goat_walkout else 5):
                        radius = 30 + i * 20
                        pygame.draw.rect(
                            suspense_burst,
                            (*accent, max(10, burst_alpha - i * 18)),
                            (center_x - 120 - radius // 2, card_y + 30 - radius // 3, card_w + 240 + radius, card_h + 80 + radius),
                            2,
                            border_radius=26,
                        )
                    self.screen.blit(suspense_burst, (0, 0))
                self.draw_card(center_x - card_w / 2, card_y, card_w, card_h, player)

                ease = 1.0 - (1.0 - reveal_phase) * (1.0 - reveal_phase)
                shown_rating = max(1, int(player["rating"] * ease))
                rating_text = self.big.render(str(shown_rating), True, WHITE)
                rating_box = pygame.Rect(center_x - 64, card_y + card_h + 14, 128, 46)
                pygame.draw.rect(self.screen, (10, 14, 22), rating_box, 0, border_radius=12)
                pygame.draw.rect(self.screen, accent, rating_box, 2, border_radius=12)
                if reveal_phase > 0.88 or (is_suspense_walkout and reveal_phase > 0.72):
                    slam = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                    slam_layers = 8 if is_goat_walkout else 6 if is_suspense_walkout else 4
                    for i in range(slam_layers):
                        alpha = max(0, 110 - i * 12) if is_goat_walkout else max(0, 80 - i * 12) if is_suspense_walkout else max(0, 60 - i * 14)
                        pygame.draw.rect(slam, (*accent, alpha), (center_x - 90 - i * 10, rating_box.y - i * 4, 180 + i * 20, 58 + i * 8), 2, border_radius=14)
                    self.screen.blit(slam, (0, 0))
                self.screen.blit(rating_text, (center_x - rating_text.get_width() // 2, card_y + card_h + 20))

                if reveal_phase >= 0.45:
                    name_text = self.font.render(player["name"], True, WHITE)
                    self.screen.blit(name_text, (center_x - name_text.get_width() // 2, card_y + card_h + 58))

                if reveal_phase > 0.55:
                    confetti_count = 18 if tier in ("Bronze", "Silver", "Gold") else 28
                    if tier in ("Diamond", "Mythic", "Ascended", "Legend", "Icon", "GOAT"):
                        confetti_count += 16
                    for i in range(confetti_count):
                        offset = i * 0.37
                        cx = int(140 + ((i * 53) % (WIDTH - 280)))
                        cy = int(80 + ((elapsed * 110 + offset * 140) % (HEIGHT - 160)))
                        color_mix = accent if i % 2 == 0 else WHITE
                        pygame.draw.rect(self.screen, color_mix, (cx, cy, 6, 12), 0, border_radius=3)
                    if tier in ("Diamond", "Mythic", "Ascended", "Legend", "Icon", "GOAT"):
                        flare = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                        for beam in range(5 if is_goat_walkout else 3):
                            spread = 120 + beam * 60
                            flare_color = (255, 232, 170) if is_goat_walkout and beam % 2 == 0 else accent
                            pygame.draw.polygon(
                                flare,
                                (*flare_color, max(18, 56 - beam * 8)),
                                [(center_x - spread, HEIGHT), (center_x + spread, HEIGHT), (center_x + 60, 120), (center_x - 60, 120)],
                            )
                        self.screen.blit(flare, (0, 0))
                    spark_count = 34 if is_goat_walkout else 22 if tier in ("Diamond", "Mythic", "Ascended", "Legend", "Icon") else 10
                    starburst = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                    for i in range(spark_count):
                        angle = (i / max(1, spark_count)) * math.tau + elapsed * 0.25
                        dist = 120 + (i % 5) * 26
                        sx = int(center_x + math.cos(angle) * dist)
                        sy = int(card_y + 150 + math.sin(angle) * dist * 0.7)
                        pygame.draw.line(starburst, (*accent, 120), (center_x, card_y + 150), (sx, sy), 2)
                        pygame.draw.circle(starburst, WHITE, (sx, sy), 2)
                    self.screen.blit(starburst, (0, 0))

        footer = self.small.render("Club  |  Position  |  Promo  |  Walkout Reveal", True, (178, 188, 204))
        self.screen.blit(footer, (center_x - footer.get_width() // 2, HEIGHT - 34))

    def draw_pack_summary(self):
        if not self.last_pack:
            return
        panel = pygame.Rect(120, 96, 960, 520)
        pygame.draw.rect(self.screen, (18, 24, 36), panel, 0, border_radius=22)
        pygame.draw.rect(self.screen, (70, 86, 122), panel, 3, border_radius=22)
        featured = max(self.last_pack, key=lambda p: (self.rarity_rank(p.get("rarity", "Bronze")), p.get("rating", 0)))
        featured_rarity = featured.get("rarity", "Bronze")
        big_hit = featured_rarity in ("Legend", "Transcendent", "Celestial", "Eternal", "Immortal", "Omega", "Icon", "GOAT")
        title = "Massive Pull" if big_hit else "Pack Summary"
        subtitle = f"Best card: {featured['name']} | {featured['rating']} OVR | {featured_rarity}"
        total_ovr = sum(p.get("rating", 0) for p in self.last_pack)
        unique_rarities = len({p.get("rarity", "Bronze") for p in self.last_pack})
        self.screen.blit(self.big.render(title, True, WHITE), (panel.x + 18, panel.y + 16))
        self.screen.blit(self.small.render(subtitle[:82], True, (190, 200, 215)), (panel.x + 20, panel.y + 50))
        reward_chip = pygame.Rect(panel.right - 230, panel.y + 18, 190, 52)
        pygame.draw.rect(self.screen, (30, 38, 56), reward_chip, 0, border_radius=14)
        pygame.draw.rect(self.screen, (244, 206, 84) if big_hit else (90, 108, 144), reward_chip, 2, border_radius=14)
        self.screen.blit(self.small.render(f"Total OVR {total_ovr}", True, WHITE), (reward_chip.x + 18, reward_chip.y + 10))
        self.screen.blit(self.small.render(f"{unique_rarities} rarity bands", True, (214, 222, 236)), (reward_chip.x + 18, reward_chip.y + 28))
        start_x = panel.x + 26
        for i, player in enumerate(self.last_pack[:5]):
            is_featured = self.fantasy_card_key(player) == self.fantasy_card_key(featured)
            card_x = start_x + i * 182
            card_y = panel.y + 92
            self.draw_card(card_x, card_y, 160, 250, player)
            if is_featured:
                pygame.draw.rect(self.screen, YELLOW, (card_x - 4, card_y - 4, 168, 258), 3, border_radius=18)
        y = panel.y + 372
        for player in self.last_pack[:3]:
            promo = player.get("promo", "Base")
            rarity = player.get("rarity", "Bronze")
            line = f"{player['name']}  {player['rating']} OVR  {player.get('position', 'ST')}  {rarity}/{promo}"
            self.screen.blit(self.small.render(line, True, WHITE), (panel.x + 24, y))
            y += 26
        footer = pygame.Rect(panel.x + 24, panel.bottom - 92, panel.w - 48, 54)
        pygame.draw.rect(self.screen, (28, 34, 48), footer, 0, border_radius=14)
        pygame.draw.rect(self.screen, (90, 108, 144), footer, 2, border_radius=14)
        footer_text = "Featured pull locked to walkout highlight." if big_hit else "Standard reward reveal complete."
        self.screen.blit(self.small.render(footer_text, True, (214, 222, 236)), (footer.x + 18, footer.y + 11))
        self.screen.blit(self.small.render("Open more packs from My Packs or the shop.", True, (190, 200, 215)), (footer.x + 18, footer.y + 29))

    def start_fantasy_season(self):
        if len(self.fantasy_roster) < 11:
            return False
        self.ensure_fantasy_club_defaults()
        fantasy_name = self.fantasy_team_name.strip() or "Fantasy FC"
        self.user_team = fantasy_name
        self.game_mode = "FANTASY"
        self.active_teams = TEAMS[:]
        replaced = self.active_teams[-1] if self.active_teams else None
        if replaced:
            self.fantasy_replaced_team = replaced
            self.active_teams[-1] = fantasy_name
        if fantasy_name not in STADIUMS:
            STADIUMS[fantasy_name] = "Fantasy Arena"
        used_numbers = set()
        lineup = []
        reserves = []
        for i, entry in enumerate(self.fantasy_roster):
            name = entry["name"]
            rating = entry["rating"]
            suggested = entry.get("number", random.randint(1, 99))
            number = suggested
            while number in used_numbers:
                number += 1
            used_numbers.add(number)
            target = lineup if i < 11 else reserves
            target.append((name, number, rating))
        TEAM_LINEUPS[fantasy_name] = lineup
        ROSTER_DATA[fantasy_name] = reserves[:]
        self.apply_fantasy_club_identity()
        self.user_player_index = 9 if len(lineup) > 9 else 0
        if not self.fantasy_competitions:
            self.init_fantasy_competitions()
        else:
            self.reset_champions_bracket()
        self.apply_fantasy_form_boosts()
        self.init_league()
        self.fantasy_fixture_label = "Division Match"
        self.state = "LEAGUE"
        self.save_active_profile()
        self.add_commentary(f"Fantasy mode: {fantasy_name} created")
        return True

    def fantasy_opponents(self):
        return [team for team in self.active_teams if team != self.user_team]

    def build_fantasy_fixture(self):
        opponents = self.fantasy_opponents()
        if not opponents:
            return None
        labels = {
            "division": "Division Match",
            "ladder": "Weekly Ladder",
            "weekend": "Weekend Challenge",
            "theme": self.fantasy_competitions.get("theme", {}).get("name", "Themed Tournament"),
            "cup": "Knockout Cup",
            "draft": "Draft Run",
            "champions": "Champions Clash",
            "silver": "Silver Cup",
            "promo": "Promo Cup",
            "signature": "Signature Showdown",
        }
        mode = self.fantasy_active_competition
        self.fantasy_match_competition = mode
        if mode == "champions":
            pair = self.champions_current_pair()
            if not pair:
                self.reset_champions_bracket()
                pair = self.champions_current_pair()
            if not pair:
                return None
            fixture = pair
        elif mode == "draft":
            if not self.fantasy_draft_active:
                self.open_fantasy_draft(reset=not self.fantasy_draft_roster)
                return None
            opponent = random.choice(opponents)
            if self.week_index % 2 == 0:
                fixture = (self.user_team, opponent)
            else:
                fixture = (opponent, self.user_team)
        else:
            opponent = random.choice(opponents)
            if self.week_index % 2 == 0:
                fixture = (self.user_team, opponent)
            else:
                fixture = (opponent, self.user_team)
        return labels.get(mode, "Fantasy Match"), fixture

    def get_lineup_list(self, col):
        if col == 0:
            return self.user_starting
        if col == 1:
            return self.user_bench
        return self.user_reserves

    def swap_lineup(self, a_col, a_idx, b_col, b_idx):
        a_list = self.get_lineup_list(a_col)
        b_list = self.get_lineup_list(b_col)
        if not a_list or not b_list:
            return
        if a_idx >= len(a_list) or b_idx >= len(b_list):
            return
        if a_col == b_col and a_idx == b_idx:
            return
        controlled_entry = None
        if self.user_player_index is not None and self.user_starting:
            if self.user_player_index < len(self.user_starting):
                controlled_entry = self.user_starting[self.user_player_index]
        a_list[a_idx], b_list[b_idx] = b_list[b_idx], a_list[a_idx]
        self.persist_user_squad_layout()
        self.update_fantasy_chemistry()
        if controlled_entry is not None:
            if controlled_entry in self.user_starting:
                self.user_player_index = self.user_starting.index(controlled_entry)
            else:
                self.user_player_index = 0

    def cycle_controlled_player(self):
        if self.state != "LIVE" or not self.user_team:
            return
        squad = self.home if self.user_is_home else self.away
        if not squad:
            return
        candidates = [p for p in squad if p.role != "GK"]
        if not candidates:
            candidates = squad[:]
        if self.controlled in candidates and len(candidates) > 1:
            next_player = min(
                [p for p in candidates if p is not self.controlled],
                key=lambda p: (p.x - self.controlled.x) ** 2 + (p.y - self.controlled.y) ** 2,
            )
        else:
            next_player = min(candidates, key=lambda p: (p.x - self.ball.x) ** 2 + (p.y - self.ball.y) ** 2)
        self.controlled = next_player
        for idx, entry in enumerate(self.user_starting):
            if entry[0] == next_player.name:
                self.user_player_index = idx
                break
        self.add_commentary(f"Control switched to {next_player.name}", flash=False)

    def init_cups(self):
        teams = (self.active_teams if self.active_teams else TEAMS)[:]
        random.shuffle(teams)
        self.cups = {
            "FA": {"round": 0, "alive": set(teams), "winner": None, "last_fixtures": [], "bracket": []},
            "LC": {"round": 0, "alive": set(teams), "winner": None, "last_fixtures": [], "bracket": []},
        }
        # schedule cup rounds across the season
        self.cup_schedule = {
            2: "LC",
            6: "FA",
            10: "LC",
            14: "FA",
            20: "LC",
            24: "FA",
            30: "LC",
            34: "FA",
        }
        self.cup_round_winners = None

    def start_cup_round(self, cup_key):
        cup = self.cups[cup_key]
        alive = list(cup["alive"])
        random.shuffle(alive)
        fixtures = []
        while len(alive) >= 2:
            a = alive.pop()
            b = alive.pop()
            fixtures.append((a, b))
        if alive:
            # bye
            cup["alive"].add(alive[0])
        cup["last_fixtures"] = fixtures
        cup["round"] += 1
        cup["bracket"].append(fixtures[:])
        return fixtures

    def build_schedule(self, teams):
        teams = teams[:]
        random.shuffle(teams)
        if len(teams) % 2 == 1:
            teams.append("BYE")
        n = len(teams)
        half = n // 2
        rounds = []
        for _ in range(n - 1):
            pairings = []
            for i in range(half):
                t1 = teams[i]
                t2 = teams[n - 1 - i]
                if t1 != "BYE" and t2 != "BYE":
                    pairings.append((t1, t2))
            rounds.append(pairings)
            teams = [teams[0]] + [teams[-1]] + teams[1:-1]
        # second half swap home/away
        second = [(b, a) for rnd in rounds for (a, b) in rnd]
        return rounds + [second[i : i + len(rounds[0])] for i in range(0, len(second), len(rounds[0]))]

    def simulate_match(self, home, away):
        base = 1.2
        h_boost = 0.0
        a_boost = 0.0
        if self.user_team:
            if home == self.user_team:
                h_boost = (self.user_form - 1.0) * 1.2
            if away == self.user_team:
                a_boost = (self.user_form - 1.0) * 1.2
        strength_diff = (get_team_overall(home) - get_team_overall(away)) / 12
        h = max(0, int(random.gauss(base + 0.2 + h_boost + strength_diff, 0.9)))
        a = max(0, int(random.gauss(base - 0.1 + a_boost - strength_diff, 0.9)))
        return h, a

    def compute_match_probabilities(self, home, away):
        if not home or not away:
            return None
        home_strength = get_team_overall(home)
        away_strength = get_team_overall(away)
        home_adj = home_strength + 3
        away_adj = away_strength
        if self.user_team:
            if home == self.user_team:
                home_adj += (self.user_form - 1.0) * 5
            elif away == self.user_team:
                away_adj += (self.user_form - 1.0) * 5
        diff = home_adj - away_adj
        win_weight = math.exp(diff / 6)
        lose_weight = math.exp(-diff / 6)
        draw_weight = 1.1
        total = win_weight + lose_weight + draw_weight
        return {
            "home": win_weight / total,
            "draw": draw_weight / total,
            "away": lose_weight / total,
        }

    def apply_result(self, home, away, h, a):
        th = self.table[home]
        ta = self.table[away]
        th["P"] += 1
        ta["P"] += 1
        th["GF"] += h
        th["GA"] += a
        ta["GF"] += a
        ta["GA"] += h
        th["GD"] = th["GF"] - th["GA"]
        ta["GD"] = ta["GF"] - ta["GA"]
        if h > a:
            th["W"] += 1
            ta["L"] += 1
            th["PTS"] += 3
        elif a > h:
            ta["W"] += 1
            th["L"] += 1
            ta["PTS"] += 3
        else:
            th["D"] += 1
            ta["D"] += 1
            th["PTS"] += 1
            ta["PTS"] += 1

    def start_week(self):
        if self.game_mode == "FANTASY":
            self.restore_fantasy_club_state()
            if not self.user_team:
                self.account_message = "Fantasy club save is incomplete. Reopen fantasy mode."
                self.state = "LEAGUE"
                return
            for objective in self.fantasy_objectives.get("daily", []):
                objective["progress"] = 0
                objective["claimed"] = False
            if self.week_index % 4 == 0:
                for objective in self.fantasy_objectives.get("weekly", []):
                    objective["progress"] = 0
                    objective["claimed"] = False
            fantasy_fixture = self.build_fantasy_fixture()
            if fantasy_fixture:
                self.fantasy_fixture_label, fixture = fantasy_fixture
                self.current_home, self.current_away = fixture
                self.current_competition = self.fantasy_fixture_label
                self.pending_fixture = fixture
                self.match_probabilities = self.compute_match_probabilities(self.current_home, self.current_away)
                self.user_is_home = self.current_home == self.user_team
                self.home_kit_index = 0
                self.away_kit_index = 1
                self.lineup_col = 0
                self.lineup_idx = 0
                self.lineup_pick = None
                self.state = "LINEUP"
            return
        if self.game_mode != "FANTASY":
            self.user_budget += 10  # weekly revenue stream
        self.match_probabilities = None
        if self.week_index == 19 and not self.half_season_boosted:
            self.apply_midseason_boosts()
        if self.week_index >= 38:
            self.finish_season()
            return
        if self.transfer_window and not self.transfer_window_active():
            self.transfer_window = False
        if self.game_mode != "FANTASY":
            self.refresh_transfer_market()
        if self.week_index in self.cup_schedule:
            cup_key = self.cup_schedule[self.week_index]
            self.current_competition = cup_key
            fixtures = self.start_cup_round(cup_key)
            user_fixture = None
            for f in fixtures:
                if self.user_team in f:
                    user_fixture = f
                    break
            winners = set()
            for home, away in fixtures:
                if user_fixture and (home, away) == user_fixture:
                    continue
                h, a = self.simulate_match(home, away)
                if h == a:
                    h += random.choice([0, 1])
                winners.add(home if h > a else away)
            if user_fixture:
                self.current_home, self.current_away = user_fixture
                self.match_probabilities = self.compute_match_probabilities(self.current_home, self.current_away)
                self.user_is_home = self.current_home == self.user_team
                self.cup_round_winners = winners
                self.pending_fixture = user_fixture
                self.home_kit_index = 0
                self.away_kit_index = 1
                self.lineup_col = 0
                self.lineup_idx = 0
                self.lineup_pick = None
                self.state = "LINEUP"
            else:
                self.cups[cup_key]["alive"] = winners
                if len(winners) <= 1:
                    self.cups[cup_key]["winner"] = next(iter(winners), None)
                self.week_index += 1
                if self.game_mode != "FANTASY":
                    self.refresh_transfer_market()
            return
        fixtures = self.fixtures[self.week_index]
        user_fixture = None
        for f in fixtures:
            if self.user_team in f:
                user_fixture = f
                break
        # simulate other matches
        for home, away in fixtures:
            if user_fixture and (home, away) == user_fixture:
                continue
            h, a = self.simulate_match(home, away)
            self.apply_result(home, away, h, a)

        self.current_competition = "LEAGUE"
        if user_fixture:
            self.current_home, self.current_away = user_fixture
            self.match_probabilities = self.compute_match_probabilities(self.current_home, self.current_away)
            self.user_is_home = self.current_home == self.user_team
            self.pending_fixture = user_fixture
            self.home_kit_index = 0
            self.away_kit_index = 1
            self.lineup_col = 0
            self.lineup_idx = 0
            self.lineup_pick = None
            self.state = "LINEUP"
        else:
            self.week_index += 1
            if self.game_mode != "FANTASY":
                self.refresh_transfer_market()

    def get_team_player_names(self, team):
        lineup = TEAM_LINEUPS.get(team, DEFAULT_LINEUP)
        names = [lineup_name_number(entry, i)[0] for i, entry in enumerate(lineup)]
        return names if names else [f"{team} Player"]

    def simulate_match_with_stats(self, home, away, competition="LEAGUE"):
        h, a = self.simulate_match(home, away)
        if competition != "LEAGUE" and h == a:
            h += random.choice([0, 1])
        home_names = self.get_team_player_names(home)
        away_names = self.get_team_player_names(away)
        for _ in range(h):
            scorer = random.choice(home_names)
            self.register_stat(scorer, "goals")
            if len(home_names) > 1 and random.random() < 0.7:
                assist = random.choice([n for n in home_names if n != scorer])
                self.register_stat(assist, "assists")
        for _ in range(a):
            scorer = random.choice(away_names)
            self.register_stat(scorer, "goals")
            if len(away_names) > 1 and random.random() < 0.7:
                assist = random.choice([n for n in away_names if n != scorer])
                self.register_stat(assist, "assists")
        if a == 0:
            self.register_stat(home_names[0], "clean_sheets")
        if h == 0:
            self.register_stat(away_names[0], "clean_sheets")
        return h, a

    def skip_to_end_of_season(self):
        self.transfer_window = False
        self.pending_fixture = None
        self.match_probabilities = None
        while self.week_index < 38:
            if self.game_mode != "FANTASY":
                self.user_budget += 10
            if self.transfer_window and not self.transfer_window_active():
                self.transfer_window = False
            if self.game_mode != "FANTASY":
                self.refresh_transfer_market()
            if self.week_index in self.cup_schedule:
                cup_key = self.cup_schedule[self.week_index]
                self.current_competition = cup_key
                fixtures = self.start_cup_round(cup_key)
                winners = set()
                for home, away in fixtures:
                    h, a = self.simulate_match_with_stats(home, away, competition=cup_key)
                    winner = home if h > a else away
                    winners.add(winner)
                self.cups[cup_key]["alive"] = winners
                if len(winners) <= 1:
                    winner = next(iter(winners), None)
                    self.cups[cup_key]["winner"] = winner
                    if winner and winner == self.user_team:
                        self.career_trophies[cup_key] += 1
                        if self.game_mode == "FANTASY":
                            self.fantasy_coins += 120
                        else:
                            self.user_budget += 12
            else:
                fixtures = self.fixtures[self.week_index]
                for home, away in fixtures:
                    h, a = self.simulate_match_with_stats(home, away, competition="LEAGUE")
                    self.apply_result(home, away, h, a)
            self.week_index += 1
            if self.game_mode != "FANTASY":
                self.refresh_transfer_market()
        self.finish_season()

    def finish_season(self):
        winner = max(self.table.items(), key=lambda kv: (kv[1]["PTS"], kv[1]["GD"], kv[1]["GF"]))[0]
        if self.user_team and winner == self.user_team:
            self.career_trophies["LEAGUE"] += 1
            self.award_trophy_funds("LEAGUE")
        else:
            if self.game_mode != "FANTASY":
                self.user_budget += 10
        self.assign_season_awards()
        self.season += 1
        self.user_form = clamp(self.user_form, 0.9, 1.1)
        self.init_league()
        self.state = "LEAGUE"
        self.message = f"Season {self.season - 1} complete"

    def award_trophy_funds(self, competition):
        amounts = {"LEAGUE": 80, "FA": 65, "LC": 60}
        bonus = amounts.get(competition, 8)
        if self.game_mode == "FANTASY":
            self.fantasy_coins += bonus * 2
            msg = f"BBC: {self.user_team} bag the {competition} prize, pocketing {bonus * 2} coins."
        else:
            self.user_budget += bonus
            msg = f"BBC: {self.user_team} bag the {competition} prize, pocketing £{bonus}m."
        self.add_commentary(msg)
        bump = 2 if competition == "LEAGUE" else 1
        self.bump_ratings(bump)

    def assign_season_awards(self):
        if not self.season_stats:
            self.last_season_awards = {}
            return
        def pick(stat):
            max_value = max((data.get(stat, 0) for data in self.season_stats.values()), default=0)
            if max_value <= 0:
                return [], 0
            names = sorted([name for name, data in self.season_stats.items() if data.get(stat, 0) == max_value])
            return names, max_value
        top_scorers, goals = pick("goals")
        top_assists, assists = pick("assists")
        clean_sheeters, sheets = pick("clean_sheets")
        self.last_season_awards = {
            "top_scorer": (top_scorers, goals),
            "top_assists": (top_assists, assists),
            "clean_sheets": (clean_sheeters, sheets),
        }
        msgs = []
        if top_scorers:
            for name in top_scorers:
                self.award_player(name, "Top Scorer")
            msgs.append(f"TOP SCORER: {', '.join(top_scorers)} ({goals} goals)")
        if top_assists:
            for name in top_assists:
                self.award_player(name, "Top Assist")
            msgs.append(f"TOP ASSIST: {', '.join(top_assists)} ({assists} assists)")
        if clean_sheeters:
            for name in clean_sheeters:
                self.award_player(name, "Most Clean Sheets")
            msgs.append(f"CLEAN SHEETS: {', '.join(clean_sheeters)} ({sheets} shutouts)")
        if msgs:
            self.add_commentary("Season Awards: " + " | ".join(msgs))
        self.apply_award_boosts()

    def apply_award_boosts(self):
        awards = self.last_season_awards or {}
        winners = set()
        for key in ("top_scorer", "top_assists", "clean_sheets"):
            names, _ = awards.get(key, ([], 0))
            winners.update(names)
        for name in winners:
            self.update_rating_across_league(name, 2)

    def apply_midseason_boosts(self):
        self.half_season_boosted = True
        boosted = []
        for group in (self.user_starting, self.user_bench, self.user_reserves):
            for i, (name, num, rating) in enumerate(group):
                goals = self.get_player_stat(name, "goals")
                assists = self.get_player_stat(name, "assists")
                clean = self.get_player_stat(name, "clean_sheets")
                tackles = self.get_player_stat(name, "tackles")
                if goals >= 5 or assists >= 5 or clean >= 5 or tackles >= 10:
                    new_rating = rating + 1
                    if new_rating != rating:
                        group[i] = (name, num, new_rating)
                        self.update_team_lineup_rating(self.user_team, name, num, new_rating)
                        boosted.append(name)
        if boosted:
            self.add_commentary(f"Mid-season boosts: {', '.join(sorted(set(boosted)))}")

    def update_team_lineup_rating(self, team, name, number, rating):
        lineup = TEAM_LINEUPS.get(team, [])
        for i, entry in enumerate(lineup):
            entry_name, entry_num = lineup_name_number(entry, i)
            if entry_name == name:
                entry_num = entry_num if entry_num else number
                lineup[i] = (name, entry_num, rating)
                return

    def update_rating_across_league(self, name, delta):
        for team, lineup in TEAM_LINEUPS.items():
            for i, entry in enumerate(lineup):
                entry_name, entry_num = lineup_name_number(entry, i)
                if entry_name != name:
                    continue
                if isinstance(entry, (tuple, list)) and len(entry) > 2:
                    rating = entry[2]
                else:
                    rating = probable_rating(name, team, 70)
                lineup[i] = (entry_name, entry_num, rating + delta)
                if self.user_team and team == self.user_team:
                    # Keep user lists aligned with updated ratings
                    for group in (self.user_starting, self.user_bench, self.user_reserves):
                        for gi, (gname, gnum, grating) in enumerate(group):
                            if gname == name:
                                group[gi] = (gname, gnum, grating + delta)
                return

    def bump_ratings(self, amount):
        for lst in (self.user_starting, self.user_bench, self.user_reserves):
            for i, (name, num, rating) in enumerate(lst):
                lst[i] = (name, num, rating + amount)

    def get_used_numbers(self, team):
        used = set()
        for idx, entry in enumerate(TEAM_LINEUPS.get(team, [])):
            _, num = lineup_name_number(entry, idx)
            used.add(num)
        return used

    def assign_unique_number(self, team, suggested):
        num = suggested
        used = self.get_used_numbers(team)
        while num in used:
            num += 1
        return num

    def build_transfer_pool(self):
        pool = []
        for team, lineup in TEAM_LINEUPS.items():
            if team == self.user_team:
                continue
            for idx, entry in enumerate(lineup):
                name, num = lineup_name_number(entry, idx)
                value = random.randint(8, 60)
                rating = random.randint(50, 100)
                pool.append({"name": name, "team": team, "value": value, "rating": rating, "number": num})
        random.shuffle(pool)
        self.transfer_pool = pool[:30]
        self.transfer_offers = []

    def transfer_window_active(self):
        return self.week_index in range(0, 4) or self.week_index in range(19, 24)

    def refresh_transfer_market(self):
        self.build_transfer_pool()
        if self.transfer_window_active():
            self.transfer_offers = self.transfer_pool[:8]
        else:
            self.transfer_offers = []

    def generate_player_name(self):
        first = ["Liam", "Noah", "Mason", "Ethan", "Theo", "Lucas", "Kai", "Julian", "Arthur", "Felix", "Oscar"]
        last = ["Hayes", "Morrow", "Dalton", "Reed", "Carter", "Fletcher", "Keane", "Walters", "Briggs", "Holloway"]
        return f"{random.choice(first)} {random.choice(last)}"

    def replace_sold_player(self, team, name):
        lineup = TEAM_LINEUPS.get(team)
        if not lineup:
            return
        for i, entry in enumerate(lineup):
            n, num = lineup_name_number(entry, i)
            if n == name:
                if isinstance(entry, (tuple, list)) and len(entry) > 2:
                    rating = entry[2]
                else:
                    rating = probable_rating(name, team, 70)
                lineup[i] = (self.generate_player_name(), num, rating)
                return

    def open_transfer_window(self):
        if not self.transfer_window_active():
            return
        self.refresh_transfer_market()
        if not self.transfer_offers:
            return
        self.transfer_window = True
        self.selected_index = 0

    def start_match(self):
        self.state = "MATCH_SCENE"
        self.kickoff_pending = True
        self.kickoff_team = "H"
        self.score_h = 0
        self.score_a = 0
        self.match_time = 0
        self.half = 1
        self.set_piece_pending = False
        self.set_piece_taker = None
        self.set_piece_type = None
        self.show_lineups = False
        self.show_stats_panel = False
        self.full_time_pending = False
        self.full_time_timer = 0.0
        self.match_scene_title = ""
        self.match_scene_subtitle = ""
        self.match_scene_moment = ""
        self.match_player_stats = {}
        self.show_calendar = False
        self.show_cup_bracket = False
        # injuries and form apply for this match
        self.user_injuries = 0
        self.user_match_form = self.user_form
        if self.user_team and (self.current_home == self.user_team or self.current_away == self.user_team):
            self.user_injuries = random.choice([0, 0, 1, 2])
            self.user_match_form = clamp(self.user_form - 0.03 * self.user_injuries, 0.8, 1.2)
        self.stats = {
            "H": {"pos_time": 0.0, "shots": 0, "pass_att": 0, "pass_cmp": 0},
            "A": {"pos_time": 0.0, "shots": 0, "pass_att": 0, "pass_cmp": 0},
        }
        self.pending_pass_team = None
        self.reset_positions(kickoff=True)
        # ensure controlled player always on user's team
        if self.user_team:
            self.user_is_home = self.current_home == self.user_team
        stadium = STADIUMS.get(self.current_home, "Stadium")
        self.message = f"Matchweek {self.week_index + 1}: {self.current_home} vs {self.current_away} @ {stadium}"
        self.add_commentary(self.message)
        self.set_match_scene("pre")

    def finish_match(self):
        # apply result by competition
        if self.game_mode == "FANTASY":
            pass
        elif self.current_competition == "LEAGUE":
            self.apply_result(self.current_home, self.current_away, self.score_h, self.score_a)
        else:
            # cup winner by penalties if needed
            if self.score_h == self.score_a:
                if random.random() < 0.5:
                    self.score_h += 1
                else:
                    self.score_a += 1
            winner = self.current_home if self.score_h > self.score_a else self.current_away
            cup = self.cups[self.current_competition]
            alive = set(self.cup_round_winners or cup["alive"])
            if self.current_home in alive:
                alive.remove(self.current_home)
            if self.current_away in alive:
                alive.remove(self.current_away)
            alive.add(winner)
            cup["alive"] = alive
            if len(alive) <= 1:
                cup["winner"] = winner
                if self.user_team == winner:
                    self.career_trophies[self.current_competition] += 1
                    if self.game_mode == "FANTASY":
                        self.fantasy_coins += 120
                    else:
                        self.user_budget += 12
            self.cup_round_winners = None
        if self.game_mode == "FANTASY":
            self.register_clean_sheets()
            self.fantasy_coins += 50
            user_goals = self.score_h if self.user_is_home else self.score_a
            opp_goals = self.score_a if self.user_is_home else self.score_h
            won = user_goals > opp_goals
            drew = user_goals == opp_goals
            self.update_objective_progress("matches", 1)
            self.update_objective_progress("goals", user_goals)
            self.update_objective_progress("wins", 1 if won else 0)
            self.update_objective_progress("season_goals", user_goals)
            tackle_total = self.get_user_stat_total("tackles")
            self.update_objective_progress("tackles", absolute=tackle_total)
            self.add_fantasy_xp(40 + (20 if won else 8 if drew else 0))
            self.update_fantasy_competitions(
                user_goals > opp_goals,
                user_goals == opp_goals,
                self.fantasy_match_competition,
                user_goals,
                opp_goals,
            )
            self.apply_fantasy_progression()
        else:
            self.register_clean_sheets()
        self.week_index += 1
        self.state = "LEAGUE"
        self.kickoff_pending = True

    def register_clean_sheets(self):
        if self.score_a == 0:
            keeper = next((p for p in self.home if p.role == "GK"), None)
            if keeper:
                self.register_stat(keeper.name, "clean_sheets")
        if self.score_h == 0:
            keeper = next((p for p in self.away if p.role == "GK"), None)
            if keeper:
                self.register_stat(keeper.name, "clean_sheets")

    # --- Gameplay ---
    def add_commentary(self, text, flash=True):
        self.commentary.append(text)
        if len(self.commentary) > 6:
            self.commentary = self.commentary[-6:]
        if flash:
            self.commentary_flash = text
            self.commentary_timer = 2.5

    def say(self, event, **kw):
        lines = {
            "pass": [
                "{a} to {b} — quick one-two.",
                "Sharp pass, {a} finds {b}.",
                "{a} switches it to {b}.",
                "{a} threads it through to {b}.",
                "{a} keeps it ticking to {b}.",
            ],
            "shot": [
                "{a} hits it!",
                "{a} unleashes one!",
                "{a} goes for goal!",
                "{a} with the strike!",
            ],
            "pass_fail": [
                "{a}'s pass is cut out!",
                "{a} tries the through ball — intercepted.",
                "{a} misplaces it under pressure.",
            ],
            "shot_miss": [
                "{a} drags it wide!",
                "{a} can't find the target.",
                "{a} over the bar!",
            ],
            "goal": [
                "GOAL! {a} finishes it!",
                "{a} with a clinical finish!",
                "It’s in! {a} scores!",
                "{a} makes no mistake!",
                "Goal for {t}! {a} delivers!",
            ],
            "save": [
                "Brilliant save!",
                "The keeper denies it!",
                "Big stop!",
            ],
            "tackle_win": [
                "{a} wins it back!",
                "Crunching tackle by {a}!",
                "{a} times it perfectly!",
            ],
            "tackle_miss": [
                "{a} goes to ground and misses.",
                "{a} just late to it.",
            ],
            "throw": [
                "Throw‑in for {t}.",
                "{t} restart with the throw.",
            ],
            "corner": [
                "Corner to {t}.",
                "{t} win the corner.",
            ],
            "goalkick": [
                "Goal kick for {t}.",
                "{t} restart from the six‑yard box.",
            ],
            "dribble": [
                "{a} skips past a challenge!",
                "{a} glides forward with the ball.",
                "{a} drives into space!",
            ],
            "counter": [
                "Quick break for {t}!",
                "{t} spring the counter!",
            ],
            "skill": [
                "{a} with a slick move!",
                "{a} shows quick feet!",
            ],
            "pressure": [
                "High pressure from {t}.",
                "{t} squeeze the space.",
            ],
            "near_goal": [
                "Danger! {a} is in a shooting lane!",
                "{a} in a great position!",
            ],
        }
        templates = lines.get(event, ["{a}"])
        text = random.choice(templates).format(**kw)
        self.add_commentary(text)

    def commentary_insight(self, moment="mid"):
        if not self.user_team:
            return
        # table context
        sorted_table = sorted(
            self.table.items(),
            key=lambda kv: (kv[1]["PTS"], kv[1]["GD"], kv[1]["GF"]),
            reverse=True,
        )
        rank = next((i + 1 for i, (t, _) in enumerate(sorted_table) if t == self.user_team), 0)
        form_note = "in good form" if self.user_form >= 1.05 else "a bit flat" if self.user_form <= 0.95 else "steady"
        key_name = None
        if self.user_starting:
            key_name = self.user_starting[self.user_player_index or 0][0]
        lines = []
        if moment == "pre":
            lines = [
                f"Matchday: {self.user_team} arrive {form_note}, sitting {rank} in the table.",
                f"Big spotlight on {key_name} today for {self.user_team}.",
            ]
        elif moment == "half":
            lines = [
                f"At the break: {self.user_team} look {form_note}.",
                f"Halftime: {key_name} has been influential for {self.user_team}.",
            ]
        elif moment == "full":
            lines = [
                f"Full-time: {self.user_team} were {form_note} today.",
                f"Post-match: {key_name} stood out for {self.user_team}.",
            ]
        else:
            lines = [
                f"{self.user_team} look {form_note} right now.",
                f"{key_name} is dictating the tempo.",
                f"Table watch: {self.user_team} are {rank}th.",
            ]
        if lines:
            self.add_commentary(random.choice(lines), flash=False)

    def get_team_settings(self, team):
        if self.user_team and ((team == "H" and self.user_is_home) or (team == "A" and not self.user_is_home)):
            press = self.press_level
            line = self.line_level
            tempo = self.tempo_level
        else:
            press = 2
            line = 2
            tempo = 2
        return press, line, tempo

    def get_home_positions(self):
        center_y = HEIGHT / 2
        if self.tactic == 1:
            return [
                (FIELD_MARGIN + 40, center_y, "GK"),
                (FIELD_MARGIN + 130, center_y - 170, "DF"),
                (FIELD_MARGIN + 130, center_y - 60, "DF"),
                (FIELD_MARGIN + 130, center_y + 60, "DF"),
                (FIELD_MARGIN + 130, center_y + 170, "DF"),
                (FIELD_MARGIN + 320, center_y - 150, "MF"),
                (FIELD_MARGIN + 320, center_y - 50, "MF"),
                (FIELD_MARGIN + 320, center_y + 50, "MF"),
                (FIELD_MARGIN + 320, center_y + 150, "MF"),
                (FIELD_MARGIN + 520, center_y - 60, "FW"),
                (FIELD_MARGIN + 520, center_y + 60, "FW"),
            ]
        if self.tactic == 2:
            return [
                (FIELD_MARGIN + 40, center_y, "GK"),
                (FIELD_MARGIN + 130, center_y - 170, "DF"),
                (FIELD_MARGIN + 130, center_y - 60, "DF"),
                (FIELD_MARGIN + 130, center_y + 60, "DF"),
                (FIELD_MARGIN + 130, center_y + 170, "DF"),
                (FIELD_MARGIN + 330, center_y - 100, "MF"),
                (FIELD_MARGIN + 330, center_y, "MF"),
                (FIELD_MARGIN + 330, center_y + 100, "MF"),
                (FIELD_MARGIN + 520, center_y - 160, "FW"),
                (FIELD_MARGIN + 520, center_y, "FW"),
                (FIELD_MARGIN + 520, center_y + 160, "FW"),
            ]
        if self.tactic == 3:
            return [
                (FIELD_MARGIN + 40, center_y, "GK"),
                (FIELD_MARGIN + 160, center_y - 140, "DF"),
                (FIELD_MARGIN + 160, center_y, "DF"),
                (FIELD_MARGIN + 160, center_y + 140, "DF"),
                (FIELD_MARGIN + 330, center_y - 200, "MF"),
                (FIELD_MARGIN + 330, center_y - 80, "MF"),
                (FIELD_MARGIN + 330, center_y, "MF"),
                (FIELD_MARGIN + 330, center_y + 80, "MF"),
                (FIELD_MARGIN + 330, center_y + 200, "MF"),
                (FIELD_MARGIN + 520, center_y - 60, "FW"),
                (FIELD_MARGIN + 520, center_y + 60, "FW"),
            ]
        if self.tactic == 4:
            return [
                (FIELD_MARGIN + 40, center_y, "GK"),
                (FIELD_MARGIN + 130, center_y - 170, "DF"),
                (FIELD_MARGIN + 130, center_y - 60, "DF"),
                (FIELD_MARGIN + 130, center_y + 60, "DF"),
                (FIELD_MARGIN + 130, center_y + 170, "DF"),
                (FIELD_MARGIN + 280, center_y - 90, "MF"),
                (FIELD_MARGIN + 280, center_y + 90, "MF"),
                (FIELD_MARGIN + 420, center_y - 140, "MF"),
                (FIELD_MARGIN + 420, center_y, "MF"),
                (FIELD_MARGIN + 420, center_y + 140, "MF"),
                (FIELD_MARGIN + 540, center_y, "FW"),
            ]
        if self.tactic == 5:
            return [
                (FIELD_MARGIN + 40, center_y, "GK"),
                (FIELD_MARGIN + 120, center_y - 190, "DF"),
                (FIELD_MARGIN + 120, center_y - 95, "DF"),
                (FIELD_MARGIN + 120, center_y, "DF"),
                (FIELD_MARGIN + 120, center_y + 95, "DF"),
                (FIELD_MARGIN + 120, center_y + 190, "DF"),
                (FIELD_MARGIN + 300, center_y - 120, "MF"),
                (FIELD_MARGIN + 300, center_y, "MF"),
                (FIELD_MARGIN + 300, center_y + 120, "MF"),
                (FIELD_MARGIN + 520, center_y - 60, "FW"),
                (FIELD_MARGIN + 520, center_y + 60, "FW"),
            ]
        if self.tactic == 6:
            return [
                (FIELD_MARGIN + 40, center_y, "GK"),
                (FIELD_MARGIN + 130, center_y - 170, "DF"),
                (FIELD_MARGIN + 130, center_y - 60, "DF"),
                (FIELD_MARGIN + 130, center_y + 60, "DF"),
                (FIELD_MARGIN + 130, center_y + 170, "DF"),
                (FIELD_MARGIN + 260, center_y, "MF"),
                (FIELD_MARGIN + 360, center_y - 160, "MF"),
                (FIELD_MARGIN + 360, center_y - 60, "MF"),
                (FIELD_MARGIN + 360, center_y + 60, "MF"),
                (FIELD_MARGIN + 360, center_y + 160, "MF"),
                (FIELD_MARGIN + 540, center_y, "FW"),
            ]
        if self.tactic == 7:
            return [
                (FIELD_MARGIN + 40, center_y, "GK"),
                (FIELD_MARGIN + 130, center_y - 170, "DF"),
                (FIELD_MARGIN + 130, center_y - 60, "DF"),
                (FIELD_MARGIN + 130, center_y + 60, "DF"),
                (FIELD_MARGIN + 130, center_y + 170, "DF"),
                (FIELD_MARGIN + 280, center_y - 60, "MF"),
                (FIELD_MARGIN + 280, center_y + 60, "MF"),
                (FIELD_MARGIN + 420, center_y - 120, "FW"),
                (FIELD_MARGIN + 420, center_y + 120, "FW"),
                (FIELD_MARGIN + 540, center_y - 60, "FW"),
                (FIELD_MARGIN + 540, center_y + 60, "FW"),
            ]
        if self.tactic == 8:
            return [
                (FIELD_MARGIN + 40, center_y, "GK"),
                (FIELD_MARGIN + 150, center_y - 140, "DF"),
                (FIELD_MARGIN + 150, center_y, "DF"),
                (FIELD_MARGIN + 150, center_y + 140, "DF"),
                (FIELD_MARGIN + 320, center_y - 160, "MF"),
                (FIELD_MARGIN + 320, center_y - 50, "MF"),
                (FIELD_MARGIN + 320, center_y + 50, "MF"),
                (FIELD_MARGIN + 320, center_y + 160, "MF"),
                (FIELD_MARGIN + 520, center_y - 120, "FW"),
                (FIELD_MARGIN + 520, center_y, "FW"),
                (FIELD_MARGIN + 520, center_y + 120, "FW"),
            ]
        return [
            (FIELD_MARGIN + 40, center_y, "GK"),
            (FIELD_MARGIN + 160, center_y - 140, "DF"),
            (FIELD_MARGIN + 160, center_y, "DF"),
            (FIELD_MARGIN + 160, center_y + 140, "DF"),
            (FIELD_MARGIN + 330, center_y - 200, "MF"),
            (FIELD_MARGIN + 330, center_y - 80, "MF"),
            (FIELD_MARGIN + 330, center_y, "MF"),
            (FIELD_MARGIN + 330, center_y + 80, "MF"),
            (FIELD_MARGIN + 330, center_y + 200, "MF"),
            (FIELD_MARGIN + 520, center_y - 60, "FW"),
            (FIELD_MARGIN + 520, center_y + 60, "FW"),
        ]

    def get_away_positions(self):
        return [(WIDTH - x, y, role) for x, y, role in self.get_home_positions()]

    def reset_positions(self, kickoff=False):
        self.home = []
        self.away = []
        center_y = HEIGHT / 2

        home_names = TEAM_LINEUPS.get(self.current_home, DEFAULT_LINEUP)
        away_names = TEAM_LINEUPS.get(self.current_away, DEFAULT_LINEUP)
        if self.user_team and self.user_starting:
            if self.current_home == self.user_team:
                home_names = self.user_starting
            elif self.current_away == self.user_team:
                away_names = self.user_starting

        for i, (x, y, role) in enumerate(self.get_home_positions()):
            name, num, rating = normalize_entry(home_names[i] if i < len(home_names) else (f"H{i+1}", i + 1), i, self.current_home)
            spd = player_speed_from_rating(rating)
            if self.user_team and self.user_is_home:
                spd *= self.user_match_form
            player = Player(name, x, y, "H", role, spd, number=num, home_x=x, home_y=y)
            player.rating = rating
            meta = self.get_fantasy_card_meta(name, num, rating) if self.game_mode == "FANTASY" else None
            if meta:
                player.traits = tuple(meta.get("traits", []))
            chem = self.fantasy_chemistry_map.get((name, num, rating), 0) if self.game_mode == "FANTASY" else 0
            player.chemistry = chem
            if self.game_mode == "FANTASY":
                player.speed *= self.chemistry_multiplier(chem)
                player.rating = player.rating + chem
            self.home.append(player)

        away_positions = [
            (WIDTH - FIELD_MARGIN - 40, center_y, "GK"),
            (WIDTH - FIELD_MARGIN - 130, center_y - 170, "DF"),
            (WIDTH - FIELD_MARGIN - 130, center_y - 60, "DF"),
            (WIDTH - FIELD_MARGIN - 130, center_y + 60, "DF"),
            (WIDTH - FIELD_MARGIN - 130, center_y + 170, "DF"),
            (WIDTH - FIELD_MARGIN - 320, center_y - 150, "MF"),
            (WIDTH - FIELD_MARGIN - 320, center_y - 50, "MF"),
            (WIDTH - FIELD_MARGIN - 320, center_y + 50, "MF"),
            (WIDTH - FIELD_MARGIN - 320, center_y + 150, "MF"),
            (WIDTH - FIELD_MARGIN - 520, center_y - 60, "FW"),
            (WIDTH - FIELD_MARGIN - 520, center_y + 60, "FW"),
        ]
        for i, (x, y, role) in enumerate(away_positions):
            name, num, rating = normalize_entry(away_names[i] if i < len(away_names) else (f"A{i+1}", i + 1), i, self.current_away)
            spd = player_speed_from_rating(rating)
            if self.user_team and not self.user_is_home:
                spd *= self.user_match_form
            player = Player(name, x, y, "A", role, spd, number=num, home_x=x, home_y=y)
            player.rating = rating
            meta = self.get_fantasy_card_meta(name, num, rating) if self.game_mode == "FANTASY" else None
            if meta:
                player.traits = tuple(meta.get("traits", []))
            chem = self.fantasy_chemistry_map.get((name, num, rating), 0) if self.game_mode == "FANTASY" and self.current_away == self.user_team else 0
            player.chemistry = chem
            if self.game_mode == "FANTASY" and self.current_away == self.user_team:
                player.speed *= self.chemistry_multiplier(chem)
                player.rating = player.rating + chem
            self.away.append(player)

        for p in self.home + self.away:
            p.has_ball = False

        self.ball.x = WIDTH / 2
        self.ball.y = HEIGHT / 2
        self.ball.vx = 0
        self.ball.vy = 0

        if kickoff:
            # controlled player is always on user's team
            pick_index = self.user_player_index if self.user_player_index is not None else 9
            pick_index = max(0, min(10, pick_index))
            if self.user_team and not self.user_is_home:
                self.controlled = self.away[pick_index]
            else:
                self.controlled = self.home[pick_index]

            # kickoff goes to specified team (home at start, conceding team after goal)
            kickoff_index = 9
            if self.kickoff_team == "A":
                self.kickoff_player = self.away[kickoff_index]
            else:
                self.kickoff_player = self.home[kickoff_index]

            for p in self.home + self.away:
                p.has_ball = False
            self.kickoff_player.x = WIDTH / 2
            self.kickoff_player.y = HEIGHT / 2
            self.kickoff_player.has_ball = True
            self.ball.x = WIDTH / 2
            self.ball.y = HEIGHT / 2

    def apply_tactic(self):
        if self.user_is_home:
            positions = self.get_home_positions()
            team = self.home
        else:
            positions = self.get_away_positions()
            team = self.away
        for p, (x, y, role) in zip(team, positions):
            p.home_x = x
            p.home_y = y

    def closest_players(self, players, x, y, count):
        ranked = sorted(players, key=lambda p: (p.x - x) ** 2 + (p.y - y) ** 2)
        return ranked[:count]

    def triangle_targets(self, tx, ty, radius=70):
        return [
            (tx + radius, ty),
            (tx - radius * 0.5, ty - radius * 0.86),
            (tx - radius * 0.5, ty + radius * 0.86),
        ]

    def ball_carrier(self):
        for p in self.home + self.away:
            if p.has_ball:
                return p
        return None

    def in_penalty_box(self, team, x, y):
        if team == "H":
            left = WIDTH - FIELD_MARGIN - PENALTY_BOX_DEPTH
            right = WIDTH - FIELD_MARGIN
        else:
            left = FIELD_MARGIN
            right = FIELD_MARGIN + PENALTY_BOX_DEPTH
        top = (HEIGHT - COMMENTARY_BAR_H) / 2 - PENALTY_BOX_HEIGHT / 2
        bottom = (HEIGHT - COMMENTARY_BAR_H) / 2 + PENALTY_BOX_HEIGHT / 2
        return left <= x <= right and top <= y <= bottom

    def get_kicker(self, allow_any_team=False, prefer_controlled=False):
        if prefer_controlled and self.controlled:
            if math.hypot(self.controlled.x - self.ball.x, self.controlled.y - self.ball.y) <= KICK_RADIUS:
                self.controlled.has_ball = True
                for p in self.home + self.away:
                    if p is not self.controlled:
                        p.has_ball = False
                return self.controlled
        carrier = self.ball_carrier()
        if carrier:
            return carrier
        players = self.home + self.away if allow_any_team else self.home
        nearest = None
        best = 1e9
        for p in players:
            d = math.hypot(p.x - self.ball.x, p.y - self.ball.y)
            if d < best:
                best = d
                nearest = p
        if nearest and best <= KICK_RADIUS:
            return nearest
        return None

    def pass_ball(self, target, allow_any_team=False, prefer_controlled=False):
        carrier = self.get_kicker(allow_any_team=allow_any_team, prefer_controlled=prefer_controlled)
        if not carrier:
            return
        if carrier.team != "H" and not allow_any_team:
            return
        traits = self.apply_fantasy_player_traits(carrier)
        if random.random() < 0.12:
            self.say("dribble", a=carrier.name)
        accuracy = clamp(0.5 + (carrier.rating - 60) / 120, 0.45, 0.95)
        if "Playmaker" in traits:
            accuracy = min(0.98, accuracy + 0.08)
        if random.random() > accuracy:
            self.last_assist_candidate = None
            self.last_assist_team = None
            self.ball.vx = random.uniform(-PASS_SPEED, PASS_SPEED) * 0.4
            self.ball.vy = random.uniform(-PASS_SPEED, PASS_SPEED) * 0.4
            self.ball_free_ticks = 10
            self.say("pass_fail", a=carrier.name)
            return
        self.stats[carrier.team]["pass_att"] += 1
        self.pending_pass_team = carrier.team
        self.last_assist_candidate = carrier.name
        self.last_assist_team = carrier.team
        dx = target.x - carrier.x
        dy = target.y - carrier.y
        d = math.hypot(dx, dy)
        if d < 1:
            return
        carrier.has_ball = False
        self.ball.x = carrier.x
        self.ball.y = carrier.y
        pass_speed = PASS_SPEED * (1.08 if "Playmaker" in traits else 1.0)
        self.ball.vx = (dx / d) * pass_speed
        self.ball.vy = (dy / d) * pass_speed
        self.last_touch_team = carrier.team
        self.last_touch_name = carrier.name
        self.ball_free_ticks = 10
        self.say("pass", a=carrier.name, b=target.name)

    def shoot_toward(self, goal_x, allow_any_team=False, prefer_controlled=False):
        carrier = self.get_kicker(allow_any_team=allow_any_team, prefer_controlled=prefer_controlled)
        if not carrier:
            return
        if carrier.team != "H" and not allow_any_team:
            return
        traits = self.apply_fantasy_player_traits(carrier)
        self.stats[carrier.team]["shots"] += 1
        if random.random() < 0.25:
            self.say("near_goal", a=carrier.name)
        shot_speed = SHOT_SPEED * clamp(0.85 + (carrier.rating - 60) / 150, 0.8, 1.2)
        if "Finesse Shot" in traits:
            shot_speed *= 1.06
        goal_y = HEIGHT / 2
        dx = goal_x - carrier.x
        dy = goal_y - carrier.y
        d = math.hypot(dx, dy)
        if d < 1:
            return
        carrier.has_ball = False
        self.ball.x = carrier.x
        self.ball.y = carrier.y
        self.ball.vx = (dx / d) * shot_speed
        self.ball.vy = (dy / d) * shot_speed
        accuracy = clamp(0.55 + (carrier.rating - 60) / 110, 0.4, 0.92)
        if "Finesse Shot" in traits:
            accuracy = min(0.97, accuracy + 0.09)
        if random.random() > accuracy:
            self.say("shot_miss", a=carrier.name)
            self.ball_free_ticks = 8
            return
        self.last_touch_team = carrier.team
        self.last_touch_name = carrier.name
        self.ball_free_ticks = 12
        self.say("shot", a=carrier.name)

    def shoot_ball(self):
        if not self.controlled:
            return
        goal_x = WIDTH - FIELD_MARGIN + 10 if self.controlled.team == "H" else FIELD_MARGIN - 10
        self.shoot_toward(goal_x, allow_any_team=True, prefer_controlled=True)

    def tackle_check(self):
        carrier = self.ball_carrier()
        if not carrier:
            return
        if carrier.team == "H":
            for d in self.away:
                if dist(d, carrier) < TACKLE_RADIUS:
                    traits = self.apply_fantasy_player_traits(d)
                    if "Interceptor" not in traits and random.random() < 0.18:
                        continue
                    carrier.has_ball = False
                    d.has_ball = True
                    self.say("tackle_win", a=d.name)
                    self.last_assist_candidate = None
                    self.last_assist_team = None
                    if d.role == "DF":
                        self.register_stat(d.name, "tackles")
                    break
        else:
            for h in self.home:
                if dist(h, carrier) < TACKLE_RADIUS:
                    traits = self.apply_fantasy_player_traits(h)
                    if "Interceptor" not in traits and random.random() < 0.18:
                        continue
                    carrier.has_ball = False
                    h.has_ball = True
                    self.say("tackle_win", a=h.name)
                    self.last_assist_candidate = None
                    self.last_assist_team = None
                    if h.role == "DF":
                        self.register_stat(h.name, "tackles")
                    break

    def manual_tackle(self):
        if self.state != "LIVE" or not self.controlled:
            return
        if self.tackle_cooldown > 0:
            return
        carrier = self.ball_carrier()
        if not carrier or carrier.team != "A":
            return
        if dist(self.controlled, carrier) < TACKLE_RADIUS + 24:
            diff = self.controlled.rating - carrier.rating
            win_chance = clamp(0.55 + diff / 200, 0.35, 0.85)
            if "Interceptor" in self.apply_fantasy_player_traits(self.controlled):
                win_chance = min(0.92, win_chance + 0.12)
            if random.random() < win_chance:
                carrier.has_ball = False
                self.controlled.has_ball = True
                self.say("tackle_win", a=self.controlled.name)
                self.last_assist_candidate = None
                self.last_assist_team = None
                if self.controlled.role == "DF":
                    self.register_stat(self.controlled.name, "tackles")
            else:
                self.say("tackle_miss", a=self.controlled.name)
        else:
            self.say("tackle_miss", a=self.controlled.name)
        self.tackle_cooldown = 25

    def receive_ball(self):
        if self.set_piece_pending:
            return
        if self.ball_carrier():
            return
        if self.ball_free_ticks > 0:
            return
        if self.controlled:
            d = math.hypot(self.controlled.x - self.ball.x, self.controlled.y - self.ball.y)
            if d < CONTROL_RADIUS:
                resist = "Press Resist" in self.apply_fantasy_player_traits(self.controlled)
                pressure = min(math.hypot(p.x - self.controlled.x, p.y - self.controlled.y) for p in self.home + self.away if p is not self.controlled)
                for p in self.home + self.away:
                    p.has_ball = False
                if pressure < 28 and not resist and random.random() < 0.22:
                    self.ball.vx *= 0.4
                    self.ball.vy *= 0.4
                else:
                    self.controlled.has_ball = True
                    self.ball.vx = 0
                    self.ball.vy = 0
                self.last_touch_team = self.controlled.team
                self.last_touch_name = self.controlled.name
                if self.pending_pass_team is not None:
                    if self.controlled.team == self.pending_pass_team:
                        self.stats[self.controlled.team]["pass_cmp"] += 1
                    self.pending_pass_team = None
                return
        nearest = None
        best_d = 1e9
        for p in self.home + self.away:
            d = math.hypot(p.x - self.ball.x, p.y - self.ball.y)
            if d < best_d:
                best_d = d
                nearest = p
        if nearest and best_d < CONTROL_RADIUS:
            nearest.has_ball = True
            self.ball.vx = 0
            self.ball.vy = 0
            self.last_touch_team = nearest.team
            self.last_touch_name = nearest.name
            if self.pending_pass_team is not None:
                if nearest.team == self.pending_pass_team:
                    self.stats[nearest.team]["pass_cmp"] += 1
                self.pending_pass_team = None

    def check_goal(self):
        goal_x = WIDTH - FIELD_MARGIN
        if self.ball.x > goal_x and abs(self.ball.y - HEIGHT / 2) < GOAL_WIDTH / 2:
            scorer = self.last_touch_name
            self.score_h += 1
            self.register_stat(scorer, "goals")
            if self.last_assist_candidate and self.last_assist_team == "H" and self.last_assist_candidate != scorer:
                self.register_stat(self.last_assist_candidate, "assists")
            self.last_assist_candidate = None
            self.last_assist_team = None
            self.kickoff_pending = True
            self.kickoff_team = "A"
            self.reset_positions(kickoff=True)
            self.say("goal", a=scorer, t=self.current_home)

        goal_x = FIELD_MARGIN
        if self.ball.x < goal_x and abs(self.ball.y - HEIGHT / 2) < GOAL_WIDTH / 2:
            scorer = self.last_touch_name
            self.score_a += 1
            self.register_stat(scorer, "goals")
            if self.last_assist_candidate and self.last_assist_team == "A" and self.last_assist_candidate != scorer:
                self.register_stat(self.last_assist_candidate, "assists")
            self.last_assist_candidate = None
            self.last_assist_team = None
            self.kickoff_pending = True
            self.kickoff_team = "H"
            self.reset_positions(kickoff=True)
            self.say("goal", a=scorer, t=self.current_away)

    def update_ball(self):
        carrier = self.ball_carrier()
        if carrier:
            dir_x = 1 if carrier.team == "H" else -1
            offset = 14 if carrier is self.controlled else 10
            target_x = carrier.x + dir_x * offset
            target_y = carrier.y
            self.ball.vx += (target_x - self.ball.x) * BALL_FOLLOW_STIFFNESS
            self.ball.vy += (target_y - self.ball.y) * BALL_FOLLOW_STIFFNESS
            self.ball.vx *= BALL_FOLLOW_DAMP
            self.ball.vy *= BALL_FOLLOW_DAMP
            self.ball.update()
        else:
            self.ball.update()
            # ground friction
            self.ball.vx *= BALL_GROUND_FRICTION
            self.ball.vy *= BALL_GROUND_FRICTION
            self.ball.x = clamp(self.ball.x, FIELD_MARGIN - 20, WIDTH - FIELD_MARGIN + 20)
            self.ball.y = clamp(self.ball.y, FIELD_MARGIN - 40, HEIGHT - FIELD_MARGIN + 40)

    def check_out_of_bounds(self):
        if self.ball_carrier():
            return
        if self.ball.y < FIELD_MARGIN or self.ball.y > HEIGHT - FIELD_MARGIN:
            out_team = self.last_touch_team
            throw_team = "A" if out_team == "H" else "H"
            self.ball.y = FIELD_MARGIN if self.ball.y < FIELD_MARGIN else HEIGHT - FIELD_MARGIN
            self.ball.vx = 0
            self.ball.vy = 0
            if throw_team == "H":
                thrower = self.closest_players(self.home, self.ball.x, self.ball.y, 1)[0]
            else:
                thrower = self.closest_players(self.away, self.ball.x, self.ball.y, 1)[0]
            for p in self.home + self.away:
                p.has_ball = False
            self.set_piece_pending = True
            self.set_piece_taker = thrower
            self.set_piece_type = "throw"
            self.say("throw", t=throw_team)

    def check_endline_out(self):
        if self.ball_carrier():
            return
        if abs(self.ball.y - HEIGHT / 2) < GOAL_WIDTH / 2:
            return
        if self.ball.x < FIELD_MARGIN:
            if self.last_touch_team == "H":
                self.ball.x = FIELD_MARGIN
                self.ball.y = FIELD_MARGIN if self.ball.y < HEIGHT / 2 else HEIGHT - FIELD_MARGIN
                taker = self.closest_players(self.away, self.ball.x, self.ball.y, 1)[0]
                self.say("corner", t="Away")
            else:
                self.ball.x = FIELD_MARGIN + GOAL_BOX_DEPTH
                self.ball.y = HEIGHT / 2
                taker = self.closest_players(self.home, self.ball.x, self.ball.y, 1)[0]
                self.say("goalkick", t="Home")
            self.ball.vx = 0
            self.ball.vy = 0
            for p in self.home + self.away:
                p.has_ball = False
            self.set_piece_pending = True
            self.set_piece_taker = taker
            self.set_piece_type = "corner" if self.last_touch_team == "H" else "goalkick"
        if self.ball.x > WIDTH - FIELD_MARGIN:
            if self.last_touch_team == "A":
                self.ball.x = WIDTH - FIELD_MARGIN
                self.ball.y = FIELD_MARGIN if self.ball.y < HEIGHT / 2 else HEIGHT - FIELD_MARGIN
                taker = self.closest_players(self.home, self.ball.x, self.ball.y, 1)[0]
                self.say("corner", t="Home")
            else:
                self.ball.x = WIDTH - FIELD_MARGIN - GOAL_BOX_DEPTH
                self.ball.y = HEIGHT / 2
                taker = self.closest_players(self.away, self.ball.x, self.ball.y, 1)[0]
                self.say("goalkick", t="Away")
            self.ball.vx = 0
            self.ball.vy = 0
            for p in self.home + self.away:
                p.has_ball = False
            self.set_piece_pending = True
            self.set_piece_taker = taker
            self.set_piece_type = "corner" if self.last_touch_team == "A" else "goalkick"

    def keeper_save(self):
        if self.ball_carrier():
            return
        hk = next((p for p in self.home if p.role == "GK"), None)
        if hk and self.ball.x < FIELD_MARGIN + 30 and abs(self.ball.y - HEIGHT / 2) < GOAL_WIDTH / 2:
            if math.hypot(hk.x - self.ball.x, hk.y - self.ball.y) < KEEPER_RADIUS:
                hk.has_ball = True
                self.ball.vx = 0
                self.ball.vy = 0
                self.say("save")
                teammates = [p for p in self.home if p is not hk]
                if teammates:
                    target = min(teammates, key=lambda p: (p.x - hk.x) ** 2 + (p.y - hk.y) ** 2)
                    self.pass_ball(target, allow_any_team=True)
                return
        ak = next((p for p in self.away if p.role == "GK"), None)
        if ak and self.ball.x > WIDTH - FIELD_MARGIN - 30 and abs(self.ball.y - HEIGHT / 2) < GOAL_WIDTH / 2:
            if math.hypot(ak.x - self.ball.x, ak.y - self.ball.y) < KEEPER_RADIUS:
                ak.has_ball = True
                self.ball.vx = 0
                self.ball.vy = 0
                self.say("save")
                teammates = [p for p in self.away if p is not ak]
                if teammates:
                    target = min(teammates, key=lambda p: (p.x - ak.x) ** 2 + (p.y - ak.y) ** 2)
                    self.pass_ball(target, allow_any_team=True)
                return

    def setup_set_piece_positions(self):
        if not self.set_piece_taker:
            return
        if self.set_piece_type == "corner":
            if self.set_piece_taker.team == "H":
                box_x = WIDTH - FIELD_MARGIN - PENALTY_BOX_DEPTH + 40
                attack = self.home
                defend = self.away
            else:
                box_x = FIELD_MARGIN + PENALTY_BOX_DEPTH - 40
                attack = self.away
                defend = self.home
            box_top = (HEIGHT - COMMENTARY_BAR_H) / 2 - PENALTY_BOX_HEIGHT / 2 + 20
            box_bottom = (HEIGHT - COMMENTARY_BAR_H) / 2 + PENALTY_BOX_HEIGHT / 2 - 20
            lanes = [box_top, (box_top + box_bottom) / 2, box_bottom]
            a_targets = [(box_x + 30, lanes[0]), (box_x + 50, lanes[1]), (box_x + 30, lanes[2])]
            d_targets = [(box_x - 10, lanes[0]), (box_x - 30, lanes[1]), (box_x - 10, lanes[2])]
            ai = 0
            di = 0
            for p in attack:
                if p is self.set_piece_taker or p.role == "GK":
                    continue
                tx, ty = a_targets[ai % len(a_targets)]
                p.home_x = tx
                p.home_y = ty
                ai += 1
            for p in defend:
                if p.role == "GK":
                    continue
                tx, ty = d_targets[di % len(d_targets)]
                p.home_x = tx
                p.home_y = ty
                di += 1
        elif self.set_piece_type == "throw":
            side = -1 if self.set_piece_taker.team == "H" else 1
            support = [p for p in (self.home if self.set_piece_taker.team == "H" else self.away) if p is not self.set_piece_taker]
            for i, p in enumerate(support[:3]):
                p.home_x = self.ball.x + side * (40 + i * 20)
                p.home_y = clamp(self.ball.y + (i - 1) * 40, FIELD_MARGIN + 20, HEIGHT - FIELD_MARGIN - 20)
        elif self.set_piece_type == "goalkick":
            team = self.home if self.set_piece_taker.team == "H" else self.away
            for i, p in enumerate(team):
                if p is self.set_piece_taker:
                    continue
                p.home_x = p.home_x
                p.home_y = p.home_y

    def update_set_piece(self):
        if not self.set_piece_pending or not self.set_piece_taker:
            return
        if self.set_piece_type and self.set_piece_pending:
            self.setup_set_piece_positions()
        self.set_piece_taker.move_toward(self.ball.x, self.ball.y, spd=self.set_piece_taker.speed * 0.9)
        if math.hypot(self.set_piece_taker.x - self.ball.x, self.set_piece_taker.y - self.ball.y) <= KICK_RADIUS:
            for p in self.home + self.away:
                p.has_ball = False
            self.set_piece_taker.has_ball = True
            self.last_touch_team = self.set_piece_taker.team
            self.last_touch_name = self.set_piece_taker.name
            if self.set_piece_type == "corner":
                # auto cross into the box
                attack_team = self.home if self.set_piece_taker.team == "H" else self.away
                aerial_targets = [p for p in attack_team if p is not self.set_piece_taker and "Aerial" in self.apply_fantasy_player_traits(p)]
                if aerial_targets:
                    target_player = min(aerial_targets, key=lambda p: abs(p.x - self.ball.x) + abs(p.y - self.ball.y))
                    target_y = target_player.y
                else:
                    target_y = (HEIGHT - COMMENTARY_BAR_H) / 2 + random.randint(-60, 60)
                if self.set_piece_taker.team == "H":
                    target_x = WIDTH - FIELD_MARGIN - PENALTY_BOX_DEPTH + 40
                else:
                    target_x = FIELD_MARGIN + PENALTY_BOX_DEPTH - 40
                dx = target_x - self.ball.x
                dy = target_y - self.ball.y
                d = math.hypot(dx, dy)
                if d > 0:
                    self.ball.vx = (dx / d) * PASS_SPEED * 0.9
                    self.ball.vy = (dy / d) * PASS_SPEED * 0.9
                self.set_piece_taker.has_ball = False
                self.ball_free_ticks = 6
                self.set_piece_pending = False
            elif self.set_piece_type == "throw":
                team = self.home if self.set_piece_taker.team == "H" else self.away
                target = self.closest_players([p for p in team if p is not self.set_piece_taker], self.ball.x, self.ball.y, 1)[0]
                self.pass_ball(target, allow_any_team=True)
                self.set_piece_pending = False
            elif self.set_piece_type == "goalkick":
                team = self.home if self.set_piece_taker.team == "H" else self.away
                target = self.closest_players([p for p in team if p is not self.set_piece_taker], self.ball.x, self.ball.y, 1)[0]
                self.pass_ball(target, allow_any_team=True)
                self.set_piece_pending = False

    def update_ai(self):
        if self.set_piece_pending:
            for p in self.away:
                if p is self.set_piece_taker:
                    continue
                p.move_toward(p.home_x, p.home_y, spd=p.speed * 0.5)
            return
        press, line, tempo = self.get_team_settings("A")
        press_count = 2 + press
        line_offset = (line - 2) * 25
        tempo_speed = 0.9 + 0.1 * (tempo - 2)
        dribble_bias = DRIBBLE_TENDENCY + (0.1 if tempo == 1 else -0.1 if tempo == 3 else 0)
        carrier = self.ball_carrier()
        if carrier is self.controlled:
            return
        if carrier and carrier.team == "A":
            if self.in_penalty_box("A", carrier.x, carrier.y):
                self.shoot_toward(FIELD_MARGIN - 10, allow_any_team=True)
                return
            dist_to_goal = abs(carrier.x - (FIELD_MARGIN - 10))
            nearest_def = self.closest_players(self.home, carrier.x, carrier.y, 1)[0]
            space = dist(nearest_def, carrier)
            if dist_to_goal < 220 and random.random() < SHOOT_TENDENCY * (0.6 + AI_DIFFICULTY):
                self.shoot_toward(FIELD_MARGIN - 10, allow_any_team=True)
            elif random.random() < dribble_bias:
                carrier.move_toward(
                    FIELD_MARGIN - 10,
                    carrier.y,
                    spd=carrier.speed * (0.95 * AI_DIFFICULTY + 0.25) * tempo_speed,
                )
            else:
                if self.ai_pass_cooldown == 0:
                    target = self.closest_players([p for p in self.away if p is not carrier], carrier.x, carrier.y, 1)[0]
                    self.pass_ball(target, allow_any_team=True)
                    self.ai_pass_cooldown = 20

        if carrier:
            target_x, target_y = carrier.x, carrier.y
        else:
            target_x, target_y = self.ball.x, self.ball.y
        away_field = [p for p in self.away if p.role != "GK"]
        away_chasers = self.closest_players(away_field, target_x, target_y, min(press_count, len(away_field)))
        tri_targets = self.triangle_targets(target_x, target_y, radius=75)

        attack_shift = -60 if carrier and carrier.team == "A" else 0
        defend_shift = (50 + line_offset) if carrier and carrier.team == "H" else 0

        for p in self.away:
            if p is self.controlled:
                continue
            if p is carrier:
                continue
            if p.role == "GK":
                box_min = WIDTH - FIELD_MARGIN - PENALTY_BOX_DEPTH
                box_max = WIDTH - FIELD_MARGIN
                desired_x = box_max - min(PENALTY_BOX_DEPTH * 0.6, max(10, (WIDTH - self.ball.x) * 0.4))
                target_x = clamp(desired_x, box_min, box_max)
                target_y = clamp(self.ball.y, HEIGHT / 2 - PENALTY_BOX_HEIGHT / 2, HEIGHT / 2 + PENALTY_BOX_HEIGHT / 2)
                p.move_toward(target_x, target_y, spd=p.speed * (0.5 + 0.3 * AI_DIFFICULTY))
                continue
            if p in away_chasers:
                if carrier and carrier.team == "H":
                    tx, ty = tri_targets[away_chasers.index(p) % len(tri_targets)]
                    p.move_toward(tx, ty, spd=p.speed * (0.6 * AI_DIFFICULTY + 0.35) * tempo_speed)
                    if dist(p, carrier) < TACKLE_RADIUS + 20:
                        self.tackle_check()
                elif not carrier:
                    p.move_toward(self.ball.x, self.ball.y, spd=p.speed * 0.6 * tempo_speed)
            else:
                if carrier and carrier.team == "A":
                    p.move_toward(p.home_x + attack_shift, p.home_y, spd=p.speed * 0.55 * tempo_speed)
                elif carrier and carrier.team == "H":
                    p.move_toward(p.home_x + defend_shift, p.home_y, spd=p.speed * 0.55 * tempo_speed)
                elif not carrier:
                    sway_x = math.sin(p.y * 0.01 + pygame.time.get_ticks() * 0.001) * 10
                    sway_y = math.cos(p.x * 0.01 + pygame.time.get_ticks() * 0.001) * 8
                    p.move_toward(p.home_x + sway_x, p.home_y + sway_y, spd=p.speed * 0.55 * tempo_speed)
                else:
                    p.move_toward(p.home_x, p.home_y, spd=p.speed * 0.55 * tempo_speed)

    def update_home_ai(self):
        if self.set_piece_pending:
            for p in self.home:
                if p is self.set_piece_taker or p is self.controlled:
                    continue
                p.move_toward(p.home_x, p.home_y, spd=p.speed * 0.5)
            return
        press, line, tempo = self.get_team_settings("H")
        press_count = 2 + press
        line_offset = (line - 2) * 25
        tempo_speed = 0.9 + 0.1 * (tempo - 2)
        dribble_bias = DRIBBLE_TENDENCY + (0.1 if tempo == 1 else -0.1 if tempo == 3 else 0)
        carrier = self.ball_carrier()
        if carrier and carrier.team == "H" and carrier is not self.controlled:
            if self.in_penalty_box("H", carrier.x, carrier.y):
                self.shoot_ball()
                return
        if carrier:
            target_x, target_y = carrier.x, carrier.y
        else:
            target_x, target_y = self.ball.x, self.ball.y
        home_field = [p for p in self.home if p.role != "GK" and p is not self.controlled]
        home_chasers = self.closest_players(home_field, target_x, target_y, min(press_count, len(home_field)))
        tri_targets = self.triangle_targets(target_x, target_y, radius=75)

        attack_shift = 60 if carrier and carrier.team == "H" else 0
        defend_shift = (-50 - line_offset) if carrier and carrier.team == "A" else 0

        for p in self.home:
            if p is self.controlled:
                continue
            if p.role == "GK":
                box_min = FIELD_MARGIN
                box_max = FIELD_MARGIN + PENALTY_BOX_DEPTH
                desired_x = box_min + min(PENALTY_BOX_DEPTH * 0.6, max(10, (self.ball.x - FIELD_MARGIN) * 0.4))
                target_x = clamp(desired_x, box_min, box_max)
                target_y = clamp(self.ball.y, HEIGHT / 2 - PENALTY_BOX_HEIGHT / 2, HEIGHT / 2 + PENALTY_BOX_HEIGHT / 2)
                p.move_toward(target_x, target_y, spd=p.speed * 0.7)
                continue
            if carrier and carrier.team == "H" and carrier is p:
                goal_x = WIDTH - FIELD_MARGIN + 10
                if abs(goal_x - carrier.x) < 220 and random.random() < SHOOT_TENDENCY:
                    self.shoot_ball()
                elif random.random() < dribble_bias:
                    carrier.move_toward(goal_x, carrier.y, spd=carrier.speed * 0.95 * tempo_speed)
                elif self.ai_pass_cooldown == 0:
                    target = self.closest_players([t for t in self.home if t is not carrier], carrier.x, carrier.y, 1)[0]
                    self.pass_ball(target, allow_any_team=True)
                    self.ai_pass_cooldown = 20
                else:
                    carrier.move_toward(goal_x, carrier.y, spd=carrier.speed * 0.9 * tempo_speed)
            elif carrier and carrier.team == "A":
                if p in home_chasers:
                    tx, ty = tri_targets[home_chasers.index(p) % len(tri_targets)]
                    p.move_toward(tx, ty, spd=p.speed * 0.7 * tempo_speed)
                    if dist(p, carrier) < TACKLE_RADIUS + 20:
                        self.tackle_check()
                else:
                    sway_x = math.sin(p.y * 0.01 + pygame.time.get_ticks() * 0.001) * 10
                    sway_y = math.cos(p.x * 0.01 + pygame.time.get_ticks() * 0.001) * 8
                    p.move_toward(p.home_x + defend_shift + sway_x, p.home_y + sway_y, spd=p.speed * 0.55 * tempo_speed)
            elif not carrier:
                if p in home_chasers:
                    p.move_toward(self.ball.x, self.ball.y, spd=p.speed * 0.6 * tempo_speed)
                else:
                    sway_x = math.sin(p.y * 0.01 + pygame.time.get_ticks() * 0.001) * 10
                    sway_y = math.cos(p.x * 0.01 + pygame.time.get_ticks() * 0.001) * 8
                    p.move_toward(p.home_x + sway_x, p.home_y + sway_y, spd=p.speed * 0.55 * tempo_speed)
            else:
                sway_x = math.sin(p.y * 0.01 + pygame.time.get_ticks() * 0.001) * 10
                sway_y = math.cos(p.x * 0.01 + pygame.time.get_ticks() * 0.001) * 8
                p.move_toward(p.home_x + attack_shift + sway_x, p.home_y + sway_y, spd=p.speed * 0.55 * tempo_speed)

    def handle_controls(self, keys):
        if self.state != "LIVE":
            return
        if not self.controlled:
            return
        dx = dy = 0
        if keys[pygame.K_UP]:
            dy -= 1
        if keys[pygame.K_DOWN]:
            dy += 1
        if keys[pygame.K_LEFT]:
            dx -= 1
        if keys[pygame.K_RIGHT]:
            dx += 1
        if dx != 0 or dy != 0:
            d = math.hypot(dx, dy)
            desired_vx = (dx / d) * self.controlled.speed
            desired_vy = (dy / d) * self.controlled.speed
            self.controlled.vx += (desired_vx - self.controlled.vx) * PLAYER_ACCEL
            self.controlled.vy += (desired_vy - self.controlled.vy) * PLAYER_ACCEL
        else:
            self.controlled.vx *= PLAYER_FRICTION
            self.controlled.vy *= PLAYER_FRICTION
        self.controlled.x += self.controlled.vx
        self.controlled.y += self.controlled.vy
        self.controlled.x = clamp(self.controlled.x, FIELD_MARGIN, WIDTH - FIELD_MARGIN)
        self.controlled.y = clamp(self.controlled.y, FIELD_MARGIN, HEIGHT - FIELD_MARGIN)

    def clamp_players(self):
        for p in self.home + self.away:
            if self.set_piece_pending and p is self.set_piece_taker:
                clamped_x = clamp(p.x, FIELD_MARGIN - 12, WIDTH - FIELD_MARGIN + 12)
                clamped_y = clamp(p.y, FIELD_MARGIN - 12, HEIGHT - FIELD_MARGIN + 12)
            else:
                clamped_x = clamp(p.x, FIELD_MARGIN, WIDTH - FIELD_MARGIN)
                clamped_y = clamp(p.y, FIELD_MARGIN, HEIGHT - FIELD_MARGIN)
            if clamped_x != p.x:
                p.vx = 0
            if clamped_y != p.y:
                p.vy = 0
            p.x = clamped_x
            p.y = clamped_y

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.save_active_profile()
                pygame.quit()
                sys.exit(0)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.reconnect_button_rect and self.reconnect_button_rect.collidepoint(event.pos):
                    if self.state in ("ACCOUNT_HOME", "ACCOUNT_LOGIN", "ACCOUNT_CREATE", "ACCOUNT_DEV_LOGIN", "CLOUD_SETTINGS", "MODE_SELECT"):
                        self.reconnect_cloud()
                        continue
            if event.type == pygame.KEYDOWN:
                if self.state == "ACCOUNT_HOME":
                    options = ["Sign In", "Create Account", "Developer Sign In"]
                    if event.key == pygame.K_DOWN:
                        self.account_menu_index = (self.account_menu_index + 1) % len(options)
                    elif event.key == pygame.K_UP:
                        self.account_menu_index = (self.account_menu_index - 1) % len(options)
                    elif event.key == pygame.K_RETURN:
                        targets = ["ACCOUNT_LOGIN", "ACCOUNT_CREATE", "ACCOUNT_DEV_LOGIN"]
                        self.enter_account_state(targets[self.account_menu_index])
                    elif event.key == pygame.K_c:
                        self.cloud_settings_inputs = {
                            "cloud_enabled": True,
                            "cloud_api_url": self.app_settings.get("cloud_api_url", "http://127.0.0.1:8080"),
                        }
                        self.cloud_settings_index = 0
                        self.state = "CLOUD_SETTINGS"
                    elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        self.reconnect_cloud()
                    continue
                if self.state in ("ACCOUNT_LOGIN", "ACCOUNT_CREATE", "ACCOUNT_DEV_LOGIN"):
                    fields = self.auth_fields_for_state()
                    if event.key == pygame.K_ESCAPE:
                        self.state = "ACCOUNT_HOME"
                        self.account_message = ""
                    elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        self.reconnect_cloud()
                    elif event.key == pygame.K_UP:
                        self.account_field_index = (self.account_field_index - 1) % len(fields)
                    elif event.key == pygame.K_DOWN:
                        self.account_field_index = (self.account_field_index + 1) % len(fields)
                    elif event.key == pygame.K_BACKSPACE:
                        field = fields[self.account_field_index]
                        self.account_inputs[field] = self.account_inputs[field][:-1]
                    elif event.key == pygame.K_RETURN:
                        if self.state == "ACCOUNT_CREATE":
                            self.create_account()
                        elif self.state == "ACCOUNT_DEV_LOGIN":
                            self.login_account(require_dev=True)
                        else:
                            self.login_account(require_dev=False)
                    else:
                        field = fields[self.account_field_index]
                        if event.unicode and event.unicode.isprintable() and len(self.account_inputs[field]) < 24:
                            if field == "username":
                                if event.unicode.isalnum() or event.unicode in ("_", "-"):
                                    self.account_inputs[field] += event.unicode.lower()
                            else:
                                self.account_inputs[field] += event.unicode
                    continue
                if self.state == "CLOUD_SETTINGS":
                    fields = ["cloud_mode", "cloud_api_url"]
                    field = fields[self.cloud_settings_index]
                    if event.key == pygame.K_ESCAPE:
                        self.state = "ACCOUNT_HOME"
                        self.account_message = ""
                    elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        self.reconnect_cloud()
                    elif event.key == pygame.K_UP:
                        self.cloud_settings_index = (self.cloud_settings_index - 1) % len(fields)
                    elif event.key == pygame.K_DOWN:
                        self.cloud_settings_index = (self.cloud_settings_index + 1) % len(fields)
                    elif event.key == pygame.K_RETURN:
                        if field == "cloud_api_url":
                            self.apply_cloud_settings()
                    elif event.key == pygame.K_BACKSPACE and field == "cloud_api_url":
                        self.cloud_settings_inputs[field] = self.cloud_settings_inputs[field][:-1]
                    else:
                        if field == "cloud_api_url" and event.unicode and event.unicode.isprintable() and len(self.cloud_settings_inputs[field]) < 80:
                            self.cloud_settings_inputs[field] += event.unicode
                    continue
                if self.state == "MODE_SELECT":
                    if event.key == pygame.K_DOWN or event.key == pygame.K_UP:
                        self.mode_select_index = 1 - self.mode_select_index
                    elif event.key == pygame.K_RETURN:
                        if self.mode_select_index == 0:
                            self.load_profile_mode("CAREER")
                        else:
                            self.load_profile_mode("FANTASY")
                    elif event.key == pygame.K_c:
                        self.cloud_settings_inputs = {
                            "cloud_enabled": True,
                            "cloud_api_url": self.app_settings.get("cloud_api_url", "http://127.0.0.1:8080"),
                        }
                        self.cloud_settings_index = 0
                        self.state = "CLOUD_SETTINGS"
                    elif event.key == pygame.K_u:
                        record = self.active_account_record() or {}
                        if record.get("is_developer"):
                            self.fetch_registered_users()
                            self.fetch_admin_status()
                            self.registered_users_index = 0
                            self.state = "DEV_REGISTERED_USERS"
                    elif event.key == pygame.K_ESCAPE:
                        self.logout_account()
                    continue
                if self.state == "FANTASY_TEAM_NAME":
                    if event.key == pygame.K_BACKSPACE:
                        self.fantasy_team_name = self.fantasy_team_name[:-1]
                    elif event.key == pygame.K_RETURN:
                        self.finish_fantasy_team_setup()
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "MODE_SELECT"
                    else:
                        if event.unicode and event.unicode.isprintable() and len(self.fantasy_team_name) < 16:
                            if event.unicode.isalnum() or event.unicode == " ":
                                self.fantasy_team_name += event.unicode
                    continue
                if self.state == "DEV_REGISTERED_USERS":
                    users = self.filtered_registered_users()
                    selected = self.selected_registered_user()
                    if event.key == pygame.K_ESCAPE:
                        self.state = "MODE_SELECT"
                    elif event.key == pygame.K_TAB:
                        self.dev_console_tab = (self.dev_console_tab + 1) % len(self.developer_tabs())
                    elif event.key == pygame.K_DOWN and users:
                        self.registered_users_index = (self.registered_users_index + 1) % len(users)
                    elif event.key == pygame.K_UP and users:
                        self.registered_users_index = (self.registered_users_index - 1) % len(users)
                    elif event.key == pygame.K_BACKSPACE:
                        if self.dev_console_tab == 0:
                            self.dev_search_query = self.dev_search_query[:-1]
                        elif self.dev_console_tab == 3:
                            self.dev_announcement_input = self.dev_announcement_input[:-1]
                    elif event.key == pygame.K_RIGHT:
                        if self.dev_console_tab == 1:
                            self.dev_coin_delta_index = (self.dev_coin_delta_index + 1) % len(self.developer_coin_amounts())
                        elif self.dev_console_tab == 2 and users:
                            self.dev_pack_index = (self.dev_pack_index + 1) % len(self.developer_pack_ids())
                    elif event.key == pygame.K_LEFT:
                        if self.dev_console_tab == 1:
                            self.dev_coin_delta_index = (self.dev_coin_delta_index - 1) % len(self.developer_coin_amounts())
                        elif self.dev_console_tab == 2 and users:
                            self.dev_pack_index = (self.dev_pack_index - 1) % len(self.developer_pack_ids())
                    elif event.key == pygame.K_RIGHTBRACKET and self.dev_console_tab == 1 and self.developer_card_catalog():
                        self.dev_card_index = (self.dev_card_index + 1) % len(self.developer_card_catalog())
                    elif event.key == pygame.K_LEFTBRACKET and self.dev_console_tab == 1 and self.developer_card_catalog():
                        self.dev_card_index = (self.dev_card_index - 1) % len(self.developer_card_catalog())
                    elif event.key == pygame.K_PERIOD and self.dev_console_tab == 1:
                        self.dev_pack_index = (self.dev_pack_index + 1) % len(self.developer_pack_ids())
                    elif event.key == pygame.K_COMMA and self.dev_console_tab == 1:
                        self.dev_pack_index = (self.dev_pack_index - 1) % len(self.developer_pack_ids())
                    elif event.key == pygame.K_RETURN:
                        if self.dev_console_tab == 3:
                            self.admin_update_settings(announcement=self.dev_announcement_input)
                        else:
                            self.fetch_registered_users()
                            self.fetch_admin_status()
                    elif selected and self.dev_console_tab == 0:
                        if event.key == pygame.K_b:
                            self.admin_user_action(selected.get("username"), "unban" if selected.get("is_banned") else "ban")
                        elif event.key == pygame.K_v:
                            self.admin_user_action(selected.get("username"), "unsuspend" if selected.get("is_suspended") else "suspend", days=7)
                        elif event.key == pygame.K_p:
                            self.admin_user_action(selected.get("username"), "revoke_developer" if selected.get("is_developer") else "promote_developer")
                        elif event.key == pygame.K_w:
                            self.admin_user_action(selected.get("username"), "reset_password", new_password="legend123")
                        elif event.key == pygame.K_f:
                            self.admin_user_action(selected.get("username"), "repair_account")
                    elif selected and self.dev_console_tab == 1:
                        amount = self.developer_coin_amounts()[self.dev_coin_delta_index]
                        if event.key == pygame.K_c:
                            self.admin_user_action(selected.get("username"), "grant_coins", amount=amount)
                        elif event.key == pygame.K_x:
                            self.admin_user_action(selected.get("username"), "grant_coins", amount=-amount)
                        elif event.key == pygame.K_o:
                            pack_ids = self.developer_pack_ids()
                            self.admin_user_action(selected.get("username"), "grant_packs", pack_id=pack_ids[self.dev_pack_index % len(pack_ids)], amount=1)
                        elif event.key == pygame.K_l:
                            pack_ids = self.developer_pack_ids()
                            self.admin_user_action(selected.get("username"), "grant_packs", pack_id=pack_ids[self.dev_pack_index % len(pack_ids)], amount=-1)
                        elif event.key == pygame.K_g and self.developer_card_catalog():
                            card = self.developer_card_catalog()[self.dev_card_index % len(self.developer_card_catalog())]
                            self.admin_user_action(selected.get("username"), "add_card", card=card)
                        elif event.key == pygame.K_r:
                            snapshot = selected.get("fantasy_snapshot") or {}
                            roster = snapshot.get("fantasy_roster", [])
                            if roster:
                                self.admin_user_action(selected.get("username"), "remove_card", card_key=roster[0].get("card_key"))
                    elif selected and self.dev_console_tab == 2:
                        if event.key == pygame.K_d:
                            self.admin_tournament_action(selected.get("username"), "reset_division")
                        elif event.key == pygame.K_t:
                            self.admin_tournament_action(selected.get("username"), "reset_tournament")
                        elif event.key == pygame.K_a:
                            self.admin_tournament_action(selected.get("username"), "award_tournament_coins", amount=self.developer_coin_amounts()[self.dev_coin_delta_index])
                    elif self.dev_console_tab == 3:
                        if event.key == pygame.K_m:
                            settings = self.dev_admin_status.get("settings", {})
                            self.admin_update_settings(maintenance_mode=not settings.get("maintenance_mode", False))
                        elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                            keys = ["tournaments", "market", "objectives"]
                            target_key = keys[[pygame.K_1, pygame.K_2, pygame.K_3].index(event.key)]
                            disabled = dict(self.dev_admin_status.get("settings", {}).get("disabled_modes", {}))
                            disabled[target_key] = not disabled.get(target_key, False)
                            self.admin_update_settings(disabled_modes=disabled)
                        elif event.unicode and event.unicode.isprintable() and len(self.dev_announcement_input) < 240:
                            self.dev_announcement_input += event.unicode
                    elif selected and self.dev_console_tab == 4:
                        if event.key == pygame.K_f:
                            self.admin_user_action(selected.get("username"), "repair_account")
                    elif self.dev_console_tab == 0 and event.unicode and event.unicode.isprintable() and len(self.dev_search_query) < 24:
                        self.dev_search_query += event.unicode.lower()
                    continue
                if self.state == "FANTASY_BUILDER":
                    if event.key == pygame.K_p:
                        self.open_pack_shop("FANTASY_BUILDER")
                    elif event.key == pygame.K_s:
                        if self.start_fantasy_season():
                            pass
                        else:
                            self.add_commentary("Select at least 11 players")
                    elif event.key == pygame.K_ESCAPE:
                        self.save_active_profile()
                        self.state = "MODE_SELECT"
                    continue
                if self.state == "PACK_SHOP":
                    packs = self.visible_fantasy_packs()
                    pack_count = len(packs)
                    cols = 4
                    if not packs:
                        self.close_pack_shop()
                        continue
                    if event.key == pygame.K_LEFT:
                        self.pack_shop_index = (self.pack_shop_index - 1) % pack_count
                    elif event.key == pygame.K_RIGHT:
                        self.pack_shop_index = (self.pack_shop_index + 1) % pack_count
                    elif event.key == pygame.K_UP:
                        self.pack_shop_index = (self.pack_shop_index - cols) % pack_count
                    elif event.key == pygame.K_DOWN:
                        self.pack_shop_index = (self.pack_shop_index + cols) % pack_count
                    elif event.key == pygame.K_RETURN:
                        shop_pack = packs[self.pack_shop_index]
                        if self.fantasy_coins >= shop_pack["cost"]:
                            self.fantasy_coins -= shop_pack["cost"]
                            self.store_pack(shop_pack["id"], source="Shop")
                        else:
                            self.add_commentary("Not enough coins")
                    elif event.key == pygame.K_m:
                        self.open_my_packs(self.pack_shop_return_state or "LEAGUE")
                    elif event.key == pygame.K_o:
                        shop_pack = packs[self.pack_shop_index]
                        self.open_pack_odds(shop_pack["id"], "PACK_SHOP")
                    elif event.key == pygame.K_e:
                        self.roll_pack_event(advance=True)
                        self.add_commentary("Pack event refreshed")
                    elif event.key == pygame.K_ESCAPE:
                        self.close_pack_shop()
                    continue
                if self.state == "MY_PACKS":
                    if event.key == pygame.K_UP:
                        self.my_packs_index = max(0, self.my_packs_index - 1)
                    elif event.key == pygame.K_DOWN:
                        self.my_packs_index = min(max(0, len(self.my_packs) - 1), self.my_packs_index + 1)
                    elif event.key == pygame.K_RETURN:
                        self.pack_open_return_state = "MY_PACKS"
                        self.open_owned_pack()
                    elif event.key == pygame.K_o and self.my_packs:
                        pack_id = self.my_packs[max(0, min(self.my_packs_index, len(self.my_packs) - 1))]
                        self.open_pack_odds(pack_id, "MY_PACKS")
                    elif event.key == pygame.K_ESCAPE:
                        self.state = self.pack_shop_return_state or "LEAGUE"
                    continue
                if self.state == "PACK_ODDS":
                    if event.key == pygame.K_RETURN:
                        if self.pack_detail_return_state == "MY_PACKS":
                            self.pack_open_return_state = "MY_PACKS"
                            self.open_owned_pack()
                        else:
                            pack = self.get_pack_by_id(self.pack_detail_pack_id)
                            if self.fantasy_coins >= pack["cost"]:
                                self.fantasy_coins -= pack["cost"]
                                self.store_pack(pack["id"], source="Shop")
                                self.state = "PACK_SHOP"
                            else:
                                self.add_commentary("Not enough coins")
                    elif event.key == pygame.K_ESCAPE:
                        self.state = self.pack_detail_return_state or "PACK_SHOP"
                    continue
                if self.state == "PACK_OPENING":
                    continue
                if self.state == "PACK_SUMMARY":
                    if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                        self.state = self.pack_open_return_state or "LEAGUE"
                    continue
                if self.state == "FANTASY_SBC":
                    catalog = self.fantasy_sbc_catalog()
                    if event.key == pygame.K_UP:
                        self.fantasy_sbc_index = (self.fantasy_sbc_index - 1) % len(catalog)
                    elif event.key == pygame.K_DOWN:
                        self.fantasy_sbc_index = (self.fantasy_sbc_index + 1) % len(catalog)
                    elif event.key == pygame.K_RETURN:
                        self.start_sbc_build(self.fantasy_sbc_index)
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "LEAGUE"
                    continue
                if self.state == "FANTASY_SBC_BUILD":
                    if event.key == pygame.K_LEFT:
                        self.fantasy_sbc_col = max(0, self.fantasy_sbc_col - 1)
                        self.fantasy_sbc_idx = 0
                    elif event.key == pygame.K_RIGHT:
                        self.fantasy_sbc_col = min(2, self.fantasy_sbc_col + 1)
                        self.fantasy_sbc_idx = 0
                    elif event.key == pygame.K_TAB:
                        self.fantasy_sbc_col = (self.fantasy_sbc_col + 1) % 3
                        self.fantasy_sbc_idx = 0
                    elif event.key == pygame.K_UP:
                        self.fantasy_sbc_idx = max(0, self.fantasy_sbc_idx - 1)
                    elif event.key == pygame.K_DOWN:
                        limit = (
                            len(self.fantasy_sbc_slots)
                            if self.fantasy_sbc_col == 0
                            else len(self.get_sbc_source_list(self.fantasy_sbc_col))
                        )
                        self.fantasy_sbc_idx = min(max(0, limit - 1), self.fantasy_sbc_idx + 1)
                    elif event.key == pygame.K_RETURN:
                        if self.fantasy_sbc_col == 0:
                            self.remove_card_from_sbc(self.fantasy_sbc_idx)
                        else:
                            source = self.get_sbc_source_list(self.fantasy_sbc_col)
                            if 0 <= self.fantasy_sbc_idx < len(source):
                                self.add_card_to_sbc(source[self.fantasy_sbc_idx])
                    elif event.key == pygame.K_SPACE:
                        self.submit_active_sbc()
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "FANTASY_SBC"
                    continue
                if self.state == "FANTASY_OBJECTIVES":
                    flat = self.flat_objectives()
                    if flat:
                        if event.key == pygame.K_UP:
                            self.fantasy_objective_index = (self.fantasy_objective_index - 1) % len(flat)
                        elif event.key == pygame.K_DOWN:
                            self.fantasy_objective_index = (self.fantasy_objective_index + 1) % len(flat)
                        elif event.key == pygame.K_RETURN:
                            section, idx = flat[self.fantasy_objective_index]
                            self.claim_objective(section, idx)
                    if event.key == pygame.K_ESCAPE:
                        self.state = "LEAGUE"
                    continue
                if self.state == "FANTASY_COLLECTION":
                    total = max(1, len(self.filtered_collection_cards()))
                    cols = 4
                    if event.key == pygame.K_UP:
                        self.fantasy_collection_index = max(0, self.fantasy_collection_index - cols)
                    elif event.key == pygame.K_DOWN:
                        self.fantasy_collection_index = min(total - 1, self.fantasy_collection_index + cols)
                    elif event.key == pygame.K_LEFT:
                        self.fantasy_collection_index = max(0, self.fantasy_collection_index - 1)
                    elif event.key == pygame.K_RIGHT:
                        self.fantasy_collection_index = min(total - 1, self.fantasy_collection_index + 1)
                    elif event.key == pygame.K_g:
                        self.fantasy_collection_filter = (self.fantasy_collection_filter + 1) % len(self.collection_filter_options())
                        self.fantasy_collection_index = 0
                    elif event.key == pygame.K_TAB:
                        self.fantasy_collection_sort = (self.fantasy_collection_sort + 1) % len(self.collection_sort_options())
                        self.fantasy_collection_index = 0
                    elif event.key == pygame.K_f and self.fantasy_roster:
                        cards = self.filtered_collection_cards()
                        if cards:
                            self.toggle_favorite_card(cards[self.fantasy_collection_index])
                    elif event.key == pygame.K_r:
                        self.open_fantasy_market()
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "LEAGUE"
                    continue
                if self.state == "FANTASY_MARKET":
                    total = max(1, len(self.fantasy_market_offers))
                    if event.key == pygame.K_UP:
                        self.fantasy_market_index = max(0, self.fantasy_market_index - 1)
                    elif event.key == pygame.K_DOWN:
                        self.fantasy_market_index = min(total - 1, self.fantasy_market_index + 1)
                    elif event.key == pygame.K_RETURN:
                        self.buy_market_card(self.fantasy_market_index)
                    elif event.key == pygame.K_r:
                        self.refresh_fantasy_market()
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "LEAGUE"
                    continue
                if self.state == "FANTASY_EVOLUTIONS":
                    total = max(1, len(self.fantasy_roster))
                    if event.key == pygame.K_UP:
                        self.fantasy_evolution_index = max(0, self.fantasy_evolution_index - 1)
                    elif event.key == pygame.K_DOWN:
                        self.fantasy_evolution_index = min(total - 1, self.fantasy_evolution_index + 1)
                    elif event.key == pygame.K_LEFT:
                        self.fantasy_evolution_choice = max(0, self.fantasy_evolution_choice - 1)
                    elif event.key == pygame.K_RIGHT:
                        self.fantasy_evolution_choice = min(1, self.fantasy_evolution_choice + 1)
                    elif event.key == pygame.K_RETURN:
                        self.apply_fantasy_evolution(self.fantasy_evolution_index, self.fantasy_evolution_choice)
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "LEAGUE"
                    continue
                if self.state == "FANTASY_COMPETITIONS":
                    menu = self.fantasy_competition_menu()
                    if event.key == pygame.K_UP:
                        self.fantasy_competition_index = (self.fantasy_competition_index - 1) % len(menu)
                    elif event.key == pygame.K_DOWN:
                        self.fantasy_competition_index = (self.fantasy_competition_index + 1) % len(menu)
                    elif event.key == pygame.K_RETURN:
                        self.fantasy_active_competition = menu[self.fantasy_competition_index][0]
                        if self.fantasy_active_competition == "online_tournament":
                            data = self.fetch_online_tournament_status()
                            if data is not None:
                                self.state = "ONLINE_TOURNAMENTS"
                        elif self.fantasy_active_competition == "draft":
                            self.open_fantasy_draft(reset=not self.fantasy_draft_active)
                        else:
                            self.state = "LEAGUE"
                    elif event.key == pygame.K_d:
                        self.open_fantasy_draft(reset=not self.fantasy_draft_active)
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "LEAGUE"
                    continue
                if self.state == "FANTASY_CLUB":
                    total = 5
                    if event.key == pygame.K_UP:
                        self.fantasy_club_cursor = (self.fantasy_club_cursor - 1) % total
                    elif event.key == pygame.K_DOWN:
                        self.fantasy_club_cursor = (self.fantasy_club_cursor + 1) % total
                    elif event.key == pygame.K_LEFT:
                        if self.fantasy_club_cursor == 0:
                            self.fantasy_club_custom["badge"] = (self.fantasy_club_custom.get("badge", 0) - 1) % len(FANTASY_CLUB_BADGES)
                        elif self.fantasy_club_cursor == 1:
                            self.fantasy_club_custom["primary"] = (self.fantasy_club_custom.get("primary", 0) - 1) % len(FANTASY_CLUB_PALETTES)
                        elif self.fantasy_club_cursor == 2:
                            self.fantasy_club_custom["secondary"] = (self.fantasy_club_custom.get("secondary", 5) - 1) % len(FANTASY_CLUB_PALETTES)
                        elif self.fantasy_club_cursor == 3:
                            self.fantasy_club_custom["stadium"] = (self.fantasy_club_custom.get("stadium", 0) - 1) % len(FANTASY_STADIUM_OPTIONS)
                        self.ensure_fantasy_club_defaults()
                        self.apply_fantasy_club_identity()
                    elif event.key == pygame.K_RIGHT:
                        if self.fantasy_club_cursor == 0:
                            self.fantasy_club_custom["badge"] = (self.fantasy_club_custom.get("badge", 0) + 1) % len(FANTASY_CLUB_BADGES)
                        elif self.fantasy_club_cursor == 1:
                            self.fantasy_club_custom["primary"] = (self.fantasy_club_custom.get("primary", 0) + 1) % len(FANTASY_CLUB_PALETTES)
                        elif self.fantasy_club_cursor == 2:
                            self.fantasy_club_custom["secondary"] = (self.fantasy_club_custom.get("secondary", 5) + 1) % len(FANTASY_CLUB_PALETTES)
                        elif self.fantasy_club_cursor == 3:
                            self.fantasy_club_custom["stadium"] = (self.fantasy_club_custom.get("stadium", 0) + 1) % len(FANTASY_STADIUM_OPTIONS)
                        self.ensure_fantasy_club_defaults()
                        self.apply_fantasy_club_identity()
                    elif event.key == pygame.K_s:
                        self.export_squad_share_code()
                    elif event.key == pygame.K_BACKSPACE and self.fantasy_club_cursor == 4:
                        self.fantasy_share_input = self.fantasy_share_input[:-1]
                    elif event.key == pygame.K_RETURN and self.fantasy_club_cursor == 4:
                        self.import_squad_share_code(self.fantasy_share_input)
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "LEAGUE"
                    else:
                        if self.fantasy_club_cursor == 4 and event.unicode and event.unicode.isprintable() and len(self.fantasy_share_input) < 240:
                            self.fantasy_share_input += event.unicode
                    continue
                if self.state == "ONLINE_TOURNAMENTS":
                    leaderboard = self.online_tournament_data.get("leaderboard", [])
                    if event.key == pygame.K_UP and leaderboard:
                        self.online_tournament_index = max(0, self.online_tournament_index - 1)
                    elif event.key == pygame.K_DOWN and leaderboard:
                        self.online_tournament_index = min(len(leaderboard) - 1, self.online_tournament_index + 1)
                    elif event.key == pygame.K_r:
                        self.fetch_online_tournament_status()
                    elif event.key == pygame.K_b:
                        self.submit_online_tournament_squad()
                    elif event.key == pygame.K_c:
                        self.claim_online_tournament_rewards()
                    elif event.key == pygame.K_SPACE:
                        self.play_online_tournament_match()
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "FANTASY_COMPETITIONS"
                    continue
                if self.state == "FANTASY_DRAFT":
                    if event.key == pygame.K_LEFT:
                        self.fantasy_draft_index = max(0, self.fantasy_draft_index - 1)
                    elif event.key == pygame.K_RIGHT:
                        self.fantasy_draft_index = min(max(0, len(self.fantasy_draft_options) - 1), self.fantasy_draft_index + 1)
                    elif event.key == pygame.K_RETURN:
                        self.complete_draft_pick()
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "LEAGUE"
                    continue
                if self.state == "FANTASY_CHAMPIONS_BRACKET":
                    if event.key in (pygame.K_ESCAPE, pygame.K_k, pygame.K_o):
                        self.state = "LEAGUE"
                    continue
                if self.state == "FANTASY_PLAYER_PICK":
                    if event.key == pygame.K_LEFT:
                        self.fantasy_player_pick_index = max(0, self.fantasy_player_pick_index - 1)
                    elif event.key == pygame.K_RIGHT:
                        self.fantasy_player_pick_index = min(len(self.fantasy_player_pick_options) - 1, self.fantasy_player_pick_index + 1)
                    elif event.key == pygame.K_RETURN:
                        self.claim_player_pick()
                    continue
                if self.state == "TEAM_SELECT":
                    if event.key == pygame.K_DOWN:
                        self.selected_index = (self.selected_index + 1) % len(TEAMS)
                    elif event.key == pygame.K_UP:
                        self.selected_index = (self.selected_index - 1) % len(TEAMS)
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "MODE_SELECT"
                    elif event.key == pygame.K_RETURN:
                        self.user_team = TEAMS[self.selected_index]
                        self.selected_player_index = 0
                        self.state = "PLAYER_SELECT"
                        self.add_commentary(f"Selected {self.user_team}")
                elif self.state == "PLAYER_SELECT":
                    if event.key == pygame.K_DOWN:
                        self.selected_player_index = (self.selected_player_index + 1) % 11
                    elif event.key == pygame.K_UP:
                        self.selected_player_index = (self.selected_player_index - 1) % 11
                    elif event.key == pygame.K_ESCAPE:
                        self.state = "TEAM_SELECT"
                    elif event.key == pygame.K_RETURN:
                        self.user_player_index = self.selected_player_index
                        self.init_league()
                        self.state = "LEAGUE"
                        self.save_active_profile()
                        lineup = TEAM_LINEUPS.get(self.user_team, DEFAULT_LINEUP)
                        entry = lineup[self.user_player_index] if self.user_player_index < len(lineup) else (f"H{self.user_player_index+1}", self.user_player_index + 1)
                        name, _ = lineup_name_number(entry, self.user_player_index)
                        self.add_commentary(f"Controlling {name}")
                elif self.state == "LEAGUE":
                    if event.key == pygame.K_TAB:
                        pages = ["HOME", "TABLE", "STATS"]
                        idx = pages.index(self.league_page) if self.league_page in pages else 0
                        self.league_page = pages[(idx + 1) % len(pages)]
                    elif event.key == pygame.K_c:
                        self.cloud_settings_inputs = {
                            "cloud_enabled": True,
                            "cloud_api_url": self.app_settings.get("cloud_api_url", "http://127.0.0.1:8080"),
                        }
                        self.cloud_settings_index = 0
                        self.state = "CLOUD_SETTINGS"
                    elif event.key == pygame.K_ESCAPE:
                        self.save_active_profile()
                        self.state = "MODE_SELECT"
                    elif event.key == pygame.K_q:
                        self.logout_account()
                    elif event.key == pygame.K_u:
                        record = self.active_account_record() or {}
                        if record.get("is_developer"):
                            self.fetch_registered_users()
                            self.fetch_admin_status()
                            self.registered_users_index = 0
                            self.state = "DEV_REGISTERED_USERS"
                    elif event.key == pygame.K_SPACE:
                        self.start_week()
                    elif event.key == pygame.K_s and self.game_mode != "FANTASY":
                        self.skip_to_end_of_season()
                    elif event.key == pygame.K_t:
                        if self.game_mode != "FANTASY" and self.user_budget >= 2:
                            self.user_budget -= 2
                            self.user_form = clamp(self.user_form + 0.03, 0.9, 1.2)
                            self.add_commentary("Training completed")
                    elif event.key == pygame.K_c:
                        self.show_calendar = not self.show_calendar
                    elif event.key == pygame.K_o:
                        if self.game_mode == "FANTASY":
                            self.state = "FANTASY_COMPETITIONS"
                        else:
                            self.show_cup_bracket = not self.show_cup_bracket
                    elif event.key == pygame.K_k and self.game_mode == "FANTASY" and self.fantasy_active_competition == "champions":
                        self.state = "FANTASY_CHAMPIONS_BRACKET"
                    elif event.key == pygame.K_a:
                        if self.game_mode == "FANTASY":
                            self.state = "FANTASY_OBJECTIVES"
                        else:
                            self.show_academy = False
                            self.state = "ACADEMY"
                    elif event.key == pygame.K_b and self.game_mode == "FANTASY":
                        self.state = "FANTASY_SBC"
                    elif event.key == pygame.K_j and self.game_mode == "FANTASY":
                        self.state = "FANTASY_OBJECTIVES"
                    elif event.key == pygame.K_n and self.game_mode == "FANTASY":
                        self.state = "FANTASY_COLLECTION"
                    elif event.key == pygame.K_d and self.game_mode == "FANTASY":
                        self.open_fantasy_draft(reset=not self.fantasy_draft_active)
                    elif event.key == pygame.K_r and self.game_mode == "FANTASY":
                        self.open_fantasy_market()
                    elif event.key == pygame.K_m and self.game_mode == "FANTASY":
                        self.open_my_packs("LEAGUE")
                    elif event.key == pygame.K_e and self.game_mode == "FANTASY":
                        self.state = "FANTASY_EVOLUTIONS"
                    elif event.key == pygame.K_h and self.game_mode == "FANTASY":
                        self.state = "FANTASY_CLUB"
                    elif event.key == pygame.K_y:
                        self.run_youth_intake()
                    elif event.key == pygame.K_p and self.show_academy:
                        self.promote_academy_player(self.academy_index)
                    elif event.key == pygame.K_p and self.game_mode == "FANTASY":
                        self.open_pack_shop("LEAGUE")
                    elif event.key == pygame.K_UP and self.show_academy and not self.transfer_window:
                        self.academy_index = max(0, self.academy_index - 1)
                    elif event.key == pygame.K_DOWN and self.show_academy and not self.transfer_window:
                        if self.academy:
                            self.academy_index = min(len(self.academy) - 1, self.academy_index + 1)
                    elif event.key == pygame.K_w:
                        if self.game_mode == "FANTASY":
                            self.open_pack_shop("LEAGUE")
                        elif not self.transfer_window and self.transfer_window_active():
                            self.open_transfer_window()
                    elif event.key == pygame.K_ESCAPE:
                        if self.transfer_window:
                            self.transfer_window = False
                    elif self.transfer_window and event.key == pygame.K_UP:
                        self.selected_index = (self.selected_index - 1) % max(1, len(self.transfer_offers))
                    elif self.transfer_window and event.key == pygame.K_DOWN:
                        self.selected_index = (self.selected_index + 1) % max(1, len(self.transfer_offers))
                    elif self.transfer_window and event.key == pygame.K_RETURN:
                        if self.transfer_offers:
                            offer = self.transfer_offers[self.selected_index % len(self.transfer_offers)]
                            if self.user_budget >= offer["value"]:
                                self.user_budget -= offer["value"]
                                self.user_form = clamp(self.user_form + 0.04, 0.9, 1.3)
                                self.add_commentary(f"Signed {offer['name']}")
                                rating = offer.get("rating", random.randint(50, 100))
                                suggested_number = offer.get("number", random.randint(1, 99))
                                assigned_number = self.assign_unique_number(self.user_team, suggested_number)
                                player_tuple = (offer["name"], assigned_number, rating)
                                self.user_reserves.append(player_tuple)
                                TEAM_LINEUPS.setdefault(self.user_team, []).append(player_tuple)
                                self.replace_sold_player(offer["team"], offer["name"])
                                self.transfer_offers.remove(offer)
                            else:
                                self.add_commentary("Not enough budget")
                elif self.state == "ACADEMY":
                    if event.key == pygame.K_ESCAPE:
                        self.state = "LEAGUE"
                    elif event.key == pygame.K_y:
                        self.run_youth_intake()
                    elif event.key == pygame.K_p:
                        self.promote_academy_player(self.academy_index)
                    elif event.key == pygame.K_UP:
                        self.academy_index = max(0, self.academy_index - 1)
                    elif event.key == pygame.K_DOWN:
                        if self.academy:
                            self.academy_index = min(len(self.academy) - 1, self.academy_index + 1)
                elif self.state == "LINEUP":
                    if event.key == pygame.K_h:
                        self.home_kit_index = (self.home_kit_index + 1) % 3
                    elif event.key == pygame.K_j:
                        self.away_kit_index = (self.away_kit_index + 1) % 3
                    if event.key == pygame.K_ESCAPE:
                        if self.lineup_pick is not None:
                            self.lineup_pick = None
                            self.dragging_lineup = None
                            self.message = "Swap cancelled"
                        else:
                            self.lineup_pick = None
                            self.dragging_lineup = None
                            self.state = "LEAGUE"
                            self.message = ""
                    elif event.key == pygame.K_LEFT:
                        self.lineup_col = 0
                        self.lineup_idx = min(self.lineup_idx, len(self.user_starting) - 1)
                    elif event.key == pygame.K_RIGHT:
                        self.lineup_col = 1
                        self.lineup_idx = min(self.lineup_idx, len(self.user_bench) - 1)
                    elif event.key == pygame.K_TAB:
                        self.lineup_col = (self.lineup_col + 1) % 3
                        max_idx = len(self.get_lineup_list(self.lineup_col)) - 1
                        self.lineup_idx = max(0, min(self.lineup_idx, max_idx))
                    elif event.key == pygame.K_UP:
                        self.lineup_idx = max(0, self.lineup_idx - 1)
                    elif event.key == pygame.K_DOWN:
                        self.lineup_idx = min(
                            (len(self.user_starting) - 1)
                            if self.lineup_col == 0
                            else (len(self.user_bench) - 1)
                            if self.lineup_col == 1
                            else (len(self.user_reserves) - 1),
                            self.lineup_idx + 1,
                        )
                    elif event.key == pygame.K_RETURN:
                        if self.lineup_pick is None:
                            self.lineup_pick = (self.lineup_col, self.lineup_idx)
                        else:
                            a_col, a_idx = self.lineup_pick
                            self.swap_lineup(a_col, a_idx, self.lineup_col, self.lineup_idx)
                            self.lineup_pick = None
                    elif event.key == pygame.K_SPACE:
                        if self.pending_fixture:
                            self.start_match()
                elif event.type == pygame.MOUSEBUTTONDOWN and self.state == "LINEUP":
                    for key, rect in self.lineup_rects.items():
                        if rect.collidepoint(event.pos):
                            self.dragging_lineup = key
                            self.lineup_pick = key
                            break
                elif event.type == pygame.MOUSEBUTTONUP and self.state == "LINEUP" and self.dragging_lineup:
                    for key, rect in self.lineup_rects.items():
                        if rect.collidepoint(event.pos) and key != self.dragging_lineup:
                            self.swap_lineup(self.dragging_lineup[0], self.dragging_lineup[1], key[0], key[1])
                            break
                    self.dragging_lineup = None
                elif self.state == "LIVE":
                    if event.key == pygame.K_TAB:
                        self.cycle_controlled_player()
                    if event.key == pygame.K_1:
                        self.tactic = 1
                        self.apply_tactic()
                    elif event.key == pygame.K_2:
                        self.tactic = 2
                        self.apply_tactic()
                    elif event.key == pygame.K_3:
                        self.tactic = 3
                        self.apply_tactic()
                    elif event.key == pygame.K_4:
                        self.tactic = 4
                        self.apply_tactic()
                    elif event.key == pygame.K_5:
                        self.tactic = 5
                        self.apply_tactic()
                    elif event.key == pygame.K_6:
                        self.tactic = 6
                        self.apply_tactic()
                    elif event.key == pygame.K_7:
                        self.tactic = 7
                        self.apply_tactic()
                    elif event.key == pygame.K_8:
                        self.tactic = 8
                        self.apply_tactic()
                    elif event.key == pygame.K_b:
                        self.show_tactics_board = not self.show_tactics_board
                    elif event.key == pygame.K_l:
                        self.show_lineups = not self.show_lineups
                    elif event.key == pygame.K_r:
                        self.press_level = 1 if self.press_level >= 3 else self.press_level + 1
                    elif event.key == pygame.K_f:
                        self.line_level = 1 if self.line_level >= 3 else self.line_level + 1
                    elif event.key == pygame.K_g:
                        self.tempo_level = 1 if self.tempo_level >= 3 else self.tempo_level + 1
                    elif event.key == pygame.K_e:
                        if not self.kickoff_pending and self.controlled:
                            carrier = self.ball_carrier()
                            if carrier and carrier.team == self.controlled.team and carrier is not self.controlled:
                                self.pass_ball(self.controlled, allow_any_team=True)
                                self.add_commentary(f"{self.controlled.name} asks for the pass")
                    elif event.key == pygame.K_SPACE:
                        if self.kickoff_pending:
                            self.kickoff_pending = False
                            self.show_stats_panel = False
                            self.message = "Kickoff"
                            self.add_commentary("Kickoff")
                    elif not self.kickoff_pending:
                        if event.key == pygame.K_p:
                            carrier = self.ball_carrier()
                            if carrier and carrier.team == "H":
                                teammates = [p for p in self.home if p is not carrier]
                                target = min(teammates, key=lambda t: (t.x - carrier.x) ** 2 + (t.y - carrier.y) ** 2)
                                self.pass_ball(target, prefer_controlled=True)
                        elif event.key == pygame.K_k:
                            self.shoot_ball()
                        elif event.key == pygame.K_t:
                            self.manual_tackle()
                elif self.state == "MATCH_SCENE":
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.match_scene_timer = 0.0

    def draw_field(self):
        self.screen.fill(GREEN)
        for i in range(0, 12):
            x0 = FIELD_MARGIN + i * ((WIDTH - 2 * FIELD_MARGIN) / 12)
            pygame.draw.rect(self.screen, DARK_GREEN, (x0, FIELD_MARGIN, 40, HEIGHT - 2 * FIELD_MARGIN - COMMENTARY_BAR_H), 0)
        pygame.draw.rect(
            self.screen,
            WHITE,
            (FIELD_MARGIN, FIELD_MARGIN, WIDTH - 2 * FIELD_MARGIN, HEIGHT - 2 * FIELD_MARGIN - COMMENTARY_BAR_H),
            3,
        )
        pygame.draw.line(
            self.screen,
            WHITE,
            (WIDTH / 2, FIELD_MARGIN),
            (WIDTH / 2, HEIGHT - FIELD_MARGIN - COMMENTARY_BAR_H),
            2,
        )
        pygame.draw.circle(
            self.screen,
            WHITE,
            (int(WIDTH / 2), int((HEIGHT - COMMENTARY_BAR_H) / 2)),
            80,
            2,
        )
        # penalty boxes and goal areas
        pygame.draw.rect(
            self.screen,
            WHITE,
            (FIELD_MARGIN, (HEIGHT - COMMENTARY_BAR_H) / 2 - PENALTY_BOX_HEIGHT / 2, PENALTY_BOX_DEPTH, PENALTY_BOX_HEIGHT),
            2,
        )
        pygame.draw.rect(
            self.screen,
            WHITE,
            (
                WIDTH - FIELD_MARGIN - PENALTY_BOX_DEPTH,
                (HEIGHT - COMMENTARY_BAR_H) / 2 - PENALTY_BOX_HEIGHT / 2,
                PENALTY_BOX_DEPTH,
                PENALTY_BOX_HEIGHT,
            ),
            2,
        )
        pygame.draw.rect(
            self.screen,
            WHITE,
            (FIELD_MARGIN, (HEIGHT - COMMENTARY_BAR_H) / 2 - GOAL_BOX_HEIGHT / 2, GOAL_BOX_DEPTH, GOAL_BOX_HEIGHT),
            2,
        )
        pygame.draw.rect(
            self.screen,
            WHITE,
            (
                WIDTH - FIELD_MARGIN - GOAL_BOX_DEPTH,
                (HEIGHT - COMMENTARY_BAR_H) / 2 - GOAL_BOX_HEIGHT / 2,
                GOAL_BOX_DEPTH,
                GOAL_BOX_HEIGHT,
            ),
            2,
        )
        pygame.draw.circle(
            self.screen,
            WHITE,
            (int(FIELD_MARGIN + PENALTY_SPOT_DIST), int((HEIGHT - COMMENTARY_BAR_H) / 2)),
            3,
        )
        pygame.draw.circle(
            self.screen,
            WHITE,
            (int(WIDTH - FIELD_MARGIN - PENALTY_SPOT_DIST), int((HEIGHT - COMMENTARY_BAR_H) / 2)),
            3,
        )
        pygame.draw.rect(
            self.screen,
            WHITE,
            (FIELD_MARGIN - GOAL_DEPTH, (HEIGHT - COMMENTARY_BAR_H) / 2 - GOAL_WIDTH / 2, GOAL_DEPTH, GOAL_WIDTH),
            2,
        )
        pygame.draw.rect(
            self.screen,
            WHITE,
            (WIDTH - FIELD_MARGIN, (HEIGHT - COMMENTARY_BAR_H) / 2 - GOAL_WIDTH / 2, GOAL_DEPTH, GOAL_WIDTH),
            2,
        )

        # corner arcs
        bottom = HEIGHT - FIELD_MARGIN - COMMENTARY_BAR_H
        r = CORNER_ARC_RADIUS
        pygame.draw.arc(
            self.screen,
            WHITE,
            (FIELD_MARGIN - r, FIELD_MARGIN - r, r * 2, r * 2),
            0,
            math.pi / 2,
            2,
        )
        pygame.draw.arc(
            self.screen,
            WHITE,
            (WIDTH - FIELD_MARGIN - r, FIELD_MARGIN - r, r * 2, r * 2),
            math.pi / 2,
            math.pi,
            2,
        )
        pygame.draw.arc(
            self.screen,
            WHITE,
            (WIDTH - FIELD_MARGIN - r, bottom - r, r * 2, r * 2),
            math.pi,
            1.5 * math.pi,
            2,
        )
        pygame.draw.arc(
            self.screen,
            WHITE,
            (FIELD_MARGIN - r, bottom - r, r * 2, r * 2),
            1.5 * math.pi,
            2 * math.pi,
            2,
        )

    def draw_players(self):
        home_primary, home_secondary = get_team_kits(self.current_home)[self.home_kit_index]
        away_primary, away_secondary = get_team_kits(self.current_away)[self.away_kit_index]
        for p in self.home:
            color = home_secondary if p.role == "GK" else home_primary
            pygame.draw.circle(self.screen, color, (int(p.x), int(p.y)), 10)
            num = self.small.render(str(p.number), True, BLACK)
            self.screen.blit(num, (int(p.x - 4), int(p.y - 6)))
            if p is self.controlled:
                pygame.draw.circle(self.screen, YELLOW, (int(p.x), int(p.y)), 14, 2)
        for p in self.away:
            color = away_secondary if p.role == "GK" else away_primary
            pygame.draw.circle(self.screen, color, (int(p.x), int(p.y)), 10)
            num = self.small.render(str(p.number), True, BLACK)
            self.screen.blit(num, (int(p.x - 4), int(p.y - 6)))
            if p is self.controlled:
                pygame.draw.circle(self.screen, YELLOW, (int(p.x), int(p.y)), 14, 2)
        pygame.draw.circle(self.screen, BLACK, (int(self.ball.x), int(self.ball.y)), 5)

    def draw_profile_strip(self, x, y, w=360, h=108):
        record = self.active_account_record() or {}
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, (24, 30, 42), rect, 0, border_radius=18)
        pygame.draw.rect(self.screen, (76, 94, 132), rect, 2, border_radius=18)
        accent = (244, 206, 84) if record.get("is_developer") else (86, 170, 255)
        glow = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*accent, 40), (-30, -18, w * 0.8, h + 36))
        self.screen.blit(glow, (x, y))
        display_name = record.get("display_name", self.active_account or "Guest")
        username = record.get("username", self.active_account or "")
        mode = self.game_mode.title() if self.game_mode else "Menu"
        self.screen.blit(self.font.render(display_name[:18], True, WHITE), (x + 16, y + 14))
        source_label = "local fallback" if self.account_storage_mode == "LOCAL" else "cloud profile"
        sub = f"@{username} | {source_label}" if username else source_label
        self.screen.blit(self.small.render(sub, True, (190, 200, 215)), (x + 16, y + 42))
        pill = pygame.Rect(x + 16, y + 66, 84, 26)
        pygame.draw.rect(self.screen, (16, 22, 32), pill, 0, border_radius=10)
        pygame.draw.rect(self.screen, accent, pill, 2, border_radius=10)
        self.screen.blit(self.small.render(mode, True, WHITE), (pill.x + 12, pill.y + 6))
        if record.get("is_developer"):
            dev_pill = pygame.Rect(x + 110, y + 66, 94, 26)
            pygame.draw.rect(self.screen, (16, 22, 32), dev_pill, 0, border_radius=10)
            pygame.draw.rect(self.screen, (244, 206, 84), dev_pill, 2, border_radius=10)
            self.screen.blit(self.small.render("DEVELOPER", True, WHITE), (dev_pill.x + 8, dev_pill.y + 6))
        action = "ESC modes | Q logout"
        if record.get("is_developer"):
            action += " | U console"
        action += " | C cloud"
        self.screen.blit(self.small.render(action, True, (200, 210, 220)), (x + 150, y + 18))
        value_label = f"Coins: {self.fantasy_coins}" if self.game_mode == "FANTASY" else f"Budget: {self.user_budget}"
        self.screen.blit(self.small.render(value_label, True, WHITE), (x + 150, y + 48))

    def draw_reconnect_button(self, x, y, width=48, height=38, label="-"):
        rect = pygame.Rect(x, y, width, height)
        self.reconnect_button_rect = rect
        accent = (92, 176, 255) if self.cloud_status_label == "Connected to Cloud" else (244, 206, 84)
        pygame.draw.rect(self.screen, (18, 24, 34), rect, 0, border_radius=12)
        pygame.draw.rect(self.screen, accent, rect, 2, border_radius=12)
        text = self.small.render(label, True, WHITE)
        self.screen.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))
        return rect

    def draw_account_home(self):
        self.screen.fill((10, 14, 24))
        self.reconnect_button_rect = None
        local = self.local_account_record()
        local_cloud_state = (local or {}).get("cloud_state", "LOCAL_ONLY")
        if self.account_storage_mode == "LOCAL":
            if local_cloud_state == "SYNCED":
                storage_label = "Offline Mirror"
            elif local_cloud_state == "PENDING_CREATE":
                storage_label = "Waiting for Cloud"
            else:
                storage_label = "Local Fallback"
        else:
            storage_label = "Cloud"
        storage_accent = (244, 206, 84) if self.account_storage_mode == "LOCAL" else (92, 176, 255)
        hero = pygame.Rect(34, 24, 1098, 150)
        pygame.draw.rect(self.screen, (20, 28, 44), hero, 0, border_radius=26)
        pygame.draw.rect(self.screen, (80, 112, 166), hero, 2, border_radius=26)
        glow = pygame.Surface((hero.w, hero.h), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (86, 170, 255, 54), (-40, -24, hero.w * 0.7, hero.h + 44))
        pygame.draw.ellipse(glow, (244, 206, 84, 34), (hero.w * 0.48, -30, hero.w * 0.44, hero.h + 50))
        self.screen.blit(glow, (hero.x, hero.y))
        self.screen.blit(self.big.render("FC Legends Cloud Profiles", True, WHITE), (54, 44))
        self.screen.blit(self.font.render("Cloud accounts for career and fantasy saves", True, (214, 222, 236)), (56, 84))
        self.screen.blit(self.small.render("Create an account, sign in, or use developer sign in.", True, (190, 200, 215)), (56, 116))
        announcement = self.cloud_runtime_config.get("announcement", "")
        if announcement:
            self.screen.blit(self.small.render(f"Cloud notice: {announcement[:96]}", True, (244, 206, 84)), (56, 144))
        version_badge = pygame.Rect(910, 42, 170, 34)
        pygame.draw.rect(self.screen, (18, 24, 34), version_badge, 0, border_radius=12)
        pygame.draw.rect(self.screen, (92, 176, 255), version_badge, 2, border_radius=12)
        self.screen.blit(self.small.render(f"VERSION {self.app_version}", True, WHITE), (version_badge.x + 24, version_badge.y + 9))
        storage_badge = pygame.Rect(850, 88, 230, 34)
        pygame.draw.rect(self.screen, (18, 24, 34), storage_badge, 0, border_radius=12)
        pygame.draw.rect(self.screen, storage_accent, storage_badge, 2, border_radius=12)
        self.screen.blit(self.small.render(f"ACCOUNT STORAGE: {storage_label.upper()}", True, WHITE), (storage_badge.x + 14, storage_badge.y + 9))
        self.draw_reconnect_button(1032, 128)
        options = ["Sign In", "Create Account", "Developer Sign In"]
        y = 226
        for idx, label in enumerate(options):
            row = pygame.Rect(60, y, 460, 74)
            active = idx == self.account_menu_index
            pygame.draw.rect(self.screen, (28, 34, 48), row, 0, border_radius=18)
            pygame.draw.rect(self.screen, YELLOW if active else (80, 92, 122), row, 3 if active else 2, border_radius=18)
            tag = "DEVELOPER" if "Developer" in label else "PROFILE"
            self.screen.blit(self.font.render(label, True, WHITE), (row.x + 18, row.y + 16))
            self.screen.blit(self.small.render(tag, True, (190, 200, 215)), (row.x + 18, row.y + 46))
            y += 94
        info = pygame.Rect(560, 226, 580, 360)
        pygame.draw.rect(self.screen, (22, 28, 40), info, 0, border_radius=20)
        pygame.draw.rect(self.screen, (70, 86, 122), info, 2, border_radius=20)
        self.screen.blit(self.font.render("Cloud Saving", True, WHITE), (info.x + 18, info.y + 18))
        lines = [
            "Career and fantasy progress sync through the cloud server.",
            "Every successful sign-in is mirrored locally as a fallback.",
            "Fantasy starter coins: 100",
            f"Developer accounts: {DEVELOPER_FANTASY_COINS} coins, hidden packs, elite starter pull.",
            "Developer console can inspect accounts, grant rewards, and run live ops.",
            "Passwords stay hidden and stored as hashes.",
        ]
        y = info.y + 64
        for line in lines:
            self.screen.blit(self.small.render(line, True, (210, 218, 230)), (info.x + 18, y))
            y += 34
        footer = pygame.Rect(34, 628, 1098, 66)
        pygame.draw.rect(self.screen, (22, 28, 40), footer, 0, border_radius=18)
        pygame.draw.rect(self.screen, (70, 86, 122), footer, 2, border_radius=18)
        update_text = "Auto updates on" if self.app_version_info.get("manifest_url") else "Auto updates off"
        self.screen.blit(self.small.render(f"Use UP/DOWN and ENTER | C cloud settings | - reconnect | Storage {storage_label}", True, (190, 200, 215)), (54, 646))
        self.screen.blit(self.small.render(f"Installed {self.app_version} | {update_text}", True, (150, 210, 255)), (700, 646))

    def draw_account_form(self):
        self.screen.fill((12, 16, 26))
        self.reconnect_button_rect = None
        titles = {
            "ACCOUNT_LOGIN": "Sign In",
            "ACCOUNT_CREATE": "Create Account",
            "ACCOUNT_DEV_LOGIN": "Developer Sign In",
        }
        header = pygame.Rect(34, 24, 1098, 118)
        pygame.draw.rect(self.screen, (20, 28, 44), header, 0, border_radius=24)
        pygame.draw.rect(self.screen, (80, 112, 166), header, 2, border_radius=24)
        self.screen.blit(self.big.render(titles.get(self.state, "Account"), True, WHITE), (52, 44))
        self.screen.blit(self.small.render("UP/DOWN move | ENTER submit | - reconnect | ESC back", True, (190, 200, 215)), (54, 86))
        self.draw_reconnect_button(1032, 78)
        badge_text = self.cloud_status_label
        if badge_text in ("Connected to Cloud", "Using Local Fallback"):
            badge_color = (92, 176, 255) if badge_text == "Connected to Cloud" else (244, 206, 84)
            badge = pygame.Rect(830, 42, 250, 34)
            pygame.draw.rect(self.screen, (18, 24, 34), badge, 0, border_radius=12)
            pygame.draw.rect(self.screen, badge_color, badge, 2, border_radius=12)
            self.screen.blit(self.small.render(badge_text, True, WHITE), (badge.x + 16, badge.y + 9))
        fields = self.auth_fields_for_state()
        labels = {
            "display_name": "Display Name",
            "username": "Username",
            "password": "Password",
            "developer_code": "Developer Code",
        }
        y = 184
        for idx, field in enumerate(fields):
            row = pygame.Rect(60, y, 520, 62)
            active = idx == self.account_field_index
            pygame.draw.rect(self.screen, (28, 34, 48), row, 0, border_radius=14)
            pygame.draw.rect(self.screen, YELLOW if active else (80, 92, 122), row, 3 if active else 2, border_radius=14)
            value = self.account_inputs[field]
            shown = "*" * len(value) if field in ("password", "developer_code") and value else value
            self.screen.blit(self.small.render(labels[field], True, (180, 190, 205)), (row.x + 16, row.y + 8))
            self.screen.blit(self.font.render(shown or "_", True, WHITE), (row.x + 16, row.y + 26))
            y += 76
        side = pygame.Rect(640, 184, 460, 340)
        pygame.draw.rect(self.screen, (22, 28, 40), side, 0, border_radius=20)
        pygame.draw.rect(self.screen, (70, 86, 122), side, 2, border_radius=20)
        side_title = "What gets saved"
        if self.state == "ACCOUNT_DEV_LOGIN":
            side_title = "Developer access"
        self.screen.blit(self.font.render(side_title, True, WHITE), (side.x + 18, side.y + 18))
        info_lines = [
            "Career and fantasy saves are stored separately.",
            "Fantasy accounts keep packs, coins, cards, and events.",
            "Profiles sync to the shared cloud backend.",
            "If cloud sync disappears, local fallback keeps your account usable.",
        ]
        if self.state == "ACCOUNT_DEV_LOGIN":
            info_lines = [
                "Developer code unlocks hidden packs.",
                f"Developer profiles start with {DEVELOPER_FANTASY_COINS} fantasy coins.",
                "Registered users page becomes available.",
            ]
        elif self.state == "ACCOUNT_CREATE":
            info_lines.append("Entering the developer code here creates a dev profile.")
        sy = side.y + 68
        for line in info_lines:
            self.screen.blit(self.small.render(line, True, (210, 218, 230)), (side.x + 18, sy))
            sy += 34
        if self.account_message:
            self.screen.blit(self.font.render(self.account_message, True, YELLOW), (60, y + 10))

    def draw_mode_select(self):
        self.screen.fill((12, 16, 26))
        self.reconnect_button_rect = None
        record = self.active_account_record() or {}
        header = pygame.Rect(34, 24, 1098, 128)
        pygame.draw.rect(self.screen, (20, 28, 44), header, 0, border_radius=24)
        pygame.draw.rect(self.screen, (80, 112, 166), header, 2, border_radius=24)
        title = self.big.render("Choose Game Mode", True, WHITE)
        self.screen.blit(title, (52, 42))
        self.screen.blit(self.small.render(f"Signed in as {record.get('display_name', self.active_account or 'Guest')}", True, (190, 200, 215)), (54, 84))
        self.screen.blit(self.small.render(f"Version {self.app_version}", True, (150, 210, 255)), (54, 110))
        self.draw_reconnect_button(1032, 86)
        if record.get("is_developer"):
            badge = pygame.Rect(910, 44, 170, 34)
            pygame.draw.rect(self.screen, (18, 24, 34), badge, 0, border_radius=12)
            pygame.draw.rect(self.screen, (244, 206, 84), badge, 2, border_radius=12)
            self.screen.blit(self.small.render("DEVELOPER ACCESS", True, WHITE), (badge.x + 18, badge.y + 9))
        options = [("Career Mode", "career_snapshot"), ("Fantasy Team", "fantasy_snapshot")]
        y = 210
        for idx, (label, slot) in enumerate(options):
            row = pygame.Rect(60, y, 500, 86)
            active = idx == self.mode_select_index
            saved = bool(record.get(slot))
            pygame.draw.rect(self.screen, (28, 34, 48), row, 0, border_radius=16)
            pygame.draw.rect(self.screen, YELLOW if active else (80, 92, 122), row, 3 if active else 2, border_radius=16)
            self.screen.blit(self.font.render(label, True, WHITE), (row.x + 18, row.y + 16))
            sub = "Continue saved progress" if saved else "Start a new save"
            self.screen.blit(self.small.render(sub, True, (190, 200, 215)), (row.x + 18, row.y + 44))
            stat = record.get(slot) or {}
            preview = "No save yet"
            if stat:
                preview = f"Week {stat.get('week_index', 0) + 1} | Team {stat.get('user_team') or stat.get('fantasy_team_name', 'Pending')}"
            self.screen.blit(self.small.render(preview[:42], True, (214, 222, 236)), (row.x + 240, row.y + 46))
            y += 108
        side = pygame.Rect(620, 210, 480, 250)
        pygame.draw.rect(self.screen, (22, 28, 40), side, 0, border_radius=20)
        pygame.draw.rect(self.screen, (70, 86, 122), side, 2, border_radius=20)
        self.screen.blit(self.font.render("Profile Summary", True, WHITE), (side.x + 18, side.y + 18))
        lines = [
            f"Username: @{record.get('username', self.active_account or '')}",
            f"Career save: {'Ready' if record.get('career_snapshot') else 'Empty'}",
            f"Fantasy save: {'Ready' if record.get('fantasy_snapshot') else 'Empty'}",
            f"Developer: {'Yes' if record.get('is_developer') else 'No'}",
        ]
        sy = side.y + 64
        for line in lines:
            self.screen.blit(self.small.render(line, True, (210, 218, 230)), (side.x + 18, sy))
            sy += 34
        sync_line = self.cloud_status_label if self.cloud_status_label in ("Connected to Cloud", "Using Local Fallback") else "Cloud sync enabled"
        self.screen.blit(self.small.render(sync_line, True, (190, 200, 215)), (side.x + 18, side.y + 204))
        hint = "Use UP/DOWN and ENTER"
        if record.get("is_developer"):
            hint += " | U developer console"
        hint += " | C cloud settings | ESC log out"
        self.screen.blit(self.small.render(hint, True, (190, 200, 215)), (42, HEIGHT - 44))

    def draw_fantasy_team_name_page(self):
        self.screen.fill((12, 16, 26))
        header = pygame.Rect(34, 24, 1098, 124)
        pygame.draw.rect(self.screen, (20, 28, 44), header, 0, border_radius=24)
        pygame.draw.rect(self.screen, (80, 112, 166), header, 2, border_radius=24)
        self.screen.blit(self.big.render("Name Your Fantasy Club", True, WHITE), (52, 42))
        self.screen.blit(self.small.render("Type your team name and press ENTER to open the starter pack.", True, (190, 200, 215)), (54, 84))
        panel = pygame.Rect(60, 150, 640, 96)
        pygame.draw.rect(self.screen, (28, 34, 48), panel, 0, border_radius=18)
        pygame.draw.rect(self.screen, YELLOW, panel, 3, border_radius=18)
        shown = self.fantasy_team_name or "_"
        self.screen.blit(self.font.render(shown, True, WHITE), (panel.x + 22, panel.y + 34))
        side = pygame.Rect(760, 180, 320, 210)
        pygame.draw.rect(self.screen, (22, 28, 40), side, 0, border_radius=20)
        pygame.draw.rect(self.screen, (70, 86, 122), side, 2, border_radius=20)
        self.screen.blit(self.font.render("Account Bonus", True, WHITE), (side.x + 18, side.y + 18))
        coins = DEVELOPER_FANTASY_COINS if (self.active_account_record() or {}).get("is_developer") else DEFAULT_FANTASY_COINS
        hidden_text = "Hidden packs unlocked" if (self.active_account_record() or {}).get("is_developer") else "Hidden packs locked"
        self.screen.blit(self.small.render(f"Starting coins: {coins}", True, (210, 218, 230)), (side.x + 18, side.y + 58))
        self.screen.blit(self.small.render(hidden_text, True, (210, 218, 230)), (side.x + 18, side.y + 92))
        starter_text = "Starter pack begins after naming the club."
        if (self.active_account_record() or {}).get("is_developer"):
            starter_text = "Developer bonus: guaranteed elite-or-better starter card."
        self.screen.blit(self.small.render(starter_text, True, (210, 218, 230)), (side.x + 18, side.y + 126))
        info = [
            "Starter pack: 15 players",
            "Guaranteed at least 1 goalkeeper",
            "Highest card usually Diamond",
            "1% chance the top card is above Diamond",
            "Starting coins depend on account type",
        ]
        y = 300
        for line in info:
            self.screen.blit(self.small.render(line, True, (210, 218, 230)), (64, y))
            y += 34

    def draw_registered_users_page(self):
        users = self.filtered_registered_users()
        selected = self.selected_registered_user()
        tabs = self.developer_tabs()
        tab_name = tabs[self.dev_console_tab]
        settings = self.dev_admin_status.get("settings", {})
        metrics = self.dev_admin_status.get("metrics", {})
        self.screen.fill((12, 16, 26))
        self.screen.blit(self.big.render("Developer Console", True, WHITE), (34, 22))
        self.screen.blit(self.small.render("TAB tabs | UP/DOWN browse | ENTER refresh/save | ESC back", True, (190, 200, 215)), (36, 56))
        tab_x = 34
        for idx, tab in enumerate(tabs):
            pill = pygame.Rect(tab_x, 88, 156, 34)
            active = idx == self.dev_console_tab
            pygame.draw.rect(self.screen, (20, 28, 40), pill, 0, border_radius=12)
            pygame.draw.rect(self.screen, YELLOW if active else (80, 92, 122), pill, 2, border_radius=12)
            self.screen.blit(self.small.render(tab, True, WHITE), (pill.x + 16, pill.y + 9))
            tab_x += 168
        if not users:
            self.screen.blit(self.font.render("No users registered", True, WHITE), (40, 150))
            return
        list_panel = pygame.Rect(34, 140, 420, 546)
        detail_panel = pygame.Rect(486, 140, 648, 546)
        for panel in (list_panel, detail_panel):
            pygame.draw.rect(self.screen, (22, 28, 40), panel, 0, border_radius=18)
            pygame.draw.rect(self.screen, (70, 86, 122), panel, 2, border_radius=18)
        self.screen.blit(self.small.render(f"Search: {self.dev_search_query or '_'}", True, (214, 222, 236)), (list_panel.x + 16, list_panel.y + 14))
        start = max(0, min(self.registered_users_index - 6, max(0, len(users) - 12)))
        y = list_panel.y + 44
        for idx in range(start, min(len(users), start + 12)):
            user = users[idx]
            row = pygame.Rect(list_panel.x + 12, y, list_panel.w - 24, 40)
            active = idx == self.registered_users_index
            pygame.draw.rect(self.screen, (36, 44, 60), row, 0, border_radius=10)
            pygame.draw.rect(self.screen, YELLOW if active else (86, 98, 126), row, 2, border_radius=10)
            status = "BANNED" if user.get("is_banned") else "SUSP" if user.get("is_suspended") else "OK"
            label = f"{user.get('username', '')} {'DEV' if user.get('is_developer') else 'USER'} {status}"
            self.screen.blit(self.small.render(label, True, WHITE), (row.x + 10, row.y + 12))
            y += 46
        summary = selected.get("fantasy_summary", {}) if selected else {}
        snapshot = (selected.get("fantasy_snapshot") or selected.get("career_snapshot") or {}) if selected else {}
        cards = snapshot.get("fantasy_roster", [])
        if not cards and summary:
            cards = [{}] * summary.get("cards", 0)
        top_cards = sorted(cards, key=lambda card: (-card.get("rating", 0), card.get("name", "")))[:6]
        lineup = snapshot.get("lineup") or []
        coins = snapshot.get("fantasy_coins", summary.get("coins", 0))
        packs = len(snapshot.get("my_packs", []))
        xp = snapshot.get("fantasy_season_xp", summary.get("xp", 0))
        team_name = summary.get("team_name") or snapshot.get("fantasy_team_name", "None")
        highest_card = max((card.get("rating", 0) for card in cards if isinstance(card, dict)), default=0)
        avg_top_five = 0
        rated_cards = [card.get("rating", 0) for card in cards if isinstance(card, dict) and card.get("rating")]
        if rated_cards:
            top_five = sorted(rated_cards, reverse=True)[:5]
            avg_top_five = sum(top_five) // max(1, len(top_five))
        y = detail_panel.y + 24
        if tab_name == "Users":
            lines = [
                f"Display Name: {selected.get('display_name', '')}",
                f"Username: {selected.get('username', '')}",
                f"Storage: {selected.get('storage_mode', 'CLOUD')}",
                f"Developer: {'Yes' if selected.get('is_developer') else 'No'}",
                f"Banned: {'Yes' if selected.get('is_banned') else 'No'}",
                f"Suspended: {'Yes' if selected.get('is_suspended') else 'No'}",
                f"Last Mode: {selected.get('last_mode', 'CAREER')}",
                f"Fantasy Team: {team_name}",
                f"Cards: {summary.get('cards', len(cards))}",
                f"Coins: {coins}",
                f"Packs: {packs}",
                f"Season XP: {xp}",
                "B ban/unban | V suspend | P dev toggle",
                "W reset password to legend123 | F repair",
            ]
            for line in lines:
                self.screen.blit(self.small.render(line[:68], True, WHITE), (detail_panel.x + 18, y))
                y += 34
        elif tab_name == "Economy":
            catalog = self.developer_card_catalog()
            gift_card = catalog[self.dev_card_index % len(catalog)] if catalog else {}
            selected_card = top_cards[0] if top_cards else {}
            lines = [
                f"Target: {selected.get('username', '')}",
                f"Coin Delta: {self.developer_coin_amounts()[self.dev_coin_delta_index]}",
                f"Pack: {self.developer_pack_ids()[self.dev_pack_index % len(self.developer_pack_ids())]}",
                f"Gift Card: {gift_card.get('name', 'None')} {gift_card.get('rating', '')}",
                f"Remove Card: {selected_card.get('name', 'None')} {selected_card.get('rating', '')}",
                "C add coins | X remove coins",
                "O add pack | L remove pack",
                "G gift selected card | R remove top card",
                "LEFT/RIGHT changes amount, pack, and gift card",
            ]
            for line in lines:
                self.screen.blit(self.small.render(line[:72], True, WHITE), (detail_panel.x + 18, y))
                y += 34
        elif tab_name == "Tournaments":
            lines = [
                f"Target: {selected.get('username', '')}",
                f"Division rewards preset: {self.developer_coin_amounts()[self.dev_coin_delta_index]}",
                f"Users tracked: {metrics.get('users', 0)}",
                f"Division entries: {metrics.get('online_divisions', 0)}",
                f"Tournament entries: {metrics.get('online_tournaments', 0)}",
                "D reset online division",
                "T reset tournament run",
                "A add tournament reward coins",
            ]
            for line in lines:
                self.screen.blit(self.small.render(line[:72], True, WHITE), (detail_panel.x + 18, y))
                y += 34
        elif tab_name == "Live Ops":
            disabled = settings.get("disabled_modes", {})
            lines = [
                f"Maintenance: {'ON' if settings.get('maintenance_mode') else 'OFF'}",
                f"Tournaments disabled: {'Yes' if disabled.get('tournaments') else 'No'}",
                f"Market disabled: {'Yes' if disabled.get('market') else 'No'}",
                f"Objectives disabled: {'Yes' if disabled.get('objectives') else 'No'}",
                f"Announcement: {self.dev_announcement_input[:60] or 'None'}",
                "M toggle maintenance",
                "1/2/3 toggle tournaments, market, objectives",
                "Type announcement text and press ENTER to save",
            ]
            for line in lines:
                self.screen.blit(self.small.render(line[:76], True, WHITE), (detail_panel.x + 18, y))
                y += 34
        else:
            local = self.local_account_record(selected.get("username")) if selected else None
            compare = "Local mirror found" if local else "No local mirror on this Mac"
            updated_label = selected.get("updated_at") or selected.get("created_at") or "Unknown"
            lines = [
                f"Target: {selected.get('username', '')}",
                f"Save source: {selected.get('storage_mode', 'CLOUD')}",
                f"Career save: {'Yes' if selected.get('career_snapshot') else 'No'}",
                f"Fantasy save: {'Yes' if selected.get('fantasy_snapshot') else 'No'}",
                compare,
                f"Last server update: {str(updated_label)[:36]}",
                "F repair fantasy snapshot and sync structure",
            ]
            for line in lines:
                self.screen.blit(self.small.render(line[:74], True, WHITE), (detail_panel.x + 18, y))
                y += 34
        meta_y = detail_panel.bottom - 160
        self.screen.blit(self.font.render("Top Cards", True, WHITE), (detail_panel.x + 18, meta_y))
        y = meta_y + 38
        if not top_cards or not top_cards[0]:
            self.screen.blit(self.small.render("No fantasy cards yet", True, (190, 200, 215)), (detail_panel.x + 18, y))
        else:
            for card in top_cards[:4]:
                line = f"{card.get('name', '')} | {card.get('rating', 0)} | {card.get('rarity', 'Bronze')}"
                self.screen.blit(self.small.render(line[:52], True, (220, 228, 236)), (detail_panel.x + 18, y))
                y += 28
        if self.dev_action_message:
            self.screen.blit(self.small.render(self.dev_action_message[:96], True, YELLOW), (36, HEIGHT - 24))

    def draw_cloud_settings_page(self):
        self.screen.fill((12, 16, 26))
        self.reconnect_button_rect = None
        header = pygame.Rect(34, 24, 1098, 120)
        pygame.draw.rect(self.screen, (20, 28, 44), header, 0, border_radius=24)
        pygame.draw.rect(self.screen, (80, 112, 166), header, 2, border_radius=24)
        self.screen.blit(self.big.render("Cloud Settings", True, WHITE), (52, 42))
        self.screen.blit(self.small.render("UP/DOWN select | ENTER save | - reconnect | ESC back", True, (190, 200, 215)), (54, 86))
        self.draw_reconnect_button(1032, 78)
        rows = [
            ("Cloud Mode", "REQUIRED"),
            ("Cloud API URL", self.cloud_settings_inputs.get("cloud_api_url", "")),
        ]
        y = 190
        for idx, (label, value) in enumerate(rows):
            row = pygame.Rect(60, y, 700, 72)
            active = idx == self.cloud_settings_index
            pygame.draw.rect(self.screen, (28, 34, 48), row, 0, border_radius=16)
            pygame.draw.rect(self.screen, YELLOW if active else (80, 92, 122), row, 3 if active else 2, border_radius=16)
            self.screen.blit(self.small.render(label, True, (180, 190, 205)), (row.x + 18, row.y + 10))
            self.screen.blit(self.font.render(value or "_", True, WHITE), (row.x + 18, row.y + 34))
            y += 96
        side = pygame.Rect(800, 190, 300, 260)
        pygame.draw.rect(self.screen, (22, 28, 40), side, 0, border_radius=20)
        pygame.draw.rect(self.screen, (70, 86, 122), side, 2, border_radius=20)
        self.screen.blit(self.font.render("Status", True, WHITE), (side.x + 18, side.y + 18))
        status_lines = [
            "Current mode: Cloud",
            f"Saved URL: {self.app_settings.get('cloud_api_url', '')[:26]}",
            "Changing this signs out the current account.",
            "Launcher app reads the same saved settings.",
        ]
        sy = side.y + 58
        for line in status_lines:
            self.screen.blit(self.small.render(line, True, (210, 218, 230)), (side.x + 18, sy))
            sy += 34
        if self.account_message:
            self.screen.blit(self.font.render(self.account_message, True, YELLOW), (60, 418))

    def draw_fantasy_builder(self):
        self.screen.fill((16, 20, 26))
        self.screen.blit(self.big.render("Fantasy Team", True, WHITE), (30, 20))
        self.screen.blit(self.small.render("S start season | P shop | ESC mode select", True, (180, 190, 205)), (30, 52))

        name_text = self.fantasy_team_name.strip() or "Fantasy FC"
        self.screen.blit(self.font.render(f"Team: {name_text}", True, WHITE), (30, 82))
        self.screen.blit(self.font.render(f"Squad Size: {len(self.fantasy_roster)}", True, WHITE), (30, 108))
        self.screen.blit(self.font.render(f"Coins: {self.fantasy_coins}", True, WHITE), (30, 134))
        self.screen.blit(self.small.render("Starter pack already opened. Packs are the only way to add players.", True, (200, 210, 220)), (30, 160))

        left_x = 30
        left_y = 200
        left_w = 520
        left_h = 460
        right_x = 600
        right_y = 200
        right_w = 560
        right_h = 460

        pygame.draw.rect(self.screen, (26, 32, 40), (left_x, left_y, left_w, left_h), 0)
        pygame.draw.rect(self.screen, (60, 70, 85), (left_x, left_y, left_w, left_h), 2)
        self.screen.blit(self.font.render("Your Squad", True, WHITE), (left_x + 12, left_y + 8))

        y = left_y + 38
        for i, p in enumerate(self.fantasy_roster[:21]):
            tier, accent = self.card_tier(p["rating"])
            label = f"{i+1:>2}. {p['name']:<18}  {p['rating']:>2}  {tier}"
            if i % 2 == 0:
                pygame.draw.rect(self.screen, (30, 38, 50), (left_x + 8, y - 2, left_w - 16, 22), 0)
            self.screen.blit(self.small.render(label, True, WHITE), (left_x + 12, y))
            pygame.draw.circle(self.screen, accent, (left_x + left_w - 20, y + 7), 5)
            y += 20

        pygame.draw.rect(self.screen, (26, 32, 40), (right_x, right_y, right_w, right_h), 0)
        pygame.draw.rect(self.screen, (60, 70, 85), (right_x, right_y, right_w, right_h), 2)
        self.screen.blit(self.font.render("Collection View", True, WHITE), (right_x + 12, right_y + 8))
        self.screen.blit(self.small.render("Open packs to grow the squad before the season starts.", True, (200, 210, 220)), (right_x + 12, right_y + 36))
        summary = [
            f"Packs owned: {len(self.my_packs)}",
            f"Ready to play: {'Yes' if len(self.fantasy_roster) >= 11 else 'No'}",
            f"Highest card: {max((p['rating'] for p in self.fantasy_roster), default=0)}",
        ]
        y = right_y + 72
        for line in summary:
            self.screen.blit(self.font.render(line, True, WHITE), (right_x + 12, y))
            y += 34

        if self.last_pack:
            pack_y = 520
            self.screen.blit(self.font.render("Last Pack", True, WHITE), (right_x + 12, pack_y))
            card_w = 160
            card_h = 110
            gap = 16
            base_x = right_x + 12
            for i, player in enumerate(self.last_pack[:3]):
                cx = base_x + i * (card_w + gap)
                self.draw_card(cx, pack_y + 28, card_w, card_h, player)

    def draw_team_select(self):
        self.screen.fill(GRAY)
        title = self.big.render("Choose your Premier League team", True, BLACK)
        self.screen.blit(title, (30, 30))
        y = 80
        for i, t in enumerate(TEAMS):
            color = BLACK
            if i == self.selected_index:
                color = RED
            self.screen.blit(self.font.render(t, True, color), (40, y))
            y += 22
        self.screen.blit(self.font.render("Use UP/DOWN and ENTER", True, BLACK), (40, HEIGHT - 40))

    def draw_player_select(self):
        if self.game_mode == "FANTASY":
            self.state = "LEAGUE"
            return
        self.screen.fill(GRAY)
        title = self.big.render("Choose player to control", True, BLACK)
        self.screen.blit(title, (30, 30))
        if self.user_team:
            self.screen.blit(self.font.render(f"Team: {self.user_team}", True, BLACK), (30, 55))

        lineup = TEAM_LINEUPS.get(self.user_team, DEFAULT_LINEUP)
        roles = [r for r, _ in DEFAULT_LINEUP]
        y = 90
        for i in range(11):
            entry = lineup[i] if i < len(lineup) else (f"H{i+1}", i + 1)
            name, num = lineup_name_number(entry, i)
            role = roles[i] if i < len(roles) else ""
            label = f"{num:>2}  {name}  ({role})"
            color = RED if i == self.selected_player_index else BLACK
            self.screen.blit(self.font.render(label, True, color), (40, y))
            y += 22

        self.screen.blit(self.font.render("Use UP/DOWN and ENTER", True, BLACK), (40, HEIGHT - 40))

    def draw_lineup_select(self):
        self.screen.fill((12, 18, 30))
        bg = pygame.Surface((WIDTH, HEIGHT))
        bg.fill((12, 18, 30))
        for stripe in range(8):
            pygame.draw.rect(bg, (14 + stripe * 3, 26 + stripe * 4, 36 + stripe * 3), (0, stripe * 95, WIDTH, 60))
        self.screen.blit(bg, (0, 0))

        def visible_range(total, selected, max_visible):
            if total <= max_visible:
                return 0, total
            start = max(0, min(selected - max_visible + 1, total - max_visible))
            return start, start + max_visible

        self.lineup_rects = {}
        header_h = 110
        self.screen.blit(self.big.render("Squad", True, WHITE), (26, 18))
        if self.user_team:
            self.screen.blit(self.font.render(self.user_team, True, (210, 220, 230)), (28, 50))
        if self.pending_fixture:
            home, away = self.pending_fixture
            self.screen.blit(self.font.render(f"{home} vs {away}", True, (210, 220, 230)), (28, 74))
            self.draw_kit_picker(980, 18, home, away)

        left_panel = pygame.Rect(20, 120, 220, 560)
        pitch_rect = pygame.Rect(255, 120, 670, 560)
        right_panel = pygame.Rect(940, 120, 240, 560)
        bench_panel = pygame.Rect(255, 690, 925, 120)

        pygame.draw.rect(self.screen, (20, 26, 38), left_panel, 0, border_radius=18)
        pygame.draw.rect(self.screen, (45, 60, 90), left_panel, 2, border_radius=18)
        pygame.draw.rect(self.screen, (24, 78, 48), pitch_rect, 0, border_radius=22)
        pygame.draw.rect(self.screen, (220, 225, 230), pitch_rect, 2, border_radius=22)
        pygame.draw.rect(self.screen, (20, 26, 38), right_panel, 0, border_radius=18)
        pygame.draw.rect(self.screen, (45, 60, 90), right_panel, 2, border_radius=18)
        pygame.draw.rect(self.screen, (20, 26, 38), bench_panel, 0, border_radius=18)
        pygame.draw.rect(self.screen, (45, 60, 90), bench_panel, 2, border_radius=18)

        # pitch lines
        pygame.draw.line(self.screen, (235, 235, 235), (pitch_rect.centerx, pitch_rect.top + 18), (pitch_rect.centerx, pitch_rect.bottom - 18), 2)
        pygame.draw.circle(self.screen, (235, 235, 235), pitch_rect.center, 62, 2)
        pygame.draw.rect(self.screen, (235, 235, 235), (pitch_rect.left + 18, pitch_rect.centery - 120, 110, 240), 2)
        pygame.draw.rect(self.screen, (235, 235, 235), (pitch_rect.right - 128, pitch_rect.centery - 120, 110, 240), 2)
        pygame.draw.rect(self.screen, (235, 235, 235), (pitch_rect.left + 18, pitch_rect.centery - 60, 50, 120), 2)
        pygame.draw.rect(self.screen, (235, 235, 235), (pitch_rect.right - 68, pitch_rect.centery - 60, 50, 120), 2)

        self.screen.blit(self.small.render("Starter XI", True, WHITE), (left_panel.x + 12, left_panel.y + 10))
        if self.game_mode == "FANTASY":
            self.screen.blit(self.small.render(f"Team Chem {self.fantasy_chemistry_total}/33", True, (200, 210, 220)), (left_panel.x + 12, left_panel.y + 26))
        self.screen.blit(self.small.render("Bench", True, WHITE), (bench_panel.x + 12, bench_panel.y + 10))
        self.screen.blit(self.small.render("Reserves", True, WHITE), (right_panel.x + 12, right_panel.y + 10))

        positions = self.get_home_positions()
        role_map = [p[2] for p in positions]
        field_left = FIELD_MARGIN
        field_width = WIDTH - 2 * FIELD_MARGIN
        field_height = HEIGHT - 2 * FIELD_MARGIN
        card_w = 86
        card_h = 106

        for i, entry in enumerate(self.user_starting):
            is_selected = self.lineup_col == 0 and i == self.lineup_idx
            is_pick = self.lineup_pick == (0, i)
            px, py, role = positions[i]
            rel_x = (px - field_left) / field_width
            rel_y = (py - FIELD_MARGIN) / field_height
            cx = pitch_rect.x + rel_x * pitch_rect.w - card_w / 2
            cy = pitch_rect.y + rel_y * pitch_rect.h - card_h / 2
            rect = pygame.Rect(int(cx), int(cy), card_w, card_h)
            self.lineup_rects[(0, i)] = rect
        if self.game_mode == "FANTASY":
            link_colors = {
                3: (90, 220, 130),
                2: (90, 220, 130),
                1: (244, 206, 84),
                0: (220, 92, 92),
                -1: (210, 80, 170),
            }
            for a_idx, b_idx, strength, label in self.fantasy_chemistry_links:
                if (0, a_idx) not in self.lineup_rects or (0, b_idx) not in self.lineup_rects:
                    continue
                a_rect = self.lineup_rects[(0, a_idx)]
                b_rect = self.lineup_rects[(0, b_idx)]
                ax, ay = a_rect.centerx, a_rect.centery
                bx, by = b_rect.centerx, b_rect.centery
                pygame.draw.line(self.screen, link_colors.get(strength, (220, 92, 92)), (ax, ay), (bx, by), 5 if strength >= 3 else 4 if strength == 2 else 3)
                mid_x = (ax + bx) // 2
                mid_y = (ay + by) // 2
                self.screen.blit(self.small.render(label[:5], True, link_colors.get(strength, WHITE)), (mid_x - 12, mid_y - 8))
        for i, entry in enumerate(self.user_starting):
            is_selected = self.lineup_col == 0 and i == self.lineup_idx
            is_pick = self.lineup_pick == (0, i)
            role = role_map[i]
            rect = self.lineup_rects[(0, i)]
            self.lineup_rects[(0, i)] = self.draw_squad_card(rect.x, rect.y, card_w, card_h, entry, role=role, selected=is_selected, picked=is_pick)

        stat_entry = None
        if self.lineup_col == 0 and self.user_starting and self.lineup_idx < len(self.user_starting):
            stat_entry = self.user_starting[self.lineup_idx]
        elif self.lineup_col == 1 and self.user_bench and self.lineup_idx < len(self.user_bench):
            stat_entry = self.user_bench[self.lineup_idx]
        elif self.lineup_col == 2 and self.user_reserves and self.lineup_idx < len(self.user_reserves):
            stat_entry = self.user_reserves[self.lineup_idx]

        if stat_entry:
            name, num, rating = stat_entry
            card_meta = self.get_fantasy_card_meta(name, num, rating) or self.get_fantasy_card_meta(name)
            rarity = card_meta.get("rarity", "Base") if card_meta else "Base"
            promo = card_meta.get("promo", "Base") if card_meta else "Base"
            league = card_meta.get("league", get_team_league(card_meta.get("team", ""))) if card_meta else get_team_league("")
            preferred_position = card_meta.get("position", "ST") if card_meta else "ST"
            traits = card_meta.get("traits", []) if card_meta else []
            evo_level = card_meta.get("evo_level", 0) if card_meta else 0
            chemistry = self.fantasy_chemistry_map.get((name, num, rating), 0) if self.game_mode == "FANTASY" else 0
            self.screen.blit(self.font.render(f"{name}", True, WHITE), (left_panel.x + 12, left_panel.y + 44))
            self.screen.blit(self.small.render(f"#{num}  OVR {rating}", True, (200, 210, 220)), (left_panel.x + 12, left_panel.y + 68))
            self.screen.blit(self.small.render(f"Rarity: {rarity}  Promo: {promo}", True, (220, 228, 236)), (left_panel.x + 12, left_panel.y + 88))
            self.screen.blit(self.small.render(f"League: {league}", True, (220, 228, 236)), (left_panel.x + 12, left_panel.y + 106))
            self.screen.blit(self.small.render(f"Preferred Pos: {preferred_position}", True, (220, 228, 236)), (left_panel.x + 12, left_panel.y + 124))
            if self.game_mode == "FANTASY":
                evo_text = f"Evolution: Level {evo_level}" if evo_level > 0 else "Evolution: None"
                self.screen.blit(self.small.render(f"Chemistry: {chemistry}/3", True, (220, 228, 236)), (left_panel.x + 12, left_panel.y + 142))
                self.screen.blit(self.small.render(evo_text, True, (170, 235, 210) if evo_level > 0 else (220, 228, 236)), (left_panel.x + 12, left_panel.y + 160))
                chem_tags = " ".join(self.fantasy_chemistry_breakdown.get((name, num, rating), [])) or "None"
                self.screen.blit(self.small.render(f"Chem Tags: {chem_tags[:20]}", True, (220, 228, 236)), (left_panel.x + 12, left_panel.y + 178))
            effective = rating + chemistry
            pace = int(80 * (effective / 100))
            pass_pct = int(70 * (effective / 100))
            shoot = int(70 * (effective / 100))
            tackle = int(65 * (effective / 100))
            bars = [("PAC", pace), ("PAS", pass_pct), ("SHO", shoot), ("TAC", tackle)]
            y = left_panel.y + (212 if self.game_mode == "FANTASY" else 160)
            for label, value in bars:
                self.screen.blit(self.small.render(label, True, WHITE), (left_panel.x + 12, y))
                pygame.draw.rect(self.screen, (40, 48, 62), (left_panel.x + 52, y + 2, 120, 8), 0, border_radius=4)
                pygame.draw.rect(self.screen, LIGHT_GREEN, (left_panel.x + 52, y + 2, int(120 * (value / 100)), 8), 0, border_radius=4)
                y += 28
            skill_text = ", ".join(traits) if traits else "None"
            self.screen.blit(self.small.render("Skills:", True, WHITE), (left_panel.x + 12, y + 4))
            skill_lines = [skill_text[i:i + 24] for i in range(0, len(skill_text), 24)] or ["None"]
            for line_idx, line in enumerate(skill_lines[:2]):
                self.screen.blit(self.small.render(line, True, (200, 210, 220)), (left_panel.x + 12, y + 24 + line_idx * 18))
            goals = self.get_player_stat(name, "goals")
            assists = self.get_player_stat(name, "assists")
            clean = self.get_player_stat(name, "clean_sheets")
            tackles = self.get_player_stat(name, "tackles")
            stat_y = y + 64
            self.screen.blit(self.small.render(f"{goals} Goals", True, (200, 210, 220)), (left_panel.x + 12, stat_y))
            self.screen.blit(self.small.render(f"{assists} Assists", True, (200, 210, 220)), (left_panel.x + 12, stat_y + 20))
            self.screen.blit(self.small.render(f"{clean} Clean Sheets", True, (200, 210, 220)), (left_panel.x + 12, stat_y + 40))
            self.screen.blit(self.small.render(f"{tackles} Tackles", True, (200, 210, 220)), (left_panel.x + 12, stat_y + 60))

        bench_active = self.lineup_col == 1 or (self.lineup_pick and self.lineup_pick[0] == 1)
        bench_card_w = 80 if not bench_active else 92
        bench_card_h = 96 if not bench_active else 110
        bench_spacing = 12
        bench_visible = 9 if not bench_active else 8
        bench_start, bench_end = visible_range(len(self.user_bench), self.lineup_idx if self.lineup_col == 1 else 0, bench_visible)
        if not bench_active:
            self.screen.blit(self.small.render("Move to bench to expand", True, (180, 190, 205)), (bench_panel.x + 12, bench_panel.y + 36))
            preview_count = min(5, len(self.user_bench))
            for draw_idx, i in enumerate(range(preview_count)):
                entry = self.user_bench[i]
                x = bench_panel.x + 12 + draw_idx * 92
                y = bench_panel.y + 18
                rect = self.draw_squad_card(x, y, 72, 88, entry, role="SUB")
                self.lineup_rects[(1, i)] = rect
            if len(self.user_bench) > preview_count:
                self.screen.blit(self.small.render(f"+{len(self.user_bench) - preview_count} more", True, (180, 190, 205)), (bench_panel.right - 86, bench_panel.y + 84))
        else:
            expand_rect = pygame.Rect(210, 540, 1010, 190)
            shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 80))
            self.screen.blit(shade, (0, 0))
            pygame.draw.rect(self.screen, (24, 30, 42), expand_rect, 0, border_radius=20)
            pygame.draw.rect(self.screen, (72, 92, 128), expand_rect, 3, border_radius=20)
            self.screen.blit(self.font.render("Bench", True, WHITE), (expand_rect.x + 16, expand_rect.y + 12))
            self.screen.blit(self.small.render("UP/DOWN select | ENTER swap | TAB to move on", True, (200, 210, 220)), (expand_rect.x + 16, expand_rect.y + 40))
            for draw_idx, i in enumerate(range(bench_start, bench_end)):
                entry = self.user_bench[i]
                x = expand_rect.x + 18 + draw_idx * (bench_card_w + bench_spacing)
                y = expand_rect.y + 66
                is_selected = self.lineup_col == 1 and i == self.lineup_idx
                is_pick = self.lineup_pick == (1, i)
                rect = self.draw_squad_card(x, y, bench_card_w, bench_card_h, entry, role="SUB", selected=is_selected, picked=is_pick)
                self.lineup_rects[(1, i)] = rect

        reserve_line_h = 26
        reserve_visible = 20
        reserve_start, reserve_end = visible_range(len(self.user_reserves), self.lineup_idx if self.lineup_col == 2 else 0, reserve_visible)
        y = right_panel.y + 40
        for i in range(reserve_start, reserve_end):
            entry = self.user_reserves[i]
            is_selected = self.lineup_col == 2 and i == self.lineup_idx
            is_pick = self.lineup_pick == (2, i)
            row_rect = pygame.Rect(right_panel.x + 8, y - 2, right_panel.w - 16, reserve_line_h)
            if is_selected:
                pygame.draw.rect(self.screen, (70, 82, 110), row_rect, 0, border_radius=8)
            elif i % 2 == 0:
                pygame.draw.rect(self.screen, (28, 34, 46), row_rect, 0, border_radius=8)
            if is_pick:
                pygame.draw.rect(self.screen, CYAN, row_rect, 2, border_radius=8)
            name, num, rating = entry
            label = f"{num:>2}  {name[:14]:<14} {rating:>2}"
            self.screen.blit(self.small.render(label, True, WHITE), (right_panel.x + 12, y))
            self.lineup_rects[(2, i)] = row_rect
            y += reserve_line_h

        self.screen.blit(self.small.render("Drag or ENTER to swap | TAB/ARROWS move | SPACE start | ESC back", True, (190, 200, 210)), (24, HEIGHT - 28))
        if self.game_mode == "FANTASY":
            self.screen.blit(self.small.render("Links: club/nation/league | green strong | gold medium | red weak", True, (190, 200, 210)), (430, HEIGHT - 28))

    def draw_kit_picker(self, x, y, home, away):
        home_kits = get_team_kits(home)
        away_kits = get_team_kits(away)
        self.screen.blit(self.small.render("Kits: H to cycle home | J to cycle away", True, (200, 210, 220)), (x, y))
        box_y = y + 18
        box_w = 120
        box_h = 26
        # Home preview
        h_primary, h_secondary = home_kits[self.home_kit_index]
        pygame.draw.rect(self.screen, h_primary, (x, box_y, box_w, box_h), 0)
        pygame.draw.rect(self.screen, h_secondary, (x, box_y, box_w, box_h), 2)
        self.screen.blit(self.small.render(f"{home} ({self.home_kit_index + 1})", True, (200, 210, 220)), (x + 130, box_y + 4))
        # Away preview
        a_primary, a_secondary = away_kits[self.away_kit_index]
        ay = box_y + 30
        pygame.draw.rect(self.screen, a_primary, (x, ay, box_w, box_h), 0)
        pygame.draw.rect(self.screen, a_secondary, (x, ay, box_w, box_h), 2)
        self.screen.blit(self.small.render(f"{away} ({self.away_kit_index + 1})", True, (200, 210, 220)), (x + 130, ay + 4))

    def draw_probability_card(self, panel_x, panel_y, home, away):
        if not self.match_probabilities:
            return
        panel_w = 260
        panel_h = 120
        rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(self.screen, (26, 32, 40), rect, 0)
        pygame.draw.rect(self.screen, (60, 70, 85), rect, 2)
        title = f"{home} vs {away}"
        self.screen.blit(self.font.render("Probabilities", True, WHITE), (panel_x + 8, panel_y + 6))
        self.screen.blit(self.small.render(title, True, (200, 210, 220)), (panel_x + 8, panel_y + 30))
        probs = self.match_probabilities
        lines = [
            (f"{home} win", probs["home"]),
            ("Draw", probs["draw"]),
            (f"{away} win", probs["away"]),
        ]
        y = panel_y + 52
        for label, value in lines:
            pct = int(round(value * 100))
            line = f"{label}: {pct}%"
            self.screen.blit(self.small.render(line, True, WHITE), (panel_x + 8, y))
            y += 20

    def draw_league(self):
        if self.game_mode == "FANTASY":
            self.draw_league_home()
        elif self.league_page == "TABLE":
            self.draw_league_table()
        elif self.league_page == "STATS":
            self.draw_league_stats()
        else:
            self.draw_league_home()

    def draw_league_home(self):
        self.screen.fill((18, 22, 28))
        self.draw_profile_strip(770, 18, 390, 108)
        is_cup_week = self.week_index in self.cup_schedule
        comp = self.cup_schedule.get(self.week_index, "LEAGUE")
        title_text = f"Matchweek {self.week_index + 1}" if not is_cup_week else f"{comp} Round"
        if self.game_mode != "FANTASY":
            self.screen.blit(self.big.render("Premier League Hub", True, WHITE), (30, 20))
            self.screen.blit(self.font.render(title_text, True, (200, 210, 220)), (30, 54))
        else:
            self.screen.blit(self.big.render("Fantasy", True, WHITE), (30, 20))
            self.screen.blit(self.font.render(self.fantasy_fixture_label, True, (200, 210, 220)), (30, 54))
        if self.user_team:
            self.screen.blit(self.font.render(f"Club: {self.user_team}", True, WHITE), (30, 78))
        if self.game_mode == "FANTASY":
            top_hint = "TAB cycle | SPACE play | H club/share | P/W shop | D draft | ESC modes | Q logout"
            bottom_hint = "A/J objectives | B SBCs | N collection | R market | M my packs | E evolutions | O competitions"
            if self.fantasy_active_competition == "champions":
                bottom_hint = "A/J objectives | B SBCs | N collection | R market | M my packs | O competitions | K bracket"
            if (self.active_account_record() or {}).get("is_developer"):
                bottom_hint += " | U users"
            self.screen.blit(self.small.render(top_hint, True, (180, 190, 205)), (30, 106))
            self.screen.blit(self.small.render(bottom_hint, True, (180, 190, 205)), (30, 126))
        else:
            desc = "TAB cycle | SPACE play | A academy | ESC modes | Q logout"
            if self.game_mode != "FANTASY":
                desc = "TAB cycle | SPACE play | S skip | A academy | ESC modes | Q logout"
            self.screen.blit(self.small.render(desc, True, (180, 190, 205)), (30, 106))
            self.screen.blit(self.small.render("T train | C calendar | O cups | W transfers | Y youth intake", True, (180, 190, 205)), (30, 126))

        card_x = 30
        card_y = 160
        card_w = 520
        card_h = 120
        user_fixture = None
        if self.game_mode != "FANTASY":
            pygame.draw.rect(self.screen, (26, 32, 40), (card_x, card_y, card_w, card_h), 0)
            pygame.draw.rect(self.screen, (60, 70, 85), (card_x, card_y, card_w, card_h), 2)
            self.screen.blit(self.font.render("Next Match", True, WHITE), (card_x + 12, card_y + 8))
            if comp == "LEAGUE" and self.week_index < len(self.fixtures):
                for f in self.fixtures[self.week_index]:
                    if self.user_team in f:
                        user_fixture = f
                        break
            if user_fixture:
                home, away = user_fixture
                self.screen.blit(self.font.render(f"{home} vs {away}", True, WHITE), (card_x + 12, card_y + 40))
                if self.match_probabilities:
                    p = self.match_probabilities
                    line = f"H {int(p['home']*100)}%  D {int(p['draw']*100)}%  A {int(p['away']*100)}%"
                    self.screen.blit(self.small.render(line, True, (200, 210, 220)), (card_x + 12, card_y + 70))
            else:
                self.screen.blit(self.font.render("No fixture this week", True, WHITE), (card_x + 12, card_y + 40))

        # Club stats card
        stat_x = 30
        stat_y = 300
        stat_w = 520
        stat_h = 160
        pygame.draw.rect(self.screen, (26, 32, 40), (stat_x, stat_y, stat_w, stat_h), 0)
        pygame.draw.rect(self.screen, (60, 70, 85), (stat_x, stat_y, stat_w, stat_h), 2)
        self.screen.blit(self.font.render("Club Status", True, WHITE), (stat_x + 12, stat_y + 8))
        if self.game_mode == "FANTASY":
            club = self.ensure_fantasy_club_defaults()
            self.screen.blit(self.font.render(f"Coins: {self.fantasy_coins}", True, WHITE), (stat_x + 12, stat_y + 44))
            self.screen.blit(self.font.render(f"Squad Size: {len(self.fantasy_roster)}", True, WHITE), (stat_x + 12, stat_y + 74))
            self.screen.blit(self.font.render(f"Chemistry: {self.fantasy_chemistry_total}/33", True, WHITE), (stat_x + 12, stat_y + 104))
            self.screen.blit(self.small.render(f"Badge: {self.fantasy_club_badge_name()} | Stadium: {FANTASY_STADIUM_OPTIONS[club['stadium']]}", True, (190, 200, 215)), (stat_x + 12, stat_y + 132))
        else:
            self.screen.blit(self.font.render(f"Budget: £{self.user_budget}m", True, WHITE), (stat_x + 12, stat_y + 44))
            self.screen.blit(self.font.render(f"Form: {self.user_form:.2f}", True, WHITE), (stat_x + 12, stat_y + 74))
            self.screen.blit(self.font.render(f"Trophies: L{self.career_trophies['LEAGUE']} FA{self.career_trophies['FA']} LC{self.career_trophies['LC']}", True, WHITE), (stat_x + 12, stat_y + 104))

        if self.show_calendar and self.game_mode != "FANTASY":
            self.draw_calendar()
        if (self.show_cup_bracket or is_cup_week) and self.game_mode != "FANTASY":
            self.draw_cup_bracket(comp)
        if self.transfer_window and self.game_mode != "FANTASY":
            self.draw_transfer_window()
        if self.game_mode == "FANTASY":
            panel = pygame.Rect(600, 460, 520, 180)
            pygame.draw.rect(self.screen, (26, 32, 40), panel, 0)
            pygame.draw.rect(self.screen, (60, 70, 85), panel, 2)
            self.screen.blit(self.font.render("Fantasy Progress", True, WHITE), (panel.x + 12, panel.y + 10))
            daily_ready = sum(
                1
                for obj in self.fantasy_objectives.get("daily", [])
                if not obj.get("claimed") and obj.get("progress", 0) >= obj.get("target", 0)
            )
            weekly_ready = sum(
                1
                for obj in self.fantasy_objectives.get("weekly", [])
                if not obj.get("claimed") and obj.get("progress", 0) >= obj.get("target", 0)
            )
            self.screen.blit(self.small.render(f"Objectives ready: Daily {daily_ready} | Weekly {weekly_ready}", True, WHITE), (panel.x + 12, panel.y + 46))
            self.screen.blit(self.small.render(f"Season XP: {self.fantasy_season_xp} | Track tier: {self.fantasy_season_claimed}", True, WHITE), (panel.x + 12, panel.y + 76))
            sbc_ready = sum(1 for sbc in self.fantasy_sbc_catalog() if self.can_complete_sbc(sbc))
            self.screen.blit(self.small.render(f"SBCs ready: {sbc_ready}", True, WHITE), (panel.x + 12, panel.y + 106))
            menu_lookup = {key: (title, desc) for key, title, desc in self.fantasy_competition_menu()}
            active_key = self.fantasy_active_competition
            active_title = menu_lookup.get(active_key, ("Division Match", ""))[0]
            current = self.fantasy_competitions.get(active_key, {})
            progress = self.fantasy_competition_progress_text(active_key, current)
            self.screen.blit(self.small.render(f"Selected competition: {active_title}", True, (190, 200, 215)), (panel.x + 12, panel.y + 138))
            self.screen.blit(self.small.render(progress[:72], True, (190, 200, 215)), (panel.x + 12, panel.y + 156))

    def draw_fantasy_competitions(self):
        comps = self.fantasy_competitions or {}
        base_x = 600
        panel_w = 520
        panel_h = 280
        panel_y = 160
        pygame.draw.rect(self.screen, (26, 32, 40), (base_x, panel_y, panel_w, panel_h), 0)
        pygame.draw.rect(self.screen, (60, 70, 85), (base_x, panel_y, panel_w, panel_h), 2)
        self.screen.blit(self.font.render("Fantasy Competitions", True, WHITE), (base_x + 12, panel_y + 10))
        div = comps.get("division", {})
        ladder = comps.get("ladder", {})
        cup = comps.get("cup", {})
        weekend = comps.get("weekend", {})
        theme = comps.get("theme", {})
        lines = [
            f"Division Ladder: Tier {div.get('tier', 10)} | {div.get('points', 0)}/12 pts | {div.get('wins', 0)} wins",
            f"Weekly Ladder: Week {ladder.get('week', 1)} | {ladder.get('points', 0)} pts in {ladder.get('played', 0)}/{ladder.get('target', 6)}",
            f"Knockout Cup: Round {cup.get('round', 1)} | {'Alive' if cup.get('alive', True) else 'Reset next match'}",
            f"Weekend Challenge: {weekend.get('wins', 0)}/{weekend.get('target', 5)} wins in {weekend.get('played', 0)} matches",
        ]
        y = panel_y + 54
        for line in lines:
            self.screen.blit(self.small.render(line, True, WHITE), (base_x + 12, y))
            y += 44

    def draw_league_table(self):
        self.screen.fill((18, 22, 28))
        self.screen.blit(self.big.render("League Table", True, WHITE), (30, 20))
        self.screen.blit(self.small.render("TAB cycle", True, (180, 190, 205)), (30, 52))
        sorted_table = sorted(
            self.table.items(),
            key=lambda kv: (kv[1]["PTS"], kv[1]["GD"], kv[1]["GF"]),
            reverse=True,
        )
        header = ["Pos", "Team", "P", "W", "D", "L", "GD", "Pts"]
        col_x = [30, 620]
        rows_per_col = 10
        for col in range(2):
            y = 100
            pygame.draw.rect(self.screen, (26, 32, 40), (col_x[col], y - 6, 520, 22), 0)
            hx = col_x[col]
            self.screen.blit(self.small.render(header[0], True, (200, 210, 220)), (hx, y))
            self.screen.blit(self.small.render(header[1], True, (200, 210, 220)), (hx + 40, y))
            self.screen.blit(self.small.render(header[2], True, (200, 210, 220)), (hx + 210, y))
            self.screen.blit(self.small.render(header[3], True, (200, 210, 220)), (hx + 245, y))
            self.screen.blit(self.small.render(header[4], True, (200, 210, 220)), (hx + 280, y))
            self.screen.blit(self.small.render(header[5], True, (200, 210, 220)), (hx + 315, y))
            self.screen.blit(self.small.render(header[6], True, (200, 210, 220)), (hx + 350, y))
            self.screen.blit(self.small.render(header[7], True, (200, 210, 220)), (hx + 395, y))
            y += 26
            start = col * rows_per_col
            end = start + rows_per_col
            for i, (team, s) in enumerate(sorted_table[start:end], start=start):
                row_color = (36, 44, 56) if i % 2 == 0 else (30, 38, 50)
                if self.user_team and team == self.user_team:
                    row_color = (60, 70, 85)
                pygame.draw.rect(self.screen, row_color, (col_x[col], y - 4, 520, 22), 0)
                self.screen.blit(self.small.render(f"{i+1:>2}", True, WHITE), (col_x[col], y))
                self.screen.blit(self.small.render(f"{team:<16}", True, WHITE), (col_x[col] + 40, y))
                self.screen.blit(self.small.render(f"{s['P']:>2}", True, WHITE), (col_x[col] + 210, y))
                self.screen.blit(self.small.render(f"{s['W']:>2}", True, WHITE), (col_x[col] + 245, y))
                self.screen.blit(self.small.render(f"{s['D']:>2}", True, WHITE), (col_x[col] + 280, y))
                self.screen.blit(self.small.render(f"{s['L']:>2}", True, WHITE), (col_x[col] + 315, y))
                self.screen.blit(self.small.render(f"{s['GD']:>3}", True, WHITE), (col_x[col] + 350, y))
                self.screen.blit(self.small.render(f"{s['PTS']:>3}", True, WHITE), (col_x[col] + 395, y))
                y += 22

    def draw_league_stats(self):
        self.screen.fill((18, 22, 28))
        self.screen.blit(self.big.render("Season Center", True, WHITE), (30, 20))
        self.screen.blit(self.small.render("TAB cycle", True, (180, 190, 205)), (30, 52))

        card_x = 30
        card_y = 90
        card_w = 520
        card_h = 360
        pygame.draw.rect(self.screen, (26, 32, 40), (card_x, card_y, card_w, card_h), 0)
        pygame.draw.rect(self.screen, (60, 70, 85), (card_x, card_y, card_w, card_h), 2)
        self.screen.blit(self.font.render("Leaders", True, WHITE), (card_x + 12, card_y + 10))

        stats = [
            ("Goals", "goals"),
            ("Assists", "assists"),
            ("Clean Sheets", "clean_sheets"),
            ("Tackles", "tackles"),
        ]
        y = card_y + 42
        for label, stat_key in stats:
            self.screen.blit(self.small.render(label, True, (200, 210, 220)), (card_x + 12, y))
            leaders = self.get_leading_players(stat_key)
            if not leaders:
                self.screen.blit(self.small.render("None yet", True, (170, 180, 195)), (card_x + 140, y))
            else:
                line = " | ".join([f"{v} {n}" for n, v in leaders])
                self.screen.blit(self.small.render(line, True, WHITE), (card_x + 140, y))
            y += 26

        awards_x = 600
        awards_y = 90
        awards_w = 520
        awards_h = 180
        pygame.draw.rect(self.screen, (26, 32, 40), (awards_x, awards_y, awards_w, awards_h), 0)
        pygame.draw.rect(self.screen, (60, 70, 85), (awards_x, awards_y, awards_w, awards_h), 2)
        self.screen.blit(self.font.render("Awards Tracker", True, WHITE), (awards_x + 12, awards_y + 10))
        lines = [
            ("Top Scorer", self.awards.get("top_scorer")),
            ("Top Assists", self.awards.get("top_assists")),
            ("Most Clean Sheets", self.awards.get("top_clean_sheets")),
        ]
        y = awards_y + 44
        for label, name in lines:
            text = f"{label}: {name}" if name else f"{label}: TBD"
            self.screen.blit(self.small.render(text, True, WHITE), (awards_x + 12, y))
            y += 26

    def draw_live_stat_panels(self):
        panel_x = 30
        panel_y = 340
        panel_w = 520
        panel_h = 140
        pygame.draw.rect(self.screen, (26, 32, 40), (panel_x, panel_y, panel_w, panel_h), 0)
        pygame.draw.rect(self.screen, (60, 70, 85), (panel_x, panel_y, panel_w, panel_h), 2)
        self.screen.blit(self.small.render("Live Leaders (Season)", True, WHITE), (panel_x + 8, panel_y + 8))
        stats = [
            ("Goals", "goals"),
            ("Assists", "assists"),
            ("Clean Sheets", "clean_sheets"),
        ]
        col_w = panel_w / len(stats)
        y_start = panel_y + 30
        for idx, (label, stat_key) in enumerate(stats):
            x = panel_x + idx * col_w
            self.screen.blit(self.small.render(label, True, (200, 210, 220)), (x + 8, y_start))
            leaders = self.get_leading_players(stat_key)
            if not leaders:
                self.screen.blit(self.small.render("None yet", True, (170, 180, 195)), (x + 8, y_start + 20))
                continue
            y = y_start + 18
            for name, value in leaders:
                text = f"{value} - {name}"
                self.screen.blit(self.small.render(text, True, WHITE), (x + 8, y))
                y += 18

    def get_leading_players(self, stat, limit=3):
        entries = [(name, data.get(stat, 0)) for name, data in self.season_stats.items() if data.get(stat, 0) > 0]
        entries.sort(key=lambda kv: (-kv[1], kv[0]))
        return entries[:limit]

    def draw_academy_panel(self):
        self.screen.fill((18, 22, 28))
        title = self.big.render("Academy & Scouting", True, WHITE)
        self.screen.blit(title, (30, 20))
        self.screen.blit(self.font.render("Y: Youth intake   P: Promote   Esc: Back", True, WHITE), (30, 52))

        panel_x = 30
        panel_y = 90
        panel_w = WIDTH - 60
        panel_h = HEIGHT - 160
        pygame.draw.rect(self.screen, (26, 32, 40), (panel_x, panel_y, panel_w, panel_h), 0)
        pygame.draw.rect(self.screen, (60, 70, 85), (panel_x, panel_y, panel_w, panel_h), 2)

        if not self.academy:
            status = "No academy players yet. Press Y to run youth intake." if not self.academy_intake_done else "No academy players."
            self.screen.blit(self.font.render(status, True, WHITE), (panel_x + 16, panel_y + 20))
            return

        header = ["Name", "Age", "Pos", "OVR", "POT"]
        col_x = [panel_x + 20, panel_x + 420, panel_x + 500, panel_x + 580, panel_x + 660]
        for label, x in zip(header, col_x):
            self.screen.blit(self.small.render(label, True, (200, 210, 220)), (x, panel_y + 16))

        row_y = panel_y + 44
        row_h = 26
        max_rows = int((panel_h - 80) / row_h)
        for i, p in enumerate(self.academy[:max_rows]):
            row_color = (36, 44, 56) if i % 2 == 0 else (30, 38, 50)
            pygame.draw.rect(self.screen, row_color, (panel_x + 10, row_y - 4, panel_w - 20, row_h), 0)
            if i == self.academy_index:
                pygame.draw.rect(self.screen, (240, 200, 90), (panel_x + 10, row_y - 4, panel_w - 20, row_h), 2)
            self.screen.blit(self.font.render(p["name"], True, WHITE), (col_x[0], row_y - 2))
            self.screen.blit(self.font.render(str(p["age"]), True, WHITE), (col_x[1], row_y - 2))
            self.screen.blit(self.font.render(p["pos"], True, WHITE), (col_x[2], row_y - 2))
            self.screen.blit(self.font.render(str(p["rating"]), True, WHITE), (col_x[3], row_y - 2))
            self.screen.blit(self.font.render(str(p["potential"]), True, WHITE), (col_x[4], row_y - 2))
            row_y += row_h

    def draw_hud(self):
        mins = int(self.match_time // 60)
        secs = int(self.match_time % 60)
        time_str = f"{mins:02d}:{secs:02d}  H{self.half}"
        line1 = f"{self.current_home} {self.score_h} - {self.score_a} {self.current_away}   Time {time_str}"
        line2 = "Controls: Arrows move, P pass, K shoot, T tackle, E ask pass  |  SPACE=Kickoff  |  L=Lineups  |  R/F/G=Press/Line/Tempo"
        self.screen.blit(self.font.render(line1, True, WHITE), (20, 10))
        self.screen.blit(self.font.render(line2, True, WHITE), (20, 34))

        # tactics board (toggle with B)
        if self.show_tactics_board:
            board_w = 360
            board_h = 300
            board_x = WIDTH - board_w - 20
            board_y = 10
            pygame.draw.rect(self.screen, WHITE, (board_x, board_y, board_w, board_h), 0)
            pygame.draw.rect(self.screen, BLACK, (board_x, board_y, board_w, board_h), 2)
            title = self.font.render("Tactics Board (B to hide)", True, BLACK)
            self.screen.blit(title, (board_x + 10, board_y + 8))
            tactics = [
                (1, "4-4-2"),
                (2, "4-3-3"),
                (3, "3-5-2"),
                (4, "4-2-3-1"),
                (5, "5-3-2"),
                (6, "4-1-4-1"),
                (7, "4-2-2-2"),
                (8, "3-4-3"),
            ]
            y = board_y + 36
            for tid, name in tactics:
                label = f"{tid}. {name}"
                color = RED if self.tactic == tid else BLACK
                self.screen.blit(self.font.render(label, True, color), (board_x + 12, y))
                y += 24
            def level_name(v):
                return "Low" if v == 1 else "Med" if v == 2 else "High"
            status = [
                f"Press: {level_name(self.press_level)}",
                f"Line: {level_name(self.line_level)}",
                f"Tempo: {level_name(self.tempo_level)}",
            ]
            y += 8
            for ln in status:
                self.screen.blit(self.small.render(ln, True, BLACK), (board_x + 12, y))
                y += 18

        # commentary bar
        pygame.draw.rect(self.screen, WHITE, (0, HEIGHT - COMMENTARY_BAR_H, WIDTH, COMMENTARY_BAR_H), 0)
        if self.commentary_timer > 0:
            self.screen.blit(self.big.render(self.commentary_flash, True, BLACK), (20, HEIGHT - COMMENTARY_BAR_H + 6))
        # log (single line)
        if self.commentary:
            self.screen.blit(self.font.render(self.commentary[-1], True, BLACK), (20, HEIGHT - 22))

        if self.show_lineups:
            self.draw_lineups()

    def draw_calendar(self):
        panel_w = 520
        panel_h = 240
        panel_x = WIDTH - panel_w - 30
        panel_y = 420
        pygame.draw.rect(self.screen, (26, 32, 40), (panel_x, panel_y, panel_w, panel_h), 0)
        pygame.draw.rect(self.screen, (60, 70, 85), (panel_x, panel_y, panel_w, panel_h), 2)
        self.screen.blit(self.font.render("Calendar (next fixtures)", True, WHITE), (panel_x + 10, panel_y + 8))

        rows = []
        for w in range(self.week_index, min(self.week_index + 6, 38)):
            user_fixture = None
            comp = self.cup_schedule.get(w, "LEAGUE")
            label = "Premier League" if comp == "LEAGUE" else ("FA Cup" if comp == "FA" else "League Cup")
            if comp == "LEAGUE":
                fixtures = self.fixtures[w]
                for f in fixtures:
                    if self.user_team in f:
                        user_fixture = f
                        break
                if user_fixture:
                    home, away = user_fixture
                    vs = f"{home} vs {away}"
                else:
                    vs = "Bye/Simulated"
            else:
                vs = "Cup round (opponent TBD)"
            rows.append((w + 1, label, vs))

        # Header
        header_y = panel_y + 36
        self.screen.blit(self.small.render("Week", True, (200, 210, 220)), (panel_x + 10, header_y))
        self.screen.blit(self.small.render("Competition", True, (200, 210, 220)), (panel_x + 90, header_y))
        self.screen.blit(self.small.render("Fixture", True, (200, 210, 220)), (panel_x + 260, header_y))
        y = header_y + 20
        for w, comp, vs in rows:
            line = f"Week {w:>2}: {comp}  |  {vs}"
            self.screen.blit(self.small.render(f"{w:>2}", True, WHITE), (panel_x + 10, y))
            self.screen.blit(self.small.render(comp, True, WHITE), (panel_x + 90, y))
            self.screen.blit(self.small.render(vs, True, WHITE), (panel_x + 260, y))
            y += 22

    def draw_transfer_window(self):
        panel_w = 520
        panel_h = 240
        panel_x = WIDTH - panel_w - 30
        panel_y = 420
        pygame.draw.rect(self.screen, (26, 32, 40), (panel_x, panel_y, panel_w, panel_h), 0)
        pygame.draw.rect(self.screen, (60, 70, 85), (panel_x, panel_y, panel_w, panel_h), 2)
        self.screen.blit(self.font.render("Transfer Window", True, WHITE), (panel_x + 10, panel_y + 8))
        self.screen.blit(self.small.render("UP/DOWN select | ENTER buy | ESC close", True, (200, 210, 220)), (panel_x + 10, panel_y + 32))
        y = panel_y + 56
        if not self.transfer_offers:
            self.screen.blit(self.font.render("No offers available", True, WHITE), (panel_x + 10, y))
            return
        # Header
        self.screen.blit(self.small.render("Player", True, (200, 210, 220)), (panel_x + 10, y))
        self.screen.blit(self.small.render("Club", True, (200, 210, 220)), (panel_x + 220, y))
        self.screen.blit(self.small.render("Fee", True, (200, 210, 220)), (panel_x + 360, y))
        self.screen.blit(self.small.render("OVR", True, (200, 210, 220)), (panel_x + 445, y))
        y += 22
        for i, offer in enumerate(self.transfer_offers):
            color = RED if i == (self.selected_index % len(self.transfer_offers)) else WHITE
            name = offer["name"]
            club = offer["team"]
            fee = f"£{offer['value']}m"
            rating = f"{offer['rating']}"
            # Truncate long names to avoid overflow
            if len(name) > 18:
                name = name[:15] + "..."
            if len(club) > 14:
                club = club[:11] + "..."
            self.screen.blit(self.small.render(name, True, color), (panel_x + 10, y))
            self.screen.blit(self.small.render(club, True, color), (panel_x + 220, y))
            self.screen.blit(self.small.render(fee, True, color), (panel_x + 360, y))
            self.screen.blit(self.small.render(rating, True, color), (panel_x + 455, y))
            y += 22

    def draw_cup_bracket(self, comp):
        if comp not in ("FA", "LC"):
            return
        cup = self.cups.get(comp, {})
        panel_w = 520
        panel_h = 260
        panel_x = WIDTH - panel_w - 30
        panel_y = 150
        pygame.draw.rect(self.screen, (26, 32, 40), (panel_x, panel_y, panel_w, panel_h), 0)
        pygame.draw.rect(self.screen, (60, 70, 85), (panel_x, panel_y, panel_w, panel_h), 2)
        title = "FA Cup Bracket" if comp == "FA" else "League Cup Bracket"
        self.screen.blit(self.font.render(f"{title} (Round {cup.get('round', 0)})", True, WHITE), (panel_x + 10, panel_y + 8))
        bracket = cup.get("bracket", [])
        y = panel_y + 36
        if not bracket:
            self.screen.blit(self.font.render("Draw not available yet", True, WHITE), (panel_x + 10, y))
            return
        col_w = 165
        max_rounds = min(3, len(bracket))
        for r in range(max_rounds):
            x = panel_x + 10 + r * col_w
            self.screen.blit(self.small.render(f"R{r + 1}", True, (200, 210, 220)), (x, y))
            yy = y + 18
            for home, away in bracket[r][:5]:
                line = f"{home} v {away}"
                self.screen.blit(self.small.render(line, True, WHITE), (x, yy))
                yy += 18

    def draw_lineups(self):
        home_lineup = TEAM_LINEUPS.get(self.current_home, DEFAULT_LINEUP)
        away_lineup = TEAM_LINEUPS.get(self.current_away, DEFAULT_LINEUP)
        if self.user_team and self.user_starting:
            if self.current_home == self.user_team:
                home_lineup = self.user_starting
            elif self.current_away == self.user_team:
                away_lineup = self.user_starting

        panel_w = 520
        panel_h = 330
        panel_x = (WIDTH - panel_w) / 2
        panel_y = (HEIGHT - COMMENTARY_BAR_H - panel_h) / 2
        pygame.draw.rect(self.screen, WHITE, (panel_x, panel_y, panel_w, panel_h), 0)
        pygame.draw.rect(self.screen, BLACK, (panel_x, panel_y, panel_w, panel_h), 2)
        title = self.big.render("Lineups (L to close)", True, BLACK)
        self.screen.blit(title, (panel_x + 12, panel_y + 8))

        col_mid = panel_x + panel_w / 2
        self.screen.blit(self.font.render(self.current_home, True, BLACK), (panel_x + 12, panel_y + 42))
        self.screen.blit(self.font.render(self.current_away, True, BLACK), (col_mid + 12, panel_y + 42))

        y = panel_y + 68
        for i in range(11):
            h_entry = home_lineup[i] if i < len(home_lineup) else (f"H{i+1}", i + 1)
            a_entry = away_lineup[i] if i < len(away_lineup) else (f"A{i+1}", i + 1)
            h_name, h_num = lineup_name_number(h_entry, i)
            a_name, a_num = lineup_name_number(a_entry, i)
            h_text = f"{h_num:>2}  {h_name}"
            a_text = f"{a_num:>2}  {a_name}"
            self.screen.blit(self.small.render(h_text, True, BLACK), (panel_x + 12, y))
            self.screen.blit(self.small.render(a_text, True, BLACK), (col_mid + 12, y))
            y += 22

    def resolve_collisions(self):
        players = self.home + self.away
        min_dist = PLAYER_RADIUS * 2 - 1
        for i in range(len(players)):
            for j in range(i + 1, len(players)):
                a = players[i]
                b = players[j]
                dx = b.x - a.x
                dy = b.y - a.y
                d = math.hypot(dx, dy)
                if d == 0:
                    dx, dy = random.uniform(-1, 1), random.uniform(-1, 1)
                    d = math.hypot(dx, dy)
                if d < min_dist:
                    push = (min_dist - d) / 2
                    a.x -= (dx / d) * push
                    a.y -= (dy / d) * push
                    b.x += (dx / d) * push
                    b.y += (dy / d) * push
                    a.x = clamp(a.x, FIELD_MARGIN, WIDTH - FIELD_MARGIN)
                    a.y = clamp(a.y, FIELD_MARGIN, HEIGHT - FIELD_MARGIN)
                    b.x = clamp(b.x, FIELD_MARGIN, WIDTH - FIELD_MARGIN)
                    b.y = clamp(b.y, FIELD_MARGIN, HEIGHT - FIELD_MARGIN)

    def step(self):
        self.handle_events()
        keys = pygame.key.get_pressed()
        self.handle_controls(keys)

        now = pygame.time.get_ticks()
        dt = (now - self.last_ticks) / 1000.0
        self.last_ticks = now
        if self.active_account and self.game_mode in ("CAREER", "FANTASY"):
            self.profile_autosave_timer -= dt
            if self.profile_autosave_timer <= 0:
                self.save_active_profile()
                self.profile_autosave_timer = 8.0

        if self.commentary_timer > 0:
            self.commentary_timer -= 1 / FPS
        if self.walkout_timer > 0:
            self.walkout_timer = max(0.0, self.walkout_timer - dt)
        if self.pack_summary_timer > 0:
            self.pack_summary_timer = max(0.0, self.pack_summary_timer - dt)
        if self.state == "PACK_OPENING" and self.walkout_timer <= 0 and self.last_pack:
            self.state = "PACK_SUMMARY"
        if self.state == "MATCH_SCENE":
            if self.match_scene_timer > 0:
                self.match_scene_timer = max(0.0, self.match_scene_timer - dt)
            if self.match_scene_timer <= 0:
                if self.match_scene_continue == "FINISH_MATCH":
                    self.finish_match()
                else:
                    self.state = "LIVE"

        if self.state == "LIVE":
            if self.full_time_pending:
                self.full_time_timer -= dt
                if self.full_time_timer <= 0:
                    self.state = "MATCH_SCENE"
                    self.full_time_pending = False
                    self.set_match_scene("full")
                    pygame.display.flip()
                    self.clock.tick(FPS)
                    return
            if not self.kickoff_pending:
                self.match_time += dt
                carrier = self.ball_carrier()
                if carrier:
                    self.stats[carrier.team]["pos_time"] += dt
                if self.match_time >= self.next_insight_time:
                    self.commentary_insight("mid")
                    self.next_insight_time += random.choice([18, 22, 26])
                if self.ball_free_ticks > 0:
                    self.ball_free_ticks -= 1
                if self.tackle_cooldown > 0:
                    self.tackle_cooldown -= 1
                if self.ai_pass_cooldown > 0:
                    self.ai_pass_cooldown -= 1
                self.update_home_ai()
                self.update_ai()
                self.clamp_players()
                self.update_ball()
                self.check_out_of_bounds()
                self.check_goal()
                self.check_endline_out()
                self.keeper_save()
                self.update_set_piece()
                self.receive_ball()
                self.tackle_check()
                self.resolve_collisions()
            else:
                for p in self.home:
                    if p is self.controlled:
                        continue
                    p.move_toward(p.home_x, p.home_y, spd=p.speed * 0.5)
                for p in self.away:
                    if p is self.controlled:
                        continue
                    p.move_toward(p.home_x, p.home_y, spd=p.speed * 0.5)
                if self.kickoff_player:
                    self.kickoff_player.x = WIDTH / 2
                    self.kickoff_player.y = HEIGHT / 2
                    self.ball.x = WIDTH / 2
                    self.ball.y = HEIGHT / 2

            if self.half == 1 and self.match_time >= HALF_SECONDS:
                self.half = 2
                self.match_time = 0
                self.kickoff_pending = True
                self.reset_positions(kickoff=True)
                self.add_commentary("Halftime")
                self.set_match_scene("half")
                self.commentary_insight("half")
                self.state = "MATCH_SCENE"
            elif self.half == 2 and self.match_time >= HALF_SECONDS and not self.full_time_pending:
                self.full_time_pending = True
                self.full_time_timer = 3.0
                self.commentary_insight("full")

        if self.state == "ACCOUNT_HOME":
            self.draw_account_home()
        elif self.state in ("ACCOUNT_LOGIN", "ACCOUNT_CREATE", "ACCOUNT_DEV_LOGIN"):
            self.draw_account_form()
        elif self.state == "CLOUD_SETTINGS":
            self.draw_cloud_settings_page()
        elif self.state == "MODE_SELECT":
            self.draw_mode_select()
        elif self.state == "FANTASY_TEAM_NAME":
            self.draw_fantasy_team_name_page()
        elif self.state == "FANTASY_BUILDER":
            self.draw_fantasy_builder()
        elif self.state == "PACK_SHOP":
            self.draw_pack_shop_page()
        elif self.state == "MY_PACKS":
            self.draw_my_packs_page()
        elif self.state == "PACK_ODDS":
            self.draw_pack_odds_page()
        elif self.state == "PACK_OPENING":
            self.draw_walkout_overlay()
        elif self.state == "PACK_SUMMARY":
            self.draw_pack_summary_page()
        elif self.state == "MATCH_SCENE":
            self.draw_match_scene()
        elif self.state == "FANTASY_SBC":
            self.draw_fantasy_sbc_page()
        elif self.state == "FANTASY_SBC_BUILD":
            self.draw_fantasy_sbc_build_page()
        elif self.state == "FANTASY_OBJECTIVES":
            self.draw_fantasy_objectives_page()
        elif self.state == "FANTASY_COLLECTION":
            self.draw_fantasy_collection_page()
        elif self.state == "FANTASY_MARKET":
            self.draw_fantasy_market_page()
        elif self.state == "FANTASY_EVOLUTIONS":
            self.draw_fantasy_evolutions_page()
        elif self.state == "FANTASY_COMPETITIONS":
            self.draw_fantasy_competitions_page()
        elif self.state == "FANTASY_CLUB":
            self.draw_fantasy_club_page()
        elif self.state == "FANTASY_DRAFT":
            self.draw_fantasy_draft_page()
        elif self.state == "FANTASY_CHAMPIONS_BRACKET":
            self.draw_fantasy_champions_bracket_page()
        elif self.state == "DEV_REGISTERED_USERS":
            self.draw_registered_users_page()
        elif self.state == "FANTASY_PLAYER_PICK":
            self.draw_fantasy_player_pick_page()
        elif self.state == "TEAM_SELECT":
            self.draw_team_select()
        elif self.state == "PLAYER_SELECT":
            self.draw_player_select()
        elif self.state == "LINEUP":
            self.draw_lineup_select()
        elif self.state == "LEAGUE":
            self.draw_league()
        elif self.state == "ACADEMY":
            self.draw_academy_panel()
        else:
            self.draw_field()
            self.draw_players()
            self.draw_hud()

        pygame.display.flip()
        self.clock.tick(FPS)


if __name__ == "__main__":
    game = Game()
    game.selected_index = 0
    while True:
        game.step()
