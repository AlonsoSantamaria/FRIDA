# FRIDA — Autonomous Strategic Urban Intelligence

**FRIDA = Foresight & Resilience Intelligence for Dynamic Administration**

> **Nobody asked her. She noticed.**

FRIDA is an autonomous strategic urban intelligence system designed to notice meaningful change before decision-makers think to ask about it.

She does **not** watch people. She watches the city.

FRIDA observes authorized public evidence, separates routine activity from strategically relevant change, investigates bounded questions, preserves provenance and uncertainty, and produces durable strategic briefings under deterministic governance.

## Judge Quick Start

**Public demo:** https://frida-zz37olzlja-pv.a.run.app

No credentials are required. The demonstration is public and read-only.

For the fastest judge path, open the app and follow:

1. **FRIDA in Action** — current London observation and live activity.
2. **Briefings** — durable current and historical strategic briefs.
3. **Current Strategic Brief** — deterministic Yellow posture with the semantic assessment `POSSIBLE / INTERVENTION_OPPORTUNITY`.
4. **FRIDA Explained** — deterministic controls + bounded cognitive stages.
5. **Under the Hood** — real persisted observation and appraisal events.
6. **Raw Governed Appraisal Record** — structured facts, evidence references, provenance, uncertainty, and advisory state.
7. **Historical Briefings** — evidence-time cutoffs that preserve historical integrity.

See the full **Judge Quick Start + User Guide + Roadmap** in [`docs/JUDGE_QUICK_START_USER_GUIDE_ROADMAP.md`](docs/JUDGE_QUICK_START_USER_GUIDE_ROADMAP.md).

## What FRIDA Does

FRIDA follows a governed strategic workflow:

**Observe → Appraise → Investigate → Look Ahead → Govern → Brief**

The system is deliberately built around one architectural rule:

> **Determinism establishes what is true and what is allowed. Cognition explores what it might mean.**

Deterministic controls govern source authorization, provenance, normalization, eligibility, evidence-time boundaries, persisted state, and what claims may be surfaced.

Gemini is used only inside bounded cognitive stages to explore possible meaning, relationships, implications, missing evidence, and strategic questions.

The result is an autonomous multi-step workflow — **not** a runtime fleet of independent sub-agents.

## Current Demonstration

The public assignment is **London**.

The current Strategic Brief is a **Yellow advisory posture**. Its semantic assessment is:

`POSSIBLE / INTERVENTION_OPPORTUNITY`

This is deliberately **not** a canonical Red condition, Case, prediction, emergency declaration, or causal claim.

FRIDA keeps uncertainty visible and distinguishes:

- observed evidence;
- plausible relationships;
- missing evidence;
- bounded strategic questions;
- governed advisory state.

Historical briefs demonstrate governed temporal memory: a brief may be generated now while being restricted to evidence available at a historical cutoff. FRIDA does not give the past tomorrow's newspaper.

## Google Technology

The deployed submission uses:

- **Gemini 3.6 Flash**
- **Google GenAI SDK (`google-genai`)**
- **Vertex AI**
- **Google Cloud Run**
- **Google Cloud SQL**
- **PostgreSQL 16**
- **Python 3.12**
- **Pydantic**
- **Psycopg**

The production service is deployed on Google Cloud Run and exposed through a Google-managed `.run.app` URL.

## Authorized Public Source Fabric

The London demonstration uses an authorized public-source fabric including:

- Planning London Datahub;
- Transport for London;
- Environment Agency;
- Greater London Authority population projections;
- Metropolitan Police Service aggregate borough-level context.

News and official announcements may act as governed clues, but are never accepted as conclusions by themselves.

The current public demonstration intentionally uses a limited source fabric. Broader, higher-resolution, and more timely authorized sources may materially improve assessment precision and completeness.

## Strategic Memory

FRIDA persists durable observations, appraisals, evidence references, briefings, timestamps, uncertainty, and governance state.

Historical evaluation applies the evidence cutoff **before** cognitive interpretation. This allows the system to reuse today's reasoning architecture without leaking future evidence into the past.

## Safety and Governance

FRIDA is strategic intelligence, not person-level surveillance.

The public demonstration:

- does not identify or track individuals;
- does not perform predictive policing;
- does not convert correlation into causation;
- does not treat missing evidence as proof;
- does not allow cognitive stages to override deterministic governance;
- does not expose hidden prompts, secrets, credentials, or private reasoning.

## Architecture

FRIDA uses a layered / hexagonal architecture with deterministic authority around bounded cognitive stages.

The judge-facing architecture diagram is included with the Devpost submission and documents:

- source acquisition and authorization;
- normalization and provenance;
- observation and appraisal;
- Gemini cognitive stages;
- governed persistence;
- strategic brief generation;
- public read-only presentation.

## Production Evidence

At submission time, the production deployment is represented by:

- Cloud Run service: `frida`
- Cloud Run revision: `frida-00087-vxc`
- Cloud SQL instance: `frida-postgres`
- PostgreSQL: 16
- Functional build commit: `b5c1b65f249b424a73a87e9788848139181e81f7`
- Test status: **191 passed / 0 failed**

## Reproducibility

The judge-facing experience requires **no local installation**; the submitted public deployment is immediately usable through the hosted URL.

The repository is intended to preserve the application source, configuration contracts, tests, documentation, and deployment packaging used by the submitted build. Runtime secrets and credentials are intentionally excluded.

Production execution requires the corresponding Google Cloud project configuration, authorized-source credentials where applicable, Cloud SQL connectivity, and Vertex AI access. Those secrets are not committed to the repository.

## Scope

This submission is deliberately focused on **strategic urban intelligence**.

FRIDA's governed observation–appraisal–research–foresight engine is architecturally reusable beyond urban intelligence, but that broader platform potential is future work rather than a claim about the present submission.

## Project

Built for the **All Things Agentic Hackathon**.

**Track:** Taskmaster

**FRIDA — Autonomous Strategic Urban Intelligence**

> **She notices when the future has already started.**
