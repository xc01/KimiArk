"""Offline checks for mechanics rebaseline classification boundaries."""
from arknights_planner.search.mechanics_rebaseline import MechanicsRebaseline


def test_frontier_classification_keeps_missing_history_distinct():
    old = {"first_failure_frontier": {"frame": 366, "route": "route-2", "failure_type": "EARLY_LEAK"}}
    assert MechanicsRebaseline._classify(old, {"first_failure_frontier": None}, available=False) == "HISTORICAL_STRATEGY_NOT_PERSISTED"


def test_frontier_classification_does_not_call_a_moved_frontier_preserved():
    old = {"first_failure_frontier": {"frame": 366, "route": "route-2", "failure_type": "EARLY_LEAK"}}
    new = {"first_failure_frontier": {"frame": 564, "route": "route-2", "failure_type": "EARLY_LEAK"}}
    assert MechanicsRebaseline._classify(old, new, available=True) == "MOVED"


def test_absent_historical_route_does_not_create_a_false_frontier_move():
    old = {"first_failure_frontier": {"frame": 366, "route": "UNAVAILABLE_NOT_PERSISTED", "failure_type": "EARLY_LEAK"}}
    new = {"first_failure_frontier": {"frame": 366, "route": "route-2", "failure_type": "EARLY_LEAK"}}
    assert MechanicsRebaseline._classify(old, new, available=True) == "PRESERVED"
