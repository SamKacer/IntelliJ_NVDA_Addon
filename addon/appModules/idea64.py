# IntelliJ Support App Module for NVDA
#Copyright (C) 2019-2020 Samuel Kacer
#GNU GENERAL PUBLIC LICENSE V2
#Author: Samuel Kacer <samuel.kacer@gmail.com>
#https://github.com/SamKacer/IntelliJ_NVDA_Addon

from buildVersion import version_year
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
from core import callLater

# handle both pre and post 2022 controlTypes
if version_year >= 2022:
	EDITABLE_TEXT = controlTypes.Role.EDITABLETEXT
	STATUSBAR = controlTypes.Role.STATUSBAR
else:
	EDITABLE_TEXT = controlTypes.ROLE_EDITABLETEXT
	STATUSBAR = controlTypes.ROLE_STATUSBAR

CONF_KEY = 'intellij'
BEEP_ON_STATUS_CHANGED_KEY = 'beepOnStatusChange'
BEEP_ON_STATUS_CLEARED_KEY = 'beepOnStatusCleared'
SPEAK_ON_STATUS_CHANGED_KEY = 'speakOnStatusChange'
INTERRUPT_SPEECH_KEY = 'interruptOnStatusChange'
BEEP_BEFORE_READING_KEY = 'beepBeforeReadingStatus'
BEEP_AFTER_READING_KEY = 'beepAfterReadingStatus'
BEEP_ON_BREAKPOINT_KEY = 'beepOnBreakpoint'

DEFAULT_BEEP_ON_CHANGE = False
DEFAULT_BEEP_ON_STATUS_CLEARED = False
DEFAULT_SPEAK_ON_CHANGE = True
DEFAULT_INTERRUPT_SPEECH = False
DEFAULT_BEEP_BEFORE_READING = True
DEFAULT_BEEP_AFTER_READING = False
DEFAULT_BEEP_ON_BREAKPOINT = True

config.conf.spec[CONF_KEY] = {
	BEEP_ON_STATUS_CHANGED_KEY : f'boolean(default={DEFAULT_BEEP_ON_CHANGE})',
	BEEP_ON_STATUS_CLEARED_KEY : f'boolean(default={DEFAULT_BEEP_ON_STATUS_CLEARED})',
	SPEAK_ON_STATUS_CHANGED_KEY : f'boolean(default={DEFAULT_SPEAK_ON_CHANGE})',
	INTERRUPT_SPEECH_KEY : f'boolean(default={DEFAULT_INTERRUPT_SPEECH})',
	BEEP_BEFORE_READING_KEY : f'boolean(default={DEFAULT_BEEP_BEFORE_READING})',
	BEEP_AFTER_READING_KEY : f'boolean(default={DEFAULT_BEEP_AFTER_READING})',
	BEEP_ON_BREAKPOINT_KEY: f'boolean(default={DEFAULT_BEEP_ON_BREAKPOINT})'
}

class IntelliJAddonSettings(SettingsPanel):
	title = "IntelliJ Improved"

	def makeSettings(self, settingsSizer):
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		conf = config.conf[CONF_KEY]
		self.beepOnChange= sHelper.addItem(wx.CheckBox(self, label="Beep when status bar changes"))
		self.beepOnChange.SetValue(conf[BEEP_ON_STATUS_CHANGED_KEY])
		self.beepOnClear= sHelper.addItem(wx.CheckBox(self, label="Beep when status bar is cleared"))
		self.beepOnClear.SetValue(conf[BEEP_ON_STATUS_CLEARED_KEY])
		self.speakOnChange = sHelper.addItem(wx.CheckBox(self, label="Automatically read status bar changes"))
		self.speakOnChange.SetValue(conf[SPEAK_ON_STATUS_CHANGED_KEY])
		self.beepBeforeReading = sHelper.addItem(wx.CheckBox(self, label="Beep before status bar change is read"))
		self.beepBeforeReading.SetValue(conf[BEEP_BEFORE_READING_KEY])
		self.beepAfterReading = sHelper.addItem(wx.CheckBox(self, label="Beep after status bar change is read"))
		self.beepAfterReading.SetValue(conf[BEEP_AFTER_READING_KEY])
		self.interruptSpeech = sHelper.addItem(wx.CheckBox(self, label="Interrupt speech when automatically reading status bar changes"))
		self.interruptSpeech.SetValue(conf[INTERRUPT_SPEECH_KEY])
		self.beepOnBreakpoint = sHelper.addItem(wx.CheckBox(self, label="Beep when breakpoint is detected on current line"))
		self.beepOnBreakpoint.SetValue(conf[BEEP_ON_BREAKPOINT_KEY])

	def onSave(self):
		conf = config.conf[CONF_KEY]
		conf[BEEP_ON_STATUS_CHANGED_KEY] = self.beepOnChange.Value
		conf[BEEP_ON_STATUS_CLEARED_KEY] = self.beepOnClear.Value
		conf[SPEAK_ON_STATUS_CHANGED_KEY] = self.speakOnChange.Value
		conf[INTERRUPT_SPEECH_KEY] = self.interruptSpeech.Value
		conf[BEEP_BEFORE_READING_KEY] = self.beepBeforeReading.Value
		conf[BEEP_AFTER_READING_KEY] = self.beepAfterReading.Value
		conf[BEEP_ON_BREAKPOINT_KEY] = self.beepOnBreakpoint.Value
		setGlobalVars()

