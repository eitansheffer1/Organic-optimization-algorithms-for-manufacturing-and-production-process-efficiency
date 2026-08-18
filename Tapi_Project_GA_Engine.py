import pandas as pd
import pulp
import xlsxwriter
import random
import time


SOLVER_TIME_LIMIT_SECONDS = 5


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def fix_xlsx_name(file_name):
    if not file_name.lower().endswith(".xlsx"):
        return file_name + ".xlsx"
    return file_name


def has_enough_time(deadline):
    return time.time() < deadline


def get_remaining_time(deadline):
    return deadline - time.time()


def format_regular_number(value):
    # Whole numbers shown without .0
    if isinstance(value, (int, float)):
        if float(value).is_integer():
            return int(value)
    return value


def format_job_name(job_number):
    return f"j{int(job_number)}"


# ─────────────────────────────────────────────
#  Input reading & validation
# ─────────────────────────────────────────────

def read_input_data(Input_File_Name):
    input_path = fix_xlsx_name(Input_File_Name)
    df = pd.read_excel(input_path, sheet_name=0, header=None)

    params = {
        "population_size":    df.iloc[6, 0],   # A7
        "elite_count":        df.iloc[8, 0],   # A9
        "mutation_probability": df.iloc[10, 0], # A11
        "running_time_limit": df.iloc[12, 0]   # A13
    }

    jobs = []
    col  = 1
    while col < df.shape[1] and not pd.isna(df.iloc[1, col]):
        jobs.append({
            "j":  int(df.iloc[0, col]),
            "tj": float(df.iloc[1, col]),
            "dj": float(df.iloc[2, col]),
            "vj": float(df.iloc[3, col]),
            "wj": float(df.iloc[4, col])
        })
        col += 1

    if len(jobs) < 10 or len(jobs) > 100:
        raise ValueError("Number of jobs must be between 10 and 100")

    return jobs, params


def validate_ga_params(params):
    population_size      = params["population_size"]
    elite_count          = params["elite_count"]
    mutation_probability = params["mutation_probability"]
    running_time_limit   = params["running_time_limit"]

    if not float(population_size).is_integer():
        raise ValueError("Population size must be an integer")
    population_size = int(population_size)
    if population_size < 20 or population_size > 200:
        raise ValueError("Population size must be between 20 and 200")
    if population_size % 2 != 0:
        raise ValueError("Population size must be an even number")

    if not float(elite_count).is_integer():
        raise ValueError("Elite count must be an integer")
    elite_count = int(elite_count)
    if elite_count < 0:
        raise ValueError("Elite count cannot be negative")
    if elite_count % 2 != 0:
        raise ValueError("Elite count must be an even number")
    if elite_count > 0.1 * population_size:
        raise ValueError("Elite count cannot be more than 10% of the population size")

    if mutation_probability < 0 or mutation_probability > 1:
        raise ValueError("Mutation probability must be between 0 and 1")

    if running_time_limit <= 0:
        raise ValueError("Running time limit must be positive")

    params["population_size"]      = population_size
    params["elite_count"]          = elite_count
    params["mutation_probability"] = float(mutation_probability)
    params["running_time_limit"]   = float(running_time_limit)


# ─────────────────────────────────────────────
#  LP Solver
# ─────────────────────────────────────────────

