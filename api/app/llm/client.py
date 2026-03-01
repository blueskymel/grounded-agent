import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()


def get_aoai_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    )


def get_chat_deployment() -> str:
    return os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"]