# FRIDA — Judge Quick Start + User Guide + Roadmap

## 1. Judge Quick Start

**Public application:**  
https://frida-zz37olzlja-pv.a.run.app

**Credentials:** None. The demonstration is public and read-only.

### Recommended 3–5 minute judge path

#### 1. FRIDA in Action
Open the home page.

What to notice:

- the active assignment is London;
- FRIDA displays attributable observation activity;
- the activity stream is evidence of execution, not by itself a strategic finding;
- the current briefing posture is governed rather than manually selected.

#### 2. Briefings
Open **Briefings**.

What to notice:

- current and historical briefs are durable artifacts;
- historical briefs carry evidence-time boundaries;
- the system separates generation time from evidence time.

#### 3. Current Strategic Brief
Open the current brief.

Current deterministic posture:

**YELLOW**

Current semantic assessment:

**POSSIBLE / INTERVENTION_OPPORTUNITY**

This is an advisory state. It is **not**:

- a canonical Red condition;
- a Case;
- an emergency declaration;
- a prediction;
- a causal conclusion.

Read the strategic question, supporting evidence, missing evidence, and uncertainty together. FRIDA is designed to preserve those distinctions.

#### 4. FRIDA Explained
Open **FRIDA Explained**.

The architecture follows one core principle:

> **Determinism establishes what is true and what is allowed. Cognition explores what it might mean.**

The workflow is:

**Observe → Appraise → Investigate → Look Ahead → Govern → Brief**

Deterministic controls establish authorization, provenance, normalization, eligibility, evidence-time boundaries, persisted state, and claim limits.

Bounded Gemini stages explore possible meaning without obtaining authority to redefine the facts.

#### 5. Under the Hood
Open **Under the Hood**.

This view exposes real persisted execution records such as timestamped observations and appraisal activity.

It exists to demonstrate that FRIDA is running a governed process rather than presenting a static mockup.

No hidden prompts, credentials, secrets, or private chain-of-thought are exposed.

#### 6. Raw Governed Appraisal Record
Open the **Raw Governed Appraisal Record** associated with the current appraisal.

What to inspect:

- structured facts;
- evidence identifiers;
- timestamps;
- provenance;
- uncertainty;
- advisory state;
- persisted read-only data.

This is the governed record beneath the executive presentation.

#### 7. Historical Brief
Open any historical brief.

The important property is **temporal integrity**.

A historical brief may be generated today, but its evidence bundle is restricted to evidence available at its historical cutoff. The cutoff is applied before cognitive interpretation.

In plain language:

> FRIDA does not give the past tomorrow's newspaper.

---

# 2. User Guide

## Home — FRIDA in Action

The home page presents the current city assignment, strategic posture, recent observation activity, and access to the current briefing.

Observation activity should be interpreted as **what FRIDA has seen and processed**, not as a declaration that every event is strategically important.

FRIDA deliberately separates activity from strategic escalation.

## Briefings

The Briefings view contains durable strategic artifacts.

Use it to:

- open the current strategic brief;
- inspect historical briefs;
- compare evidence-time periods;
- review the posture FRIDA actually produced.

Status colors are governance states, not general statements about whether an entire city is safe or unsafe.

### Green
Observed and evaluated; no material strategic change detected in the monitored evidence for that period.

### Yellow
Attention is warranted because the evidence is emerging, incomplete, strategically interesting, or advisory.

### Red
A governed leading condition merits timely decision-maker attention.

Red does **not** mean certainty, prediction, or emergency unless the evidence and governance contract specifically support such a conclusion.

The current London demonstration is Yellow.

## Strategic Brief

A Strategic Brief converts governed evidence into an executive artifact.

Read the sections together:

- bounded strategic question;
- observed evidence;
- possible relationship or interpretation;
- missing evidence;
- uncertainty;
- posture / advisory state.

A plausible relationship is not presented as causality.

A missing source is not silently filled with model knowledge.

## Advisory

The Advisory view exposes the current first-appraisal interpretation in more detail.

It is intentionally bounded and explicitly separates:

- what was observed;
- what may be strategically relevant;
- what remains unknown;
- what evidence would be useful next.

## FRIDA Explained

This view explains the runtime contract.

FRIDA is one autonomous workflow with specialized cognitive stages and deterministic authority.

