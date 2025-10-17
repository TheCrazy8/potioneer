# Hunger Bens Simulator

Hunger games similator but i added at least one too many features

## Running (CLI)
Examples:

```
python main.py --seed 42 --max-days 15
python main.py --quiet --export-log run.json
python main.py --roster custom_roster.json --strict-shutdown 10
```

Interactive (legacy) mode:

```
python main.py --interactive
```

## Windows GUI
On Windows you can launch a Tkinter GUI:

```
python main.py --gui
```

GUI Features:
- Enter seed (optional) for reproducibility
- Set Max Days and optional Strict Shutdown day
- Toggle Verbose (controls console printing; GUI always captures log)
- Optional export JSON filename (Browse to pick path)
- Load a custom roster JSON (list or dict format; see below)
- Run Simulation: displays live log lines in scrollable window
- Clear Output / Quit buttons

Roster file format examples:

List form:
```json
[
	{"key": "c1", "name": "Alpha", "gender": "f", "age": 20, "district": 3},
	{"key": "c2", "name": "Beta", "gender": "m", "age": 19, "district": 7}
]
```

Dict form:
```json
{
	"c1": {"name": "Alpha", "gender": "f", "age": 20, "district": 3},
	"c2": {"name": "Beta", "gender": "m", "age": 19, "district": 7}
}
```

## Export Log
Use `--export-log myrun.json` or specify path in GUI to save full simulation details (tributes, death log, events, stats, alliances, seed).

## Reproducibility
Providing a `--seed` or GUI seed ensures an identical event sequence across runs with the same roster and parameters.

## License
- [Apache License 2.0](https://github.com/TheCrazy8/hunger-bens/blob/main/LICENSE)
  
## Web Version (GitHub Pages)
This uses Pyodide to make the site functional and should load in most web browsers.

## Custom Content (Weapons / Hazards / Events)

You can extend the simulation without editing `main.py` by providing a content JSON file and optional events Python module.

CLI usage:
```
python main.py --content my_content.json
```
Combine with roster:
```
python main.py --roster custom_roster.json --content my_content.json --seed 99
```

GUI usage (Windows): Use the "Content JSON" loader to integrate extensions before running.

Schema example:
```json
{
	"weapons": {
		"laser spoon": "vaporizes",
		"sonic fork": "resonates"
	},
	"items": ["force field", "decoy duck"],
	"hazards": {
		"gravity well": "spaghettified",
		"nano swarm": "dismantled"
	},
	"events_module": "events_extra.py"
}
```

`events_module` is an optional Python file you create containing any of these variables:
```python
# events_extra.py
def event_echo(tributes, rng, sim):
		t = rng.choice(tributes)
		return [f"{t.name} shouts into the void; the echo offers no counsel."]

DAY_EVENTS_EXTRA = [event_echo]
NIGHT_EVENTS_EXTRA = []
GLOBAL_EVENTS_EXTRA = []
```

All event callables must accept `(tributes_list, rng, simulator)` and return a list of narrative strings.

New weapons get verbs (used in combat narration). New items appended to supply pools. Hazards map to their death-effect keywords. If weights aren't specified, added events receive a neutral base weight of 0.7.

Tip: Keep events fast and side-effect minimal beyond modifying tribute properties.


## Credit

- [Sun Valley](https://github.com/rdbende/Sun-Valley-ttk-theme): Windows gui theme
- [Pyodide](https://pyodide.org/): Used for GitHub Pages functionality
