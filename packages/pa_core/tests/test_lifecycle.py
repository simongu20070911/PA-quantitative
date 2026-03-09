from __future__ import annotations

import unittest

from pa_core.schemas import ResolvedStructureState, StructureLifecycleEvent
from pa_core.structures.lifecycle import (
    LifecycleTransitionError,
    resolve_structure_rows_from_lifecycle_events,
    resolve_structure_states_from_lifecycle_events,
)


class LifecycleReducerTests(unittest.TestCase):
    def test_typed_events_resolve_to_typed_structure_state(self) -> None:
        rows = [
            StructureLifecycleEvent(
                event_id="pivot-100:created:100",
                structure_id="pivot-100",
                kind="pivot_high",
                event_type="created",
                event_bar_id=100,
                event_order=0,
                state_after_event="candidate",
                reason_codes=("visible",),
                start_bar_id=100,
                end_bar_id=None,
                confirm_bar_id=None,
                anchor_bar_ids=(100,),
                payload_after={
                    "explanation_codes": ("left_window_3",),
                    "extreme_price": 10.5,
                },
                changed_fields=(),
                session_id=20240102,
                session_date=20240102,
            ),
            StructureLifecycleEvent(
                event_id="pivot-100:confirmed:105",
                structure_id="pivot-100",
                kind="pivot_high",
                event_type="confirmed",
                event_bar_id=105,
                event_order=0,
                state_after_event="confirmed",
                reason_codes=("confirmed",),
                start_bar_id=100,
                end_bar_id=None,
                confirm_bar_id=105,
                anchor_bar_ids=(100,),
                payload_after=None,
                changed_fields=("confirm_bar_id",),
                session_id=20240102,
                session_date=20240102,
            ),
        ]

        resolved = resolve_structure_states_from_lifecycle_events(rows, as_of_bar_id=105)

        self.assertEqual(
            resolved,
            {
                "pivot-100": ResolvedStructureState(
                    structure_id="pivot-100",
                    kind="pivot_high",
                    state="confirmed",
                    start_bar_id=100,
                    end_bar_id=None,
                    confirm_bar_id=105,
                    anchor_bar_ids=(100,),
                    session_id=20240102,
                    session_date=20240102,
                    payload={
                        "explanation_codes": ["left_window_3"],
                        "extreme_price": 10.5,
                    },
                    reason_codes=("confirmed",),
                    explanation_codes=("left_window_3",),
                )
            },
        )

    def test_created_then_confirmed_resolves_post_event_state(self) -> None:
        rows = [
            {
                "event_id": "pivot-100:created:100",
                "structure_id": "pivot-100",
                "kind": "pivot_high",
                "event_type": "created",
                "event_bar_id": 100,
                "event_order": 0,
                "state_after_event": "candidate",
                "reason_codes": ("visible",),
                "start_bar_id": 100,
                "end_bar_id": None,
                "confirm_bar_id": None,
                "anchor_bar_ids": (100,),
                "predecessor_structure_id": None,
                "successor_structure_id": None,
                "payload_after": {
                    "explanation_codes": ("left_window_3",),
                    "extreme_price": 10.5,
                },
                "changed_fields": (),
                "session_id": 20240102,
                "session_date": 20240102,
            },
            {
                "event_id": "pivot-100:confirmed:105",
                "structure_id": "pivot-100",
                "kind": "pivot_high",
                "event_type": "confirmed",
                "event_bar_id": 105,
                "event_order": 0,
                "state_after_event": "confirmed",
                "reason_codes": ("confirmed",),
                "start_bar_id": 100,
                "end_bar_id": None,
                "confirm_bar_id": 105,
                "anchor_bar_ids": (100,),
                "predecessor_structure_id": None,
                "successor_structure_id": None,
                "payload_after": None,
                "changed_fields": ("confirm_bar_id",),
                "session_id": 20240102,
                "session_date": 20240102,
            },
        ]

        resolved = resolve_structure_rows_from_lifecycle_events(rows, as_of_bar_id=105)

        self.assertEqual(set(resolved), {"pivot-100"})
        self.assertEqual(resolved["pivot-100"]["state"], "confirmed")
        self.assertEqual(resolved["pivot-100"]["confirm_bar_id"], 105)
        self.assertEqual(resolved["pivot-100"]["payload"]["extreme_price"], 10.5)
        self.assertEqual(resolved["pivot-100"]["explanation_codes"], ["left_window_3"])

    def test_replaced_structure_leaves_active_state(self) -> None:
        rows = [
            {
                "event_id": "pivot-100:created:100",
                "structure_id": "pivot-100",
                "kind": "pivot_high",
                "event_type": "created",
                "event_bar_id": 100,
                "event_order": 0,
                "state_after_event": "candidate",
                "reason_codes": ("visible",),
                "start_bar_id": 100,
                "end_bar_id": None,
                "confirm_bar_id": None,
                "anchor_bar_ids": (100,),
                "predecessor_structure_id": None,
                "successor_structure_id": None,
                "payload_after": {"explanation_codes": ("left_window_3",)},
                "changed_fields": (),
                "session_id": 20240102,
                "session_date": 20240102,
            },
            {
                "event_id": "pivot-100:replaced:101",
                "structure_id": "pivot-100",
                "kind": "pivot_high",
                "event_type": "replaced",
                "event_bar_id": 101,
                "event_order": 0,
                "state_after_event": "invalidated",
                "reason_codes": ("replaced",),
                "start_bar_id": 100,
                "end_bar_id": None,
                "confirm_bar_id": None,
                "anchor_bar_ids": (100,),
                "predecessor_structure_id": None,
                "successor_structure_id": "pivot-101",
                "payload_after": None,
                "changed_fields": ("successor_structure_id",),
                "session_id": 20240102,
                "session_date": 20240102,
            },
            {
                "event_id": "pivot-101:created:101",
                "structure_id": "pivot-101",
                "kind": "pivot_high",
                "event_type": "created",
                "event_bar_id": 101,
                "event_order": 1,
                "state_after_event": "candidate",
                "reason_codes": ("visible",),
                "start_bar_id": 101,
                "end_bar_id": None,
                "confirm_bar_id": None,
                "anchor_bar_ids": (101,),
                "predecessor_structure_id": "pivot-100",
                "successor_structure_id": None,
                "payload_after": {"explanation_codes": ("left_window_3",)},
                "changed_fields": (),
                "session_id": 20240102,
                "session_date": 20240102,
            },
        ]

        resolved = resolve_structure_rows_from_lifecycle_events(rows, as_of_bar_id=101)

        self.assertEqual(set(resolved), {"pivot-101"})
        self.assertEqual(resolved["pivot-101"]["state"], "candidate")

    def test_initial_non_created_events_raise_by_default(self) -> None:
        base_row = {
            "event_id": "pivot-100:first:100",
            "structure_id": "pivot-100",
            "kind": "pivot_high",
            "event_bar_id": 100,
            "event_order": 0,
            "start_bar_id": 100,
            "end_bar_id": None,
            "confirm_bar_id": None,
            "anchor_bar_ids": (100,),
            "predecessor_structure_id": None,
            "successor_structure_id": None,
            "payload_after": {"explanation_codes": ("left_window_3",)},
            "changed_fields": (),
            "session_id": 20240102,
            "session_date": 20240102,
        }
        for event_type, state_after_event in (
            ("confirmed", "confirmed"),
            ("updated", "candidate"),
            ("invalidated", "invalidated"),
            ("replaced", "invalidated"),
        ):
            with self.subTest(event_type=event_type):
                with self.assertRaises(LifecycleTransitionError):
                    resolve_structure_rows_from_lifecycle_events(
                        [
                            {
                                **base_row,
                                "event_type": event_type,
                                "state_after_event": state_after_event,
                                "reason_codes": (event_type,),
                            }
                        ],
                        as_of_bar_id=100,
                    )

    def test_initial_confirmed_event_can_be_allowed_explicitly(self) -> None:
        resolved = resolve_structure_rows_from_lifecycle_events(
            [
                {
                    "event_id": "pivot-100:confirmed:100",
                    "structure_id": "pivot-100",
                    "kind": "pivot_high",
                    "event_type": "confirmed",
                    "event_bar_id": 100,
                    "event_order": 0,
                    "state_after_event": "confirmed",
                    "reason_codes": ("born_confirmed",),
                    "start_bar_id": 100,
                    "end_bar_id": None,
                    "confirm_bar_id": 100,
                    "anchor_bar_ids": (100,),
                    "predecessor_structure_id": None,
                    "successor_structure_id": None,
                    "payload_after": {"explanation_codes": ("left_window_3",)},
                    "changed_fields": ("confirm_bar_id",),
                    "session_id": 20240102,
                    "session_date": 20240102,
                }
            ],
            as_of_bar_id=100,
            allow_initial_confirmed=True,
        )

        self.assertEqual(set(resolved), {"pivot-100"})
        self.assertEqual(resolved["pivot-100"]["state"], "confirmed")
        self.assertEqual(resolved["pivot-100"]["confirm_bar_id"], 100)

    def test_confirmed_event_requires_confirmed_state_after_event(self) -> None:
        with self.assertRaises(LifecycleTransitionError):
            resolve_structure_rows_from_lifecycle_events(
                [
                    {
                        "event_id": "pivot-100:created:100",
                        "structure_id": "pivot-100",
                        "kind": "pivot_high",
                        "event_type": "created",
                        "event_bar_id": 100,
                        "event_order": 0,
                        "state_after_event": "candidate",
                        "reason_codes": ("visible",),
                        "start_bar_id": 100,
                        "end_bar_id": None,
                        "confirm_bar_id": None,
                        "anchor_bar_ids": (100,),
                        "predecessor_structure_id": None,
                        "successor_structure_id": None,
                        "payload_after": {"explanation_codes": ("left_window_3",)},
                        "changed_fields": (),
                        "session_id": 20240102,
                        "session_date": 20240102,
                    },
                    {
                        "event_id": "pivot-100:confirmed:105",
                        "structure_id": "pivot-100",
                        "kind": "pivot_high",
                        "event_type": "confirmed",
                        "event_bar_id": 105,
                        "event_order": 0,
                        "state_after_event": "candidate",
                        "reason_codes": ("confirmed",),
                        "start_bar_id": 100,
                        "end_bar_id": None,
                        "confirm_bar_id": 105,
                        "anchor_bar_ids": (100,),
                        "predecessor_structure_id": None,
                        "successor_structure_id": None,
                        "payload_after": None,
                        "changed_fields": ("confirm_bar_id",),
                        "session_id": 20240102,
                        "session_date": 20240102,
                    },
                ],
                as_of_bar_id=105,
            )


if __name__ == "__main__":
    unittest.main()
