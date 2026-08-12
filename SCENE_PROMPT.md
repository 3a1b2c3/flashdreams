# Scene Prompt Feature

## Overview

The Scene Prompt feature allows you to input and manage text prompts for the world model during interactive-drive sessions. The prompt is displayed in the HUD and can be edited in real-time.

## Usage

### Entering Edit Mode
- Press **P** to enter prompt edit mode
- The prompt field will turn **green** with an input box
- Instructions appear: "Scene Prompt (Enter=send, Esc=cancel):"

### Editing the Prompt
- Type text using the keyboard (letters, numbers, spaces supported)
- Press **Backspace** to delete the last character
- Character counter shows current/max: `Characters: X/500`
- Max length is 500 characters

### Sending the Prompt
- Press **Return/Enter** to send the prompt
- The field exits edit mode and displays the prompt text
- Press **Escape** to cancel editing without sending

### Display Mode
- When not editing, the prompt appears at the **top-left** of the HUD
- Shows the current prompt text or `[No prompt set - Press P to add one]` if empty
- Format: "Scene Prompt (P to edit): [your prompt text]"

## Implementation Details

### File Locations
- **Main HUD code**: `integrations/omnidreams/omnidreams/interactive_drive/slangpy_hud_presenter.py`
  - Keyboard handler: `_on_keyboard_event()` (~line 2421)
  - Prompt rendering: `_draw_prompt_overlay()` (~line 1484)
  - Prompt sending: `_send_scene_prompt()` (~line 2900)

### Key Components

**State Variables** (initialized in `__init__`, ~line 449):
```python
self._prompt_edit_mode = False      # Whether in edit mode
self._prompt_text = ""              # Current input being edited
self._current_scene_prompt = ""     # The stored/displayed prompt
```

**Keyboard Input** (in `_on_keyboard_event`):
- **P key**: Enter edit mode
- **Escape**: Exit edit mode
- **Backspace**: Delete last character
- **Return**: Send the prompt
- **Characters (a-z, 0-9, space)**: Add to prompt text
- Character extraction: KeyCode enum names are converted to characters (e.g., `KeyCode.i` → `'i'`, `KeyCode.digit1` → `'1'`)

**Rendering** (in `_draw_prompt_overlay`):
- **Edit mode**: Green background, input area, character counter, instructions
- **Display mode**: Gray text showing the stored prompt
- Position: Top-left of canvas (20px from left, 20px from top)

## Current Status

### What Works
✅ Prompt input and editing (keyboard, text entry)  
✅ Display and visualization in HUD  
✅ Storage of prompt text  
✅ Character limit enforcement (500 chars)  
✅ Visual feedback (edit mode highlighting, character counter)  

### What's Not Yet Implemented
⏳ **World Model Integration**: The prompt is stored and displayed but not yet connected to the world model's conditioning system. Pressing Enter logs the prompt but does not currently affect video generation.

To enable world model integration, the `_send_scene_prompt()` method (line 2900) needs to:
1. Access the world model session/pipeline
2. Update the text embedding in the `conditional_dict`
3. Trigger the world model to use the new prompt for subsequent frames

This can be implemented once the world model's conditioning API is available in the presenter context.

## Physics Parameters

The interactive-drive app also supports tunable physics parameters via CLI arguments. See `run_interactive_drive_perf.bat` for available options:
- `--suspension-stiffness`: Suspension stiffness (default 42, extreme 100)
- `--suspension-damping`: Suspension damping (default 9, bouncy 2)
- `--collision-restitution`: Bounce factor (default 0.22, extreme 0.8)
- `--collision-friction`: Surface friction (default 0.65, slippery 0.3)
- `--tire-grip`: Tire grip (default 1.35, high 2.5)

Example command with extreme bouncy physics:
```batch
interactive-drive.exe --suspension-stiffness 100 --suspension-damping 2 --collision-restitution 0.8 --collision-friction 0.3 --tire-grip 2.5
```

## Debugging

Enable debug logs to trace prompt interactions:
```
LOGLEVEL=DEBUG
PYTHONUNBUFFERED=1
```

Look for log messages with the `[PROMPT-EDIT]` prefix to see:
- Mode changes (entering/exiting edit)
- Text updates
- Prompt sends
