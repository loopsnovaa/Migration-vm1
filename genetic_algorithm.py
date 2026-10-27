
import json
import os
import random
import shlex
import subprocess
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

POP_SIZE = 30
GENERATIONS = 60
MUTATION_RATE = 0.12

NODES = ["VM1", "VM2"]

MIGRATION_TIME_SEC = 30
MIGRATION_COST_PER_SEC = 0.002

# Change this to the VM currently hosting your workload.
CURRENT_NODE = "VM1"

# Each file must contain the Price Oracle's price_history.json
# list from the corresponding VM.
HISTORY_FILES = {
    "VM1": "price_history_vm1.json",
    "VM2": "price_history_vm2.json",
}

HISTORY_STEPS = 5

# A recommendation is always calculated.
# Actual migration is disabled until a verified VM-to-VM
# migration command is configured.
EXECUTE_MIGRATION = False

# Configure this environment variable only after confirming
# the command performs migration to the specified destination.
# Example command template:
# MIGRATION_COMMAND='your_verified_command {source} {target}'
MIGRATION_COMMAND = os.getenv("MIGRATION_COMMAND", "").strip()

# Resource weights
PRICE_WEIGHT = 0.40
CPU_WEIGHT = 0.25
RAM_WEIGHT = 0.25
NETWORK_WEIGHT = 0.10

# Normalization limits; adjust to your environment.
MAX_PRICE = 20.0
MAX_CPU = 100.0
MAX_RAM = 100.0
MAX_NETWORK_MBPS = 100.0

# Avoid migrations for very small estimated improvements.
# This is a minimum normalized-score improvement threshold.
MIN_IMPROVEMENT = 0.02


# ============================================================
# PRICE ORACLE HISTORY
# ============================================================

def load_history(filename, steps=HISTORY_STEPS):
    path = Path(filename)

    if not path.is_file():
        raise FileNotFoundError(
            f"Metrics file not found: {path}\n"
            "Export the Price Oracle history from this VM "
            "and save it under the configured filename."
        )

    with path.open("r", encoding="utf-8") as file:
        history = json.load(file)

    if not isinstance(history, list) or not history:
        raise ValueError(f"No metric samples found in {path}")

    required = {"price", "cpu", "ram", "network_mbps"}
    valid_samples = []

    for index, sample in enumerate(history):
        if not isinstance(sample, dict):
            continue

        if not required.issubset(sample):
            continue

        try:
            metrics = {
                key: float(sample[key])
                for key in required
            }
        except (TypeError, ValueError):
            continue

        if not all(
            value >= 0 and value < float("inf")
            for value in metrics.values()
        ):
            continue

        valid_samples.append(metrics)

    if not valid_samples:
        raise ValueError(
            f"No valid CPU/RAM/network/price samples in {path}"
        )

    return valid_samples[-steps:]


def build_forecast():
    """
    Build equal-length placement sequences from recent
    Price Oracle observations.

    These are historical observations, NOT future predictions.
    """
    histories = {
        node: load_history(filename)
        for node, filename in HISTORY_FILES.items()
    }

    steps = min(len(samples) for samples in histories.values())

    if steps == 0:
        raise ValueError("Both VMs need at least one valid sample.")

    return {
        node: samples[-steps:]
        for node, samples in histories.items()
    }


# ============================================================
# GENETIC ALGORITHM
# ============================================================

def normalize(value, minimum, maximum):
    if maximum <= minimum:
        return 0.0

    normalized = (value - minimum) / (maximum - minimum)
    return max(0.0, min(1.0, normalized))


def migration_penalty(plan, current_node_index):
    switches = 0

    # Include the transition from the actual current node
    # to the first placement in the candidate plan.
    if plan and plan[0] != current_node_index:
        switches += 1

    for i in range(1, len(plan)):
        if plan[i] != plan[i - 1]:
            switches += 1

    return switches * MIGRATION_TIME_SEC * MIGRATION_COST_PER_SEC


def step_score(state):
    price_score = normalize(state["price"], 0, MAX_PRICE)
    cpu_score = normalize(state["cpu"], 0, MAX_CPU)
    ram_score = normalize(state["ram"], 0, MAX_RAM)
    network_score = normalize(
        state["network_mbps"], 0, MAX_NETWORK_MBPS
    )

    return (
        price_score * PRICE_WEIGHT
        + cpu_score * CPU_WEIGHT
        + ram_score * RAM_WEIGHT
        + network_score * NETWORK_WEIGHT
    )


def fitness(plan, forecast, current_node_index):
    total_score = 0.0

    for step, node_index in enumerate(plan):
        node = NODES[node_index]
        state = forecast[node][step]
        total_score += step_score(state)

    total_score += (
        migration_penalty(plan, current_node_index) * 0.10
    )

    # The GA maximizes fitness, so lower cost means higher fitness.
    return -total_score


def create_population(steps):
    return [
        [random.randint(0, 1) for _ in range(steps)]
        for _ in range(POP_SIZE)
    ]


