"""Bookshelf: Sage OS's built-in knowledge base (DECISIONS D2, D6, D7; roadmap K1-K11).

The vault is plain markdown on disk and the only source of truth (BookShelf invariant I3);
everything Sage OS keeps about it is a cache rebuilt from the files.
"""
from .vault import Vault

__all__ = ["Vault"]