@dataclass
class Vars:
	beepOnChange: bool = DEFAULT_BEEP_ON_CHANGE
	beepOnClear: bool = DEFAULT_BEEP_ON_STATUS_CLEARED
	speakOnChange: bool = DEFAULT_SPEAK_ON_CHANGE
	interruptSpeech: bool = DEFAULT_INTERRUPT_SPEECH
	beepBeforeReading: bool = DEFAULT_BEEP_BEFORE_READING
	beepAfterReading: bool = DEFAULT_BEEP_AFTER_READING
	beepOnBreakpoint: bool = DEFAULT_BEEP_ON_BREAKPOINT

vars = Vars()

def setGlobalVars():
	conf = config.conf[CONF_KEY]
	vars.beepOnChange = conf[BEEP_ON_STATUS_CHANGED_KEY]
	vars.beepOnClear = conf[BEEP_ON_STATUS_CLEARED_KEY]
	vars.speakOnChange = conf[SPEAK_ON_STATUS_CHANGED_KEY]
	vars.interruptSpeech = conf[INTERRUPT_SPEECH_KEY]
	vars.beepBeforeReading = conf[BEEP_BEFORE_READING_KEY]
	vars.beepAfterReading = conf[BEEP_AFTER_READING_KEY]
	vars.beepOnBreakpoint = conf[BEEP_ON_BREAKPOINT_KEY]

# initialize conf in case being run for the first time
if config.conf.get(CONF_KEY) is None:
	config.conf[CONF_KEY] = {}
setGlobalVars()


class EnhancedEditableText(EditableTextWithoutAutoSelectDetection):
	__gestures = (
		# these IntelliJ commands change caret position, so they should trigger reading new line position
		{ 
			g: "caret_moveByLine"
			for g in (
				"kb:alt+downArrow",
				"kb:alt+upArrow",
				"kb:control+[",
				"kb:control+]",
				"kb:f2",
				"kb:shift+f2",
				"kb:control+b",
				"kb:control+alt+leftArrow",
				"kb:control+alt+rightArrow",
				"kb:control+y",
				"kb:f3",
				"kb:shift+f3",
				"kb:control+u",
				"kb:control+shift+backspace",
				"kb:control+/",
				"kb:alt+j",
				"kb:alt+control+downArrow",
				"kb:alt+control+upArrow",
				"kb:control+z",
				"kb:f8",
				"kb:alt+shift+f8",
				"kb:f7",
				"kb:alt+shift+f7",
				"kb:shift+f7",
				"kb:shift+f8",
				"kb:alt+f10",
			)
		} |
		# these gestures trigger selection change
		{
			g: "caret_changeSelection"
			for g in (
				"kb:control+w",
				"kb:control+shift+w",
				"kb:alt+shift+j",
				"kb:control+shift+[",
				"kb:control+shift+]",
			)
		}
	)

	shouldFireCaretMovementFailedEvents = True

	def event_caretMovementFailed(self, gesture):
		PlaySound('SystemExclamation', SND_ASYNC | SND_ALIAS)

	def event_caret(self):
		super().event_caret()
		if vars.beepOnBreakpoint:
			# delay checkForBreakpoint to insure that the line number in the status bar is updated
			callLater(100, self.checkForBreakpoint)

	def checkForBreakpoint(self):
		foregroundObj = api.getForegroundObject()
		appModule = foregroundObj.appModule
		if appModule.hasBreakpointOnCurrentLine():
			tones.beep(300, 150)


