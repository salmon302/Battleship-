import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai import (
    BaseAI,
    PlacementAI,
    RandomAI,
    HuntAndTargetAI,
    StatisticalAI,
    RandomPlacementAI,
    EdgePlacementAI,
    DistributedPlacementAI,
)
from engine import Board, Ship, CellStatus


SHIP_TYPES = [
    ("Carrier", 5),
    ("Battleship", 4),
    ("Cruiser", 3),
    ("Submarine", 3),
    ("Destroyer", 2),
]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


@dataclass(frozen=True)
class DifficultyGenome:
    name: str = "profile"
    parity_weight: float = 0.8
    adjacency_weight: float = 1.6
    center_weight: float = 0.2
    edge_weight: float = -0.2
    graph_weight: float = 1.1
    exploration_rate: float = 0.08
    placement_edge_bias: float = 0.3
    placement_center_bias: float = 0.2
    placement_spread_bias: float = 0.7

    def mutate(self, rng: random.Random, scale: float = 0.25, name: str | None = None) -> "DifficultyGenome":
        return DifficultyGenome(
            name=name or self.name,
            parity_weight=_clamp(self.parity_weight + rng.gauss(0.0, scale), -1.0, 2.5),
            adjacency_weight=_clamp(self.adjacency_weight + rng.gauss(0.0, scale), -1.0, 3.0),
            center_weight=_clamp(self.center_weight + rng.gauss(0.0, scale), -1.5, 1.5),
            edge_weight=_clamp(self.edge_weight + rng.gauss(0.0, scale), -1.5, 1.5),
            graph_weight=_clamp(self.graph_weight + rng.gauss(0.0, scale), 0.0, 3.0),
            exploration_rate=_clamp(self.exploration_rate + rng.gauss(0.0, scale * 0.15), 0.01, 0.35),
            placement_edge_bias=_clamp(self.placement_edge_bias + rng.gauss(0.0, scale), -1.5, 1.5),
            placement_center_bias=_clamp(self.placement_center_bias + rng.gauss(0.0, scale), -1.5, 1.5),
            placement_spread_bias=_clamp(self.placement_spread_bias + rng.gauss(0.0, scale), -1.5, 1.5),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "parity_weight": self.parity_weight,
            "adjacency_weight": self.adjacency_weight,
            "center_weight": self.center_weight,
            "edge_weight": self.edge_weight,
            "graph_weight": self.graph_weight,
            "exploration_rate": self.exploration_rate,
            "placement_edge_bias": self.placement_edge_bias,
            "placement_center_bias": self.placement_center_bias,
            "placement_spread_bias": self.placement_spread_bias,
        }

    @staticmethod
    def from_dict(data: dict[str, Any], name: str | None = None) -> "DifficultyGenome":
        merged = dict(data or {})
        if name is not None:
            merged["name"] = name
        return DifficultyGenome(
            name=str(merged.get("name", "profile")),
            parity_weight=float(merged.get("parity_weight", 0.8)),
            adjacency_weight=float(merged.get("adjacency_weight", 1.6)),
            center_weight=float(merged.get("center_weight", 0.2)),
            edge_weight=float(merged.get("edge_weight", -0.2)),
            graph_weight=float(merged.get("graph_weight", 1.1)),
            exploration_rate=float(merged.get("exploration_rate", 0.08)),
            placement_edge_bias=float(merged.get("placement_edge_bias", 0.3)),
            placement_center_bias=float(merged.get("placement_center_bias", 0.2)),
            placement_spread_bias=float(merged.get("placement_spread_bias", 0.7)),
        )


class KnowledgeGraph:
    def __init__(self, decay: float = 0.999):
        self.decay = float(decay)
        self.edges: dict[str, dict[str, float]] = {}

    def score(self, state: str, action: str) -> float:
        return float(self.edges.get(state, {}).get(action, 0.0))

    def update(self, state: str, action: str, reward: float, lr: float = 0.2) -> None:
        bucket = self.edges.setdefault(state, {})
        prev = float(bucket.get(action, 0.0))
        bucket[action] = prev + float(lr) * (float(reward) - prev)

    def decay_all(self) -> None:
        if self.decay >= 1.0:
            return
        for bucket in self.edges.values():
            for action in list(bucket.keys()):
                bucket[action] = bucket[action] * self.decay

    def to_dict(self) -> dict[str, Any]:
        return {"decay": self.decay, "edges": self.edges}

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> "KnowledgeGraph":
        payload = data or {}
        graph = KnowledgeGraph(decay=float(payload.get("decay", 0.999)))
        edges = payload.get("edges", {})
        if isinstance(edges, dict):
            for state, actions in edges.items():
                if not isinstance(actions, dict):
                    continue
                graph.edges[str(state)] = {str(a): float(v) for a, v in actions.items()}
        return graph

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load(path: str | Path) -> "KnowledgeGraph":
        target = Path(path)
        if not target.exists():
            return KnowledgeGraph()
        with target.open("r", encoding="utf8") as f:
            return KnowledgeGraph.from_dict(json.load(f))


