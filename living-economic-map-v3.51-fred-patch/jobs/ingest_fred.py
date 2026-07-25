from __future__ import annotations

import json

from lemp_macro.live_fred import ingest_priority_series


def main() -> None:
    print(json.dumps(ingest_priority_series(), default=str))


if __name__ == "__main__":
    main()
