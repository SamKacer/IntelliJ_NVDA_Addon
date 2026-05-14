import re
from collections import deque

from jetbrainsCompat import STATUSBAR, ROLE_TAB, ROLE_TREEVIEW, STATE_SELECTED


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
