# Handoff: BrightNode Car Counter — 5 Selectable UI Themes

## Overview
A theme system for the existing "Line-crossing vehicle counter" screen (Upload &amp; Process page of the BrightNode car-counting app). Same layout, copy, and controls as the current UI — five interchangeable visual themes, user-selectable at runtime, persisted across sessions.

## About the Design Files
The files in `reference/` are **design references built in HTML/CSS/JS** — they show intended look, states, and interaction, not code to paste verbatim into the app. Recreate this in the **existing Flask + Jinja + static CSS/JS stack**, following whatever templating/CSS conventions the app already uses (e.g. a shared `base.html`, existing `static/css` structure, existing JS bundling approach). If the app has no established front-end pattern yet, plain Jinja templates + a CSS-variable stylesheet + vanilla JS (as modeled in `reference/`) is a reasonable default.

- `reference/car-counter-app-reference.html` — fully interactive single-file prototype. Open directly in a browser. Every control works (sliders, orientation/speed toggles, file picker, theme switcher, simulated "Process video" run). Use it to see exact behavior and states.
- `reference/theme-tokens.css` — the 5 themes as CSS custom properties, scoped under `[data-theme="…"]` selectors. This is close to drop-in ready for a Flask static asset — copy into the project's stylesheet and reference the variables from existing markup/CSS.

## Fidelity
**High-fidelity.** Colors, type, spacing, radii, and copy are final for all 5 themes. Implement pixel-accurately; do not restyle.

## Themes
Theme switch value stored as one of: `midnight`, `studio`, `terracotta`, `amber`, `pastel` (matches `data-theme` attribute values in `theme-tokens.css`).

1. **Midnight Ops** (`midnight`) — dark, near-black surfaces, teal accent (`#2dd4bf`) for IN/active states, amber (`#f59e0b`) for OUT. Headers/body in Space Grotesk, data/labels in JetBrains Mono. 8–10px radii.
2. **Studio Light** (`studio`) — clean light SaaS look, white/near-white surfaces, indigo accent (`#4f46e5`). Sora for headers, system-ui for body. 8–12px radii, soft shadows on cards.
3. **Terracotta Editorial** (`terracotta`) — warm cream background, serif headers (Newsreader), terracotta accent (`#c1552c`) with olive-green IN color (`#6b7a4f`). 8px radii.
4. **Amber Industrial** (`amber`) — near-black utilitarian dashboard, amber accent (`#f5b31c`), red OUT color (`#e5484d`). IBM Plex Sans Condensed + IBM Plex Mono. **0px radii everywhere** (sharp corners) and a faint grid-line background texture behind the main content area.
5. **Soft Pastel** (`pastel`) — lavender/white background, purple accent (`#8b5cf6`), mint IN (`#0d9668`) / coral OUT (`#fb7185`). Quicksand throughout. Largest radii (12–18px), pill-shaped buttons/toggles.

All 5 share identical layout — only tokens (color, font, radius) and the subtle amber grid texture change.

## Screens / Views
### Upload & Process (primary screen — fully specified)
**Layout:** Full-height flex row: fixed 230px sidebar + flexible main content, both inside a full-viewport column with a theme-switcher bar on top.

