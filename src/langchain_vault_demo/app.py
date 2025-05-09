import os

from langchain.base_language import BaseLanguageModel
from langchain_community.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain_openai.chat_models.base import ChatOpenAI

from .interface import StAppParams, run_streamlit


def main():
    chain = _load_few_shot_chain(llm=_get_llm(), db=_get_db())
    run_streamlit(StAppParams(prompt_chain=chain))


def _load_few_shot_chain(llm: BaseLanguageModel, db: SQLDatabase) -> SQLDatabaseChain:
    return SQLDatabaseChain.from_llm(
        llm, db, return_intermediate_steps=True, verbose=False, top_k=3
    )


def _get_llm() -> BaseLanguageModel:
    if "OPENAI_API_KEY" not in os.environ or len(os.environ["OPENAI_API_KEY"]) == 0:
        raise ValueError(
            "Please set the OPENAI_API_KEY environment variable to your OpenAI API key."
        )
    return ChatOpenAI(model_name="gpt-4", temperature=0.3, verbose=True)


def _get_db() -> SQLDatabase:
    for env_var in ["DB_USER", "DB_PASSWORD", "DB_HOST", "DB_NAME"]:
        if env_var not in os.environ or len(os.environ[env_var]) == 0:
            raise ValueError(
                f"Please set the {env_var} environment variable to your database credentials."
            )

    return SQLDatabase.from_uri(
        f"postgresql+psycopg2://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}@{os.environ['DB_HOST']}/{os.environ['DB_NAME']}"
    )


if __name__ == "__main__":
    main()
