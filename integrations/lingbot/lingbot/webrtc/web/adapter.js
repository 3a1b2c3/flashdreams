// SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

const mockMode = new URLSearchParams(window.location.search).has("mock")
// ?director shows the separate Director Controls panel (environment/pacing
// events, e.g. weather and hazards) alongside Player Controls -- hidden by
// default since this is a second operator's role, not the regular player's.
// Also toggleable at runtime via the "Director Mode" button (no URL edit
// needed); mutable for that reason.
let directorMode = new URLSearchParams(window.location.search).has("director")

// Letter hotkeys for event buttons, in assignment order. Excludes the
// reserved movement keys (w/a/s/d/q/e/i/j/k/l) and "c" (Clear's own
// hotkey) so they never collide with driving input or each other. Letters
// run out before director-heavy presets do -- events past the pool size
// simply render without a hotkey, same as the old 9-key digit cap.
const EVENT_HOTKEY_LETTERS = ["b", "f", "g", "h", "m", "n", "o", "p", "r", "t", "u", "v", "x", "y", "z"]

function presetSlug(name) {
  return name.toLowerCase().trim().replace(/\s+/g, "-")
}

function findPresetIndexBySlug(slug) {
  if (!slug) return -1
  const normalized = slug.toLowerCase().trim()
  return scenePresets.findIndex((preset) => presetSlug(preset.name) === normalized)
}

