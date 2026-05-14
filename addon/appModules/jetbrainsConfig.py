import config
import gui
import wx
from dataclasses import dataclass
from gui.settingsDialogs import SettingsPanel

CONF_KEY                    = "intellij"
BEEP_ON_STATUS_CHANGED_KEY  = "beepOnStatusChange"
BEEP_ON_STATUS_CLEARED_KEY  = "beepOnStatusCleared"
SPEAK_ON_STATUS_CHANGED_KEY = "speakOnStatusChange"
INTERRUPT_SPEECH_KEY        = "interruptOnStatusChange"
BEEP_BEFORE_READING_KEY     = "beepBeforeReadingStatus"
BEEP_AFTER_READING_KEY      = "beepAfterReadingStatus"
BEEP_ON_BREAKPOINT_KEY      = "beepOnBreakpoint"
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

config.conf.spec[CONF_KEY] = {k: f"boolean(default={v})" for k, v in _DEFAULTS.items()}
if config.conf.get(CONF_KEY) is None:
    config.conf[CONF_KEY] = {}


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

vars = _Vars()


def setGlobalVars():
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


class JetBrainsAddonSettings(SettingsPanel):
    title = "JetBrains IDEs"

    def makeSettings(self, settingsSizer):
        sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
        conf = config.conf[CONF_KEY]

        self.beepOnChange = sHelper.addItem(wx.CheckBox(self, label="Beep when status bar changes"))
        self.beepOnChange.SetValue(conf[BEEP_ON_STATUS_CHANGED_KEY])

        self.beepOnClear = sHelper.addItem(wx.CheckBox(self, label="Beep when status bar is cleared"))
        self.beepOnClear.SetValue(conf[BEEP_ON_STATUS_CLEARED_KEY])

        self.speakOnChange = sHelper.addItem(wx.CheckBox(self, label="Automatically read status bar changes"))
        self.speakOnChange.SetValue(conf[SPEAK_ON_STATUS_CHANGED_KEY])

        self.beepBeforeReading = sHelper.addItem(wx.CheckBox(self, label="Beep before status bar change is read"))
        self.beepBeforeReading.SetValue(conf[BEEP_BEFORE_READING_KEY])

        self.beepAfterReading = sHelper.addItem(wx.CheckBox(self, label="Beep after status bar change is read"))
        self.beepAfterReading.SetValue(conf[BEEP_AFTER_READING_KEY])

        self.interruptSpeech = sHelper.addItem(wx.CheckBox(self, label="Interrupt speech when automatically reading status bar changes"))
        self.interruptSpeech.SetValue(conf[INTERRUPT_SPEECH_KEY])

        self.beepOnBreakpoint = sHelper.addItem(wx.CheckBox(self, label="(Experimental) Beep when breakpoint is detected on current line"))
        self.beepOnBreakpoint.SetValue(conf[BEEP_ON_BREAKPOINT_KEY])

        self.readAiSuggestionAuto = sHelper.addItem(wx.CheckBox(self, label="Automatically read AI inline code suggestions (GitHub Copilot, JetBrains AI, Tabnine)"))
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
