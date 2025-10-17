import random
import re
import json
import sys
import argparse
import os
import importlib.util
import zipfile
import hashlib
import tempfile
import shutil
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Callable, Optional, Set, Tuple, Any
from datetime import datetime
if os.name == "nt":
    import tkinter
    import tkinter.ttk as ttk
    from tkinter import scrolledtext, messagebox, filedialog
    # Try optional Sun Valley theme if installed; proceed without it if missing
    try:
        import sv_ttk  # type: ignore
    except Exception:
        sv_ttk = None  # type: ignore
else:
    pass

# -----------------------------
# Persistent Config (plugins, etc.)
# -----------------------------
_CONFIG: Dict[str, Any] = {}

def _default_plugins_enabled() -> bool:
    return os.name == 'nt'

def get_config_path() -> str:
    # Prefer user roaming AppData on Windows; fallback to local file next to script
    if os.name == 'nt':
        base = os.environ.get('APPDATA') or os.environ.get('LOCALAPPDATA')
        if base:
            cfg_dir = os.path.join(base, 'HungerBens')
            try:
                os.makedirs(cfg_dir, exist_ok=True)
            except Exception:
                pass
            return os.path.join(cfg_dir, 'config.json')
    # Non-Windows or no appdata: store beside script
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, 'config.json')

def load_config() -> Dict[str, Any]:
    cfg = {"plugins_enabled": _default_plugins_enabled()}
    path = get_config_path()
    try:
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cfg.update(data)
    except Exception:
        # Ignore and use defaults
        pass
    return cfg

def save_config(cfg: Dict[str, Any]):
    try:
        path = get_config_path()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        # Best-effort only
        pass

# Initialize config cache
_CONFIG = load_config()
# Ensure the config file exists on first run by persisting defaults
try:
    save_config(_CONFIG)
except Exception:
    pass

# -----------------------------
# Base Tribute Data (can be replaced/extended by JSON roster)
# -----------------------------
tributedict: Dict[str, Dict[str, Any]] = {
    
}

# -----------------------------
# Weapons / Items / Hazards (original lists preserved)
# -----------------------------
WEAPON_VERBS = {
    "fists": "pummels", "rock": "bludgeons", "stick": "strikes", "knife": "slashes",
    "gun": "shoots", "bow": "shoots", "bow tie": "dazzles", "spear": "impales",
    "machete": "cleaves", "trident": "skewers", "slingshot": "snipes", "net": "ensnares",
    "pan": "clonks", "frying pan": "clonks", "taser": "zaps", "rubber chicken": "humiliates",
    "baguette": "wallops", "glitter bomb": "bedazzles", "garden gnome": "wallops",
    "foam sword": "bonks", "chainsaw": "rips", "umbrella": "jab-pokes", "yo-yo": "whips",
    "fish": "slaps", "harpoon": "skewers", "boomerang": "returns and whacks",
    "lute": "serenades then whacks", "meteor shard": "slices",
}
WEAPONS = set(WEAPON_VERBS.keys()) - {"fists", "rock", "stick"}
CORNUCOPIA_ITEMS = [
    "knife","gun","bow","medical kit","rope","canteen","map","compass",
    "flashlight","shield","spear","helmet","machete","trident","slingshot",
    "net","taser","pan","frying pan","chainsaw","harpoon","boomerang",
    "rubber chicken","baguette","glitter bomb","garden gnome",
    "foam sword","umbrella","yo-yo","fish","egg","lute",
]
SUPPLY_ITEMS = [
    "berries","egg","bandages","water pouch","protein bar","energy drink",
    "antidote","cloak","snare wire","fire starter","sleeping bag","binoculars",
    "adrenaline shot","moral support note","patch kit","duct tape"
]
HAZARDS = [
    "acid rain","falling debris","poison mist","lava vent","wild animal",
    "flash flood","earthquake","forest fire","quicksand","sandstorm",
    "swarm of insects","toxic spores","lightning strike","hail barrage",
    "rogue drone","mutant vines","radioactive plume","hypersonic gust",
    "magnetic storm","memory fog"
]
HAZARD_EFFECTS = {
    "acid rain":"burned","falling debris":"crushed","poison mist":"poisoned","lava vent":"scorched",
    "wild animal":"mauled","flash flood":"swept away","earthquake":"trampled","forest fire":"burned",
    "quicksand":"engulfed","sandstorm":"buried","swarm of insects":"overwhelmed","toxic spores":"choked",
    "lightning strike":"electrocuted","hail barrage":"bludgeoned","rogue drone":"laser‑tagged fatally",
    "mutant vines":"constricted","radioactive plume":"irradiated","hypersonic gust":"rag-dolled",
    "magnetic storm":"crushed by flying metal","memory fog":"forgot themselves and wandered off",
}

# -----------------------------
# Map Regions & Biomes (detailed)
# -----------------------------
# Biome definitions control map color and slightly bias environmental hazards
BIOMES_DEF: Dict[str, Dict[str, Any]] = {
    "Forest":   {"fill": "#1e3b2a", "env_delta": -0.02, "hazards": ["forest fire","toxic spores","swarm of insects"]},
    "Desert":   {"fill": "#5a4b2c", "env_delta": +0.02, "hazards": ["sandstorm","hail barrage"]},
    "Swamp":    {"fill": "#243a2a", "env_delta": +0.01, "hazards": ["toxic spores","quicksand","swarm of insects"]},
    "Marsh":    {"fill": "#2a3a2e", "env_delta": +0.01, "hazards": ["mutant vines","wild animal","swarm of insects"]},
    "Mountain": {"fill": "#3b3f4a", "env_delta": +0.01, "hazards": ["falling debris","lightning strike","earthquake"]},
    "Plains":   {"fill": "#2e3b4f", "env_delta":  0.00, "hazards": ["flash flood","hail barrage"]},
    "Ruins":    {"fill": "#3a2e3f", "env_delta": +0.01, "hazards": ["falling debris","rogue drone"]},
    "Lake":     {"fill": "#203a4f", "env_delta": -0.01, "hazards": ["flash flood","acid rain"]},
    "Tundra":   {"fill": "#2f3b3f", "env_delta": +0.01, "hazards": ["hail barrage","hypersonic gust"]},
    "Volcano":  {"fill": "#4a2e2e", "env_delta": +0.03, "hazards": ["lava vent","falling debris"]},
    "Pit":   {"fill": "#2e2e2e", "env_delta": +0.02, "hazards": ["falling debris","wild animal"]},
    "Craters": {"fill": "#3b2e2e", "env_delta": +0.02, "hazards": ["lava vent","wild animal"]},
    "Flatlands":  {"fill": "#4a4a6e", "env_delta":  0.00, "hazards": ["magnetic storm","falling debris"]},
    "Hills":    {"fill": "#3b4f2e", "env_delta":  0.00, "hazards": ["wild animal","earthquake"]},
    "Badlands": {"fill": "#4f3b2e", "env_delta": +0.02, "hazards": ["sandstorm","flash flood"]},
    "Canyon":  {"fill": "#4a3b2e", "env_delta": +0.01, "hazards": ["falling debris","wild animal"]},
    "Glacier": {"fill": "#2e4f5a", "env_delta": -0.01, "hazards": ["hail barrage","hypersonic gust"]},
    "Unknown":  {"fill": "#2e3b4f", "env_delta":  0.00, "hazards": []},
}

# Region layout in a grid (col,row) for map drawing; names double as Tribute.region values
MAP_REGIONS: Dict[str, Dict[str, Any]] = {
    # Row 0
    "Pointed Pines":           {"grid": (0,0), "biome": "Forest",   "features": ["tall pines","forage spots"]},
    "Camelback Ridge":        {"grid": (1,0), "biome": "Mountain", "features": ["cliffs","thin air"]},
    "Snow Dunes":        {"grid": (2,0), "biome": "Desert",   "features": ["snow dunes","mirages"]},
    "Frozen Plateau":     {"grid": (3,0), "biome": "Tundra",   "features": ["permafrost","hail"]},
    "Glacial Glacier":         {"grid": (4,0), "biome": "Glacier",   "features": ["crevasses","whiteout"]},
    "Deep Center":        {"grid": (5,0), "biome": "Plains",   "features": ["open fields","scattered trees"]},
    "Secret Hollow":        {"grid": (6,0), "biome": "Forest",   "features": ["dense trees","hidden paths"]},
    "Rocky Flats":        {"grid": (7,0), "biome": "Flatlands", "features": ["rock formations","caves"]},
    "Dusty Expanse":       {"grid": (8,0), "biome": "Desert",   "features": ["dust clouds","dry riverbeds"]},
    "Whispering Woods":     {"grid": (9,0), "biome": "Forest",   "features": ["tall trees","echoing sounds"]},
    # Row 1
    "Soggy Swamp":         {"grid": (0,1), "biome": "Swamp",    "features": ["bogs","mosquitoes"]},
    "Wild Woods":         {"grid": (1,1), "biome": "Forest",   "features": ["dense underbrush"]},
    "Windswept Plains":       {"grid": (2,1), "biome": "Plains",   "features": ["open wind","cover dips"]},
    "Grey Ruins":         {"grid": (3,1), "biome": "Ruins",    "features": ["crumbling walls","drone beacons"]},
    "Definitely not a Sea Lake":      {"grid": (4,1), "biome": "Lake",     "features": ["shoreline","islets"]},
    "Misty Hills":        {"grid": (5,1), "biome": "Hills", "features": ["fog","steep paths"]},
    "Ancient Grove":      {"grid": (6,1), "biome": "Forest",   "features": ["giant trees","wildlife"]},
    "Barren Badlands":      {"grid": (7,1), "biome": "Desert",   "features": ["rocky outcrops","dry gullies"]},
    "Echoing Canyon":      {"grid": (8,1), "biome": "Mountain", "features": ["sheer walls","echoes"]},
    "Thorny Thicket":      {"grid": (9,1), "biome": "Forest",   "features": ["thick brambles","hidden trails"]},
    # Row 2
    "Winding Bog":        {"grid": (0,2), "biome": "Swamp",    "features": ["mire","strangler vines"]},
    "Golden Plains":   {"grid": (1,2), "biome": "Plains",   "features": ["tall grass","burrows"]},
    "Amber Waves":             {"grid": (2,2), "biome": "Plains",   "features": ["serene environment","open fields"]},
    "Ash Fields":         {"grid": (3,2), "biome": "Volcano",  "features": ["ashfall","vents"]},
    "River Delta":        {"grid": (4,2), "biome": "Lake",     "features": ["shallows","reeds"]},
    "Crescent Cliffs":      {"grid": (5,2), "biome": "Mountain", "features": ["cliffside","rockslides"]},
    "Hidden Thicket":      {"grid": (6,2), "biome": "Forest",   "features": ["dense trees","wildlife"]},
    "Sunbaked Flats":      {"grid": (7,2), "biome": "Desert",   "features": ["cracked earth","heat mirages"]},
    "Rockslide Ridge":      {"grid": (8,2), "biome": "Mountain", "features": ["unstable rocks","narrow paths"]},
    "Shadowed Hollow":     {"grid": (9,2), "biome": "Forest",   "features": ["deep shade","twisting paths"]},
    # Row 3
    "Salted Desert":   {"grid": (0,3), "biome": "Desert",   "features": ["salt flats","dust devils"]},
    "Scree Ridge":        {"grid": (1,3), "biome": "Mountain", "features": ["scree","caves"]},
    "Murky Marsh":        {"grid": (2,3), "biome": "Marsh",    "features": ["suckholes","gnats"]},
    "Voliatile Volcano":         {"grid": (3,3), "biome": "Volcano",  "features": ["lava tubes","heat shimmer"]},
    "Crystal Flats":      {"grid": (4,3), "biome": "Flatlands",   "features": ["glittering crust","open sightlines"]},
    "Rolling Hills":      {"grid": (5,3), "biome": "Hills",    "features": ["gentle slopes","hidden dips"]},
    "Birchwood Forest":   {"grid": (6,3), "biome": "Forest",   "features": ["birch trees","leaf litter"]},
    "Dustbowl":        {"grid": (7,3), "biome": "Desert",   "features": ["dry soil","dust devils"]},
    "Granite Gorge":      {"grid": (8,3), "biome": "Mountain", "features": ["granite walls","narrow paths"]},
    "Cedar Grove":        {"grid": (9,3), "biome": "Forest",   "features": ["cedar trees","pine needles"]},
    # Row 4
    "Ckoudy Cliffs":     {"grid": (0,4), "biome": "Mountain", "features": ["sheer drops","goat paths"]},
    "Amber Savannah":     {"grid": (1,4), "biome": "Plains",   "features": ["amber grass","stray herds"]},
    "Sunken Gardens":     {"grid": (2,4), "biome": "Swamp",    "features": ["sunken ruins","humid haze"]},
    "Mirror Lake":        {"grid": (3,4), "biome": "Lake",     "features": ["glass calm","islands"]},
    "The Citadel":        {"grid": (4,4), "biome": "Ruins",    "features": ["ancient walls","Cornucopia"]},
    "Far Reaches":         {"grid": (5,4), "biome": "Desert",   "features": ["sand dunes","mirage pools"]},
    "Pine Barrens":       {"grid": (6,4), "biome": "Forest",   "features": ["pine trees","wildlife"]},
    "Blasted Hearth":      {"grid": (7,4), "biome": "Desert",   "features": ["scorched earth","heat haze"]},
    "Limestone Ledges":   {"grid": (8,4), "biome": "Mountain", "features": ["limestone cliffs","caves"]},
    "Maple Woods":        {"grid": (9,4), "biome": "Forest",   "features": ["maple trees","leaf piles"]},
    # Row 5
    "Muddy Flats":        {"grid": (0,5), "biome": "Swamp",    "features": ["muddy ground","swamp gas"]},
    "Prairie Winds":      {"grid": (1,5), "biome": "Plains",   "features": ["open fields","strong winds"]},
    "Willow Marsh":       {"grid": (2,5), "biome": "Marsh",    "features": ["weeping willows","soggy ground"]},
    "Blue Lagoon":        {"grid": (3,5), "biome": "Lake",     "features": ["clear water","fish"]},
    "Old Fortress":       {"grid": (4,5), "biome": "Ruins",    "features": ["ruined walls","watchtowers"]},
    "Scorched Expanse":   {"grid": (5,5), "biome": "Volcano",  "features": ["scorched earth","lava flows"]},
    "Oakwood":            {"grid": (6,5), "biome": "Forest",   "features": ["oak trees","acorns"]},
    "Redrock Canyon":     {"grid": (7,5), "biome": "Mountain", "features": ["red rock","narrow paths"]},
    "Canyon Springs":     {"grid": (8,5), "biome": "Mountain", "features": ["water source","steep walls"]},
    "Aspen Grove":        {"grid": (9,5), "biome": "Forest",   "features": ["aspen trees","leaf piles"]},
    # Row 6
    "Thornbrush Thicket": {"grid": (0,6), "biome": "Forest",   "features": ["thick brambles","hidden trails"]},
    "Golden Hills":       {"grid": (1,6), "biome": "Hills",    "features": ["golden grass","rolling terrain"]},
    "Reed Marsh":         {"grid": (2,6), "biome": "Marsh",    "features": ["tall reeds","soggy ground"]},
    "Serene Lake":        {"grid": (3,6), "biome": "Lake",     "features": ["calm waters","fish"]},
    "Ancient Outpost":    {"grid": (4,6), "biome": "Ruins",    "features": ["crumbling walls","watchtowers"]},
    "Blazing Flats":      {"grid": (5,6), "biome": "Desert",   "features": ["scorched earth","heat haze"]},
    "Firwood":            {"grid": (6,6), "biome": "Forest",   "features": ["fir trees","pine needles"]},
    "Cinder Ridge":       {"grid": (7,6), "biome": "Volcano",  "features": ["cinder cones","lava flows"]},
    "Granite Cliffs":     {"grid": (8,6), "biome": "Mountain", "features": ["granite walls","narrow paths"]},
    "Spruce Forest":      {"grid": (9,6), "biome": "Forest",   "features": ["spruce trees","dense foliage"]},
    # Row 7
    "Tar Pits":        {"grid": (0,7), "biome": "Pit",    "features": ["tar pits","sulfur vents"]},
    "Windy Plains":       {"grid": (1,7), "biome": "Plains",   "features": ["open fields","strong winds"]},
    "Foggy Marsh":        {"grid": (2,7), "biome": "Marsh",    "features": ["thick fog","soggy ground"]},
    "Crater Lake":       {"grid": (3,7), "biome": "Craters",  "features": ["crater walls","rocky terrain"]},
    "Derelict Stronghold": {"grid": (4,7), "biome": "Ruins",    "features": ["ruined walls","watchtowers"]},
    "Blistering Expanse": {"grid": (5,7), "biome": "Desert",   "features": ["scorched earth","heat haze"]},
    "Hemlock Thicket":    {"grid": (6,7), "biome": "Forest",   "features": ["hemlock trees","dense foliage"]},
    "Obsidian Ridge":     {"grid": (7,7), "biome": "Volcano",  "features": ["obsidian shards","lava flows"]},
    "Slate Cliffs":       {"grid": (8,7), "biome": "Mountain", "features": ["slate walls","narrow paths"]},
    "Cypress Grove":      {"grid": (9,7), "biome": "Forest",   "features": ["cypress trees","swampy ground"]},
    # Row 8
    "Quagmire":           {"grid": (0,8), "biome": "Swamp",    "features": ["quicksand","swamp gas", "giggity giggity"]},
    "Prairie Fields":     {"grid": (1,8), "biome": "Plains",   "features": ["open fields","burrows"]},
    "Mangrove Marsh":     {"grid": (2,8), "biome": "Marsh",    "features": ["mangroves","soggy ground"]},
    "Meteor Crater":      {"grid": (3,8), "biome": "Craters",  "features": ["crater walls","rocky terrain"]},
    "Forgotten Keep":     {"grid": (4,8), "biome": "Ruins",    "features": ["crumbling walls","watchtowers"]},
    "Scorching Flats":    {"grid": (5,8), "biome": "Desert",   "features": ["scorched earth","heat haze"]},
    "Juniper Wood":       {"grid": (6,8), "biome": "Forest",   "features": ["juniper trees","pine needles"]},
    "Lava Ridge":         {"grid": (7,8), "biome": "Volcano",  "features": ["lava flows","heat vents"]},
    "Basalt Cliffs":      {"grid": (8,8), "biome": "Mountain", "features": ["basalt walls","narrow paths"]},
    "Yew Forest":         {"grid": (9,8), "biome": "Forest",   "features": ["yew trees","dense foliage"]},
    # Row 9
    "Swampy Hollow":      {"grid": (0,9), "biome": "Swamp",    "features": ["swamp gas","bogs"]},
    "Endless Prairie":    {"grid": (1,9), "biome": "Plains",   "features": ["open fields","burrows"]},
    "Cattail Marsh":      {"grid": (2,9), "biome": "Marsh",    "features": ["cattails","soggy ground"]},
    "Ashen Crater":       {"grid": (3,9), "biome": "Craters",  "features": ["ash deposits","rocky terrain"]},
    "Ruined Bastion":     {"grid": (4,9), "biome": "Ruins",    "features": ["crumbling walls","watchtowers"]},
    "Blazing Desert":     {"grid": (5,9), "biome": "Desert",   "features": ["scorched earth","heat haze"]},
    "Spruce Thicket":     {"grid": (6,9), "biome": "Forest",   "features": ["spruce trees","dense foliage"]},
    "Magma Ridge":       {"grid": (7,9), "biome": "Volcano",  "features": ["magma flows","heat vents"]},
    "Quartz Cliffs":      {"grid": (8,9), "biome": "Mountain", "features": ["quartz walls","narrow paths"]},
    "Fir Forest":         {"grid": (9,9), "biome": "Forest",   "features": ["fir trees","pine needles"]},
}