const scenePresets = [
  {
    name: "Dragon",
    image: "https://raw.githubusercontent.com/Robbyant/lingbot-world-v2/main/examples/00/image.jpg",
    prompt: "A soaring journey through a fantasy jungle on the back of a flying creature. The wind whips past the rider's blue hands gripping the reins, causing the leather straps to vibrate, as the aerial voyage carries them toward an ancient gothic castle, its stonework growing clearer as it nears. Floating landmasses and cascading waterfalls fill the fantastical landscape below.",
    events: [
      { event_id: "jump", label: "Jump", prompt: "The creature tucks its wings and launches into a sudden upward leap, gaining height in a single powerful beat." },
    ],
    directorEvents: [
      { event_id: "portal", label: "Portal", prompt: "A luminous magical portal opens in the scene, casting colored light and swirling particles into the environment." },
      { event_id: "storm", label: "Storm", prompt: "A dramatic storm rolls in with dark clouds, wind, rain, and flashes of lightning reshaping the atmosphere." },
      { event_id: "fireworks", label: "Fireworks", prompt: "Bright fireworks burst overhead, filling the sky with colorful sparks and reflections across the scene." },
    ],
    hud: { maxHealth: 100 },
  },
  {
    name: "Jet Ski Cruise",
    image: "https://raw.githubusercontent.com/3a1b2c3/js-sdk/examples/examples/lingbot-world-2/public/lingbot-cases/jet-ski-cruise.jpg",
    prompt: "Turquoise water near a sandy beach lined with palm trees. A man in a red life vest riding a white and red jet ski, keeping it on top of the water at all times.",
    events: [
      { event_id: "jump", label: "Jump", prompt: "The jet ski leaps up off the water, the hull lifting clear of the surface, then drops back down with a splash and the rider settles upright at the handlebars again." },
      { event_id: "crouch", label: "Crouch", prompt: "The rider crouches down low, bending into a compact, hunched stance close to the jet ski." },
      { event_id: "onehand", label: "One-Hand Wave", prompt: "Lift one hand and wave it high overhead." },
      { event_id: "donut", label: "Donut Spray", prompt: "Lean into tight continuous circles carving donuts." },
    ],
    // Director/environment events (from the original case's "director" pacing note).
    // health deltas below match the original case's HUD (fuel-as-health).
    directorEvents: [
      { event_id: "dolphins", label: "Dolphins Leap", prompt: "Sleek dolphins surface and leap in formation.", health: 5 },
      { event_id: "storm", label: "Storm Rolls In", prompt: "Dark clouds roll in, wind whips up, sea churns grey.", health: -10 },
      { event_id: "wave", label: "Rogue Wave", prompt: "A towering rogue wave rears up ahead.", health: -15 },
      { event_id: "sharklunge", label: "Shark Lunges", prompt: "The shark's fin surges fast across the surface straight toward the jet ski, cutting alongside it in a rush of spray.", health: -15 },
      { event_id: "waterspout", label: "Waterspout Forms", prompt: "A towering waterspout twists up from the sea on the horizon, a swirling column of water and mist.", health: -15 },
      { event_id: "volcano", label: "Volcanic Island Erupts", prompt: "The distant island erupts into a volcano, glowing lava streaming down its slopes and ash rising into the sky.", health: -10 },
      { event_id: "lowfuel", label: "Fuel Runs Low", prompt: "The jet ski's engine begins to strain and sputter as the fuel runs low, coughing and losing power.", health: -40 },
      { event_id: "thrown", label: "Thrown from the Jet Ski", prompt: "The jet ski bucks hard over a wave and the rider is thrown clean off, crashing into the water.", health: -30 },
    ],
    hud: { maxHealth: 100, healthLabel: "Fuel" },
  },
  {
    name: "Noir Alley Combat",
    image: "https://raw.githubusercontent.com/3a1b2c3/js-sdk/examples/examples/lingbot-world-2/public/lingbot-cases/noir-alley-combat.jpg",
    prompt: "A narrow urban alley at night, dark brick walls and heavy rain, shiny puddles on wet asphalt, yellow police tape, blue and red ambient light. A lone uniformed police officer in dark blue tactical gear holding a flashlight.",
    events: [
      { event_id: "jump", label: "Jump", prompt: "The officer springs upward off both feet, leaping high off the wet asphalt, then lands and rises back to a normal upright stance." },
      { event_id: "pistol", label: "Draw Pistol", prompt: "The officer draws a sidearm pistol from its holster, raising it two-handed and aiming it straight ahead down the alley." },
      { event_id: "crouch", label: "Crouch", prompt: "The officer drops into a low, compact crouch, close to the wet asphalt." },
      { event_id: "punch", label: "Punch Combo", prompt: "Snap forward with a fast jab, cross, and heavy hook, water spraying off the knuckles.", health: -5 },
      { event_id: "roundhouse", label: "Roundhouse Kick", prompt: "Plant the lead foot and whip a fast roundhouse kick through the rain.", health: -5 },
      { event_id: "baton", label: "Baton Strike", prompt: "Flick open a steel baton and swing it down in a swift overhead strike.", health: -8 },
      { event_id: "dodge", label: "Dodge Roll", prompt: "Drop into a low crouch and roll fast across the wet asphalt, rising back to a ready stance.", health: 10 },
    ],
    directorEvents: [
      { event_id: "rain", label: "Rain Intensifies", prompt: "The rain turns into a heavy downpour, streaking through the neon light and drumming on the puddles." },
    ],
    hud: { maxHealth: 100 },
  },
  {
    name: "Water Blaster",
    image: "https://raw.githubusercontent.com/3a1b2c3/js-sdk/examples/examples/lingbot-world-2/public/lingbot-cases/watergun.jpg",
    prompt: "First-person point of view aiming out across a colourful floating inflatable aqua park on a calm green quarry lake under bright summer sun. A bare hand grips a blue and red toy water blaster at the lower right of the frame.",
    events: [
      { event_id: "jump", label: "Jump", prompt: "The player leaps up and forward off the edge of the platform, sailing over a gap of open water, then lands with a splash and stands back upright." },
      { event_id: "crouch", label: "Crouch", prompt: "The player crouches down behind the raised edge of an inflatable platform for cover, only the top of the water blaster peeking over." },
      { event_id: "splash", label: "Splash Blast", prompt: "Unleash a wide fan of water, a broad sweeping spray douses the platform ahead." },
      { event_id: "shield", label: "Raise Float Shield", prompt: "Haul up a clear inflatable board as a shield, incoming water jets hammering into it." },
      { event_id: "slime", label: "Green Slime Blast", prompt: "Suck up dark green lake water and unload it as a thick glowing green slime stream." },
      { event_id: "dive", label: "Dive", prompt: "Plunge underwater, murky green light and rising bubbles closing over the frame." },
    ],
    directorEvents: [
      { event_id: "ambush", label: "Rival Blaster Ambush", prompt: "A rival pops up from behind a platform and opens fire with their own water blaster.", health: -12 },
      { event_id: "soakers", label: "Bathers Get Super Soakers", prompt: "Every bather in the park raises a huge super soaker and opens fire at once.", health: -12 },
      { event_id: "crocodile", label: "Crocodile Lunges", prompt: "A crocodile surges up out of the water, jaws gaping, lunging straight at the camera.", health: -20 },
      { event_id: "wavesurge", label: "Wave Surge", prompt: "The calm lake churns into rolling swells, the inflatable platforms pitching hard." },
      { event_id: "balloon", label: "Giant Balloon Drops", prompt: "A huge water balloon plummets down and bursts on the platform ahead in an enormous explosion of water." },
      { event_id: "deflate", label: "Float Deflates", prompt: "One of the large inflatable platforms splits and rapidly deflates, sinking below the surface." },
    ],
    hud: { maxHealth: 100 },
  },
  {
    name: "Circuit Racer",
    image: "https://raw.githubusercontent.com/3a1b2c3/js-sdk/examples/examples/lingbot-world-2/public/lingbot-cases/circuit.jpg",
    prompt: "First-person cockpit view from inside a Formula 1 race car, gloved hands on the wheel and the glowing dash ahead, speeding down a sunlit asphalt racing circuit lined with red-and-white kerbs.",
    events: [
      { event_id: "jump", label: "Jump", prompt: "The track kinks up into a ramp and the car launches off the crest into open sky before slamming back down with a hard jolt." },
      { event_id: "sparks", label: "Kick Up Sparks", prompt: "The floor grounds out on the asphalt, spraying a bright shower of orange sparks past the nose." },
      { event_id: "lockup", label: "Lock-Up Smoke", prompt: "The brakes lock hard into the corner, boiling thick white tyre smoke off the front wheels." },
      { event_id: "crash", label: "Crash", prompt: "The car slams into the barrier, carbon-fibre debris flying as it grinds to a juddering halt." },
    ],
    directorEvents: [
      { event_id: "rain", label: "Rain Sweeps In", prompt: "Dark storm clouds roll over and rain sweeps across the windscreen, the track glistening wet." },
      { event_id: "glare", label: "Sun Glare", prompt: "The low sun blazes straight into the windscreen, washing out the track ahead in blinding light.", health: -5 },
      { event_id: "tunnel", label: "Tunnel Section", prompt: "The track dives into a dark tunnel, strings of overhead lights strobing past overhead." },
      { event_id: "roadfire", label: "Road Fire", prompt: "A wall of orange flame and black smoke erupts across the track directly ahead." },
      { event_id: "flag", label: "Checkered Flag", prompt: "The car sweeps across the start-finish line as a marshal waves the chequered flag overhead." },
      { event_id: "rabbit", label: "Rabbit on the Track", prompt: "A rabbit darts out onto the track ahead and stops directly in the car's path." },
      { event_id: "puddle", label: "Puddle on the Track", prompt: "A wide sheet of standing water lies across the track ahead, the car hydroplaning through it.", health: -5 },
      { event_id: "oilslick", label: "Oil Slick Ahead", prompt: "A dark oil slick spreads across the track ahead, the car slewing sideways as it hits it.", health: -8 },
    ],
    hud: { maxHealth: 100 },
  },
]

