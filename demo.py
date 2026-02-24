import httpx

BASE = "http://127.0.0.1:8000"


def main():
    timeout = httpx.Timeout(connect=5.0, read=120.0, write=120.0, pool=5.0)

    with httpx.Client(timeout=timeout) as client:
        print("\nFetching examples...\n")
        examples = client.get(f"{BASE}/examples").json()

        batch_input = [{"text": e["text"]} for e in examples]

        print("Sending batch to /process/batch... (this can take ~10-30s)\n")
        resp = client.post(f"{BASE}/process/batch", json=batch_input)
        resp.raise_for_status()

        results = resp.json()

    for i, r in enumerate(results):
        print("=" * 60)
        print(f"Case {i+1}")
        print(f"Entity: {r.get('entity_name')} ({r.get('entity_type')})")
        print(f"Jurisdiction: {r.get('jurisdiction')}")
        print(f"Risk Score: {r.get('risk_score')}")
        print(f"Flags: {', '.join(r.get('risk_flags', []))}")
        print(f"Summary: {r.get('summary')}")
        print("=" * 60)
        print()


if __name__ == "__main__":
    try:
        main()
    except httpx.ReadTimeout:
        print(
            "\nClient timed out waiting for the server. Increase read timeout further (e.g. 240s)."
        )
    except Exception as e:
        print(f"\nError: {e}")
