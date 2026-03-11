# Workaround for top-level ``mcp`` package shadowing.
#
# Several task preprocess scripts (e.g. canvas-art-manager, canvas-homework-
# grader-python) add the ``utils/`` directory to ``sys.path`` so they can do
# short imports like ``from app_specific.poste.ops import clear_folder``.
# See for example canvas-art-manager/preprocess/main.py lines 69-72:
#
#     utils_dir = toolathlon_root / "utils"
#     sys.path.insert(0, str(utils_dir))
#     from app_specific.poste.ops import clear_folder
#
# With ``utils/`` on sys.path, a later ``import mcp`` (triggered deep inside
# agents.mcp.server -> ``from mcp import ClientSession``) resolves to THIS
# file instead of the installed ``mcp`` SDK, because Python finds
# ``utils/mcp/__init__.py`` before reaching site-packages.
#
# The guard below detects that situation (``__name__ == "mcp"`` means we were
# loaded as the top-level ``mcp`` rather than as ``utils.mcp``) and
# transparently replaces ourselves in ``sys.modules`` with the real package.

import sys as _sys

if __name__ == "mcp":
    import importlib as _importlib
    import pathlib as _pathlib

    # Remove this (wrong) module so importlib can search again.
    del _sys.modules["mcp"]

    # Temporarily hide our parent directory from sys.path so the finder
    # skips us and discovers the real site-packages ``mcp`` instead.
    _this_parent = str(_pathlib.Path(__file__).resolve().parent.parent)
    _hidden = []
    for _p in list(_sys.path):
        try:
            if str(_pathlib.Path(_p).resolve()) == _this_parent:
                _hidden.append(_p)
                _sys.path.remove(_p)
        except (OSError, ValueError):
            pass

    try:
        _real_mcp = _importlib.import_module("mcp")
        _sys.modules["mcp"] = _real_mcp
    finally:
        # Restore the hidden entries so other ``utils.*`` imports still work.
        for _p in reversed(_hidden):
            _sys.path.insert(0, _p)
