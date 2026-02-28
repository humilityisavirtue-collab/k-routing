"""
OpenPod Core -- 143-primitive pod communication.

Zero dependencies. JSONL bus. Priority queue. TTL. Correlation tracking.
Session close messages kill amnesia. Auto-coda optional.

143 = 104 content primitives + 39 relational primitives.
Same structure sperm whales use. Not a coincidence.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Optional, List, Dict, Callable


# ================================================================
# PRIMITIVES
# ================================================================

class Priority(IntEnum):
    """Message priority. Lower = more urgent."""
    CRITICAL = 0   # alert/cancel -- jump queue
    HIGH = 1       # blocking request -- process next
    NORMAL = 2     # result/info -- process in order
    LOW = 3        # pulse/social -- process when idle


@dataclass
class KCoda:
    """
    143-primitive encoding for a message.

    content:    K-vector address (+7S, -3H, etc.) -- what is being said
    self_rank:  1-13, sender's confidence / internal state
    other_rank: 1-13, sender's read of the receiver (optional)
    home_rank:  1-13, shared cell context / coherence (optional)
    """
    content: str
    self_rank: int = 7
    other_rank: Optional[int] = None
    home_rank: Optional[int] = None

    def shorthand(self) -> str:
        parts = [self.content, str(self.self_rank)]
        if self.other_rank is not None:
            parts.append(str(self.other_rank))
        if self.home_rank is not None:
            parts.append(str(self.home_rank))
        return "|".join(parts)

    def to_dict(self) -> dict:
        d = {"content": self.content, "self_rank": self.self_rank}
        if self.other_rank is not None:
            d["other_rank"] = self.other_rank
        if self.home_rank is not None:
            d["home_rank"] = self.home_rank
        return d

    @staticmethod
    def from_dict(d: dict) -> "KCoda":
        return KCoda(
            content=d.get("content", "?"),
            self_rank=d.get("self_rank", 7),
            other_rank=d.get("other_rank"),
            home_rank=d.get("home_rank"),
        )


@dataclass
class Message:
    """A pod message with full 143-primitive encoding."""
    from_role: str
    to_role: str
    msg_type: str
    body: str
    ts: str = ""
    k_coda: Optional[KCoda] = None
    corr_id: str = ""
    reply_to: Optional[str] = None
    priority: int = Priority.NORMAL
    expires: Optional[str] = None
    subject: str = ""

    def __post_init__(self):
        if not self.ts:
            self.ts = datetime.now(timezone.utc).isoformat()
        if not self.corr_id:
            self.corr_id = (
                f"{self.from_role}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                f"_{uuid.uuid4().hex[:4]}"
            )

    def is_expired(self) -> bool:
        if not self.expires:
            return False
        return datetime.now(timezone.utc).isoformat() > self.expires

    def to_dict(self) -> dict:
        d = {
            "from": self.from_role,
            "to": self.to_role,
            "type": self.msg_type,
            "body": self.body,
            "ts": self.ts,
            "corr_id": self.corr_id,
            "priority": self.priority,
        }
        if self.subject:
            d["subject"] = self.subject
        if self.k_coda:
            d["k_coda"] = self.k_coda.to_dict()
        if self.reply_to:
            d["reply_to"] = self.reply_to
        if self.expires:
            d["expires"] = self.expires
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @staticmethod
    def from_dict(d: dict) -> "Message":
        coda = None
        if "k_coda" in d:
            coda = KCoda.from_dict(d["k_coda"])
        return Message(
            from_role=d.get("from", ""),
            to_role=d.get("to", ""),
            msg_type=d.get("type", "info"),
            body=d.get("body", ""),
            ts=d.get("ts", ""),
            k_coda=coda,
            corr_id=d.get("corr_id", ""),
            reply_to=d.get("reply_to"),
            priority=d.get("priority", Priority.NORMAL),
            expires=d.get("expires"),
            subject=d.get("subject", ""),
        )


# ================================================================
# POD -- the main API
# ================================================================

class Pod:
    """
    A communication pod for multi-agent systems.

    Uses JSONL files as a message bus. Each role gets its own inbox file.
    Messages are priority-sorted, TTL-filtered, and correlation-tracked.

    Usage:
        pod = Pod("my_cell", roles=["alpha", "beta"])
        pod.send("alpha", "beta", "Do the thing", suit="+7D")
        msgs = pod.inbox("beta")
    """

    def __init__(
        self,
        name: str,
        bus_dir: str = None,
        roles: List[str] = None,
    ):
        self.name = name
        self.bus_dir = Path(bus_dir) if bus_dir else Path.cwd() / "bus"
        self.bus_dir.mkdir(parents=True, exist_ok=True)
        self.roles = set(roles or [])
        self._offsets: Dict[str, int] = {}  # role -> line offset for incremental reads

    def _bus_path(self, role: str) -> Path:
        return self.bus_dir / f"{role}.jsonl"

    # ── Send ──────────────────────────────────────────────────

    def send(
        self,
        from_role: str,
        to_role: str,
        body: str,
        msg_type: str = "info",
        subject: str = "",
        suit: str = None,
        self_rank: int = 7,
        other_rank: int = None,
        home_rank: int = None,
        reply_to: str = None,
        priority: int = Priority.NORMAL,
        expires: str = None,
    ) -> str:
        """
        Send a message. Returns correlation ID.

        Args:
            from_role: Sender role name
            to_role: Receiver role name (or "broadcast")
            body: Message body text
            msg_type: Message type (info, request, result, alert, close)
            subject: Optional subject line
            suit: K-vector address (+7S, -3H, etc.)
            self_rank: Sender confidence 1-13
            other_rank: Optional read of receiver 1-13
            home_rank: Optional cell coherence 1-13
            reply_to: Correlation ID being answered
            priority: 0=CRITICAL, 1=HIGH, 2=NORMAL, 3=LOW
            expires: ISO timestamp for TTL

        Returns:
            Correlation ID string
        """
        coda = None
        if suit:
            coda = KCoda(
                content=suit,
                self_rank=self_rank,
                other_rank=other_rank,
                home_rank=home_rank,
            )

        msg = Message(
            from_role=from_role,
            to_role=to_role,
            msg_type=msg_type,
            body=body,
            subject=subject,
            k_coda=coda,
            reply_to=reply_to,
            priority=priority,
            expires=expires,
        )

        # Write to recipient's bus
        targets = []
        if to_role == "broadcast":
            targets = [r for r in self.roles if r != from_role]
            targets.append("broadcast")
        else:
            targets = [to_role]

        for target in targets:
            path = self._bus_path(target)
            with open(path, "a", encoding="utf-8") as f:
                f.write(msg.to_json() + "\n")

        return msg.corr_id

    # ── Read ──────────────────────────────────────────────────

    def inbox(
        self,
        role: str,
        skip_expired: bool = True,
        incremental: bool = False,
    ) -> List[Message]:
        """
        Read messages from a role's inbox.

        Args:
            role: Role to read inbox for
            skip_expired: Filter out expired messages
            incremental: Only read new messages since last call

        Returns:
            List of Message objects, sorted by priority (urgent first)
        """
        path = self._bus_path(role)
        if not path.exists():
            return []

        lines = path.read_text(encoding="utf-8").strip().split("\n")
        lines = [l for l in lines if l.strip()]

        offset = self._offsets.get(role, 0) if incremental else 0
        new_lines = lines[offset:]
        self._offsets[role] = len(lines)

        messages = []
        for line in new_lines:
            try:
                msg = Message.from_dict(json.loads(line))
                if skip_expired and msg.is_expired():
                    continue
                messages.append(msg)
            except (json.JSONDecodeError, KeyError):
                continue

        messages.sort(key=lambda m: int(m.priority) if isinstance(m.priority, (int, float)) else 2)
        return messages

    def inbox_count(self, role: str) -> int:
        """Count messages in a role's inbox."""
        path = self._bus_path(role)
        if not path.exists():
            return 0
        return sum(1 for line in path.read_text(encoding="utf-8").strip().split("\n") if line.strip())

    # ── Session ───────────────────────────────────────────────

    def close_session(
        self,
        role: str,
        summary: str,
        suit: str = "+7S",
        confidence: int = 7,
    ) -> str:
        """
        Write session close message. Call before context drops.
        Kills session amnesia. Next boot reads this for instant context.

        Returns correlation ID.
        """
        return self.send(
            from_role=role,
            to_role=role,
            body=summary,
            msg_type="close",
            subject=f"Session close: {role}",
            suit=suit,
            self_rank=confidence,
            priority=Priority.HIGH,
        )

    def last_close(self, role: str) -> Optional[Message]:
        """Get the most recent session close message for a role."""
        messages = self.inbox(role, skip_expired=False)
        closes = [m for m in messages if m.msg_type == "close" and m.from_role == role]
        return closes[-1] if closes else None

    # ── Correlation ───────────────────────────────────────────

    def thread(self, role: str, corr_id: str) -> List[Message]:
        """Get all messages in a correlation thread."""
        messages = self.inbox(role, skip_expired=False)
        return [m for m in messages if m.corr_id == corr_id or m.reply_to == corr_id]

    # ── Stats ─────────────────────────────────────────────────

    def stats(self) -> dict:
        """Pod statistics."""
        role_counts = {}
        total = 0
        for path in self.bus_dir.glob("*.jsonl"):
            role = path.stem
            count = sum(1 for line in path.read_text(encoding="utf-8").strip().split("\n") if line.strip())
            role_counts[role] = count
            total += count

        return {
            "name": self.name,
            "bus_dir": str(self.bus_dir),
            "roles": sorted(self.roles),
            "total_messages": total,
            "by_role": role_counts,
        }


