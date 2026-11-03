"""The shared gifting vocabulary.

Recipients, chats and the rulebook all describe situations with these same values, which
is what lets the agent pick exactly the rules that apply to "coworker, farewell".
"""

from enum import StrEnum


class Relationship(StrEnum):
    PARTNER = "partner"
    PARENT = "parent"
    CHILD = "child"
    SIBLING = "sibling"
    GRANDPARENT = "grandparent"
    RELATIVE = "relative"
    FRIEND = "friend"
    COWORKER = "coworker"
    MANAGER = "manager"
    CLIENT = "client"
    TEACHER = "teacher"
    NEIGHBOR = "neighbor"
    OTHER = "other"


class Occasion(StrEnum):
    BIRTHDAY = "birthday"
    ANNIVERSARY = "anniversary"
    HOLIDAY = "holiday"
    WEDDING = "wedding"
    BABY = "baby"
    GRADUATION = "graduation"
    HOUSEWARMING = "housewarming"
    FAREWELL = "farewell"
    RETIREMENT = "retirement"
    THANK_YOU = "thank_you"
    GET_WELL = "get_well"
    JUST_BECAUSE = "just_because"
    OTHER = "other"
