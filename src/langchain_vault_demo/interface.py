# Copyright (c) HashiCorp, Inc.
# SPDX-License-Identifier: MIT

import ast
import json
import logging
import time

import pandas as pd
import streamlit as st
from langchain_openai.chat_models.base import ChatOpenAI
from streamlit.delta_generator import DeltaGenerator

from . import MSG_NO_ANSWER, PROMPT


def run_streamlit() -> None:
    st.set_page_config(
        page_title="LangChain Vault Demo",
        page_icon=":guardsman:",
        layout="wide",
    )

    chat_tab, details_tab, secrets_tab = st.tabs(["Chat", "Details", "Secrets"])
    _set_chat_tab(chat_tab)
    _set_details_tab(details_tab)
    _set_secrets_tab(secrets_tab)


def _clear_session() -> None:
    for key in st.session_state.keys():
        del st.session_state[key]


def _clear_text() -> None:
    st.session_state["query"] = st.session_state["query_text"]
    st.session_state["query_text"] = ""
    st.session_state["query_error"] = ""


def _set_chat_tab(tab: DeltaGenerator) -> None:
    with tab:
        col1, col2 = st.columns([6, 1], gap="medium")

        with col2:
            with st.container():
                st.button("Clear", on_click=_clear_session)
        with col1:
            with st.container():
                st.markdown("## The Museum of Modern Art (MoMA) Collection")
                st.markdown(
                    "Ask a question about the collection using natural language."
                )

                st.markdown(" ")
                with st.expander("Sample questions"):
                    st.markdown(
                        """
                        - How many artists are there in the collection?
                        - How many pieces of artwork are there?
                        - How many artists are there whose nationality is Italian?
                        - How many artworks are by the artist Claude Monet?
                        - How many artworks are classified as paintings?
                        - How many artworks were created by Spanish artists?
                        - How many artist names start with the letter 'M'?
                        """
                    )

                st.markdown(" ")
                with st.container():
                    input_text = st.text_input(
                        "Ask a question:",
                        "",
                        key="query_text",
                        placeholder="Type your question here...",
                        on_change=_clear_text,
                    )
                    logging.info("Question: %s", input_text)

                    user_input = st.session_state["query"]
                    if user_input:
                        with st.spinner(text="In progress..."):
                            st.session_state.past.append(user_input)
                            try:
                                res = st.session_state.llm_chain.invoke(
                                    {"query": PROMPT.format(question=user_input)}
                                )
                                st.session_state.generated.append(res)
                                logging.info("Query: %s", st.session_state["query"])
                                logging.info(
                                    "Result: %s", st.session_state["generated"]
                                )
                            except Exception as exc:
                                st.session_state.generated.append(MSG_NO_ANSWER)
                                logging.error("Error: %s", exc)
                                st.session_state["query_error"] = exc

                    if st.session_state["generated"]:
                        with col1:
                            for i in range(
                                len(st.session_state["generated"]) - 1, -1, -1
                            ):
                                if i >= 0:
                                    with st.chat_message("assistant"):
                                        if (
                                            st.session_state["generated"][i]
                                            == MSG_NO_ANSWER
                                        ):
                                            st.write(MSG_NO_ANSWER)
                                        else:
                                            st.write(
                                                st.session_state["generated"][i][
                                                    "result"
                                                ]
                                            )
                                    with st.chat_message("user"):
                                        st.write(st.session_state["past"][i])
                                else:
                                    with st.chat_message("assistant"):
                                        st.write(MSG_NO_ANSWER)
                                    with st.chat_message("user"):
                                        st.write(st.session_state["past"][i])


def _set_details_tab(tab: DeltaGenerator) -> None:
    with tab:
        with st.container():
            st.markdown("### LLM Details")
            st.markdown(
                f"Foundational Model: {_get_model_md(st.session_state.llm_chain)}"
            )

            pos = len(st.session_state["generated"]) - 1
            if pos >= 0 and st.session_state["generated"][pos] != MSG_NO_ANSWER:
                st.markdown("Query:")
                st.code(st.session_state["generated"][pos]["query"], language="text")

                st.markdown("SQL Query:")
                st.code(
                    st.session_state["generated"][pos]["intermediate_steps"][1],
                    language="sql",
                )

                st.markdown("Results:")
                st.code(
                    st.session_state["generated"][pos]["intermediate_steps"][3],
                    language="python",
                )

                st.markdown("Answer:")
                st.code(st.session_state["generated"][pos]["result"], language="text")

                data = ast.literal_eval(
                    st.session_state["generated"][pos]["intermediate_steps"][3]
                )
                if len(data) > 0 and len(data[0]) > 1:
                    st.markdown("DataFrame:")
                    st.dataframe(pd.DataFrame(data), use_container_width=False)

            st.markdown("Query Error:")
            st.code(st.session_state["query_error"], language="text")


def _set_secrets_tab(tab: DeltaGenerator) -> None:
    with tab:
        with st.container():
            st.markdown("### Secrets")

            # Session ID
            st.markdown("#### Session ID")
            st.code(st.session_state.session_id, language="text")

            # Database credentials
            st.markdown("#### PostgreSQL credentials")
            if st.session_state.db_creds is None:
                st.markdown(
                    "No database credentials found. Please check your Vault configuration."
                )
            else:
                creds_container = st.empty()
                while st.session_state.db_creds.is_running:
                    creds_container.empty()
                    with creds_container:
                        if st.session_state.db_creds.credentials is None:
                            st.markdown(
                                "No database credentials found. Please check your Vault configuration."
                            )
                        else:
                            st.code(
                                language="json",
                                body=json.dumps(
                                    {
                                        "lease_id": st.session_state.db_creds.lease_id,
                                        "lease_duration": st.session_state.db_creds.lease_duration,
                                        "lease_expiration": st.session_state.db_creds.lease_expiration,
                                        "username": st.session_state.db_creds.credentials[
                                            "username"
                                        ],
                                        "password": _redact_string(
                                            st.session_state.db_creds.credentials[
                                                "password"
                                            ]
                                        ),
                                    },
                                    indent=4,
                                ),
                            )
                    time.sleep(st.session_state.db_creds.next_renew_interval())


def _get_model_md(p) -> str:
    if st.session_state.llm_chain is None:
        return "None"
    if isinstance(st.session_state.llm_chain.llm_chain.llm, ChatOpenAI):
        return f"`openai {st.session_state.llm_chain.llm_chain.llm.model_name}`"
    return "Unknown"


def _redact_string(str: str, show_chars: int = 5, redact_char: str = "*") -> str:
    """
    Redact all but the first and last `show_chars` characters of a string.
    """
    if (
        len(str) <= 2 * show_chars
    ):  # If the string is too short to redact, return it as is
        return str

    return str[:show_chars] + redact_char * (len(str) - show_chars)
