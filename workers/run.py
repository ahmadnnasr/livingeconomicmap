import argparse
import signal
import time


running = True


def stop(*_args):
    global running
    running = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "queue",
        choices=[
            "ingestion",
            "reasoning",
            "publication",
            "maintenance",
        ],
    )
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    print(
        f"worker_started queue={args.queue}",
        flush=True,
    )

    while running:
        time.sleep(5)

    print(
        f"worker_stopped queue={args.queue}",
        flush=True,
    )


if __name__ == "__main__":
    main()
