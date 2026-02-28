"""
openai_compat.py — KLAW as a drop-in OpenAI replacement.

Start the server: uvicorn klaw.api:app --port 8104
Then run this script — zero other changes needed.
"""
from openai import OpenAI

# Point any OpenAI client at localhost:8104
client = OpenAI(
    api_key="klaw-local",
    base_url="http://localhost:8104/v1"
)

response = client.chat.completions.create(
    model="klaw",
    messages=[{"role": "user", "content": "explain the halting problem"}]
)

print(response.choices[0].message.content)
# Headers include: X-K-Address, X-Cost, X-Tier, X-Savings