class KnowledgeGraphAI(BaseAI):
    def __init__(
        self,
        board: Board,
        genome: DifficultyGenome | None = None,
        graph: KnowledgeGraph | None = None,
        rng: random.Random | None = None,
    ):
        super().__init__(board)
        self.genome = genome or DifficultyGenome(name="human-medium")
        self.graph = graph or KnowledgeGraph()
        self.rng = rng or random.Random()
        self.recent_hits: list[tuple[int, int]] = []
        self.last_state: str | None = None
        self.last_action: str | None = None

    def _state_tag(self) -> str:
        return "target" if self.recent_hits else "search"

    def _action_tag(self, x: int, y: int, near_hit: bool) -> str:
        edge = x == 0 or y == 0 or x == self.board.width - 1 or y == self.board.height - 1
        center_x = (self.board.width - 1) / 2.0
        center_y = (self.board.height - 1) / 2.0
        dist = abs(x - center_x) + abs(y - center_y)
        center = dist <= (self.board.width + self.board.height) / 5.0
        parity = (x + y) % 2
        return f"p{parity}|{'edge' if edge else 'inner'}|{'near' if near_hit else 'far'}|{'center' if center else 'outer'}"

    def _near_hit(self, x: int, y: int) -> bool:
        for hx, hy in self.recent_hits:
            if abs(hx - x) + abs(hy - y) == 1:
                return True
        return False

    def _candidate_score(self, x: int, y: int, state_tag: str) -> tuple[float, str]:
        near_hit = self._near_hit(x, y)
        is_even = 1.0 if (x + y) % 2 == 0 else 0.0
        is_edge = 1.0 if (x == 0 or y == 0 or x == self.board.width - 1 or y == self.board.height - 1) else 0.0

        center_x = (self.board.width - 1) / 2.0
        center_y = (self.board.height - 1) / 2.0
        max_dist = center_x + center_y
        center_dist = abs(x - center_x) + abs(y - center_y)
        center_score = 1.0 - (center_dist / max(1.0, max_dist))

        action_tag = self._action_tag(x, y, near_hit)
        graph_score = self.graph.score(state_tag, action_tag)

        score = 0.0
        score += self.genome.parity_weight * is_even
        score += self.genome.adjacency_weight * (1.0 if near_hit else 0.0)
        score += self.genome.center_weight * center_score
        score += self.genome.edge_weight * is_edge
        score += self.genome.graph_weight * graph_score
        score += self.rng.uniform(-0.02, 0.02)
        return score, action_tag

    def get_shot_coordinates(self) -> tuple[int, int]:
        available = self._get_available_shots()
        if not available:
            return (0, 0)

        state_tag = self._state_tag()
        if self.rng.random() < self.genome.exploration_rate:
            shot = self.rng.choice(available)
            action_tag = self._action_tag(shot[0], shot[1], self._near_hit(shot[0], shot[1]))
        else:
            best_score = -1e18
            best_shots: list[tuple[int, int, str]] = []
            for x, y in available:
                score, action_tag = self._candidate_score(x, y, state_tag)
                if score > best_score + 1e-12:
                    best_score = score
                    best_shots = [(x, y, action_tag)]
                elif abs(score - best_score) <= 1e-12:
                    best_shots.append((x, y, action_tag))
            x, y, action_tag = self.rng.choice(best_shots)
            shot = (x, y)

        self.shots.add(shot)
        self.last_state = state_tag
        self.last_action = action_tag
        return shot

    def observe_shot_result(self, x: int, y: int, status: CellStatus, is_sunk: bool):
        reward = 1.0 if status == CellStatus.HIT else -0.15
        if is_sunk:
            reward += 0.6

        if self.last_state is not None and self.last_action is not None:
            self.graph.update(self.last_state, self.last_action, reward)

        if status == CellStatus.HIT:
            if (x, y) not in self.recent_hits:
                self.recent_hits.append((x, y))
            if len(self.recent_hits) > 10:
                self.recent_hits = self.recent_hits[-10:]
            if is_sunk:
                self.recent_hits.clear()

        self.graph.decay_all()


