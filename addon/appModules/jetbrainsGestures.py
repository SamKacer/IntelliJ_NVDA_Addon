# Gesture tiers for JetBrains IDEs.
# TIER1: universal — all JetBrains IDEs, all default keymaps.
# TIER2: IntelliJ / PyCharm default keymap only.
# TIER3: debugger-specific (IntelliJ / PyCharm default keymap).

TIER1_MOVE_BY_LINE = frozenset({
    "kb:f2",                       # Next highlighted error
    "kb:shift+f2",                 # Previous highlighted error
    "kb:control+b",                # Go to declaration
    "kb:control+alt+leftArrow",    # Navigate back
    "kb:control+alt+rightArrow",   # Navigate forward
    "kb:control+shift+backspace",  # Last edit location
    "kb:control+z",                # Undo
})

TIER1_SELECTION = frozenset({
    "kb:control+w",       # Extend selection (structural)
    "kb:control+shift+w", # Shrink selection (structural)
})

TIER2_MOVE_BY_LINE = frozenset({
    "kb:alt+downArrow",          # Move statement down
    "kb:alt+upArrow",            # Move statement up
    "kb:control+[",              # Code block start
    "kb:control+]",              # Code block end
    "kb:f3",                     # Find next
    "kb:shift+f3",               # Find previous
    "kb:control+u",              # Go to super method/class
    "kb:control+/",              # Toggle line comment
    "kb:alt+j",                  # Add next occurrence
    "kb:alt+control+downArrow",  # Clone caret below
    "kb:alt+control+upArrow",    # Clone caret above
    "kb:control+y",              # Delete line
})

TIER2_SELECTION = frozenset({
    "kb:alt+shift+j",       # Unselect last occurrence
    "kb:control+shift+[",   # Select to block start
    "kb:control+shift+]",   # Select to block end
})

TIER3_MOVE_BY_LINE = frozenset({
    "kb:f8",            # Step over
    "kb:alt+shift+f8",  # Force step over
    "kb:f7",            # Step into
    "kb:alt+shift+f7",  # Force step into
    "kb:shift+f7",      # Smart step into
    "kb:shift+f8",      # Step out
    "kb:alt+f10",       # Show execution point
})

_ALL_MOVE_BY_LINE = TIER1_MOVE_BY_LINE | TIER2_MOVE_BY_LINE | TIER3_MOVE_BY_LINE
_ALL_SELECTION    = TIER1_SELECTION | TIER2_SELECTION
