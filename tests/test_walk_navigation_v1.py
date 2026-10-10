from __future__ import annotations

import unittest

from arknights_planner.navigation import WalkNavigator, path_length


def full_grid(rows: int, columns: int) -> set[tuple[int, int]]:
    return {(row, col) for row in range(rows) for col in range(columns)}


class WalkNavigationTests(unittest.TestCase):
    def test_spfa_smooths_to_a_seen_ancestor_without_crossing_an_unseen_one(self):
        passable = full_grid(3, 3)
        path = WalkNavigator(3, 3, passable.__contains__).path((2, 0), (0, 2))
        self.assertEqual(path, ((2, 0), (0, 2)))
        self.assertAlmostEqual(path_length(path), 2 * 2 ** 0.5)

    def test_bresenham_corner_rule_rejects_a_blocked_side_tile(self):
        passable = full_grid(3, 3)
        blocked = {(1, 0)}
        path = WalkNavigator(
            3, 3, lambda coordinate: coordinate in passable and coordinate not in blocked
        ).field_to((0, 2)).path_from((2, 0))
        self.assertIn((2, 0), path)
        self.assertEqual(path[-1], (0, 2))
        self.assertIn((1, 2), path)

    def test_disabled_diagonal_uses_row_and_column_raycast(self):
        path = WalkNavigator(3, 3, full_grid(3, 3).__contains__).path(
            (2, 0), (0, 2), allow_diagonal=False
        )
        self.assertEqual(path, ((2, 0), (2, 2), (0, 2)))

    def test_obstacle_like_tile_has_source_backed_penalty(self):
        passable = full_grid(1, 3)
        navigator = WalkNavigator(
            1, 3, passable.__contains__, obstacle_like=lambda coordinate: coordinate == (0, 1)
        )
        self.assertEqual(navigator.path((0, 0), (0, 2)), ((0, 0), (0, 1), (0, 2)))
        self.assertEqual(navigator.field_to((0, 2)).distances[(0, 0)], 1001)




def test_bresenham_corner_rule_rejects_a_blocked_side_tile():
    passable = full_grid(3, 3)
    blocked = {(1, 0)}
    path = WalkNavigator(
        3, 3, lambda coordinate: coordinate in passable and coordinate not in blocked
    ).field_to((0, 2)).path_from((2, 0))
    assert (2, 0) in path
    assert path[-1] == (0, 2)
    assert (1, 1) in path


def test_disabled_diagonal_uses_row_and_column_raycast():
    path = WalkNavigator(3, 3, full_grid(3, 3).__contains__).path(
        (2, 0), (0, 2), allow_diagonal=False
    )
    assert path == ((2, 0), (1, 0), (0, 0), (0, 1), (0, 2))


def test_obstacle_like_tile_has_source_backed_penalty():
    passable = full_grid(1, 3)
    path = WalkNavigator(
        1, 3, passable.__contains__, obstacle_like=lambda coordinate: coordinate == (0, 1)
    ).path((0, 0), (0, 2))
    assert path == ((0, 0), (0, 1), (0, 2))
    field = WalkNavigator(
        1, 3, passable.__contains__, obstacle_like=lambda coordinate: coordinate == (0, 1)
    ).field_to((0, 2))
    assert field.distances[(0, 2)] == 1001
