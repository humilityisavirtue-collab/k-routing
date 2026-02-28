"""
OpenPod -- 143-Primitive Inter-Agent Communication Protocol.

Whale-grade pod comms for AI agent cells. Zero deps. Magically fast.

Quick start:
    from openpod import Pod

    pod = Pod("my_cell", roles=["alpha", "beta", "gamma"])
    pod.send("alpha", "beta", "Build the widget", suit="+7D")
    messages = pod.inbox("beta")

143 primitives = 104 content (K-rooms) + 39 relational (3 axes x 13 ranks).
The minimum complete vocabulary for embodied, relational intelligence.
"""

__version__ = "0.1.0"

from openpod.core import Pod, KCoda, Message, Priority
from openpod.core import send, inbox, close_session
from openpod.models import LocalModels, load_torch_model, torch_available

__all__ = [
    "Pod", "KCoda", "Message", "Priority",
    "send", "inbox", "close_session",
    "LocalModels", "load_torch_model", "torch_available",
    "__version__",
]
