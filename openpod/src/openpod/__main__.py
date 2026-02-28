"""
OpenPod CLI -- 143-primitive pod communication + local model management.

Usage:
    openpod send alpha beta "Build the thing" --suit "+7D"
    openpod inbox beta
    openpod close alpha "Session done. Widget built."
    openpod stats
    openpod demo

    openpod model status           # What's available
    openpod model setup            # One-command pull + test
    openpod model setup --all      # Include optional models
    openpod model pull hermes3:8b  # Pull specific model
    openpod model test hermes3:8b  # Test inference
    openpod model ask hermes3:8b "What is K-104?"
    openpod model gpu              # Check PyTorch/CUDA
"""

import json
import sys


def main():
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = sys.argv[1:]
    if not args:
        print(__doc__.strip())
        return

    cmd = args[0]

    if cmd == "send":
        cmd_send(args[1:])
    elif cmd == "inbox":
        cmd_inbox(args[1:])
    elif cmd == "close":
        cmd_close(args[1:])
    elif cmd == "stats":
        cmd_stats(args[1:])
    elif cmd == "demo":
        cmd_demo()
    elif cmd == "model":
        cmd_model(args[1:])
    elif cmd == "setup":
        cmd_setup()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__.strip())


def cmd_send(args):
    if len(args) < 3:
        print("Usage: openpod send <from> <to> <body> [--suit +7S] [--priority 2] [--subject ...]")
        return
    from openpod import Pod
    from_role, to_role, body = args[0], args[1], args[2]

    suit = None
    priority = 2
    subject = ""
    bus_dir = None
    i = 3
    while i < len(args):
        if args[i] == "--suit" and i + 1 < len(args):
            suit = args[i + 1]; i += 2
        elif args[i] == "--priority" and i + 1 < len(args):
            priority = int(args[i + 1]); i += 2
        elif args[i] == "--subject" and i + 1 < len(args):
            subject = args[i + 1]; i += 2
        elif args[i] == "--bus" and i + 1 < len(args):
            bus_dir = args[i + 1]; i += 2
        else:
            i += 1

    pod = Pod("cli", bus_dir=bus_dir)
    corr_id = pod.send(from_role, to_role, body, suit=suit, priority=priority, subject=subject)
    print(f"  Sent: {from_role} -> {to_role}")
    print(f"  ID:   {corr_id}")
    if suit:
        print(f"  Coda: {suit}")


def cmd_inbox(args):
    if not args:
        print("Usage: openpod inbox <role> [--bus <dir>] [--tail <n>]")
        return
    from openpod import Pod
    role = args[0]
    bus_dir = None
    tail = 10
    i = 1
    while i < len(args):
        if args[i] == "--bus" and i + 1 < len(args):
            bus_dir = args[i + 1]; i += 2
        elif args[i] == "--tail" and i + 1 < len(args):
            tail = int(args[i + 1]); i += 2
        else:
            i += 1

    pod = Pod("cli", bus_dir=bus_dir)
    messages = pod.inbox(role)
    if not messages:
        print(f"  No messages for {role}")
        return

    print(f"  {role}: {len(messages)} messages (showing last {tail})")
    print()
    for msg in messages[-tail:]:
        pri = ["!!!", "!!", " ", "."][min(msg.priority, 3)]
        coda = msg.k_coda.shorthand() if msg.k_coda else ""
        subj = msg.subject[:40] if msg.subject else msg.body[:40]
        print(f"  {pri} [{msg.from_role}] {subj}  {coda}")


def cmd_close(args):
    if len(args) < 2:
        print("Usage: openpod close <role> <summary> [--suit +7S] [--bus <dir>]")
        return
    from openpod import Pod
    role, summary = args[0], args[1]
    suit = "+7S"
    bus_dir = None
    i = 2
    while i < len(args):
        if args[i] == "--suit" and i + 1 < len(args):
            suit = args[i + 1]; i += 2
        elif args[i] == "--bus" and i + 1 < len(args):
            bus_dir = args[i + 1]; i += 2
        else:
            i += 1

    pod = Pod("cli", bus_dir=bus_dir)
    corr_id = pod.close_session(role, summary, suit=suit)
    print(f"  Session closed: {role}")
    print(f"  ID: {corr_id}")


def cmd_stats(args):
    from openpod import Pod
    bus_dir = None
    roles = []
    i = 0
    while i < len(args):
        if args[i] == "--bus" and i + 1 < len(args):
            bus_dir = args[i + 1]; i += 2
        else:
            roles.append(args[i]); i += 1

    pod = Pod("cli", bus_dir=bus_dir, roles=roles)
    s = pod.stats()
    print(f"\n  {'='*45}")
    print(f"  OPENPOD: {s['name']}")
    print(f"  {'='*45}")
    print(f"  Bus:      {s['bus_dir']}")
    print(f"  Total:    {s['total_messages']} messages")
    for role, count in sorted(s["by_role"].items(), key=lambda x: -x[1]):
        print(f"    {role:>12}: {count}")
    print()