class AdaptivePlacementAI(PlacementAI):
    def __init__(self, board: Board, genome: DifficultyGenome, rng: random.Random | None = None):
        super().__init__(board)
        self.genome = genome
        self.rng = rng or random.Random()

    def _existing_ship_cells(self) -> list[tuple[int, int]]:
        cells: list[tuple[int, int]] = []
        for y in range(self.board.height):
            for x in range(self.board.width):
                if self.board.grid[y][x] == CellStatus.SHIP:
                    cells.append((x, y))
        return cells

    def _placement_score(self, coords: list[tuple[int, int]]) -> float:
        w = self.board.width
        h = self.board.height
        center_x = (w - 1) / 2.0
        center_y = (h - 1) / 2.0

        edge_hits = 0.0
        center_sum = 0.0
        for x, y in coords:
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                edge_hits += 1.0
            dist = abs(x - center_x) + abs(y - center_y)
            center_sum += 1.0 - dist / max(1.0, center_x + center_y)

        edge_ratio = edge_hits / len(coords)
        center_ratio = center_sum / len(coords)

        existing = self._existing_ship_cells()
        spread_score = 0.5
        if existing:
            distances = []
            for x, y in coords:
                min_dist = min(abs(x - ex) + abs(y - ey) for ex, ey in existing)
                distances.append(float(min_dist))
            spread_score = _clamp(_mean(distances) / max(1.0, (w + h) / 4.0), 0.0, 1.0)

        score = 0.0
        score += self.genome.placement_edge_bias * edge_ratio
        score += self.genome.placement_center_bias * center_ratio
        score += self.genome.placement_spread_bias * spread_score
        score += self.rng.uniform(-0.02, 0.02)
        return score

    def place_ships(self, ship_types: list[tuple[str, int]]):
        for name, size in ship_types:
            best: tuple[float, int, int, bool] | None = None
            for _ in range(140):
                horizontal = bool(self.rng.getrandbits(1))
                x = self.rng.randint(0, self.board.width - 1)
                y = self.rng.randint(0, self.board.height - 1)
                ship = Ship(name, size)
                if not self.board.can_place_ship(ship, x, y, horizontal):
                    continue

                dx, dy = (1, 0) if horizontal else (0, 1)
                coords = [(x + i * dx, y + i * dy) for i in range(size)]
                score = self._placement_score(coords)
                if best is None or score > best[0]:
                    best = (score, x, y, horizontal)

            if best is not None:
                _, bx, by, bh = best
                self.board.place_ship(Ship(name, size), bx, by, bh)
                continue

            # Random fallback to guarantee placement progress.
            placed = False
            while not placed:
                horizontal = bool(self.rng.getrandbits(1))
                x = self.rng.randint(0, self.board.width - 1)
                y = self.rng.randint(0, self.board.height - 1)
                placed = self.board.place_ship(Ship(name, size), x, y, horizontal)


def _simulate_attack(attacker: BaseAI, defender_board: Board, max_shots: int = 200) -> int:
    turns = 0
    while not defender_board.all_ships_sunk and turns < max_shots:
        x, y = attacker.get_shot_coordinates()
        status, is_sunk = defender_board.receive_shot(x, y)

        if status == CellStatus.HIT and hasattr(attacker, "report_hit"):
            attacker.report_hit(x, y, is_sunk)

        if hasattr(attacker, "observe_shot_result"):
            attacker.observe_shot_result(x, y, status, is_sunk)

        turns += 1
    return turns


def _normalize_turn_score(turns: float) -> float:
    # 17 is best possible (all ship cells); 100 is worst possible on a 10x10 board.
    return _clamp((100.0 - turns) * (100.0 / 83.0), 0.0, 100.0)


def _normalize_survival_score(turns: float) -> float:
    return _clamp((turns - 17.0) * (100.0 / 83.0), 0.0, 100.0)


def _first_shot_entropy(genome: DifficultyGenome, samples: int = 48, seed: int = 0) -> float:
    counts: dict[tuple[int, int], int] = {}
    for idx in range(samples):
        board = Board(10, 10)
        rng = random.Random(seed + idx)
        ai = KnowledgeGraphAI(board, genome=genome, graph=KnowledgeGraph(), rng=rng)
        shot = ai.get_shot_coordinates()
        counts[shot] = counts.get(shot, 0) + 1

    total = float(sum(counts.values()))
    if total <= 0.0:
        return 0.0

    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(max(p, 1e-12))

    max_entropy = math.log2(100.0)
    return _clamp(100.0 * entropy / max(1e-9, max_entropy), 0.0, 100.0)