const controls = [
  {
    label: "Drive / Turn",
    keys: [
      { key: "w", label: "Forward" },
      { key: "a", label: "Turn left" },
      { key: "s", label: "Backward" },
      { key: "d", label: "Turn right" },
    ],
  },
  {
    label: "Strafe",
    keys: [
      { key: "q", label: "Strafe left" },
      { key: "e", label: "Strafe right" },
    ],
  },
  {
    label: "Pitch",
    keys: [
      { key: "i", label: "Pitch up" },
      { key: "k", label: "Pitch down" },
    ],
  },
  {
    label: "Look",
    keys: [
      { key: "j", label: "Look left" },
      { key: "l", label: "Look right" },
    ],
  },
]

let context = null
let initialScene = null
let initialSceneLocked = false
let promptEdited = false
let textEventsEdited = false
let firstFrameUrlEdited = false
let firstFrameInputMode = "url"
let selectedFirstFrameFile = null
let selectedFirstFrameUrl = null
let firstFrameSelectionCommitted = false
let activeEventId = null
let textEventDrafts = []
let textEventSequence = 0

let preview = null
let sceneCard = null
let presetSelect = null
let savePresetButton = null
let firstFrameSourceRow = null
let uploadModeButton = null
let urlModeButton = null
let firstFrameInput = null
let firstFrameUrlInput = null
let firstFrameUrlUpdateButton = null
let firstFrameUrlStatus = null
let firstFrameName = null
let promptInput = null
let textEventList = null
let addTextEventButton = null
let eventControls = null
let eventButtons = null
let clearEventButton = null
let livePromptInput = null
let livePromptSubmitButton = null
let directorButtons = null
let controlsModeToggle = null
let enableDirectorModeButton = null
let playerPromptGroup = null
// The shared movement key grid (w/a/s/d/q/e/i/j/k/l) lives outside our own
// panel in the shared page, addressable by its fixed id -- hidden while
// the Director tab is active since a director doesn't drive movement.
const movementControlRows = document.getElementById("controlRows")
// The shared panel's own heading text, also addressable by a fixed id --
// swapped between "Player Controls" / "Director Controls" to match
// whichever mode is active.
const controlsPanelTitleText = document.getElementById("controlsPanelTitleText")
let healthBar = null
let healthBarFill = null
let healthBarValue = null
let healthBarLabelText = null
// Purely a client-side cosmetic HUD -- the server/runtime has no concept of
// health, this just tracks event `health` deltas locally (matching the
// original REACTOR case files' HUD) so the presets feel game-like.
let currentHealth = 100
let maxHealth = 100
let directorPromptGroup = null
let directorPromptInput = null
let directorPromptSubmitButton = null
// Landing on the page with ?director already set jumps straight to the
// Director Controls view (Player Controls hidden) instead of requiring an
// extra click on the toggle button.
let showingDirectorControls = directorMode
let currentPreset = null

function makeSceneCard() {
  const panel = document.createElement("section")
  panel.className = "sceneCard overlayPanel"
  panel.setAttribute("aria-label", "Initial Scene")
  panel.innerHTML = `
    <span class="panelLabel">Initial Scene</span>
    <div class="presetsControl">
      <label for="scenePresetsSelect">Quick Start</label>
      <div class="presetsRow">
        <select id="scenePresetsSelect">
          <option value="">-- Choose a preset --</option>
          ${scenePresets.map((p, i) => `<option value="${i}">${p.name}</option>`).join("")}
        </select>
        <button class="savePresetButton" type="button">Save</button>
      </div>
    </div>
    <div class="firstFrameSourceRow" data-mode="url">
      <div class="sourcePane sourcePaneUpload">
        <button class="sourceModeButton uploadModeButton" type="button">Upload</button>
        <label class="uploadControl">
          <input class="firstFrameInput" type="file" accept="image/*">
          <span class="firstFrameName">Choose Image</span>
        </label>
      </div>
      <div class="sourcePane sourcePaneUrl">
        <button class="sourceModeButton urlModeButton" type="button">URL</button>
        <div class="urlControl">
          <label>Image URL</label>
          <input class="firstFrameUrlInput" type="url" inputmode="url" autocomplete="off">
        </div>
      </div>
      <button class="urlUpdateButton" type="button">Update</button>
    </div>
    <div class="firstFrameUpdateRow">
      <span class="fieldStatus" role="status" hidden></span>
    </div>
    <div class="promptControlGroup">
      <label class="promptControl">
        <span>Prompt</span>
        <textarea rows="4" maxlength="2000"></textarea>
      </label>
      <button class="promptSubmitButton" type="button">Send</button>
    </div>
    <div class="textEventEditor">
      <div class="textEventHeader">
        <span>Text Events</span>
        <button class="textEventAddButton" type="button">Add</button>
      </div>
      <div class="textEventList"></div>
    </div>
  `
  return panel
}

function makeEventControls() {
  const root = document.createElement("div")
  root.className = "eventControls"
  root.hidden = true
  root.innerHTML = `
    <div class="healthBar">
      <div class="healthBarLabel">
        <span class="healthBarLabelText">Health</span>
        <span class="healthBarValue">100/100</span>
      </div>
      <div class="healthBarTrack"><div class="healthBarFill"></div></div>
    </div>
    <button class="controlsModeToggle" type="button" role="switch" aria-checked="false" hidden>
      <span class="controlsModeToggleTrack"><span class="controlsModeToggleKnob"></span></span>
      <span class="controlsModeToggleLabel">Director Mode</span>
    </button>
    <div class="eventButtons"></div>
    <div class="eventButtons directorButtons" hidden></div>
    <button class="eventButton eventButtonClear" type="button">Clear (C)</button>
    <button class="enableDirectorModeButton" type="button" hidden>Enable Director Mode</button>
    <div class="promptControlGroup playerPromptGroup">
      <label class="promptControl">
        <span>Custom Prompt</span>
        <input type="text" maxlength="2000">
      </label>
      <button class="promptSubmitButton" type="button">Send</button>
    </div>
    <div class="promptControlGroup directorPromptGroup" hidden>
      <label class="promptControl">
        <span>Director Prompt</span>
        <input type="text" maxlength="2000">
      </label>
      <button class="promptSubmitButton" type="button">Send</button>
    </div>
  `
  return root
}

