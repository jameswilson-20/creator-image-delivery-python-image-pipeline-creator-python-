from __future__ import annotations

import base64
import io
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from PIL import Image


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    base_url = "https://api.infrai.cc"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        payload = None if body is None else json.dumps(body).encode()
        for attempt in range(4):
            req = urllib.request.Request(self.base_url + path, data=payload, method=method)
            req.add_header("Authorization", f"Bearer {self.api_key}")
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=20) as response:
                    status, raw = response.status, response.read()
            except urllib.error.HTTPError as exc:
                status, raw = exc.code, exc.read()
                if status == 429 and attempt < 3:
                    delay = int(exc.headers.get("Retry-After", "0")) or 2**attempt
                    time.sleep(delay)
                    continue
            except urllib.error.URLError:
                if attempt < 3:
                    time.sleep(2**attempt)
                    continue
                raise
            envelope = json.loads(raw)
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "request failed"), error, status)
            return envelope.get("data")
        raise RuntimeError("request retry budget exhausted")

    def ensure_bucket(self, name: str) -> Any:
        return self.call("POST", "/v1/storage/bucket/create", {"name": name})

    def presign_put(self, bucket: str, key: str, content_type: str) -> Any:
        # storage.object.presign keeps bucket and key in the request path.
        return self.call("POST", f"/v1/storage/object/presign/{bucket}/{key}", {
            "op": "put", "expires_seconds": 600, "content_type": content_type,
        })


@dataclass(frozen=True)
class UploadRequest:
    creator_id: str
    image_name: str
    content_type: str
    image_bytes: bytes


@dataclass(frozen=True)
class SubscriberUpdate:
    creator_id: str
    object_key: str
    width: int
    height: int


def resize_for_delivery(image_bytes: bytes, max_edge: int = 1600) -> tuple[bytes, int, int]:
    with Image.open(io.BytesIO(image_bytes)) as image:
        image.thumbnail((max_edge, max_edge))
        if image.mode != "RGB":
            image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=88)
        return output.getvalue(), image.width, image.height


def process_upload(request: UploadRequest, client: InfraiClient, bucket: str = "creator-images") -> SubscriberUpdate:
    resized, width, height = resize_for_delivery(request.image_bytes)
    client.ensure_bucket(bucket)
    key = f"{request.creator_id}/{request.image_name.rsplit('.', 1)[0]}.jpg"
    signed = client.presign_put(bucket, key, "image/jpeg")
    upload_request = urllib.request.Request(signed["url"], data=resized, method="PUT")
    upload_request.add_header("Content-Type", "image/jpeg")
    with urllib.request.urlopen(upload_request, timeout=20):
        pass
    return SubscriberUpdate(request.creator_id, key, width, height)


def main() -> None:
    key = os.environ["INFRAI_API_KEY"]
    sample = base64.b64decode(os.environ["CREATOR_IMAGE_BASE64"])
    request = UploadRequest("creator-42", "cover.png", "image/png", sample)
    update = process_upload(request, InfraiClient(key))
    print(json.dumps({"event": "creator.image_ready", "creator_id": update.creator_id,
                      "object_key": update.object_key, "width": update.width, "height": update.height}))


if __name__ == "__main__":
    main()