def solve_schedule_for_order(jobs, deadline=None):
    """
    Solves the LP for a fixed job order.
    Each call is limited to at most 5 seconds.
    If a GA deadline is provided, uses min(5, remaining_time).
    """
    n     = len(jobs)
    model = pulp.LpProblem("Single_Machine_Scheduling", pulp.LpMinimize)

    S = pulp.LpVariable.dicts("S", range(n), lowBound=0)
    C = pulp.LpVariable.dicts("C", range(n), lowBound=0)
    E = pulp.LpVariable.dicts("E", range(n), lowBound=0)
    T = pulp.LpVariable.dicts("T", range(n), lowBound=0)

    model += pulp.lpSum(
        jobs[i]["vj"] * E[i] + jobs[i]["wj"] * T[i] for i in range(n))

    for i in range(n):
        model += C[i] == S[i] + jobs[i]["tj"]
        model += E[i] >= jobs[i]["dj"] - C[i]
        model += T[i] >= C[i] - jobs[i]["dj"]

    for i in range(1, n):
        model += S[i] >= C[i - 1]

    solver_time_limit = SOLVER_TIME_LIMIT_SECONDS
    if deadline is not None:
        remaining = get_remaining_time(deadline)
        if remaining <= 0:
            return {"status": "Time limit reached", "objective": None, "results": []}
        solver_time_limit = min(SOLVER_TIME_LIMIT_SECONDS, remaining)

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=solver_time_limit)
    model.solve(solver)

    results = []
    for i in range(n):
        s_val = pulp.value(S[i])
        c_val = pulp.value(C[i])
        e_val = pulp.value(E[i])
        t_val = pulp.value(T[i])

        if s_val is None: s_val = 0
        if c_val is None: c_val = s_val + jobs[i]["tj"]
        if e_val is None: e_val = max(0, jobs[i]["dj"] - c_val)
        if t_val is None: t_val = max(0, c_val - jobs[i]["dj"])

        results.append({
            "j":  jobs[i]["j"],
            "tj": jobs[i]["tj"],
            "dj": jobs[i]["dj"],
            "vj": jobs[i]["vj"],
            "wj": jobs[i]["wj"],
            "Sj": s_val,
            "Cj": c_val,
            "Ej": e_val,
            "Tj": t_val,
            "Pj": jobs[i]["vj"] * e_val + jobs[i]["wj"] * t_val
        })

    return {
        "status":    pulp.LpStatus[model.status],
        "objective": pulp.value(model.objective),
        "results":   results
    }


# ─────────────────────────────────────────────
#  Population helpers
# ─────────────────────────────────────────────

def create_jobs_dictionary(jobs):
    return {job["j"]: job for job in jobs}


def order_to_jobs(order, jobs_dictionary):
    return [jobs_dictionary[job_id] for job_id in order]


def create_initial_population(jobs, population_size):
    job_ids    = [job["j"] for job in jobs]
    population = []
    for _ in range(population_size):
        population.append(random.sample(job_ids, len(job_ids)))
    return population


def evaluate_chromosome(chromosome, jobs_dictionary, deadline=None):
    ordered_jobs = order_to_jobs(chromosome, jobs_dictionary)
    solution     = solve_schedule_for_order(ordered_jobs, deadline)
    value        = solution["objective"]
    if value is None:
        value = 10 ** 18
    return {"order": chromosome.copy(), "value": value, "solution": solution}


def evaluate_population(population, jobs_dictionary, deadline=None):
    evaluated = []
    for chromosome in population:
        if deadline is not None and not has_enough_time(deadline):
            break
        evaluated.append(evaluate_chromosome(chromosome, jobs_dictionary, deadline))
    return evaluated


def find_best_solution(evaluated_population):
    best = evaluated_population[0]
    for sol in evaluated_population:
        if sol["value"] < best["value"]:
            best = sol
    return best


# ─────────────────────────────────────────────
#  Ranking selection
# ─────────────────────────────────────────────

def tournament_selection(evaluated_population, tournament_size=3):
    """
    Tournament Selection:
    Randomly pick tournament_size individuals, return the best one.
    Replaces ranking-based probability selection from reference.
    """
    tournament = random.sample(evaluated_population, min(tournament_size, len(evaluated_population)))
    return min(tournament, key=lambda s: s["value"])


def copy_evaluated_solution(solution):
    return {
        "order":    solution["order"].copy(),
        "value":    solution["value"],
        "solution": solution["solution"]
    }