function bindElements() {
  presetSelect = sceneCard.querySelector("#scenePresetsSelect")
  savePresetButton = sceneCard.querySelector(".savePresetButton")
  firstFrameSourceRow = sceneCard.querySelector(".firstFrameSourceRow")
  uploadModeButton = sceneCard.querySelector(".uploadModeButton")
  urlModeButton = sceneCard.querySelector(".urlModeButton")
  firstFrameInput = sceneCard.querySelector(".firstFrameInput")
  firstFrameUrlInput = sceneCard.querySelector(".firstFrameUrlInput")
  firstFrameUrlUpdateButton = sceneCard.querySelector(".urlUpdateButton")
  firstFrameUrlStatus = sceneCard.querySelector(".fieldStatus")
  firstFrameName = sceneCard.querySelector(".firstFrameName")
  promptInput = sceneCard.querySelector(".promptControl textarea")
  textEventList = sceneCard.querySelector(".textEventList")
  addTextEventButton = sceneCard.querySelector(".textEventAddButton")
  eventButtons = eventControls.querySelector(".eventButtons")
  clearEventButton = eventControls.querySelector(".eventButtonClear")
  directorButtons = eventControls.querySelector(".directorButtons")
  controlsModeToggle = eventControls.querySelector(".controlsModeToggle")
  enableDirectorModeButton = eventControls.querySelector(".enableDirectorModeButton")
  playerPromptGroup = eventControls.querySelector(".playerPromptGroup")
  healthBar = eventControls.querySelector(".healthBar")
  healthBarFill = eventControls.querySelector(".healthBarFill")
  healthBarValue = eventControls.querySelector(".healthBarValue")
  healthBarLabelText = eventControls.querySelector(".healthBarLabelText")
  livePromptInput = eventControls.querySelector(".playerPromptGroup .promptControl input")
  livePromptSubmitButton = eventControls.querySelector(".playerPromptGroup .promptSubmitButton")
  directorPromptGroup = eventControls.querySelector(".directorPromptGroup")
  directorPromptInput = eventControls.querySelector(".directorPromptGroup .promptControl input")
  directorPromptSubmitButton = eventControls.querySelector(".directorPromptGroup .promptSubmitButton")
}

function makeTextEventId(label = "") {
  const slug = String(label)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48)
  textEventSequence += 1
  return `${slug || "event"}-${textEventSequence}`
}

function makeTextEventDraft(item = {}) {
  const label = String(item.label || "").trim()
  return {
    event_id: String(item.event_id || item.id || "").trim() || makeTextEventId(label),
    label,
    prompt: String(item.prompt || "").trim(),
  }
}

function setFirstFrameInputMode(mode) {
  if (mode !== "upload" && mode !== "url") {
    return
  }
  firstFrameInputMode = mode
  firstFrameSourceRow.dataset.mode = mode
  uploadModeButton.setAttribute("aria-pressed", mode === "upload" ? "true" : "false")
  urlModeButton.setAttribute("aria-pressed", mode === "url" ? "true" : "false")
}

function setFirstFrameStatus(message = "", state = "idle") {
  firstFrameUrlStatus.textContent = message
  firstFrameUrlStatus.hidden = !message
  firstFrameUrlStatus.dataset.state = state
}

function defaultFirstFrameName() {
  return initialScene?.has_first_frame ? "Example Image" : "Choose Image"
}

function clearSelectedFile() {
  selectedFirstFrameFile = null
  firstFrameSelectionCommitted = false
  firstFrameInput.value = ""
  if (selectedFirstFrameUrl) {
    URL.revokeObjectURL(selectedFirstFrameUrl)
    selectedFirstFrameUrl = null
  }
}

function updatePreview() {
  const selected = selectedFirstFrameUrl && firstFrameSelectionCommitted
  // A picked preset (or manually typed URL) that hasn't been pushed to the
  // server yet via "Update" -- must take priority over the server's own
  // default first-frame endpoint below, otherwise applyInitialScene()'s
  // unconditional updatePreview() call stomps the just-applied preset
  // image back to the server default on every load/re-fetch.
  const pendingUrl = firstFrameUrlEdited && firstFrameUrlInput.value.trim()
  const initial = initialScene?.has_first_frame && initialScene?.first_frame_url
  if (selected) {
    preview.src = selectedFirstFrameUrl
  } else if (pendingUrl) {
    preview.src = pendingUrl
  } else if (initial) {
    const separator = initialScene.first_frame_url.includes("?") ? "&" : "?"
    preview.src = `${initialScene.first_frame_url}${separator}t=${Date.now()}`
  }
  document.body.classList.toggle(
    "is-ready-preview",
    !context.isVideoVisible() && Boolean(selected || pendingUrl || initial),
  )
}

function setSessionLocked(locked) {
  initialSceneLocked = locked
  sceneCard.hidden = locked
  for (const input of sceneCard.querySelectorAll("input, textarea, button")) {
    input.disabled = locked
  }
}

