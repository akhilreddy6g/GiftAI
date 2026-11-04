"""Builds the gifting rulebook from books and papers that stay on the developer's machine.

extract -> draft -> group -> review -> seed. An LLM drafts candidate rules from each
chapter, similar candidates are grouped across sources, a person picks or rewrites one
rule per group, and the approved rulebook (committed to the repo) is loaded into the
database.
"""
