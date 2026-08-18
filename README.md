# Organic Optimization Algorithms for Manufacturing and Production Process Efficiency

A single-machine job scheduling optimizer that minimizes the total earliness/tardiness penalty of a production sequence. The project combines **linear programming** (for optimal timing of a fixed job order) with a **genetic algorithm** (for searching the space of job orders), wrapped in a simple desktop GUI.

## The problem

Given a set of jobs, each with a processing time, a due date, and earliness/tardiness weights, the goal is to find a schedule on a single machine that minimizes the total penalty:

```
minimize   Σ ( vⱼ · Eⱼ + wⱼ · Tⱼ )
```

where for each job *j*: `Eⱼ` is its earliness, `Tⱼ` is its tardiness, `vⱼ` is the earliness weight, and `wⱼ` is the tardiness weight. The decision is the **order** in which jobs run and their exact start/finish times.

## How it works

The solution has two computational engines and a GUI front end.

**Solver Engine** (`Tapi_Project_Solver_Engine.py`) — For a *given* job order, it builds and solves a linear program (using PuLP with the CBC solver) that assigns optimal start (`S`), completion (`C`), earliness (`E`), and tardiness (`T`) values, subject to sequential, non-overlapping execution on one machine. Each LP solve is time-limited to keep the search responsive. It also writes a formatted output Excel file with a results table and a Gantt-style row, filling in idle times where the machine waits.

**Genetic Algorithm Engine** (`Tapi_Project_GA_Engine.py`) — Searches over job orders to find a better sequence than the original. Each *chromosome* is a permutation of jobs, and its fitness is obtained by solving the LP (via the Solver Engine's logic) for that order. The GA uses:

- **Tournament selection** to choose parents,
- **Order Crossover (OX)** to recombine two parent sequences,
- **Inversion mutation** to reverse a random segment of a sequence,
- **Elitism** to carry the best solutions unchanged into the next generation.

It runs generation after generation until a user-defined time limit is reached, then writes the best schedule found to the output Excel file.

**GUI** (`Project_Form.py`) — A small Tkinter window where the user enters the input and output file names, optionally ticks *"Run Genetic Algorithm?"* (unticked runs the plain Solver instead), and clicks **Solve**.

## Files in this repository

| File | Description |
|------|-------------|
| `Project_Form.py` | Tkinter GUI — entry point for running the solver or the GA |
| `Tapi_Project_GA_Engine.py` | Genetic algorithm engine (OX crossover, tournament selection, elitism, inversion mutation) |
| `Tapi_Project_Solver_Engine.py` | LP-based single-order solver (PuLP + CBC) and Excel output writer |
| `Input_Data_File_Example.xlsx` | Example input: job data (tⱼ, dⱼ, vⱼ, wⱼ) and GA parameters |
| `GA_Picture.PNG` | Background image loaded by the GUI |
| `GA_Algorithm_Flowchart.png` | Flowchart of the genetic algorithm |
| `Solver_Algorithm_Flowchart.png` | Flowchart of the LP solver |

## Input file format

The input Excel file contains a jobs table and the GA parameters:

- **Jobs table** — one column per job with rows `tⱼ` (processing time), `dⱼ` (due date), `vⱼ` (earliness weight), `wⱼ` (tardiness weight).
- **GA parameters** — population size, number of elite solutions kept per generation, mutation probability, and the running-time limit in seconds.

## Requirements

Written in Python 3. It uses:

```bash
pip install pandas pulp xlsxwriter openpyxl pillow
```

(`tkinter` ships with the standard Python installation.) The CBC solver is bundled with PuLP.

## Running

```bash
python Project_Form.py
```

Enter the input and output file names in the window, choose whether to run the genetic algorithm, and click **Solve**. The optimized schedule is written to the output Excel file.
