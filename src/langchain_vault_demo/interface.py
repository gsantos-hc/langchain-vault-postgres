import ast
from dataclasses import dataclass
from logging import getLogger

import pandas as pd
import streamlit as st
from langchain_experimental.sql import SQLDatabaseChain
from langchain_openai.chat_models.base import ChatOpenAI
from streamlit.delta_generator import DeltaGenerator

from . import MSG_NO_ANSWER, PROMPT

logger = getLogger(__name__)


@dataclass
class StAppParams:
    prompt_chain: SQLDatabaseChain


def run_streamlit(params: StAppParams) -> None:
    _init_session()
    st.set_page_config(
        page_title="LangChain Vault Demo",
        page_icon=":guardsman:",
        layout="wide",
    )

    chat_tab, details_tab, secrets_tab = st.tabs(["Chat", "Details", "Secrets"])
    _set_chat_tab(chat_tab, params)
    _set_details_tab(details_tab, params)
    _set_secrets_tab(secrets_tab)


def _init_session() -> None:
    if "visibility" not in st.session_state:
        st.session_state.visibility = "visible"
        st.session_state.disabled = False
    if "generated" not in st.session_state:
        st.session_state["generated"] = []
    if "past" not in st.session_state:
        st.session_state["past"] = []
    if "query" not in st.session_state:
        st.session_state["query"] = ""
    if "query_text" not in st.session_state:
        st.session_state["query_text"] = ""
    if "query_error" not in st.session_state:
        st.session_state["query_error"] = ""


def _clear_session() -> None:
    for key in st.session_state.keys():
        del st.session_state[key]


def _clear_text() -> None:
    st.session_state["query"] = st.session_state["query_text"]
    st.session_state["query_text"] = ""
    st.session_state["query_error"] = ""


def _set_chat_tab(tab: DeltaGenerator, params: StAppParams) -> None:
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
                    logger.info("Question: %s", input_text)

                    user_input = st.session_state["query"]
                    if user_input:
                        with st.spinner(text="In progress..."):
                            st.session_state.past.append(user_input)
                            try:
                                res = params.prompt_chain.invoke(
                                    {"query": PROMPT.format(question=user_input)}
                                )
                                st.session_state.generated.append(res)
                                logger.info("Query: %s", st.session_state["query"])
                                logger.info("Result: %s", st.session_state["generated"])
                            except Exception as exc:
                                st.session_state.generated.append(MSG_NO_ANSWER)
                                logger.error("Error: %s", exc)
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


def _set_details_tab(tab: DeltaGenerator, params: StAppParams) -> None:
    with tab:
        with st.container():
            st.markdown("### LLM Details")
            st.markdown(f"Foundational Model: {_get_model_md(params)}")

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


def _set_secrets_tab(tab: DeltaGenerator) -> None: ...


def _get_model_md(params: StAppParams) -> str:
    if params.prompt_chain.llm_chain is None:
        return "None"
    if isinstance(params.prompt_chain.llm_chain.llm, ChatOpenAI):
        return f"**OpenAI `{params.prompt_chain.llm_chain.llm.model_name}`**"
    return "Unknown"
