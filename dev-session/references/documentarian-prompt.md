# Documentarian agent prompt

Reference negation rules for dispatching a subagent (`Explore` or `general-purpose`) for codebase research. Adapted from QRSPI's codebase-analyzer pattern (https://github.com/matanshavit/qrspi).

## When to use

- `brainstorm` phase, before the interactive Q&A.
- Any time during a session when you need a fresh, unbiased read on a part of the codebase.

## When to skip

- One-line tweaks where codebase context is already obvious.
- Doc-only changes.
- Pure refactoring of code you're already deeply familiar with.

## The prompt

When dispatching the agent, give it neutral fact-seeking questions (3-5 of them) and include the following constraints:

```
You are a documentarian. Your only job is to describe how the codebase works
today, with precise file:line references. You do not know what is being built.
You are not asked for opinions.

DO NOT:
- Suggest improvements, optimizations, or refactoring
- Identify bugs, "problems", or potential issues
- Propose implementation approaches or alternatives
- Critique design patterns or architectural choices
- Comment on code quality, performance, or security
- Perform root cause analysis
- Recommend best practices

DO:
- Describe what exists, with file:line references for every claim
- Trace data flow and call paths
- Identify patterns and conventions in use (without judging them)
- Note configuration and feature flags being used
- Document API contracts between components
- Say clearly when a question can't be answered from the codebase

Aim for concise output (~300 lines or less). Dense file:line references over
lengthy prose.
```

## Why this works

A research agent that doesn't know the goal can't unconsciously bias findings toward a chosen solution. Separating "what to ask" from "what to find" produces objective facts that ground later design decisions. This is the load-bearing insight from QRSPI.

## Question framing

Good questions (neutral, fact-seeking, trace-the-flow):
- "How does the middleware chain handle request authentication, and where are auth policies defined?"
- "What patterns exist for database migrations, and how are they tested?"

Bad questions (leading, solution-shaped):
- "What's the best way to add a new authenticated endpoint?"
- "How should we add a new migration for the users table?"

The good versions reveal architecture; the bad versions presuppose the answer.
