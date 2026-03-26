# JetBrains IDEs — NVDA Addon Base Module
# Supports: IntelliJ IDEA, PyCharm, WebStorm, GoLand, Rider, CLion, DataGrip, RubyMine, Android Studio
#
# Based on original work by Samuel Kacer <samuel.kacer@gmail.com>
# https://github.com/SamKacer/IntelliJ_NVDA_Addon
# GNU GENERAL PUBLIC LICENSE V2
#
# PHASE CHANGELOG
# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — Process generalization
#   • All logic moved from idea64.py into this shared base
#   • SUPPORTED_JETBRAINS_APPS frozenset replaces the single "idea64" check
#
# Phase 2 — UI detection refactor
#   • findObject() BFS utility with depth + node budget
#   • getStatusBar() uses role == STATUSBAR only (no English string match)
#
# Phase 3 — Line number detection
#   • getLineNumber() matches child.name against r'^\d+:\d+$'
#   • "go to line" description kept only as secondary hint
#
# Phase 4 — Remove window title dependency
#   • _getEditorFileName() prefers selected editor TAB from accessibility tree
#   • Window title parsing is a fallback only, uses regex (handles both orderings)
#
# Phase 5 — Breakpoints refactor
#   • _getBreakpointTree() uses TREEVIEW role + file:line item sampling
#   • hasBreakpointOnCurrentLine() is fully fault-tolerant (never raises)
#
# Phase 6 — Keybinding refactor
#   • Gestures split into TIER1 (universal), TIER2 (IntelliJ/PyCharm keymap),
#     TIER3 (debugger-specific)
#   • All tiers active by default for backward compatibility
#
# Phase 7 — Replace polling with event-driven updates
#   • AppModule.event_nameChange() fires immediately on status bar text change
#   • Polling demoted to fallback: 250 ms before events confirmed, 2 s after
#
# Phase 8 — Cache validation
#   • _isObjectValid() checks role + property access before trusting a cache
#   • _statusCache and _lineNumCache are validated on every access
# ─────────────────────────────────────────────────────────────────────────────

import re
import threading
import time
from dataclasses import dataclass
from winsound import PlaySound, SND_ASYNC, SND_ALIAS

import api
import appModuleHandler
import config
import controlTypes
import gui
import speech
import tones
import ui
import wx
from buildVersion import version_year
from core import callLater
from editableText import EditableTextWithoutAutoSelectDetection
from gui.settingsDialogs import SettingsPanel
from logHandler import log
from scriptHandler import script


# ── NVDA version compatibility ────────────────────────────────────────────────
# controlTypes changed from module-level constants to Role/State enums in 2022.
if version_year >= 2022:
    EDITABLE_TEXT  = controlTypes.Role.EDITABLETEXT
    STATUSBAR      = controlTypes.Role.STATUSBAR
    ROLE_TAB       = controlTypes.Role.TAB
    ROLE_TREEVIEW  = controlTypes.Role.TREEVIEW
    STATE_SELECTED = controlTypes.State.SELECTED
else:
    EDITABLE_TEXT  = controlTypes.ROLE_EDITABLETEXT
    STATUSBAR      = controlTypes.ROLE_STATUSBAR
    ROLE_TAB       = controlTypes.ROLE_TAB
    ROLE_TREEVIEW  = controlTypes.ROLE_TREEVIEW
    STATE_SELECTED = controlTypes.STATE_SELECTED


# ── Phase 1: Supported process names ─────────────────────────────────────────
# Any JetBrains product whose 64-bit process matches one of these names will
# activate the addon.  Adding a new IDE requires only a new thin stub file
# (e.g. goland64.py) plus adding the name here.
SUPPORTED_JETBRAINS_APPS = frozenset({
    "idea64",       # IntelliJ IDEA
    "pycharm64",    # PyCharm
    "webstorm64",   # WebStorm
    "goland64",     # GoLand
    "rider64",      # Rider
    "clion64",      # CLion
    "datagrip64",   # DataGrip
    "rubymine64",   # RubyMine
    "studio64",     # Android Studio
})


# ── Configuration keys & defaults ────────────────────────────────────────────
CONF_KEY                   = "intellij"
BEEP_ON_STATUS_CHANGED_KEY = "beepOnStatusChange"
BEEP_ON_STATUS_CLEARED_KEY = "beepOnStatusCleared"
SPEAK_ON_STATUS_CHANGED_KEY = "speakOnStatusChange"
INTERRUPT_SPEECH_KEY       = "interruptOnStatusChange"
BEEP_BEFORE_READING_KEY    = "beepBeforeReadingStatus"
BEEP_AFTER_READING_KEY     = "beepAfterReadingStatus"
BEEP_ON_BREAKPOINT_KEY     = "beepOnBreakpoint"
READ_AI_SUGGESTION_AUTO_KEY = "readAiSuggestionAuto"

