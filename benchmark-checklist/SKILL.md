---
name: benchmark-checklist
description: "Design or assess performance measurements before reporting a speedup, regression, or comparison. Check correctness, completed work, comparable conditions, repeatability, and relevance. Use for benchmarks and measured performance claims, not routine test timings."
license: MIT
---

# Benchmark checklist

Make the measurement support the claim being made. Separate an observed difference from an explanation of its cause, and a microbenchmark from the effect a user experiences.

## Define the comparison

State the proposed claim, metric and unit, workload, dataset size, concurrency, revisions, and environment. Read the harness to establish what it times, counts, and excludes. Include setup in the timed region only when the claim includes setup. Decide whether caches and initialization should be warm or cold, then apply that choice consistently.

Use representative builds, versions, and settings. If comparing implementations, avoid giving one side a debug build or an obviously inappropriate configuration. If the question is specifically about defaults or deployment cost, compare those actual conditions and retain setup or tuning costs in the decision. Do not silently optimize away the scenario the user asked about.

Inspect current machine load and available resources with tools appropriate to the host; do not assume Linux commands exist. Isolate interference when feasible. Do not stop other workloads or change system settings without authorization. Record unavoidable contention and alternate or randomize comparison order to reduce drift.

## Check that the number measures useful work

Before interpreting timings, verify both:

- **Correctness:** count errors, non-success responses, retries, and timeouts; validate output content rather than only its presence. Report failed operations separately so fast rejections cannot look like improved throughput.
- **Completion:** establish that the intended work occurred inside the measured region. Consume lazy results, await asynchronous work, observe the expected requests or side effects, and ensure the runtime cannot discard unused computation.

For an explicitly requested rough estimate, one run can suffice if these two checks hold. Label it a single-run estimate; do not turn it into a reliable comparison or recommendation.

## Repeat and explain

For a comparison, start with at least five runs per side, alternating or randomizing order after consistent warmup. Record the individual results, sample count, median, and spread. Distinguish latency percentiles within each run from the distribution of whole-run measurements. When noise is comparable to the observed gap, report that the sample does not resolve the difference; use more runs or an appropriate statistical method if the decision warrants it. Do not claim equality from an inconclusive sample.

Investigate surprising results and claimed mechanisms with a separate diagnostic run. Profiling or tracing can change timing, so keep those runs out of headline measurements. Look at both the target and load generator for CPU, I/O, locks, memory, or network limits. Map the observed bottleneck to relevant code when possible. If the limiter is unknown, say so; a reproducible timing observation can still stand, while a causal explanation remains unproven.

Check physical and end-to-end limits. Bytes per second must fit the path's bandwidth; a speedup cannot save more time than the changed work previously consumed. If a component accounts for fraction `f` of total time and becomes `s` times faster, the maximum overall speedup under that model is `1 / ((1 - f) + f / s)`. State when overlapping work or a shifted bottleneck makes that model inappropriate.

Pair a microbenchmark with a representative user path before claiming user-visible improvement. If that is unavailable, keep the claim limited to the measured operation. Do not infer overall latency gains from a helper's speedup.

## Report the evidence

Lead with the finding: faster, slower, no difference resolved by this sample, or inconclusive. Give the metric and units, before/after values, sample counts and spread, correctness and work checks, relevant configuration, and evidence limits. Keep causal claims tied to diagnostic evidence.

Preserve raw runs and rerunnable commands in a named artifact when useful, and link it from the concise result. Report revisions and environment so another run can be compared. Respect the request's cost and execution scope; an unreachable service or missing credential is a blocker to that measurement, not permission to switch providers or workloads.

## Source

Adapted from Lauren Tan's pstack [benchmark-checklist](https://github.com/cursor/plugins/blob/d457567332aa6989e753ea289f30ea2bfbc80bc0/pstack/skills/benchmark-checklist/SKILL.md) at revision `d457567332aa6989e753ea289f30ea2bfbc80bc0`. This adaptation uses host-appropriate tools, preserves questions about defaults, and separates measured effects from unverified causal explanations. See [LICENSE](LICENSE).
