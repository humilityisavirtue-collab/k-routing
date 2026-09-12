"""KLAW smoke gate — run: python tests/test_smoke.py
Each assertion prints PASS/FAIL with the observed value. Exits nonzero on any FAIL."""
import sys, os, tempfile

sys.path.insert(0, "src")
from klaw.router import KlawRouter, ClawRuntime

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))

# --- corpus: the rooms.claw runtime must decrypt and expose rooms ---
rt = ClawRuntime()
check("corpus decrypts", rt.loaded, f"{rt.room_count} rooms")
check("corpus has >=100 rooms", rt.room_count >= 100, str(rt.room_count))

# --- classification ---
r = KlawRouter(data_dir=__import__("pathlib").Path(tempfile.mkdtemp()))
c = r.classify("hey, how's it going?")
check("flexible greeting -> tier 0", c["tier"] == 0, str(c["tier"]))
check("greeting has template_response", bool(c["template_response"]), repr(c["template_response"])[:40])
check("greeting k_address +1H", c["k_address"] == "+1H", c["k_address"])

# --- greeting rotation: multiple responses per greeting, rotated by day ---
pool = r.classifier.GREETING_ROTATIONS["hey"]
pinned = [r.classifier._get_greeting_response("hey", day_seed=d) for d in (738000, 738001, 738002, 738003)]
check("greeting rotation varies across days", len(set(pinned)) > 1, f"got {len(set(pinned))} distinct in 4 days")
check("rotation is deterministic per day", all(p == r.classifier._get_greeting_response("hey", day_seed=d)
                                               for d, p in zip((738000, 738001), pinned[:2])))
check("rotation output is always a pool member", all(p in pool for p in pinned))

c2 = r.classify("debug this stack trace for me, the exception happens in production")
check("coding query -> tier 2", c2["tier"] == 2, f"tier={c2['tier']} reason={c2['reason']}")
check("coding k_address ends in S", c2["k_address"].endswith("S"), c2["k_address"])
check("classification carries room enrichment", c2.get("room_name") is not None,
      f"room={c2.get('room_name')} meaning={c2.get('room_meaning')}")

# --- route (template path, no network) ---
res = r.route("hey, how's it going?")
check("route(greeting) -> tier_name 'template'", res["tier_name"] == "template", res["tier_name"])
check("route(greeting) returns a response", isinstance(res["response"], str) and len(res["response"]) > 0)
check("route(greeting) cost is 0", res["cost"] == 0.0, str(res["cost"]))
check("route result has top-level k_address", "k_address" in res and res["k_address"] == "+1H", str(res.get("k_address")))

# --- local fallback: no server on the test port must yield structured error, never crash ---
res2 = r.route("a plain question that lands on tier 1")
check("tier-1 failure returns structured result", isinstance(res2, dict) and "tier" in res2)
check("tier-1 fallback does not raise", True)  # got here == did not raise

fails = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} passed" + (f" — FAILURES: {fails}" if fails else " — ALL GREEN"))
sys.exit(1 if fails else 0)