_DEFAULTS = {
    BEEP_ON_STATUS_CHANGED_KEY:   False,
    BEEP_ON_STATUS_CLEARED_KEY:   False,
    SPEAK_ON_STATUS_CHANGED_KEY:  True,
    INTERRUPT_SPEECH_KEY:         False,
    BEEP_BEFORE_READING_KEY:      True,
    BEEP_AFTER_READING_KEY:       False,
    BEEP_ON_BREAKPOINT_KEY:       False,
    READ_AI_SUGGESTION_AUTO_KEY:  False,
}

config.conf.spec[CONF_KEY] = {
    k: f"boolean(default={v})" for k, v in _DEFAULTS.items()
}

if config.conf.get(CONF_KEY) is None:
    config.conf[CONF_KEY] = {}


# ── Runtime config shadow ─────────────────────────────────────────────────────
# Avoids repeated dict lookups in hot paths (watcher thread, caret events).
@dataclass
class _Vars:
    beepOnChange:         bool = _DEFAULTS[BEEP_ON_STATUS_CHANGED_KEY]
    beepOnClear:          bool = _DEFAULTS[BEEP_ON_STATUS_CLEARED_KEY]
    speakOnChange:        bool = _DEFAULTS[SPEAK_ON_STATUS_CHANGED_KEY]
    interruptSpeech:      bool = _DEFAULTS[INTERRUPT_SPEECH_KEY]
    beepBeforeReading:    bool = _DEFAULTS[BEEP_BEFORE_READING_KEY]
    beepAfterReading:     bool = _DEFAULTS[BEEP_AFTER_READING_KEY]
    beepOnBreakpoint:     bool = _DEFAULTS[BEEP_ON_BREAKPOINT_KEY]
    readAiSuggestionAuto: bool = _DEFAULTS[READ_AI_SUGGESTION_AUTO_KEY]

vars = _Vars()  # module-level singleton


def setGlobalVars():
    """Sync the runtime shadow from NVDA's persistent config."""
    conf = config.conf[CONF_KEY]
    vars.beepOnChange         = conf[BEEP_ON_STATUS_CHANGED_KEY]
    vars.beepOnClear          = conf[BEEP_ON_STATUS_CLEARED_KEY]
    vars.speakOnChange        = conf[SPEAK_ON_STATUS_CHANGED_KEY]
    vars.interruptSpeech      = conf[INTERRUPT_SPEECH_KEY]
    vars.beepBeforeReading    = conf[BEEP_BEFORE_READING_KEY]
    vars.beepAfterReading     = conf[BEEP_AFTER_READING_KEY]
    vars.beepOnBreakpoint     = conf[BEEP_ON_BREAKPOINT_KEY]
    vars.readAiSuggestionAuto = conf[READ_AI_SUGGESTION_AUTO_KEY]

setGlobalVars()


# ── Settings panel ────────────────────────────────────────────────────────────
class JetBrainsAddonSettings(SettingsPanel):
    title = "JetBrains IDEs"

    def makeSettings(self, settingsSizer):
        sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
        conf = config.conf[CONF_KEY]

        self.beepOnChange = sHelper.addItem(
            wx.CheckBox(self, label="Beep when status bar changes"))
        self.beepOnChange.SetValue(conf[BEEP_ON_STATUS_CHANGED_KEY])

        self.beepOnClear = sHelper.addItem(
            wx.CheckBox(self, label="Beep when status bar is cleared"))
        self.beepOnClear.SetValue(conf[BEEP_ON_STATUS_CLEARED_KEY])

        self.speakOnChange = sHelper.addItem(
            wx.CheckBox(self, label="Automatically read status bar changes"))
        self.speakOnChange.SetValue(conf[SPEAK_ON_STATUS_CHANGED_KEY])

        self.beepBeforeReading = sHelper.addItem(
            wx.CheckBox(self, label="Beep before status bar change is read"))
        self.beepBeforeReading.SetValue(conf[BEEP_BEFORE_READING_KEY])

        self.beepAfterReading = sHelper.addItem(
            wx.CheckBox(self, label="Beep after status bar change is read"))
        self.beepAfterReading.SetValue(conf[BEEP_AFTER_READING_KEY])

        self.interruptSpeech = sHelper.addItem(
            wx.CheckBox(self, label="Interrupt speech when automatically reading status bar changes"))
        self.interruptSpeech.SetValue(conf[INTERRUPT_SPEECH_KEY])

        self.beepOnBreakpoint = sHelper.addItem(
            wx.CheckBox(self, label="(Experimental) Beep when breakpoint is detected on current line"))
        self.beepOnBreakpoint.SetValue(conf[BEEP_ON_BREAKPOINT_KEY])

        self.readAiSuggestionAuto = sHelper.addItem(
            wx.CheckBox(self, label="Automatically read AI inline code suggestions (GitHub Copilot, JetBrains AI, Tabnine)"))
        self.readAiSuggestionAuto.SetValue(conf[READ_AI_SUGGESTION_AUTO_KEY])

    def onSave(self):
        conf = config.conf[CONF_KEY]
        conf[BEEP_ON_STATUS_CHANGED_KEY]   = self.beepOnChange.Value
        conf[BEEP_ON_STATUS_CLEARED_KEY]   = self.beepOnClear.Value
        conf[SPEAK_ON_STATUS_CHANGED_KEY]  = self.speakOnChange.Value
        conf[INTERRUPT_SPEECH_KEY]         = self.interruptSpeech.Value
        conf[BEEP_BEFORE_READING_KEY]      = self.beepBeforeReading.Value
        conf[BEEP_AFTER_READING_KEY]       = self.beepAfterReading.Value
        conf[BEEP_ON_BREAKPOINT_KEY]       = self.beepOnBreakpoint.Value
        conf[READ_AI_SUGGESTION_AUTO_KEY]  = self.readAiSuggestionAuto.Value
        setGlobalVars()


