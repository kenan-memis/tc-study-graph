# StudyGraph – Optional Tasks Tracking

This file tracks optional tasks for Sprint 3 and how they are implemented in this project.

---

## Easy

### Easy #1 — Ask ChatGPT to critique usability/security/prompting
- **Status:** ✅ Implemented
- **What was added:**
  - Structured critique note with findings and actions:
    - usability
    - security/resilience
    - prompting
  - Applied improvements from critique:
    - safer user-facing error messaging (no raw exception details)
    - provider API-key readiness hint in `General Settings`
- **Files:**
  - `docs/EASY_1_CRITIQUE_USABILITY_SECURITY_PROMPTS.md`
  - `studygraph/ui/app.py`

### Easy #2 — Give the agent a personality
- **Status:** ✅ Implemented
- **What was added:**
  - UI selector: `Response style` with `Friendly`, `Formal`, `Concise`
  - Selected style is stored in session input and injected into:
    - streamed study-plan prompt
    - streamed recommendation prompt
    - study material generation prompt
- **Files:**
  - `studygraph/ui/app.py`
  - `studygraph/models.py`
  - `studygraph/graph/workflow.py`
  - `studygraph/prompts/prompts.yaml`
  - `studygraph/prompts/loader.py`

### Easy #3 — Let user choose model provider
- **Status:** ✅ Implemented
- **What was added:**
  - `General Settings` sidebar section with persistent `LLM provider` selector (`OpenAI`, `Gemini`)
  - Selected provider is saved and applied to:
    - streamed study-plan generation
    - streamed recommendation generation
    - study material generation
    - quiz generation
  - Keeps fallback behavior when provider key is missing or API call fails
- **Files:**
  - `studygraph/ui/app.py`
  - `studygraph/models.py`
  - `studygraph/graph/workflow.py`

### Easy #4 — Add OpenAI settings (temperature/top-p)
- **Status:** ✅ Implemented
- **What was added:**
  - `General Settings` sidebar section with persistent:
    - `Temperature` slider (0.0–2.0)
    - `Top-p` slider (0.0–1.0)
  - Saved values are applied to:
    - streamed study-plan generation
    - streamed recommendation generation
    - study material generation
    - quiz generation
- **Files:**
  - `studygraph/ui/app.py`
  - `studygraph/models.py`
  - `studygraph/graph/workflow.py`

### Easy #5 — Interactive help/chatbot guide
- **Status:** ✅ Implemented
- **What was added:**
  - In-app interactive help expander under **Start Study Session**
  - Prompt-writing tips for course/topic/goal selection
  - One-click presets that auto-fill course/topic/study-goal fields
  - Includes custom-course (`Other…`) preset example
- **Files:**
  - `studygraph/ui/app.py`

---

## Medium

### Medium #2 — Add retry logic for agents
- **Status:** ✅ Implemented
- **What was added:**
  - Shared retry utility with exponential backoff + jitter (`max_attempts=3`)
  - Retries are applied for model/provider request calls in:
    - streamed study-plan generation
    - streamed recommendation generation
    - quiz generation
    - study material generation
  - Existing fallback behavior is preserved if retries still fail
- **Files:**
  - `studygraph/utils/retry.py`
  - `studygraph/utils/__init__.py`
  - `studygraph/ui/app.py`
  - `studygraph/graph/workflow.py`
  - `tests/test_retry.py`

---

## Hard

Not started.

