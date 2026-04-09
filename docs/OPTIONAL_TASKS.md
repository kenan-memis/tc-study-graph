# StudyGraph – Optional Tasks Tracking

This file tracks optional tasks for Sprint 3 and how they are implemented in this project.

---

## Easy

### Easy #1 — Ask ChatGPT to critique usability/security/prompting
- **Status:** Not started
- **Planned output:** `sprint_3/` note with critique + applied improvements

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
- **Status:** Not started
- **Planned approach:** provider/model selector (OpenAI/Gemini) for selected text-generation nodes

### Easy #4 — Add OpenAI settings (temperature/top-p)
- **Status:** Not started
- **Planned approach:** Streamlit sliders in a settings section, applied to generation calls

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

Not started.

---

## Hard

Not started.

