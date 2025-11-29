# src/agents/memory_agent.py
import json
import os
from ..utils.logger import logger

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "memory.json")
os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
if not os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "w") as f:
        json.dump([], f)

def load_memory():
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(entries):
    with open(MEMORY_FILE, "w") as f:
        json.dump(entries, f, indent=2)

def store_case(case_obj: dict):
    mem = load_memory()
    mem.append(case_obj)
    save_memory(mem)
    logger.info(f"Stored case: {case_obj.get('case_id')}")

def list_cases():
    return load_memory()
