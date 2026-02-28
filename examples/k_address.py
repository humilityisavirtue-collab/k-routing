"""
k_address.py — See how K-vector classification works.

A K-address has three components:
  polarity  (+/-): light (constructive) or dark (blocked/urgent)
  rank      (1-13): intensity / depth (Ace=1 through King=13)
  suit      (H/S/D/C): semantic domain

104 rooms total. Every query has one.
"""
from klaw import KlawClassifier

clf = KlawClassifier()

examples = [
    "hello",                                    # +2H  warm greeting
    "how are you feeling today",                # +3H  emotional check-in
    "debug this Python traceback",              # +6S  analytical problem
    "I can't figure this out, everything fails",# -7S  dark analysis / crisis
    "write a REST API endpoint",                # +5D  material construction
    "ship it",                                  # +4C  action / will
    "novel synthesis of two unrelated fields",  # +KS  peak analysis
]

for query in examples:
    addr = clf.classify(query)
    print(f"  {addr['shorthand']:<5}  {query}")

print()
print("Shorthand format: [polarity][rank][suit]")
print("  + = light (constructive)   - = dark (blocked/urgent)")
print("  H = Hearts (emotion)       S = Spades (analysis)")
print("  D = Diamonds (material)    C = Clubs (action)")
