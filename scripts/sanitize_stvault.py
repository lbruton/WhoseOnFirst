#!/usr/bin/env python3
"""Sanitize a .stvault export for safe use in the dev environment.

Strips all PII from `team_members` (name + phone), replacing with a fixed
phonetic-alphabet roster and FCC-reserved 555-01xx fictional numbers.
Preserves IDs, active flags, rotation order, and timestamps so the
`schedule` rows and the 48h Tue-Wed shift pattern stay intact.

Other tables (shifts, schedule, settings) are copied through unchanged.
The export format already omits `users` and `notification_log`, so there
is nothing auth- or history-sensitive to strip.

Usage:
    python3 scripts/sanitize_stvault.py <input.stvault> <output.stvault>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Phonetic-alphabet roster keyed by rotation_order. Order 0-6 are active;
# the last entry is reserved for the single inactive slot (rotation_order=None).
# Phone numbers use the FCC-reserved 555-0100 through 555-0199 block, which
# is guaranteed never to be assigned to a real subscriber.
ACTIVE_ROSTER = [
    ("Alice Alpha", "+15550100101"),
    ("Bob Bravo", "+15550100102"),
    ("Carol Charlie", "+15550100103"),
    ("Dave Delta", "+15550100104"),
    ("Eve Echo", "+15550100105"),
    ("Frank Foxtrot", "+15550100106"),
    ("Grace Golf", "+15550100107"),
]
INACTIVE_NAME = "Henry Hotel"
INACTIVE_PHONE = "+15550100108"


def sanitize(payload: dict) -> dict:
    members = payload["data"]["team_members"]

    # Sort active members by rotation_order so the phonetic alphabet reads
    # naturally in rotation views. Inactive members keep their IDs but get
    # the single reserved "Henry Hotel" identity.
    active = sorted(
        (m for m in members if m["is_active"]),
        key=lambda m: m["rotation_order"],
    )
    inactive = [m for m in members if not m["is_active"]]

    if len(active) > len(ACTIVE_ROSTER):
        raise ValueError(
            f"Export has {len(active)} active members but roster only has "
            f"{len(ACTIVE_ROSTER)} slots. Add more phonetic names."
        )

    for member, (fake_name, fake_phone) in zip(active, ACTIVE_ROSTER):
        member["name"] = fake_name
        member["phone"] = fake_phone
        member["secondary_phone"] = None

    for member in inactive:
        member["name"] = INACTIVE_NAME
        member["phone"] = INACTIVE_PHONE
        member["secondary_phone"] = None

    return payload


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    with src.open() as f:
        payload = json.load(f)
    sanitized = sanitize(payload)
    with dst.open("w") as f:
        json.dump(sanitized, f, indent=2)
    print(
        f"Sanitized {len(sanitized['data']['team_members'])} team members, "
        f"wrote {dst}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
