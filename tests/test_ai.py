import unittest

import ai as ai_module
from engine import Board
from mcs import MonteCarloAI


class TestAIs(unittest.TestCase):
    def test_random_ai_unique_shots(self):
        board = Board(4, 3)
        r = ai_module.RandomAI(board)
        shots = set()
        for _ in range(board.width * board.height):
            x, y = r.get_shot_coordinates()
            self.assertTrue(0 <= x < board.width)
            self.assertTrue(0 <= y < board.height)
            shots.add((x, y))
        self.assertEqual(len(shots), board.width * board.height)

    def test_sequential_ai_order(self):
        board = Board(3, 2)
        s = ai_module.SequentialAI(board)
        expected = []
        for y in range(board.height):
            for x in range(board.width):
                expected.append((x, y))

        got = [s.get_shot_coordinates() for _ in range(board.width * board.height)]
        self.assertEqual(got, expected)

    def test_checkerboard_ai_parity(self):
        board = Board(4, 4)
        c = ai_module.CheckerboardAI(board)
        seen = set()
        # take a number of shots and ensure unique
        for _ in range(board.width * board.height):
            x, y = c.get_shot_coordinates()
            self.assertTrue(0 <= x < board.width)
            self.assertTrue(0 <= y < board.height)
            seen.add((x, y))
        self.assertEqual(len(seen), board.width * board.height)

    def test_hunt_and_target_reports_neighbors(self):
        board = Board(5, 5)
        h = ai_module.HuntAndTargetAI(board)
        h.report_hit(2, 2, is_sunk=False)
        # neighbors should be in targets (order not important)
        neighbors = {(3, 2), (1, 2), (2, 3), (2, 1)}
        self.assertTrue(neighbors.issubset(set(h.targets) | set(h.hits)))

    def test_qlearning_updates_q(self):
        board = Board(3, 3)
        q = ai_module.QLearningAI(board, alpha=0.5, epsilon=0.0, persist=False)
        # ensure selecting best uses q table; update one cell and observe change
        old = q.q[0][0]
        q.observe_shot_result(0, 0, ai_module.CellStatus.HIT, is_sunk=False)
        self.assertNotEqual(q.q[0][0], old)

    def test_heatmap_updates(self):
        board = Board(3, 3)
        h = ai_module.HeatmapAI(board, persist=False)
        before = h.heatmap[1][1]
        h.observe_shot_result(1, 1, ai_module.CellStatus.HIT, is_sunk=False)
        self.assertGreater(h.heatmap[1][1], before)

    def test_create_pve_ai_mapping_and_fallback(self):
        board = Board(5, 5)
        self.assertIsInstance(ai_module.create_pve_ai("HuntAndTarget", board), ai_module.HuntAndTargetAI)
        self.assertIsInstance(ai_module.create_pve_ai("Statistical", board), ai_module.StatisticalAI)
        self.assertIsInstance(ai_module.create_pve_ai("MonteCarlo", board), MonteCarloAI)
        self.assertIsInstance(ai_module.create_pve_ai("Unknown", board), ai_module.HuntAndTargetAI)

    def test_placement_strategies_place_full_fleet(self):
        ship_types = [("Carrier", 5), ("Battleship", 4), ("Cruiser", 3), ("Submarine", 3), ("Destroyer", 2)]
        expected_ship_cells = sum(size for _, size in ship_types)

        for placement_cls in (ai_module.RandomPlacementAI, ai_module.EdgePlacementAI, ai_module.DistributedPlacementAI):
            board = Board(10, 10)
            placement_cls(board).place_ships(ship_types)

            self.assertEqual(len(board.ships), len(ship_types))
            placed_cells = sum(1 for row in board.grid for cell in row if cell == ai_module.CellStatus.SHIP)
            self.assertEqual(placed_cells, expected_ship_cells)


if __name__ == "__main__":
    unittest.main()