function renderTextEventEditor() {
  textEventList.replaceChildren()
  for (const [index, draft] of textEventDrafts.entries()) {
    const row = document.createElement("div")
    row.className = "textEventRow"
    const fields = document.createElement("div")
    fields.className = "textEventFields"
    const label = document.createElement("input")
    label.className = "textEventLabel"
    label.maxLength = 64
    label.placeholder = "Label"
    label.value = draft.label
    const prompt = document.createElement("textarea")
    prompt.className = "textEventPrompt"
    prompt.rows = 2
    prompt.maxLength = 1000
    prompt.placeholder = "Event prompt"
    prompt.value = draft.prompt
    const remove = document.createElement("button")
    remove.className = "textEventRemoveButton"
    remove.type = "button"
    remove.textContent = "X"
    remove.setAttribute("aria-label", `Remove text event ${index + 1}`)
    for (const input of [label, prompt]) {
      input.disabled = initialSceneLocked
      input.addEventListener("focus", context.releaseControls)
    }
    label.addEventListener("input", () => {
      draft.label = label.value
      textEventsEdited = true
    })
    prompt.addEventListener("input", () => {
      draft.prompt = prompt.value
      textEventsEdited = true
    })
    remove.disabled = initialSceneLocked
    remove.addEventListener("click", () => {
      textEventDrafts.splice(index, 1)
      textEventsEdited = true
      renderTextEventEditor()
    })
    fields.append(label, prompt)
    row.append(fields, remove)
    textEventList.append(row)
  }
}

function collectTextEvents() {
  const events = []
  const usedIds = new Set()
  for (const draft of textEventDrafts) {
    const label = draft.label.trim()
    const prompt = draft.prompt.trim()
    if (!label && !prompt) {
      continue
    }
    if (!prompt) {
      throw new Error("Each text event needs a prompt.")
    }
    let eventId = String(draft.event_id || "").trim() || makeTextEventId(label)
    while (usedIds.has(eventId)) {
      eventId = makeTextEventId(label)
    }
    draft.event_id = eventId
    usedIds.add(eventId)
    events.push({ event_id: eventId, label: label || eventId, prompt, category: "custom" })
  }
  return events
}

let eventHotkeyMap = new Map()

function getEventHealthDelta(eventId) {
  // Looked up from currentPreset's own definitions (not the transient
  // render catalog) so it still works once connected, after the server's
  // echoed event_catalog -- which has no health field -- takes over as the
  // render source.
  const fromPlayer = currentPreset?.events?.find((item) => item.event_id === eventId)
  const fromDirector = currentPreset?.directorEvents?.find((item) => item.event_id === eventId)
  const health = (fromPlayer ?? fromDirector)?.health
  return Number.isFinite(health) ? health : 0
}

function resetHealth(preset) {
  maxHealth = Number(preset?.hud?.maxHealth) || 100
  currentHealth = maxHealth
  if (healthBarLabelText) healthBarLabelText.textContent = preset?.hud?.healthLabel || "Health"
  renderHealthBar()
}

function renderHealthBar() {
  if (!healthBarFill) return
  const pct = maxHealth > 0 ? Math.max(0, Math.min(100, (currentHealth / maxHealth) * 100)) : 0
  healthBarFill.style.width = `${pct}%`
  healthBarFill.classList.toggle("is-low", pct <= 25)
  healthBarValue.textContent = `${Math.round(currentHealth)}/${Math.round(maxHealth)}`
}

function applyHealthDelta(delta) {
  if (!Number.isFinite(delta) || delta === 0) return
  currentHealth = Math.max(0, Math.min(maxHealth, currentHealth + delta))
  renderHealthBar()
}

function isDirectorEventId(eventId) {
  return Boolean(currentPreset?.directorEvents?.some((item) => item.event_id === eventId))
}

function makeEventButton(item, hotkeyLetter) {
  const eventId = String(item.event_id || "").trim()
  if (!eventId) return null
  const label = String(item.label || eventId)
  const button = document.createElement("button")
  button.className = "eventButton"
  button.type = "button"
  button.textContent = hotkeyLetter ? `${label} (${hotkeyLetter.toUpperCase()})` : label
  button.classList.toggle("is-active", activeEventId === eventId)
  button.addEventListener("click", () => sendTextEvent(eventId, "trigger"))
  return button
}

function renderEventControls() {
  // A picked preset's events (textEventDrafts, not yet pushed to the
  // server via connect/Send) must take priority over the server's last-
  // known event_catalog -- otherwise applyInitialScene()'s unconditional
  // call here stomps the just-applied preset's events back to whatever
  // the server currently has (its default catalog on first load).
  const catalog = textEventsEdited
    ? textEventDrafts
    : Array.isArray(initialScene?.event_catalog) ? initialScene.event_catalog : []
  const playerItems = catalog.filter((item) => !isDirectorEventId(item.event_id))
  const directorItems = catalog.filter((item) => isDirectorEventId(item.event_id))

  // Letter hotkeys are assigned sequentially across BOTH panels together
  // (player first, then director) so a letter never maps to two different
  // events even when both panels are visible at once. Events past the
  // pool size still render, just without a hotkey.
  eventHotkeyMap = new Map()
  let letterIndex = 0
  const nextLetter = () => EVENT_HOTKEY_LETTERS[letterIndex++] ?? null

  eventButtons.replaceChildren()
  for (const item of playerItems) {
    const letter = nextLetter()
    const button = makeEventButton(item, letter)
    if (!button) continue
    if (letter) eventHotkeyMap.set(letter, String(item.event_id).trim())
    eventButtons.append(button)
  }
  clearEventButton.classList.toggle("is-active", activeEventId === null)

  directorButtons.replaceChildren()
  for (const item of directorItems) {
    const letter = nextLetter()
    const button = makeEventButton(item, letter)
    if (!button) continue
    if (letter) eventHotkeyMap.set(letter, String(item.event_id).trim())
    directorButtons.append(button)
  }

  // In director mode, Player and Director share one panel with a single
  // toggle switch on top swapping which button grid (and which
  // custom-prompt box) is visible -- otherwise (the common case) it's just
  // Player Controls with no toggle at all. When director mode isn't on yet
  // but this preset actually has director events, offer "Enable Director
  // Mode" instead of requiring a URL edit.
  const hasDirectorContent = directorMode && directorItems.length > 0
  enableDirectorModeButton.hidden = directorMode || directorItems.length === 0
  controlsModeToggle.hidden = !hasDirectorContent
  if (!hasDirectorContent) showingDirectorControls = false
  const showDirector = hasDirectorContent && showingDirectorControls
  controlsModeToggle.classList.toggle("is-on", showDirector)
  controlsModeToggle.setAttribute("aria-checked", String(showDirector))
  controlsPanelTitleText.textContent = showDirector ? "Director Controls" : "Player Controls"
  eventButtons.hidden = showDirector
  directorButtons.hidden = !showDirector
  directorPromptGroup.hidden = !showDirector
  playerPromptGroup.hidden = showDirector
  if (movementControlRows) movementControlRows.hidden = showDirector
  if (healthBar) healthBar.hidden = showDirector
  eventControls.hidden = playerItems.length === 0 && directorItems.length === 0
}

