# ADR-001: MRR Movement Classification

**Status:** Accepted  
**Date:** 2024-01-01  
**Deciders:** Analytics Engineering

---

## Context

Every revenue analytics system must answer: *why did MRR change?*

The answer requires classifying subscription events into mutually exclusive, collectively exhaustive revenue motions. Most teams define these informally, in ad-hoc queries, in different ways across different reports. This ADR documents the canonical definitions used in this project.

---

## Decision

We classify every subscription event into one of five movement types:

| Movement | Event type | Condition | MRR delta |
|---|---|---|---|
| `new_business` | `subscription_created` | First payment from this subscription | `+ new_mrr` |
| `expansion` | `subscription_changed` | `new_mrr > old_mrr` | `+ (new_mrr - old_mrr)` |
| `contraction` | `subscription_changed` | `new_mrr < old_mrr` | `- (old_mrr - new_mrr)` |
| `churn` | `subscription_cancelled` | Any cancellation | `- old_mrr` |
| `reactivation` | `subscription_reactivated` | Subscription restarts after cancellation | `+ new_mrr` |

The classification logic lives in `models/intermediate/int_mrr_movements.sql`. No mart model should re-derive movement types — they should always join to `int_mrr_movements`.

---

## Key boundary decisions

### Reactivation is not new_business

A returning customer is not a new customer. Conflating them inflates new_business MRR, which misrepresents growth quality. We track reactivation separately so it can be included in or excluded from NRR depending on the context.

### Reactivation is included in NRR

NRR measures "how much of the revenue from a given cohort do we still have?" A reactivated customer is still a customer from that cohort — they cancelled and came back. Excluding reactivations from NRR would understate retention and would differ from how most investors and boards calculate it.

GRR (Gross Revenue Retention) excludes expansion entirely. It is always ≤ NRR and caps at 100%. GRR is the conservative benchmark for measuring pure churn impact.

### Same-month churn and reactivation are preserved

If a customer churns and reactivates in the same calendar month, snapshot-based MRR calculation would show no change (because start-of-month = end-of-month status). Event-based calculation correctly records both the churn and the reactivation as separate revenue motions.

This is why `int_mrr_movements` is built from the event log, not from a monthly subscription snapshot.

### No "resurrection" category

Some vendors distinguish "reactivation" (same subscription ID restarts) from "resurrection" (new subscription from a previously churned account). We don't have multi-subscription-per-account logic in this dataset, so we use a single `reactivation` type. In a production system with multiple subscriptions per account, this distinction would be worth adding.

---

## Consequences

- All revenue reporting builds on `int_mrr_movements`
- The five movement types are enforced as an `accepted_values` test in dbt
- `fct_mrr` uses these types directly — no re-derivation in SQL
- `fct_nrr` includes reactivation in the retention calculation explicitly
