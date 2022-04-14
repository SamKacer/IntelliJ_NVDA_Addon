# IntelliJ Support App Module for NVDA
#Copyright (C) 2019-2020 Samuel Kacer
#GNU GENERAL PUBLIC LICENSE V2
#Author: Samuel Kacer <samuel.kacer@gmail.com>
#https://github.com/SamKacer/IntelliJ_NVDA_Addon

import appModuleHandler
import tones
import controlTypes
from editableText import EditableTextWithoutAutoSelectDetection
from logHandler import log
from scriptHandler import script
import speech
import ui
import api
import threading
import time
from winsound import PlaySound, SND_ASYNC, SND_ALIAS

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
		self.watcher = StatusBarWatcher()
		self.watcher.start()

	def terminate(self):
		self.watcher.stopped = True

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		if obj.role == controlTypes.ROLE_EDITABLETEXT:
			clsList.insert(0, EnhancedEditableText)
	
	@script(gesture = 'kb:NVDA+i')
	def script_readStatusBar(self, gesture):
		obj = api.getForegroundObject().simpleFirstChild
		tones.beep(550,50)
		while obj is not None:
			if obj.role is controlTypes.ROLE_STATUSBAR:
				msg = obj.simpleFirstChild.name
				ui.message(msg)
				return
			obj = obj.simpleNext
		ui.message('couldnt find status bar')

class StatusBarWatcher(threading.Thread):
	ERROR_FOUND_TONE = 1000
	ERROR_FIXED_TONE = 2000
	sleepDuration = 0.25

	def __init__(self, beepOnError=True, speakOnError=True, interruptSpeech=False):
		super(StatusBarWatcher, self).__init__()
		self.stopped = False
		self._lastText = ""
		self.beepOnError = beepOnError
		self.speakOnError = speakOnError
		self.interruptSpeech = interruptSpeech

	def _statusBarFound(self, obj):
		# Don't use simpleFirstChild here since we need to know wether the error is fixed
		if not obj.firstChild:
			return

		msg = obj.firstChild.name

		if self._lastText != msg:
			if self.beepOnError:
				tones.beep(self.ERROR_FOUND_TONE if msg else self.ERROR_FIXED_TONE, 50)

			if msg and self.speakOnError:
				if self.interruptSpeech:
					speech.cancelSpeech()

				ui.message(msg)

			self._lastText = msg

	def _runLoopIteration(self):
		obj = api.getForegroundObject()

		if obj is None or not obj.appModule.appName == "idea64":
			# Ignore cases nvda is lost
			return

		obj = obj.simpleFirstChild

		while obj is not None:
			if obj.role is controlTypes.ROLE_STATUSBAR:
				self._statusBarFound(obj)
				break

			obj = obj.simpleNext

	def run(self):
		while not self.stopped:
			try:
				self._runLoopIteration()
			except Exception as error:
				log.warn("Error on watcher thread: %s" % error)
			time.sleep(self.sleepDuration)
