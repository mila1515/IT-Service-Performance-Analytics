# Project Architecture

This document describes the global structure of the analytics workflow. Detailed analysis, Python code and outputs are kept in the notebooks.

## Analytics Workflow

```text
Raw Data
    |
    v
01_Data_Understanding
    |
    v
02_Data_Cleaning
    |
    v
03_EDA
    |
    v
SQL Database
    |
    v
Power BI Dashboard
    |
    v
Business Recommendations
```

## Repository Structure

```text
IT-Service-Performance-Analytics/
|
|-- data/
|   |-- raw/
|   `-- processed/
|
|-- docs/
|   |-- Business_Context.md
|   |-- Project_Plan.md
|   |-- Data_Dictionary.md
|   |-- KPI_Definition.md
|   `-- Architecture.md
|
|-- notebooks/
|   `-- 01_Data_Understanding.ipynb
|
|-- README.md
|-- pyproject.toml
`-- uv.lock
```

## Separation of Responsibilities

- `README.md` presents the project and helps recruiters or reviewers understand the scope quickly.
- `docs/` contains project documentation: business context, planning, data dictionary, KPI definitions and architecture.
- `notebooks/` contains executable analysis steps, including Python code, outputs and business interpretation.
- `data/` stores raw and processed datasets.
