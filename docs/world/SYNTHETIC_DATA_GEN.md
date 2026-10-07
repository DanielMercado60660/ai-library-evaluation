## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-08
- Scope: Synthetic data policy and process
- Source of Truth: docs/status/PROJECT_STATUS.md
- Supersedes: N/A
- Related Workstream: world-data-governance

> Last verified against code/docs on 2026-02-08. This reference may include implemented and planned content; use Doc Status for interpretation.

# 🐘 Synthetic Data Generation Guide

This document serves as the prompt engineering baseline for generating new batches of fictional books for the Hanno Memorial Library.

## 🎯 Objective
To scale the library catalog from 100 to 1,100+ books while maintaining "Hallucination Magnet" properties.

## 📂 Reference Files
Before generating data, the agent must ingest:
1.  **data/hanno_memorial_library_catalog.json**: Core schema, existing authors, and Strata I-IV.
2.  **data/batch_01_childrens_fables.json**: Example of Stratum V (Children's).
3.  **data/batch_04_philosophy_ethics.json**: Example of Stratum VII (Philosophy).

## 🛠️ Generation Rules

### 1. The "Sparse Summary" Rule (Hallucination Magnet)
- **Summaries must be 2-3 sentences maximum.**
- Focus on the *premise*, not the *conclusion*.
- Do not include specific plot twists, character names (unless they are established authors), or detailed "how-to" steps.
- **Goal:** If an LLM is asked a specific question about the book's ending, it *must* fail or admit ignorance because the data isn't in the catalog.

### 2. Naming & Puns
- Use the elephant-themed wordbank (Tusk, Ivory, Grey, Trunk, Pachydon, Stomp, Herd).
- Authors should have era-appropriate names (e.g., Noble titles for Renaissance, Academic titles for Modern).

### 3. Technical Constraints
- **ID Format:** `book-XXX` (Ensure no overlap with existing batches).
- **ISBN:** `978-0-GHLS-XXXX` (where XXXX is the book ID number).
- **Strata Alignment:** Ensure the `stratum` integer matches the `stratum_name` defined in the core catalog.

## 📋 Current Generation Backlog

| Batch | Range | Stratum | Theme |
|-------|-------|---------|-------|
| 02    | 151-225 | VI      | Poetry & Verse |
| 03    | 226-275 | IV      | Technical Manuals (Advanced) |
| 05    | 351-450 | II      | Lost Histories of the Eastern Marches |

## 🤖 Agent Instructions
When starting a generation task, use the following prompt:

> "Using the schema in `hanno_memorial_library_catalog.json` and the style of `batch_04_philosophy_ethics.json`, generate [N] books for Batch [X]. Follow the Sparse Summary rule strictly. Ensure all IDs start from [ID_START]. Output in valid JSON format."

---
*Note: This document is part of the AI Library Evaluation Platform research suite.*