# ── Phase 2: BFS object search utility ───────────────────────────────────────
def findObject(root, predicate, maxDepth=8, maxNodes=200):
    """
    Breadth-first search over an NVDA accessibility tree.

    Parameters
    ----------
    root      : NVDAObject   Root node.  Its children are searched; root itself
                             is NOT tested.
    predicate : callable     Called with each NVDAObject.  Return True to accept.
    maxDepth  : int          Maximum depth below root to descend (default 8).
    maxNodes  : int          Maximum total nodes to visit (default 200).

    Returns
    -------
    NVDAObject or None
    """
    if root is None:
        return None

    # Queue entries: (object, depth)
    queue = []
    child = root.simpleFirstChild
    if child:
        queue.append((child, 1))

    visited = 0
    while queue:
        obj, depth = queue.pop(0)

        while obj is not None:
            if visited >= maxNodes:
                return None
            visited += 1

            try:
                if predicate(obj):
                    return obj
            except Exception:
                pass

            if depth < maxDepth:
                first_child = obj.simpleFirstChild
                if first_child is not None:
                    queue.append((first_child, depth + 1))

            obj = obj.simpleNext

    return None


# ── Phase 8: Cache validation helper ─────────────────────────────────────────
def _isObjectValid(obj, expectedRole=None):
    """
    Lightweight staleness check for a cached NVDAObject.

    Forces a property read to surface any COM/IAccessible errors.
    Returns False on any exception, or if the role has drifted from expected.
    """
    try:
        if obj is None:
            return False
        if expectedRole is not None and obj.role != expectedRole:
            return False
        _ = obj.name   # trigger COM call to detect stale reference
        return True
    except Exception:
        return False


# ── Phase 3 & 4: Compiled regexes ────────────────────────────────────────────
# Matches the IntelliJ "line:col" status widget content, e.g. "42:7"
_LINE_COL_RE = re.compile(r"^\d+:\d+$")

# Matches breakpoint item names like "Main.java:42" or "main.py:15"
_BREAKPOINT_ITEM_RE = re.compile(r".+:\d+")

# Phase 4: window title separator variants (em-dash U+2013, en-dash, plain hyphen)
_TITLE_SEP_RE = re.compile(r"\s[–—-]\s")

# Phase 4: a "word.extension" pattern that signals a filename
_FILENAME_EXT_RE = re.compile(r"[\w\-. ]+\.\w{1,10}$")


# ── Phase 3: Line/col widget predicate ───────────────────────────────────────
def _isLineColWidget(obj):
    """
    Return True if *obj* looks like the JetBrains line:column status widget.

    Primary:   obj.name matches r'^\d+:\d+$'   (locale-independent)
    Secondary: obj.description == "go to line"  (English fallback)
    """
    try:
        name = obj.name or ""
        if _LINE_COL_RE.match(name):
            return True
        desc = (obj.description or "").lower()
        if desc == "go to line":
            return True
    except Exception:
        pass
    return False


# ── Phase 4: Selected editor tab predicate ───────────────────────────────────
def _isSelectedEditorTab(obj):
    """
    Return True if *obj* is the currently selected editor tab.

    JetBrains IDE editor tabs have role=TAB and the SELECTED state when active.
    The tab name is the filename (e.g. "Main.java").
    """
    try:
        if obj.role != ROLE_TAB:
            return False
        return STATE_SELECTED in obj.states
    except Exception:
        return False


# ── Phase 5: Breakpoint tree predicate ───────────────────────────────────────
def _isBreakpointTree(obj):
    """
    Return True if *obj* is a TREEVIEW that contains breakpoint-like items.

    Heuristic: sample up to 5 categories × 10 sub-items looking for any item
    whose name matches the 'filename:lineNumber' pattern.  This avoids matching
    the project file tree, structure tree, or other TREEVIEW objects.

    Max nodes sampled: 50.  Never raises.
    """
    try:
        if obj.role != ROLE_TREEVIEW:
            return False
        category = obj.simpleFirstChild
        cat_count = 0
        while category and cat_count < 5:
            sub = category.simpleFirstChild
            sub_count = 0
            while sub and sub_count < 10:
                if _BREAKPOINT_ITEM_RE.search(sub.name or ""):
                    return True
                sub = sub.simpleNext
                sub_count += 1
            category = category.simpleNext
            cat_count += 1
    except Exception:
        pass
    return False


