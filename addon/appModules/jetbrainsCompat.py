# controlTypes changed from module-level constants to Role/State enums in NVDA 2022.
import controlTypes
from buildVersion import version_year

if version_year >= 2022:
    EDITABLE_TEXT  = controlTypes.Role.EDITABLETEXT
    STATUSBAR      = controlTypes.Role.STATUSBAR
    ROLE_TAB       = controlTypes.Role.TAB
    ROLE_TREEVIEW  = controlTypes.Role.TREEVIEW
    STATE_SELECTED = controlTypes.State.SELECTED
else:
    EDITABLE_TEXT  = controlTypes.ROLE_EDITABLETEXT
    STATUSBAR      = controlTypes.ROLE_STATUSBAR
    ROLE_TAB       = controlTypes.ROLE_TAB
    ROLE_TREEVIEW  = controlTypes.ROLE_TREEVIEW
    STATE_SELECTED = controlTypes.STATE_SELECTED
