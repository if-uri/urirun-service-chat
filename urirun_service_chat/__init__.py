SERVICE_ID = "chat"


def service_manifest() -> dict:
    from .core import service_manifest as _service_manifest

    return _service_manifest()


def urirun_service() -> dict:
    from .core import urirun_service as _urirun_service

    return _urirun_service()


__all__ = ["SERVICE_ID", "service_manifest", "urirun_service"]
