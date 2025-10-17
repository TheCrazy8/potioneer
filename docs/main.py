import tkinter as tk
import tkinter.ttk as ttk
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Union
import ast
import os
import sys
import json

try:
	from PIL import Image, ImageTk  # type: ignore
	USE_PIL = True
except Exception:
	USE_PIL = False


# -----------------------------
# Data model and helpers
# -----------------------------

def requires(*args, **kwargs) -> Dict[str, int]:
	"""
	Flexible recipe requirement parser that supports:
	- kwargs: requires(mushroom=3, onion=1)
	- dict: requires({"mushroom": 3, "onion": 1})
	- list/tuple of pairs: requires([("mushroom", 3), ("onion", 1)])
	- string specs (for convenience):
		requires('"mushroom":3, "onion":1')
		requires('mushroom:3, onion:1')
		requires('{"mushroom": 3, "onion": 1}')
	Returns a normalized dict[str, int].
	"""
	result: Dict[str, int] = {}

	def add_pair(k: str, v: Union[str, int]):
		if k is None:
			return
		key = str(k).strip().strip('\'"')
		try:
			val = int(v)
		except Exception:
			try:
				# handle like '3x' or '3 '
				val = int(str(v).strip().rstrip('xX'))
			except Exception:
				raise ValueError(f"Invalid quantity for '{key}': {v}")
		if val < 0:
			raise ValueError(f"Quantity must be >= 0 for '{key}'")
		result[key] = result.get(key, 0) + val

	# kwargs first
	for k, v in kwargs.items():
		add_pair(k, v)

	for arg in args:
		if isinstance(arg, dict):
			for k, v in arg.items():
				add_pair(k, v)
		elif isinstance(arg, (list, tuple)):
			# list/tuple of pairs
			for item in arg:
				if isinstance(item, (list, tuple)) and len(item) == 2:
					add_pair(item[0], item[1])
				else:
					raise ValueError("List/tuple must contain (name, qty) pairs")
		elif isinstance(arg, str):
			s = arg.strip()
			if not s:
				continue
			# Try literal eval directly if it looks like a dict
			parsed = None
			if s.startswith("{") and s.endswith("}"):
				try:
					parsed = ast.literal_eval(s)
				except Exception:
					parsed = None
			if parsed is None:
				# Accept formats like '"mushroom":3, "onion":1' or 'mushroom:3, onion:1'
				try:
					# Ensure braces for literal_eval
					to_eval = s
					if not (s.startswith("{") and s.endswith("}")):
						to_eval = "{" + s + "}"
					# Replace name:qty without quotes into '"name": qty'
					# A simple heuristic: ensure keys are quoted
					# We'll split by commas at top level and parse pairs
					temp_dict: Dict[str, int] = {}
					for pair in to_eval.strip('{}').split(','):
						if not pair.strip():
							continue
						if ':' not in pair:
							raise ValueError(f"Invalid requirement pair: '{pair}'")
						k_raw, v_raw = pair.split(':', 1)
						add_pair(k_raw.strip().strip('\'"'), v_raw.strip())
					parsed = result  # already added
				except Exception as e:
					raise ValueError(f"Could not parse requirement string: {s}\n{e}")
		else:
			raise TypeError(f"Unsupported requires() arg type: {type(arg)}")

	# Normalize zero-entries out
	return {k: int(v) for k, v in result.items() if int(v) > 0}


@dataclass
class Ingredient:
	name: str
	image: Optional[Path] = None


@dataclass
class Potion:
	name: str
	requirements: Dict[str, int]
	image: Optional[Path] = None