def cmd_demo():
    from openpod import Pod
    import tempfile, os
    tmp = tempfile.mkdtemp(prefix="openpod_demo_")
    pod = Pod("demo_cell", bus_dir=tmp, roles=["alpha", "beta", "gamma"])

    print("\n  OpenPod Demo -- 143-primitive pod comms\n")

    # Send some messages
    id1 = pod.send("alpha", "beta", "Navigator fix complete.", msg_type="result",
                    suit="+8S", self_rank=9, subject="Fix done")
    print(f"  alpha -> beta: 'Navigator fix complete.' [{id1}]")

    id2 = pod.send("beta", "alpha", "Acknowledged. Integrating.", msg_type="response",
                    suit="+6D", self_rank=7, reply_to=id1, subject="ACK")
    print(f"  beta -> alpha: 'Acknowledged.' [reply_to={id1[:20]}...]")

    id3 = pod.send("gamma", "broadcast", "Coherence alert: 3 suits active.",
                    msg_type="alert", suit="-10C", self_rank=9, priority=0,
                    subject="COHERENCE ALERT")
    print(f"  gamma -> broadcast: CRITICAL alert [{id3}]")

    pod.close_session("alpha", "Demo done. Navigator fixed, widget built.", suit="+9S")
    print(f"  alpha: session closed")

    # Read inbox
    print(f"\n  --- beta inbox ---")
    for msg in pod.inbox("beta"):
        pri = ["!!!", "!!", " ", "."][min(msg.priority, 3)]
        coda = msg.k_coda.shorthand() if msg.k_coda else ""
        print(f"  {pri} [{msg.from_role}] {msg.subject}  {coda}")

    print(f"\n  --- alpha last close ---")
    lc = pod.last_close("alpha")
    if lc:
        print(f"  {lc.body}")

    # Stats
    s = pod.stats()
    print(f"\n  Total: {s['total_messages']} messages across {len(s['by_role'])} channels")

    # Cleanup
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n  Demo complete. Temp bus cleaned up.\n")


def cmd_setup():
    print("""
  ============================================================
                      OPENPOD SETUP
  ============================================================

  1. Install:
     pip install openpod

  2. Create a pod:
     from openpod import Pod
     pod = Pod("my_cell", roles=["alpha", "beta", "gamma"])

  3. Send messages:
     pod.send("alpha", "beta", "Do the thing", suit="+7D")

  4. Read inbox:
     for msg in pod.inbox("beta"):
         print(msg.body)

  5. Close sessions (kills amnesia):
     pod.close_session("alpha", "Widget built. Tests pass.")

  CLI usage:
     openpod send alpha beta "message" --suit "+7S"
     openpod inbox beta
     openpod close alpha "summary"
     openpod stats
     openpod demo
  ============================================================
""")


def cmd_model(args):
    if not args:
        print("Usage: openpod model <status|setup|pull|test|ask|gpu>")
        return

    from openpod.models import LocalModels, torch_available
    lm = LocalModels()
    subcmd = args[0]

    if subcmd == "status":
        s = lm.status()
        print(f"\n  {'='*45}")
        print(f"  OPENPOD LOCAL MODELS")
        print(f"  {'='*45}")
        print(f"  Ollama:  {'running' if s['ollama_running'] else 'NOT running'}")
        if s['models_available']:
            print(f"  Models:")
            for m in s['models_available']:
                print(f"    {m['name']:>25}  {m['size']}")
        if s['models_missing']:
            print(f"  Missing:")
            for m in s['models_missing']:
                req = " (REQUIRED)" if m['required'] else ""
                print(f"    {m['model']:>25}  {m['size']}  {m['purpose']}{req}")
        print(f"  Ready:   {'YES' if s['ready'] else 'NO'}")
        print()

    elif subcmd == "setup":
        include_all = "--all" in args
        print(f"\n  OpenPod Model Setup\n")
        lm.setup(include_optional=include_all)
        print()

    elif subcmd == "pull":
        if len(args) < 2:
            print("Usage: openpod model pull <model_name>")
            return
        lm.pull(args[1])

    elif subcmd == "test":
        if len(args) < 2:
            print("Usage: openpod model test <model_name>")
            return
        t = lm.test(args[1])
        ok = "OK" if t["ok"] else "FAIL"
        print(f"  {t['model']}: {ok} ({t['latency_ms']}ms) -> \"{t['response']}\"")

    elif subcmd == "ask":
        if len(args) < 3:
            print("Usage: openpod model ask <model> <prompt>")
            return
        model = args[1]
        prompt = " ".join(args[2:])
        response = lm.ask(model, prompt)
        print(f"\n  {response}\n")

    elif subcmd == "gpu":
        ta = torch_available()
        print(f"\n  PyTorch:  {'installed' if ta['torch'] else 'NOT installed'}")
        print(f"  CUDA:     {'available' if ta['cuda'] else 'not available'}")
        if ta['cuda']:
            print(f"  GPU:      {ta['gpu_name']}")
            print(f"  VRAM:     {ta['vram_gb']}GB")
        if not ta['torch']:
            print(f"\n  Install: pip install torch transformers")
        print()

    else:
        print(f"Unknown model command: {subcmd}")
        print("  Commands: status, setup, pull, test, ask, gpu")


if __name__ == "__main__":
    main()
