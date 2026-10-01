"""Bookshelf: Sage OS's built-in knowledge base (DECISIONS D2, D6, D7, D9-D12; roadmap K1-K11).

The vault is plain markdown on disk and the only source of truth (BookShelf invariant I3);
everything Sage OS keeps about it -- like the search index -- is a cache rebuilt from the files.
"""
from .index import SearchIndex
from .proposals import ProposalError, SensitiveContent, StaleProposal
from .screen import screen
from .vault import Vault
from .writer import Writer

__all__ = ["ProposalError", "SearchIndex", "SensitiveContent", "StaleProposal", "Vault", "Writer", "screen"]
