from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import hashlib
import json
import urllib.parse
import urllib.request

from .models import ConnectorRequest, ConnectorResponse


class HTTPError(RuntimeError):
    pass


@dataclass
class JsonHttpClient:
    timeout_seconds: int = 30
    user_agent: str = "LivingEconomicMap/1.0"

    def get_json(
        self,
        source_id: str,
        request: ConnectorRequest,
        secret: str | None = None,
        secret_parameter: str | None = None,
    ) -> ConnectorResponse:
        params = dict(request.parameters)
        if secret and secret_parameter:
            params[secret_parameter] = secret

        url = request.endpoint
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)

        http_request = urllib.request.Request(
            url,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(
                http_request,
                timeout=self.timeout_seconds,
            ) as response:
                raw = response.read()
        except Exception as exc:
            raise HTTPError(f"{source_id} request failed: {exc}") from exc

        payload = json.loads(raw.decode("utf-8"))
        digest = hashlib.sha256(raw).hexdigest()
        return ConnectorResponse(
            source_id=source_id,
            request=request,
            payload=payload,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            content_hash=digest,
        )
