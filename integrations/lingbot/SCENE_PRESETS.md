# LingBot Scene Presets

## Overview
Scene presets allow users to quickly load predefined scene configurations (prompt + events) into the LingBot initial scene panel.

## Features
- **Built-in presets**: 5 default scene presets (Dragon, Jet Ski Cruise, Noir Alley Combat, Water Blaster, Circuit Racer)
- **Default on load**: "Dragon" auto-applies when the page opens (no manual selection needed)
- **Save custom presets**: Save current scene configuration as a new preset
- **Persistent storage**: Presets saved in browser localStorage
- **Quick access**: Dropdown selector in "Quick Start" section
- **Images**: each built-in preset's start image is a public `raw.githubusercontent.com` URL (no binaries committed to this repo)

## Usage

### Loading a Preset
1. Open LingBot WebRTC interface (the "Dragon" preset is pre-selected by default)
2. Find "Quick Start" dropdown in Initial Scene panel
3. Select a different preset from the dropdown
4. Preset prompt + events + start image auto-populate the form; the dropdown stays on the selected preset name

### In-Game Event Hotkeys
Once connected, each preset's events are playable with **letter-key
hotkeys** — every event button shows its letter (e.g. "Portal (B)").
Letters are assigned in order from a fixed pool (`b, f, g, h, m, n, o, p,
r, t, u, v, x, y, z`) that deliberately excludes the movement keys
(w/a/s/d/q/e/i/j/k/l) so hotkeys never collide with driving input. Press
**c** to Clear the active event — present and wired the same way on every
game, since Clear isn't part of any preset's catalog. Ignored while typing
in a text field. Events beyond the 15-letter pool still work by click,
just without a shown hotkey.

### Director Controls
Each preset's events are split into two categories, matching the original
REACTOR case files' `actor: "character"` (player-triggered) vs.
`actor: "environment"` (narrative/pacing) events:
- **Player Controls** — always visible, the regular action buttons.
- **Director Controls** — a separate panel with the environment/pacing
  events (weather, hazards, wildlife, etc.), only reachable when the page
  URL includes `?director` (e.g. `?manual&director`). When present, a
  toggle button appears in each panel ("Director Controls →" /
  "← Player Controls") to switch between them — only one is shown at a
  time. Hotkey letters are assigned across *both* panels together (player
  first) so a letter never maps to two different events even though only
  one panel is visible at once.

Both panels' events are always uploaded to the server together regardless
of `?director` — the shared WebRTC protocol has no player/director
distinction, so this split is purely a client-side UI/visibility choice.

### Sharing a Preset via URL
Add `?preset=<slug>` to the page URL to land directly on a specific built-in
preset instead of the "Dragon" default — the slug is the preset name,
lowercased with spaces replaced by hyphens (e.g. `Water Blaster` →
`water-blaster`). Example: `http://<host>:8089/request_session?preset=circuit-racer`.
Unknown/missing slugs fall back to the default preset. This only shares
*which game loads*, not a live/running session — WebRTC still allows only
one active session per server process.

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

## Adding a New Built-in Preset (Game)

Built-in presets live in the `scenePresets` array at the top of
`integrations/lingbot/lingbot/webrtc/web/adapter.js`. To add one:

1. **Write the base prompt** (1-3 sentences): subject + environment + style,
   third person (or first person for cockpit/POV scenes like Circuit
   Racer/Water Blaster). No camera-motion or input language — this app
   drives movement via the `w/a/s/d/q/e/i/j/k/l` keys and text events, not
   prose.
2. **Write 8-10 events**: each a short one-sentence imperative/descriptive
   clause (`{ event_id, label, prompt }`). `event_id` is a short lowercase
   token, unique within that preset's own `events` array (ids can repeat
   *across* presets — each preset's list is independent). Mix
   character-triggered actions (tricks, attacks) with environment beats
   (weather, other characters/vehicles appearing).
   - If you have access to `REACTOR_js-sdk`'s `lib/lingbot-cases/*.json`
     (a richer, layered `base`/`camera`/`movement`/`events` scene format
     used by a different app), you can mine its `scene.base.default` and
     `scene.events[].detail` text for content and compress it down to this
     flatter prompt+events shape — drop the camera/movement layers and any
     `EXACTLY ONE ...` frame-count guard clauses, since this app doesn't use
     that layering. Reference copies of a few are kept in
     `lingbot/webrtc/web/assets/sources/` for exactly this purpose.
3. **Pick a start image**: use a public, already-hosted `https://` URL
   (e.g. a `raw.githubusercontent.com` link) rather than committing a new
   binary to this repo. The server validates any URL submitted through the
   "Update" button (`_validate_remote_url` in `lingbot/webrtc/session.py`)
   and **rejects non-publicly-routable hosts** (private/LAN IPs, localhost)
   as an SSRF guard — so an image served by this same box's own private IP
   won't work as a preset `image` URL, but any normal public host will.
