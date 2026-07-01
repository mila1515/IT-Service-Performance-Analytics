# KPI Definitions

This document defines the main business indicators planned for the project. Final formulas may be refined after data cleaning and validation.

## SLA Compliance Rate

Percentage of incidents that met their SLA target.

```text
SLA Compliance Rate = Incidents with made_sla = True / Total incidents
```

## SLA Breach Rate

Percentage of incidents that did not meet their SLA target.

```text
SLA Breach Rate = Incidents with made_sla = False / Total incidents
```

## Average Resolution Time

Average time between incident opening and resolution.

```text
Average Resolution Time = Average(resolved_at - opened_at)
```

## Average Closure Time

Average time between incident opening and closure.

```text
Average Closure Time = Average(closed_at - opened_at)
```

## Reassignment Rate

Share of incidents reassigned at least once.

```text
Reassignment Rate = Incidents with reassignment_count > 0 / Total incidents
```

## Reopen Rate

Share of incidents reopened at least once.

```text
Reopen Rate = Incidents with reopen_count > 0 / Total incidents
```

## Incident Volume

Number of incidents opened over a selected period.

```text
Incident Volume = Count of distinct incident numbers
```

## Performance Dimensions

The KPIs should be analyzed by:

- Assignment group
- Category and subcategory
- Priority
- Impact and urgency
- Contact type
- Location
- Time period