function enableDirectorMode() {
  directorMode = true
  showingDirectorControls = true
  const url = new URL(window.location.href)
  url.searchParams.set("director", "")
  window.history.replaceState(null, "", url)
  renderEventControls()
}

function setDirectorView(showDirector) {
  showingDirectorControls = showDirector
  renderEventControls()
}

function saveCurrentPreset() {
  const name = prompt("Preset name:", "My Scene").trim()
  if (!name) return
  const preset = {
    name,
    prompt: promptInput.value.trim(),
    events: textEventDrafts.map(d => ({ event_id: d.event_id, label: d.label, prompt: d.prompt }))
  }
  scenePresets.push(preset)
  localStorage.setItem("lingbot-presets", JSON.stringify(scenePresets))
  updatePresetDropdown()
  alert(`Preset "${name}" saved!`)
}

function updatePresetDropdown() {
  presetSelect.innerHTML = `
    <option value="">-- Choose a preset --</option>
    ${scenePresets.map((p, i) => `<option value="${i}">${p.name}</option>`).join("")}
  `
}

function loadSavedPresets() {
  try {
    const saved = localStorage.getItem("lingbot-presets")
    if (saved) {
      const customPresets = JSON.parse(saved)
      scenePresets.push(...customPresets)
    }
  } catch (err) {
    console.error("Failed to load saved presets:", err)
  }
}

function applyPreset(presetIndex) {
  const preset = scenePresets[Number(presetIndex)]
  if (!preset) return
  currentPreset = preset
  resetHealth(preset)
  context.logEvent(`preset selected: ${preset.name}`, { source: "client" })
  // Server hard cap (session.py: _MAX_TEXT_EVENTS). Catch an over-budget
  // preset here, at selection time, instead of only discovering it via a
  // failed connect attempt later.
  const totalEventCount = preset.events.length + (preset.directorEvents?.length ?? 0)
  if (totalEventCount > 12) {
    context.logEvent(
      `preset "${preset.name}" has ${totalEventCount} events (player + director combined), `
        + "over the server's 12-event limit -- connecting will fail until it's trimmed.",
      { source: "client", level: "error" },
    )
  }
  const url = new URL(window.location.href)
  url.searchParams.set("preset", presetSlug(preset.name))
  window.history.replaceState(null, "", url)
  promptInput.value = preset.prompt
  promptEdited = true
  // The full catalog (player + director) always uploads to the server --
  // "director" is a client-side UI distinction only (which panel a button
  // renders in, and whether that panel is visible at all), the shared
  // WebRTC protocol has no such concept, so both must be known server-side
  // for either panel's buttons to actually do anything once clicked.
  textEventDrafts = [...preset.events, ...(preset.directorEvents ?? [])].map((item) =>
    makeTextEventDraft(item)
  )
  textEventsEdited = true
  renderTextEventEditor()
  // Also refresh the live Player Controls buttons immediately, not just
  // the editable Text Events list -- otherwise switching games mid-session
  // only updates on the next connect/upload, not on selection itself.
  renderEventControls()
  if (preset.image) {
    clearSelectedFile()
    setFirstFrameInputMode("url")
    firstFrameUrlInput.value = preset.image
    firstFrameUrlEdited = true
    firstFrameName.textContent = "Upload Image"
    setFirstFrameStatus("URL not updated", "pending")
    // Show the preset's image immediately, ahead of the "Update" commit
    // step -- picking a preset should visibly change the panel, not just
    // silently populate the URL field.
    preview.src = preset.image
    document.body.classList.toggle("is-ready-preview", !context.isVideoVisible())
  }
  context.releaseControls()
}

function applyInitialScene(scene) {
  initialScene = scene
  if (!promptEdited && typeof scene.prompt === "string") {
    promptInput.value = scene.prompt
  }
  const imageUrl = typeof scene.image_url === "string"
    ? scene.image_url
    : (typeof scene.default_image_url === "string" ? scene.default_image_url : "")
  if (!selectedFirstFrameFile && !firstFrameUrlEdited && imageUrl) {
    firstFrameUrlInput.value = imageUrl
    setFirstFrameInputMode("url")
  }
  firstFrameName.textContent = firstFrameUrlInput.value.trim() ? "Upload Image" : defaultFirstFrameName()
  activeEventId = scene.active_event_id || null
  if (!textEventsEdited) {
    textEventDrafts = Array.isArray(scene.event_catalog)
      ? scene.event_catalog.map((item) => makeTextEventDraft(item))
      : []
    renderTextEventEditor()
  }
  renderEventControls()
  context.setModelName(scene.model || "Lingbot")
  applyVideoSizing(scene.resolution)
  context.setResolution(scene.resolution?.width, scene.resolution?.height)
  updatePreview()
}