class GameState:
	def __init__(self):
		self.ingredients: Dict[str, Ingredient] = {}
		self.potions: List[Potion] = []
		self.inventory: Dict[str, int] = {}
		self.brewed: Dict[str, int] = {}
		self.pot: Dict[str, int] = {}

	def add_ingredient(self, name: str, image_path: Optional[Path] = None, starting_qty: int = 0):
		key = name.strip()
		self.ingredients[key] = Ingredient(name=key, image=image_path)
		if starting_qty > 0:
			self.inventory[key] = self.inventory.get(key, 0) + starting_qty

	def add_potion(self, name: str, reqs: Dict[str, int], image_path: Optional[Path] = None):
		self.potions.append(Potion(name=name.strip(), requirements=reqs, image=image_path))

	def can_brew_from_pot(self, potion: Potion) -> Tuple[bool, Dict[str, int]]:
		missing: Dict[str, int] = {}
		# Must match required counts exactly; extras block brewing
		for ing, qty in potion.requirements.items():
			have = self.pot.get(ing, 0)
			if have < qty:
				missing[ing] = qty - have
		# Also ensure no extra items in pot
		extras = {}
		for ing, qty in self.pot.items():
			if ing not in potion.requirements:
				extras[ing] = qty
			elif qty > potion.requirements[ing]:
				extras[ing] = qty - potion.requirements[ing]
		can = (not missing) and (not extras)
		if not can and extras:
			# encode extras as negative missing to surface in UI
			for k, v in extras.items():
				missing[f"extra:{k}"] = v
		return can, missing

	def brew(self, potion: Potion) -> bool:
		can, missing = self.can_brew_from_pot(potion)
		if not can:
			return False
		# Consume from pot (pot already holds the reqs), clear pot after brewing
		self.pot.clear()
		self.brewed[potion.name] = self.brewed.get(potion.name, 0) + 1
		return True

	def add_to_pot(self, ing: str) -> bool:
		if self.inventory.get(ing, 0) <= 0:
			return False
		self.inventory[ing] -= 1
		self.pot[ing] = self.pot.get(ing, 0) + 1
		if self.inventory[ing] <= 0:
			del self.inventory[ing]
		return True

	def remove_from_pot(self, ing: str) -> bool:
		if self.pot.get(ing, 0) <= 0:
			return False
		self.pot[ing] -= 1
		if self.pot[ing] <= 0:
			del self.pot[ing]
		self.inventory[ing] = self.inventory.get(ing, 0) + 1
		return True

	def clear_pot(self):
		# Return all to inventory
		for ing, qty in list(self.pot.items()):
			self.inventory[ing] = self.inventory.get(ing, 0) + qty
		self.pot.clear()


# -----------------------------
# Tkinter UI
# -----------------------------

