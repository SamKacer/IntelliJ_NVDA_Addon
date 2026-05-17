# JetBrains IDEs — NVDA Addon
# Supports: IntelliJ IDEA, PyCharm, WebStorm, GoLand, Rider, CLion, DataGrip, RubyMine, Android Studio
# Based on original work by Samuel Kacer <samuel.kacer@gmail.com>
# GNU GENERAL PUBLIC LICENSE V2

import time
from winsound import PlaySound, SND_ASYNC, SND_ALIAS

import api
import appModuleHandler
import config
import gui
import tones
import ui
from core import callLater
from editableText import EditableTextWithoutAutoSelectDetection
from logHandler import log
from scriptHandler import script

from .jetbrainsCompat import EDITABLE_TEXT, STATUSBAR
from .jetbrainsConfig import (
    vars, setGlobalVars, JetBrainsAddonSettings,
    CONF_KEY,
    SPEAK_ON_STATUS_CHANGED_KEY, INTERRUPT_SPEECH_KEY,
    BEEP_ON_BREAKPOINT_KEY, READ_AI_SUGGESTION_AUTO_KEY,
)
from .jetbrainsTraversal import (
    findObject, _isObjectValid,
    _isLineColWidget, _isSelectedEditorTab, _isBreakpointTree,
    _filenameFromWindowTitle, _LINE_COL_RE,
    collectStatusBarText, isDescendantOfStatusBar, _isStatusBarElement,
)
from .jetbrainsGestures import (
    TIER1_MOVE_BY_LINE, TIER1_SELECTION,
    TIER2_MOVE_BY_LINE, TIER2_SELECTION,
    TIER3_MOVE_BY_LINE,
    _ALL_MOVE_BY_LINE, _ALL_SELECTION,
)
from .jetbrainsStatus import StatusBarWatcher


SUPPORTED_JETBRAINS_APPS = frozenset({
    "idea64",     # IntelliJ IDEA
    "pycharm64",  # PyCharm
    "webstorm64", # WebStorm
    "goland64",   # GoLand
    "rider64",    # Rider
    "clion64",    # CLion
    "datagrip64", # DataGrip
    "rubymine64", # RubyMine
    "studio64",   # Android Studio
})


def _readTextAfterCaret(obj):
    """
    Return text from caret to end of line.
    JAB exposes inline AI suggestions (Copilot, JetBrains AI) by appending
    ghost text after the caret on the same accessible line.
    """
    try:
        import textInfos
        if obj is None or not hasattr(obj, "makeTextInfo"):
            return None
        caretInfo = obj.makeTextInfo(textInfos.POSITION_CARET)
        afterCaret = caretInfo.copy()
        afterCaret.expand(textInfos.UNIT_LINE)
        afterCaret.setEndPoint(caretInfo, "startToStart")
        text = afterCaret.text.rstrip("\r\n")
        return text if text.strip() else None
    except Exception:
        return None


class EnhancedEditableText(EditableTextWithoutAutoSelectDetection):
    """NVDAObject overlay for JetBrains editor text fields."""

    __gestures = (
        {g: "caret_moveByLine"      for g in _ALL_MOVE_BY_LINE} |
        {g: "caret_changeSelection" for g in _ALL_SELECTION}
    )

    shouldFireCaretMovementFailedEvents = True

    def initOverlayClass(self):
        self._aiCheckId = 0
        self._bpCheckId = 0

    def event_caretMovementFailed(self, gesture):
        PlaySound("SystemExclamation", SND_ASYNC | SND_ALIAS)

    def event_caret(self):
        super().event_caret()
        if vars.beepOnBreakpoint:
            # Debounce: only the last caret event within a rapid burst runs the
            # breakpoint check, preventing N×heavy-JAB-walk on the main thread.
            self._bpCheckId += 1
            bpId = self._bpCheckId
            callLater(100, lambda: self._checkForBreakpoint(bpId))
        if vars.readAiSuggestionAuto:
            # Debounce: skip if a newer caret event arrives within 800 ms.
            # Copilot suggestions typically appear 300-600 ms after typing stops.
            self._aiCheckId += 1
            checkId = self._aiCheckId
            callLater(800, lambda: self._checkAndAnnounceAiSuggestion(checkId))

    def _checkAndAnnounceAiSuggestion(self, checkId):
        if checkId != self._aiCheckId:
            return
        suggestion = _readTextAfterCaret(self)
        if suggestion:
            ui.message(suggestion)

    def _checkForBreakpoint(self, bpId):
        if bpId != self._bpCheckId:
            return
        try:
            am = self.appModule
            if am is None:
                return
            if am.hasBreakpointOnCurrentLine():
                tones.beep(300, 150)
        except Exception:
            pass