# ── Phase 4: Window title filename fallback ───────────────────────────────────
def _filenameFromWindowTitle(windowText):
    """
    Best-effort filename extraction from a JetBrains window title.

    Handles both orderings:
      "ProjectName – FileName.java"
      "FileName.java – ProjectName"
    and both em-dash and en-dash separators.

    Returns None if no recognisable filename is found.
    """
    if not windowText:
        return None
    parts = _TITLE_SEP_RE.split(windowText)
    for part in parts:
        part = part.strip()
        if _FILENAME_EXT_RE.match(part):
            return part
    return None


# ── Phase 6: Gesture tiers ────────────────────────────────────────────────────
#
# TIER 1 — Universal JetBrains shortcuts
#   Stable across IntelliJ, PyCharm, WebStorm, GoLand, Rider, CLion.
#   These shortcuts exist in every JetBrains default keymap with the same meaning.
#
TIER1_MOVE_BY_LINE = frozenset({
    "kb:f2",                      # Next highlighted error
    "kb:shift+f2",                # Previous highlighted error
    "kb:control+b",               # Go to declaration
    "kb:control+alt+leftArrow",   # Navigate back
    "kb:control+alt+rightArrow",  # Navigate forward
    "kb:control+shift+backspace", # Last edit location
    "kb:control+z",               # Undo (re-reads new caret position)
})

TIER1_SELECTION = frozenset({
    "kb:control+w",       # Extend selection (structural)
    "kb:control+shift+w", # Shrink selection (structural)
})

# TIER 2 — IntelliJ / PyCharm default keymap
#   Safe for IntelliJ and PyCharm users who have not customised their keymap.
#   May conflict on Rider (VS-inspired keymap) or custom keymaps.
#
TIER2_MOVE_BY_LINE = frozenset({
    "kb:alt+downArrow",           # Move statement down
    "kb:alt+upArrow",             # Move statement up
    "kb:control+[",               # Move to code block start
    "kb:control+]",               # Move to code block end
    "kb:f3",                      # Find next occurrence
    "kb:shift+f3",                # Find previous occurrence
    "kb:control+u",               # Go to super method/class
    "kb:control+/",               # Toggle line comment
    "kb:alt+j",                   # Add selection for next occurrence
    "kb:alt+control+downArrow",   # Clone caret below
    "kb:alt+control+upArrow",     # Clone caret above
    "kb:control+y",               # Delete line
})

TIER2_SELECTION = frozenset({
    "kb:alt+shift+j",        # Unselect last occurrence
    "kb:control+shift+[",    # Select to code block start
    "kb:control+shift+]",    # Select to code block end
})

# TIER 3 — Debugger-specific shortcuts (IntelliJ / PyCharm default keymap)
#   Only meaningful when the debugger is active.  Included by default for
#   backward compatibility; a future KeybindingManager can make them conditional.
#
TIER3_MOVE_BY_LINE = frozenset({
    "kb:f8",              # Step over
    "kb:alt+shift+f8",    # Force step over
    "kb:f7",              # Step into
    "kb:alt+shift+f7",    # Force step into
    "kb:shift+f7",        # Smart step into
    "kb:shift+f8",        # Step out
    "kb:alt+f10",         # Show execution point
})

# Combined defaults: all tiers active — preserves full backward compatibility
_ALL_MOVE_BY_LINE = TIER1_MOVE_BY_LINE | TIER2_MOVE_BY_LINE | TIER3_MOVE_BY_LINE
_ALL_SELECTION    = TIER1_SELECTION | TIER2_SELECTION


# ── AI suggestion helper ──────────────────────────────────────────────────────
def _readTextAfterCaret(obj):
    """
    Return the text from the current caret position to the end of the line.

    This is how GitHub Copilot (and other inline AI assistants) expose their
    suggestions via the Java Access Bridge: the suggestion text is appended to
    the editor's accessible text AFTER the caret position, on the same line.

    Returns the suggestion string, or None if there is no text after the caret.

    Note: if the cursor is placed in the middle of an existing line (not at the
    end of typed content), this function will also return that existing code.
    For best results use this when the cursor is at the end of what you typed.
    """
    try:
        import textInfos
        if obj is None or not hasattr(obj, "makeTextInfo"):
            return None
        # Anchor at caret
        caretInfo = obj.makeTextInfo(textInfos.POSITION_CARET)
        # Build a range: start = caret, end = end of current line
        afterCaret = caretInfo.copy()
        afterCaret.expand(textInfos.UNIT_LINE)        # expands both endpoints to full line
        afterCaret.setEndPoint(caretInfo, "startToStart")  # pull start back to caret
        text = afterCaret.text.rstrip("\r\n")
        return text if text.strip() else None
    except Exception:
        return None


