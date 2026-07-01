# Data Dictionary

This document describes the dataset columns and their business role. Detailed exploration results are kept in the data understanding notebook.

| Column | Description | Type | Business Role |
| ------ | ----------- | ---- | ------------- |
| number | Incident identifier. | Text | Unique business key for incident tracking. |
| incident_state | Current lifecycle state of the incident. | Text | Supports incident status and workflow analysis. |
| active | Indicates whether the incident is still active. | Boolean | Helps separate open and closed incidents. |
| reassignment_count | Number of times the incident was reassigned. | Integer | Proxy for routing complexity and operational friction. |
| reopen_count | Number of times the incident was reopened. | Integer | Indicator of resolution quality. |
| sys_mod_count | Number of system updates on the record. | Integer | Proxy for handling effort and activity volume. |
| made_sla | Indicates whether the incident met SLA requirements. | Boolean | Main SLA compliance indicator. |
| caller_id | Anonymized caller identifier. | Text | Supports demand and requester pattern analysis. |
| opened_by | User who opened the incident. | Text | Helps understand ticket creation channels and ownership. |
| opened_at | Incident opening timestamp. | Date/Time | Starting point for aging, trend and resolution time analysis. |
| sys_created_by | User or process that created the record. | Text | Supports data lineage and creation pattern checks. |
| sys_created_at | System creation timestamp. | Date/Time | Used to compare opening and system creation timing. |
| sys_updated_by | Last user or process that updated the record. | Text | Supports update and ownership checks. |
| sys_updated_at | Last system update timestamp. | Date/Time | Useful for activity recency and aging analysis. |
| contact_type | Channel used to report the incident. | Text | Enables channel performance comparison. |
| location | Anonymized location associated with the incident. | Text | Supports geographic or site-level analysis. |
| category | Main incident category. | Text | Key dimension for service performance analysis. |
| subcategory | More detailed incident category. | Text | Helps identify specific drivers of workload and delays. |
| u_symptom | Reported symptom. | Text | Supports root-cause and demand pattern analysis. |
| cmdb_ci | Configuration item linked to the incident. | Text | Connects incidents to impacted assets or services. |
| impact | Business impact level. | Text | Used for severity and prioritization analysis. |
| urgency | Urgency level. | Text | Used with impact to evaluate prioritization. |
| priority | Incident priority. | Text | Key dimension for SLA and operational performance. |
| assignment_group | Support group assigned to the incident. | Text | Main dimension for support team performance. |
| assigned_to | User assigned to the incident. | Text | Supports analyst-level workload analysis when appropriate. |
| knowledge | Indicates whether a knowledge article was used or linked. | Boolean | Helps assess knowledge management contribution. |
| u_priority_confirmation | Indicates whether priority was confirmed. | Boolean | Supports quality checks around prioritization. |
| notify | Notification setting. | Text | Describes communication handling for the incident. |
| problem_id | Related problem record, if any. | Text | Links incidents to problem management. |
| rfc | Related change request, if any. | Text | Links incidents to change management. |
| vendor | Related vendor, if any. | Text | Supports third-party dependency analysis. |
| caused_by | Related cause or change reference. | Text | Helps identify incidents caused by known events. |
| closed_code | Closure code. | Text | Supports closure reason and resolution pattern analysis. |
| resolved_by | User who resolved the incident. | Text | Supports resolution ownership analysis. |
| resolved_at | Resolution timestamp. | Date/Time | End point for resolution time calculation. |
| closed_at | Closure timestamp. | Date/Time | End point for closure delay and lifecycle analysis. |
