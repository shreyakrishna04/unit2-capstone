# tokenomics/logger.py
import json
from datetime import datetime
#using costs for gemini-3.5-flash-lite
COST_PER_1K_INPUT  = 0.0003   # $0.30 per 1M tokens
COST_PER_1K_OUTPUT = 0.0025    # $2.50 per 1M tokens

def log(query: str, agent: str, input_tokens: int, output_tokens: int):
    input_cost  = (input_tokens  / 1000) * COST_PER_1K_INPUT
    output_cost = (output_tokens / 1000) * COST_PER_1K_OUTPUT
    total_cost  = input_cost + output_cost

    entry = {
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "agent": agent,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(total_cost, 6),
        "cost_per_1000_queries": round(total_cost * 1000, 2)
    }

    print(f"\n[TOKENOMICS] Agent: {agent} | Input: {input_tokens} | Output: {output_tokens} | Cost: ${total_cost:.6f}")

    with open("tokenomics_log.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")

    return entry