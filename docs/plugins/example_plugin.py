"""
Hunger Bens Plugin Template (Windows loader)

Drop this file (renamed) into one of these folders to load it automatically:
 - %LOCALAPPDATA%\HungerBens\plugins
 - %APPDATA%\HungerBens\plugins
 - %PROGRAMDATA%\HungerBens\plugins
 - Or the repo: docs/plugins

A plugin can export any of these optional callables:
 - get_custom_content() -> dict
	 Keys:
	   - "weapons": { name: verb }
	   - "items": [ str, ... ]
	   - "hazards": { name: effect }
 - get_events() -> { "day": [callable], "night": [callable], "global": [callable] }
	 Each event: (tributes: list, rng: random.Random, sim: object) -> list[str]
 - get_event_weights() -> { callable or callable_name: float }
	 Adjusts the relative frequency of your events.

Tips:
 - Avoid external imports. Stick to stdlib and what the game passes to you.
 - Keep events resilient if required content isn't present.
 - Return a list of narrative strings (each printed to the log).
"""

from typing import Any, Dict, List, Callable
import random

# Optional metadata
PLUGIN_NAME = "Confetti Extras"
PLUGIN_VERSION = "1.0.0"


# -----------------------------
# Custom Content
# -----------------------------
def get_custom_content() -> Dict[str, Any]:
	"""Provide extra weapons/items/hazards.

	This content is merged into the game's registries on load.
	"""
	return {
		# Weapon verbs describe how the weapon acts in kill lines
		"weapons": {
			"confetti cannon": "confetti-blasts",
			"rubber mallet": "bonks",
		},
		# Items show up in supply finds, crates, etc.
		"items": [
			"cupcake",
			"party horn",
		],
		# Hazards with their cause-of-death effect words
		"hazards": {
			"confetti fog": "suffocated in paper shreds",
		},
	}


# -----------------------------
# Example Events
# -----------------------------
def event_cupcake_party(tributes: List[Any], rng: random.Random, sim: Any) -> List[str]:
	"""Day/Night event: tasty morale boost for one tribute."""
	if not tributes:
		return []
	t = rng.choice(tributes)
	# Try to give a cupcake if items integrated; otherwise just narrate.
	try:
		if hasattr(t, "inventory") and isinstance(t.inventory, list):
			t.inventory.append("cupcake")
		if hasattr(t, "adjust_morale"):
			t.adjust_morale(+1)
	except Exception:
		pass
	return [f"{getattr(t, 'name', 'A tribute')} discovers a cupcake and feels a little braver."]


def event_confetti_misfire(tributes: List[Any], rng: random.Random, sim: Any) -> List[str]:
	"""Day/Night event: harmless mishap that lowers morale slightly."""
	if not tributes:
		return []
	t = rng.choice(tributes)
	try:
		if hasattr(t, "adjust_morale"):
			t.adjust_morale(-1)
	except Exception:
		pass
	return [f"{getattr(t, 'name', 'A tribute')} fumbles a party horn; the squeak gives away their position."]


def global_confetti_fog(all_tributes: List[Any], rng: random.Random, sim: Any) -> List[str]:
	"""Global event: a light, non-lethal weather moment."""
	lines = ["A gentle confetti fog drifts through the arena, sparkling in the light."]
	for t in all_tributes:
		if not getattr(t, 'alive', True):
			continue
		# Small morale swing either way
		try:
			if hasattr(t, 'adjust_morale'):
				t.adjust_morale(rng.choice([-1, 0, +1]))
		except Exception:
			pass
	return lines


# -----------------------------
# Registration
# -----------------------------
def get_events() -> Dict[str, List[Callable]]:
	"""Return event callables grouped by phase.

	You can return empty lists for phases you don't use.
	"""
	return {
		"day": [event_cupcake_party, event_confetti_misfire],
		"night": [event_cupcake_party],
		"global": [global_confetti_fog],
	}


def get_event_weights() -> Dict[Any, float]:
	"""Weights increase/decrease selection frequency.

	Use either the function object or its __name__ as the key.
	Base weights are ~0.5-1.3 in core; here we keep them modest.
	"""
	return {
		event_cupcake_party: 0.9,
		event_confetti_misfire: 0.6,
		"global_confetti_fog": 0.7,
	}


# Optional: simple self-check (won't run in the game, only when executed directly)
if __name__ == "__main__":
	print(f"Plugin: {PLUGIN_NAME} v{PLUGIN_VERSION}")
	print("Custom content:")
	print(get_custom_content())
	print("Events:")
	print({k: [f.__name__ for f in v] for k, v in get_events().items()})
	print("Weights:")
	print(get_event_weights())