# Public region names used throughout the simulator
REGIONS: List[str] = list(MAP_REGIONS.keys())

def get_region_biome(region: str) -> str:
    info = MAP_REGIONS.get(region)
    return (info or {}).get("biome", "Plains")

def get_biome_info(region: str) -> Dict[str, Any]:
    b = get_region_biome(region)
    return BIOMES_DEF.get(b, {"fill": "#2e3b4f", "env_delta": 0.0, "hazards": []})

# -----------------------------
# Utility helpers
# -----------------------------
def _a_or_an(item: str) -> str:
    if item.startswith(("a ", "an ")):
        return item
    article = "an" if item[0].lower() in "aeiou" or item.startswith(("honest", "hour")) else "a"
    return f"{article} {item}"

# -----------------------------
# Status Variant System (adds descriptive variety)
# -----------------------------
# Certain status tags (non-critical ones) now have variant synonyms for flavor.
# We maintain a mapping of a canonical base tag to its possible variants. Critical tags
# like 'fallen' and 'wounded' remain unchanged for programmatic clarity.
STATUS_VARIANTS: Dict[str, List[str]] = {
    "frustrated": ["frustrated", "exasperated", "annoyed", "irritated"],
    "shaken": ["shaken", "rattled", "unnerved", "disturbed"],
    "singed": ["singed", "scorched", "charred"],
    "disoriented": ["disoriented", "confused", "dazed", "lost"],
}

VARIANT_LOOKUP: Dict[str, str] = {variant: base for base, arr in STATUS_VARIANTS.items() for variant in arr}

def add_status_variant(t: "Tribute", base_tag: str, rng: random.Random):
    """Add a status variant for the given base tag.

    - If the base tag has variants and the tribute does not already possess ANY variant
      from that group, choose one randomly.
    - If the tribute already has one variant from the group, do nothing (avoid clutter).
    - If the base tag has no variants registered, fall back to normal add_status.
    """
    variants = STATUS_VARIANTS.get(base_tag)
    if not variants:
        t.add_status(base_tag)
        return
    if any(v in t.status for v in variants):  # already has a variant of this group
        return
    choice = rng.choice(variants)
    t.add_status(choice)

# -----------------------------
# Traits & Data Models
# -----------------------------
# Lightweight trait system; traits add small bonuses in some events.
TRAIT_POOL: List[str] = [
    "agile",      # better at avoiding hazards and traps
    "strong",     # edge in direct skirmishes
    "stealthy",   # edge in sneak attacks
    "medic",      # improved self-heal
    "lucky",      # slightly better odds against global hazards
    "clumsy",     # worse at traps and stealth
]

@dataclass
class Tribute:
    key: str
    name: str
    gender: str
    age: int
    district: int
    alive: bool = True
    kills: int = 0
    inventory: List[str] = field(default_factory=list)
    status: List[str] = field(default_factory=list)
    morale: int = 5
    notoriety: int = 0
    cause_of_death: Optional[str] = None
    # New survival fields
    hunger: float = 70                 # 0-100, lower is worse
    stamina: int = 100               # 0-100
    traits: List[str] = field(default_factory=list)
    region: str = "Center"

    def __str__(self):
        status_bits = f" [{','.join(self.status)}]" if self.status else ""
        status = "Alive" if self.alive else f"Fallen ({self.cause_of_death or 'unknown'})"
        # Compact summary includes current region and core vitals
        return (
            f"{self.name} (D{self.district}, {status}, Kills:{self.kills}, "
            f"Morale:{self.morale}, Notoriety:{self.notoriety}, H:{self.hunger}, S:{self.stamina}, Reg:{self.region}{status_bits})"
        )

    def adjust_morale(self, delta: int):
        self.morale = max(0, min(10, self.morale + delta))

    def add_status(self, tag: str):
        if tag not in self.status:
            self.status.append(tag)

    def remove_status(self, tag: str):
        if tag in self.status:
            self.status.remove(tag)

    def adjust_hunger(self, delta: int):
        self.hunger = max(0, min(100, self.hunger + delta))

    def adjust_stamina(self, delta: int):
        self.stamina = max(0, min(100, self.stamina + delta))

# -----------------------------
# Alliance tracking
# -----------------------------
class AllianceManager:
    def __init__(self):
        # Each alliance is a frozenset of tribute keys
        self.alliances: Set[frozenset[str]] = set()

    def form_alliance(self, a: Tribute, b: Tribute):
        if not a.alive or not b.alive or a.key == b.key:
            return
        # Merge if they already are indirectly connected
        existing = [al for al in self.alliances if a.key in al or b.key in al]
        group = {a.key, b.key}
        for al in existing:
            if group & set(al):
                group |= set(al)
                self.alliances.remove(al)
        self.alliances.add(frozenset(group))

    def breakup(self, tkeys: List[str]):
        to_remove = []
        for al in self.alliances:
            if any(k in al for k in tkeys):
                to_remove.append(al)
        for al in to_remove:
            self.alliances.remove(al)

    def members_of(self, tribute: Tribute) -> Set[str]:
        for al in self.alliances:
            if tribute.key in al:
                return set(al)
        return set()

    def is_allied(self, a: Tribute, b: Tribute) -> bool:
        if a.key == b.key:
            return True
        return any(a.key in al and b.key in al for al in self.alliances)

    def remove_dead(self, tributes: List[Tribute]):
        alive_keys = {t.key for t in tributes if t.alive}
        updated = set()
        for al in self.alliances:
            trimmed = al & alive_keys
            if len(trimmed) >= 2:
                updated.add(frozenset(trimmed))
        self.alliances = updated

    def to_dict(self):
        return [list(al) for al in self.alliances]

# -----------------------------
# Kill / death utility
# -----------------------------
def _kill(victim: Tribute, cause: str):
    victim.alive = False
    victim.add_status("fallen")
    victim.cause_of_death = cause

# ============================= EVENTS =============================
# Original event functions updated minimally to integrate new morale / notoriety dynamics.
# Some new events appended for alliance mechanics.