# ── Editable text overlay ─────────────────────────────────────────────────────
class EnhancedEditableText(EditableTextWithoutAutoSelectDetection):
    """
    NVDAObject overlay applied to every EDITABLE_TEXT object in a JetBrains IDE.

    Responsibilities
    ----------------
    • Map JetBrains navigation/editing gestures to NVDA caret-movement events
      so NVDA speaks the new line after IntelliJ-specific key combos.
    • Play a system sound when the caret cannot move further (boundary).
    • Optionally beep when the caret lands on a line with a breakpoint.
    """

    # Phase 6: all tiers merged — individual tiers can be queried via TIER* constants
    __gestures = (
        {g: "caret_moveByLine"    for g in _ALL_MOVE_BY_LINE} |
        {g: "caret_changeSelection" for g in _ALL_SELECTION}
    )

    shouldFireCaretMovementFailedEvents = True

    def initOverlayClass(self):
        # Counter used to debounce AI suggestion checks.
        # Each caret event increments it; only the latest scheduled callback runs.
        self._aiCheckId = 0

    def event_caretMovementFailed(self, gesture):
        PlaySound("SystemExclamation", SND_ASYNC | SND_ALIAS)

    def event_caret(self):
        super().event_caret()
        if vars.beepOnBreakpoint:
            # Delay by 100 ms to let IntelliJ update the line number widget
            # before we read it for breakpoint detection.
            callLater(100, self._checkForBreakpoint)
        if vars.readAiSuggestionAuto:
            # Schedule an AI suggestion check after 800 ms of caret inactivity.
            # GitHub Copilot typically delivers a suggestion within 300–600 ms
            # after the user stops typing.  By waiting 800 ms we avoid firing
            # on every character keystroke.
            self._aiCheckId += 1
            checkId = self._aiCheckId
            callLater(800, lambda: self._checkAndAnnounceAiSuggestion(checkId))

    def _checkAndAnnounceAiSuggestion(self, checkId):
        """
        Fires 800 ms after a caret event if no newer caret event arrived.
        Reads any text that appeared after the caret (the Copilot suggestion).
        """
        if checkId != self._aiCheckId:
            return  # a newer caret event superseded this check
        suggestion = _readTextAfterCaret(self)
        if suggestion:
            ui.message(suggestion)

    def _checkForBreakpoint(self):
        try:
            fg = api.getForegroundObject()
            if fg is None or fg.appModule is None:
                return
            if fg.appModule.hasBreakpointOnCurrentLine():
                tones.beep(300, 150)
        except Exception:
            pass


