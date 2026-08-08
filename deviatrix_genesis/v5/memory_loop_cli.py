"""v5 CLI — Memory OS autonomous loop.

Usage::

    python -m deviatrix_genesis.v5 memory-loop --brief "GTM strategy" --write-memory-os
    python -m deviatrix_genesis.v5 memory-loop --from-memory-os --top-k 10
"""

from __future__ import annotations

import argparse
import json
import sys

from .memory_loop import ResilientMemoryLoop, build_brief_from_memories


def main() -> int:
    p = argparse.ArgumentParser(description="Deviatrix v5 Memory OS loop")
    p.add_argument("--brief", default="", help="Brief text (or --from-memory-os)")
    p.add_argument("--from-memory-os", action="store_true", help="Build brief from Memory OS")
    p.add_argument("--top-k", type=int, default=10, help="Top-k memories for brief")
    p.add_argument("--max-ideas", type=int, default=12)
    p.add_argument("--max-rounds", type=int, default=5)
    p.add_argument("--out", default=None, help="Output JSON path")
    args = p.parse_args()

    loop = ResilientMemoryLoop()

    if args.from_memory_os:
        # Query Memory OS for brief
        memories = loop._query_strategic_memories(top_k=args.top_k)
        brief = build_brief_from_memories(memories)
        print(f"[memory-loop] built brief from {len(memories)} memories")
    elif args.brief:
        brief = args.brief
    else:
        print("Error: provide --brief or --from-memory-os", file=sys.stderr)
        return 1

    print(f"[memory-loop] running cycle: {brief[:80]}...")
    result = loop.run_cycle(brief=brief, max_ideas=args.max_ideas, max_rounds=args.max_rounds)

    print(f"[memory-loop] survivors: {len(result.get('survivors', []))}")
    print(f"[memory-loop] memory IDs written: {len(result.get('memory_ids_written', []))}")
    if result.get("errors"):
        print(f"[memory-loop] errors: {result['errors']}")

    if args.out:
        with open(args.out, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"[memory-loop] wrote {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
