import unittest

from multi_ai import MultiAIGame


class TestMultiAIHeadless(unittest.TestCase):
    def _run_game(self, seed: int):
        game = MultiAIGame(num_ais=2, attack_all=False, seed=seed, render=False)
        max_turns = 5000

        while not game.game_over and max_turns > 0:
            game.perform_ai_turn()
            max_turns -= 1

        self.assertTrue(game.game_over)
        self.assertGreater(max_turns, 0)
        return game.winner, game.analytics.turns if game.analytics else None

    def test_seeded_headless_run_is_reproducible(self):
        first = self._run_game(42)
        second = self._run_game(42)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