class AppModule(appModuleHandler.AppModule):
	def __init__(self, pid, appName=None):
		super(AppModule, self).__init__(pid, appName)
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(IntelliJAddonSettings)
		self.status = None
		self.lineNumber = None
		self.bookmarks = None
		self.lastCheckedBreakpointFile = None
		self.lastCheckedBreakpointLine = None
		self.watcher = StatusBarWatcher(self)
		self.watcher.start()

	def terminate(self):
		self.watcher.stopped = True
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(IntelliJAddonSettings)

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		if obj.role == EDITABLE_TEXT:
			clsList.insert(0, EnhancedEditableText)
	
	@script(
		"Read the status bar",
		gesture = 'kb:NVDA+i',
		category="IntelliJ")
	def script_readStatusBar(self, gesture):
		status = self.getStatusBar()
		if status is None:
			ui.browseableMessage(isHtml=True, message="""
				<p>Failed to read the status bar text. Make sure the "status text" status bar widget is enabled:</p>
				<ol>
					<li>
						Open the Search All panel by double tapping shift
					</li>
					<li>
						Search for "Status Bar Widgets" and activate it with Enter.
					</li>
					<li>
						Find  "status text" in the list.
					</li>
					<li>
						Activate it by pressing spacebar. (It  might not report whether it is checked or not)
					</li>
					<li>
						Exit the widgets list by pressing Esc.
					</li>
					<li>
						Retry reading the error/warning description.
					</li>
				</ol>
			""")
		else:
			if status.simpleFirstChild and status.simpleFirstChild.name:
				msg = status.simpleFirstChild.name
				ui.message(msg)

	def getStatusBar(self, refresh: bool = False):
		obj = api.getForegroundObject()
		if not obj or not obj.appModule or not obj.appModule.appName == "idea64":
			# Ignore cases nvda is lost
			return
		if self.status and not refresh:
			return self.status
		else:
			obj = obj.simpleFirstChild
			while obj is not None:
				# This first searching pattern is for IntelliJ post v2023
				if obj.name == "Status Bar":
					child = obj.simpleFirstChild
					if child.role == STATUSBAR:
						obj = child
						self.status = obj
						break
				# this second searching pattern is for IntelliJ pre v2023
				if obj.role == STATUSBAR:
					self.status = obj
					break

				obj = obj.simpleNext

			return obj

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

	@script("Toggle beep on breakpoint", category="IntelliJ")
	def script_toggleBeepOnBreakpoint(self, gesture):
		newVal = not vars.beepOnBreakpoint
		config.conf[CONF_KEY][BEEP_ON_BREAKPOINT_KEY] = newVal
		vars.beepOnBreakpoint = newVal
		ui.message("Enabled beep on breakpoint" if newVal else "Disabled beep on breakpoint")

	@script(
		"Read current line number from IntelliJ",
		gesture="kb:nvda+alt+l",
		category="IntelliJ"
	)
	def script_readLineNumber(self, gesture):
		lineNumber = self.getLineNumber()
		if lineNumber is None:
			ui.browseableMessage(isHtml=True, message="""
				<p>Failed to read the line number. Make sure the editor is open and the "Line:Column Number" status bar widget is enabled:</p>
				<ol>
					<li>
						Open the Search All panel by double tapping shift
					</li>
					<li>
						Search for "Status Bar Widgets" and activate it with Enter.
					</li>
					<li>
						Find  "Line:Column Number" in the list.
					</li>
					<li>
						Activate it by pressing spacebar. (It  might not report whether it is checked or not)
					</li>
					<li>
						Exit the widgets list by pressing Esc.
					</li>
					<li>
						Retry reading the line number.
					</li>
				</ol>
			""")
		else:
			if lineNumber.name:
				ui.message(f"Line {lineNumber.name}")

	def getLineNumber(self):
		obj = api.getForegroundObject()
		if not obj or not obj.appModule or not obj.appModule.appName == "idea64":
			# Ignore cases nvda is lost
			return
		if self.lineNumber:
			return self.lineNumber

		obj = obj.simpleFirstChild
		while obj is not None:
			if obj.name == "Status Bar" or obj.role == STATUSBAR:
				child = obj.simpleFirstChild

				while child is not None:
					if child.description and child.description.lower() == "go to line":
						self.lineNumber = child
						return child
					child = child.simpleNext

			obj = obj.simpleNext

		return None

	def hasBreakpointOnCurrentLine(self):
		lineObj = self.getLineNumber()
		if not lineObj or not lineObj.name or ":" not in lineObj.name:
			return False

		try:
			line = int(lineObj.name.split(":")[0])
		except ValueError:
			return False

		# Get file name from window title
		fg = api.getForegroundObject()
		if not fg or not fg.windowText:
			return False

		# Example: 'sample – Main.java' => Main.java
		windowTitle = fg.windowText
		if "–" in windowTitle:
			fileName = windowTitle.split("–")[-1].strip()
		else:
			fileName = windowTitle.strip()

		# optimisation to return early if we got an event for the same line number and file we just checked
		if self.lastCheckedBreakpointFile == fileName and self.lastCheckedBreakpointLine == line:
			return False  # Already checked

		self.lastCheckedBreakpointFile = fileName
		self.lastCheckedBreakpointLine = line

		breakpointTree = self.getBreakpointTree()
		if not breakpointTree:
			return False

		category = breakpointTree.simpleFirstChild
		while category:
			# Check different types of breakpoints (Java, conditional, etc.), although line breakpoints seem to be the only breakpoint type that provides a line number
			subItem = category.simpleFirstChild
			while subItem:
				name = subItem.name.lower()
				if fileName.lower() in name:
					if f":{line}" in name:
						return True
				subItem = subItem.simpleNext
			category = category.simpleNext

		return False

	def getBreakpointTree(self):
		# Unable to cache breakpoint tree due to object becoming stale
		root = self.getBookmarks()
		if not root:
			return None

		tree = root.simpleLastChild.simpleFirstChild
		while tree:
			if tree.name and tree.name.lower() == "breakpoints":
				break
			tree = tree.simpleNext

		return tree

	def getBookmarks(self):
		obj = api.getForegroundObject()
		if not obj or not obj.appModule or not obj.appModule.appName == "idea64":
			# Ignore cases nvda is lost
			return
		if self.bookmarks:
			return self.bookmarks

		obj = obj.simpleFirstChild
		while obj is not None:
			if obj.name and obj.name .lower() == "bookmarks tool window":
				self.bookmarks = obj
				break

			obj = obj.simpleNext

		return obj


