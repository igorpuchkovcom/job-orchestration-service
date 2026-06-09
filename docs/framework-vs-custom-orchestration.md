# Framework vs Custom Orchestration

## Why this document exists

This repository was intentionally built as a bounded, deterministic control-plane showcase.  
The interview question is valid: "Why not start with an orchestration framework?"

Short answer: for this scope, the control plane itself was the product boundary, and framework-first adoption would have been premature.

## Frameworks that could have been considered

- `LangChain`: model/tool abstraction helpers and rapid composition utilities.
- `LangGraph`: graph/state-machine execution for branching, loops, and checkpointable agent workflows.
- `CrewAI`: multi-agent orchestration patterns and role-based agent collaboration.
- `Celery` / `RQ` / Redis Streams: background job execution and queue-backed worker scaling.
- `Temporal`: durable workflow execution with retries, timers, and resumability across process restarts.
- `Prefect`: workflow orchestration with scheduling and execution visibility.
- `Argo Workflows`: Kubernetes-native workflow DAG orchestration.

## Why the original orchestration did not require LangChain/LangGraph first

The existing flow is a deterministic one-step orchestration path:

- create job;
- start job;
- execute one provider-backed step;
- persist job/step/event state;
- return bounded result summary.

For this shape, introducing LangGraph/LangChain as the first code change would mostly add ceremony:

- no branching graph to manage yet;
- no multi-step tool loop yet;
- no long-running checkpointed workflow yet;
- no async worker fleet yet.

So the immediate engineering value was to keep the control plane explicit and stable, then improve runtime/model boundaries.

## Why custom orchestration was justified here

This service is not trying to be a generic agent runtime. It is a product-specific control plane with explicit ownership of:

- API contracts;
- lifecycle FSM and transition validity;
- jobs/steps/events persistence;
- auditability and event chronology;
- idempotency and duplicate-start guard;
- normalized error envelope;
- authorization boundary.

Those are domain and platform-control concerns that remain important regardless of which execution framework is used underneath.

## What should remain custom

These concerns are part of service ownership and should stay in this backend:

- API and response contracts;
- lifecycle state model and transition rules;
- persistence model for jobs/steps/events;
- audit trail and operational history;
- idempotency boundaries and request/start guards;
- error normalization and request-correlation behavior;
- authN/authZ boundary enforcement.

## What can move to frameworks later

Framework adoption becomes useful when execution complexity grows beyond deterministic single-step orchestration:

- execution graph and branching workflows;
- multi-step tool chains;
- agent loops and planner/executor patterns;
- durable async execution and resumability;
- long-running workloads with cross-restart retries.

Practical mapping:

- `LangGraph` fits when graph state, branching, and checkpointing become first-order requirements.
- `LangChain` fits as tool/model composition grows and reusable agent/tool abstractions become beneficial.
- `Celery`/`Temporal`/`Argo` fit when async durability, worker scale-out, and operational workflow guarantees are required.

## Why not LangGraph as the first change in this repo

Because it would not have addressed the highest-risk gap raised in feedback.  
The core gap was not "missing graph runtime"; it was "show clearer AI-platform boundaries: model identity, runtime adapter choices, and inference metrics."

For this bounded showcase, the right sequence is:

1. keep control-plane ownership explicit;
2. make runtime/model boundary pluggable;
3. add lightweight inference metadata/metrics;
4. introduce execution frameworks later when workflow complexity justifies them.

## What framework adoption would NOT solve by itself

Using LangGraph/Celery/Temporal/Argo does not automatically provide:

- model registry design and governance;
- serving runtime implementation;
- GPU scheduling;
- OpenNebula/Kubernetes deployment integration;
- inference metrics strategy;
- production observability stack.

Those are separate platform concerns that require explicit architecture and operations work.
