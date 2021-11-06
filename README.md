# IntelliJ_NVDA_Addon
Addon for NVDA that adds support for using IntelliJ.
Current features are:
* when caret moves to different line, the line at the new position is read out
* when selection changes it is read out
* command to read status bar (NVDA + I)

## How to install
1. Download latest release or build by running scons
2. install like a normal addon by opening the generated addon file with NVDA (should open with NVDA by default)

## Tips for using IntelliJ
### Checking errors/warnings
When focused inside a file editor:
* F2/ shift + F2 : go to next/previous error or warning
When editor cursor is on error/warning:
* ctrl + F1: show error description
* alt + enter: open list of quick actions

### Navigating
* ctrl + tab/ ctrl + shift + tab: switch between editors and views
* alt + number: move to coresponding numbered view
* F12: go to last non-editor view
inside editor:
* alt + up arrow/ alt + down arrow: jump to previous/next class, field, or method declaration
* ctrl + {/ ctrl + }: GO TO PREVIOUS/NEXT MATCHING BRACE
* ctrl + B: go to declaration
* ctrl + shift + B: go to type declaration
* ctrl + G: go to line
* ctrl + N: go to class
* shift, shift: "finad anything" dialogue

### VCS
* ctrl + K: make commit
* ctrl + shift + K: push
* ctrl + alt + Z: revert

### Misc.
* ctrl + shift + A: search for action
* ctrl + alt + L: format code
* alt + F7: find usages
* alt + shift + F9: open run dialogue (note: if editor caret is on unit test, this will also autogenerate a run configuration for running that specific test case)
