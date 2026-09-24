from functools import lru_cache

from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from .config import settings

COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"
MAPS_SCOPE = "https://atlas.microsoft.com/.default"


@lru_cache(maxsize=1)
def get_credential() -> DefaultAzureCredential:
    if settings.managed_identity_client_id:
        return DefaultAzureCredential(
            managed_identity_client_id=settings.managed_identity_client_id
        )
    return DefaultAzureCredential()


@lru_cache(maxsize=1)
def get_cognitive_token_provider():
    return get_bearer_token_provider(get_credential(), COGNITIVE_SCOPE)


def get_maps_token() -> str:
    return get_credential().get_token(MAPS_SCOPE).token