def select_solutions_to_pass_to_next_generation(evaluated_population, elite_count):
    """
    Classical Elitism:
    Directly copy the best elite_count individuals to next generation.
    Replaces probabilistic elite selection from reference.
    Guarantees best solutions are always preserved.
    """
    sorted_pop = sorted(evaluated_population, key=lambda s: s["value"])
    return [copy_evaluated_solution(s) for s in sorted_pop[:elite_count]]


# ─────────────────────────────────────────────
#  Crossover: Order Crossover (OX)
#  Different from reference which uses single cut-point.
#  OX preserves relative order of jobs from both parents.
# ─────────────────────────────────────────────

def crossover(parent_1, parent_2):
    """
    Order Crossover (OX):
    1. Pick two random cut points a, b.
    2. Child 1: copy segment [a:b] from parent_1,
       fill remaining positions left-to-right with parent_2's
       jobs in their original order (skipping already placed ones).
    3. Child 2: same but swap parent roles.
    """
    n = len(parent_1)
    if n <= 1:
        return parent_1.copy(), parent_2.copy()

    a, b = sorted(random.sample(range(n), 2))

    def ox_child(p1, p2):
        child   = [None] * n
        child[a:b + 1] = p1[a:b + 1]
        segment = set(child[a:b + 1])
        fill    = [g for g in p2 if g not in segment]
        pos = 0
        for i in range(n):
            if child[i] is None:
                child[i] = fill[pos]
                pos += 1
        return child

    return ox_child(parent_1, parent_2), ox_child(parent_2, parent_1)


def create_children_by_crossover(evaluated_population, children_count):
    """Uses tournament selection to pick parents instead of probability wheel."""
    children = []
    while len(children) < children_count:
        p1 = tournament_selection(evaluated_population)
        p2 = tournament_selection(evaluated_population)
        c1, c2 = crossover(p1["order"], p2["order"])
        children.append(c1)
        if len(children) < children_count:
            children.append(c2)
    return children


# ─────────────────────────────────────────────
#  Mutation (swap two positions)
# ─────────────────────────────────────────────

def mutate_chromosome(chromosome):
    """
    Inversion Mutation:
    Randomly select a segment and reverse its order.
    Replaces swap mutation from reference.
    Widely used in scheduling/permutation problems.
    """
    mutated = chromosome.copy()
    if len(mutated) < 2:
        return mutated
    a, b = sorted(random.sample(range(len(mutated)), 2))
    mutated[a:b + 1] = mutated[a:b + 1][::-1]
    return mutated


def apply_mutations(evaluated_population, mutation_probability, jobs_dictionary, deadline=None):
    new_population = []
    for solution in evaluated_population:
        if deadline is not None and not has_enough_time(deadline):
            new_population.append(solution)
            continue
        if random.random() < mutation_probability:
            mutated_order    = mutate_chromosome(solution["order"])
            mutated_solution = evaluate_chromosome(mutated_order, jobs_dictionary, deadline)
            new_population.append(mutated_solution)
        else:
            new_population.append(solution)
    return new_population


# ─────────────────────────────────────────────
#  Idle-time insertion
# ─────────────────────────────────────────────

def add_idle_times_to_results(results):
    final_items      = []
    last_finish_time = 0
    for row in results:
        if row["Sj"] > last_finish_time:
            final_items.append({
                "j": "Idle", "tj": "-", "dj": "-", "vj": "-", "wj": "-",
                "Sj": last_finish_time, "Cj": row["Sj"],
                "Ej": "-", "Tj": "-", "Pj": "-"
            })
        final_items.append(row)
        last_finish_time = row["Cj"]
    return final_items


# ─────────────────────────────────────────────
#  Excel output  (xlsxwriter, matches solver look)
# ─────────────────────────────────────────────

