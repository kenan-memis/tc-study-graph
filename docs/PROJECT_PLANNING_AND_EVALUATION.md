# StudyGraph – Project Planning and Evaluation

## 1. Project plan

### 1.1 Goal and scope

- **Project name**: StudyGraph
- **Goal**: Build a student-focused AI exam preparation assistant that helps learners plan study sessions, practice with adaptive quizzes, and improve weak topics over time.
- **Primary users**: Students preparing for exams, quizzes, and course assessments.
- **Stack**: Python, Streamlit, LangChain, LangGraph, OpenAI API.
- **Core architecture requirement**: LangGraph-first implementation (stateful agent workflow, not only a linear chain).

### 1.2 Problem definition

Students often struggle with:

1. Structuring study time effectively,
2. Practicing weak areas consistently,
3. Continuing progress across sessions.

StudyGraph solves this with a loop: **plan -> practice -> evaluate -> adapt -> remember**.

### 1.3 Scope boundaries (MVP)

**In scope**:
- Single-user study assistant in Streamlit
- Student profile + session topic/course intake
- LangGraph-based workflow
- Persistent memory of progress/weak topics
- Practical recommendations for next study session

**Out of scope**:
- Multi-user authentication
- Full LMS integration
- Heavy analytics dashboard

---

## 2. Requirement mapping to StudyGraph

| Requirement area | Sprint 3 expectation | StudyGraph approach |
|------------------|----------------------|---------------------|
| Agent purpose | Clear purpose, usefulness, users | Exam-prep coach for students |
| Core functionality | Useful features + interactions | Plan generation, quiz, evaluation, adaptive recommendations |
| UI | Intuitive front end | Streamlit sections: profile, session, quiz, results |
| Technical implementation | Tools, error handling, real-world usage | LangGraph stateful flow, validation, fallbacks |
| Documentation | Usage + decisions | README + docs planning/evaluation + optional tasks docs |

---

## 3. LangGraph architecture plan

### 3.1 Planned graph flow

1. `load_profile`
2. `build_study_plan`
3. `generate_quiz`
4. `evaluate_answers`
5. `update_memory`
6. `recommend_next_step`

### 3.2 Conditional behavior

- Low score -> remedial recommendation path
- High score -> progression recommendation path

### 3.3 State design

**Short-term state**:
- current course/topic
- plan and generated quiz
- submitted answers and score

**Long-term memory**:
- learner profile/preferences
- historical scores by topic/course
- weak-topic trends

---

## 4. Implementation phases

### Phase A – Initialization
- Project skeleton, dependencies, base docs

### Phase B – Core models + memory
- Profile/session/result schemas
- Persistent memory storage and retrieval

### Phase C – LangGraph backend
- Node implementations + routing + state handling

### Phase D – Streamlit flow
- End-to-end user experience: profile -> session -> quiz -> results

### Phase E – Reliability
- Validation, error handling, fallback behavior

### Phase F – Docs + review readiness
- Final docs, examples, limitations, improvement notes

---

## 5. Understanding core concepts (presentation)

### 5.1 Agent vs pipeline

StudyGraph is an agentic workflow where next steps depend on learner state and results, not only a fixed linear sequence.

### 5.2 ReAct and tool use

The system reasons over state, invokes tools (plan/quiz/evaluate), observes outputs, and decides the next action.

### 5.3 State and memory

- Short-term state controls one run.
- Long-term memory enables personalization over time.

### 5.4 Human-in-the-loop

User feedback (difficulty, confidence, preferences) influences recommendations and adaptation.

---

## 6. Technical implementation plan

### 6.1 Proposed project structure

```text
study-graph/
├── AGENTS.md
├── README.md
├── docs/
│   ├── PROJECT_PLANNING_AND_EVALUATION.md
│   ├── OPTIONAL_TASKS.md
│   └── EVALUATION.md
├── data/
│   └── raw/
├── studygraph/
│   ├── graph/
│   ├── tools/
│   ├── memory/
│   └── ui/
├── tests/
├── pyproject.toml
└── main.py
```

### 6.2 Error handling and edge cases

- Empty/invalid user inputs -> validation messages
- Malformed model output -> schema fallback
- Memory read/write issues -> safe defaults + recoverable behavior
- API/tool errors -> graceful user message and fallback flow

### 6.3 Security considerations

- Secrets in `.env` only
- No secret output in logs/UI
- Basic input guards and sane size limits

### 6.4 Testing strategy (required)

- Unit tests for deterministic logic:
  - scoring/evaluation helpers
  - weak-topic extraction
  - recommendation selection
- Memory tests:
  - profile save/load
  - session history append/read
- Graph smoke test:
  - one end-to-end run with mocked model/tool outputs

---

## 7. Optional tasks strategy

Target: **2 medium + 1 hard** minimum.

Planned:
1. Medium: token usage and cost display
2. Medium: memory enhancement + adaptation logic
3. Hard: agentic retrieval/external enrichment integrated in graph routing

---

## 8. Evaluation and quality plan

Evaluation will include:

- Functional checks (plan/quiz/evaluate/adapt)
- Memory checks (persistence across sessions)
- Reliability checks (errors/fallbacks)
- Automated test checks (unit + graph smoke)
- User-value checks (practical exam-prep usefulness)

---

## 9. Reflection and improvement

### 9.1 Expected limitations

- Model output quality can vary by topic
- Early sessions have limited personalization history
- Retrieval quality depends on source/tool reliability

### 9.2 Future improvements

- Richer progress analytics
- More domain-specific study packs
- Better source grounding/citations in explanations

---

## 10. Current status

- Project idea: locked (student exam-prep assistant)
- Name: locked (`StudyGraph`)
- Status: initialized; implementation in progress by phases
