# IntelliJ_NVDA_Addon
Addon for NVDA that adds support for using IntelliJ.
Current features are:

* when caret moves to different line, the line at the new position is read out
* when selection changes it is read out
* when the status bar text has changed, NVDA beeps and speaks it
    - this includes reading the error description if the caret landed on one
    - configurable in settings
* command to read status bar (NVDA + I)

## How to install
1. Download latest release or build by running scons
2. install like a normal addon by opening the generated addon file with NVDA (should open with NVDA by default)

## How to fix the status bar text not being read

If the status bar text isn't read out, such as for automatically reading error/warning descriptions, then it is likely that the status bar text widget isn't enabled. Since IntelliJ version 2023.3, it seems to be disabled by default, so it has to be manually enabled. To do so, do the following:

1. Open the Search All panel by double tapping shift
2. Search for "Status Bar Widgets" and activate it with Enter.
3. Find  "status text" in the list.
4. Activate it by pressing spacebar. (It  might not report whether it is checked or not)
5. Exit the widgets list by pressing Esc.
6. Retry reading the error/warning description.

You can test whether the status bar text can now be read successfully by jumping to an error/warning with F2 and pressing NVDA + I.

## Tips for using IntelliJ
### Checking errors/warnings
#### When focused inside a file editor:
* F2/ shift + F2 : go to next/previous error or warning
#### When editor cursor is on error/warning:
* NVDA  + I: Quickly read error description displayed in status bar
* ctrl + F1: open message box with more detailed error description
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

## Changelog
### Version 1.4.0
* Read line after pressing Control + Z
### Version 1.3.4
* Updated NVDA last tested version to 2024.4.1
* Display help message on enabling the status bar text widget if unable to read the status text
### Version 1.3.3
* Fixed not being able to find the status bar in IntelliJ v2023.1
### Version 1.3.2
* compatible with NVDA version 2023.1 and beyond
### Version 1.3.1
* fixed the status bar sometimes being read while not in IntelliJ
### Version 1.3.0
* added feature for automatically reading errors and other status bar changes (thanks to Thiago @thgcode for the contribution!)
* reading status bar with NVDA + I is much faster
* compatible with NVDA 2022+