It is **not** marketed as a runtime fleet of independent agents.

The cognitive stages cannot:

- authorize an unapproved source;
- rewrite provenance;
- move an evidence cutoff;
- silently convert uncertainty into fact;
- create authority they were not given.

## Under the Hood

Under the Hood is the execution-transparency surface.

It exposes persisted process evidence without exposing secrets or private reasoning.

Use it to verify that observation and appraisal events occurred and were recorded.

## Raw Governed Appraisal Record

This is the closest judge-facing view to the persisted governed object.

It is useful for validating:

- data lineage;
- evidence references;
- timestamps;
- structured status;
- uncertainty;
- machine-readable appraisal state.

## Historical Memory

Historical briefs are designed to answer:

**What would FRIDA have been able to notice using only the evidence available by that date?**

The evidence cutoff is applied before the cognitive stage. This avoids hindsight leakage while allowing the same governed reasoning architecture to evaluate multiple historical windows.

---

# 3. What the Demonstration Does Not Claim

FRIDA does not claim to know everything occurring in London.

The public source fabric is intentionally limited.

The demonstration does not:

- watch or identify individuals;
- perform predictive policing;
- infer causality merely from temporal proximity;
- force unrelated facts into one narrative;
- treat a model response as evidence;
- portray every anomaly as a strategic threat.

The system is designed to be strategically curious **under governance**.

---

# 4. Google Cloud and AI Runtime

The submitted production build uses:

- **Gemini 3.6 Flash**
- **Google GenAI SDK (`google-genai`)**
- **Vertex AI**
- **Google Cloud Run**
- **Google Cloud SQL**
- **PostgreSQL 16**
- **Python 3.12**

Production deployment evidence at submission:

- Cloud Run service: `frida`
- Cloud Run revision: `frida-00087-vxc`
- Cloud SQL instance: `frida-postgres`
- functional build commit: `b5c1b65f249b424a73a87e9788848139181e81f7`
- tests: **191 passed / 0 failed**

The Google GenAI SDK is the production model integration path.

Google ADK is **not** claimed as the deployed runtime framework.

---

# 5. Source Governance

The current London source fabric includes authorized public information from:

- Planning London Datahub;
- Transport for London;
- Environment Agency;
- Greater London Authority;
- Metropolitan Police Service aggregate borough-level context.

News and official announcements can be clues, but are never accepted as conclusions merely because they were published.

The public demo intentionally carries the limitation:

> This brief reflects the authorized public sources currently available to FRIDA. Broader, higher-resolution and more timely authorized sources may materially improve the precision and completeness of the assessment.

---

# 6. Roadmap

## Near Term

### Broader authorized source coverage
Expand the source fabric while preserving source-level authorization, provenance, normalization, and temporal controls.

### Higher-resolution temporal memory
Increase the number and diversity of governed historical windows and improve side-by-side temporal comparison.

### Stronger executive explanation
Improve the visual distinction among:

- observed fact;
- interpretation;
- missing evidence;
- uncertainty;
- advisory posture.

### Semantic status visualization
Display Green / Yellow / Red states more explicitly and consistently across briefing lists and detail views while preserving their precise governance meaning.

### Additional city assignments
Apply the same governed engine to additional cities with city-specific source authorization and evidence contracts.

## Medium Term

### Governed discovery
Allow FRIDA to identify candidate public sources while keeping human or deterministic authorization separate from discovery.

### Richer cross-domain relationships
Evaluate planning, mobility, housing, environment, resilience, and other urban domains together without forcing unrelated facts into a narrative.

### Decision-support scenarios
Move from noticing and briefing toward bounded strategic scenario exploration, with explicit assumptions and no silent conversion of scenarios into predictions.

### Operational observability
Expand execution telemetry, health diagnostics, source freshness reporting, and judge/operator visibility.

## Longer Term

FRIDA's governed observation–appraisal–research–foresight engine is architecturally reusable beyond urban intelligence.

That potential is intentionally outside the claims of this hackathon submission.

The submitted product remains focused on one question:

> **Can an autonomous system notice strategic urban change before a decision-maker thinks to ask about it — while remaining governable, attributable, and honest about uncertainty?**

FRIDA's answer is a working beginning.

**Nobody asked her. She noticed.**
