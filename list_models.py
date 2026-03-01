"""Diagnostic script — lists all Gemini models available for the given API key."""
import os
from google import genai
from google.genai import types

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("ERROR: GOOGLE_API_KEY not set")
    raise SystemExit(1)

for api_ver in ("v1beta", "v1"):
    print(f"\n=== Models available via {api_ver} ===")
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version=api_ver),
        )
        for m in client.models.list():
            print(m.name)
    except Exception as e:
        print(f"  Error: {e}")
