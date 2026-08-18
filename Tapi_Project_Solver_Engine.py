import pandas as pd
import pulp
import xlsxwriter


SOLVER_TIME_LIMIT_SECONDS = 5


# ─────────────────────────────────────────────
#  Helpers  (shared with GA engine)
# ─────────────────────────────────────────────

def fix_xlsx_name(file_name):
    if not file_name.lower().endswith(".xlsx"):
        return file_name + ".xlsx"
    return file_name


def format_regular_number(value):
    if isinstance(value, (int, float)):
        if float(value).is_integer():
            return int(value)
    return value


def format_job_name(job_number):
    return f"j{int(job_number)}"


# ─────────────────────────────────────────────
#  Input reading
# ─────────────────────────────────────────────

def read_input(file_name):
    """Read job data and GA parameters from input Excel file."""
    input_path = fix_xlsx_name(file_name)
    df = pd.read_excel(input_path, sheet_name=0, header=None)

    params = {
        "population_size":      df.iloc[6, 0],
        "elite_count":          df.iloc[8, 0],
        "mutation_probability": df.iloc[10, 0],
        "running_time_limit":   df.iloc[12, 0]
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

    return jobs, params


# ─────────────────────────────────────────────
#  LP Solver
# ─────────────────────────────────────────────

def solve_schedule_for_order(jobs, deadline=None):
    """
    Solves LP for a fixed job order.
    Limit per call: min(5 sec, remaining time to deadline).
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
        remaining = deadline - __import__('time').time()
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
#  Excel output  (xlsxwriter)
# ─────────────────────────────────────────────

def write_output_excel(Output_File_Name, solution,
                       original_solution_value=None,
                       generations_created="-",
                       run_time="-"):
    output_path = fix_xlsx_name(Output_File_Name)

    if original_solution_value is None:
        original_solution_value = solution["objective"]

    results_with_idle = add_idle_times_to_results(solution["results"])

    workbook  = xlsxwriter.Workbook(output_path)
    worksheet = workbook.add_worksheet("Results")

    job_format = workbook.add_format({
        "bg_color": "#AED6F1",
        "border": 1, "align": "center", "valign": "vcenter"
    })
    idle_format = workbook.add_format({
        "bg_color": "#A9DFBF",
        "border": 1, "align": "center", "valign": "vcenter"
    })
    label_format = workbook.add_format({
        "bold": True, "border": 1, "align": "center", "valign": "vcenter"
    })
    value_format = workbook.add_format({
        "border": 1, "align": "center", "valign": "vcenter"
    })
    gantt_job_format = workbook.add_format({
        "bg_color": "#85C1E9",
        "border": 1, "align": "center", "valign": "vcenter", "text_wrap": True
    })
    gantt_idle_format = workbook.add_format({
        "bg_color": "#A9DFBF",
        "border": 1, "align": "center", "valign": "vcenter", "text_wrap": True
    })

    # ── Table rows 1-10 ───────────────────────────────────────────
    row_labels = ["j", "tj", "dj", "vj", "wj", "Sj", "Cj", "Ej", "Tj", "Pj"]

    for r, label in enumerate(row_labels):
        worksheet.write(r, 0, label, label_format)

        for c, item in enumerate(results_with_idle):
            col     = c + 1
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
    worksheet.write("A12", "Total Penalty",    label_format)
    worksheet.write("B12", format_regular_number(solution["objective"]), value_format)

    worksheet.write("A13", "Original Sol",     label_format)
    worksheet.write("B13", format_regular_number(original_solution_value), value_format)

    worksheet.write("A14", "Total Gen Created", label_format)
    worksheet.write("B14", generations_created, value_format)

    worksheet.write("A15", "Run time",         label_format)
    worksheet.write("B15", format_regular_number(run_time), value_format)

    # ── Gantt row 17 ──────────────────────────────────────────────
    worksheet.write("A17", "Gantt:", label_format)

    for c, item in enumerate(results_with_idle):
        col     = c + 1
        is_idle = item["j"] == "Idle"
        s       = float(item["Sj"])
        cv      = float(item["Cj"])

        if is_idle:
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
#  Public entry point: Run_Solver
# ─────────────────────────────────────────────

def Run_Solver(Input_File_Name, Output_File_Na):
    print("SOLVER IS RUNNING")

    jobs, _ = read_input(Input_File_Name)
    solution = solve_schedule_for_order(jobs)

    print(f"Solver status: {solution['status']}")
    print(f"Objective value: {solution['objective']}")

    write_output_excel(Output_File_Na, solution)
    print(f"Solver done. Output: {fix_xlsx_name(Output_File_Na)}")
