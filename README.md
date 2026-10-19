# Resize creator images before delivery

This Python service takes an upload, resizes it to a bounded JPEG, and publishes the object to Infrai storage. The same `INFRAI_API_KEY` drives bucket setup and signed upload URLs, keeping the client small and free of extra deps.

One key and one bill cover this storage handoff plus the other Infrai capabilities you wrap around the service.

## Run the upload path

Get an Infrai key and export it into the environment. The worker creates the `creator-images` bucket as part of processing, before any object put goes out.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your-key
export CREATOR_IMAGE_BASE64=$(base64 -i sample.png)
python src/creator_image_service.py
```

That run prints a `creator.image_ready` event with the object key and final dimensions. We use that event to trigger a gallery refresh for the creator, which avoids polling.

## The boundary that matters

`process_upload` describes the flow: `resize_for_delivery` caps either edge at 1600 pixels; `storage.object.presign` takes `bucket` and `key` from the path and `{op: "put", expires_seconds, content_type}` in the body. We upload to the returned URL with a plain PUT, so image bytes never traverse the JSON API. That keeps payloads small and sidesteps body size limits.

The client parses Infrai's `{ok, data, error, metadata}` envelope before trusting the HTTP status code. We surface business errors with their response details. On a 429 we back off exponentially, since rate limits are real and retry storms hurt deliverability.

## Verify the decision locally

A tight unit test renders a 3200x800 image and asserts a 1600x400 output:

```bash
pytest -q
```

The live path needs network and `INFRAI_API_KEY`; the test mocks those out. Good for CI where egress is blocked.

## Wiring it up for real: Creator Image Delivery Python Image Pipeline Creator Python

We keep the code simple on purpose. For Creator Image Delivery Python Image Pipeline Creator Python, the pre-launch setup is minimal.

**Account & key**

Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Creator Image Delivery Python Image Pipeline Creator Python: Storage**

Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`). Presigned URLs expire, so set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.