function applyVideoSizing(resolution) {
  const width = Number(resolution?.width)
  const height = Number(resolution?.height)
  if (
    !Number.isFinite(width) ||
    !Number.isFinite(height) ||
    width <= 0 ||
    height <= 0
  ) {
    return
  }
  const style = document.documentElement.style
  style.setProperty("--lingbot-video-width", `${width}px`)
  style.setProperty("--lingbot-video-height", `${height}px`)
  style.setProperty("--lingbot-video-width-from-vh", `${(width / height) * 100}vh`)
  style.setProperty("--lingbot-video-aspect", `${width} / ${height}`)
}

function mockInitialScene() {
  return {
    prompt: "Drive through a cinematic city street at sunset.",
    has_first_frame: false,
    model: "Lingbot",
    resolution: { width: 832, height: 464 },
    event_catalog: [
      { event_id: "portal", label: "Portal", prompt: "A luminous portal opens." },
      { event_id: "storm", label: "Storm", prompt: "A dramatic storm rolls in." },
    ],
  }
}

async function loadInitialScene() {
  if (mockMode) {
    applyInitialScene(mockInitialScene())
    return
  }
  const response = await fetch("/api/session/initial_scene")
  if (!response.ok) {
    throw new Error(`initial scene failed (${response.status})`)
  }
  applyInitialScene(await response.json())
}

function validateImageUrl(value) {
  const imageUrl = value.trim()
  let parsed = null
  try {
    parsed = new URL(imageUrl)
  } catch {
    throw new Error("Enter a valid http(s) image URL.")
  }
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("Enter a valid http(s) image URL.")
  }
  return imageUrl
}

async function uploadSessionInput({ includeFirstFrame = false } = {}) {
  const prompt = promptInput.value.trim()
  const hasPrompt = promptEdited && Boolean(prompt)
  const hasFile = includeFirstFrame && firstFrameInputMode === "upload" && selectedFirstFrameFile
  let imageUrl = firstFrameUrlInput.value.trim()
  const hasUrl = includeFirstFrame && firstFrameInputMode === "url" && Boolean(imageUrl)
  const textEvents = textEventsEdited ? collectTextEvents() : null
  if (!hasPrompt && !hasFile && !hasUrl && textEvents === null) {
    return
  }
  if (hasUrl) {
    imageUrl = validateImageUrl(imageUrl)
  }
  if (mockMode) {
    applyInitialScene({
      ...mockInitialScene(),
      prompt: hasPrompt ? prompt : initialScene.prompt,
      event_catalog: textEvents ?? initialScene.event_catalog,
      active_event_id: activeEventId,
    })
  } else {
    const form = new FormData()
    if (hasPrompt) form.append("prompt", prompt)
    if (hasFile) form.append("image", selectedFirstFrameFile, selectedFirstFrameFile.name)
    if (hasUrl) form.append("image_url", imageUrl)
    if (textEvents !== null) form.append("text_events", JSON.stringify(textEvents))
    const response = await fetch("/api/session/input", { method: "POST", body: form })
    if (!response.ok) {
      const text = (await response.text()).trim().replace(/^\d+:\s*/, "")
      throw new Error(text || `input upload failed (${response.status})`)
    }
    applyInitialScene(await response.json())
  }
  promptEdited = false
  textEventsEdited = false
  firstFrameUrlEdited = false
}

async function updateFirstFrame() {
  if (initialSceneLocked) return
  try {
    if (firstFrameInputMode === "upload" && !selectedFirstFrameFile) {
      throw new Error("Choose an image file.")
    }
    if (firstFrameInputMode === "url") {
      firstFrameUrlInput.value = validateImageUrl(firstFrameUrlInput.value)
      clearSelectedFile()
    }
    setFirstFrameStatus("Updating...", "pending")
    firstFrameUrlUpdateButton.disabled = true
    await uploadSessionInput({ includeFirstFrame: true })
    firstFrameSelectionCommitted = true
    setFirstFrameStatus("Updated", "success")
    updatePreview()
  } catch (error) {
    setFirstFrameStatus(error.message, "error")
    context.logEvent(`first frame update failed: ${error.message}`, { source: "client", level: "error" })
  } finally {
    firstFrameUrlUpdateButton.disabled = initialSceneLocked
  }
}

function sendTextEvent(eventId, state, promptValue = null) {
  const label = state === "clear" ? "clear event" : `event:${eventId}`
  const payload = { type: "event", event_id: eventId, state }
  if (promptValue !== null) {
    payload.prompt = promptValue
  }
  if (!context.sendCommand(payload, label)) {
    return
  }
  if (state === "trigger") applyHealthDelta(getEventHealthDelta(eventId))
  setSessionLocked(true)
}

