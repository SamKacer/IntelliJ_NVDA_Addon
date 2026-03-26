# JetBrains IDEs — NVDA Addon

NVDA screen reader addon that adds full accessibility support for JetBrains IDEs.

> **This addon is a community fork of the original
> [IntelliJ NVDA Addon](https://github.com/SamKacer/IntelliJ_NVDA_Addon)
> by [Samuel Kacer](https://github.com/SamKacer).**
> The original addon supported IntelliJ IDEA only.
> This fork extends it to support all major JetBrains IDEs, fixes compatibility
> issues found in the original, and adds new features.

---

## Supported IDEs

| IDE | Process |
|---|---|
| IntelliJ IDEA | idea64.exe |
| PyCharm | pycharm64.exe |
| WebStorm | webstorm64.exe |
| GoLand | goland64.exe |
| Rider | rider64.exe |
| CLion | clion64.exe |

> Android Studio, DataGrip, and RubyMine are included in the supported process
> list and may work, but have not been fully tested in this beta.

---

## What's new in this fork

### Compatibility improvements (vs. original)
- **Multi-IDE support** — a single addon installation covers all JetBrains products.
  The original only supported IntelliJ IDEA 64-bit.
- **Locale-independent UI detection** — status bar and line number widget are now
  detected by role and content pattern (`line:col` regex), not by hardcoded
  English strings. Works on non-English IntelliJ installations.
- **More robust accessibility tree search** — replaced flat sibling walking with
  a BFS utility (`findObject`) with depth and node budgets.
  Handles structural changes between IntelliJ versions without extra code paths.
- **Filename detection without window title parsing** — now reads the active
  editor tab from the accessibility tree instead of splitting the window title
  on an em-dash character. More reliable across IntelliJ versions and project
  name formats.
- **Stale cache protection** — all cached accessibility objects are validated
  before use, preventing silent failures after tab switches or layout changes.
- **Event-driven status bar updates** — when IntelliJ's Java Access Bridge fires
  accessibility events, status changes are announced with zero polling latency.
  Polling is kept as a fallback for environments where events are not delivered.

### New features in this beta
- **AI autocomplete suggestion reading** — when an inline suggestion from
  GitHub Copilot, JetBrains AI Assistant, Tabnine, or any other inline AI
  coding assistant appears in the editor, NVDA can announce it.
  Two modes available, both configurable independently:
  - **Automatic mode** (off by default): NVDA reads the suggestion aloud
    approximately 800 ms after you stop typing, when Copilot's ghost text
    has had time to appear. Enable in NVDA Settings > JetBrains IDEs.
  - **On-demand mode** (always available): press **NVDA+Shift+A** at any
    time to hear the current suggestion without waiting.

---

## Current features

- When the caret moves to a different line, the line content at the new position
  is read out.
- When text selection changes, the new selection is read out.
- When the status bar text changes (e.g. a new error or warning is highlighted),
  NVDA announces it automatically.
  - Configurable: beep before/after reading, interrupt speech, enable/disable.
- **NVDA+I** — read the current status bar message on demand.
- **NVDA+Alt+L** — read the current line number and column.
- **NVDA+Shift+A** — read the current AI inline suggestion (GitHub Copilot,
  JetBrains AI, Tabnine). Works whenever ghost text is visible in the editor.
- Automatic AI suggestion reading — NVDA announces the suggestion ~800 ms after
  you stop typing. Disabled by default; enable in NVDA Settings > JetBrains IDEs.
- *(Experimental)* When the caret moves to a line that has a breakpoint set,
  NVDA beeps. Requires the Bookmarks panel to be open.
  Disabled by default. Can be enabled in NVDA Settings > JetBrains IDEs.

---

## How to install

1. Download the latest `.nvda-addon` file from the releases page.
2. Open the file — NVDA will prompt you to install it.
3. Click **Yes** and wait for NVDA to restart.

Or via the NVDA menu:
`NVDA+N` → Tools → Manage add-ons → Install → select the `.nvda-addon` file.

> **If you have the original IntelliJ NVDA Addon installed, remove it first**
> before installing this fork to avoid conflicts.

---

## Configuration

Open **NVDA Settings** (`NVDA+N` → Preferences → Settings) and navigate to
**JetBrains IDEs**. The following options are available:

| Option | Default | Description |
|---|---|---|
| Beep when status bar changes | Off | Short beep when a new message appears |
| Beep when status bar is cleared | Off | Short beep when the message disappears |
| Automatically read status bar changes | On | Speak the message as soon as it appears |
| Beep before reading the message | On | Tonal cue before the spoken message |
| Beep after reading the message | Off | Tonal cue after the spoken message |
| Interrupt speech when reading status changes | Off | Cancel any current speech before reading |
| (Experimental) Beep when breakpoint is on current line | Off | Requires Bookmarks panel open |
| Automatically read AI inline code suggestions | Off | Reads Copilot/AI suggestion ~800 ms after typing stops |

---

## Required setup: enabling status bar widgets

The status bar features (error reading, line number) require specific widgets
to be enabled in the JetBrains IDE status bar.

### Enable "status text" widget (for error/warning reading)

1. Double-tap **Shift** to open Search Everywhere.
2. Search for `Status Bar Widgets` and press **Enter**.
3. Find **status text** in the list.
4. Press **Space** to enable it. (The checkbox may not report its state audibly.)
5. Press **Escape** to close.
6. Test with **NVDA+I** while the caret is on an error line.

If `status text` does not appear in the list, try this alternative:
1. Open the **View** menu (`Alt+V`).
2. Go to **Appearance** > **Navigation Bar**.
3. Select any option other than **In Status Bar** (e.g. **Top** or **Don't Show**).
4. Retry reading with **NVDA+I**.

### Enable "Line:Column Number" widget (for line number reading)

1. Double-tap **Shift** to open Search Everywhere.
2. Search for `Status Bar Widgets` and press **Enter**.
3. Find **Line:Column Number** in the list.
4. Press **Space** to enable it.
5. Press **Escape** to close.
6. Test with **NVDA+Alt+L** while the caret is in the editor.

> Note: the breakpoint detection feature also requires the line number widget
> to be enabled.

---

## Keyboard shortcuts reference

### AI inline suggestions (GitHub Copilot, JetBrains AI, Tabnine)
| Key | Action |
|---|---|
| NVDA+Shift+A | Read current suggestion immediately (on-demand) |
| *(no default)* | Toggle automatic suggestion reading |
| Tab | Accept the current suggestion |
| Escape | Dismiss the current suggestion |
| Alt+] | Next suggestion |
| Alt+[ | Previous suggestion |

### Error and warning navigation
| Key | Action |
|---|---|
| F2 / Shift+F2 | Go to next / previous error or warning |
| NVDA+I | Read current status bar message (error description) |
| Ctrl+F1 | Open detailed error description popup |
| Alt+Enter | Open quick-fix action list |

### Line and position
| Key | Action |
|---|---|
| NVDA+Alt+L | Read current line number and column |
| Ctrl+G | Go to specific line number |
| Ctrl+Shift+Backspace | Go to last edit location |

### Editor navigation
| Key | Action |
|---|---|
| Ctrl+B | Go to declaration |
| Ctrl+Alt+Left / Right | Navigate back / forward |
| Alt+Up / Alt+Down | Jump to previous / next method or class |
| Ctrl+[ / Ctrl+] | Go to start / end of code block |
| F3 / Shift+F3 | Find next / previous occurrence |
| Ctrl+Shift+B | Go to type declaration |

### Selection
| Key | Action |
|---|---|
| Ctrl+W / Ctrl+Shift+W | Expand / shrink structural selection |
| Alt+Shift+J | Unselect last occurrence |

### Debugging
| Key | Action |
|---|---|
| F8 | Step over |
| F7 | Step into |
| Shift+F7 | Smart step into |
| Shift+F8 | Step out |
| F9 | Resume |
| Alt+F10 | Jump to current execution line |
| Ctrl+F8 | Toggle breakpoint |
| Ctrl+Shift+F8 | View all breakpoints |

### VCS
| Key | Action |
|---|---|
| Ctrl+K | Commit |
| Ctrl+Shift+K | Push |
| Ctrl+Alt+Z | Revert |

### General
| Key | Action |
|---|---|
| Shift, Shift | Search everywhere |
| Ctrl+Shift+A | Find action |
| Ctrl+Alt+L | Format code |
| Alt+F7 | Find usages |
| Ctrl+Tab | Switch between editors and views |
| Alt+[number] | Open numbered tool window |
| F12 | Return to last tool window |

---

## Known limitations (beta)

- The addon targets 64-bit JetBrains processes only (`*64.exe`).
  Legacy 32-bit installations (`idea.exe`, `pycharm.exe`) are not supported.
- The breakpoint detection feature requires the **Bookmarks** tool window to be
  open and visible. If the panel is closed, the beep will not fire.
- Breakpoint detection has only been tested with Java/Kotlin line breakpoints in
  IntelliJ IDEA. Behavior in other IDEs or with conditional breakpoints may vary.
- AI suggestion reading works when the suggestion text is exposed by IntelliJ's
  Java Access Bridge. With GitHub Copilot this is supported from IntelliJ 2023.1+.
  If `NVDA+Shift+A` returns "No AI suggestion available", ensure Copilot is active
  and a suggestion is visible (gray ghost text) before pressing the shortcut.
- This addon has been tested against NVDA 2025.3.2.
  Earlier NVDA versions back to 2022.1 should work but have not been tested
  in this fork.

---

## Building from source

Requirements: Python 3.x (no external dependencies needed for the build script).

```
python build.py
```

This produces `JetBrains-1.0-beta.nvda-addon` in the project root.

*(SCons is also supported if available: run `scons` in the project root.)*

---

## Credits

- **Samuel Kacer** — original [IntelliJ NVDA Addon](https://github.com/SamKacer/IntelliJ_NVDA_Addon)
  (versions 1.0 through 1.5.2). The core architecture, status bar monitoring,
  gesture handling, and settings panel are all based on his work.
- **Tim (@tbreitenfeldt)** — line number reading and breakpoint detection
  features (contributed to the original addon, version 1.5.0).
- **Thiago (@thgcode)** — automatic status bar change reading
  (contributed to the original addon, version 1.3.0).
- **Community fork contributors** — multi-IDE support, locale-independent
  detection, robustness improvements, and new features.

---

## License

GNU General Public License Version 2.
See [LICENSE.md](LICENSE.md) for full text.

---

## Changelog

### Version 1.0-beta (this release)
**This is a community fork of the original IntelliJ NVDA Addon.**

#### Compatibility improvements
- Added support for PyCharm, WebStorm, GoLand, Rider, and CLion in addition to
  IntelliJ IDEA. A single addon installation covers all JetBrains products.
- Status bar is now detected by accessibility role, not by the English string
  "Status Bar". Works on non-English IDE installations.
- Line number widget is now detected by content pattern (`line:col`) rather than
  the English tooltip "go to line".
- Filename extraction for breakpoint detection no longer relies on parsing the
  window title with an em-dash. Reads the selected editor tab instead.
- Cached accessibility objects are now validated before use, preventing stale
  reference errors after layout changes or tab switches.
- BFS tree search with depth and node budgets replaces flat sibling walking,
  making the addon resilient to structural changes between IDE versions.
- Added event-driven status bar updates as primary mechanism; polling demoted to
  a fallback with adaptive interval (250 ms without events, 2 s with events).
- Fixed: critical import error in stub files (`from .jetbrainsBase import` was
  incorrectly written as `from jetbrainsBase import`, causing the addon to fail
  to load entirely and produce no speech output).

#### New features
- **NVDA+Shift+A** — on-demand reading of the current AI inline suggestion.
  Works with GitHub Copilot, JetBrains AI Assistant, and Tabnine.
- **Automatic AI suggestion reading** — optional; disabled by default.
  When enabled, NVDA reads the suggestion aloud 800 ms after the caret stops
  moving, without requiring a keypress.
  Toggle via NVDA Settings > JetBrains IDEs or assign a gesture in Input Gestures.

#### Architecture
- Extracted all logic into a single base module (`jetbrainsBase.py`).
  Each IDE stub file (`idea64.py`, `pycharm64.py`, etc.) is now 4 lines.
- Keybindings split into three tiers:
  Tier 1 (universal), Tier 2 (IntelliJ/PyCharm default keymap),
  Tier 3 (debugger-specific).

---

*Previous versions (1.0 through 1.5.2) are from the original addon by Samuel Kacer.
See the [original repository](https://github.com/SamKacer/IntelliJ_NVDA_Addon) for that history.*
