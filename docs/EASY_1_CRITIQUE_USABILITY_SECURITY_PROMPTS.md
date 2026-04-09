# Easy #1 Critique: Usability, Security, Prompting

This note documents a structured critique of StudyGraph and the follow-up actions taken.

## Scope reviewed

- Profile manager flow (create/edit/select)
- Study session flow (course/topic/goal/style -> plan/material -> quiz -> evaluation)
- General settings (provider/model settings)
- Failure/fallback behavior for model calls
- Prompt structure and maintainability

## Findings and actions

### 1) Usability

**Finding U1 (High):** Profile create/edit actions were mixed in one form state, which could lead to accidental updates or confusing validation messages.  
**Action taken:** Added explicit form modes:
- `Create new profile`
- `Edit selected profile`

Each mode now shows only the relevant action button, with proper field behavior.

**Finding U2 (Medium):** Important controls lacked clear "not selected" states in some select boxes.  
**Action taken:** Added consistent `Select...` placeholders and validation in profile and study-session fields before running actions.

**Finding U3 (Medium):** AI configuration was mixed into study content form and felt out of place.  
**Action taken:** Moved provider/model controls to a dedicated sidebar `General Settings` section, with persistence across reruns.

### 2) Security / resilience

**Finding S1 (Medium):** Raw exception text was shown to users in UI errors, which can expose internal implementation details.  
**Action taken:** Replaced raw exception output with safe, user-facing messages (e.g. `Failed to generate quiz. Please try again.`).

**Finding S2 (Low):** Provider failures were not clearly signaled before user action.  
**Action taken:** Added provider API-key readiness indicator in `General Settings`; if missing, UI warns that fallback outputs will be used.

### 3) Prompt engineering

**Finding P1 (Medium):** Prompt management is centralized and good, but critique confirms consistency needs to be preserved as features expand.  
**Action taken:** Kept YAML-based prompt source as single truth and continued using render-based prompt injection for generation and streaming calls.

**Finding P2 (Low):** Cross-course recommendation leakage was a risk.  
**Already addressed before this note:** Course-scoped weak-topic memory and prompt instructions prevent cross-subject contamination in study plans.

## Net result

- Cleaner and safer UX for profile management
- Clearer configuration ownership (general vs session-specific inputs)
- Better user-facing resilience during model/provider issues
- Prompt architecture remains maintainable and reviewer-friendly

## Deferred improvements (recommended later)

- Add tests for:
  - profile duplicate prevention at UI/business-flow boundary
  - model setting propagation (temperature/top-p)
  - provider fallback paths and key-availability behavior
- Add optional "debug mode" switch for development-only detailed errors
- Expand language options and related prompt localization
