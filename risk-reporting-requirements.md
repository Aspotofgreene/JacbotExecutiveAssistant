# Risk Reporting Requirements — Executive Dashboard

**Line of Business:** WME
**Reporting period:** Current status (refreshed monthly; first cut May 2026)
**Audience:** Executive leadership (LOB head, CIO, CISO, ORM)
**Author:** Risk Reporting team
**Status:** Draft requirements for development

---

## 1. Purpose

Provide executive leadership with a single, near-real-time view of technology and cyber risk posture for the WME line of business. The dashboard must let an executive answer, in under 60 seconds:

1. Where are we red, yellow, or green against policy thresholds?
2. Which applications, teams, or BMAs are driving the red?
3. What is overdue, past due, or coming due, and who owns it?

The dashboard is not a system of record. It is a reporting layer over existing authoritative sources (ServiceNow, Archer, EIM, ITRM, VMG, LeanIX).

---

## 2. Scope

In scope:

- All applications and infrastructure mapped to LOB = WME.
- The five risk domains listed in section 5.
- Drill-down to the dimensions in section 4.

Out of scope (for v1):

- Write-back to source systems.
- Workflow / remediation tracking beyond display of status.
- Non-WME lines of business (architecture must allow extension; UI scope is WME only).

---

## 3. Common requirements (apply to every metric)

| # | Requirement |
|---|---|
| 3.1 | Each metric must display a current value (count or %), the policy threshold, and a R / Y / G status derived from the threshold. |
| 3.2 | R/Y/G thresholds must be configurable per metric without a code release (config table or admin UI). |
| 3.3 | Each metric must show a trend sparkline for the trailing 13 months. |
| 3.4 | Each metric must be drillable along the dimensions in section 4. |
| 3.5 | Each metric must display: source system, last-refreshed timestamp, and record count behind the value. |
| 3.6 | Every drill-down row must deep-link back to the record in the source system (e.g., Archer finding URL, ServiceNow ticket URL). |
| 3.7 | Stale data (source not refreshed within its SLA — see section 7) must be visually flagged; the metric must not silently show old numbers. |
| 3.8 | Every metric must appear in the glossary (section 8) with a plain-language definition aimed at a non-technical executive. |
| 3.9 | Export to PDF and Excel of the current view, including filters applied. |
| 3.10 | Role-based access: viewer, LOB-admin, global-admin. No PII beyond user IDs already exposed in source systems. |

---

## 4. Drill-down dimensions

Every metric must be filterable and groupable by:

- **LOB** (Line of Business)
- **BMA** (Business Managed Application)
- **App Code**
- **L3 / L4 / L5** organizational hierarchy
- **Tech** (technology / platform owner)

The default landing view is filtered to LOB = WME, all other dimensions = "All".

---

## 5. Metrics

Metrics are grouped into five domains. For each metric the developer must implement: value, threshold, R/Y/G status, trend, drill-down, source link, and glossary entry (per section 3).

### 5.1 Logical Access

Source of record: **ServiceNow**

| ID | Metric | Unit | Notes |
|----|--------|------|-------|
| LA-01 | **AM %** — Access Management compliance | % | % of in-scope user access reviewed / recertified vs. population. R/Y/G against policy threshold. |
| LA-02 | **AR %** — Access Recertification completion | % | % of access recertification campaigns completed on time. |
| LA-03 | **PAM %** — Privileged Access Management compliance | % | % of privileged accounts compliant with PAM controls (vaulted, rotated, monitored). |

### 5.2 Technology & Cyber Risk Management

| ID | Metric | Unit | Source | Notes |
|----|--------|------|--------|-------|
| RM-01 | **ACA overdue** | # | Archer | Application Control Assessments past their due date. |
| RM-02 | **ACA incomplete (bank)** | # | Archer | ACAs started but not completed by the bank-level due date. |
| RM-03 | **EIM — coming due** | # | EIM | Enterprise Issue Management items with due date inside the warning window (define window in config; default 30 days). |
| RM-04 | **EIM — past due** | # | EIM | EIM items past their due date. |
| RM-05 | **IT Risk findings — coming due** | # | ITRM | Findings inside the warning window. |
| RM-06 | **IT Risk findings — past due** | # | ITRM | Findings past their due date. |

Additional requirement: each EIM and ITRM record must surface its **acceptance / extension status** (annotated on the whiteboard as "Accept y's / Remind") so executives can distinguish a true breach from a formally accepted risk or pending extension.

### 5.3 Cyber Security

| ID | Metric | Unit | Source | Notes |
|----|--------|------|--------|-------|
| CS-01 | **Pentest overdue / not started** | # | LeanIX | In-scope apps whose pentest is past due or has never been started. |
| CS-02 | **Pentest vulnerabilities overdue** | # | ITRM / VMG | Findings from pentests past their remediation SLA. Break out by severity (Critical / High / Medium / Low). |
| CS-03 | **ISS not compliant** | # | VMG | Information Security Standards exceptions / non-compliance count. |
| CS-04 | **Tech currency** | # / % | TBD — confirm source | Count and % of components running unsupported / out-of-support versions. |
| CS-05 | **Server hygiene** | # / % | TBD — confirm source | Servers failing baseline hygiene checks (patching, configuration, agent coverage). |

> **Open question for the business:** confirm authoritative source for CS-04 and CS-05 (likely VMG or a CMDB feed) before development starts.

### 5.4 IT Change Management

