import argparse
import datetime
import json
from pathlib import Path

from human_difficulty import DifficultyLab, DifficultyGenome, build_difficulty_profiles, save_profiles


def run_difficulty_search(
    generations: int,
    population: int,
    games_per_eval: int,
    seed: int | None,
    profile_out: str,
    report_prefix: str,
) -> dict:
    lab = DifficultyLab(seed=seed)
    result = lab.evolve(
        generations=generations,
        population=population,
        games_per_eval=games_per_eval,
    )

    best_payload = result.get("best", {})
    best_genome = DifficultyGenome.from_dict(best_payload.get("genome", {}), name="best")
    profiles = build_difficulty_profiles(best_genome)

    profile_path = save_profiles(
        profile_out,
        profiles,
        metadata={
            "seed": seed,
            "generations": generations,
            "population": population,
            "games_per_eval": games_per_eval,
            "best_score": best_payload.get("difficulty_score"),
        },
    )

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_name = f"{report_prefix}_{stamp}.json"
    report_path = Path(profile_path).parent / report_name
    with report_path.open("w", encoding="utf8") as f:
        json.dump(result, f, indent=2)

    result["profile_path"] = str(profile_path)
    result["report_path"] = str(report_path)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search for high-difficulty human opponent profiles")
    parser.add_argument("--generations", type=int, default=8, help="Evolution generations")
    parser.add_argument("--population", type=int, default=16, help="Population size per generation")
    parser.add_argument("--games-per-eval", type=int, default=2, help="Evaluation games per proxy matchup")
    parser.add_argument("--seed", type=int, default=None, help="Optional deterministic random seed")
    parser.add_argument(
        "--profile-out",
        type=str,
        default="results/human_opponents.json",
        help="Output path for generated difficulty profiles",
    )
    parser.add_argument(
        "--report-prefix",
        type=str,
        default="difficulty_search",
        help="Filename prefix for search report JSON",
    )

    args = parser.parse_args()

    print(
        f"Running difficulty lab: generations={args.generations}, population={args.population}, "
        f"games_per_eval={args.games_per_eval}"
    )
    if args.seed is not None:
        print(f"Deterministic seed enabled: {args.seed}")

    result = run_difficulty_search(
        generations=args.generations,
        population=args.population,
        games_per_eval=args.games_per_eval,
        seed=args.seed,
        profile_out=args.profile_out,
        report_prefix=args.report_prefix,
    )

    best = result.get("best", {})
    print(
        "Best profile score: "
        f"{best.get('difficulty_score')} "
        f"(offense={best.get('offense_score')}, defense={best.get('defense_score')}, "
        f"unpredictability={best.get('unpredictability')})"
    )
    print(f"Saved profiles: {result.get('profile_path')}")
    print(f"Saved search report: {result.get('report_path')}")