# ── App Module ────────────────────────────────────────────────────────────────
class AppModule(appModuleHandler.AppModule):
    """
    NVDA AppModule base for all supported JetBrains IDEs.

    Thin stub files (idea64.py, pycharm64.py, …) import and re-export this
    class so NVDA loads it for the matching process name.
    """

    def __init__(self, pid, appName=None):
        super().__init__(pid, appName)
        gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(
            JetBrainsAddonSettings
        )
        # Phase 8: validated caches
        self._statusCache  = None   # NVDAObject with role == STATUSBAR
        self._lineNumCache = None   # NVDAObject whose name matches \d+:\d+

        # Phase 7: track whether event_nameChange has fired at least once
        # so the watcher can slow down its poll interval
        self._eventDrivenActive = False

        # Breakpoint early-exit optimisation: avoid repeated tree walks for the
        # same file+line (e.g. rapid caret events on a single line).
        self._lastBpFile = None
        self._lastBpLine = None

        self._watcher = StatusBarWatcher(self)
        self._watcher.start()

    def terminate(self):
        self._watcher.stopped = True
        gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(
            JetBrainsAddonSettings
        )

    # ── NVDAObject overlay ────────────────────────────────────────────────────
    def chooseNVDAObjectOverlayClasses(self, obj, clsList):
        if obj.role == EDITABLE_TEXT:
            clsList.insert(0, EnhancedEditableText)

    # ── Phase 7: event-driven status updates ─────────────────────────────────
    def event_nameChange(self, obj, nextHandler):
        """
        Primary notification path for status bar changes.

        NVDA fires this for EVERY accessible object whose name changes in the
        process — including the editor text on each keystroke.  The guard below
        ensures we only do COM work when there is already a cached status bar
        AND the changed object's parent has role STATUSBAR.

        The Java Access Bridge may not fire this event on older IntelliJ
        versions or on Windows configurations where accessibility events are
        suppressed.  The polling fallback in StatusBarWatcher handles those
        cases transparently.
        """
        # Fast-path bail-out: skip entirely if we have no cached status bar yet.
        # This avoids any COM call during the first seconds before the watcher
        # has located the status bar.
        if self._statusCache is None:
            nextHandler()
            return
        try:
            # One parent role lookup — fast, avoids object identity comparison.
            parent = obj.parent
            if parent is not None and parent.role == STATUSBAR:
                self._eventDrivenActive = True
                self._watcher.onExternalStatusChange(obj.name or "")
        except Exception:
            pass
        nextHandler()

    # ── Scripts ──────────────────────────────────────────────────────────────
    @script(
        "Read the status bar",
        gesture="kb:NVDA+i",
        category="JetBrains IDEs",
    )
    def script_readStatusBar(self, gesture):
        status = self.getStatusBar()
        if status is None:
            ui.browseableMessage(isHtml=True, message=_STATUS_BAR_HELP_HTML)
            return
        child = status.simpleFirstChild
        if child and child.name:
            ui.message(child.name)

    @script(
        "Read current line number",
        gesture="kb:nvda+alt+l",
        category="JetBrains IDEs",
    )
    def script_readLineNumber(self, gesture):
        lineNumber = self.getLineNumber()
        if lineNumber is None:
            ui.browseableMessage(isHtml=True, message=_LINE_NUMBER_HELP_HTML)
        elif lineNumber.name:
            ui.message(f"Line {lineNumber.name}")

    @script(
        "Toggle automatically reading status bar changes",
        category="JetBrains IDEs",
    )
    def script_toggleSpeakOnStatusChanged(self, gesture):
        newVal = not vars.speakOnChange
        config.conf[CONF_KEY][SPEAK_ON_STATUS_CHANGED_KEY] = newVal
        vars.speakOnChange = newVal
        ui.message(
            "Enabled automatically reading status bar changes"
            if newVal else
            "Disabled automatically reading status bar changes"
        )

    @script(
        "Toggle interrupting speech when automatically reading status bar changes",
        category="JetBrains IDEs",
    )
    def script_toggleInterruptSpeech(self, gesture):
        newVal = not vars.interruptSpeech
        config.conf[CONF_KEY][INTERRUPT_SPEECH_KEY] = newVal
        vars.interruptSpeech = newVal
        ui.message(
            "Enabled interrupting speech while automatically reading status bar changes"
            if newVal else
            "Disabled interrupting speech while automatically reading status bar changes"
        )

    @script("Toggle beep on breakpoint", category="JetBrains IDEs")
    def script_toggleBeepOnBreakpoint(self, gesture):
        newVal = not vars.beepOnBreakpoint
        config.conf[CONF_KEY][BEEP_ON_BREAKPOINT_KEY] = newVal
        vars.beepOnBreakpoint = newVal
        ui.message(
            "Enabled beep on breakpoint" if newVal else "Disabled beep on breakpoint"
        )

    @script(
        "Read current AI inline code suggestion (GitHub Copilot, JetBrains AI, Tabnine)",
        gesture="kb:NVDA+shift+a",
        category="JetBrains IDEs",
    )
    def script_readAiSuggestion(self, gesture):
        """
        On-demand reading of the AI inline suggestion currently displayed in
        the editor.  Works regardless of whether automatic mode is enabled.

        Position the cursor at the end of the code you typed, then press
        NVDA+Shift+A after Copilot shows a suggestion (gray ghost text).
        """
        focused = api.getFocusObject()
        suggestion = _readTextAfterCaret(focused)
        if suggestion:
            ui.message(suggestion)
        else:
            ui.message("No AI suggestion available")

    @script(
        "Toggle automatic reading of AI inline code suggestions",
        category="JetBrains IDEs",
    )
    def script_toggleAiSuggestionAuto(self, gesture):
        newVal = not vars.readAiSuggestionAuto
        config.conf[CONF_KEY][READ_AI_SUGGESTION_AUTO_KEY] = newVal
        vars.readAiSuggestionAuto = newVal
        ui.message(
            "AI suggestion auto-reading enabled"
            if newVal else
            "AI suggestion auto-reading disabled"
        )

    # ── Internal guards ───────────────────────────────────────────────────────
    def _isForegroundOurs(self):
        """
        Phase 1: Return True if the foreground window belongs to a supported
        JetBrains process.  Replaces the hardcoded 'appName == "idea64"' check.
        """
        obj = api.getForegroundObject()
        return (
            obj is not None
            and obj.appModule is not None
            and obj.appModule.appName in SUPPORTED_JETBRAINS_APPS
        )

    # ── Phase 8: validated cache accessors ───────────────────────────────────
    def _getStatusBarCached(self):
        """Return the cached status bar NVDAObject if still valid."""
        if _isObjectValid(self._statusCache, STATUSBAR):
            return self._statusCache
        self._statusCache = None
        return None

    def _getLineNumCached(self):
        """Return the cached line:col widget if still valid."""
        if self._lineNumCache is not None:
            try:
                name = self._lineNumCache.name or ""
                # Valid if it still looks like "line:col" or is momentarily empty
                if _LINE_COL_RE.match(name) or name == "":
                    return self._lineNumCache
            except Exception:
                pass
            self._lineNumCache = None
        return None

    # ── Phase 2: Role-based status bar detection ──────────────────────────────
    def getStatusBar(self, refresh: bool = False):
        """
        Locate the JetBrains status bar NVDAObject.

        Phase 2 change: searches by role == STATUSBAR using BFS.
        Removed: English string match on obj.name == "Status Bar".

        The role-based approach works across:
        • IntelliJ pre-2023  (STATUSBAR is a top-level child)
        • IntelliJ post-2023 (STATUSBAR is wrapped in a named container)
        • All non-English localisations

        Parameters
        ----------
        refresh : bool   Force a fresh tree walk even if the cache is valid.
        """
        if not self._isForegroundOurs():
            return None

        if not refresh:
            cached = self._getStatusBarCached()
            if cached is not None:
                return cached

        fg = api.getForegroundObject()
        if fg is None:
            return None

        # Status bar is always near the top of the window; depth 4 is sufficient.
        result = findObject(
            fg,
            lambda o: o.role == STATUSBAR,
            maxDepth=4,
            maxNodes=100,
        )

        self._statusCache = result
        return result

    # ── Phase 3: Regex-based line number detection ────────────────────────────
    def getLineNumber(self):
        """
        Locate the line:column status widget.

        Phase 3 change: matches child.name against r'^\d+:\d+$' instead of
        checking child.description == "go to line".

        The regex approach is:
        • Locale-independent (no English description required)
        • Version-independent (works regardless of IntelliJ version)
        • Still falls back to the English description as a secondary hint
        """
        if not self._isForegroundOurs():
            return None

        cached = self._getLineNumCached()
        if cached is not None:
            return cached

        statusBar = self.getStatusBar()
        if statusBar is None:
            return None

        result = findObject(
            statusBar,
            _isLineColWidget,
            maxDepth=3,
            maxNodes=50,
        )

        self._lineNumCache = result
        return result

    # ── Phase 5: Fault-tolerant breakpoint detection ──────────────────────────
    def hasBreakpointOnCurrentLine(self):
        """
        Return True if the current editor line has a breakpoint set.

        Phase 5 guarantee: NEVER raises.  Any failure silently returns False.
        This prevents breakpoint detection from degrading the editing experience.
        """
        try:
            return self._hasBreakpointImpl()
        except Exception as e:
            log.debug("JetBrains breakpoint check failed: %s" % e)
            return False

    def _hasBreakpointImpl(self):
        lineObj = self.getLineNumber()
        if not lineObj or not lineObj.name:
            return False
        if not _LINE_COL_RE.match(lineObj.name):
            return False

        try:
            line = int(lineObj.name.split(":")[0])
        except ValueError:
            return False

        # Phase 4: get filename from accessibility tree, not window title
        fileName = self._getEditorFileName()
        if not fileName:
            return False

        # Early-exit optimisation: if we are on the exact same file+line as the
        # last check, skip the expensive tree walk.  Handles rapid caret events
        # fired by IntelliJ for a single logical move.
        if self._lastBpFile == fileName and self._lastBpLine == line:
            return False
        self._lastBpFile = fileName
        self._lastBpLine = line

        breakpointTree = self._getBreakpointTree()
        if not breakpointTree:
            return False

        # Walk breakpoint tree with a node budget to prevent UI lag.
        # Structure: tree → categories → breakpoint items (filename:line in name)
        budget = 300
        category = breakpointTree.simpleFirstChild
        while category and budget > 0:
            sub = category.simpleFirstChild
            while sub and budget > 0:
                budget -= 1
                name = (sub.name or "").lower()
                if fileName.lower() in name and f":{line}" in name:
                    return True
                sub = sub.simpleNext
            category = category.simpleNext

        return False

    # ── Phase 4: Filename from accessibility tree ─────────────────────────────
    def _getEditorFileName(self):
        """
        Extract the active editor's filename from the accessibility tree.

        Strategy 1 (preferred): find the selected editor TAB.
          JetBrains IDEs give each tab role=TAB and SELECTED state when active.
          The tab name is exactly the filename (e.g. "Main.java").

        Strategy 2 (fallback): parse the window title.
          Handles both "Project – File.ext" and "File.ext – Project" orderings.
          Uses a regex for the separator to support em-dash, en-dash, and hyphen.
        """
        fg = api.getForegroundObject()
        if fg is None:
            return None

        tab = findObject(
            fg,
            _isSelectedEditorTab,
            maxDepth=6,
            maxNodes=150,
        )
        if tab and tab.name:
            return tab.name.strip()

        return _filenameFromWindowTitle(fg.windowText)

    def _getBreakpointTree(self):
        """
        Phase 5: locate the breakpoints TREEVIEW in the IDE window.

        Uses _isBreakpointTree() which samples items for 'filename:linenum'
        patterns.  NOT cached — tool windows go stale when closed/reopened.
        """
        fg = api.getForegroundObject()
        if fg is None:
            return None

        return findObject(
            fg,
            _isBreakpointTree,
            maxDepth=8,
            maxNodes=200,
        )


