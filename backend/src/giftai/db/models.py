"""Imports every ORM model so that ``Base.metadata`` knows the full schema.

Alembic imports this module before comparing models with the database. Each feature that
stores data adds its ``models`` module here.
"""
