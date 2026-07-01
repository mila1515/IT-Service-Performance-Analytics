# IT Service Performance Analytics

## Project Overview

This project simulates a real-world Data Analyst mission within an IT department (ITSM).

Using a ServiceNow incident management dataset, the objective is to analyze IT service performance, monitor SLA compliance, identify operational bottlenecks and provide actionable business insights through SQL, Python and Power BI.

The project follows a complete analytics workflow similar to what is implemented in an enterprise environment.

---

## Project Workflow

```
Raw ServiceNow Data
        │
        ▼
Business Understanding
        │
        ▼
Data Understanding & Exploration
        │
        ▼
Data Cleaning & Transformation
        │
        ▼
SQL Analytics & KPI Calculation
        │
        ▼
Power BI Dashboard & Visualization
        │
        ▼
Business Recommendations & Insights
```

---

## Business Context

An IT department receives thousands of incidents every month through ServiceNow.

Although large amounts of operational data are available, managers lack consolidated indicators to monitor service quality and identify improvement opportunities.

As a Data Analyst, my mission is to transform raw incident data into business insights that support operational and strategic decision-making.

---

## Business Objectives

- Analyze incident management performance.
- Measure SLA compliance.
- Identify the main causes of service delays.
- Evaluate support team performance.
- Build executive dashboards.
- Provide data-driven recommendations.

---

## Project Deliverables

At the end of the project, the repository will include:

- Enterprise-grade data cleaning pipeline
- Exploratory data analysis notebook
- SQL analytical queries
- Power BI executive dashboard
- Business recommendations report
- Complete project documentation

---

## Key Performance Indicators

The project focuses on monitoring the following KPIs:

- **SLA Compliance Rate** – Percentage of incidents resolved within SLA
- **SLA Breach Rate** – Percentage of incidents exceeding SLA
- **Average Resolution Time** – Mean time to resolve incidents
- **Average Closure Time** – Mean time from incident creation to closure
- **Reassignment Rate** – Percentage of incidents reassigned
- **Reopen Rate** – Percentage of incidents reopened
- **Incident Volume** – Total incident count and trends
- **Support Team Performance** – Per-team resolution metrics

---

## Technologies

- Python
- Pandas
- SQL
- Power BI
- Git & GitHub
- uv

---

## Skills Demonstrated

- Data Cleaning & Transformation
- Exploratory Data Analysis
- SQL Analytics & Query Optimization
- Business Intelligence & Dashboarding
- KPI Design & Measurement
- Data Visualization & Storytelling
- Business Context Understanding
- Git Version Control
- Enterprise Documentation

---

## Environment Setup

This project uses `uv` for Python dependency management.

```powershell
uv sync
```

To launch Jupyter:

```powershell
uv run jupyter notebook
```

The Python version is defined in `.python-version`, and project dependencies are defined in `pyproject.toml`.

---

## Dataset

Incident Management Process Enriched Event Log

- 141,712 events
- 24,918 incidents
- 36 variables

Source:
(UCI Machine Learning Repository)

---

## Project Documentation

- [Business Context](docs/Business_Context.md)
- [Project Plan](docs/Project_Plan.md)
- [Data Dictionary](docs/Data_Dictionary.md)
- [KPI Definitions](docs/KPI_Definition.md)
- [Project Architecture](docs/Architecture.md)

---

## Repository Structure

```
IT-Service-Performance-Analytics/
│
├── data/
│   ├── raw/
│   │   └── incident_event_log.csv
│   └── processed/
│
├── notebooks/
│   ├── 01_Data_Understanding.ipynb
│   ├── 02_Data_Cleaning.ipynb
│   ├── 03_Exploratory_Data_Analysis.ipynb
│   ├── 04_SQL_Analysis.ipynb
│   └── 05_Business_Insights.ipynb
│
├── sql/
│   └── [analytical queries & KPI calculations]
│
├── dashboard/
│   └── [Power BI files]
│
├── reports/
│   └── [business insights & recommendations]
│
├── docs/
│   ├── Business_Context.md
│   ├── Project_Plan.md
│   ├── Data_Dictionary.md
│   ├── KPI_Definition.md
│   └── Architecture.md
│
├── README.md
├── pyproject.toml
└── .python-version
```

---

## Project Status

| Phase | Status | Notes |
|-------|--------|-------|
| Business Understanding | ✅ Completed | Context, objectives, and KPIs defined |
| Data Understanding | 🚧 In Progress | Exploring dataset structure and variables |
| Data Cleaning | ⏳ Planned | Handling missing values and data quality |
| Exploratory Data Analysis | ⏳ Planned | Statistical analysis and visualization |
| SQL Analysis | ⏳ Planned | KPI calculations and analytical queries |
| Power BI Dashboard | ⏳ Planned | Executive dashboard creation |
| Business Insights | ⏳ Planned | Recommendations and conclusions |