class ImageCache:
	def __init__(self):
		# key: (Path, size) for PIL; or Path for tk.PhotoImage fallback
		self._cache: Dict[Tuple[Path, Tuple[int, int]], tk.PhotoImage] = {}

	def load(self, path: Optional[Path], size: Tuple[int, int] = (64, 64)) -> Optional[tk.PhotoImage]:
		if not path:
			return None
		try:
			p = path.resolve()
			cache_key = (p, size)
			if cache_key in self._cache:
				return self._cache[cache_key]

			if USE_PIL:
				with Image.open(p) as im:
					im = im.convert("RGBA")
					im.thumbnail(size, Image.LANCZOS)
					photo = ImageTk.PhotoImage(im)
			else:
				# Fallback to tk.PhotoImage (supports gif/pgm/ppm and png on most Tk builds)
				photo = tk.PhotoImage(file=str(p))
				w = photo.width(); h = photo.height()
				target_w, target_h = size
				fx = max(1, w // max(1, target_w))
				fy = max(1, h // max(1, target_h))
				if fx > 1 or fy > 1:
					photo = photo.subsample(max(1, fx), max(1, fy))
			self._cache[cache_key] = photo
			return photo
		except Exception:
			return None


class PotionGameUI(tk.Tk):
	def __init__(self, state: GameState, assets_dirs: Dict[str, Path], save_path: Path, on_save):
		super().__init__()
		self.state = state
		# assets_dirs: {'user': Path, 'bundled': Path|None, 'dev': Path}
		self.assets_dirs = assets_dirs
		self.save_path = save_path
		self._on_save = on_save
		self.title("Potioneer - Cozy Forest Cauldron")
		self.geometry("1060x720")
		self.minsize(960, 640)
		self.configure(bg="#1f2d24")  # deep forest green

		# Tk styles
		style = ttk.Style(self)
		try:
			style.theme_use("clam")
		except Exception:
			pass
		style.configure("TFrame", background="#1f2d24")
		style.configure("Card.TFrame", background="#26352b", relief="groove", borderwidth=1)
		style.configure("Header.TLabel", background="#1f2d24", foreground="#e7f5e9", font=("Georgia", 16, "bold"))
		style.configure("Body.TLabel", background="#26352b", foreground="#d3ead7", font=("Georgia", 11))
		style.configure("Small.TLabel", background="#26352b", foreground="#b6d1bf", font=("Georgia", 10))
		style.configure("Wood.TButton", background="#6b4f3b", foreground="#f5eddc", font=("Georgia", 11, "bold"))
		style.map("Wood.TButton", background=[("active", "#7c5a44")])

		self.image_cache = ImageCache()

		# Layout frames
		self.columnconfigure(0, weight=1)
		self.columnconfigure(1, weight=2)
		self.columnconfigure(2, weight=1)
		self.rowconfigure(0, weight=1)

		self.left = ttk.Frame(self)
		self.center = ttk.Frame(self)
		self.right = ttk.Frame(self)
		self.left.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
		self.center.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
		self.right.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)

		self._build_left()
		self._build_center()
		self._build_right()
		self._refresh_all()
		self.protocol("WM_DELETE_WINDOW", self._on_close)

	# ---------- Left: Inventory ----------
	def _build_left(self):
		header = ttk.Label(self.left, text="Satchel of Ingredients", style="Header.TLabel")
		header.pack(anchor="w", pady=(0, 8))

		self.inv_container = ttk.Frame(self.left, style="Card.TFrame")
		self.inv_container.pack(fill="both", expand=True)

		self.inv_grid = ttk.Frame(self.inv_container, style="Card.TFrame")
		self.inv_grid.pack(fill="both", expand=True, padx=8, pady=8)

		hint = ttk.Label(
			self.left,
			text="Tip: Left-click adds to pot. Right-click removes from pot (if present).",
			style="Small.TLabel",
		)
		hint.pack(anchor="w", pady=(6, 0))

	def _render_inventory(self):
		for child in self.inv_grid.winfo_children():
			child.destroy()
		items = sorted(self.state.inventory.items())
		cols = 3
		for idx, (name, qty) in enumerate(items):
			r, c = divmod(idx, cols)
			img = self._load_ing_image(name)
			frame = ttk.Frame(self.inv_grid, style="Card.TFrame")
			frame.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")

			btn = tk.Button(
				frame,
				image=img if img else None,
				text=name if not img else "",
				compound="top",
				bg="#3a4a41",
				fg="#f5eddc",
				activebackground="#46574d",
				relief="flat",
				padx=6, pady=6,
				command=lambda n=name: self._on_add_to_pot(n),
			)
			btn.bind("<Button-3>", lambda e, n=name: self._on_remove_from_pot(n))
			btn.pack(fill="both", expand=True)
			lbl = ttk.Label(frame, text=f"{name} x{qty}", style="Small.TLabel")
			lbl.pack(anchor="center", pady=(4, 4))

	# ---------- Center: Cauldron ----------
	def _build_center(self):
		header = ttk.Label(self.center, text="Cauldron", style="Header.TLabel")
		header.pack(anchor="w", pady=(0, 8))

		self.cauldron_card = ttk.Frame(self.center, style="Card.TFrame")
		self.cauldron_card.pack(fill="both", expand=True)

		top_bar = ttk.Frame(self.cauldron_card, style="Card.TFrame")
		top_bar.pack(fill="x", padx=8, pady=(8, 0))
		clear_btn = ttk.Button(top_bar, text="Return All", style="Wood.TButton", command=self._on_clear_pot)
		clear_btn.pack(side="right")
		save_btn = ttk.Button(top_bar, text="Save Now", style="Wood.TButton", command=self._on_save_click)
		save_btn.pack(side="right", padx=(0, 6))

		self.cauldron_canvas = tk.Canvas(self.cauldron_card, height=220, bg="#26352b", highlightthickness=0)
		self.cauldron_canvas.pack(fill="x", padx=8, pady=8)
		self._draw_cauldron()

		self.pot_list = ttk.Frame(self.cauldron_card, style="Card.TFrame")
		self.pot_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))

	def _draw_cauldron(self):
		c = self.cauldron_canvas
		c.delete("all")
		w = c.winfo_reqwidth()
		h = c.winfo_height()
		if w <= 1:
			w = 800
		if h <= 1:
			h = 220
		# Simple cozy cauldron drawing
		c.create_oval(80, 60, w - 80, h - 10, fill="#1a2320", outline="#0e1612", width=3)
		c.create_oval(110, 40, w - 110, h - 120, fill="#2d3f35", outline="#16231d", width=2)
		c.create_text(w // 2, 30, text="Dragonsbreath Co.", fill="#b6d1bf", font=("Georgia", 12, "italic"))

	def _render_pot_contents(self):
		for child in self.pot_list.winfo_children():
			child.destroy()
		if not self.state.pot:
			lbl = ttk.Label(self.pot_list, text="The cauldron awaits...", style="Body.TLabel")
			lbl.pack(anchor="center", pady=12)
			return
		for name, qty in sorted(self.state.pot.items()):
			row = ttk.Frame(self.pot_list, style="Card.TFrame")
			row.pack(fill="x", padx=4, pady=2)
			img = self._load_ing_image(name, (32, 32))
			icon = ttk.Label(row, image=img if img else None, text=name if not img else "", style="Small.TLabel")
			if img:
				icon.image = img  # keep ref
			icon.pack(side="left")
			ttk.Label(row, text=f"x{qty}", style="Small.TLabel").pack(side="left", padx=8)
			tk.Button(
				row,
				text="-",
				bg="#6b4f3b", fg="#f5eddc",
				activebackground="#7c5a44",
				width=3,
				command=lambda n=name: self._on_remove_from_pot(n),
			).pack(side="right")

	# ---------- Right: Recipes & Brew ----------
	def _build_right(self):
		header = ttk.Label(self.right, text="Recipes", style="Header.TLabel")
		header.pack(anchor="w", pady=(0, 8))

		self.recipes_container = ttk.Frame(self.right, style="Card.TFrame")
		self.recipes_container.pack(fill="both", expand=True)

		self.recipes_scroll = tk.Canvas(self.recipes_container, bg="#26352b", highlightthickness=0)
		self.scrollbar = ttk.Scrollbar(self.recipes_container, orient="vertical", command=self.recipes_scroll.yview)
		self.recipes_frame = ttk.Frame(self.recipes_scroll, style="Card.TFrame")
		self.recipes_frame.bind(
			"<Configure>",
			lambda e: self.recipes_scroll.configure(scrollregion=self.recipes_scroll.bbox("all")),
		)
		self.recipes_scroll.create_window((0, 0), window=self.recipes_frame, anchor="nw")
		self.recipes_scroll.configure(yscrollcommand=self.scrollbar.set)
		self.recipes_scroll.pack(side="left", fill="both", expand=True)
		self.scrollbar.pack(side="right", fill="y")

		brewed_header = ttk.Label(self.right, text="Brewed Potions", style="Header.TLabel")
		brewed_header.pack(anchor="w", pady=(10, 8))

		self.brewed_container = ttk.Frame(self.right, style="Card.TFrame")
		self.brewed_container.pack(fill="both", expand=False)

	def _render_recipes(self):
		for child in self.recipes_frame.winfo_children():
			child.destroy()
		for potion in self.state.potions:
			card = ttk.Frame(self.recipes_frame, style="Card.TFrame")
			card.pack(fill="x", padx=8, pady=6)

			top = ttk.Frame(card, style="Card.TFrame")
			top.pack(fill="x", padx=8, pady=(8, 4))
			img = self._load_potion_image(potion.name)
			icon = ttk.Label(top, image=img if img else None, text=potion.name if not img else "", style="Body.TLabel")
			if img:
				icon.image = img
			icon.pack(side="left")

			req_text = ", ".join([f"{k}:{v}" for k, v in potion.requirements.items()])
			req_lbl = ttk.Label(card, text=f"Needs: {req_text}", style="Small.TLabel")
			req_lbl.pack(anchor="w", padx=12)

			can, missing = self.state.can_brew_from_pot(potion)
			status_text = "Ready to brew" if can else self._missing_text(missing)
			status_color = "#b6f5c6" if can else "#f5d3b6"
			status = ttk.Label(card, text=status_text, style="Small.TLabel")
			status.configure(foreground=status_color)
			status.pack(anchor="w", padx=12, pady=(2, 6))

			actions = ttk.Frame(card, style="Card.TFrame")
			actions.pack(fill="x", padx=8, pady=(0, 8))
			brew_btn = ttk.Button(actions, text="Brew", style="Wood.TButton", command=lambda p=potion: self._on_brew(p))
			if not can:
				brew_btn.state(["disabled"])
			brew_btn.pack(side="right")
		# Reset progress button under recipe list
		reset_bar = ttk.Frame(self.recipes_frame, style="Card.TFrame")
		reset_bar.pack(fill="x", padx=8, pady=(8, 8))
		ttk.Button(reset_bar, text="Reset Progress", style="Wood.TButton", command=self._on_reset_progress).pack(side="right")

	def _render_brewed(self):
		for child in self.brewed_container.winfo_children():
			child.destroy()
		if not self.state.brewed:
			ttk.Label(self.brewed_container, text="None yet", style="Small.TLabel").pack(anchor="w", padx=8, pady=6)
			return
		for name, qty in sorted(self.state.brewed.items()):
			row = ttk.Frame(self.brewed_container, style="Card.TFrame")
			row.pack(fill="x", padx=8, pady=4)
			img = self._load_potion_image(name, (24, 24))
			icon = ttk.Label(row, image=img if img else None, text=name if not img else "", style="Small.TLabel")
			if img:
				icon.image = img
			icon.pack(side="left")
			ttk.Label(row, text=f"x{qty}", style="Small.TLabel").pack(side="left", padx=8)

	# ---------- Event handlers ----------
	def _on_add_to_pot(self, name: str):
		if self.state.add_to_pot(name):
			self._refresh_all()
			self._auto_save()

	def _on_remove_from_pot(self, name: str):
		if name.startswith("extra:"):
			name = name.split(":", 1)[1]
		if self.state.remove_from_pot(name):
			self._refresh_all()
			self._auto_save()

	def _on_clear_pot(self):
		self.state.clear_pot()
		self._refresh_all()
		self._auto_save()

	def _on_brew(self, potion: Potion):
		success = self.state.brew(potion)
		if success:
			self._refresh_all()
			self._flash_message(f"Brewed {potion.name}! ✨")
			self._auto_save()
		else:
			self._flash_message("That mixture isn't quite right.")

	def _on_save_click(self):
		self._auto_save(force=True)
		self._flash_message("Progress saved.", ms=900)

	def _on_reset_progress(self):
		# Clear brewed, pot, and reset inventory to zero but keep ingredients; rely on bootstrap defaults if desired
		self.state.brewed.clear()
		self.state.clear_pot()
		# Do not wipe ingredient catalog; just zero out inventory
		self.state.inventory.clear()
		self._refresh_all()
		self._auto_save(force=True)
		self._flash_message("Progress reset.")

	def _flash_message(self, text: str, ms: int = 1400):
		if hasattr(self, "_flash_lbl") and self._flash_lbl is not None:
			try:
				self._flash_lbl.destroy()
			except Exception:
				pass
		self._flash_lbl = ttk.Label(self.center, text=text, style="Header.TLabel")
		self._flash_lbl.configure(foreground="#d1f5e0")
		self._flash_lbl.place(relx=0.5, rely=0.02, anchor="n")
		self.after(ms, lambda: (self._flash_lbl.destroy() if self._flash_lbl else None))

	# ---------- Helpers ----------
	def _refresh_all(self):
		self._render_inventory()
		self._render_pot_contents()
		self._render_recipes()
		self._render_brewed()

	def _auto_save(self, force: bool = False):
		try:
			self._on_save(self.state, self.save_path)
		except Exception:
			# Non-fatal
			pass

	def _on_close(self):
		self._auto_save(force=True)
		self.destroy()

	def _missing_text(self, missing: Dict[str, int]) -> str:
		if not missing:
			return ""
		parts = []
		for k, v in missing.items():
			if k.startswith("extra:"):
				parts.append(f"remove {k.split(':',1)[1]}×{v}")
			else:
				parts.append(f"need {k}×{v}")
		return ", ".join(parts)

	def _asset_path(self, category: str, name: str) -> Optional[Path]:
		# Look for images under (in order): user assets, bundled assets, dev assets
		def find_in(folder: Optional[Path]) -> Optional[Path]:
			if not folder:
				return None
			for ext in (".png", ".gif", ".ppm", ".pgm"):
				p = folder / category / f"{name}{ext}"
				if p.exists():
					return p
			return None
		return (
			find_in(self.assets_dirs.get("user"))
			or find_in(self.assets_dirs.get("bundled"))
			or find_in(self.assets_dirs.get("dev"))
		)

	def _load_ing_image(self, name: str, size: Tuple[int, int] = (64, 64)) -> Optional[tk.PhotoImage]:
		path = self._asset_path("ingredients", name)
		return self.image_cache.load(path, size)

	def _load_potion_image(self, name: str, size: Tuple[int, int] = (64, 64)) -> Optional[tk.PhotoImage]:
		path = self._asset_path("potions", name)
		return self.image_cache.load(path, size)


# -----------------------------
# Bootstrapping sample content and persistence
# -----------------------------

def user_data_dir(app_name: str = "Potioneer") -> Path:
	# Determine a per-user data directory
	if os.name == 'nt':
		base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~\\AppData\\Local')
	elif sys.platform == 'darwin':
		base = os.path.expanduser('~/Library/Application Support')
	else:
		base = os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
	return Path(base) / app_name


def get_assets_dirs(dev_base_dir: Path) -> Dict[str, Path]:
	dev_assets = dev_base_dir / "assets"
	user_dir = user_data_dir()
	user_assets = user_dir / "assets"
	user_assets.mkdir(parents=True, exist_ok=True)
	# Detect PyInstaller bundle assets
	bundled_base = None
	if hasattr(sys, '_MEIPASS'):
		bundled_base = Path(getattr(sys, '_MEIPASS')) / "assets"
	dirs: Dict[str, Path] = {"dev": dev_assets, "user": user_assets}
	if bundled_base and bundled_base.exists():
		dirs["bundled"] = bundled_base
	return dirs


def save_state(state: GameState, save_path: Path):
	save_path.parent.mkdir(parents=True, exist_ok=True)
	data = {
		"inventory": state.inventory,
		"brewed": state.brewed,
	}
	with save_path.open('w', encoding='utf-8') as f:
		json.dump(data, f, indent=2)


def load_state(save_path: Path) -> Optional[Dict[str, Dict[str, int]]]:
	if not save_path.exists():
		return None
	try:
		with save_path.open('r', encoding='utf-8') as f:
			data = json.load(f)
		inv = {str(k): int(v) for k, v in data.get('inventory', {}).items()}
		brw = {str(k): int(v) for k, v in data.get('brewed', {}).items()}
		return {"inventory": inv, "brewed": brw}
	except Exception:
		return None


def bootstrap_game(state: GameState, base_dir: Path) -> Tuple[Dict[str, Path], Path]:
	assets_dirs = get_assets_dirs(base_dir)
	# Define where to store save.json
	data_dir = user_data_dir()
	save_path = data_dir / "save.json"

	# Register some ingredients (images are optional; place matching files to see them)
	seed_ingredients: List[Tuple[str, int]] = [
		("mushroom", 5),
		("onion", 3),
		("herb", 6),
		("berry", 6),
		("water", 10),
		("flower", 4),
		("root", 5),
		("leaf", 7),
	]
	for name, qty in seed_ingredients:
		state.add_ingredient(name, None, starting_qty=0)

	# Load saved state or seed defaults
	loaded = load_state(save_path)
	if loaded:
		state.inventory.update(loaded["inventory"])  # adhere to catalog keys
		state.brewed.update(loaded["brewed"])        
	else:
		# Use seed quantities on fresh start
		for name, qty in seed_ingredients:
			if qty > 0:
				state.inventory[name] = qty

	# Define recipes using the flexible requires() helper
	def potion(name: str, req_spec):
		state.add_potion(name, requires(req_spec) if not isinstance(req_spec, dict) else req_spec)

	potion("Minor Healing Draught", requires("mushroom:1, herb:2, water:1"))
	potion("Night Sight Tonic", requires('"mushroom":2, "berry":2, "onion":1'))
	potion("Forest Whisper Elixir", requires({"flower": 2, "herb": 1, "water": 1}))
	potion("Stoneskin Philter", requires(leaf=3, root=2, water=1))

	# Optional: set potion images if present (resolved at render time via _asset_path)

	return assets_dirs, save_path


def main():
	# Determine base dir relative to this file (docs/)
	here = Path(__file__).parent
	state = GameState()
	assets_dirs, save_path = bootstrap_game(state, here)

	def _save(state_obj: GameState, path: Path):
		save_state(state_obj, path)

	app = PotionGameUI(state, assets_dirs, save_path, _save)
	app.mainloop()


if __name__ == "__main__":
	main()
