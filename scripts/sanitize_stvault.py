#!/usr/bin/env python3
"""Sanitize a .stvault export for safe use in the dev environment.

Strips all PII from `team_members` (name + phone), replacing with a fixed
phonetic-alphabet roster and fictional phone numbers in the FCC-reserved
fictional-use block (area code 212, exchange 555, line 0100-0199).
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

# Phonetic-alphabet rosters for active and inactive team members.
# Phone numbers use the FCC-reserved fictional-use block: NXX=555,
# line 0100-0199, documented in NANPA / FCC guidelines for use in
# media and testing — guaranteed never to be assigned to a real
# subscriber. We anchor the area code to 212 (New York), which is a
# real NPA, because the reservation is only valid when paired with a
# real area code. Each member gets a unique phone number to satisfy
# any UNIQUE constraint the team_members.phone column may have.
ACTIVE_ROSTER = [
    ("Alice Alpha", "+12125550101"),
    ("Bob Bravo", "+12125550102"),
    ("Carol Charlie", "+12125550103"),
    ("Dave Delta", "+12125550104"),
    ("Eve Echo", "+12125550105"),
    ("Frank Foxtrot", "+12125550106"),
    ("Grace Golf", "+12125550107"),
]
# Separate namespace for inactive members, continuing the phonetic
# alphabet. Sized for growth — a real team will rarely have >4 inactive
# members sitting in the DB, but allocating the next block of the
# alphabet is cheap and keeps roster slots unique across active+inactive.
INACTIVE_ROSTER = [
    ("Henry Hotel", "+12125550151"),
    ("India Indigo", "+12125550152"),
    ("Juliet Jazz", "+12125550153"),
    ("Kilo Kite", "+12125550154"),
    ("Lima Lynx", "+12125550155"),
    ("Mike Mango", "+12125550156"),
    ("November Nova", "+12125550157"),
    ("Oscar Orbit", "+12125550158"),
]


def sanitize(payload: dict) -> dict:
    members = payload["data"]["team_members"]

    # Sort active members by rotation_order so the phonetic alphabet reads
    # naturally in rotation views. The `(x is None, x)` tuple key puts any
    # rows with a null rotation_order at the end rather than crashing on
    # the None comparison — defensive against unexpected prod data shapes.
    active = sorted(
        (m for m in members if m["is_active"]),
        key=lambda m: (m["rotation_order"] is None, m["rotation_order"]),
    )
    inactive = sorted(
        (m for m in members if not m["is_active"]),
        key=lambda m: (m["id"] is None, m["id"]),
    )

    if len(active) > len(ACTIVE_ROSTER):
        raise ValueError(
            f"Export has {len(active)} active members but ACTIVE_ROSTER only "
            f"has {len(ACTIVE_ROSTER)} slots. Extend ACTIVE_ROSTER."
        )
    if len(inactive) > len(INACTIVE_ROSTER):
        raise ValueError(
            f"Export has {len(inactive)} inactive members but INACTIVE_ROSTER "
            f"only has {len(INACTIVE_ROSTER)} slots. Extend INACTIVE_ROSTER."
        )

    for member, (fake_name, fake_phone) in zip(active, ACTIVE_ROSTER):
        member["name"] = fake_name
        member["phone"] = fake_phone
        member["secondary_phone"] = None

    for member, (fake_name, fake_phone) in zip(inactive, INACTIVE_ROSTER):
        member["name"] = fake_name
        member["phone"] = fake_phone
        member["secondary_phone"] = None

    return payload


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    with src.open(encoding="utf-8") as f:
        payload = json.load(f)
    sanitized = sanitize(payload)
    with dst.open("w", encoding="utf-8") as f:
        # Match the admin export endpoint's UTF-8 behavior so a round-trip
        # (export -> sanitize -> import) preserves any non-ASCII content in
        # settings or schedule fields byte-for-byte.
        json.dump(sanitized, f, indent=2, ensure_ascii=False)
    print(
        f"Sanitized {len(sanitized['data']['team_members'])} team members, "
        f"wrote {dst}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
