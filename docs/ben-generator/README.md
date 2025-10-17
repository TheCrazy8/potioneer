# Hunger Bens .ben Plugin Builder

A browser-based tool for creating plugin archives (.ben files) for the Hunger Bens Simulator.

## What is a .ben file?

A `.ben` file is simply a ZIP archive with a `.ben` extension containing Python plugin code. The Hunger Bens Simulator loads these plugins on Windows to extend gameplay with custom weapons, items, hazards, and events.

## Valid Plugin Structures

The simulator expects one of these entry points:

1. **Single file**: `plugin.py` at the root
2. **Package**: `plugin/__init__.py` 
3. **Fallback**: Exactly one `.py` file at the root level

### Optional Plugin API

Your entry module can define these optional functions:

```python
def get_custom_content():
    """Return custom content to merge into the game."""
    return {
        "weapons": {"laser spoon": "vaporizes"},
        "items": ["force field", "decoy duck"],
        "hazards": {"gravity well": "spaghettified"}
    }

def get_events():
    """Return event callables grouped by phase."""
    return {
        "day": [my_day_event],
        "night": [my_night_event],
        "global": [my_global_event]
    }

def get_event_weights():
    """Define relative event frequencies."""
    return {
        my_day_event: 0.8,
        "my_night_event": 1.2
    }
```

Event callables must accept `(tributes: list, rng: random.Random, sim: object)` and return a list of narrative strings.

## Using the Builder

### Quick Builder

The **Quick Builder** generates a complete plugin from a form:

1. **Fill in metadata**: Plugin ID (required), author, description, license
2. **Choose structure**: Single file (`plugin.py`) or package (`plugin/__init__.py`)
3. **Add custom content** (optional): Paste valid JSON for weapons, items, or hazards
4. **Include sample event** (optional): Adds example event scaffolding
5. **Additional files**: Optionally include README.txt and LICENSE.txt
6. **Build**: Click "Build .ben File" to download

![Quick Builder Screenshot](placeholder_screenshot_quick.png)

**Example JSON for custom content:**

Weapons:
```json
{"confetti cannon": "confetti-blasts", "rubber mallet": "bonks"}
```

Items:
```json
["cupcake", "party horn"]
```

Hazards:
```json
{"confetti fog": "suffocated in paper shreds"}
```

### Advanced Builder

The **Advanced Builder** lets you manually construct your plugin:

1. **Add files**: Create new text files or upload existing ones
2. **Add folders**: Organize files into directories
3. **Edit files**: Click the edit icon to modify file contents
4. **Manage structure**: Rename or delete files/folders as needed
5. **Validate**: The builder checks for valid entry points before packaging
6. **Build**: Enter a plugin ID and click "Build .ben File"

![Advanced Builder Screenshot](placeholder_screenshot_advanced.png)

**Tips:**
- Ensure you have at least one valid entry file
- Use forward slashes in paths (e.g., `plugin/__init__.py`)
- Test Python syntax before building

## Testing Your Plugin

### Installation

Copy your `.ben` file to one of these locations on Windows:

- `%LOCALAPPDATA%\HungerBens\plugins`
- `%APPDATA%\HungerBens\plugins`
- `%PROGRAMDATA%\HungerBens\plugins`
- Or place in `docs/plugins` in the repository

### Running

1. Launch the Hunger Bens Simulator GUI
2. Go to **Settings** to verify plugins are enabled
3. Run a simulation
4. Check the log output for plugin loading messages

The simulator logs will show:
```
[Plugins] Loaded my_custom_plugin.py
[Plugins] Integrated custom content from my_custom_plugin.py
[Plugins] Registered events from my_custom_plugin.py
```

### Debugging

If your plugin doesn't load:

1. **Check the entry point**: Verify you have `plugin.py`, `plugin/__init__.py`, or exactly one `.py` at root
2. **Validate Python syntax**: Run `python -m py_compile plugin.py` on the extracted file
3. **Review logs**: The simulator logs plugin errors with tracebacks
4. **Test functions**: Run your plugin directly: `python plugin.py`

You can extract the `.ben` file with any ZIP tool (rename to `.zip` if needed) to inspect contents.

## Examples

### Minimal Plugin

The simplest valid plugin:

**plugin.py**
```python
"""
My First Plugin
"""

def get_custom_content():
    return {
        "weapons": {"rubber chicken": "bonks"}
    }
```

### Plugin with Events

**plugin.py**
```python
"""
Event Plugin
"""
import random

def my_event(tributes, rng, sim):
    if not tributes:
        return []
    t = rng.choice(tributes)
    return [f"{t.name} discovers something interesting."]

def get_events():
    return {
        "day": [my_event],
        "night": [],
        "global": []
    }

def get_event_weights():
    return {
        my_event: 0.9
    }
```

### Package Structure

For larger plugins, use a package:

```
my_plugin.ben (zip containing):
├── plugin/
│   ├── __init__.py      # Main entry point
│   ├── events.py        # Event definitions
│   └── content.py       # Custom content
├── README.txt
└── LICENSE.txt
```

**plugin/__init__.py**
```python
"""
My Complex Plugin
"""
from .content import get_custom_content
from .events import get_events, get_event_weights

__all__ = ['get_custom_content', 'get_events', 'get_event_weights']
```

## Troubleshooting

### "No valid entry point found"

Ensure you have one of:
- A file named `plugin.py` at the root
- A folder named `plugin` with `__init__.py` inside
- Exactly one `.py` file at the root (no other `.py` files)

### "Invalid JSON"

Check your custom content JSON:
- Use double quotes for strings
- No trailing commas
- Valid JSON syntax (test with an online validator)

### Plugin doesn't appear in simulator

- Verify the file is in a recognized plugins folder
- Check that plugins are enabled in Settings
- Look for error messages in the simulator log
- The simulator only loads plugins on Windows

## Resources

- [Main Repository](https://github.com/TheCrazy8/hunger-bens)
- [Example Plugin](https://github.com/TheCrazy8/hunger-bens/blob/main/docs/plugins/example_plugin.py)
- [Web Simulator](https://thecrazy8.github.io/hunger-bens/)

## License

This builder tool is part of the Hunger Bens project and follows the same license (Apache 2.0).