class StatusBarWatcher(threading.Thread):
	STATUS_CHANGED_TONE = 1000
	AFTER_TONE = 800
	STATUS_CLEARED_TONE = 500
	SLEEP_DURATION = 0.25
	REFRESH_INTERVAL = 5 # seconds

	def __init__(self, addon):
		super(StatusBarWatcher, self).__init__()
		self.stopped = False
		self._lastText = ""
		self.addon = addon
		self.lastRefresh = time.time()

	def _statusBarFound(self, obj):
		# Don't use simpleFirstChild here since we need to know wether the error is fixed
		if not obj.firstChild:
			return

		msg = obj.firstChild.name

		if self._lastText != msg:
			if msg and vars.beepOnChange:
				tones.beep(StatusBarWatcher.STATUS_CHANGED_TONE, 50)
			elif not msg and vars.beepOnClear:
				tones.beep(StatusBarWatcher.STATUS_CLEARED_TONE, 50)

			if msg and vars.speakOnChange:
				seq = []
				if vars.beepBeforeReading:
					seq.append(speech.commands.BeepCommand(StatusBarWatcher.STATUS_CHANGED_TONE, 50))
				seq.append(msg)
				if vars.beepAfterReading:
					seq.append(speech.commands.BeepCommand(StatusBarWatcher.AFTER_TONE, 50))
				speech.speak(seq, priority= speech.Spri.NOW if vars.interruptSpeech else speech.Spri.NORMAL)

			self._lastText = msg

	def _runLoopIteration(self):
		now = time.time()
		shouldRefresh = now - self.lastRefresh > StatusBarWatcher .REFRESH_INTERVAL
		if shouldRefresh:
			self.lastRefresh = now
		status = self.addon.getStatusBar(refresh=shouldRefresh)
		if status:
			self._statusBarFound(status)

	def run(self):
		while not self.stopped:
			try:
				self._runLoopIteration()
			except Exception as error:
				log.warn("Error on watcher thread: %s" % error)
			time.sleep(StatusBarWatcher.SLEEP_DURATION)
