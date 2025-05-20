import logging
import os
import uuid
from threading import Thread
from typing import Optional

import streamlit as st
from langchain.base_language import BaseLanguageModel
from langchain_community.cache import SQLiteCache
from langchain_community.utilities import SQLDatabase
from langchain_core.globals import set_llm_cache
from langchain_experimental.sql import SQLDatabaseChain
from langchain_openai.chat_models.base import ChatOpenAI
from streamlit.runtime.scriptrunner import (
    ScriptRunContext,
    add_script_run_ctx,
    get_script_run_ctx,
)

from .interface import run_streamlit
from .vault import DynamicDatabaseSecret, get_vault_client

# Demo only, configuration should not be hardcoded
VAULT_AGENT_OPENAI_KEY_PATH = "/vault/secrets/openai-token"
PSQL_URI = "postgresql+psycopg2://{username}:{password}@{host}/{database}"
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


def main():
    # Check that all required environment variables are set
    for env_var in ["VAULT_ADDR", "VAULT_DB_ROLE", "DB_HOST", "DB_NAME"]:
        if env_var not in os.environ.keys():
            raise ValueError(f"Please set the {env_var} environment variable.")

    # Initialize Streamlit session state
    st_init_session()

    # Instantiate the Vault client and ensure that the session ID is passed through
    # as a correlation ID. We could use other headers, but Vault tracks correlation IDs
    # in audit logs by default, so it's an easier choice for demo purposes.
    vault_client = get_vault_client(
        vault_addr=os.environ["VAULT_ADDR"],
        correlation_id=st.session_state.session_id,
    )

    # Generate short-lived dynamic credentials for the database and start the renewal
    # thread in the background.
    if st.session_state.db_creds is None:
        st_context = get_script_run_ctx()
        st.session_state.db_creds = DynamicDatabaseSecret(
            client=vault_client,
            role_name=os.environ["VAULT_DB_ROLE"],
            mount_point=os.environ.get("VAULT_DB_MOUNT", "database"),
            callback=lambda creds, thread=None: _update_db_client(
                creds, thread, st_context
            ),
        )
        st.session_state.db_creds.acquire()
        st.session_state.db_creds.start()

    # Instantiate the database client with Vault-backed dynamic credentials
    db_client = _get_db_client(st.session_state.db_creds)
    st.session_state.llm_chain = _load_few_shot_chain(llm=_get_llm(), db=db_client)

    # Run the streamlit app
    run_streamlit()


def st_init_session() -> None:
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "db_creds" not in st.session_state:
        st.session_state.db_creds = None

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


def _load_few_shot_chain(llm: BaseLanguageModel, db: SQLDatabase) -> SQLDatabaseChain:
    return SQLDatabaseChain.from_llm(
        llm, db, return_intermediate_steps=True, verbose=False, top_k=3
    )


def _get_db_client(db_creds: DynamicDatabaseSecret) -> SQLDatabase:
    if db_creds.credentials is None:
        raise ValueError("Database credentials are not available.")
    return SQLDatabase.from_uri(
        PSQL_URI.format(
            username=db_creds.credentials["username"],
            password=db_creds.credentials["password"],
            host=os.environ["DB_HOST"],
            database=os.environ["DB_NAME"],
        )
    )


def _update_db_client(
    db_creds: DynamicDatabaseSecret,
    thread: Optional[Thread] = None,
    st_context: Optional[ScriptRunContext] = None,
) -> None:
    if thread and st_context:
        add_script_run_ctx(thread, st_context)
    if "llm_chain" in st.session_state:
        st.session_state.llm_chain.database = _get_db_client(db_creds)


def _get_llm() -> BaseLanguageModel:
    if "OPENAI_API_KEY" not in os.environ or len(os.environ["OPENAI_API_KEY"]) == 0:
        if os.path.isfile(VAULT_AGENT_OPENAI_KEY_PATH):
            try:
                with open(VAULT_AGENT_OPENAI_KEY_PATH, "r") as f:
                    os.environ["OPENAI_API_KEY"] = f.read().strip()
            except Exception:
                logging.exception("Could not read OpenAI API key from file.")
                raise
        else:
            raise ValueError(
                "Please set the OPENAI_API_KEY environment variable to your OpenAI API key."
            )

    openai = ChatOpenAI(model="gpt-4", temperature=0.3, verbose=True)
    set_llm_cache(SQLiteCache("openai_cache.db"))
    return openai


if __name__ == "__main__":
    main()
