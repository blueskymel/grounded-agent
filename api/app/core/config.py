from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.key_vault import load_key_vault_secret_values


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"
    agent_framework: str = "classic"

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

    # Azure Key Vault / Managed Identity
    key_vault_url: str | None = None
    managed_identity_client_id: str | None = None
    keyvault_azure_openai_api_key_secret_name: str | None = None
    keyvault_azure_search_api_key_secret_name: str | None = None
    keyvault_applicationinsights_connection_string_secret_name: str | None = None

    # Azure Monitor / Application Insights
    applicationinsights_connection_string: str | None = None


def apply_key_vault_overrides(settings: Settings) -> Settings:
    if not settings.key_vault_url:
        return settings

    secret_name_map: dict[str, str] = {}
    if not settings.azure_openai_api_key and settings.keyvault_azure_openai_api_key_secret_name:
        secret_name_map["azure_openai_api_key"] = settings.keyvault_azure_openai_api_key_secret_name
    if not settings.azure_search_api_key and settings.keyvault_azure_search_api_key_secret_name:
        secret_name_map["azure_search_api_key"] = settings.keyvault_azure_search_api_key_secret_name
    if (
        not settings.applicationinsights_connection_string
        and settings.keyvault_applicationinsights_connection_string_secret_name
    ):
        secret_name_map[
            "applicationinsights_connection_string"
        ] = settings.keyvault_applicationinsights_connection_string_secret_name

    if not secret_name_map:
        return settings

    resolved = load_key_vault_secret_values(
        key_vault_url=settings.key_vault_url,
        managed_identity_client_id=settings.managed_identity_client_id,
        secret_name_map=secret_name_map,
    )
    for field_name, value in resolved.items():
        setattr(settings, field_name, value)

    return settings


def build_settings() -> Settings:
    return apply_key_vault_overrides(Settings())


settings = build_settings()