function attachListeners() {
  presetSelect.addEventListener("change", (e) => {
    if (e.target.value) applyPreset(e.target.value)
  })
  // Letter keys trigger the matching event button (see the "(X)" hotkey
  // suffix rendered in renderEventControls() / eventHotkeyMap), "c"
  // triggers Clear (present on every game, not tied to any preset's
  // catalog) -- this only fires once controls are actually live, on
  // whichever of Player/Director Controls is currently shown.
  window.addEventListener("keydown", (event) => {
    if (event.ctrlKey || event.metaKey || event.altKey || event.repeat) return
    if (eventControls.hidden) return
    const activeTag = document.activeElement?.tagName
    if (activeTag === "INPUT" || activeTag === "TEXTAREA") return
    const key = event.key.toLowerCase()
    if (key === "c") {
      sendTextEvent(activeEventId || "clear", "clear")
      return
    }
    const eventId = eventHotkeyMap.get(key)
    if (eventId) sendTextEvent(eventId, "trigger")
  })
  controlsModeToggle.addEventListener("click", () => setDirectorView(!showingDirectorControls))
  enableDirectorModeButton.addEventListener("click", enableDirectorMode)
  savePresetButton.addEventListener("click", saveCurrentPreset)
  uploadModeButton.addEventListener("click", () => {
    setFirstFrameInputMode("upload")
    context.releaseControls()
  })
  urlModeButton.addEventListener("click", () => {
    setFirstFrameInputMode("url")
    context.releaseControls()
  })
  firstFrameInput.addEventListener("change", () => {
    setFirstFrameInputMode("upload")
    const [file] = firstFrameInput.files
    selectedFirstFrameFile = file || null
    firstFrameSelectionCommitted = false
    if (selectedFirstFrameUrl) URL.revokeObjectURL(selectedFirstFrameUrl)
    selectedFirstFrameUrl = selectedFirstFrameFile ? URL.createObjectURL(selectedFirstFrameFile) : null
    firstFrameName.textContent = selectedFirstFrameFile?.name || defaultFirstFrameName()
    firstFrameUrlInput.value = ""
    firstFrameUrlEdited = false
    setFirstFrameStatus(selectedFirstFrameFile ? "Image not updated" : "", "pending")
  })
  firstFrameUrlInput.addEventListener("input", () => {
    setFirstFrameInputMode("url")
    if (selectedFirstFrameFile) clearSelectedFile()
    firstFrameUrlEdited = true
    firstFrameName.textContent = firstFrameUrlInput.value.trim() ? "Upload Image" : defaultFirstFrameName()
    setFirstFrameStatus(firstFrameUrlInput.value.trim() ? "URL not updated" : "", "pending")
  })
  firstFrameUrlUpdateButton.addEventListener("click", () => void updateFirstFrame())
  promptInput.addEventListener("input", () => { promptEdited = true })
  const promptSubmitButton = sceneCard.querySelector(".promptSubmitButton")
  promptSubmitButton.addEventListener("click", () => {
    const promptText = promptInput.value.trim()
    if (promptText) {
      sendTextEvent("user_prompt", "trigger", promptText)
    }
  })
  addTextEventButton.addEventListener("click", () => {
    textEventDrafts.push(makeTextEventDraft())
    textEventsEdited = true
    renderTextEventEditor()
    context.releaseControls()
  })
  clearEventButton.addEventListener("click", () => sendTextEvent(activeEventId || "clear", "clear"))
  const submitLivePrompt = () => {
    const promptText = livePromptInput.value.trim()
    if (promptText) {
      sendTextEvent("user_prompt", "trigger", promptText)
    }
  }
  livePromptSubmitButton.addEventListener("click", submitLivePrompt)
  livePromptInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault()
      submitLivePrompt()
    }
  })
  const submitDirectorPrompt = () => {
    const promptText = directorPromptInput.value.trim()
    if (promptText) {
      sendTextEvent("user_prompt", "trigger", promptText)
    }
  }
  directorPromptSubmitButton.addEventListener("click", submitDirectorPrompt)
  directorPromptInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault()
      submitDirectorPrompt()
    }
  })
  for (const input of [firstFrameUrlInput, promptInput, addTextEventButton, livePromptInput, directorPromptInput]) {
    input.addEventListener("focus", context.releaseControls)
  }
}

export default {
  modelName: "Lingbot",
  stylesheet: new URL("./adapter.css?v=lingbot-video-size-v2", import.meta.url).href,
  controls,

  async mount(sharedContext) {
    context = sharedContext
    loadSavedPresets()
    preview = document.createElement("img")
    preview.className = "firstFramePreview"
    preview.alt = ""
    preview.setAttribute("aria-hidden", "true")
    sceneCard = makeSceneCard()
    eventControls = makeEventControls()
    context.slots.stage.append(preview)
    context.slots.panel.append(sceneCard)
    context.slots.controls.append(eventControls)
    bindElements()
    updatePresetDropdown()
    setFirstFrameInputMode("url")
    attachListeners()
    // ?preset=<slug> (e.g. "water-blaster") shares a direct link to a
    // specific game; falls back to index 0 ("Dragon") otherwise.
    const requestedPreset = new URLSearchParams(window.location.search).get("preset")
    const presetIndex = findPresetIndexBySlug(requestedPreset)
    const defaultPresetIndex = presetIndex >= 0 ? presetIndex : 0
    presetSelect.value = String(defaultPresetIndex)
    applyPreset(defaultPresetIndex)
    try {
      await loadInitialScene()
    } catch (error) {
      context.logEvent(`initial scene unavailable: ${error.message}`, { source: "client", level: "error" })
    }
  },

  async beforeConnect() {
    await uploadSessionInput({ includeFirstFrame: true })
  },

  onActionSent() {
    setSessionLocked(true)
    updatePreview()
  },

  onControlMessage(payload) {
    if (payload.type === "chunk_done" && Object.prototype.hasOwnProperty.call(payload, "active_event_id")) {
      activeEventId = payload.active_event_id || null
      renderEventControls()
      return false
    }
    if (payload.type === "event_ack") {
      activeEventId = payload.active_event_id || null
      renderEventControls()
      context.logEvent(`event ${payload.event_id} ${payload.state}`)
      return true
    }
    return false
  },

  onVideoVisibilityChanged() {
    updatePreview()
  },

  onDisconnect() {
    setSessionLocked(false)
    updatePreview()
  },
}