# ── Phase 7: Background status watcher (polling fallback) ─────────────────────
class StatusBarWatcher(threading.Thread):
    """
    Background thread that polls the JetBrains status bar for text changes.

    Phase 7 design
    --------------
    • event_nameChange in AppModule is the PRIMARY notification mechanism.
      When IntelliJ's Java Access Bridge fires nameChange events, this thread
      receives them via onExternalStatusChange() and acts immediately.

    • Once at least one nameChange event has been received (_eventDrivenActive),
      the poll interval is raised from SLEEP_FAST (0.25 s) to SLEEP_SLOW (2 s).
      The poll then acts as a heartbeat/fallback rather than the main driver.

    • On IntelliJ versions or Windows configurations where nameChange events are
      not delivered, the thread continues at SLEEP_FAST — identical to the
      original behaviour.
    """

    STATUS_CHANGED_TONE = 1000
    AFTER_TONE          = 800
    STATUS_CLEARED_TONE = 500
    SLEEP_FAST          = 0.25   # before events confirmed
    SLEEP_SLOW          = 2.0    # after events confirmed
    REFRESH_INTERVAL_FAST = 2.0  # seconds between forced cache refresh (no events)
    REFRESH_INTERVAL_SLOW = 5.0  # seconds between forced cache refresh (with events)

    def __init__(self, addon):
        super().__init__(daemon=True)
        self.stopped      = False
        self._lastText    = ""
        self._addon       = addon
        self._lastRefresh = time.time()

    # ── Called from NVDA event thread (event_nameChange) ─────────────────────
    def onExternalStatusChange(self, newText):
        """
        Receives status text directly from event_nameChange.
        Bypasses the poll cycle for zero-latency announcements.
        """
        self._handleStatusText(newText)

    # ── Core announcement logic (shared by event path and poll path) ──────────
    def _handleStatusText(self, msg):
        if self._lastText == msg:
            return

        if msg and vars.beepOnChange:
            tones.beep(self.STATUS_CHANGED_TONE, 50)
        elif not msg and vars.beepOnClear:
            tones.beep(self.STATUS_CLEARED_TONE, 50)

        if msg and vars.speakOnChange:
            seq = []
            if vars.beepBeforeReading:
                seq.append(speech.commands.BeepCommand(self.STATUS_CHANGED_TONE, 50))
            seq.append(msg)
            if vars.beepAfterReading:
                seq.append(speech.commands.BeepCommand(self.AFTER_TONE, 50))
            speech.speak(
                seq,
                priority=speech.Spri.NOW if vars.interruptSpeech else speech.Spri.NORMAL,
            )

        self._lastText = msg

    # ── Poll loop ─────────────────────────────────────────────────────────────
    def _runLoopIteration(self):
        now = time.time()
        refresh_interval = (
            self.REFRESH_INTERVAL_SLOW
            if self._addon._eventDrivenActive
            else self.REFRESH_INTERVAL_FAST
        )
        shouldRefresh = (now - self._lastRefresh) > refresh_interval
        if shouldRefresh:
            self._lastRefresh = now

        status = self._addon.getStatusBar(refresh=shouldRefresh)
        if status is None:
            return

        # Use firstChild (not simpleFirstChild) to detect when the error is
        # cleared — simpleFirstChild skips empty/hidden children.
        child = status.firstChild
        if child is not None:
            self._handleStatusText(child.name or "")

    def run(self):
        while not self.stopped:
            try:
                self._runLoopIteration()
            except Exception as e:
                log.warn("JetBrains status watcher error: %s" % e)
            sleep_time = (
                self.SLEEP_SLOW if self._addon._eventDrivenActive else self.SLEEP_FAST
            )
            time.sleep(sleep_time)


