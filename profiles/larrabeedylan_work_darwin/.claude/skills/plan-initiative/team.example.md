# Team

Roster used by `/plan-initiative` to decide who gets what. Copy this file to `team.md`
in the same directory and edit it — `team.md` is gitignored and never leaves your machine.

One `##` section per person. The skill matches the name after `with` in the skill
argument against these headings (first name, case-insensitive), and plans lanes only
for the people named in that argument.

Keep it honest and keep it current. "Ramps slowly on" is not a criticism — it is the
number the plan uses to decide whether teaching costs more than doing, so a vague or
flattering entry produces a worse plan than a blunt one.

---

## Dylan

- **Role:** Staff engineer — usually the initiative owner
- **Seniority:** Senior/staff
- **Specialties:** Platform services, Temporal workflows, GitLab CI, data pipelines
- **Ramps slowly on:** Frontend state management
- **Capacity:** Full, minus ~1 day/week of review and meetings
- **Notes:** Holds the model on most platform work — critical-path tasks in that area
  are cheaper for him to do than to explain. Prefers to keep the integration ticket.

## Victor

- **Role:** Software engineer — new hire (started 2026-07)
- **Seniority:** Mid, ramping on this codebase
- **Specialties:** TypeScript, API design, strong test discipline
- **Ramps slowly on:** Our auth model, Temporal, the tenant isolation rules
- **Capacity:** Full
- **Notes:** Give an early self-contained win, then work with high context locality.
  Off-critical-path tasks in unfamiliar areas are good learning investments; do not
  make him sole owner of a critical-path integration this quarter.

## Aimon

- **Role:** Security engineer
- **Seniority:** Senior
- **Specialties:** AuthN/AuthZ, secrets handling, threat modeling, dependency/supply chain
- **Ramps slowly on:** Our billing domain, frontend
- **Capacity:** 50% — split across security review for other teams
- **Notes:** Security-shaped tickets cost him near-zero ramp. Schedule his work in
  contiguous blocks; half-capacity means fewer wave-days, not smaller tickets.

---

<!--
Fields the skill reads. Extra prose is fine — it gets read too.

- Role / Seniority   → ramp-cost estimates
- Specialties        → zero-ramp matches
- Ramps slowly on    → teach-vs-do decisions, learning-investment assignments
- Capacity           → wave-days available per person
- Notes              → standing preferences ("never give X the migration")
-->
