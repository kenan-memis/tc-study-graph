from __future__ import annotations

import streamlit as st


def main() -> None:
    st.set_page_config(page_title="StudyGraph", page_icon="📘", layout="wide")
    st.title("StudyGraph")
    st.caption("LangGraph-based student exam prep assistant")
    st.info("Project initialized. Next step: add profile, session flow, and LangGraph agent.")


if __name__ == "__main__":
    main()

