"""Input length limits — keep aligned with ``studygraph.models`` ``Field(max_length=...)``."""

# StudentProfile
MAX_LEARNER_NAME = 80
MAX_PREFERRED_LANGUAGE = 40

# StudySessionInput / SessionRecord / FeedbackRecord (course, topic)
MAX_COURSE = 80
MAX_TOPIC = 800

# FeedbackRecord.note
MAX_FEEDBACK_NOTE = 300
