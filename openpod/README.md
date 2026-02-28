# OpenPod

143-primitive inter-agent communication protocol. Whale-grade pod comms for AI agent cells.

## Install

```bash
pip install openpod
```

## Quick Start

```python
from openpod import Pod

pod = Pod("my_cell", roles=["alpha", "beta", "gamma"])

# Send with K-coda (suit + confidence)
pod.send("alpha", "beta", "Build the widget", suit="+7D", self_rank=9)

# Read inbox (priority-sorted, TTL-filtered)
for msg in pod.inbox("beta"):
    print(f"[{msg.from_role}] {msg.body}")

# Close session (kills amnesia)
pod.close_session("alpha", "Widget built. Tests pass.")
```

## CLI

```bash
openpod send alpha beta "Do the thing" --suit "+7S"
openpod inbox beta
openpod close alpha "Session done."
openpod stats
openpod demo
```

## Why 143

104 content primitives (4 suits x 13 ranks x 2 polarities) + 39 relational primitives (3 axes x 13 ranks) = 143. Same vocabulary size as sperm whale codas. The minimum complete set for embodied, relational intelligence.

## License

MIT
