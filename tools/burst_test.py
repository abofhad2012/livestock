import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def hit(url: str, timeout: float):
    start = time.perf_counter()
    try:
        req = Request(url, headers={"User-Agent": "LivestockLoadTest/1.0"})
        with urlopen(req, timeout=timeout) as response:
            response.read(512)
            status = response.status
    except HTTPError as exc:
        status = exc.code
    except URLError:
        status = "ERR"
    except Exception:
        status = "ERR"

    return status, time.perf_counter() - start


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    parser.add_argument("-n", "--requests", type=int, default=1000)
    parser.add_argument("-c", "--concurrency", type=int, default=200)
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()

    started = time.perf_counter()
    durations = []
    counts = {}

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(hit, args.url, args.timeout)
            for _ in range(args.requests)
        ]

        for future in as_completed(futures):
            status, duration = future.result()
            durations.append(duration)
            counts[status] = counts.get(status, 0) + 1

    elapsed = time.perf_counter() - started
    rps = args.requests / elapsed if elapsed else 0

    print("=" * 60)
    print(f"URL: {args.url}")
    print(f"Requests: {args.requests}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Elapsed seconds: {elapsed:.3f}")
    print(f"Requests/sec: {rps:.1f}")
    print(f"Status counts: {counts}")

    if durations:
        print(
            "Latency ms: "
            f"avg={statistics.mean(durations) * 1000:.1f}, "
            f"min={min(durations) * 1000:.1f}, "
            f"max={max(durations) * 1000:.1f}"
        )

        if len(durations) >= 20:
            p95 = statistics.quantiles(durations, n=20)[18]
            print(f"p95 ms: {p95 * 1000:.1f}")

    if elapsed <= 1:
        print("RESULT: 1000 requests finished in under 1 second.")
    else:
        print("RESULT: 1000 requests did NOT finish in under 1 second on this setup.")

    print("=" * 60)


if __name__ == "__main__":
    main()