def event_find_supplies(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    t = rng.choice(tributes)
    item = rng.choice(SUPPLY_ITEMS + list(WEAPONS))
    t.inventory.append(item)
    t.adjust_morale(+1)
    if t.notoriety > 5 and rng.random() < 0.15:
        t.adjust_morale(+1)
        return [f"{t.name} finds {_a_or_an(item)}; sponsors applaud their infamous flair."]
    return [f"{t.name} finds {_a_or_an(item)} and looks pleased."]

def get_adjacent_regions(region: str) -> List[str]:
    """Return a list of region names adjacent to the given region in the grid."""
    info = MAP_REGIONS.get(region)
    if not info:
        return []
    col, row = info["grid"]
    adjacent = []
    for dc in [-1, 0, 1]:
        for dr in [-1, 0, 1]:
            if abs(dc) + abs(dr) != 1:
                continue  # only cardinal directions
            ncol, nrow = col + dc, row + dr
            for rname, rinfo in MAP_REGIONS.items():
                if rinfo["grid"] == (ncol, nrow):
                    adjacent.append(rname)
                    break
    return adjacent

def event_small_skirmish(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    if len(tributes) < 2: return []
    # Weighted targeting: higher notoriety more likely to be attacked
    weights = []
    for t in tributes:
        weights.append(1 + t.notoriety * 0.4)
    a = rng.choices(tributes, weights=weights, k=1)[0]
    b_candidates = [t for t in tributes if t != a]
    b = rng.choice(b_candidates)
    # Make sure tributes are in same or bordering regions
    region_map = {t.region: t for t in tributes}
    valid_pairs = []
    if a != b and (a.region == b.region or b.region in get_adjacent_regions(a.region)):
        valid_pairs.append((a, b))
    if not valid_pairs: return [f"{a.name} phsycically attacks {b.name}.  {b.name} is unnafected."]
    # Allies less likely to attack unless betrayal check triggers
    if sim.alliances.is_allied(a, b) and rng.random() < 0.75:
        return [f"{a.name} and {b.name} square up but recall their alliance and back off."]
    # Morale modifies success
    prob_a = 0.5 + (a.morale - b.morale) * 0.04
    # Trait modifiers
    if 'strong' in a.traits:
        prob_a += 0.05
    if 'strong' in b.traits:
        prob_a -= 0.05
    # Exhaustion or low stamina reduces odds
    if a.stamina < 30:
        prob_a -= 0.05
    if b.stamina < 30:
        prob_a += 0.05
    prob_a = max(0.1, min(0.9, prob_a))
    winner, loser = (a, b) if rng.random() < prob_a else (b, a)
    usable = [it for it in winner.inventory if it in WEAPONS]
    weapon = rng.choice(usable) if usable else rng.choice(["fists", "rock", "stick"])
    verb = WEAPON_VERBS.get(weapon, "attacks")
    # The chance of a kill is random, but influenced by weapon lethality and winner's morale
    kill_chance = 0.3 + (0.1 if weapon in ["sword", "axe", "spear", "bow"] else 0.0)
    kill_chance += (winner.morale - 5) * 0.02
    kill_chance = max(0.1, min(0.8, kill_chance))
    kill = rng.random() < kill_chance
    if kill:
        _kill(loser, f"defeated by {winner.name} ({weapon})")
        winner.kills += 1
        winner.notoriety += 1 + (1 if weapon in WEAPONS else 0)
        winner.adjust_morale(+1)
        with_part = f" with {_a_or_an(weapon)}" if weapon not in ["fists"] else ""
        # Spend some stamina in a skirmish; winner less
        winner.adjust_stamina(-10)
        loser.adjust_stamina(-20)
        return [f"{winner.name} {verb} {loser.name}{with_part}. {loser.name} is eliminated."]
    else:
        winner.adjust_stamina(-15)
        loser.adjust_stamina(-10)
        winner.adjust_morale(-1)
        loser.adjust_morale(+0)
        return [f"{winner.name} {verb} {loser.name}, but fails to finish them off. Both look shaken."]

def event_trap_failure(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    t = rng.choice(tributes)
    base = 0.18
    base -= (t.morale - 5) * 0.01  # morale reduces failure
    if 'clumsy' in t.traits:
        base += 0.05
    if 'agile' in t.traits:
        base -= 0.03
    if rng.random() < base:
        _kill(t, "botched trap")
        return [f"{t.name} tinkers with an over‑complicated trap; a spring snaps and ends their run."]
    add_status_variant(t, "frustrated", rng)
    t.adjust_morale(-1)
    return [f"{t.name}'s elaborate trap collapses harmlessly."]

def event_alliance(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    if len(tributes) < 2: return []
    a, b = rng.sample(tributes, 2)
    # Make sure tributes are in same or bordering regions
    if a.region != b.region and b.region not in get_adjacent_regions(a.region):
        return []
    if sim.alliances.is_allied(a, b):
        return [f"{a.name} and {b.name} reaffirm their alliance over shared rations."]
    sim.alliances.form_alliance(a, b)
    a.adjust_morale(+1); b.adjust_morale(+1)
    return [f"{a.name} and {b.name} form a wary alliance, exchanging nods and snacks."]

def event_environment(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    t = rng.choice(tributes)
    # Bias hazard and chance by current biome
    biome = get_region_biome(t.region)
    binfo = BIOMES_DEF.get(biome, {})
    pref = list(binfo.get("hazards", []))
    hazard = rng.choice(pref) if pref and rng.random() < 0.45 else rng.choice(HAZARDS)
    effect = HAZARD_EFFECTS[hazard]
    chance = 0.28 - (t.morale - 5) * 0.015 + float(binfo.get("env_delta", 0.0))
    if 'agile' in t.traits:
        chance -= 0.03
    if 'lucky' in t.traits:
        chance -= 0.02
    if rng.random() < chance:
        _kill(t, f"{effect} by {hazard}")
        return [f"{t.name} is {effect} by {hazard}."]
    add_status_variant(t, "shaken", rng)
    t.adjust_morale(-1)
    return [f"{t.name} narrowly avoids {hazard}."]

def event_heal(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    t = rng.choice(tributes)
    heal_items = {"medical kit": 3, "bandages": 2, "antidote": 2, "patch kit": 2, "adrenaline shot": 2}
    present = [i for i in t.inventory if i in heal_items]
    if present:
        use = rng.choice(present)
        if "wounded" in t.status:
            t.remove_status("wounded")
        t.adjust_morale(+2)
        return [f"{t.name} uses {use} to patch up and looks revitalized."]
    # Medic trait sometimes helps without items
    if 'medic' in t.traits and 'wounded' in t.status and rng.random() < 0.5:
        t.remove_status('wounded')
        t.adjust_morale(+1)
        return [f"{t.name} improvises medical care and stabilizes their wounds."]
    return [f"{t.name} improvises medical care with leaves. It doesn't help."]

def event_supply_drop(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    t = rng.choice(tributes)
    available = list(set(WEAPONS).union(SUPPLY_ITEMS))
    crate_items = rng.sample(available, rng.randint(1, 3))
    t.inventory.extend(crate_items)
    t.adjust_morale(+1)
    if t.notoriety > 6:
        bonus = rng.choice(available)
        t.inventory.append(bonus)
        return [f"A sponsor drone delivers a premium crate to {t.name}: {', '.join(crate_items+[bonus])}."]
    return [f"A sponsor drone delivers a crate to {t.name}: {', '.join(crate_items)}."]

def event_argument(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    if len(tributes) < 2: return []
    a, b = rng.sample(tributes, 2)
    # Make sure tributes are in same or bordering regions
    if a.region != b.region and b.region not in get_adjacent_regions(a.region):
        return []
    topic = rng.choice([
        "who invented fire first","proper egg-boiling duration","ethical glitter deployment",
        "ideal camouflage color","if morale is real or a construct"
    ])
    a.adjust_morale(-1); b.adjust_morale(-1)
    # Chance of alliance fracture
    fractured = False
    if sim.alliances.is_allied(a, b) and rng.random() < 0.25:
        sim.alliances.breakup([a.key, b.key])
        fractured = True
    line = f"{a.name} and {b.name} argue about {topic}. Productivity plummets."
    if fractured:
        line += " Their alliance fractures."
    return [line]

def event_funny_business(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    t = rng.choice(tributes)
    gag = rng.choice([
        "holds a motivational seminar for moss","crowns a log 'Assistant Manager'",
        "practices autograph signatures","poses heroically to no audience",
        "attempts to train a butterfly","delivers a monologue about destiny",
        "gives their weapon a pep talk","trades secrets with a tree",
        "starts a one-tribute parade","drafts arena bylaws in dirt"
    ])
    if t.morale < 4 and rng.random() < 0.4:
        t.adjust_morale(+2)
        return [f"{t.name} {gag}. It oddly lifts their spirits."]
    return [f"{t.name} {gag}."]

def event_weapon_malfunction(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    armed = [t for t in tributes if any(it in WEAPONS for it in t.inventory)]
    if not armed: return []
    t = rng.choice(armed)
    w = rng.choice([it for it in t.inventory if it in WEAPONS])
    base = 0.12 + (t.notoriety * 0.01)  # flashy gear risk
    if rng.random() < base:
        _kill(t, f"{w} malfunction")
        return [f"{t.name}'s {w} misfires catastrophically. {t.name} is eliminated."]
    add_status_variant(t, "singed", rng)
    t.adjust_morale(-2)
    return [f"{t.name}'s {w} fizzles embarrassingly, leaving scorch marks."]

def event_scavenger_find(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    t = rng.choice(tributes)
    find = rng.choice(["abandoned bivouac","cryptic rune","half-eaten ration","rusted locker","mysterious hatch"])
    item = rng.choice(SUPPLY_ITEMS + list(WEAPONS))
    t.inventory.append(item)
    return [f"{t.name} investigates {find} and acquires {_a_or_an(item)}."]

def event_stealth_fail(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    t = rng.choice(tributes)
    mishap = rng.choice(["steps on ten twigs at once","sneezes thunderously","drops all gear noisily",
                         "laughs at own joke","waves at a hidden camera"])
    t.adjust_morale(-1)
    return [f"{t.name} attempts stealth but {mishap}."]

def event_sneak_attack(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    if len(tributes) < 2: return []
    attacker, victim = rng.sample(tributes, 2)
    # Make sure tributes are in same or bordering regions
    if attacker.region != victim.region and victim.region not in get_adjacent_regions(attacker.region):
        return []
    if sim.alliances.is_allied(attacker, victim) and rng.random() < 0.8:
        return [f"{attacker.name} considers ambushing ally {victim.name} but hesitates."]
    usable = [w for w in attacker.inventory if w in WEAPONS]
    weapon = rng.choice(usable) if usable else None
    base = 0.48 + (attacker.morale - 5) * 0.04
    if 'stealthy' in attacker.traits:
        base += 0.05
    if 'agile' in attacker.traits:
        base += 0.02
    if victim.stamina < 30:
        base += 0.03
    if attacker.stamina < 30:
        base -= 0.04
    base = max(0.2, min(0.85, base))
    if rng.random() < base:
        _kill(victim, f"ambushed by {attacker.name}")
        attacker.kills += 1
        attacker.notoriety += 2
        attacker.adjust_morale(+2)
        attacker.adjust_stamina(-15)
        if weapon:
            verb = WEAPON_VERBS.get(weapon, "eliminates")
            return [f"{attacker.name} ambushes {victim.name} with {_a_or_an(weapon)} and {verb} them. {victim.name} falls."]
        return [f"{attacker.name} executes a bare-handed ambush on {victim.name}. {victim.name} is eliminated."]
    attacker.adjust_morale(-1)
    attacker.adjust_stamina(-8)
    return [f"{attacker.name}'s ambush on {victim.name} fails; {attacker.name} retreats."]

def event_dance_off(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    if len(tributes) < 2: return []
    a, b = rng.sample(tributes, 2)
    # Make sure tributes are in same or bordering regions
    if a.region != b.region and b.region not in get_adjacent_regions(a.region):
        return []
    winner = rng.choice([a, b])
    loot = rng.choice(SUPPLY_ITEMS + list(WEAPONS))
    winner.inventory.append(loot)
    winner.adjust_morale(+2)
    return [f"{a.name} and {b.name} stage a sudden dance-off. {winner.name} wins flair rights and pockets {_a_or_an(loot)}."]

def event_meteor_shower(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    t = rng.choice(tributes)
    chance = 0.22 - (t.morale - 5)*0.01
    if rng.random() < chance:
        _kill(t, "micro-meteor strike")
        shard = "meteor shard"
        alive = [x for x in tributes if x.alive]
        if alive and rng.random() < 0.5:
            rng.choice(alive).inventory.append(shard)
        return [f"A micro-meteor strikes near {t.name}. {t.name} is vaporized."]
    return [f"{t.name} weaves through incandescent falling debris."]

def event_sponsor_message(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    t = rng.choice(tributes)
    msgs = ["TRY HARDER","STYLE MATTERS","LOOK WEST","WE BELIEVE (?)","STOP WAVING","EGGS?"]
    if t.notoriety > 5:
        msgs += ["INFAMY SELLS","KEEP THE DRAMA COMING"]
    msg = rng.choice(msgs)
    t.adjust_morale(+1)
    return [f"A drone beams a hologram at {t.name}: '{msg}'"]

def event_trap_success(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    setters = [t for t in tributes if "snare wire" in t.inventory or "net" in t.inventory]
    if not setters or len(tributes) < 2: return []
    trapper = rng.choice(setters)
    targets = [t for t in tributes if t != trapper]
    victim = rng.choice(targets)
    if sim.alliances.is_allied(trapper, victim) and rng.random() < 0.6:
        return [f"{trapper.name}'s trap nearly snares ally {victim.name}; they reset it carefully."]
    chance = 0.55 + (trapper.morale - 5)*0.02
    if random.random() < chance:
        _kill(victim, f"trap set by {trapper.name}")
        trapper.kills += 1
        trapper.notoriety += 1
        return [f"{trapper.name}'s concealed trap snaps and claims {victim.name}."]
    else:
        trapper.adjust_morale(-1)
        return [f"{trapper.name}'s trap is triggered prematurely by {victim.name}, who escapes."]

def event_camouflage(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    t = rng.choice(tributes)
    t.adjust_morale(+1)
    loot = rng.choice(["berries","protein bar","cloak","bandages"])
    t.inventory.append(loot)
    return [f"{t.name} spends time camouflaging and quietly acquires {loot}."]

def event_reckless_experiment(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    t = rng.choice(tributes)
    chance = 0.15 - (t.morale - 5)*0.01
    if rng.random() < chance:
        _kill(t, "chemical experiment explosion")
        return [f"{t.name} tests an improvised chemical mixture. It detonates violently."]
    t.add_status("wounded")
    t.adjust_morale(-2)
    return [f"{t.name} experiments with arena flora and suffers minor burns."]

def event_chain_hunt(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    if len(tributes) < 3: return []
    a, b, c = rng.sample(tributes, 3)
    lines = [f"{a.name} chases {b.name}; {b.name} runs into {c.name}. Chaos ensues."]
    r = rng.random()
    if r < 0.33:
        _kill(b, f"eliminated in chain hunt by {a.name}")
        a.kills += 1
        lines.append(f"{a.name} eliminates {b.name} while {c.name} vanishes.")
    elif r < 0.66:
        _kill(a, f"countered by {c.name}")
        c.kills += 1
        lines.append(f"{c.name} counters brilliantly and takes down {a.name}; {b.name} escapes.")
    else:
        _kill(c, f"used as distraction by {b.name}")
        b.kills += 1
        lines.append(f"{b.name} uses {c.name} as a distraction and eliminates them.")
    return lines

def event_spooked_flock(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    t = rng.choice(tributes)
    t.adjust_morale(-1)
    return [f"{t.name} startles a flock of metallic birds; the clatter rattles their nerves."]

# New alliance-centric events
def event_alliance_aid(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    allied_groups = [al for al in sim.alliances.alliances if len(al) >= 2]
    if not allied_groups: return []
    group = rng.choice(list(allied_groups))
    members = [t for t in tributes if t.key in group]
    if not members: return []
    helper = rng.choice(members)
    receiver_candidates = [m for m in members if m != helper]
    if not receiver_candidates: return []
    receiver = rng.choice(receiver_candidates)
    item = rng.choice(SUPPLY_ITEMS)
    receiver.inventory.append(item)
    helper.adjust_morale(+1); receiver.adjust_morale(+1)
    return [f"{helper.name} shares {item} with ally {receiver.name}; their cohesion strengthens."]

def event_alliance_betrayal(tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    # Low chance betrayal
    if len(sim.alliances.alliances) == 0: return []
    if rng.random() > 0.25: return []
    group = rng.choice(list(sim.alliances.alliances))
    if len(group) < 2: return []
    keys = list(group)
    attacker_key, victim_key = rng.sample(keys, 2)
    attacker = next(t for t in tributes if t.key == attacker_key)
    victim = next(t for t in tributes if t.key == victim_key)
    prob = 0.5 + (attacker.morale - victim.morale)*0.05
    prob = max(0.2, min(0.85, prob))
    if rng.random() < prob:
        _kill(victim, f"betrayed by {attacker.name}")
        attacker.kills += 1
        attacker.notoriety += 3
        sim.alliances.breakup([attacker.key, victim.key])
        return [f"Betrayal! {attacker.name} turns on ally {victim.name}, eliminating them."]
    attacker.adjust_morale(-2)
    sim.alliances.breakup([attacker.key, victim.key])
    return [f"{attacker.name} attempts to betray {victim.name} but fails; the alliance dissolves in distrust."]

# ============================= GLOBAL EVENTS =============================
def global_weather_shift(all_tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    weather = rng.choice(["frigid hail","sweltering humidity","dense fog","glitter drizzle","electrostatic haze"])
    lines = [f"A sudden arena-wide weather shift blankets the zone in {weather}."]
    for t in all_tributes:
        if not t.alive: continue
        if weather in ["dense fog","glitter drizzle"] and rng.random() < 0.25:
            add_status_variant(t, "disoriented", rng)
            lines.append(f"{t.name} becomes disoriented.")
        if weather == "frigid hail" and rng.random() < 0.15:
            t.add_status("wounded")
            t.adjust_morale(-1)
    return lines

def global_safe_zone_shrink(all_tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    lines = ["Loud klaxons blare: the safe zone contracts sharply toward the Cornucopia."]
    threatened = [t for t in all_tributes if t.alive and rng.random() < 0.25]
    for t in threatened:
        death_chance = 0.40 - (t.morale - 5)*0.02
        if 'lucky' in t.traits:
            death_chance -= 0.03
        if rng.random() < death_chance:
            _kill(t, "caught outside perimeter")
            lines.append(f"{t.name} is caught outside the new perimeter and collapses.")
        else:
            t.adjust_morale(-1)
            lines.append(f"{t.name} barely sprints inside the perimeter, shaken.")
    return lines

def global_region_collapse(all_tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    # Pick a non-center region to collapse; survivors flee to Center
    collapsing = rng.choice([r for r in REGIONS if r != 'The Citadel'])
    lines = [f"A siren howls: the {collapsing} region becomes a kill zone!"]
    for t in list(all_tributes):
        if not t.alive:
            continue
        if t.region == collapsing:
            chance = 0.45 - (t.morale - 5)*0.02
            if 'agile' in t.traits:
                chance -= 0.04
            if 'lucky' in t.traits:
                chance -= 0.03  
            if rng.random() < chance:
                _kill(t, f"region collapse in {collapsing}")
                lines.append(f"{t.name} is overwhelmed by the collapsing {collapsing} sector.")
            else:
                t.region = 'Center'
                t.adjust_morale(-1)
                lines.append(f"{t.name} escapes {collapsing} just in time and flees to Center.")
    return lines

def global_supply_shortage(all_tributes: List[Tribute], rng: random.Random, sim) -> List[str]:
    lines = ["A scarcity protocol triggers: many food caches evaporate in a flash of light."]
    for t in all_tributes:
        if not t.alive: continue
        edible = [i for i in t.inventory if i in ["berries","protein bar","egg","water pouch","energy drink"]]
        if edible and rng.random() < 0.5:
            lost = rng.choice(edible)
            t.inventory.remove(lost)
            t.adjust_morale(-1)
            lines.append(f"{t.name} loses {lost}.")
    return lines

GLOBAL_EVENTS: List[Callable[[List[Tribute], random.Random, "HungerBensSimulator"], List[str]]] = [
    global_weather_shift,
    global_safe_zone_shrink,
    global_supply_shortage,
    global_region_collapse,
]

# Event pools (call signatures now expect sim)
DAY_EVENTS: List[Callable[[List[Tribute], random.Random, "HungerBensSimulator"], List[str]]] = [
    event_find_supplies, event_small_skirmish, event_trap_failure, event_alliance,
    event_supply_drop, event_argument, event_funny_business, event_scavenger_find,
    event_weapon_malfunction, event_stealth_fail, event_sneak_attack, event_dance_off,
    event_sponsor_message, event_trap_success, event_camouflage, event_reckless_experiment,
    event_chain_hunt, event_spooked_flock, event_alliance_aid, event_alliance_betrayal
]

NIGHT_EVENTS: List[Callable[[List[Tribute], random.Random, "HungerBensSimulator"], List[str]]] = [
    event_trap_failure, event_environment, event_small_skirmish, event_heal,
    event_funny_business, event_weapon_malfunction, event_stealth_fail, event_sneak_attack,
    event_meteor_shower, event_sponsor_message, event_trap_success, event_camouflage,
    event_reckless_experiment, event_spooked_flock, event_alliance_aid, event_alliance_betrayal
]

# Default weights baseline
BASE_EVENT_WEIGHTS = {
    event_find_supplies: 1.2,
    event_small_skirmish: 1.3,
    event_trap_failure: 0.9,
    event_alliance: 0.8,
    event_supply_drop: 0.7,
    event_argument: 0.9,
    event_funny_business: 0.7,
    event_scavenger_find: 1.0,
    event_weapon_malfunction: 0.5,
    event_stealth_fail: 0.6,
    event_sneak_attack: 1.1,
    event_dance_off: 0.4,
    event_sponsor_message: 0.6,
    event_trap_success: 0.8,
    event_camouflage: 0.8,
    event_reckless_experiment: 0.5,
    event_chain_hunt: 0.5,
    event_spooked_flock: 0.6,
    event_alliance_aid: 0.5,
    event_alliance_betrayal: 0.3,
    event_environment: 1.0,
    event_heal: 0.9,
    event_meteor_shower: 0.4,
}

# -----------------------------
# Windows-only Plugin System
# -----------------------------
# Plugin API (optional functions in each plugin module):
#   - get_custom_content() -> dict with keys like {"weapons": {...}, "items": [...], "hazards": {...}}
#   - get_events() -> {"day": [callables], "night": [callables], "global": [callables]}
#   - get_event_weights() -> {callable or callable.__name__: float}
# Any provided content/events will be merged into the simulator's registries.
#
# Search order (Windows):
#   1) HUNGER_BENS_PLUGIN_DIRS (os.pathsep-separated list)
#   2) Repo-relative: <repo>/docs/plugins
#   3) %LOCALAPPDATA%\HungerBens\plugins
#   4) %APPDATA%\HungerBens\plugins (Roaming)
#   5) %PROGRAMDATA%\HungerBens\plugins (machine-wide)
#
# Files supported:
#   - Single-file Python modules: *.py (legacy)
#   - Zipped plugins: *.ben (zip archives; will be extracted to cache and loaded)

_PLUGINS_LOADED = False

def _log_plugin(line: str, log_fn: Optional[Callable[[str], None]] = None):
    try:
        if log_fn:
            log_fn(line)
        else:
            print(line)
    except Exception:
        pass

def _iter_plugin_paths() -> List[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_plugins = os.path.join(here, 'plugins')
    env_dirs_raw = os.environ.get('HUNGER_BENS_PLUGIN_DIRS', '')
    env_dirs = [p for p in env_dirs_raw.split(os.pathsep) if p]
    candidates: List[str] = []
    if env_dirs:
        candidates.extend(env_dirs)
    # Default search locations
    candidates.append(repo_plugins)
    if os.name == 'nt':
        lap = os.environ.get('LOCALAPPDATA')
        rap = os.environ.get('APPDATA')  # Roaming
        prog = os.environ.get('PROGRAMDATA')
        if lap:
            candidates.append(os.path.join(lap, 'HungerBens', 'plugins'))
        if rap:
            candidates.append(os.path.join(rap, 'HungerBens', 'plugins'))
        if prog:
            candidates.append(os.path.join(prog, 'HungerBens', 'plugins'))
    # Deduplicate while preserving order
    seen = set()
    ordered = []
    for p in candidates:
        if p and p not in seen:
            seen.add(p)
            ordered.append(p)
    return [p for p in ordered if os.path.isdir(p)]

def scan_plugin_files() -> List[Tuple[str, str]]:
    """Return list of (plugin_id, absolute_path) for available plugin files without importing.
    Supports:
      - *.py single-file plugins
      - *.ben (zip archives; treated as plugin bundles)
    Skips __init__.py.
    """
    results: List[Tuple[str, str]] = []
    for d in _iter_plugin_paths():
        try:
            # We prefer .ben over .py if both exist with same id in the same folder
            files = sorted(os.listdir(d), key=lambda n: (0 if n.endswith('.ben') else 1, n.lower()))
            for fname in files:
                lower = fname.lower()
                # Skip non-plugin files
                if not (lower.endswith('.py') or lower.endswith('.ben')) or fname == '__init__.py':
                    continue
                fpath = os.path.join(d, fname)
                pid = os.path.splitext(fname)[0]
                results.append((pid, fpath))
        except Exception:
            continue
    # Dedup by id with first occurrence kept
    seen: Set[str] = set()
    unique: List[Tuple[str, str]] = []
    for pid, path in results:
        if pid in seen:
            continue
        seen.add(pid)
        unique.append((pid, path))
    return unique

def _hash_file(path: str) -> str:
    try:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        # Fallback to mtime+size hash
        try:
            st = os.stat(path)
            raw = f"{getattr(st, 'st_mtime', 0)}:{getattr(st, 'st_size', 0)}".encode()
            return hashlib.sha256(raw).hexdigest()
        except Exception:
            return "unknown"

def _get_cache_base_dir() -> str:
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('APPDATA') or tempfile.gettempdir()
    p = os.path.join(base, 'HungerBens', 'plugins_cache')
    try:
        os.makedirs(p, exist_ok=True)
    except Exception:
        pass
    return p

def _prune_old_caches(cache_base: str, pid: str, keep_path: str):
    try:
        for name in os.listdir(cache_base):
            if name.startswith(f"{pid}-"):
                full = os.path.join(cache_base, name)
                if os.path.abspath(full) != os.path.abspath(keep_path):
                    shutil.rmtree(full, ignore_errors=True)
    except Exception:
        pass

def _extract_zip_plugin(pid: str, archive_path: str, log_fn: Optional[Callable[[str], None]]) -> Optional[str]:
    """Extract .ben (zip) plugin into a versioned cache folder and return the extraction dir."""
    try:
        sig = _hash_file(archive_path)[:12]
        cache_base = _get_cache_base_dir()
        dest_dir = os.path.join(cache_base, f"{pid}-{sig}")
        if not os.path.isdir(dest_dir):
            # Fresh extract
            try:
                os.makedirs(dest_dir, exist_ok=True)
            except Exception:
                pass
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(dest_dir)
        # Prune other versions of same pid
        _prune_old_caches(cache_base, pid, dest_dir)
        return dest_dir
    except Exception as e:
        _log_plugin(f"[Plugins] Failed to extract {os.path.basename(archive_path)}: {e}", log_fn)
        return None

def _find_zip_entry_file(extracted_dir: str) -> Optional[str]:
    """Heuristics to locate the plugin's entry .py within an extracted plugin folder."""
    try:
        # 1) Prefer ./plugin.py
        candidate = os.path.join(extracted_dir, 'plugin.py')
        if os.path.isfile(candidate):
            return candidate
        # 2) Prefer package ./plugin/__init__.py
        pkg_init = os.path.join(extracted_dir, 'plugin', '__init__.py')
        if os.path.isfile(pkg_init):
            return pkg_init
        # 3) If exactly one top-level .py exists, use it
        tops = [f for f in os.listdir(extracted_dir) if f.endswith('.py')]
        if len(tops) == 1:
            return os.path.join(extracted_dir, tops[0])
        # 4) If there's a package folder with __init__, and it's the only package, use it
        pkgs = []
        for entry in os.listdir(extracted_dir):
            p = os.path.join(extracted_dir, entry)
            if os.path.isdir(p) and os.path.isfile(os.path.join(p, '__init__.py')):
                pkgs.append(os.path.join(p, '__init__.py'))
        if len(pkgs) == 1:
            return pkgs[0]
    except Exception:
        pass
    return None

def load_windows_plugins(log_fn: Optional[Callable[[str], None]] = None):
    global _PLUGINS_LOADED
    if _PLUGINS_LOADED:
        return
    if os.name != 'nt':
        return
    # Proactively ensure common plugin directories exist (per-user and machine-wide)
    try:
        lap = os.environ.get('LOCALAPPDATA')
        rap = os.environ.get('APPDATA')
        prog = os.environ.get('PROGRAMDATA')
        for base in (lap, rap, prog):
            if not base:
                continue
            pdir = os.path.join(base, 'HungerBens', 'plugins')
            try:
                os.makedirs(pdir, exist_ok=True)
            except Exception as e:
                _log_plugin(f"[Plugins] Could not create {pdir}: {e}", log_fn)
    except Exception:
        pass
    plugin_dirs = _iter_plugin_paths()
    if not plugin_dirs:
        _PLUGINS_LOADED = True
        return
    loaded_any = False
    loaded_ids: Set[str] = set()
    # Integrate config for per-plugin enable/disable; discover new plugins
    cfg_plugins: Dict[str, Any] = _CONFIG.get('plugins', {}) if isinstance(_CONFIG.get('plugins'), dict) else {}
    discovered = scan_plugin_files()
    # Seed config entries for new plugins
    for pid, ppath in discovered:
        entry = cfg_plugins.get(pid)
        if not isinstance(entry, dict):
            cfg_plugins[pid] = {"enabled": True, "path": ppath}
        else:
            # Update path if changed
            if ppath and entry.get('path') != ppath:
                entry['path'] = ppath
    _CONFIG['plugins'] = cfg_plugins
    try:
        save_config(_CONFIG)
    except Exception:
        pass

    # Helper to integrate a loaded module
    def _integrate_plugin_module(mod, fname: str):
        nonlocal loaded_any
        plugin_events: Dict[str, List[Callable]] = {}
        # Content
        if hasattr(mod, 'get_custom_content'):
            try:
                cc = mod.get_custom_content()  # type: ignore[attr-defined]
                if isinstance(cc, dict) and cc:
                    integrate_custom_content(cc)
                    _log_plugin(f"[Plugins] Integrated custom content from {fname}", log_fn)
            except Exception as e:
                _log_plugin(f"[Plugins] get_custom_content error in {fname}: {e}", log_fn)
        # Events
        if hasattr(mod, 'get_events'):
            try:
                ev = mod.get_events()  # type: ignore[attr-defined]
                if isinstance(ev, dict):
                    for k in ('day','night','global'):
                        arr = ev.get(k, [])
                        if isinstance(arr, list):
                            plugin_events[k] = [f for f in arr if callable(f)]
                        else:
                            plugin_events[k] = []
                    if plugin_events.get('day'):
                        DAY_EVENTS.extend(plugin_events['day'])
                    if plugin_events.get('night'):
                        NIGHT_EVENTS.extend(plugin_events['night'])
                    if plugin_events.get('global'):
                        GLOBAL_EVENTS.extend(plugin_events['global'])
                    _log_plugin(f"[Plugins] Registered events from {fname}", log_fn)
            except Exception as e:
                _log_plugin(f"[Plugins] get_events error in {fname}: {e}", log_fn)
        # Event weights
        if hasattr(mod, 'get_event_weights'):
            try:
                w = mod.get_event_weights()  # type: ignore[attr-defined]
                if isinstance(w, dict):
                    for key, weight in w.items():
                        if not isinstance(weight, (int, float)):
                            continue
                        func = None
                        if callable(key):
                            func = key
                        elif isinstance(key, str):
                            # Try to resolve by name among plugin events
                            for arr in (plugin_events.get('day', []), plugin_events.get('night', []), plugin_events.get('global', [])):
                                for f in arr:
                                    if getattr(f, '__name__', '') == key:
                                        func = f
                                        break
                                if func:
                                    break
                        if func:
                            BASE_EVENT_WEIGHTS[func] = float(weight)
                    _log_plugin(f"[Plugins] Applied event weights from {fname}", log_fn)
            except Exception as e:
                _log_plugin(f"[Plugins] get_event_weights error in {fname}: {e}", log_fn)
        loaded_any = True

    # Load plugins
    for d in plugin_dirs:
        try:
            files = sorted(os.listdir(d), key=lambda n: (0 if n.lower().endswith('.ben') else 1, n.lower()))
            for fname in files:
                lower = fname.lower()
                if not (lower.endswith('.py') or lower.endswith('.ben')) or fname == '__init__.py':
                    continue
                fpath = os.path.join(d, fname)
                pid = os.path.splitext(fname)[0]
                # De-duplicate by pid across directories and file types
                if pid in loaded_ids:
                    continue
                # Respect per-plugin enable flag
                pen = cfg_plugins.get(pid, {}).get('enabled', True)
                if not pen:
                    _log_plugin(f"[Plugins] Skipped disabled plugin {fname}", log_fn)
                    continue
                try:
                    if lower.endswith('.py'):
                        mod_name = f"hb_plugin_{pid}"
                        spec = importlib.util.spec_from_file_location(mod_name, fpath)
                        if not spec or not spec.loader:
                            continue
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules[mod_name] = mod
                        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
                        _log_plugin(f"[Plugins] Loaded {fname}", log_fn)
                        _integrate_plugin_module(mod, fname)
                        loaded_ids.add(pid)
                    elif lower.endswith('.ben'):
                        extracted = _extract_zip_plugin(pid, fpath, log_fn)
                        if not extracted:
                            continue
                        # Add extracted root to sys.path for any internal imports
                        if extracted not in sys.path:
                            sys.path.insert(0, extracted)
                        entry = _find_zip_entry_file(extracted)
                        if not entry:
                            _log_plugin(f"[Plugins] No suitable entry .py found in {fname}", log_fn)
                            continue
                        mod_name = f"hb_plugin_{pid}"
                        spec = importlib.util.spec_from_file_location(mod_name, entry)
                        if not spec or not spec.loader:
                            _log_plugin(f"[Plugins] Could not build loader for {fname}", log_fn)
                            continue
                        mod = importlib.util.module_from_spec(spec)
                        sys.modules[mod_name] = mod
                        # If package, inform importlib about package layout
                        if os.path.basename(entry) == '__init__.py':
                            try:
                                mod.__package__ = mod_name
                                if hasattr(spec, 'submodule_search_locations') and spec.submodule_search_locations is None:  # type: ignore[attr-defined]
                                    spec.submodule_search_locations = [os.path.dirname(entry)]  # type: ignore[attr-defined]
                            except Exception:
                                pass
                        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
                        _log_plugin(f"[Plugins] Loaded {fname} (archive)", log_fn)
                        _integrate_plugin_module(mod, fname)
                        loaded_ids.add(pid)
                except Exception as e:
                    _log_plugin(f"[Plugins] Failed to load {fname}: {e}", log_fn)
        except Exception as e:
            _log_plugin(f"[Plugins] Directory error for {d}: {e}", log_fn)
    _PLUGINS_LOADED = True
    if loaded_any:
        _log_plugin("[Plugins] Windows plugins loaded.", log_fn)

# -----------------------------
# Simulator
# -----------------------------
class HungerBensSimulator:
    def __init__(
        self,
        tribute_data: Dict[str, Dict[str, Any]],
        seed: Optional[int] = None,
        max_days: int = 50,
        verbose: bool = True,
        export_log: Optional[str] = None,
        strict_shutdown: Optional[int] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.rng = random.Random(seed)
        self.seed = seed
        self.max_days = max_days
        self.verbose = verbose
        self.day_count = 0
        self.strict_shutdown = strict_shutdown
        self._log_callback = log_callback
        self.tributes: List[Tribute] = [
            Tribute(
                key=k,
                name=v["name"],
                gender=v.get("gender","unknown"),
                age=int(v.get("age", 0)),
                district=int(v.get("district", 0)),
            )
            for k, v in tribute_data.items()
        ]
        self.log: List[str] = []
        self._cornucopia_run = False
        self.alliances = AllianceManager()
        self.history_stats = {
            "day_morale_avg": [],
            "events_run": 0,
        }
        self.export_log_path = export_log
        self.death_log: List[Dict[str, Any]] = []
        # Initialize traits and regions deterministically by seed
        for t in self.tributes:
            # Assign region
            try:
                t.region = self.rng.choice(REGIONS)
            except Exception:
                t.region = 'Center'
            # Assign 0-2 traits
            num = 0
            r = self.rng.random()
            if r < 0.55:
                num = 1
            if r < 0.20:
                num = 2
            if TRAIT_POOL and num > 0:
                try:
                    t.traits = self.rng.sample(TRAIT_POOL, k=num)
                except Exception:
                    t.traits = []

        # Step-mode state (GUI manual stepping)
        self._step_active: bool = False
        self._step_phase: Optional[str] = None  # intro, corn, setup_day, day, setup_night, night, end_of_day, finalize, done
        self._step_events_left: int = 0
        self._step_block: Optional[str] = None  # 'day' or 'night'

    # --- Manual step mode API (for GUI) ---
    def start_stepping(self):
        """Prepare the simulator to run one event at a time via step_once()."""
        if self._step_active:
            return
        self._step_active = True
        self._step_phase = 'intro'
        # Ensure cornucopia not run yet
        self._cornucopia_run = False

    def _prepare_block(self, block: str):
        # Setup event count for a block
        alive = self.alive_tributes()
        events_to_run = 0
        if alive:
            events_to_run = min(len(alive), self.rng.randint(3, 6))
        self._step_events_left = events_to_run
        self._step_block = block

    def _print_fallen_for_phase(self, phase: str):
        fallen = [t for t in self.tributes if not t.alive and f"(Fallen logged {t.key})" not in t.__dict__]
        if fallen:
            self._log("\nFallen this phase:")
            for f in fallen:
                self._log(f" - {f.name}")
                f.__dict__[f"(Fallen logged {f.key})"] = True
                self.death_log.append({"name": f.name, "cause": f.cause_of_death, "day": self.day_count, "phase": phase})
        self.alliances.remove_dead(self.tributes)

    def step_once(self) -> bool:
        """Execute the next event unit. Returns True when the simulation is fully complete."""
        if not self._step_active:
            # If not in step mode, run to completion
            self.run()
            return True
        if self._step_phase == 'done':
            return True
        # Intro step
        if self._step_phase == 'intro':
            self._log_intro()
            self._step_phase = 'corn'
            return False
        # Cornucopia step
        if self._step_phase == 'corn':
            self._cornucopia_phase()
            self._step_phase = 'setup_day'
            return False
        # Setup next day
        if self._step_phase == 'setup_day':
            # Termination checks before starting a new day
            if len(self.alive_tributes()) <= 1 or self.day_count >= self.max_days or (self.strict_shutdown and self.day_count >= self.strict_shutdown and len(self.alive_tributes()) > 2):
                self._step_phase = 'finalize'
            else:
                self.day_count += 1
                self._log(f"\n--- Day {self.day_count} ---")
                # Track average morale like normal
                alive = self.alive_tributes()
                if alive:
                    avg_morale = sum(t.morale for t in alive)/len(alive)
                    self.history_stats["day_morale_avg"].append(avg_morale)
                self._prepare_block('day')
                self._step_phase = 'day'
            return False
        # Day events (one at a time)
        if self._step_phase == 'day':
            if self._step_events_left <= 0:
                # After block: maybe global event, then fallen, then setup night
                self._maybe_global_event()
                self._print_fallen_for_phase('day')
                self._step_phase = 'setup_night'
                return False
            alive = self.alive_tributes()
            if len(alive) <= 1:
                self._step_phase = 'finalize'
                return False
            event_func = self._choose_weighted_event(DAY_EVENTS)
            narrative = event_func(alive, self.rng, self)
            self.history_stats["events_run"] += 1
            for line in narrative:
                if line:
                    self._log(line)
            self._post_event_cleanup()
            self._step_events_left -= 1
            return False
        # Setup night
        if self._step_phase == 'setup_night':
            self._log(f"\n*** Night {self.day_count} ***")
            self._prepare_block('night')
            self._step_phase = 'night'
            return False
        # Night events (one at a time)
        if self._step_phase == 'night':
            if self._step_events_left <= 0:
                # After night block: apply resource tick, then maybe proceed
                self._print_fallen_for_phase('night')
                self._resource_tick()
                self._step_phase = 'setup_day'
                return False
            alive = self.alive_tributes()
            if len(alive) <= 1:
                self._step_phase = 'finalize'
                return False
            event_func = self._choose_weighted_event(NIGHT_EVENTS)
            narrative = event_func(alive, self.rng, self)
            self.history_stats["events_run"] += 1
            for line in narrative:
                if line:
                    self._log(line)
            self._post_event_cleanup()
            self._step_events_left -= 1
            return False
        # Finalization step
        if self._step_phase == 'finalize':
            self._announce_winner()
            self._output_stats()
            if self.export_log_path:
                self._export_run()
            self._step_phase = 'done'
            return True
        return False

    # --- Basic helpers ---
    def alive_tributes(self) -> List[Tribute]:
        return [t for t in self.tributes if t.alive]

    def _log(self, message: str):
        self.log.append(message)
        if self.verbose:
            print(message)
        if self._log_callback:
            try:
                self._log_callback(message)
            except Exception:
                # Fail silently so simulation continues even if GUI callback breaks
                pass

    # --- Simulation Control ---
    def run(self):
        self._log_intro()
        self._cornucopia_phase()
        while len(self.alive_tributes()) > 1 and self.day_count < self.max_days:
            self.day_count += 1
            self._simulate_day()
            if len(self.alive_tributes()) <= 1:
                break
            self._simulate_night()
            if self.day_count == 3 and len(self.alive_tributes()) > 4:
                self._feast_event()
            if self.strict_shutdown and self.day_count >= self.strict_shutdown and len(self.alive_tributes()) > 2:
                self._log("\nEARLY ARENA TERMINATION PROTOCOL TRIGGERED.")
                break
        self._announce_winner()
        self._output_stats()
        if self.export_log_path:
            self._export_run()
        return self.log

    # --- Phase Methods ---
    def _cornucopia_phase(self):
        if self._cornucopia_run: return
        self._cornucopia_run = True
        self._log("--- Cornucopia (Bloodbath) ---")
        tribs = self.alive_tributes()
        self.rng.shuffle(tribs)
        actions_summary: List[str] = []
        engaged = set()

        for t in tribs:
            if not t.alive or t.key in engaged:
                continue
            roll = self.rng.random()
            if roll < 0.30 and len(self.alive_tributes()) > 1:
                opponents = [o for o in self.alive_tributes() if o.key != t.key and o.key not in engaged]
                if opponents:
                    opp = self.rng.choice(opponents)
                    engaged.add(t.key); engaged.add(opp.key)
                    # Morale impacts who wins initial struggle
                    prob_t = 0.5 + (t.morale - opp.morale) * 0.05
                    winner, loser = (t, opp) if self.rng.random() < prob_t else (opp, t)
                    loot = self.rng.choice(CORNUCOPIA_ITEMS)
                    winner.inventory.append(loot)
                    _kill(loser, f"bloodbath elimination by {winner.name}")
                    winner.kills += 1
                    winner.notoriety += 1
                    winner.adjust_morale(+1)
                    actions_summary.append(f"{winner.name} overpowers {loser.name} at the Cornucopia and claims {_a_or_an(loot)}.")
                else:
                    item = self.rng.choice(CORNUCOPIA_ITEMS)
                    t.inventory.append(item)
                    actions_summary.append(f"{t.name} hastily grabs {_a_or_an(item)}.")
            elif roll < 0.70:
                grabs = self.rng.randint(1, 3)
                items = self.rng.sample(CORNUCOPIA_ITEMS, grabs)
                t.inventory.extend(items)
                actions_summary.append(f"{t.name} secures {', '.join(items)} before retreating.")
            else:
                actions_summary.append(f"{t.name} flees the Cornucopia empty-handed.")
        for line in actions_summary:
            self._log(line)

        fallen = [t for t in self.tributes if not t.alive]
        if fallen:
            self._log("\nFallen in the Bloodbath:")
            for f in fallen:
                self._log(f" - {f.name}")
                f.__dict__[f"(Fallen logged {f.key})"] = True

    def _simulate_day(self):
        self._log(f"\n--- Day {self.day_count} ---")
        self._run_event_block(DAY_EVENTS, "day")

    def _simulate_night(self):
        self._log(f"\n*** Night {self.day_count} ***")
        self._run_event_block(NIGHT_EVENTS, "night")
        # Nightly survival tick: hunger/stamina and occasional movement
        self._resource_tick()

    def _feast_event(self):
        self._log("\n=== The Feast is announced! ===")
        participants = [t for t in self.alive_tributes() if self.rng.random() < 0.65]
        if len(participants) < 2:
            self._log("No one risks attending the Feast.")
            return
        self.rng.shuffle(participants)
        loot_pool = SUPPLY_ITEMS + list(WEAPONS)
        for i in range(0, len(participants), 2):
            if i + 1 >= len(participants):
                p = participants[i]
                item = self.rng.choice(loot_pool)
                p.inventory.append(item)
                self._log(f"{p.name} sneaks in late and grabs {_a_or_an(item)} uncontested.")
                continue
            a, b = participants[i], participants[i + 1]
            if not (a.alive and b.alive):
                continue
            prob_a = 0.5 + (a.morale - b.morale) * 0.04
            if self.rng.random() < 0.55:
                winner, loser = (a, b) if self.rng.random() < prob_a else (b, a)
                _kill(loser, f"Feast clash vs {winner.name}")
                winner.kills += 1
                loot = self.rng.choice(loot_pool)
                winner.inventory.append(loot)
                self._log(f"{winner.name} defeats {loser.name} at the Feast and seizes {_a_or_an(loot)}.")
            else:
                loot_a = self.rng.choice(loot_pool)
                loot_b = self.rng.choice(loot_pool)
                a.inventory.append(loot_a)
                b.inventory.append(loot_b)
                self._log(f"{a.name} and {b.name} snatch {_a_or_an(loot_a)} and {_a_or_an(loot_b)} then disengage.")

    # --- Event Loop ---
    def _run_event_block(self, event_pool, phase):
        alive = self.alive_tributes()
        if not alive: return
        # Track average morale
        avg_morale = sum(t.morale for t in alive)/len(alive)
        self.history_stats["day_morale_avg"].append(avg_morale)
        events_to_run = min(len(alive), self.rng.randint(3, 6))
        for _ in range(events_to_run):
            alive = self.alive_tributes()
            if len(alive) <= 1: break
            event_func = self._choose_weighted_event(event_pool)
            narrative = event_func(alive, self.rng, self)
            self.history_stats["events_run"] += 1
            for line in narrative:
                if line:
                    self._log(line)
            self._post_event_cleanup()
        self._maybe_global_event()
        fallen = [t for t in self.tributes if not t.alive and f"(Fallen logged {t.key})" not in t.__dict__]
        if fallen:
            self._log("\nFallen this phase:")
            for f in fallen:
                self._log(f" - {f.name}")
                f.__dict__[f"(Fallen logged {f.key})"] = True
                self.death_log.append({"name": f.name, "cause": f.cause_of_death, "day": self.day_count, "phase": phase})
        self.alliances.remove_dead(self.tributes)

    def _choose_weighted_event(self, pool):
        # Base weights + dynamic scaling
        weights = []
        alive_count = len(self.alive_tributes())
        for ev in pool:
            base = BASE_EVENT_WEIGHTS.get(ev, 0.7)
            # More aggressive events when fewer tributes
            if alive_count < 10 and ev in [event_small_skirmish, event_sneak_attack, event_trap_success]:
                base *= 1.3
            # Less comedic late game
            if alive_count < 6 and ev in [event_funny_business, event_dance_off]:
                base *= 0.5
            # Betrayal more likely mid-late
            if ev == event_alliance_betrayal and 6 < alive_count < 20:
                base *= 1.4
            weights.append(base)
        return self.rng.choices(pool, weights=weights, k=1)[0]

    def _maybe_global_event(self):
        # Scale frequency as days progress (capped)
        base = 0.30 + (self.day_count * 0.01)
        if self.rng.random() < min(0.55, base):
            ge = self.rng.choice(GLOBAL_EVENTS)
            lines = ge(self.alive_tributes(), self.rng, self)
            for l in lines:
                self._log(l)

    def _post_event_cleanup(self):
        # Remove duplicate clutter items (optional logic: keep only one of repeated 'moral support note')
        for t in self.tributes:
            if not t.alive: continue
            # Example dedup for moral support note
            filtered = []
            seen_note = False
            for it in t.inventory:
                if it == "moral support note":
                    if seen_note:
                        continue
                    seen_note = True
                filtered.append(it)
            t.inventory = filtered

    # --- Finalization ---
    def _announce_winner(self):
        winners = self.alive_tributes()
        if winners:
            if len(winners) > 1 and self.day_count >= self.max_days:
                self._log("\nARENA FORCED SHUTDOWN: Multiple survivors remain!")
                for w in winners:
                    self._log(f"Survivor: {w.name} (District {w.district}, Kills: {w.kills}, Notoriety:{w.notoriety})")
            elif len(winners) > 1 and self.strict_shutdown and self.day_count >= self.strict_shutdown:
                self._log("\nEARLY SHUTDOWN: Multiple survivors extracted!")
                for w in winners:
                    self._log(f"Extracted: {w.name} (District {w.district}, Kills: {w.kills}, Notoriety:{w.notoriety})")
            else:
                w = winners[0]
                self._log(f"\nVICTOR: {w.name} (District {w.district}, Kills: {w.kills}, Notoriety:{w.notoriety})")
        else:
            self._log("\nNo victor emerged. The arena claims all.")
        self._log("\nFinal standings:")
        for t in sorted(self.tributes, key=lambda x: (-x.alive, -x.kills, -x.notoriety, x.name)):
            self._log(f" - {t}")

    def _output_stats(self):
        self._log("\n=== Statistics Summary ===")
        kills_sorted = sorted(self.tributes, key=lambda t: t.kills, reverse=True)
        top_killers = [t for t in kills_sorted if t.kills > 0][:5]
        if top_killers:
            self._log("Top Killers:")
            for t in top_killers:
                self._log(f"  {t.name}: {t.kills} kills (Notoriety {t.notoriety})")
        avg_morale_series = self.history_stats["day_morale_avg"]
        if avg_morale_series:
            self._log(f"Average Morale Trend: {', '.join(f'{m:.1f}' for m in avg_morale_series)}")
        death_causes = {}
        for d in self.death_log:
            death_causes[d["cause"]] = death_causes.get(d["cause"], 0) + 1
        if death_causes:
            self._log("Death Causes:")
            for cause, count in sorted(death_causes.items(), key=lambda x: -x[1]):
                self._log(f"  {cause}: {count}")
        self._log(f"Total Events Run: {self.history_stats['events_run']}")

        if self.seed is not None:
            self._log(f"Reproducible with seed {self.seed}")
        else:
            self._log("A random seed was used (not provided).")

    # --- Survival mechanics ---
    def _resource_tick(self):
        """Apply nightly hunger/stamina changes, consume supplies, and random movement."""
        alive = self.alive_tributes()
        for t in alive:
            # Natural recovery and decay
            t.adjust_hunger(-0.1)
            t.adjust_stamina(+10)
            # Sleeping bag helps
            if 'sleeping bag' in t.inventory:
                t.adjust_stamina(+10)
            # Consume food/water if low hunger or stamina
            ate = None
            drank = None
            if t.hunger < 60:
                for food in ["protein bar", "berries", "egg"]:
                    if food in t.inventory:
                        t.inventory.remove(food)
                        t.adjust_hunger(+25 if food == 'protein bar' else +18)
                        t.adjust_morale(+1)
                        ate = food
                        break
            if t.stamina < 70:
                for drink in ["energy drink", "water pouch"]:
                    if drink in t.inventory:
                        t.inventory.remove(drink)
                        t.adjust_stamina(+20 if drink == 'energy drink' else +12)
                        t.adjust_hunger(+5 if drink == 'energy drink' else +2)
                        drank = drink
                        break
            # Status updates
            if t.hunger < 30 and 'hungry' not in t.status:
                t.add_status('hungry')
            if t.hunger >= 30 and 'hungry' in t.status:
                t.remove_status('hungry')
            if t.hunger <= 0 and 'starving' not in t.status:
                t.add_status('starving')
            if t.hunger > 0 and 'starving' in t.status:
                t.remove_status('starving')
            # Starvation risk
            if t.hunger <= 0:
                risk = 0.15
                if 'lucky' in t.traits:
                    risk -= 0.04
                if self.rng.random() < risk:
                    _kill(t, 'starvation')
                    self._log(f"{t.name} succumbs to starvation during the long night.")
                    self.death_log.append({"name": t.name, "cause": t.cause_of_death, "day": self.day_count, "phase": "night"})
                    continue
            # Random movement across regions
            if self.rng.random() < 0.30:
                old = t.region
                t.region = self.rng.choice(REGIONS)
                if t.region != old:
                    try:
                        biome = get_region_biome(t.region)
                        self._log(f"{t.name} relocates from {old} to {t.region} ({biome}) under cover of darkness.")
                    except Exception:
                        self._log(f"{t.name} relocates from {old} to {t.region} under cover of darkness.")
            # Log consumption
            if ate or drank:
                parts = []
                if ate:
                    parts.append(f"eats {ate}")
                if drank:
                    parts.append(f"drinks {drank}")
                self._log(f"{t.name} {' and '.join(parts)} and feels a bit better.")

    def _log_intro(self):
        self._log("Welcome to the Hunger Bens Simulation (Enhanced Edition)!")
        self._log(
            f"Total Tributes: {len(self.tributes)}\n"
            "Tributes entering the arena: "
            + ", ".join(f"{t.name} (D{t.district})" for t in self.tributes)
            + "\n"
        )

    def _export_run(self):
        data = {
            "timestamp": datetime.utcnow().isoformat()+"Z",
            "seed": self.seed,
            "max_days": self.max_days,
            "final_day": self.day_count,
            "alliances": self.alliances.to_dict(),
            "tributes": [self._tribute_to_dict(t) for t in self.tributes],
            "death_log": self.death_log,
            "log": self.log,
            "stats": self.history_stats,
        }
        try:
            with open(self.export_log_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._log(f"\nRun exported to {self.export_log_path}")
        except Exception as e:
            self._log(f"Failed to export log: {e}")

    def _tribute_to_dict(self, t: Tribute):
        d = asdict(t)
        return d

# -----------------------------
# Roster / Input Utilities
# -----------------------------
def load_roster_json(path: str) -> Dict[str, Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Accept list or dict
    roster: Dict[str, Dict[str, Any]] = {}
    if isinstance(data, list):
        for idx, entry in enumerate(data, start=1):
            if not isinstance(entry, dict): continue
            key = entry.get("key") or f"cust{idx}"
            roster[key] = {
                "name": entry.get("name", f"Custom {idx}"),
                "gender": entry.get("gender", "unknown"),
                "age": entry.get("age", 18),
                "district": entry.get("district", (idx % 12) + 1)
            }
    elif isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                roster[k] = {
                    "name": v.get("name", k),
                    "gender": v.get("gender", "unknown"),
                    "age": v.get("age", 18),
                    "district": v.get("district", 1)
                }
    return roster

def addnomen(dicty_ref: Dict[str, Dict[str, Any]]):
    print("Add custom tributes (blank key to stop).")
    while True:
        key = input("Enter a unique key for the tribute (e.g., tribX) or blank to finish: ").strip()
        if not key:
            break
        if key in dicty_ref:
            print("Key already exists. Choose a different key.")
            continue
        name = input("Enter the tribute's name: ").strip()
        if not name:
            print("Name cannot be empty."); continue
        gender = input("Enter the tribute's gender: ").strip() or "unspecified"
        age = input("Enter the tribute's age (number): ").strip()
        if not age.isdigit():
            print("Age must be a number."); continue
        district = input("Enter the tribute's district (1-12): ").strip()
        if not district.isdigit() or not (1 <= int(district) <= 12):
            print("District must be a number 1-12."); continue
        dicty_ref[key] = {
            "name": name,
            "gender": gender,
            "age": int(age),
            "district": int(district),
        }
        if input("Add more tributes? (y/n): ").lower() != 'y':
            break

# -----------------------------
# Custom Content Loader (Weapons / Hazards / Events)
# -----------------------------
# Supported JSON schema (any field optional):
# {
#   "weapons": {"laser spoon": "zaps"},             # weapon name -> verb
#   "items": ["force field", "decoy duck"],         # extra supply items
#   "hazards": {"gravity well": "crushed"},        # hazard -> effect keyword
# }
# or separate flags per file.

def load_custom_content(path: str):
    """Load custom content definitions from JSON.
    Returns dict with potential keys: weapons, items, hazards
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Custom content JSON must be an object.")
        return data
    except Exception as e:
        print(f"Failed to load custom content: {e}")
        return {}

def load_custom_content_from_string(s: str) -> Dict[str, Any]:
    """Parse custom content JSON from a raw string without using files.
    Returns an empty dict on failure.
    """
    try:
        data = json.loads(s)
        if not isinstance(data, dict):
            raise ValueError("Custom content JSON must be an object.")
        return data
    except Exception as e:
        print(f"Failed to parse custom content JSON: {e}")
        return {}

def integrate_custom_content(content: Dict[str, Any]):
    """Mutate global registries with user-provided extensions."""
    # Weapons
    new_weapons = content.get('weapons', {})
    if isinstance(new_weapons, dict):
        for w, verb in new_weapons.items():
            if not isinstance(w, str) or not isinstance(verb, str):
                continue
            WEAPON_VERBS[w] = verb
        # Update WEAPONS set (exclude base non-weapons)
        global WEAPONS
        WEAPONS = set(WEAPON_VERBS.keys()) - {"fists", "rock", "stick"}
    # Items
    extra_items = content.get('items', [])
    if isinstance(extra_items, list):
        for it in extra_items:
            if isinstance(it, str) and it not in SUPPLY_ITEMS and it not in CORNUCOPIA_ITEMS:
                SUPPLY_ITEMS.append(it)
    # Hazards
    new_hazards = content.get('hazards', {})
    if isinstance(new_hazards, dict):
        for hz, effect in new_hazards.items():
            if not isinstance(hz, str) or not isinstance(effect, str):
                continue
            if hz not in HAZARDS:
                HAZARDS.append(hz)
            HAZARD_EFFECTS[hz] = effect

# -----------------------------
# Convenience Runner
# -----------------------------
def run_simulation(
    seed: Optional[int] = None,
    max_days: int = 30,
    verbose: bool = True,
    export_log: Optional[str] = None,
    roster: Optional[Dict[str, Dict[str, Any]]] = None,
    strict_shutdown: Optional[int] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    enable_plugins: Optional[bool] = None,
    # Back-compat alias used by older web UI (docs/index.html)
    strict_shutdown_day: Optional[int] = None,
):
    tribute_source = roster if roster else tributedict
    # Prefer explicit strict_shutdown; fall back to alias if provided
    if strict_shutdown is None and strict_shutdown_day is not None:
        strict_shutdown = strict_shutdown_day
    # Windows-only plugin activation (default comes from config unless explicitly overridden)
    try:
        if enable_plugins is None:
            enable = bool(_CONFIG.get('plugins_enabled', _default_plugins_enabled())) and (os.name == 'nt')
        else:
            enable = bool(enable_plugins) and (os.name == 'nt')
        if enable:
            load_windows_plugins(log_callback)
    except Exception:
        # Never fail simulation due to plugins
        messagebox.showerror("Plugin Error", "An error occurred while loading plugins. Continuing without plugins.")
        pass
    sim = HungerBensSimulator(
        tribute_source,
        seed=seed,
        max_days=max_days,
        verbose=verbose,
        export_log=export_log,
        strict_shutdown=strict_shutdown,
        log_callback=log_callback,
    )
    sim.run()
    return sim

# -----------------------------
# Windows-only Tkinter GUI
# -----------------------------
if os.name == 'nt':
    class HungerBensGUI:
        def __init__(self, root):
            self.root = root
            root.title("Hunger Bens Simulator")
            # Initialize state and variables BEFORE building widgets (used by Checkbutton)
            self.current_sim: Optional[HungerBensSimulator] = None
            self.roster_override: Optional[Dict[str, Dict[str, Any]]] = None
            self.plugins_var = tkinter.BooleanVar(value=bool(_CONFIG.get('plugins_enabled', _default_plugins_enabled())))
            # Map/Tracker state
            self.tribute_colors: Dict[str, str] = {}
            self._region_boxes: Dict[str, Tuple[int, int, int, int]] = {}
            self._build_widgets()
            # Persist when toggled
            try:
                self.plugins_var.trace_add('write', lambda *args: self._on_plugins_toggle())
            except Exception:
                pass

        def _build_widgets(self):
            # Root layout: two columns (left main UI, right map panel)
            self.root.columnconfigure(0, weight=1)
            self.root.columnconfigure(1, weight=0)
            self.root.rowconfigure(1, weight=1)

            # Left controls frame
            frm = ttk.Frame(self.root, padding=10)
            frm.grid(row=0, column=0, sticky='nsew')

            # Inputs
            ttk.Label(frm, text="Seed:").grid(row=0, column=0, sticky='w')
            self.seed_entry = ttk.Entry(frm, width=12)
            self.seed_entry.grid(row=0, column=1, sticky='w')

            ttk.Label(frm, text="Max Days:").grid(row=0, column=2, sticky='w')
            self.days_entry = ttk.Entry(frm, width=6)
            self.days_entry.insert(0, '30')
            self.days_entry.grid(row=0, column=3, sticky='w')

            ttk.Label(frm, text="Strict Shutdown Day:").grid(row=1, column=0, sticky='w')
            self.strict_entry = ttk.Entry(frm, width=12)
            self.strict_entry.grid(row=1, column=1, sticky='w')

            self.verbose_var = tkinter.BooleanVar(value=True)
            ttk.Checkbutton(frm, text="Verbose", variable=self.verbose_var).grid(row=1, column=2, columnspan=2, sticky='w')

            ttk.Label(frm, text="Export Log File:").grid(row=2, column=0, sticky='w')
            self.export_entry = ttk.Entry(frm, width=25)
            self.export_entry.grid(row=2, column=1, columnspan=2, sticky='we')
            ttk.Button(frm, text="Browse", command=self._browse_export).grid(row=2, column=3, sticky='w')

            # Roster load
            ttk.Label(frm, text="Custom Roster JSON:").grid(row=3, column=0, sticky='w')
            self.roster_entry = ttk.Entry(frm, width=25)
            self.roster_entry.grid(row=3, column=1, columnspan=2, sticky='we')
            ttk.Button(frm, text="Load", command=self._load_roster).grid(row=3, column=3, sticky='w')

            ttk.Label(frm, text="Content JSON:").grid(row=4, column=0, sticky='w')
            self.content_entry = ttk.Entry(frm, width=25)
            self.content_entry.grid(row=4, column=1, columnspan=2, sticky='we')
            ttk.Button(frm, text="Load", command=self._load_content).grid(row=4, column=3, sticky='w')

            # Inline JSON for content (no external files)
            ttk.Label(frm, text="Inline Content JSON:").grid(row=5, column=0, sticky='w')
            self.inline_content_entry = ttk.Entry(frm, width=25)
            self.inline_content_entry.grid(row=5, column=1, columnspan=2, sticky='we')
            ttk.Button(frm, text="Apply", command=self._apply_inline_content).grid(row=5, column=3, sticky='w')

            # Plugins (Windows only)
            ttk.Checkbutton(frm, text="Enable Plugins (Windows)", variable=self.plugins_var).grid(row=6, column=0, columnspan=2, sticky='w')

            # Run controls
            btn_frame = ttk.Frame(frm)
            btn_frame.grid(row=7, column=0, columnspan=4, pady=(8,4), sticky='we')
            ttk.Button(btn_frame, text="Run Simulation", command=self._run).grid(row=0, column=0, padx=4)
            ttk.Button(btn_frame, text="Clear Output", command=self._clear_output).grid(row=0, column=1, padx=4)
            ttk.Button(btn_frame, text="Content Editor", command=self._open_content_editor).grid(row=0, column=2, padx=4)
            ttk.Button(btn_frame, text="Settings", command=self._open_settings).grid(row=0, column=3, padx=4)
            ttk.Button(btn_frame, text="Quit", command=self.root.quit).grid(row=0, column=4, padx=4)

            # Step controls
            step_row = ttk.Frame(frm)
            step_row.grid(row=8, column=0, columnspan=4, sticky='we', pady=(4,0))
            self.step_mode_var = tkinter.BooleanVar(value=False)
            self.hide_fallen_var = tkinter.BooleanVar(value=True)
            ttk.Checkbutton(step_row, text="Manual step mode (Enter to step)", variable=self.step_mode_var, command=self._on_step_mode_toggle).pack(side='left')
            ttk.Button(step_row, text="Step (Enter)", command=self._step_once).pack(side='left', padx=6)
            ttk.Checkbutton(step_row, text="Hide fallen on map", variable=self.hide_fallen_var, command=self._update_map_from_sim).pack(side='left', padx=8)
            # Next N events controls
            nn = ttk.Frame(frm)
            nn.grid(row=9, column=0, columnspan=4, sticky='we')
            ttk.Label(nn, text="Next N events:").pack(side='left')
            self.step_n_entry = ttk.Entry(nn, width=5)
            self.step_n_entry.insert(0, '5')
            self.step_n_entry.pack(side='left', padx=(4,6))
            ttk.Button(nn, text="Next N", command=self._step_n_click).pack(side='left')

            # Next Day and Until X Left controls
            nd = ttk.Frame(frm)
            nd.grid(row=10, column=0, columnspan=4, sticky='we', pady=(2,0))
            ttk.Button(nd, text="Next Day (to night)", command=self._next_day_click).pack(side='left')
            ttk.Label(nd, text="  Run until X left:").pack(side='left')
            self.until_left_entry = ttk.Entry(nd, width=5)
            self.until_left_entry.insert(0, '4')
            self.until_left_entry.pack(side='left', padx=(4,6))
            ttk.Button(nd, text="Run", command=self._run_until_left_click).pack(side='left')
            ttk.Button(nd, text="Next Night (to day)", command=self._next_night_click).pack(side='left', padx=(12,0))

            # Output area
            self.output = scrolledtext.ScrolledText(self.root, wrap='word', height=30)
            self.output.grid(row=1, column=0, sticky='nsew')
            # Styling tags for simple markdown-like emphasis
            try:
                self.output.tag_configure('header', font=(None, 11, 'bold'))
                self.output.tag_configure('bold', font=(None, 10, 'bold'))
                self.output.tag_configure('italic', font=(None, 10, 'italic'))
            except Exception:
                pass
            # Toggle for styled output
            self.styled_var = tkinter.BooleanVar(value=True)
            style_row = ttk.Frame(self.root)
            style_row.grid(row=2, column=0, sticky='we')
            ttk.Checkbutton(style_row, text="Markdown-style output", variable=self.styled_var).pack(anchor='w', padx=10)

            # Right map/tracker panel
            self._init_map_panel()

        def _init_map_panel(self):
            panel = ttk.Frame(self.root, padding=(6, 10, 10, 10))
            panel.grid(row=0, column=1, rowspan=3, sticky='ns')
            ttk.Label(panel, text="Arena Map", font=(None, 12, 'bold')).pack(anchor='n')
            # Canvas for map
            # Slightly wider canvas so 5x5 labels have more room
            self.map_canvas = tkinter.Canvas(panel, width=420, height=480, background="#111")
            self.map_canvas.pack(anchor='n', pady=(6, 6))
            # Reserve header height inside each region cell for wrapped labels
            self._region_header_h = 32
            # Tooltip label (hidden by default)
            self._tooltip = tkinter.Label(panel, text='', background='#222', foreground='#fff', relief='solid', borderwidth=1, padx=4, pady=2)
            self._tooltip.place_forget()
            # Legend area
            ttk.Label(panel, text="Legend").pack(anchor='w')
            self.legend = scrolledtext.ScrolledText(panel, width=36, height=10)
            try:
                self.legend.configure(state='disabled')
            except Exception:
                pass
            self.legend.pack(fill='x', anchor='w')
            # Pre-draw the static map grid
            self._draw_map_static()
            # Bind mouse motion for tooltip
            try:
                self.map_canvas.bind('<Motion>', self._on_map_motion)
                self.map_canvas.bind('<Leave>', lambda e: self._hide_tooltip())
            except Exception:
                pass

        def _draw_map_static(self):
            c = self.map_canvas
            c.delete('all')
            w = int(c['width'])
            h = int(c['height'])
            # Dynamic grid layout driven by MAP_REGIONS positions (now 5x5)
            max_x = max((info.get('grid', (0,0))[0] for info in MAP_REGIONS.values()), default=0)
            max_y = max((info.get('grid', (0,0))[1] for info in MAP_REGIONS.values()), default=0)
            cols, rows = max_x + 1, max_y + 1
            cell_w = w // cols
            cell_h = h // rows
            # Helper to draw a region rectangle and label w/ biome tint
            def region_box(name: str, rx: int, ry: int):
                info = MAP_REGIONS.get(name, {})
                biome = info.get('biome', 'Plains')
                fill = get_biome_info(name).get('fill', '#222b36')
                x0 = rx * cell_w + 6
                y0 = ry * cell_h + 6
                x1 = (rx + 1) * cell_w - 6
                y1 = (ry + 1) * cell_h - 6
                c.create_rectangle(x0, y0, x1, y1, outline="#555", fill=fill)
                # Wrap the region name inside the cell so it doesn't overflow
                label_width = max(20, (x1 - x0) - 10)
                c.create_text(
                    (x0 + x1)//2,
                    y0 + 6,
                    text=f"{name}",
                    fill="#ddd",
                    font=(None, 8, 'bold'),
                    anchor='n',
                    width=label_width,
                    justify='center'
                )
                self._region_boxes[name] = (x0, y0, x1, y1)
            # Draw all map regions
            self._region_boxes.clear()
            for rname, rinfo in MAP_REGIONS.items():
                gx, gy = rinfo.get('grid', (0,0))
                region_box(rname, gx, gy)
            # Grid lines
            for i in range(1, cols):
                c.create_line(i * cell_w, 0, i * cell_w, h, fill="#333")
            for i in range(1, rows):
                c.create_line(0, i * cell_h, w, i * cell_h, fill="#333")

        def _hash_seed(self, s: str) -> int:
            try:
                return int(hashlib.sha256(s.encode('utf-8')).hexdigest()[:8], 16)
            except Exception:
                return abs(hash(s)) & 0xFFFFFFFF

        def _region_point_for(self, region: str, key: str) -> Tuple[int, int]:
            box = self._region_boxes.get(region)
            if not box:
                # Fallback to center if unknown
                box = self._region_boxes.get('Center', (10, 10, 100, 100))
            x0, y0, x1, y1 = box
            pad = 10
            # Keep markers below the label area (header height)
            header_h = getattr(self, '_region_header_h', 32)
            x0p, y0p, x1p, y1p = x0 + pad, y0 + header_h, x1 - pad, y1 - pad
            rng = random.Random(self._hash_seed(f"{key}|{region}"))
            x = int(rng.uniform(x0p, x1p))
            y = int(rng.uniform(y0p, y1p))
            return x, y

        def _generate_unique_colors(self, keys: List[str]) -> Dict[str, str]:
            # Evenly spaced hues for distinct colors
            n = max(1, len(keys))
            colors: Dict[str, str] = {}
            def hsv_to_hex(h, s, v):
                import colorsys
                r, g, b = colorsys.hsv_to_rgb(h, s, v)
                return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
            for i, k in enumerate(keys):
                h = (i / n) % 1.0
                # Use high saturation/value for visibility
                colors[k] = hsv_to_hex(h, 0.75, 0.95)
            return colors

        def _refresh_legend(self):
            try:
                self.legend.configure(state='normal')
                self.legend.delete('1.0', 'end')
                if not self.current_sim:
                    self.legend.insert('end', 'Run a simulation to populate the legend.')
                    self.legend.configure(state='disabled')
                    return
                for t in self.current_sim.tributes:
                    color = self.tribute_colors.get(t.key, '#aaa')
                    tag = f"c_{t.key}"
                    try:
                        self.legend.tag_configure(tag, foreground=color)
                    except Exception:
                        pass
                    status = '✖' if not t.alive else '●'
                    self.legend.insert('end', f"{status} ")
                    self.legend.insert('end', "■ ", tag)
                    self.legend.insert('end', f"{t.name} (D{t.district})\n")
                self.legend.configure(state='disabled')
            except Exception:
                pass

        def _update_map_from_sim(self):
            # Draw/refresh tribute markers based on current simulator state
            c = self.map_canvas
            if not c:
                return
            # Keep static background, remove only markers
            c.delete('marker')
            sim = self.current_sim
            if not sim:
                return
            radius = 5
            for t in sim.tributes:
                color = self.tribute_colors.get(t.key, '#aaa')
                x, y = self._region_point_for(t.region if t.region in REGIONS else 'Center', t.key)
                if not t.alive:
                    if self.hide_fallen_var.get():
                        continue
                    # Draw an X for fallen tributes in grayscale
                    l1 = c.create_line(x - radius, y - radius, x + radius, y + radius, fill='#777', width=2, tags=('marker', 'm_'+t.key))
                    l2 = c.create_line(x - radius, y + radius, x + radius, y - radius, fill='#777', width=2, tags=('marker', 'm_'+t.key))
                    c.addtag_withtag('m_'+t.key, l1)
                    c.addtag_withtag('m_'+t.key, l2)
                else:
                    ov = c.create_oval(x - radius, y - radius, x + radius, y + radius, fill=color, outline='#000', width=1, tags=('marker', 'm_'+t.key))
                    c.addtag_withtag('m_'+t.key, ov)
            # Optionally refresh legend statuses
            self._refresh_legend()

        def _browse_export(self):
            path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON','*.json')])
            if path:
                self.export_entry.delete(0, 'end')
                self.export_entry.insert(0, path)

        def _load_roster(self):
            path = filedialog.askopenfilename(filetypes=[('JSON','*.json')])
            if not path:
                return
            try:
                data = load_roster_json(path)
                self.roster_override = data
                self.roster_entry.delete(0,'end')
                self.roster_entry.insert(0, path)
                messagebox.showinfo("Roster Loaded", f"Loaded {len(data)} tributes")
            except Exception as e:
                messagebox.showerror("Roster Error", f"Failed to load roster: {e}")

        def _load_content(self):
            path = filedialog.askopenfilename(filetypes=[('JSON','*.json')])
            if not path:
                return
            try:
                cc = load_custom_content(path)
                integrate_custom_content(cc)
                self.content_entry.delete(0,'end')
                self.content_entry.insert(0, path)
                messagebox.showinfo("Content Loaded", "Custom content integrated")
            except Exception as e:
                messagebox.showerror("Content Error", f"Failed to load content: {e}")

        def _apply_inline_content(self):
            raw = self.inline_content_entry.get().strip()
            if not raw:
                messagebox.showwarning("No JSON", "Please paste JSON into the Inline Content JSON field.")
                return
            data = load_custom_content_from_string(raw)
            if not data:
                messagebox.showerror("Invalid JSON", "Failed to parse custom content JSON. Check format.")
                return
            try:
                integrate_custom_content(data)
                messagebox.showinfo("Content Applied", "Inline custom content integrated")
            except Exception as e:
                messagebox.showerror("Content Error", f"Failed to integrate content: {e}")

        def _on_map_motion(self, event):
            if not self.current_sim:
                return
            # Hit test for marker items; we tagged per-tribute as 'm_<key>'
            c = self.map_canvas
            items = c.find_overlapping(event.x-2, event.y-2, event.x+2, event.y+2)
            hovered_key = None
            hovered_region = None
            for it in items:
                tags = c.gettags(it)
                for tg in tags:
                    if tg.startswith('m_'):
                        hovered_key = tg[2:]
                        break
                if hovered_key:
                    break
            # If no tribute marker under cursor, try showing region tooltip
            if not hovered_key:
                # Determine region under cursor
                for name, (x0,y0,x1,y1) in self._region_boxes.items():
                    if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                        hovered_region = name
                        break
                if not hovered_region:
                    self._hide_tooltip(); return
                info = MAP_REGIONS.get(hovered_region, {})
                biome = info.get('biome', 'Unknown')
                feats = info.get('features', [])
                text = f"{hovered_region}\nBiome: {biome}\nFeatures: {', '.join(feats) if feats else 'None'}"
                self._show_tooltip(event.x_root, event.y_root, text)
                return
            # Find tribute and show tooltip
            try:
                t = next((x for x in self.current_sim.tributes if x.key == hovered_key), None)
                if not t:
                    self._hide_tooltip(); return
                biome = get_region_biome(t.region)
                text = f"{t.name} (D{t.district})\nReg: {t.region} | {biome}\nKills: {t.kills} | Morale: {t.morale}"
                self._show_tooltip(event.x_root, event.y_root, text)
            except Exception:
                self._hide_tooltip()

        def _show_tooltip(self, screen_x: int, screen_y: int, text: str):
            try:
                self._tooltip.configure(text=text)
                # Position near cursor; translate to panel-local using place(x,y)
                # Compute relative coords to panel
                panel = self._tooltip.master
                if hasattr(panel, 'winfo_rootx'):
                    rx = screen_x - panel.winfo_rootx() + 12
                    ry = screen_y - panel.winfo_rooty() + 12
                else:
                    rx, ry = 10, 10
                self._tooltip.place(x=rx, y=ry)
            except Exception:
                pass

        def _hide_tooltip(self):
            try:
                self._tooltip.place_forget()
            except Exception:
                pass

        def _append_log(self, line: str):
            # Markdown-like rendering: headers (# ...), section lines (---/***/===), bold (**...**), italics (_..._), list bullets
            try:
                if not self.styled_var.get():
                    self.output.insert('end', line + '\n')
                    self.output.see('end')
                    # Try to refresh the map alongside plain output mode
                    try:
                        self._update_map_from_sim()
                    except Exception:
                        pass
                    return
                text = line
                is_header = False
                if text.startswith(('# ', '## ', '### ', '#### ', '##### ', '###### ')):
                    is_header = True
                if text.startswith(("--- ", "*** ", "=== ", "VICTOR:", "Final standings:", "Fallen", "=== Statistics")):
                    is_header = True
                start_index = self.output.index('end-1c')
                if is_header:
                    self.output.insert('end', text + '\n', 'header')
                else:
                    # Insert raw, then apply inline tags
                    self.output.insert('end', text + '\n')
                    try:
                        # Bold **...**
                        for m in re.finditer(r"\*\*(.+?)\*\*", text):
                            a, b = m.span(1)
                            self.output.tag_add('bold', f"{start_index}+{a}c", f"{start_index}+{b}c")
                        # Italic _..._
                        for m in re.finditer(r"_(.+?)_", text):
                            a, b = m.span(1)
                            self.output.tag_add('italic', f"{start_index}+{a}c", f"{start_index}+{b}c")
                        # List bullets: make the leading ' - ' bold
                        if text.strip().startswith('- '):
                            # bold first token till space after dash
                            leading = text.index('- ')
                            self.output.tag_add('bold', f"{start_index}+{leading}c", f"{start_index}+{leading+2}c")
                    except Exception:
                        pass
                self.output.see('end')
                # Keep map in sync during logging
                try:
                    self._update_map_from_sim()
                except Exception:
                    pass
            except Exception:
                self.output.insert('end', line + '\n')
                self.output.see('end')

        def _clear_output(self):
            self.output.delete('1.0', 'end')

        def _run(self):
            # Parse inputs
            seed_txt = self.seed_entry.get().strip()
            seed = int(seed_txt) if seed_txt.isdigit() else None
            days_txt = self.days_entry.get().strip()
            try:
                max_days = int(days_txt) if days_txt else 30
            except ValueError:
                messagebox.showerror("Input Error", "Max Days must be an integer.")
                return
            strict_txt = self.strict_entry.get().strip()
            strict = int(strict_txt) if strict_txt.isdigit() else None
            export_file = self.export_entry.get().strip() or None
            verbose = self.verbose_var.get()

            self._clear_output()
            self._append_log("Launching simulation...")
            try:
                # Build simulator directly so we can live-update map using self.current_sim
                tribute_source = self.roster_override if self.roster_override else tributedict
                # Optional plugin loading (Windows only)
                try:
                    if self.plugins_var.get():
                        load_windows_plugins(self._append_log)
                except Exception:
                    pass
                sim = HungerBensSimulator(
                    tribute_source,
                    seed=seed,
                    max_days=max_days,
                    verbose=verbose,
                    export_log=export_file,
                    strict_shutdown=strict,
                    log_callback=self._append_log,
                )
                # Assign deterministic unique colors for all tributes
                keys = [t.key for t in sim.tributes]
                self.tribute_colors = self._generate_unique_colors(keys)
                self.current_sim = sim
                # Refresh legend and map before run to show initial positions
                self._draw_map_static()
                self._refresh_legend()
                self._update_map_from_sim()
                if self.step_mode_var.get():
                    sim.start_stepping()
                    # Bind Enter key for stepping
                    try:
                        self.root.bind('<Return>', lambda e: self._step_once())
                    except Exception:
                        pass
                else:
                    # Run simulation (blocking)
                    sim.run()
                    self._append_log("Simulation complete.")
            except Exception as e:
                messagebox.showerror("Run Error", f"Simulation failed: {e}")

        def _on_step_mode_toggle(self):
            # Rebind Enter only when enabled
            try:
                if self.step_mode_var.get():
                    self.root.bind('<Return>', lambda e: self._step_once())
                else:
                    self.root.unbind('<Return>')
            except Exception:
                pass

        def _step_once(self):
            if not self.current_sim:
                return
            finished = self.current_sim.step_once()
            if finished:
                self._append_log("Simulation complete.")
                # Unbind after completion
                try:
                    self.root.unbind('<Return>')
                except Exception:
                    pass
            # Always try to refresh visuals after a step
            try:
                self._update_map_from_sim()
            except Exception:
                pass

        def _ensure_step_mode(self):
            # If the current sim isn't in step mode yet, enable it
            if not self.current_sim:
                return False
            sim = self.current_sim
            try:
                if not getattr(sim, '_step_active', False):
                    sim.start_stepping()
                    self.step_mode_var.set(True)
                    try:
                        self.root.bind('<Return>', lambda e: self._step_once())
                    except Exception:
                        pass
            except Exception:
                return False
            return True

        def _step_n_click(self):
            if not self.current_sim:
                return
            # Parse N
            try:
                n = int(self.step_n_entry.get().strip())
            except Exception:
                n = 5
            n = max(1, min(1000, n))
            self._step_n(n)

        def _step_n(self, n: int):
            if not self._ensure_step_mode():
                return
            sim = self.current_sim
            # Advance until N day/night events occur or finished
            start_events = sim.history_stats.get('events_run', 0)
            target = start_events + n
            finished = False
            # Step loop
            guard = 0
            while sim.history_stats.get('events_run', 0) < target and not finished:
                finished = sim.step_once()
                # Refresh visuals and pump UI
                try:
                    self._update_map_from_sim()
                    self.root.update_idletasks()
                except Exception:
                    pass
                guard += 1
                if guard > n * 5 + 100:
                    # Safety break in case of unforeseen loop conditions
                    break
            if finished:
                self._append_log("Simulation complete.")
                try:
                    self.root.unbind('<Return>')
                except Exception:
                    pass

        def _next_day_click(self):
            self._step_until_next_night()

        def _step_until_next_night(self):
            if not self._ensure_step_mode():
                return
            sim = self.current_sim
            finished = False
            transitions = 0
            guard = 0
            while not finished:
                prev_phase = getattr(sim, '_step_phase', None)
                finished = sim.step_once()
                # Reached the night header when we transition setup_night -> night
                if prev_phase == 'setup_night' and getattr(sim, '_step_phase', None) == 'night':
                    transitions += 1
                    break
                try:
                    self._update_map_from_sim()
                    self.root.update_idletasks()
                except Exception:
                    pass
                guard += 1
                if guard > 2000:
                    break
            # Final refresh and completion handling
            try:
                self._update_map_from_sim()
            except Exception:
                pass
            if finished:
                self._append_log("Simulation complete.")
                try:
                    self.root.unbind('<Return>')
                except Exception:
                    pass

        def _run_until_left_click(self):
            if not self._ensure_step_mode():
                return
            try:
                target_left = int(self.until_left_entry.get().strip())
            except Exception:
                target_left = 4
            target_left = max(1, target_left)
            self._run_until_left(target_left)

        def _run_until_left(self, target_left: int):
            sim = self.current_sim
            if not sim:
                return
            finished = False
            guard = 0
            while not finished:
                # Check condition
                try:
                    alive_count = len(sim.alive_tributes())
                except Exception:
                    alive_count = target_left
                if alive_count <= target_left:
                    break
                finished = sim.step_once()
                try:
                    self._update_map_from_sim()
                    self.root.update_idletasks()
                except Exception:
                    pass
                guard += 1
                if guard > 10000:
                    break
            # Final UI updates
            try:
                self._update_map_from_sim()
            except Exception:
                pass
            if finished:
                self._append_log("Simulation complete.")
                try:
                    self.root.unbind('<Return>')
                except Exception:
                    pass

        def _next_night_click(self):
            self._step_until_night_complete()

        def _step_until_night_complete(self):
            if not self._ensure_step_mode():
                return
            sim = self.current_sim
            finished = False
            guard = 0
            # If we're not yet in the night block for the current day, advance to it first
            while getattr(sim, '_step_phase', None) not in ('night', 'setup_night', 'finalize', 'done') and not finished:
                finished = sim.step_once()
                try:
                    self._update_map_from_sim(); self.root.update_idletasks()
                except Exception:
                    pass
                guard += 1
                if guard > 2000:
                    break
            if finished:
                self._append_log("Simulation complete.")
                try:
                    self.root.unbind('<Return>')
                except Exception:
                    pass
                return
            # Now consume the night block fully, including the nightly resource tick
            guard2 = 0
            while not finished:
                prev_phase = getattr(sim, '_step_phase', None)
                finished = sim.step_once()
                # Stop once we've transitioned past night to setup_day
                if prev_phase == 'night' and getattr(sim, '_step_phase', None) == 'setup_day':
                    break
                try:
                    self._update_map_from_sim(); self.root.update_idletasks()
                except Exception:
                    pass
                guard2 += 1
                if guard2 > 5000:
                    break
            try:
                self._update_map_from_sim()
            except Exception:
                pass
            if finished:
                self._append_log("Simulation complete.")
                try:
                    self.root.unbind('<Return>')
                except Exception:
                    pass

        def _on_plugins_toggle(self):
            val = bool(self.plugins_var.get())
            try:
                _CONFIG['plugins_enabled'] = val
                save_config(_CONFIG)
            except Exception:
                pass

        def _open_content_editor(self):
            # Minimal modal JSON editor to add weapons/items/hazards
            win = tkinter.Toplevel(self.root)
            win.title("Content Editor")
            win.geometry("560x420")
            ttk.Label(win, text="Paste custom content JSON (weapons/items/hazards)").pack(anchor='w', padx=10, pady=(10,4))
            txt = scrolledtext.ScrolledText(win, wrap='word', height=18)
            txt.pack(fill='both', expand=True, padx=10)
            # Prefill with a helpful template
            template = {
                "weapons": {"laser spoon": "zaps"},
                "items": ["force field"],
                "hazards": {"gravity well": "crushed"}
            }
            try:
                txt.insert('1.0', json.dumps(template, indent=2))
            except Exception:
                pass
            btns = ttk.Frame(win)
            btns.pack(fill='x', pady=8)
            def apply_and_close():
                raw = txt.get('1.0', 'end').strip()
                try:
                    data = load_custom_content_from_string(raw)
                    if not data:
                        messagebox.showerror("Invalid JSON", "Could not parse JSON or wrong shape.")
                        return
                    integrate_custom_content(data)
                    messagebox.showinfo("Applied", "Custom content integrated.")
                    win.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to apply content: {e}")
            ttk.Button(btns, text="Apply", command=apply_and_close).pack(side='right', padx=10)
            ttk.Button(btns, text="Close", command=win.destroy).pack(side='right')

        def _compute_plugin_paths(self):
            here = os.path.dirname(os.path.abspath(__file__))
            repo_plugins = os.path.join(here, 'plugins')
            lap = os.environ.get('LOCALAPPDATA')
            rap = os.environ.get('APPDATA')
            prog = os.environ.get('PROGRAMDATA')
            paths = []
            if lap:
                paths.append(("LocalAppData", os.path.join(lap, 'HungerBens', 'plugins')))
            if rap:
                paths.append(("AppData (Roaming)", os.path.join(rap, 'HungerBens', 'plugins')))
            if prog:
                paths.append(("ProgramData (All Users)", os.path.join(prog, 'HungerBens', 'plugins')))
            paths.append(("Repo (docs/plugins)", repo_plugins))
            return paths

        def _open_folder(self, path: str):
            try:
                os.makedirs(path, exist_ok=True)
                os.startfile(path)  # type: ignore[attr-defined]
            except Exception as e:
                messagebox.showerror("Open Folder", f"Failed to open/create folder:\n{path}\n\n{e}")

        def _open_settings(self):
            win = tkinter.Toplevel(self.root)
            win.title("Settings")
            win.geometry("560x360")
            c = ttk.Frame(win, padding=10)
            c.pack(fill='both', expand=True)

            # Section: Plugins
            ttk.Label(c, text="Plugins", font=(None, 12, 'bold')).pack(anchor='w')
            desc = "Manage plugin folders and enable/disable individual plugins."
            ttk.Label(c, text=desc).pack(anchor='w', pady=(0,8))

            paths = self._compute_plugin_paths()
            # Scrollable area if many rows
            canvas = tkinter.Canvas(c, highlightthickness=0)
            scroll_y = ttk.Scrollbar(c, orient='vertical', command=canvas.yview)
            row_frame = ttk.Frame(canvas)
            row_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            canvas.create_window((0,0), window=row_frame, anchor='nw')
            canvas.configure(yscrollcommand=scroll_y.set, height=180)
            canvas.pack(side='left', fill='both', expand=True)
            scroll_y.pack(side='right', fill='y')

            for i, (label, p) in enumerate(paths):
                row = ttk.Frame(row_frame)
                row.grid(row=i, column=0, sticky='we', pady=3)
                row.columnconfigure(1, weight=1)
                exists = os.path.isdir(p)
                text = f"{label}: {p}"
                ttk.Label(row, text=text, wraplength=420, justify='left').grid(row=0, column=0, sticky='w')
                state = "Exists" if exists else "(will be created)"
                ttk.Label(row, text=state, foreground=("#8f8" if exists else "#ff8")).grid(row=0, column=1, padx=8, sticky='e')
                ttk.Button(row, text="Open", command=lambda path=p: self._open_folder(path)).grid(row=0, column=2, padx=6)

            # Other settings placeholders (future)
            ttk.Separator(c).pack(fill='x', pady=10)
            # Plugin enable/disable list
            ttk.Label(c, text="Installed Plugins", font=(None, 12, 'bold')).pack(anchor='w')
            list_frame = ttk.Frame(c)
            list_frame.pack(fill='both', expand=True)
            inner = ttk.Frame(list_frame)
            inner.pack(fill='both', expand=True)

            def refresh_plugins():
                for w in inner.winfo_children():
                    w.destroy()
                plugins = scan_plugin_files()
                cfg_pl = _CONFIG.get('plugins', {}) if isinstance(_CONFIG.get('plugins'), dict) else {}
                rowi = 0
                for pid, path in plugins:
                    entry = cfg_pl.get(pid, {"enabled": True, "path": path})
                    var = tkinter.BooleanVar(value=bool(entry.get('enabled', True)))
                    def make_cb(p_id: str, v: tkinter.BooleanVar):
                        def _cb(*_):
                            cfg = _CONFIG.get('plugins')
                            if not isinstance(cfg, dict):
                                _CONFIG['plugins'] = {}
                                cfg = _CONFIG['plugins']
                            ent = cfg.get(p_id)
                            if not isinstance(ent, dict):
                                ent = {}
                                cfg[p_id] = ent
                            ent['enabled'] = bool(v.get())
                            ent['path'] = path
                            save_config(_CONFIG)
                        return _cb
                    var.trace_add('write', make_cb(pid, var))
                    row = ttk.Frame(inner)
                    row.grid(row=rowi, column=0, sticky='we', pady=2)
                    row.columnconfigure(1, weight=1)
                    ttk.Checkbutton(row, text=pid, variable=var).grid(row=0, column=0, sticky='w')
                    ttk.Label(row, text=path, wraplength=360).grid(row=0, column=1, sticky='w', padx=6)
                    rowi += 1

            btns = ttk.Frame(c)
            btns.pack(fill='x', pady=(6,0))
            ttk.Button(btns, text="Refresh", command=refresh_plugins).pack(side='left')
            ttk.Button(btns, text="Close", command=win.destroy).pack(side='right')

            # Initial population
            refresh_plugins()


def askagain(roster):
    import sys
    try:
        has_tty = bool(sys.stdin and sys.stdin.isatty())
    except Exception:
        has_tty = False
    if not has_tty:
        # No interactive console available; do not prompt again.
        print("Thank you for using the Hunger Bens Simulator!")
        return
    while True:
        again = input("Run another simulation? (y/n): ").lower()
        if again == 'y':
            mainloop(roster_override=roster)
        elif again == 'n':
            break
        else:
            print("Please enter 'y' or 'n'.")
    print("Thank you for using the Hunger Bens Simulator!")

def mainloop(roster_override=None, clear_screen: bool = True):
    import sys
    # If started without a console (e.g., windowed EXE), avoid interactive prompts
    try:
        has_tty = bool(sys.stdin and sys.stdin.isatty())
    except Exception:
        has_tty = False
    if not has_tty:
        if os.name == 'nt':
            try:
                import tkinter
                root = tkinter.Tk()
                gui = HungerBensGUI(root)
                try:
                    sv_ttk.set_theme("dark")
                except Exception:
                    pass
                root.mainloop()
                return
            except Exception:
                os.environ["HUNGER_BENS_NO_INTERACTIVE"] = "1"
                return cli_entry()
        else:
            os.environ["HUNGER_BENS_NO_INTERACTIVE"] = "1"
            return cli_entry()
    seedin = input("Enter a seed (or leave blank for random): ").strip()
    seedin = int(seedin) if seedin.isdigit() else None
    maxday = input("Enter max days (default 30): ").strip()
    maxday = int(maxday) if maxday.isdigit() else 30
    strict = input("Enter strict shutdown day (optional, blank=none): ").strip()
    strict = int(strict) if strict.isdigit() else None
    verb = input("Verbose output? (y/n, default y): ").lower() != 'n'
    working_dicty = dict(tributedict) if roster_override is None else dict(roster_override)
    if input("Add custom tributes? (y/n): ").lower() == 'y':
        addnomen(working_dicty)
    # Inline custom content JSON (no file required)
    if input("Add custom content via JSON? (y/n): ").lower() == 'y':
        print("Paste a JSON object with optional keys: 'weapons', 'items', 'hazards'. One line recommended.")
        raw = input("Content JSON (blank to skip): ").strip()
        if raw:
            cc = load_custom_content_from_string(raw)
            if cc:
                integrate_custom_content(cc)
                print("Custom content integrated.")
            else:
                print("Invalid JSON; skipping custom content.")
    export_q = input("Export run to JSON? (filename or blank): ").strip()
    export_file = export_q if export_q else None
    if clear_screen:
        # Clear screen so the simulation output starts at top of terminal for readability
        try:
            if os.name == 'nt':
                os.system('cls')
            else:
                os.system('clear')
        except Exception:
            pass
    run_simulation(seed=seedin, max_days=maxday, verbose=verb, export_log=export_file, roster=working_dicty, strict_shutdown=strict)
    print("\nSimulation complete.")
    print("You can rerun with the same seed for identical results.")
    print(seedin if seedin is not None else "Random seed used.")
    askagain(working_dicty)

# -----------------------------
# CLI Argument Parsing
# -----------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Hunger Bens Simulator (Enhanced)")
    parser.add_argument("--seed", type=int, help="Random seed (int)")
    parser.add_argument("--max-days", type=int, default=30, help="Maximum days to simulate")
    parser.add_argument("--quiet", action="store_true", help="Suppress live output (still logs internally)")
    parser.add_argument("--export-log", type=str, help="Export full run JSON to file")
    parser.add_argument("--roster", type=str, help="Path to JSON roster file")
    parser.add_argument("--content", type=str, help="Path to JSON custom content file (weapons/hazards/events)")
    parser.add_argument("--content-json", type=str, help="Inline JSON string for custom content (no file)")
    parser.add_argument("--strict-shutdown", type=int, help="Force terminate after given day if multiple alive")
    parser.add_argument("--interactive", action="store_true", help="Use interactive loop instead of single run")
    parser.add_argument("--no-clear", action="store_true", help="Disable clearing the screen before interactive simulation output")
    if os.name == 'nt':
        parser.add_argument("--gui", action="store_true", help="Launch Tkinter GUI (Windows only)")
        parser.add_argument("--no-plugins", action="store_true", help="Disable Windows plugin loader")
        parser.add_argument("--plugin-dir", type=str, help="Directory for Windows plugins (overrides default)")
        parser.add_argument("--plugins", action="store_true", help="Enable Windows plugin loader (overrides config)")
    return parser.parse_args()

def cli_entry():
    args = parse_args()
    roster_data = None
    if args.roster:
        if not os.path.isfile(args.roster):
            print(f"Roster file not found: {args.roster}")
            return
        try:
            roster_data = load_roster_json(args.roster)
            print(f"Loaded {len(roster_data)} custom tributes from {args.roster}")
        except Exception as e:
            print(f"Failed to load roster: {e}")
            return
    if args.content:
        if not os.path.isfile(args.content):
            print(f"Custom content file not found: {args.content}")
        else:
            cc = load_custom_content(args.content)
            integrate_custom_content(cc)
            print(f"Custom content integrated from {args.content}")
    if getattr(args, 'content_json', None):
        cc2 = load_custom_content_from_string(args.content_json)
        if cc2:
            integrate_custom_content(cc2)
            print("Inline custom content integrated from --content-json")
        else:
            print("Failed to parse --content-json; ignoring.")
    # GUI mode
    if os.name == 'nt' and getattr(args, 'gui', False):
        import tkinter
        root = tkinter.Tk()
        gui = HungerBensGUI(root)
        try:
            sv_ttk.set_theme("dark")
        except Exception:
            pass
        root.mainloop()
        return
    if args.interactive:
        mainloop(roster_override=roster_data, clear_screen=not args.no_clear)
    else:
        # Configure plugin dirs if provided (Windows only)
        if os.name == 'nt':
            if getattr(args, 'plugin_dir', None):
                os.environ['HUNGER_BENS_PLUGIN_DIRS'] = args.plugin_dir
        # Determine plugin enablement: CLI overrides config; default uses config
        enable_plugins = None
        if os.name == 'nt':
            if getattr(args, 'no_plugins', False):
                enable_plugins = False
            elif getattr(args, 'plugins', False):
                enable_plugins = True
        run_simulation(
            seed=args.seed,
            max_days=args.max_days,
            verbose=not args.quiet,
            export_log=args.export_log,
            roster=roster_data,
            strict_shutdown=args.strict_shutdown,
            enable_plugins=enable_plugins,
        )

if __name__ == "__main__":
    import sys
    # Web/Pyodide path explicitly disables interactive
    if os.environ.get("HUNGER_BENS_NO_INTERACTIVE") == "1":
        cli_entry()
    else:
        # If packaged (PyInstaller) or without a console TTY, prefer GUI on Windows
        is_frozen = bool(getattr(sys, 'frozen', False))
        try:
            has_tty = bool(sys.stdin and sys.stdin.isatty())
        except Exception:
            has_tty = False
        prefer_gui = (os.name == 'nt') and (is_frozen or not has_tty)

        if len(sys.argv) > 1 and not prefer_gui:
            # Respect CLI args when present and console available
            cli_entry()
        elif os.name == 'nt':
            # Launch Windows GUI by default for packaged/no-tty scenarios
            try:
                import tkinter
                root = tkinter.Tk()
                gui = HungerBensGUI(root)
                try:
                    sv_ttk.set_theme("dark")
                except Exception:
                    pass
                    messagebox.showerror("Theme Error", "Failed to set Sunset Valley theme; using default.")
                root.mainloop()
            except Exception:
                # If GUI fails, fall back to CLI without interactive prompts
                os.environ["HUNGER_BENS_NO_INTERACTIVE"] = "1"
                cli_entry()
        else:
            # Non-Windows: use CLI; interactive only when TTY is present
            if len(sys.argv) > 1 or not has_tty:
                cli_entry()
            else:
                mainloop(clear_screen=True)