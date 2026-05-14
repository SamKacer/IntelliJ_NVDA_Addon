import re
from collections import deque

from .jetbrainsCompat import STATUSBAR, ROLE_TAB, ROLE_TREEVIEW, STATE_SELECTED

# Widgets that appear in every JetBrains status bar but carry no useful info.
_STATUS_NOISE = frozenset({
    "utf-8", "crlf", "lf", "cr",
    "2 spaces", "4 spaces",
    "spaces: 2", "spaces: 4",
    "tab size: 2", "tab size: 4",
    "indent: 2", "indent: 4",
})

# Accessible name used by JAB for the status bar panel in New UI (2024.2+).
# The old UI exposes a proper STATUSBAR role; the new UI uses a generic PANEL
# named "Status Bar" instead. This name is always English in JAB regardless
# of the IDE's display language.
_STATUS_BAR_PANEL_NAME = "status bar"


def _isObjectValid(obj, expectedRole=None):
    """Forces a COM read to detect stale NVDAObject references."""
    try:
        if obj is None:
            return False
        if expectedRole is not None and obj.role != expectedRole:
            return False
        _ = obj.name
        return True
    except Exception:
        return False


def findObject(root, predicate, maxDepth=8, maxNodes=200):
    """BFS over NVDA accessibility tree. root itself is not tested."""
    if root is None:
        return None
    queue = deque()
    child = root.simpleFirstChild
    if child:
        queue.append((child, 1))
    visited = 0
    while queue:
        obj, depth = queue.popleft()
        while obj is not None:
            if visited >= maxNodes:
                return None
            visited += 1
            try:
                if predicate(obj):
                    return obj
            except Exception:
                pass
            if depth < maxDepth:
                fc = obj.simpleFirstChild
                if fc is not None:
                    queue.append((fc, depth + 1))
            obj = obj.simpleNext
    return None


def _isStatusBarElement(obj):
    """
    Match the status bar in both classic and New UI.

    Classic UI (≤ 2024.1): STATUSBAR role.
    New UI (2024.2+): generic PANEL with accessible name 'Status Bar'.
    """
    try:
        if obj.role == STATUSBAR:
            return True
        if (obj.name or "").strip().lower() == _STATUS_BAR_PANEL_NAME:
            return True
    except Exception:
        pass
    return False


def collectStatusBarText(statusBar, maxDepth=4, maxNodes=80):
    """
    Collect visible text from a JetBrains status bar.

    Works with both:
    - Classic UI: single text child with the error/warning message.
    - New UI 2024.2+: multiple independent widgets as separate children/descendants.

    Uses firstChild at the top level so a cleared bar (empty firstChild) returns "".
    Uses simpleFirstChild for descendants to skip hidden/invisible items.
    Filters _STATUS_NOISE and deduplicates before joining with " | ".
    """
    if statusBar is None:
        return ""
    parts = []
    seen = set()
    queue = deque()
    try:
        root_child = statusBar.firstChild
        if root_child is not None:
            queue.append((root_child, 1))
    except Exception:
        return ""
    visited = 0
    while queue and visited < maxNodes:
        obj, depth = queue.popleft()
        while obj is not None and visited < maxNodes:
            visited += 1
            try:
                name = obj.name
                if isinstance(name, str):
                    text = name.strip()
                    if text and text.lower() not in _STATUS_NOISE and text not in seen:
                        parts.append(text)
                        seen.add(text)
            except Exception:
                pass
            if depth < maxDepth:
                try:
                    fc = obj.simpleFirstChild
                    if fc is not None:
                        queue.append((fc, depth + 1))
                except Exception:
                    pass
            try:
                obj = obj.simpleNext
            except Exception:
                break
    return " | ".join(parts)


def isDescendantOfStatusBar(obj, maxDepth=5):
    """
    Walk the parent chain to check whether obj lives inside the status bar.

    Handles both classic UI (STATUSBAR role) and New UI 2024.2+ (PANEL named
    'Status Bar'). maxDepth is intentionally small to limit JAB round-trips
    per event_nameChange call.
    """
    if obj is None:
        return False
    current = obj
    for _ in range(maxDepth):
        try:
            parent = current.parent
        except Exception:
            return False
        if parent is None:
            return False
        if _isStatusBarElement(parent):
            return True
        current = parent
    return False


_LINE_COL_RE        = re.compile(r"^\d+:\d+$")
_BREAKPOINT_ITEM_RE = re.compile(r".+:\d+")
_TITLE_SEP_RE       = re.compile(r"\s[–—-]\s")
_FILENAME_EXT_RE    = re.compile(r"[\w\-. ]+\.\w{1,10}$")


def _isLineColWidget(obj):
    # Primary: name \d+:\d+ (locale-independent). Fallback: English description.
    try:
        if _LINE_COL_RE.match(obj.name or ""):
            return True
        if (obj.description or "").lower() == "go to line":
            return True
    except Exception:
        pass
    return False


def _isSelectedEditorTab(obj):
    # JetBrains editor tabs: role=TAB with SELECTED state when active.
    try:
        return obj.role == ROLE_TAB and STATE_SELECTED in obj.states
    except Exception:
        return False


def _isBreakpointTree(obj):
    # Heuristic: TREEVIEW whose sub-items contain "filename:linenum" patterns.
    # Samples up to 5 categories x 10 items to avoid false-positives from
    # project/structure trees (also TREEVIEW).
    try:
        if obj.role != ROLE_TREEVIEW:
            return False
        category = obj.simpleFirstChild
        cat_count = 0
        while category and cat_count < 5:
            sub = category.simpleFirstChild
            sub_count = 0
            while sub and sub_count < 10:
                if _BREAKPOINT_ITEM_RE.search(sub.name or ""):
                    return True
                sub = sub.simpleNext
                sub_count += 1
            category = category.simpleNext
            cat_count += 1
    except Exception:
        pass
    return False


def _filenameFromWindowTitle(windowText):
    # Handles "ProjectName – File.java" and "File.java – ProjectName" orderings.
    if not windowText:
        return None
    for part in _TITLE_SEP_RE.split(windowText):
        part = part.strip()
        if _FILENAME_EXT_RE.match(part):
            return part
    return None
