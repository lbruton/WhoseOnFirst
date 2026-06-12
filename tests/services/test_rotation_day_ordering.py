"""
WOF-8 regression tests: rotation must order shifts by chronological day of week,
NOT by shift_number.

shift_number is a free-form user label. When shifts are removed and re-added in the
admin UI, a shift for an earlier day can receive a higher shift_number than a later
day (e.g. Tuesday ends up #6/#7). Because each shift's calendar date is derived from
its day_of_week, ordering the rotation by shift_number assigns members to the wrong
days — a silent on-call mis-rotation. These tests pin the correct behavior: members
are assigned in chronological day order regardless of shift_number values.
"""

from datetime import datetime

from src.services.rotation_algorithm import RotationAlgorithmService


def _make_member(repo, name, phone):
    return repo.create({"name": name, "phone": phone, "is_active": True})


class TestRotationDayOrdering:
    """Rotation assignment must follow weekday order, not shift_number order."""

    def test_rotation_orders_by_day_not_shift_number(
        self, db_session, team_member_repo, shift_repo, chicago_tz
    ):
        """A Tuesday shift numbered out of order still gets the second member."""
        m1 = _make_member(team_member_repo, "M1", "+15550000001")
        m2 = _make_member(team_member_repo, "M2", "+15550000002")
        m3 = _make_member(team_member_repo, "M3", "+15550000003")

        # shift_number deliberately NOT in day order: Tuesday is #7 (last by number)
        shift_repo.create({"shift_number": 1, "day_of_week": "Monday",
                           "duration_hours": 24, "start_time": "08:00:00"})
        shift_repo.create({"shift_number": 7, "day_of_week": "Tuesday",
                           "duration_hours": 24, "start_time": "08:00:00"})
        shift_repo.create({"shift_number": 2, "day_of_week": "Wednesday",
                           "duration_hours": 24, "start_time": "08:00:00"})

        service = RotationAlgorithmService(db_session)
        start = chicago_tz.localize(datetime(2025, 11, 3, 8, 0))  # a Monday
        entries = service.generate_rotation(start, weeks=1)

        # Sort entries chronologically and read off the assigned members
        by_day = sorted(entries, key=lambda e: e["start_datetime"])
        member_ids_in_day_order = [e["team_member_id"] for e in by_day]

        # Mon -> m1, Tue -> m2, Wed -> m3 regardless of shift_number
        assert member_ids_in_day_order == [m1.id, m2.id, m3.id]

    def test_scrambled_seven_day_config_rotates_in_day_order(
        self, db_session, team_member_repo, shift_repo, chicago_tz
    ):
        """Reproduces the prod WOF-8 state: a 7-day config whose numbers are scrambled.

        Mon=1, Thu=2, Fri=3, Sat=4, Sun=5, Tue=6, Wed=7 (Tue/Wed re-added last).
        Members must still map to days in chronological order.
        """
        members = [
            _make_member(team_member_repo, f"M{i}", f"+1555000{i:04d}")
            for i in range(7)
        ]

        scrambled = [
            (1, "Monday"), (6, "Tuesday"), (7, "Wednesday"), (2, "Thursday"),
            (3, "Friday"), (4, "Saturday"), (5, "Sunday"),
        ]
        for number, day in scrambled:
            shift_repo.create({"shift_number": number, "day_of_week": day,
                               "duration_hours": 24, "start_time": "08:00:00"})

        service = RotationAlgorithmService(db_session)
        start = chicago_tz.localize(datetime(2025, 11, 3, 8, 0))  # a Monday
        entries = service.generate_rotation(start, weeks=1)

        by_day = sorted(entries, key=lambda e: e["start_datetime"])
        member_ids_in_day_order = [e["team_member_id"] for e in by_day]

        assert member_ids_in_day_order == [m.id for m in members]

    def test_double_shift_sorts_by_first_day(
        self, db_session, team_member_repo, shift_repo, chicago_tz
    ):
        """A 48h Tuesday-Wednesday shift sorts at Tuesday's position."""
        m1 = _make_member(team_member_repo, "M1", "+15550000011")
        m2 = _make_member(team_member_repo, "M2", "+15550000012")
        m3 = _make_member(team_member_repo, "M3", "+15550000013")

        shift_repo.create({"shift_number": 9, "day_of_week": "Monday",
                           "duration_hours": 24, "start_time": "08:00:00"})
        shift_repo.create({"shift_number": 1, "day_of_week": "Tuesday-Wednesday",
                           "duration_hours": 48, "start_time": "08:00:00"})
        shift_repo.create({"shift_number": 5, "day_of_week": "Thursday",
                           "duration_hours": 24, "start_time": "08:00:00"})

        service = RotationAlgorithmService(db_session)
        start = chicago_tz.localize(datetime(2025, 11, 3, 8, 0))  # a Monday
        entries = service.generate_rotation(start, weeks=1)

        by_day = sorted(entries, key=lambda e: e["start_datetime"])
        member_ids_in_day_order = [e["team_member_id"] for e in by_day]

        # Mon -> m1, Tue-Wed (48h) -> m2, Thu -> m3
        assert member_ids_in_day_order == [m1.id, m2.id, m3.id]
