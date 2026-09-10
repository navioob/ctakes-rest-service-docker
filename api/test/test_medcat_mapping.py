#!/usr/bin/env python3
"""Self-check for the MedCAT type_id -> category mapping used by parse_medcat_to_json.
Run directly: python test_medcat_mapping.py  (no server, no model pack required)

classify_tui() takes an explicit type_id_category_map so this stays offline -
the real map is built per-loaded-pack by _get_type_id_category_map(), which
does require the model pack (see api/README.md).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.functions import classify_tui

# Fake type_id -> category map, standing in for one built from a real pack's
# cdb.type_id2info (numeric ids are per-build/opaque; only the category
# matters here).
FAKE_MAP = {
    "37552161": "anatomical_sites",
    "28321150": "procedures",
    "67667581": "symptoms",
    "9090192": "diagnosis",
    "91187746": "medications",
}

CASES = [
    (["37552161"], "anatomical_sites"),
    (["28321150"], "procedures"),
    (["67667581"], "symptoms"),
    (["9090192"], "diagnosis"),
    (["91187746"], "medications"),
    (["unknown_id"], None),                    # unknown type_id -> dropped, not crash
    (["unknown_id", "9090192"], "diagnosis"),  # first known type_id in the list wins
    ([], None),
]


def test_classify_tui():
    for type_ids, expected in CASES:
        actual = classify_tui(type_ids, FAKE_MAP)
        assert actual == expected, f"classify_tui({type_ids}) = {actual!r}, expected {expected!r}"
    print(f"OK - {len(CASES)} type_id mapping cases passed")


if __name__ == "__main__":
    test_classify_tui()
