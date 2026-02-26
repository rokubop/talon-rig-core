"""Rig Core — Action-based lazy loading for consumer rigs

Consumer rigs get the core module via:
    core = actions.user.rig_core()

Then build class hierarchies at runtime in app.register("ready").
"""

from talon import Module

mod = Module()


@mod.action_class
class Actions:
    def rig_core():
        """Get rig-core module with all base classes and utilities"""
        from . import src
        return src
