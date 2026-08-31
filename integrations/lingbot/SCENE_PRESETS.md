# LingBot Scene Presets

## Overview
Scene presets allow users to quickly load predefined scene configurations (prompt + events) into the LingBot initial scene panel.

## Features
- **Built-in presets**: 4 default scene presets (Jet Ski Cruise, GTA Street Cruise, Rodeo Bull Ride, Circuit Racer)
- **Save custom presets**: Save current scene configuration as a new preset
- **Persistent storage**: Presets saved in browser localStorage
- **Quick access**: Dropdown selector in "Quick Start" section

## Usage

### Loading a Preset
1. Open LingBot WebRTC interface
2. Find "Quick Start" dropdown in Initial Scene panel
3. Select a preset from the dropdown
4. Preset prompt + events auto-populate the form; the dropdown stays on the selected preset name

### Saving a Preset
1. Edit prompt and text events in the Initial Scene panel
2. Click "Save" button next to Quick Start dropdown
3. Enter a name for the preset (e.g., "My Custom Scene")
4. Preset is saved to browser localStorage
5. New preset appears in dropdown for future use

## Data Format

Presets are stored as JSON array in `localStorage["lingbot-presets"]`:

```json
[
  {
    "name": "Preset Name",
    "prompt": "Scene prompt text",
    "events": [
      {
        "event_id": "unique-id",
        "label": "Event Label",
        "prompt": "Event prompt text"
      }
    ]
  }
]
```

## Storage Location
- **Browser**: localStorage under key `lingbot-presets`
- **Persistence**: Survives page refresh, tab close
- **Scope**: Browser/domain specific
- **Cleared when**: Browser cache is cleared, incognito mode

## Built-in Presets

### 1. Jet Ski Cruise
- **Prompt**: "Turquoise water near a sandy beach lined with palm trees. A man in a red life vest riding a white and red jet ski, keeping it on top of the water at all times."
- **Events**: Spin 360, Nose Pop, Slalom Weave, Superman, One-Hand Wave, Donut Spray, Shark Appears, Dolphins Leap, Storm Rolls In, Rogue Wave.

### 2. GTA Street Cruise
- **Prompt**: "A sun-baked city street lined with palm trees and pastel storefronts at golden hour. A teal-green 1964 lowrider convertible with gleaming chrome wire wheels cruising down the wide asphalt."
- **Events**: Hydraulics Bounce, Honk Horn, Headlights, Spray Tag, Rival Rolls Up, Police Chase, Nightfall, Rainstorm, Fireworks, Crowd Gathers.

### 3. Rodeo Bull Ride
- **Prompt**: "A dusty floodlit rodeo arena at dusk. A cowboy in a wide-brimmed hat and chaps gripping the rope one-handed on the back of a massive bucking bull."
- **Events**: Bull Bucks Violently, Bull Spins Hard, Spur the Bull, Wave Hat, Thrown Off, Dust Storm, Crowd Erupts, Rodeo Clown Distracts, Arena Fire, Bull Stands Still.

### 4. Circuit Racer
- **Prompt**: "First-person cockpit view from inside a Formula 1 race car, gloved hands on the wheel and the glowing dash ahead, speeding down a sunlit asphalt racing circuit lined with red-and-white kerbs."
- **Events**: Drift, Kick Up Sparks, Lock-Up Smoke, DRS Boost, Crash, Rain Sweeps In, Sun Glare, Tunnel Section, Road Fire, Checkered Flag.

## Browser Console Access

View all saved presets:
```javascript
JSON.parse(localStorage.getItem("lingbot-presets"))
```

Clear all presets:
```javascript
localStorage.removeItem("lingbot-presets")
```

## Implementation Files
- **UI**: `integrations/lingbot/lingbot/webrtc/web/adapter.js`
  - Lines 6-67: Preset data definitions (`scenePresets`)
  - `makeSceneCard()`: Scene card HTML with dropdown + Save button
  - `saveCurrentPreset()` / `updatePresetDropdown()` / `loadSavedPresets()` / `applyPreset()`: Load/Save preset functions
  - `presetSelect.addEventListener` / `savePresetButton.addEventListener`: Event listeners

## Future Enhancements
1. **Server-side storage**: Save presets to backend database
2. **Export/Import**: Download presets as JSON file
3. **Sharing**: Share presets via link or code
4. **Categories**: Organize presets by category
5. **Versioning**: Track preset changes over time