**Theme switcher bar** (top, full width): row of 5 pill chips, one per theme, each with a small color dot (theme's accent) + theme name. Active chip: border in accent color, soft accent background, primary text color. Inactive: border in theme's neutral border color, transparent background, secondary text color. Click any chip → instantly re-themes the whole app and persists the choice (e.g. `localStorage`, or write to a user preference / session so Flask can render the right theme server-side on next load).

**Sidebar** (230px, fixed):
- "WORKSPACE" label (uppercase, mono font, muted, letter-spacing ~0.1em)
- 3 nav rows: "Upload & Process" (active by default), "Live Feed", "Job Archive". Active row: accent-soft background, accent text color, semibold. Inactive: transparent background, secondary text color, medium weight. Clicking a nav row swaps the main content to a themed placeholder (only "Upload & Process" has full functionality in this handoff — the other two need real screens built, but should reuse the same sidebar/theme shell).
- "RECENT JOBS" label + muted placeholder copy: "Processed videos will appear here." (swap in real job list once available)
- Spacer
- Footer brand block: small accent-colored logo swatch (or actual logo asset) + "BrightNode" wordmark (header font, bold) + "CAR COUNTING · VIDEO ANALYTICS" tagline (mono/small, muted, uppercase-ish tracking)

**Main content header:**
- Title: "Line-crossing vehicle counter" (header font, ~21px bold)
- Subtitle: "Upload traffic footage and the pipeline detects, tracks, and tallies every car, truck, and bus that crosses your counting line." (secondary text color, ~13px)
- Two stat chips top-right: **IN** (theme's in-color/in-bg/in-border) and **OUT** (theme's out-color/out-bg/out-border), each showing a label (9px, mono, tracked) and a live count (18px bold, mono)
- Status row below: "FRAME 0000" (left, mono, muted) / "● COUNTING LINE ACTIVE" (right, accent color) — frame counter should reflect real backend frame progress once wired to processing

**Two-panel grid** (`1.3fr / 1fr` columns, 18px gap):

**Panel 01 — Source video** (card: theme card background/border/radius, 20px padding):
- Section label "01" (small pill badge, accent-soft bg/accent text) + "Source video" heading
- Dropzone: dashed border box, "Drop a video or click to browse" + "MP4, MOV, AVI, MKV, WEBM" helper below. Click opens a native file picker; drag-and-drop should also be supported. On file selection, dropzone label switches to the filename.
- Two-column row: **Detection confidence** slider (0.00–1.00, default 0.40, live value shown top-right of label in accent color) and **Duration** slider (disabled/greyed until a file is chosen; once chosen, shows detected duration and becomes informational — helper text switches from "Select a video to set this." to the detected duration)
- **Counting line length** slider (10–100%, default 100%, live value shown) + helper: "Shorten the line to cover a single lane instead of the full frame width/height."
- **Counting line orientation** — two-button toggle group: Horizontal (default active) / Vertical. Active button: accent border/text, accent-soft background, bold. Inactive: neutral inactive tokens. Helper: "Line is drawn across the mid-width or mid-height of the frame."
- **Processing speed** — three-button toggle group: Faster / Balanced (default active) / Sharp, same active/inactive styling as orientation. Helper: "Faster processing; slightly less accurate on small or distant vehicles."

**Panel 02 — Result** (card, same styling, flex column):
- Section label "02" + "Result" heading
- Result area (dashed border box, flexes to fill available height) with three states:
  1. **Empty** (default): centered muted copy — "Processed footage and the crossing log will appear here once a job completes."
  2. **Processing**: small spinner (border-based, accent top segment, rotating) + "Processing video…"
  3. **Complete**: left-aligned "Job complete — {filename}" (bold) + a summary line: "{in} in · {out} out · confidence {value} · {speed} mode"
- **Process video** button: full-width, accent background, accent-text color, bold, theme's pill/button radius. Label switches to "Processing…" while running and is inert (no double-submit) during that state. On completion, wire this to the real backend job — the mock currently simulates ~1.4s then fills in random in/out counts.

**Footer strip** (full width, bottom of main content): small mono/muted line — "BRIGHTNODE / CAR-COUNTER-APP — POWERED BY YOLOV8 + BYTETRACK, SERVED LOCALLY" (update wording if the real pipeline differs).

### Live Feed / Job Archive
Only a placeholder ("This screen isn't wired up in the reference UI — same shell & theme apply here.") is specified — build these out as their own task; they should inherit the sidebar, theme switcher, and footer shell shown here.

## Interactions & Behavior
- **Theme switch**: click a theme chip → all tokens update immediately, no page reload. Persist selection (localStorage key `bn-theme` in the reference, or move to a server-rendered preference/cookie if themes should apply before first paint from Flask).
- **Sidebar nav**: click switches active page/content region; sidebar item highlight follows the active page.
- **Sliders**: standard native range inputs; update live value labels on input/change.
- **Orientation / speed toggles**: single-select button groups, click sets active state.
- **Dropzone**: click (and ideally drag-and-drop) opens file selection; selecting a file updates dropzone label and enables the Duration slider display.
- **Process video button**: click → button enters "Processing…" state (disabled from re-click), result panel shows spinner; on completion, shows the summary and updates IN/OUT counts in the header. Wire this whole flow to the real Flask endpoint that kicks off and polls/streams the video-processing job; the frontend states (empty/processing/complete) should map to real job status rather than the timer used in the mock.
- No responsive/mobile behavior specified — this is a desktop workspace UI in the source design.

## State Management
Suggested client state:
- `theme`: one of the 5 keys, persisted (localStorage and/or user profile setting)
- `activePage`: which sidebar section is showing
- `confidence` (float 0–1), `lineLength` (int %), `orientation` (horizontal/vertical), `speed` (faster/balanced/sharp) — these are job parameters, should be sent to the backend when the job is submitted
- `selectedFile` — chosen video file/reference, plus its detected duration once known
- `jobStatus` — idle / processing / complete / error, driven by the real backend job rather than a client timer
- `inCount` / `outCount` — should update from backend results, ideally live during processing if the pipeline streams frame-by-frame

## Design Tokens
All theme values are enumerated in `reference/theme-tokens.css` as CSS custom properties per theme (fonts, backgrounds, borders, text colors, accent + in/out colors, radii). Use those as the source of truth rather than re-deriving values from screenshots.

## Assets
No external image/icon assets used — the sidebar logo mark is a plain color swatch (swap for the real BrightNode logo asset if one exists). No emoji or icon fonts used anywhere in this design; keep it that way for consistency.

## Files
- `reference/car-counter-app-reference.html` — interactive prototype, open directly in any browser
- `reference/theme-tokens.css` — CSS variables for all 5 themes
