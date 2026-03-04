"""Detects if this package is loaded from multiple locations."""
from talon import actions

_duplicate = False
try:
    actions.user.rig_core_version()
    _duplicate = True
except Exception:
    pass

if _duplicate:
    print("============================================================")
    print("DUPLICATE PACKAGE: talon-rig-core (user.rig_core)")
    print("")
    print("  talon-rig-core is already loaded from another location.")
    print("  If using talon-gamekit, remove your standalone talon-rig-core clone.")
    print("  Only one copy of talon-rig-core can exist in talon/user.")
    print("============================================================")
    raise RuntimeError(
        "Duplicate package: talon-rig-core (user.rig_core) is already loaded."
    )
