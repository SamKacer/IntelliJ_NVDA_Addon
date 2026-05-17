import threading
import time

import speech
import tones
from logHandler import log

from .jetbrainsConfig import vars
from .jetbrainsTraversal import collectStatusBarText


class StatusBarWatcher(threading.Thread):
    """
    Background thread polling the JetBrains status bar for text changes.

    event_nameChange is the primary notification path (zero latency).
    This thread is the fallback for systems where JAB does not fire nameChange.
    Once events are confirmed (_eventDrivenActive=True), poll interval rises
    from SLEEP_FAST to SLEEP_SLOW.
    """

    STATUS_CHANGED_TONE   = 1000
    AFTER_TONE            = 800
    STATUS_CLEARED_TONE   = 500
    SLEEP_FAST            = 0.5
    SLEEP_SLOW            = 2.0
    REFRESH_INTERVAL_FAST = 2.0
    REFRESH_INTERVAL_SLOW = 5.0
    # Minimum seconds between successive automatic speech announcements.
    # Coalesces rapid status bar bursts (indexing, building) so only the
    # latest message is spoken when multiple updates land within this window.
    SPEAK_DEBOUNCE        = 0.6

    def __init__(self, addon):
        super().__init__(daemon=True)
        self.stopped          = False
        self._lastText        = ""
        self._addon           = addon
        self._lastRefresh     = time.time()
        self._pendingRefresh  = False
        self._noChangeCount   = 0
        self._lastSpeakTime   = 0.0
        self._pendingSpeakText = None

    def triggerRefresh(self):
        """Signal an immediate re-collect on the next watcher cycle.

        Called from event_nameChange (main NVDA thread) when a status bar
        descendant fires nameChange. Setting a boolean flag is GIL-safe.
        """
        self._pendingRefresh = True
        self._noChangeCount  = 0   # Reset backoff when a new event arrives.

    def _handleStatusText(self, msg):
        if self._lastText == msg:
            self._noChangeCount += 1
            return
        self._noChangeCount = 0
        if msg and vars.beepOnChange:
            tones.beep(self.STATUS_CHANGED_TONE, 50)
        elif not msg and vars.beepOnClear:
            tones.beep(self.STATUS_CLEARED_TONE, 50)
        self._lastText = msg
        if msg and vars.speakOnChange:
            # Store the latest text; _tickSpeech() delivers it after the debounce
            # window expires, silently dropping intermediate values on rapid bursts.
            self._pendingSpeakText = msg

    def _tickSpeech(self):
        """Deliver pending speech if the debounce window has expired."""
        if self._pendingSpeakText is None:
            return
        if (time.time() - self._lastSpeakTime) < self.SPEAK_DEBOUNCE:
            return
        msg = self._pendingSpeakText
        self._pendingSpeakText = None
        self._lastSpeakTime = time.time()
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

    def _runLoopIteration(self):
        if not self._addon._isForegroundOurs():
            return
        now = time.time()
        refresh_interval = (
            self.REFRESH_INTERVAL_SLOW if self._addon._eventDrivenActive
            else self.REFRESH_INTERVAL_FAST
        )
        pending = self._pendingRefresh
        self._pendingRefresh = False
        shouldRefresh = pending or (now - self._lastRefresh) > refresh_interval
        if shouldRefresh:
            self._lastRefresh = now
        status = self._addon.getStatusBar(refresh=shouldRefresh)
        if status is None:
            return
        # collectStatusBarText handles both classic UI (single text child) and
        # New UI 2024.2+ (multiple independent widgets). Returns "" when cleared.
        text = collectStatusBarText(status)
        self._handleStatusText(text)
        self._tickSpeech()

    def run(self):
        while not self.stopped:
            try:
                self._runLoopIteration()
            except Exception as e:
                log.debug("JetBrains status watcher: %s" % e)
            base = self.SLEEP_SLOW if self._addon._eventDrivenActive else self.SLEEP_FAST
            # Progressive backoff: after 10 consecutive no-change cycles add 0.5 s
            # per batch, capped at +1.5 s. Resets automatically via triggerRefresh().
            extra = min(self._noChangeCount // 10, 3) * 0.5
            time.sleep(base + extra)