def select_parents(population, forecast, current_node_index):
    ranked = sorted(
        population,
        key=lambda plan: fitness(
            plan, forecast, current_node_index
        ),
        reverse=True,
    )
    return ranked[:POP_SIZE // 2]


def crossover(parent1, parent2):
    if len(parent1) <= 1:
        return parent1.copy()

    cut = random.randint(1, len(parent1) - 1)
    return parent1[:cut] + parent2[cut:]


def mutate(plan):
    for i in range(len(plan)):
        if random.random() < MUTATION_RATE:
            plan[i] = random.randint(0, 1)
    return plan


def run_ga(forecast, current_node_index):
    steps = len(forecast["VM1"])
    population = create_population(steps)

    print("\nRunning Genetic Algorithm...")
    print(f"Population: {POP_SIZE}")
    print(f"Generations: {GENERATIONS}")
    print(f"Mutation rate: {MUTATION_RATE}")
    print(f"Evaluation steps: {steps}")

    for generation in range(GENERATIONS):
        parents = select_parents(
            population, forecast, current_node_index
        )

        children = []

        while len(children) < POP_SIZE - len(parents):
            parent1, parent2 = random.sample(parents, 2)
            child = crossover(parent1, parent2)
            children.append(mutate(child))

        population = parents + children

        if generation % 10 == 0:
            best = max(
                population,
                key=lambda plan: fitness(
                    plan, forecast, current_node_index
                ),
            )
            print(
                f"Generation {generation:3d} "
                f"-> Fitness: "
                f"{fitness(best, forecast, current_node_index):.4f}"
            )

    return max(
        population,
        key=lambda plan: fitness(
            plan, forecast, current_node_index
        ),
    )


# ============================================================
# DECISION AND MIGRATION INTEGRATION
# ============================================================

def print_plan(plan, forecast, current_node):
    first_target = NODES[plan[0]]

    switches = sum(
        plan[i] != plan[i - 1]
        for i in range(1, len(plan))
    )

    initial_migration = first_target != current_node
    total_migrations = switches + int(initial_migration)

    migration_cost = (
        total_migrations
        * MIGRATION_TIME_SEC
        * MIGRATION_COST_PER_SEC
    )

    print("\n" + "=" * 60)
    print("GENETIC ALGORITHM RESULT")
    print("=" * 60)

    for step, node_index in enumerate(plan):
        state = forecast[NODES[node_index]][step]
        print(
            f"Step {step + 1}: {NODES[node_index]} | "
            f"Price=${state['price']:.3f}/hour | "
            f"CPU={state['cpu']:.2f}% | "
            f"RAM={state['ram']:.2f}% | "
            f"Network={state['network_mbps']:.3f} Mbps"
        )

    print(f"\nCurrent VM: {current_node}")
    print(f"Recommended VM: {first_target}")
    print(f"Initial migration required: {'YES' if initial_migration else 'NO'}")
    print(f"Plan switches: {switches}")
    print(f"Estimated migration cost: ${migration_cost:.4f}")
    print("=" * 60)

    return first_target


def invoke_migration(source, target):
    """
    Invoke an explicitly configured migration command.

    The command must implement and verify the actual migration.
    This function does not assume that a local migrate.sh can
    migrate between separate VMs.
    """
    if not EXECUTE_MIGRATION:
        print(
            "\nMigration execution is disabled. "
            "Only the recommendation was produced."
        )
        return False

    if not MIGRATION_COMMAND:
        print(
            "\nMigration was NOT executed: MIGRATION_COMMAND "
            "is not configured."
        )
        return False

    command = MIGRATION_COMMAND.format(
        source=source,
        target=target,
    )

    print(f"\nExecuting configured migration: {source} -> {target}")

    result = subprocess.run(
        shlex.split(command),
        check=False,
    )

    if result.returncode != 0:
        print(
            f"Migration command failed with exit code "
            f"{result.returncode}."
        )
        return False

    print(
        "Migration command exited successfully. "
        "Verify the destination container is running and "
        "the source container is stopped before confirming success."
    )
    return True


def main():
    if CURRENT_NODE not in NODES:
        raise ValueError(
            f"CURRENT_NODE must be one of {NODES}"
        )

    random.seed()

    current_node_index = NODES.index(CURRENT_NODE)
    forecast = build_forecast()

    best_plan = run_ga(forecast, current_node_index)
    recommended_node = print_plan(
        best_plan, forecast, CURRENT_NODE
    )

    # Compare average historical score for the same observations.
    current_score = sum(
        step_score(state)
        for state in forecast[CURRENT_NODE]
    ) / len(forecast[CURRENT_NODE])

    target_score = sum(
        step_score(state)
        for state in forecast[recommended_node]
    ) / len(forecast[recommended_node])

    improvement = current_score - target_score

    print(f"\nCurrent VM average score: {current_score:.4f}")
    print(f"Recommended VM average score: {target_score:.4f}")
    print(f"Estimated score improvement: {improvement:.4f}")

    if recommended_node == CURRENT_NODE:
        print(f"\nDecision: STAY on {CURRENT_NODE}.")
        return

    if improvement < MIN_IMPROVEMENT:
        print(
            "\nDecision: STAY. The estimated improvement "
            "does not meet the configured threshold."
        )
        return

    print(
        f"\nDecision: migration recommended "
        f"{CURRENT_NODE} -> {recommended_node}."
    )

    invoke_migration(CURRENT_NODE, recommended_node)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"\nERROR: {error}")
        raise SystemExit(1)