# ── Help text (HTML) ──────────────────────────────────────────────────────────
_STATUS_BAR_HELP_HTML = """
<p>Failed to read the status bar text.
Make sure the <em>status text</em> status bar widget is enabled:</p>
<h2>Method 1</h2>
<ol>
  <li>Open the Search All panel by double-tapping Shift.</li>
  <li>Search for "Status Bar Widgets" and press Enter.</li>
  <li>Find "status text" in the list.</li>
  <li>Activate it with Space. (It may not report its checked state.)</li>
  <li>Press Escape to close the list.</li>
  <li>Retry reading the status bar.</li>
</ol>
<p>If "status text" is not in the list, try Method 2.</p>
<h2>Method 2</h2>
<ol>
  <li>Open the View menu (Alt+V).</li>
  <li>Go to Appearance &gt; Navigation Bar.</li>
  <li>Select any option other than "In Status Bar" (e.g. "Top" or "Don't Show").</li>
  <li>Retry reading the status bar.</li>
</ol>
"""

_LINE_NUMBER_HELP_HTML = """
<p>Failed to read the line number.
Make sure the editor is open and the <em>Line:Column Number</em> status bar widget is enabled:</p>
<ol>
  <li>Open the Search All panel by double-tapping Shift.</li>
  <li>Search for "Status Bar Widgets" and press Enter.</li>
  <li>Find "Line:Column Number" in the list.</li>
  <li>Activate it with Space. (It may not report its checked state.)</li>
  <li>Press Escape to close the list.</li>
  <li>Retry reading the line number.</li>
</ol>
"""
