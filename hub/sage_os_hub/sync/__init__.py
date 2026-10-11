"""Sync-ready data model (D27 "do now", D28; roadmap Y1). No server yet: this package gives every record an ID
that can't clash between devices, names the device each change comes from, and (later parts) records changes
in a log that sync will ship.
"""
from .device import Device
from . import manifest
from .ids import is_id, new_id

__all__ = ["Device", "is_id", "manifest", "new_id"]
