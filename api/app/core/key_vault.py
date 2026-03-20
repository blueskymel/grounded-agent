from collections.abc import Mapping


def load_key_vault_secret_values(
    *,
    key_vault_url: str,
    managed_identity_client_id: str | None,
    secret_name_map: Mapping[str, str],
) -> dict[str, str]:
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError as exc:
        raise RuntimeError(
            "Key Vault support requires azure-identity and azure-keyvault-secrets to be installed."
        ) from exc

    credential = DefaultAzureCredential(managed_identity_client_id=managed_identity_client_id)
    client = SecretClient(vault_url=key_vault_url, credential=credential)

    resolved: dict[str, str] = {}
    for setting_name, secret_name in secret_name_map.items():
        resolved[setting_name] = client.get_secret(secret_name).value

    return resolved