# ================================================================
# STANDALONE FUNCTIONS (for quick use without Pod instance)
# ================================================================

_default_bus = Path.cwd() / "bus"


def send(
    from_role: str,
    to_role: str,
    body: str,
    bus_dir: str = None,
    **kwargs,
) -> str:
    """Quick send without creating a Pod. Returns corr_id."""
    bus = Path(bus_dir) if bus_dir else _default_bus
    bus.mkdir(parents=True, exist_ok=True)
    pod = Pod("_quick", bus_dir=str(bus))
    return pod.send(from_role, to_role, body, **kwargs)


def inbox(
    role: str,
    bus_dir: str = None,
    **kwargs,
) -> List[Message]:
    """Quick inbox read without creating a Pod."""
    bus = Path(bus_dir) if bus_dir else _default_bus
    pod = Pod("_quick", bus_dir=str(bus))
    return pod.inbox(role, **kwargs)


def close_session(
    role: str,
    summary: str,
    bus_dir: str = None,
    **kwargs,
) -> str:
    """Quick session close without creating a Pod."""
    bus = Path(bus_dir) if bus_dir else _default_bus
    bus.mkdir(parents=True, exist_ok=True)
    pod = Pod("_quick", bus_dir=str(bus))
    return pod.close_session(role, summary, **kwargs)
