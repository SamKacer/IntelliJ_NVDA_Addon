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

    def __init__(self, addon):
        super().__init__(daemon=True)
        self.stopped         = False
        self._lastText       = ""
        self._addon          = addon
        self._lastRefresh    = time.time()
        self._pendingRefresh = False

    def triggerRefresh(self):
        """Signal an immediate re-collect on the next watcher cycle.

        Called from event_nameChange (main NVDA thread) when a status bar
        descendant fires nameChange. Setting a boolean flag is GIL-safe.
        """
        self._pendingRefresh = True

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

    def run(self):
        while not self.stopped:
            try:
                self._runLoopIteration()
            except Exception as e:
                log.debug("JetBrains status watcher: %s" % e)
            time.sleep(
                self.SLEEP_SLOW if self._addon._eventDrivenActive else self.SLEEP_FAST
            )
