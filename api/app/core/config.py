from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"

    # Feature flag: faiss | azure_search
    retrieval_backend: str = "faiss"

    # Azure OpenAI
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str | None = None
    azure_openai_embeddings_deployment: str | None = None

    # Azure AI Search
    azure_search_endpoint: str | None = None
    azure_search_api_key: str | None = None
    azure_search_index_name: str = "groundedagent-chunks"

    # Azure Monitor / Application Insights
    applicationinsights_connection_string: str | None = None


settings = Settings()