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

### Medium #1 — Calculate and display token usage and costs
- **Status:** ✅ Implemented
- **What was added:**
  - Session-level token/cost tracking with per-call breakdown table
  - Estimated costs for supported model/provider pairs
  - UI section: `Token & Cost Summary (Current Session)`
  - Graceful handling when provider usage metadata is unavailable
- **Files:**
  - `studygraph/usage.py`
  - `studygraph/ui/app.py`
  - `studygraph/graph/workflow.py`
  - `tests/test_usage.py`

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

### Medium #3 — Implement long-term or short-term memory in LangChain/LangGraph
- **Status:** ✅ Covered by existing architecture
- **Why this counts:**
  - Long-term memory is implemented and persisted per profile in JSON storage
  - Session history is used to personalize study plans and recommendations (including course-scoped weak-topic retrieval)
  - LangGraph state is used across prepare/quiz/evaluate flows
- **Note:** Memory is implemented with a custom store (`MemoryStore`) rather than framework-native memory helpers, but functional requirements are met.
- **Files:**
  - `studygraph/memory/store.py`
  - `studygraph/graph/workflow.py`
  - `tests/test_memory_store.py`
  - `tests/test_memory_analytics.py`

### Medium #4 — Implement one more function tool that calls an external API
- **Status:** ✅ Implemented
- **What was added:**
  - New external knowledge tool using Wikipedia API:
    - `fetch_wikipedia_summary(topic)`
  - Study material generation now enriches prompt context with external facts when available
  - UI displays source attribution when external context is used
  - Failure-safe behavior: if API is unavailable, app continues with normal generation flow
- **Files:**
  - `studygraph/tools/external_knowledge.py`
  - `studygraph/tools/__init__.py`
  - `studygraph/graph/workflow.py`
  - `studygraph/ui/app.py`
  - `studygraph/prompts/prompts.yaml`
  - `studygraph/prompts/loader.py`
  - `tests/test_external_knowledge_tool.py`

### Medium #6 — Implement a caching mechanism for frequent responses
- **Status:** ✅ Implemented
- **What was added:**
  - Persistent file-based response cache for repeated generation requests
  - Cache keys include topic/course/provider/settings/profile-level context
  - Cache applied to:
    - study material generation
    - quiz generation
  - Cache hits skip provider calls and return stored outputs immediately
- **Files:**
  - `studygraph/cache.py`
  - `studygraph/graph/workflow.py`
  - `tests/test_cache.py`

### Medium #7 — Implement a feedback loop to improve responses
- **Status:** ✅ Implemented
- **What was added:**
  - Material-level feedback capture in UI:
    - thumbs up/down signal
    - reason tags
    - optional note
  - Feedback persistence per profile
  - Course-level feedback preference summarization
  - Prompt adaptation using summarized feedback preferences in:
    - streamed study plan generation
    - study material generation
  - UI transparency line: `Applied feedback preferences: ...` when available
- **Files:**
  - `studygraph/models.py`
  - `studygraph/memory/store.py`
  - `studygraph/ui/app.py`
  - `studygraph/prompts/prompts.yaml`
  - `studygraph/prompts/loader.py`
  - `studygraph/graph/workflow.py`
  - `tests/test_memory_analytics.py`

### Medium #9 — Implement multi-model support (OpenAI, Anthropic, etc.)
- **Status:** ✅ Covered (OpenAI + Gemini)
- **What is implemented:**
  - User-selectable provider (`OpenAI` / `Gemini`) in `General Settings`
  - Same app workflow supports both providers for:
    - streamed study plan
    - streamed recommendation
    - study material generation
    - quiz generation
- **Note:** Implementation currently supports 2 providers (not 3+).
- **Files:**
  - `studygraph/ui/app.py`
  - `studygraph/models.py`
  - `studygraph/graph/workflow.py`

---

## Hard

Not started.

