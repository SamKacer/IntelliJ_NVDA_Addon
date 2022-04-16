# IntelliJ Support App Module for NVDA
#Copyright (C) 2019-2020 Samuel Kacer
#GNU GENERAL PUBLIC LICENSE V2
#Author: Samuel Kacer <samuel.kacer@gmail.com>
#https://github.com/SamKacer/IntelliJ_NVDA_Addon

from dataclasses import dataclass
from unicodedata import category
import appModuleHandler
import tones
import controlTypes
import config
from editableText import EditableTextWithoutAutoSelectDetection
from logHandler import log
import gui
from gui.settingsDialogs import SettingsPanel
from scriptHandler import script
import speech
import ui
import api
import threading
import time
from winsound import PlaySound, SND_ASYNC, SND_ALIAS
import wx


CONF_KEY = 'intellij'
BEEP_ON_STATUS_CHANGED_KEY = 'beepOnError'
SPEAK_ON_STATUS_CHANGED_KEY = 'speakError'
INTERRUPT_SPEECH_KEY = 'interruptOnError'

config.conf.spec[CONF_KEY] = {
	BEEP_ON_STATUS_CHANGED_KEY : 'boolean()',
	SPEAK_ON_STATUS_CHANGED_KEY : 'boolean()',
	INTERRUPT_SPEECH_KEY : 'boolean()'
}

class IntelliJAddonSettings(SettingsPanel):
	title = "IntelliJ Improved"

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		conf = config.conf[CONF_KEY]
		self.beepOnChange= sHelper.addItem(wx.CheckBox(self, label="Beep on status bar changes"))
		self.beepOnChange.SetValue(conf[BEEP_ON_STATUS_CHANGED_KEY])
		self.speakOnChange = sHelper.addItem(wx.CheckBox(self, label="Automatically read status bar changes"))
		self.speakOnChange.SetValue(conf[SPEAK_ON_STATUS_CHANGED_KEY])
		self.interruptSpeech = sHelper.addItem(wx.CheckBox(self, label="Interrupt speech when automatically reading status bar changes"))
		self.interruptSpeech.SetValue(conf[INTERRUPT_SPEECH_KEY])

	def onSave(self):
		conf = config.conf[CONF_KEY]
		conf[BEEP_ON_STATUS_CHANGED_KEY] = self.beepOnChange.Value
		conf[SPEAK_ON_STATUS_CHANGED_KEY] = self.speakOnChange.Value
		conf[INTERRUPT_SPEECH_KEY] = self.interruptSpeech.Value
		setGlobalVars()

@dataclass
class Vars:
	beepOnChange: bool = True
	speakOnChange: bool = True
	interruptSpeech: bool = False

vars = Vars()

def setGlobalVars():
	conf = config.conf[CONF_KEY]
	vars.beepOnChange = conf[BEEP_ON_STATUS_CHANGED_KEY]
	vars.speakOnChange = conf[SPEAK_ON_STATUS_CHANGED_KEY]
	vars.interruptSpeech = conf[INTERRUPT_SPEECH_KEY]

# sQet conf in case vars not set yet
# def init_config():
	# conf = config.conf.get(CONF_KEY, dict())
	# conf[BEEP_ON_ERROR_KEY] = conf.get(BEEP_ON_ERROR_KEY, vars.beepOnError)
	# conf[SPEAK_ON_ERROR_KEY] = conf.get(SPEAK_ON_ERROR_KEY, vars.speakOnError)
	# conf[INTERRUPT_ON_ERROR_KEY] = conf.get(INTERRUPT_ON_ERROR_KEY, vars.interruptSpeech)
	# config.conf[CONF_KEY] = conf
# init_config()
setGlobalVars()

class EnhancedEditableText(EditableTextWithoutAutoSelectDetection):
	__gestures = {
		# these IntelliJ commands change caret position, so they should trigger reading new line position
		"kb:alt+downArrow" : "caret_moveByLine",
		"kb:alt+upArrow" : "caret_moveByLine",
		"kb:control+[" : "caret_moveByLine",
		"kb:control+]" : "caret_moveByLine",
		"kb:f2" : "caret_moveByLine",
		"kb:shift+f2" : "caret_moveByLine",
		"kb:control+b" : "caret_moveByLine",
		"kb:control+alt+leftArrow" : "caret_moveByLine",
		"kb:control+alt+rightArrow" : "caret_moveByLine",
		"kb:control+y" : "caret_moveByLine",
		"kb:f3" : "caret_moveByLine",
		"kb:shift+f3" : "caret_moveByLine",
		"kb:control+u" : "caret_moveByLine",
		"kb:control+shift+backspace" : "caret_moveByLine",
		"kb:control+/" : "caret_moveByLine",
		"kb:alt+j" : "caret_moveByLine",
		"kb:alt+control+downArrow" : "caret_moveByLine",
		"kb:alt+control+upArrow" : "caret_moveByLine",
		# these gestures trigger selection change
		"kb:control+w": "caret_changeSelection",
		"kb:control+shift+w": "caret_changeSelection",
		"kb:alt+shift+j": "caret_changeSelection",
		"kb:control+shift+[": "caret_changeSelection",
		"kb:control+shift+]": "caret_changeSelection",
	}

	shouldFireCaretMovementFailedEvents = True

	def event_caretMovementFailed(self, gesture):
		PlaySound('SystemExclamation', SND_ASYNC | SND_ALIAS)

	