class DifficultyLab:
    def __init__(self, seed: int | None = None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.offense_placements = [RandomPlacementAI, DistributedPlacementAI, EdgePlacementAI]
        self.defense_attackers = [RandomAI, HuntAndTargetAI, StatisticalAI]

    def _random_genome(self, name: str) -> DifficultyGenome:
        return DifficultyGenome(
            name=name,
            parity_weight=self.rng.uniform(-0.3, 1.8),
            adjacency_weight=self.rng.uniform(0.2, 2.6),
            center_weight=self.rng.uniform(-0.6, 1.0),
            edge_weight=self.rng.uniform(-1.0, 0.8),
            graph_weight=self.rng.uniform(0.1, 2.2),
            exploration_rate=self.rng.uniform(0.02, 0.25),
            placement_edge_bias=self.rng.uniform(-0.8, 1.2),
            placement_center_bias=self.rng.uniform(-0.8, 1.0),
            placement_spread_bias=self.rng.uniform(0.0, 1.3),
        )

    def evaluate_genome(self, genome: DifficultyGenome, games_per_eval: int = 2) -> dict[str, Any]:
        games = max(1, int(games_per_eval))

        offense_turns: list[float] = []
        for placement_cls in self.offense_placements:
            for _ in range(games):
                board = Board(10, 10)
                placement_cls(board).place_ships(SHIP_TYPES)
                ai_rng = random.Random(self.rng.randint(0, 10**9))
                ai = KnowledgeGraphAI(board, genome=genome, graph=KnowledgeGraph(), rng=ai_rng)
                offense_turns.append(float(_simulate_attack(ai, board)))

        defense_turns: list[float] = []
        for attacker_cls in self.defense_attackers:
            for _ in range(games):
                board = Board(10, 10)
                placement_rng = random.Random(self.rng.randint(0, 10**9))
                AdaptivePlacementAI(board, genome=genome, rng=placement_rng).place_ships(SHIP_TYPES)
                attacker = attacker_cls(board)
                defense_turns.append(float(_simulate_attack(attacker, board)))

        mean_offense = _mean(offense_turns)
        mean_defense = _mean(defense_turns)
        offense_score = _normalize_turn_score(mean_offense)
        defense_score = _normalize_survival_score(mean_defense)
        entropy_score = _first_shot_entropy(genome, samples=48, seed=self.rng.randint(0, 10**6))

        difficulty_score = 0.45 * offense_score + 0.35 * defense_score + 0.20 * entropy_score

        return {
            "genome": genome.to_dict(),
            "difficulty_score": round(difficulty_score, 3),
            "offense_score": round(offense_score, 3),
            "defense_score": round(defense_score, 3),
            "unpredictability": round(entropy_score, 3),
            "mean_offense_turns": round(mean_offense, 3),
            "mean_defense_turns": round(mean_defense, 3),
        }

    def evolve(
        self,
        generations: int = 8,
        population: int = 16,
        games_per_eval: int = 2,
        elite_size: int = 4,
    ) -> dict[str, Any]:
        generations = max(1, int(generations))
        population = max(2, int(population))
        elite_size = max(1, min(int(elite_size), population))

        candidates = [self._random_genome(f"g0_c{i}") for i in range(population)]

        history: list[dict[str, Any]] = []
        global_best: dict[str, Any] | None = None
        final_scored: list[tuple[dict[str, Any], DifficultyGenome]] = []

        for gen in range(generations):
            scored: list[tuple[dict[str, Any], DifficultyGenome]] = []
            for genome in candidates:
                metrics = self.evaluate_genome(genome, games_per_eval=games_per_eval)
                scored.append((metrics, genome))

            scored.sort(key=lambda item: item[0]["difficulty_score"], reverse=True)
            final_scored = scored

            scores = [item[0]["difficulty_score"] for item in scored]
            median_score = sorted(scores)[len(scores) // 2]
            best_metrics = scored[0][0]
            history.append(
                {
                    "generation": gen,
                    "best_score": best_metrics["difficulty_score"],
                    "median_score": round(float(median_score), 3),
                    "best_profile": best_metrics["genome"]["name"],
                }
            )

            if global_best is None or best_metrics["difficulty_score"] > global_best["difficulty_score"]:
                global_best = best_metrics

            elites = [item[1] for item in scored[:elite_size]]
            next_population: list[DifficultyGenome] = [elites[0]]
            mutation_scale = 0.35 * (0.88 ** gen)
            while len(next_population) < population:
                parent = self.rng.choice(elites)
                child = parent.mutate(
                    self.rng,
                    scale=mutation_scale,
                    name=f"g{gen + 1}_c{len(next_population)}",
                )
                next_population.append(child)
            candidates = next_population

        if global_best is None:
            raise RuntimeError("Evolution produced no candidates")

        best_genome = DifficultyGenome.from_dict(global_best["genome"], name="best")
        profiles = build_difficulty_profiles(best_genome)

        leaderboard = [entry for entry, _genome in final_scored[: min(10, len(final_scored))]]
        return {
            "best": global_best,
            "history": history,
            "leaderboard": leaderboard,
            "profiles": {name: genome.to_dict() for name, genome in profiles.items()},
        }


def build_difficulty_profiles(best: DifficultyGenome) -> dict[str, DifficultyGenome]:
    easy = DifficultyGenome(
        name="humaneasy",
        parity_weight=best.parity_weight * 0.65,
        adjacency_weight=best.adjacency_weight * 0.55,
        center_weight=best.center_weight * 0.7,
        edge_weight=best.edge_weight * 0.7,
        graph_weight=best.graph_weight * 0.5,
        exploration_rate=_clamp(best.exploration_rate * 2.0, 0.08, 0.35),
        placement_edge_bias=best.placement_edge_bias * 0.6,
        placement_center_bias=best.placement_center_bias * 0.6,
        placement_spread_bias=best.placement_spread_bias * 0.6,
    )

    medium = DifficultyGenome(
        name="humanmedium",
        parity_weight=best.parity_weight * 0.85,
        adjacency_weight=best.adjacency_weight * 0.85,
        center_weight=best.center_weight,
        edge_weight=best.edge_weight,
        graph_weight=best.graph_weight * 0.85,
        exploration_rate=_clamp(best.exploration_rate * 1.3, 0.04, 0.22),
        placement_edge_bias=best.placement_edge_bias * 0.9,
        placement_center_bias=best.placement_center_bias * 0.9,
        placement_spread_bias=best.placement_spread_bias * 0.9,
    )

    hard = DifficultyGenome(
        name="humanhard",
        parity_weight=best.parity_weight,
        adjacency_weight=best.adjacency_weight,
        center_weight=best.center_weight,
        edge_weight=best.edge_weight,
        graph_weight=best.graph_weight,
        exploration_rate=_clamp(best.exploration_rate, 0.02, 0.18),
        placement_edge_bias=best.placement_edge_bias,
        placement_center_bias=best.placement_center_bias,
        placement_spread_bias=best.placement_spread_bias,
    )

    nightmare = DifficultyGenome(
        name="humannightmare",
        parity_weight=best.parity_weight * 1.1,
        adjacency_weight=best.adjacency_weight * 1.1,
        center_weight=best.center_weight * 1.05,
        edge_weight=best.edge_weight,
        graph_weight=best.graph_weight * 1.2,
        exploration_rate=_clamp(best.exploration_rate * 0.7, 0.01, 0.12),
        placement_edge_bias=best.placement_edge_bias * 1.05,
        placement_center_bias=best.placement_center_bias * 1.05,
        placement_spread_bias=best.placement_spread_bias * 1.05,
    )

    return {
        "humaneasy": easy,
        "humanmedium": medium,
        "humanhard": hard,
        "humannightmare": nightmare,
    }


def save_profiles(path: str | Path, profiles: dict[str, DifficultyGenome], metadata: dict[str, Any] | None = None) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "profiles": {name: genome.to_dict() for name, genome in profiles.items()},
        "metadata": metadata or {},
    }
    with target.open("w", encoding="utf8") as f:
        json.dump(payload, f, indent=2)
    return str(target)


def _load_profiles(path: str | None) -> dict[str, DifficultyGenome]:
    if not path:
        return {}

    target = Path(path)
    if not target.exists():
        return {}

    try:
        with target.open("r", encoding="utf8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    profiles_data = payload.get("profiles", {}) if isinstance(payload, dict) else {}
    loaded: dict[str, DifficultyGenome] = {}
    if isinstance(profiles_data, dict):
        for name, data in profiles_data.items():
            if isinstance(data, dict):
                loaded[str(name).lower()] = DifficultyGenome.from_dict(data, name=str(name).lower())
    return loaded


def create_human_opponent_ai(ai_type: str, board: Board, profile_file: str | None = None) -> BaseAI:
    key = str(ai_type).strip().lower().replace("-", "")
    if key in {"knowledgegraph", "knowledge", "adaptive"}:
        key = "humanmedium"

    built_in = build_difficulty_profiles(DifficultyGenome(name="seed"))
    loaded = _load_profiles(profile_file)

    genome = loaded.get(key)
    if genome is None:
        genome = built_in.get(key, built_in["humanmedium"])

    return KnowledgeGraphAI(board, genome=genome, graph=KnowledgeGraph(), rng=random.Random())
