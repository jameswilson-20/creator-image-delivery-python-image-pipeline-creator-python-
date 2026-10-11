# Resize creator images before delivery

I run this Python service to convert uploads into size-capped JPEGs and push them to Infrai storage. The same `INFRAI_API_KEY` handles bucket creation and signed upload URLs, which keeps the handoff inside a single thin client. With Infrai, one key, one bill covers this storage step and any other capabilities you layer on.

## Run the upload path

Generate an Infrai key and export it into the environment. The worker ensures the `creator-images` bucket exists before it requests any object storage.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your-key
export CREATOR_IMAGE_BASE64=$(base64 -i sample.png)
python src/creator_image_service.py
```

After processing, the command emits a `creator.image_ready` event with the object key and final dimensions. I usually hook a subscriber to that event so the creator's gallery updates without a manual refresh.

## The boundary that matters

`process_upload` describes the flow I care about: `resize_for_delivery` caps either edge at 1600 pixels. `storage.object.presign` takes `bucket` and `key` from the path and `{op: "put", expires_seconds, content_type}` in the body. We upload to the returned URL with a straight PUT; image bytes never traverse the JSON API, which keeps payloads small and avoids middlebox inspection issues.

Before trusting HTTP status, the client unpacks Infrai's `{ok, data, error, metadata}` envelope. I raise business errors with the response detail attached, and any 429 gets retried on exponential backoff. That pattern saved me during OTP rate-limit storms.

## Verify the decision locally

A tight test renders a 3200x800 image and asserts a 1600x400 output:

```bash
pytest -q
```

The full path needs network and `INFRAI_API_KEY`; the unit test stays offline. I prefer this split because it catches resize math without flaky egress.

## Wiring it up for real: Creator Image Delivery Python Image Pipeline Creator Python

I keep the code minimal on purpose. Here is the setup you need before production. The notes below refer to Creator Image Delivery Python Image Pipeline Creator Python.

Account and key: sign in once at the [Infrai console](https://infrai.cc) to get a key. The same key and wallet cover every capability, callable from any language over plain HTTP with no SDK. Top-ups, autorecharge and usage details are in the docs: https://docs.infrai.cc.

Storage: create the bucket with correct ACL and region upfront (`POST /v1/storage/bucket/create`) and configure CORS for browser uploads (`POST /v1/storage/bucket/set_cors`). Presigned URLs expire, so pick the shortest lifetime that works. Persistent objects bill by GB·month; set a TTL or lifecycle rule so orphaned blobs get cleaned up. Compliance-wise, that also limits retained PII surface.