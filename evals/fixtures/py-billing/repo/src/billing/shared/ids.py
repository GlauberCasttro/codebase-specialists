"""Prefixed identifiers: inv_, pay_, je_ ..."""
import uuid


def new_id(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid.uuid4().hex[:20])