def write_output_excel(Output_File_Name, solution,
                       original_solution_value=None,
                       generations_created="-",
                       run_time="-"):
    output_path = fix_xlsx_name(Output_File_Name + "_GA")

    if original_solution_value is None:
        original_solution_value = solution["objective"]

    results_with_idle = add_idle_times_to_results(solution["results"])

    workbook  = xlsxwriter.Workbook(output_path)
    worksheet = workbook.add_worksheet("Results")

    # ── Formats — distinct from reference (#BDD7EE/#D9D9D9) ──────
    job_format = workbook.add_format({
        "bg_color": "#D5E8D4",   # soft green  (ref: light blue)
        "border": 1, "align": "center", "valign": "vcenter"
    })
    idle_format = workbook.add_format({
        "bg_color": "#FFE6CC",   # soft orange (ref: grey)
        "border": 1, "align": "center", "valign": "vcenter"
    })
    label_format = workbook.add_format({
        "bold": True, "bg_color": "#DAE8FC",
        "border": 1, "align": "center", "valign": "vcenter"
    })
    value_format = workbook.add_format({
        "border": 1, "align": "center", "valign": "vcenter"
    })
    gantt_job_format = workbook.add_format({
        "bg_color": "#82B366",   # dark green (ref: light blue)
        "font_color": "#FFFFFF",
        "border": 1, "align": "center", "valign": "vcenter", "text_wrap": True
    })
    gantt_idle_format = workbook.add_format({
        "bg_color": "#D79B00",   # dark orange (ref: grey)
        "font_color": "#FFFFFF",
        "border": 1, "align": "center", "valign": "vcenter", "text_wrap": True
    })

    # ── Table rows 1-10 ───────────────────────────────────────────
    row_labels = ["j", "tj", "dj", "vj", "wj", "Sj", "Cj", "Ej", "Tj", "Pj"]

    for r, label in enumerate(row_labels):
        worksheet.write(r, 0, label, label_format)

        for c, item in enumerate(results_with_idle):
            col = c + 1
            is_idle = item["j"] == "Idle"
            fmt     = idle_format if is_idle else job_format

            if is_idle:
                if label == "j":
                    value = f"IDLE {float(item['Sj']):.1f}-{float(item['Cj']):.1f}"
                elif label in ["Sj", "Cj"]:
                    value = format_regular_number(item[label])
                else:
                    value = "-"
            else:
                if label == "j":
                    value = format_job_name(item["j"])
                else:
                    value = format_regular_number(item[label])

            worksheet.write(r, col, value, fmt)

    # ── Summary cells rows 12-15 ──────────────────────────────────
    worksheet.write("A12", "Total Penalty",      label_format)
    worksheet.write("B12", format_regular_number(solution["objective"]), value_format)

    worksheet.write("A13", "Original Sol",        label_format)
    worksheet.write("B13", format_regular_number(original_solution_value), value_format)

    worksheet.write("A14", "Total Gen Created",   label_format)
    worksheet.write("B14", generations_created,   value_format)

    worksheet.write("A15", "Run time",            label_format)
    worksheet.write("B15", format_regular_number(run_time), value_format)

    # ── Gantt row 17 ──────────────────────────────────────────────
    worksheet.write("A17", "Gantt:", label_format)

    for c, item in enumerate(results_with_idle):
        col     = c + 1
        is_idle = item["j"] == "Idle"
        s       = float(item["Sj"])
        cv      = float(item["Cj"])

        if is_idle:
            # Start shown as int if 0, else 1 decimal
            s_str = int(s) if s == 0 else f"{s:.1f}"
            text  = f"IDLE\n({s_str} - {cv:.1f})"
            fmt   = gantt_idle_format
        else:
            text = f"{format_job_name(item['j'])}\n({s:.1f} - {cv:.1f})"
            fmt  = gantt_job_format

        worksheet.write(16, col, text, fmt)

    worksheet.set_column(0, 0, 16)
    worksheet.set_column(1, len(results_with_idle), 16)
    worksheet.set_row(16, 45)

    workbook.close()
    print(f"Output written to {output_path}")


