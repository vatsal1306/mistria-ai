# Rebel Archetype v1 Runtime & Safety Boundaries

This document clarifies the implementation boundaries for the Rebel archetype voice package. It explicitly outlines what is and is not covered in this wave of implementation to ensure prompt guidance is not mistaken for comprehensive legal or clinical compliance.

> **Disclaimer**: This documentation does not constitute legal or clinical advice. This implementation is an internal foundational feature set and does not represent a completed compliance infrastructure.

## Architecture: Layer A vs Layer B

Mistria's approach to safety divides responsibilities:
- **Layer A (Platform Level)**: Strict, un-styled platform moderation, legal disclosures, age verification, and crisis flows. This operates independent of the AI persona.
- **Layer B (Character Level)**: The AI's in-character personality, voice, and conversational boundaries. This dictates how the companion handles normal rejections, boundaries, and tone within the bounds of safety.

## What is Included in this Implementation Wave

This wave focuses primarily on Layer B (Character Level) features:
- **Deterministic Scoring**: Mechanisms to calculate and determine the user's archetype (Slow Burn).
- **Stored Archetype Result**: Persistence of the user's primary archetype result.
- **Rebel Voice Prompt**: Dedicated prompt overlay dictating Rebel's core energy, behavior stages (L1/L2/L3), and craft principles.
- **Rebel Character-Level Refusal Guidance**: In-character prompt instructions to handle boundary cases, such as refusing hard sexual requests briefly, rejecting emotional manipulation, and reducing intimacy in the face of abuse.

## What is NOT Included (Deferred Compliance)

The current implementation does **not** include the necessary Layer A (Platform Level) safety features. The following are explicitly deferred:
- Legal compliance completion (e.g., California SB 243 requirements)
- Age verification gates
- Known-minor conversational flows and blocking
- Automated crisis/self-harm classification
- Region-aware crisis resource routing
- Publicly accessible crisis protocol pages
- In-app abuse reporting infrastructure

## Required Future Reviews

Before any production release of the Rebel archetype, the following reviews must occur:
- **Legal Review**: To verify jurisdiction-specific compliance, explicit disclosures, and liabilities.
- **Clinical Review**: To ensure mental health boundary handling, dependency prevention, and crisis protocols meet therapeutic safety standards.
- **Jurisdiction Review**: Ongoing checks for regional compliance updates.

## Critical Runtime Warnings & Internal Naming

- **Identity Disclosure**: The Rebel runtime prompt must **never** claim the AI is human. It must never contradict platform-level AI disclosures.
- **Internal Naming**: The name "Rebel" (and all other archetype names like "Intense Heat") is strictly an internal identifier. It should not be surfaced or displayed directly to the end user in the UI.