4. **Add the object** to `scenePresets`:
   ```js
   {
     name: "My Game",
     image: "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>.jpg",
     prompt: "...",
     events: [
       { event_id: "thing1", label: "Thing One", prompt: "..." },
       // ...
     ],
   },
   ```
5. **(Optional) Make it the default**: the preset at index `0` is
   auto-applied on page load via `presetSelect.value = "0"; applyPreset(0)`
   in `mount()` — reorder the array (or edit those two lines) to change
   which preset that is.
6. **Reload the page** — `adapter.js` is served straight off disk on every
   request (`add_static` in `flashdreams/serving/webrtc/server.py`), so a
   browser refresh picks up the change with no server restart needed, as
   long as you're running an editable (`pip install -e`) install.
7. Update the **Built-in Presets** list below and the preset count in
   **Features** to keep this doc in sync.

## Storage Location
- **Browser**: localStorage under key `lingbot-presets`
- **Persistence**: Survives page refresh, tab close
- **Scope**: Browser/domain specific
- **Cleared when**: Browser cache is cleared, incognito mode

## Built-in Presets

### 1. Dragon (default)
- **Prompt**: "A soaring journey through a fantasy jungle on the back of a flying creature. The wind whips past the rider's blue hands gripping the reins, causing the leather straps to vibrate, as the aerial voyage carries them toward an ancient gothic castle, its stonework growing clearer as it nears. Floating landmasses and cascading waterfalls fill the fantastical landscape below."
- **Events**: Jump, Portal, Storm, Fireworks.
- Same scene as the app's example-00 default (`_DEFAULT_IMAGE_URL` in `session.py`); Portal/Storm/Fireworks are `DEFAULT_TEXT_EVENTS` from `session.py` (also on `main`), not invented for this preset. This preset just names the scene, adds Jump, and auto-selects it on load.

### 2. Jet Ski Cruise
- **Prompt**: "Turquoise water near a sandy beach lined with palm trees. A man in a red life vest riding a white and red jet ski, keeping it on top of the water at all times."
- **Events**: Jump, Crouch, One-Hand Wave, Donut Spray, Shark Appears, Dolphins Leap, Storm Rolls In, Rogue Wave, Shark Lunges, Waterspout Forms, Whale Breaches, Island Appears, Sea Turtle, Volcanic Island Erupts, Fuel Runs Low, Thrown from the Jet Ski.

### 3. Noir Alley Combat
- **Prompt**: "A narrow urban alley at night, dark brick walls and heavy rain, shiny puddles on wet asphalt, yellow police tape, blue and red ambient light. A lone uniformed police officer in dark blue tactical gear holding a flashlight."
- **Events**: Jump, Crouch, Draw Pistol, Punch Combo, Roundhouse Kick, Baton Strike, Dodge Roll, Rain Intensifies.

### 4. Water Blaster
- **Prompt**: "First-person point of view aiming out across a colourful floating inflatable aqua park on a calm green quarry lake under bright summer sun. A bare hand grips a blue and red toy water blaster at the lower right of the frame."
- **Events**: Jump, Crouch, Splash Blast, Raise Float Shield, Green Slime Blast, Dive, Rival Blaster Ambush, Bathers Get Super Soakers, Crocodile Lunges, Wave Surge, Giant Balloon Drops, Float Deflates.

### 5. Circuit Racer
- **Prompt**: "First-person cockpit view from inside a Formula 1 race car, gloved hands on the wheel and the glowing dash ahead, speeding down a sunlit asphalt racing circuit lined with red-and-white kerbs."
- **Events**: Jump, Kick Up Sparks, Lock-Up Smoke, Crash, Rain Sweeps In, Sun Glare, Tunnel Section, Road Fire, Checkered Flag, Rabbit on the Track, Puddle on the Track, Oil Slick Ahead, Clear Dry Track.

Noir Alley Combat, Water Blaster, Jet Ski Cruise, and Circuit Racer prompts/events are adapted from the richer layered scene definitions in `REACTOR_js-sdk`'s `lib/lingbot-cases/*.json` (kept as reference copies under `lingbot/webrtc/web/assets/sources/` in this repo) down to this app's flatter prompt+events format. Their start images are hotlinked from that repo's `examples` branch on GitHub rather than committed here.

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
  - Top of file: Preset data definitions (`scenePresets`)
  - `makeSceneCard()`: Scene card HTML with dropdown + Save button
  - `saveCurrentPreset()` / `updatePresetDropdown()` / `loadSavedPresets()` / `applyPreset()`: Load/Save preset functions
  - `mount()`: selects + applies preset index 0 ("Dragon") on load, before `loadInitialScene()` runs
  - `presetSelect.addEventListener` / `savePresetButton.addEventListener`: Event listeners

## Future Enhancements
1. **Server-side storage**: Save presets to backend database
2. **Export/Import**: Download presets as JSON file
3. **Sharing**: Share presets via link or code
4. **Categories**: Organize presets by category
5. **Versioning**: Track preset changes over time