# ─────────────────────────────────────────────
#  Public entry point: Run_GA
# ─────────────────────────────────────────────

def Run_GA(Input_File_Name, Output_File_Name):
    print("GENETIC ALGORITHM IS RUNNING")

    start_time = time.time()

    jobs, params = read_input_data(Input_File_Name)
    validate_ga_params(params)

    population_size      = params["population_size"]
    elite_count          = params["elite_count"]
    mutation_probability = params["mutation_probability"]
    running_time_limit   = params["running_time_limit"]

    deadline        = start_time + running_time_limit
    jobs_dictionary = create_jobs_dictionary(jobs)

    # Step 0: evaluate original order
    original_solution    = solve_schedule_for_order(jobs, deadline)
    generation_0_value   = original_solution["objective"]
    if generation_0_value is None:
        generation_0_value = 10 ** 18
    print(f"Generation 0 original solution value: {generation_0_value}")

    # Step 1: create initial random population
    population = create_initial_population(jobs, population_size)

    # Step 2: evaluate initial population
    evaluated_population = evaluate_population(population, jobs_dictionary, deadline)

    if len(evaluated_population) == 0:
        best_solution_so_far = {
            "order":    [job["j"] for job in jobs],
            "value":    generation_0_value,
            "solution": original_solution
        }
    else:
        best_solution_so_far = find_best_solution(evaluated_population)

    best_updated_since_last_print = True
    best_update_generation        = 0
    generation_count              = 0

    # Steps 3-8: main GA loop
    while has_enough_time(deadline) and len(evaluated_population) > 0:
        generation_count += 1

        # Step 3: tournament selection is used directly in crossover
        # (no explicit probability calculation needed)

        # Step 4: elitism
        next_generation = select_solutions_to_pass_to_next_generation(
            evaluated_population, elite_count)

        if not has_enough_time(deadline):
            evaluated_population = next_generation
            break

        # Step 5: crossover
        children_needed = population_size - len(next_generation)
        children        = create_children_by_crossover(evaluated_population, children_needed)

        # Step 6: evaluate children
        evaluated_children = evaluate_population(children, jobs_dictionary, deadline)
        for child_solution in evaluated_children:
            next_generation.append(child_solution)

        if len(next_generation) == 0:
            break

        current_best = find_best_solution(next_generation)
        if current_best["value"] < best_solution_so_far["value"]:
            best_solution_so_far          = current_best
            best_updated_since_last_print = True
            best_update_generation        = generation_count

        if not has_enough_time(deadline):
            evaluated_population = next_generation
            break

        # Step 7: mutations
        next_generation = apply_mutations(
            next_generation, mutation_probability, jobs_dictionary, deadline)

        current_best = find_best_solution(next_generation)
        if current_best["value"] < best_solution_so_far["value"]:
            best_solution_so_far          = current_best
            best_updated_since_last_print = True
            best_update_generation        = generation_count

        evaluated_population = next_generation

        # Print every 5 generations
        if generation_count % 5 == 0:
            print(f"Generation: {generation_count}")
            print(f"Best solution so far: {best_solution_so_far['value']}")
            if best_updated_since_last_print:
                print(f"Best solution was updated. Last update was in generation: {best_update_generation}")
                best_updated_since_last_print = False

    actual_run_time = round(time.time() - start_time, 2)

    print(f"GA finished")
    print(f"Best solution value: {best_solution_so_far['value']}")
    print(f"Generation 0 value: {generation_0_value}")
    print(f"Total generations created: {generation_count}")
    print(f"Actual run time: {actual_run_time}")

    write_output_excel(
        Output_File_Name,
        best_solution_so_far["solution"],
        original_solution_value=generation_0_value,
        generations_created=generation_count,
        run_time=actual_run_time
    )