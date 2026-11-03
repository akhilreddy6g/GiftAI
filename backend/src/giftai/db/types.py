"""Column types reused across models."""

from enum import StrEnum

from sqlalchemy import Enum


def string_enum[EnumT: StrEnum](enum_class: type[EnumT]) -> Enum:
    """Store a StrEnum by value as text guarded by a CHECK constraint.

    Unlike a native Postgres enum type, adding a value later is a plain constraint change.
    """
    return Enum(
        enum_class,
        native_enum=False,
        create_constraint=True,
        length=max(len(member.value) for member in enum_class),
        values_callable=lambda members: [member.value for member in members],
        name=enum_class.__name__.lower(),
    )