class AppModule(appModuleHandler.AppModule):
    """NVDA AppModule base for all supported JetBrains IDEs."""

    def __init__(self, pid, appName=None):
        super().__init__(pid, appName)
        gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(JetBrainsAddonSettings)
        self._statusCache        = None
        self._lineNumCache       = None
        self._eventDrivenActive  = False
        self._lastBpFile         = None
        self._lastBpLine         = None
        # Foreground cache (200 ms TTL) — reduces COM round-trips; safe because
        # focus changes are user-initiated and cannot occur faster than ~200 ms.
        self._lastForeground      = None
        self._lastForegroundTime  = 0.0
        self._lastNameChangeTrigger = 0.0
        self._watcher = StatusBarWatcher(self)
        self._watcher.start()

    def terminate(self):
        self._watcher.stopped = True
        gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(JetBrainsAddonSettings)

    def chooseNVDAObjectOverlayClasses(self, obj, clsList):
        if obj.role == EDITABLE_TEXT:
            clsList.insert(0, EnhancedEditableText)

    def event_nameChange(self, obj, nextHandler):
        # Skip until the watcher has located the status bar.
        if self._statusCache is None:
            nextHandler()
            return
        try:
            # EDITABLE_TEXT fires on every keystroke — bail before any parent walk.
            if obj.role == EDITABLE_TEXT:
                nextHandler()
                return
            # Skip the parent-chain walk when a refresh was triggered within 100 ms.
            # isDescendantOfStatusBar costs up to 5 COM round-trips per call; skipping
            # it during event bursts (indexing, building) keeps the main thread light.
            now = time.time()
            if (now - self._lastNameChangeTrigger) < 0.10:
                nextHandler()
                return
            # isDescendantOfStatusBar walks up to 5 levels so it handles both
            # classic UI (direct child) and New UI (widget nested 2-3 levels deep).
            if not isDescendantOfStatusBar(obj):
                nextHandler()
                return
            self._eventDrivenActive = True
            self._lastNameChangeTrigger = now
            # Signal the watcher thread to re-collect the full status bar text.
            # Collecting here (main thread) would risk JAB round-trips per event.
            self._watcher.triggerRefresh()
        except Exception:
            pass
        nextHandler()

    # ── Scripts ───────────────────────────────────────────────────────────────

    @script("Read the status bar", gesture="kb:NVDA+i", category="JetBrains IDEs")
    def script_readStatusBar(self, gesture):
        status = self.getStatusBar(refresh=True)
        if status is None:
            _logAccessibilityTree(self._getCachedForeground())
            ui.browseableMessage(isHtml=True, message=_STATUS_BAR_HELP_HTML)
            return
        text = collectStatusBarText(status)
        log.info("JetBrains statusBar text: %r" % text)
        if text:
            ui.message(text)
        else:
            ui.message("Status bar is empty")

    @script("Read current line number", gesture="kb:nvda+alt+l", category="JetBrains IDEs")
    def script_readLineNumber(self, gesture):
        lineNumber = self.getLineNumber()
        if lineNumber is None:
            ui.browseableMessage(isHtml=True, message=_LINE_NUMBER_HELP_HTML)
        elif lineNumber.name:
            ui.message(f"Line {lineNumber.name}")

    @script("Toggle automatically reading status bar changes", category="JetBrains IDEs")
    def script_toggleSpeakOnStatusChanged(self, gesture):
        newVal = not vars.speakOnChange
        config.conf[CONF_KEY][SPEAK_ON_STATUS_CHANGED_KEY] = newVal
        vars.speakOnChange = newVal
        ui.message(
            "Enabled automatically reading status bar changes" if newVal
            else "Disabled automatically reading status bar changes"
        )

    @script("Toggle interrupting speech when automatically reading status bar changes", category="JetBrains IDEs")
    def script_toggleInterruptSpeech(self, gesture):
        newVal = not vars.interruptSpeech
        config.conf[CONF_KEY][INTERRUPT_SPEECH_KEY] = newVal
        vars.interruptSpeech = newVal
        ui.message(
            "Enabled interrupting speech while automatically reading status bar changes" if newVal
            else "Disabled interrupting speech while automatically reading status bar changes"
        )

    @script(
        "Toggle breakpoint detection on current line (enable only when using breakpoints)",
        gesture="kb:NVDA+shift+b",
        category="JetBrains IDEs",
    )
    def script_toggleBeepOnBreakpoint(self, gesture):
        newVal = not vars.beepOnBreakpoint
        config.conf[CONF_KEY][BEEP_ON_BREAKPOINT_KEY] = newVal
        vars.beepOnBreakpoint = newVal
        ui.message("Breakpoint detection enabled" if newVal else "Breakpoint detection disabled")

    @script(
        "Read current AI inline code suggestion (GitHub Copilot, JetBrains AI, Tabnine)",
        gesture="kb:NVDA+shift+a",
        category="JetBrains IDEs",
    )
    def script_readAiSuggestion(self, gesture):
        focused = api.getFocusObject()
        suggestion = _readTextAfterCaret(focused)
        ui.message(suggestion if suggestion else "No AI suggestion available")

    @script("Toggle automatic reading of AI inline code suggestions", category="JetBrains IDEs")
    def script_toggleAiSuggestionAuto(self, gesture):
        newVal = not vars.readAiSuggestionAuto
        config.conf[CONF_KEY][READ_AI_SUGGESTION_AUTO_KEY] = newVal
        vars.readAiSuggestionAuto = newVal
        ui.message(
            "AI suggestion auto-reading enabled" if newVal
            else "AI suggestion auto-reading disabled"
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _getCachedForeground(self):
        now = time.time()
        age = now - self._lastForegroundTime
        if self._lastForeground is not None and age < 0.2:
            # Skip COM validation for entries younger than 50 ms; only validate
            # when approaching the 200 ms TTL to catch stale references cheaply.
            if age < 0.05 or _isObjectValid(self._lastForeground):
                return self._lastForeground
        try:
            fg = api.getForegroundObject()
        except Exception:
            return None
        self._lastForeground      = fg
        self._lastForegroundTime  = now
        return fg

    def _isForegroundOurs(self):
        obj = self._getCachedForeground()
        return (
            obj is not None
            and obj.appModule is not None
            and obj.appModule.appName in SUPPORTED_JETBRAINS_APPS
        )

    def _getStatusBarCached(self):
        # Validate without requiring STATUSBAR role: New UI uses a PANEL element.
        if self._statusCache is not None and _isObjectValid(self._statusCache):
            return self._statusCache
        self._statusCache = None
        return None

    def _getLineNumCached(self):
        if self._lineNumCache is not None:
            try:
                name = self._lineNumCache.name or ""
                # Valid if still "line:col" or momentarily blank between keystrokes.
                if _LINE_COL_RE.match(name) or name == "":
                    return self._lineNumCache
            except Exception:
                pass
            self._lineNumCache = None
        return None

    def getStatusBar(self, refresh: bool = False):
        if not self._isForegroundOurs():
            return None
        if not refresh:
            cached = self._getStatusBarCached()
            if cached is not None:
                return cached
        fg = self._getCachedForeground()
        if fg is None:
            return None
        # _isStatusBarElement matches STATUSBAR role (classic UI) OR the 'Status Bar'
        # PANEL used by New UI 2024.2+ — role alone is not sufficient there.
        result = findObject(fg, _isStatusBarElement, maxDepth=4, maxNodes=80)
        self._statusCache = result
        log.debug("JetBrains getStatusBar: found=%s role=%s name=%r" % (
            result is not None,
            getattr(result, "role", None) if result is not None else None,
            getattr(result, "name", None) if result is not None else None,
        ))
        return result

    def getLineNumber(self):
        if not self._isForegroundOurs():
            return None
        cached = self._getLineNumCached()
        if cached is not None:
            return cached
        statusBar = self.getStatusBar()
        if statusBar is None:
            return None
        result = findObject(statusBar, _isLineColWidget, maxDepth=3, maxNodes=50)
        self._lineNumCache = result
        return result

    def hasBreakpointOnCurrentLine(self):
        """Never raises — any failure returns False silently."""
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
        fileName = self._getEditorFileName()
        if not fileName:
            return False
        # Skip repeated tree walk when caret stays on same file+line.
        if self._lastBpFile == fileName and self._lastBpLine == line:
            return False
        self._lastBpFile = fileName
        self._lastBpLine = line
        breakpointTree = self._getBreakpointTree()
        if not breakpointTree:
            return False
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

    def _getEditorFileName(self):
        fg = self._getCachedForeground()
        if fg is None:
            return None
        tab = findObject(fg, _isSelectedEditorTab, maxDepth=6, maxNodes=150)
        if tab and tab.name:
            return tab.name.strip()
        return _filenameFromWindowTitle(fg.windowText)

    def _getBreakpointTree(self):
        fg = self._getCachedForeground()
        if fg is None:
            return None
        return findObject(fg, _isBreakpointTree, maxDepth=8, maxNodes=120)


def _logAccessibilityTree(root, maxDepth=5, maxNodes=120):
    """Dump the accessibility tree to the NVDA log for diagnostic purposes.

    Called when getStatusBar() fails so we can inspect what roles/names are
    actually present in the foreground window and adjust the search accordingly.
    """
    if root is None:
        log.info("JetBrains diag: foreground object is None")
        return
    log.info("JetBrains diag: status bar NOT found — dumping accessibility tree (depth=%d, nodes=%d)" % (maxDepth, maxNodes))
    from collections import deque
    queue = deque()
    try:
        child = root.simpleFirstChild
        if child:
            queue.append((child, 1))
    except Exception as e:
        log.info("JetBrains diag: cannot access root children: %s" % e)
        return
    visited = 0
    while queue and visited < maxNodes:
        obj, depth = queue.popleft()
        while obj is not None and visited < maxNodes:
            visited += 1
            try:
                role = obj.role
                name = obj.name
                desc = obj.description
                indent = "  " * depth
                log.info("JetBrains diag: %s[%d] role=%s name=%r desc=%r" % (indent, depth, role, name, desc))
            except Exception as e:
                log.info("JetBrains diag: %s[%d] <error reading object: %s>" % ("  " * depth, depth, e))
            if depth < maxDepth:
                try:
                    fc = obj.simpleFirstChild
                    if fc is not None:
                        queue.append((fc, depth + 1))
                except Exception:
                    pass
            try:
                obj = obj.simpleNext
            except Exception:
                break
    log.info("JetBrains diag: tree dump complete (%d nodes)" % visited)


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