| ID | Metric | Unit | Source | Notes |
|----|--------|------|--------|-------|
| CM-01 | **Source code management** | TBD | TBD | Definition pending — likely % of apps with code in an approved SCM and branch-protection / scanning enabled. Confirm with Change Management owner before build. |
| CM-02 | **Emergency IT BMA changes** | # | ServiceNow | Count of emergency changes against BMAs in the period. |
| CM-03 | **Risk: Unauthorized IT BMA changes** | # | ServiceNow | Detected changes with no approved change record. |

### 5.5 Technology & Cyber Incident and Recovery

| ID | Metric | Unit | Source | Notes |
|----|--------|------|--------|-------|
| IR-01 | **RTO not assigned** | # | LeanIX | In-scope apps with no Recovery Time Objective defined. |
| IR-02 | **RPO not assigned** | # | LeanIX | In-scope apps with no Recovery Point Objective defined. |
| IR-03 | **RTC longer than RTO** | # | LeanIX | Apps where Recovery Time Capability exceeds the documented RTO (i.e., we cannot recover in time). |
| IR-04 | **DR plan not tested** | # | TBD | Apps with no DR test on record within policy window. |
| IR-05 | **Non-compliant DR testing** | # | TBD | Apps whose last DR test failed or was non-compliant. |
| IR-06 | **P1 / P2 incidents** | # | ServiceNow | Count of P1 and P2 incidents in the period; show separately and combined. |
| IR-07 | **P3 – P5 incidents** | # | ServiceNow | Count of P3, P4, P5 incidents in the period. |

> **Open question for the business:** confirm sources for IR-04 and IR-05.

---

## 6. Visual / UX requirements

- **Landing page**: one tile per metric, grouped by the five domains in section 5, each tile showing value, threshold, R/Y/G, and trend sparkline.
- **Single status roll-up** per domain at the top of each section (worst-of child statuses).
- **Single overall LOB status** at the top of the page (worst-of domain statuses).
- **Drill-down**: clicking a tile opens a list view filtered to the records driving the number, with deep-links back to source.
- **Filters bar**: persistent across the page; filters in section 4.
- **Date control**: "as of" date picker; default = latest refresh.
- **Accessibility**: WCAG 2.1 AA. R/Y/G must not rely on color alone — include text or icon.

---

## 7. Data, refresh, and SLAs

| Source | Expected refresh cadence | Staleness threshold (flag if older than) |
|--------|--------------------------|------------------------------------------|
| ServiceNow | Daily | 36 hours |
| Archer | Daily | 48 hours |
| EIM | Daily | 48 hours |
| ITRM | Daily | 48 hours |
| VMG | Daily | 48 hours |
| LeanIX | Weekly | 10 days |

Cadences are starting assumptions — developers to confirm with each source-system owner and update before sign-off.

Data lineage must be documented: source → ingestion job → warehouse table → metric definition → tile.

---

## 8. Glossary (to be displayed in-product)

A glossary panel must be available from every page. Each term must include a plain-language definition for executives. Initial entries:

- **LOB** — Line of Business.
- **BMA** — Business Managed Application.
- **App Code** — Unique identifier for an application in the inventory.
- **L3 / L4 / L5** — Organizational hierarchy levels below the LOB.
- **AM / AR / PAM** — Access Management, Access Recertification, Privileged Access Management.
- **ACA** — Application Control Assessment.
- **EIM** — Enterprise Issue Management.
- **ITRM** — IT Risk Management.
- **VMG** — Vulnerability Management Group.
- **ISS** — Information Security Standards.
- **Pentest** — Penetration test.
- **RTO / RPO / RTC** — Recovery Time Objective / Recovery Point Objective / Recovery Time Capability.
- **DR** — Disaster Recovery.
- **P1–P5** — Incident priority levels (P1 = highest).
- **R / Y / G** — Red / Yellow / Green status against policy threshold.
- **Coming due / Past due** — Items inside the warning window vs. items past the due date.
- **Accept / Remind** — Risk acceptance status; an "accepted" item has formal sign-off, a "remind" item is awaiting action.

Developers to extend this list during build; product owner signs off before launch.

---

## 9. Non-functional requirements

- **Performance**: landing page < 3s on a corporate laptop; drill-down list < 5s for 10k rows.
- **Availability**: 99.5% during business hours.
- **Auditability**: every metric calculation must be reproducible from stored snapshots; daily snapshot retained 13 months.
- **Security**: SSO via enterprise IdP; least-privilege on source connections; no source-system credentials in client.
- **Logging**: refresh successes/failures alert to the support DL.

---

## 10. Open items for sign-off before development starts

1. Confirm authoritative source for **Tech currency** and **Server hygiene** (CS-04, CS-05).
2. Confirm definition and source for **Source code management** (CM-01).
3. Confirm sources for **DR plan not tested** and **Non-compliant DR testing** (IR-04, IR-05).
4. Confirm policy thresholds (R/Y/G) for every metric — provide as a config table.
5. Confirm warning-window length for "coming due" metrics (default proposed: 30 days).
6. Confirm refresh cadences in section 7 with each source-system owner.
7. Confirm role definitions and entitlement groups for section 3.10.

---

## 11. Acceptance criteria (summary)

The dashboard is accepted when:

- All metrics in section 5 are live, sourced from the systems listed, and matching reconciliation samples agreed with each source owner.
- All section 3 common requirements are demonstrably met for every metric.
- Drill-down dimensions in section 4 work on every tile.
- Glossary in section 8 is in-product and signed off.
- Open items in section 10 are closed.
- A UAT pack signed off by the LOB head and CISO delegate.