class AppModule(appModuleHandler.AppModule):
	def __init__(self, pid, appName=None):
		super(AppModule, self).__init__(pid, appName)
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(IntelliJAddonSettings)
		self.status = None
		self.watcher = StatusBarWatcher(self)
		self.watcher.start()

	def terminate(self):
		self.watcher.stopped = True
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(IntelliJAddonSettings)


	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		if obj.role == controlTypes.ROLE_EDITABLETEXT:
			clsList.insert(0, EnhancedEditableText)
	
	@script(
		"Read the status bar",
		gesture = 'kb:NVDA+i',
		category="IntelliJ")
	def script_readStatusBar(self, gesture):
		status = self.getStatusBar()
		if status is None:
			ui.message('couldnt find status bar')
		else:
			msg = status.simpleFirstChild.name
			ui.message(msg)

	def getStatusBar(self):
		if self.status:
			return self.status
		else:
			obj = api.getForegroundObject()
			if obj is None or not obj.appModule.appName == "idea64":
				# Ignore cases nvda is lost
				return

			obj = obj.simpleFirstChild
			while obj is not None:
				if obj.role is controlTypes.ROLE_STATUSBAR:
					self.status = obj
					break

				obj = obj.simpleNext

			return obj

	@script("Toggle beeping when the status bar changes", category="IntelliJ")
	def script_toggleBeepOnStatusBarChange(self, gesture):
		newVal = not vars.beepOnChange
		config.conf[CONF_KEY][BEEP_ON_STATUS_CHANGED_KEY] = newVal
		vars.beepOnChange = newVal
		if newVal:
			ui.message("Enabled beeping on status bar change")
		else:
			ui.message("Disabled beeping on status bar change")

	@script("Toggle automatically reading status bar changes", category="IntelliJ")
	def script_toggleSpeakOnStatusChanged(self, gesture):
		newVal = not vars.speakOnChange
		config.conf[CONF_KEY][SPEAK_ON_STATUS_CHANGED_KEY] = newVal
		vars.speakOnChange = newVal
		if newVal:
			ui.message("Enabled automatically reading status bar changes")
		else:
			ui.message("Disabled automatically reading status bar changes")

	@script("Toggle interrupting speech when automatically reading status bar changes", category="IntelliJ")
	def script_toggleInterruptSpeech(self, gesture):
		newVal = not vars.interruptSpeech
		config.conf[CONF_KEY][INTERRUPT_SPEECH_KEY] = newVal
		vars.interruptSpeech = newVal
		if newVal:
			ui.message("Enabled interrupting speech while automatically reading status bar changes")
		else:
			ui.message("Disabled interrupting speech while automatically reading status bar changes")


class StatusBarWatcher(threading.Thread):
	ERROR_FOUND_TONE = 1000
	ERROR_FIXED_TONE = 2000
	sleepDuration = 0.25

	def __init__(self, addon):
		super(StatusBarWatcher, self).__init__()
		self.stopped = False
		self._lastText = ""
		self.addon = addon

	def _statusBarFound(self, obj):
		# Don't use simpleFirstChild here since we need to know wether the error is fixed
		if not obj.firstChild:
			return

		msg = obj.firstChild.name

		if self._lastText != msg:
			if vars.beepOnChange:
				tones.beep(self.ERROR_FOUND_TONE if msg else self.ERROR_FIXED_TONE, 50)

			if msg and vars.speakOnChange:
				ui.message(msg, speechPriority= speech.Spri.NOW if vars.interruptSpeech else None)

			self._lastText = msg

	def _runLoopIteration(self):
		status = self.addon.getStatusBar()
		if status:
			self._statusBarFound(status)

	def run(self):
		while not self.stopped:
			try:
				self._runLoopIteration()
			except Exception as error:
				log.warn("Error on watcher thread: %s" % error)
			time.sleep(self.sleepDuration)
