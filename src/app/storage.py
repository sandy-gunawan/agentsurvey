import json

from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient

from .auth import get_credential
from .config import settings

INDEX_BLOB = "index/hashes.json"

_memory_index: list[dict] = []


def _service() -> BlobServiceClient:
    return BlobServiceClient(settings.storage_account_url, credential=get_credential())


def _container():
    client = _service().get_container_client(settings.storage_container)
    try:
        client.create_container()
    except ResourceExistsError:
        pass
    return client


def load_index() -> list[dict]:
    if not settings.storage_enabled:
        return _memory_index
    try:
        blob = _container().get_blob_client(INDEX_BLOB)
        return json.loads(blob.download_blob().readall())
    except Exception:
        return []


def append_index(entries: list[dict]) -> bool:
    if not settings.storage_enabled:
        _memory_index.extend(entries)
        return True
    try:
        current = load_index()
        current.extend(entries)
        _container().get_blob_client(INDEX_BLOB).upload_blob(
            json.dumps(current, ensure_ascii=False), overwrite=True
        )
        return True
    except Exception:
        _memory_index.extend(entries)
        return False


def save_photo(case_id: str, filename: str, data: bytes) -> bool:
    if not settings.storage_enabled:
        return True
    try:
        _container().get_blob_client(f"{case_id}/{filename}").upload_blob(data, overwrite=True)
        return True
    except Exception:
        return False


def save_result(case_id: str, result: dict) -> bool:
    if not settings.storage_enabled:
        return True
    try:
        _container().get_blob_client(f"{case_id}/hasil.json").upload_blob(
            json.dumps(result, ensure_ascii=False, indent=2), overwrite=True
        )
        return True
    except Exception:
        return False
