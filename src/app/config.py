import os


class Settings:
    """Seluruh akses memakai Managed Identity, jadi tidak ada kunci di sini."""

    def __init__(self) -> None:
        self.ai_endpoint = os.getenv("AZURE_AI_ENDPOINT", "")
        self.ai_deployment = os.getenv("AZURE_AI_DEPLOYMENT", "")
        self.ai_api_version = os.getenv("AZURE_AI_API_VERSION", "2024-12-01-preview")

        self.maps_client_id = os.getenv("AZURE_MAPS_CLIENT_ID", "")
        self.maps_base_url = os.getenv("AZURE_MAPS_BASE_URL", "https://atlas.microsoft.com")

        self.storage_account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL", "")
        self.storage_container = os.getenv("AZURE_STORAGE_CONTAINER", "bukti")

        # Kosong saat berjalan lokal; terisi oleh Container Apps.
        self.managed_identity_client_id = os.getenv("AZURE_CLIENT_ID", "")

        self.address_match_radius_m = int(os.getenv("ADDRESS_MATCH_RADIUS_M", "150"))
        self.gang_snap_threshold_m = int(os.getenv("GANG_SNAP_THRESHOLD_M", "30"))
        self.duplicate_threshold = int(os.getenv("DUPLICATE_THRESHOLD", "5"))

    @property
    def maps_enabled(self) -> bool:
        return bool(self.maps_client_id)

    @property
    def storage_enabled(self) -> bool:
        return bool(self.storage_account_url)


settings = Settings()
