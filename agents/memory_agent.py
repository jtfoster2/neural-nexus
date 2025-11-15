from __future__ import annotations
from typing import TypedDict, List, Dict, Any, Optional
from dataclasses import dataclass
import re
import json
from functools import lru_cache
import db


class AgentState(TypedDict, total=False):
    input: str
    email: Optional[str]
    conversation_id: Optional[str]
    messages: List[Dict[str, str]]      # [{"role":"user|assistant","content":"..."}]
    
    # Context from memory_agent / supervisor
    context_summary: Optional[str]
    context_refs: Optional[List[str]]
    preface: Optional[str]
    memory: Optional[Dict[str, Any]]

# ------------ Simple REGEX identifiers ------------
ORDER  = re.compile(r"\bORD[\-_]?\d{3,}\b", re.IGNORECASE) #example: ORD_12345
PAY    = re.compile(r"\bPAY[\-_]?\d{3,}\b", re.IGNORECASE) #example: PAY_98765
EMAIL  = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE) #email regex
DATE   = re.compile(r"\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[/\-]\d{1,2}[/\-]20\d{2})\b") #YYYY-MM-DD or MM/DD/YYYY
ADDRESS = re.compile(r"\b\d{1,6}\s+[A-Za-z0-9 .'-]+,\s*[A-Za-z .'-]+,\s*[A-Za-z]{2}\s+\d{5}(?:-\d{4})?\b", re.IGNORECASE,) #US address
PHONE  = re.compile(r"\b(\+?1[-.\s]?|)\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b") #US phone number
NAME   = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b") #Simple full name

KEYWORDS  = {
    "return": {"return","refund","rma","exchange","restocking","window"},
    "shipping": {"ship","shipped","delivered","tracking","carrier","label"},
    "policy": {"policy","warranty","eligibility","non-returnable","international"},
    "payment": {"payment","charged","refunded","authorization","stripe","paypal","square"},
    "order": {"order","orders","purchase","buy","bought","item","items","product","products"},
    "account": {"account","login","log in","sign up","password","email","username","profile","address","phone","name"},
}

# ------------ Text Processing Helpers ------------
def _tokenize(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+", s.lower()))

def _extract_entities(text: str) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {"orders": [], "payments": [], "emails": [], "dates": [], "addresses": []}
    out["orders"]   = ORDER.findall(text) or []
    out["payments"] = PAY.findall(text) or []
    out["emails"]   = EMAIL.findall(text) or []
    out["dates"]    = DATE.findall(text) or []
    out["addresses"] = ADDRESS.findall(text) or []
    return out

def _detect_domain(text: str) -> List[str]:
    toks = _tokenize(text)
    hits = []
    for tag, vocab in KEYWORDS.items():
        if toks & vocab:
            hits.append(tag)
    return hits

# ------------ Building Memory Index ------------
@dataclass
class Msg:
    idx: int
    role: str
    content: str
    ents: Dict[str, List[str]]
    tags: List[str]
    toks: set

def _build_index(messages: List[Dict[str,str]]) -> List[Msg]:
    idx: List[Msg] = []
    for i, m in enumerate(messages):
        c = m.get("content","")
        ents = _extract_entities(c)
        tags = _detect_domain(c)
        toks = _tokenize(c)
        idx.append(Msg(i, (m.get("role") or "assistant"), c, ents, tags, toks))
    return idx

def _score(query: Msg, past: Msg) -> float:
    # Simple score: token overlap + entity overlap + domain overlap, with small weights
    score = 0.0
    if not past.content or past.idx == query.idx: 
        return score
    score += len(query.toks & past.toks) * 0.5
    for k in ("orders","payments","emails","dates"):
        qset, pset = set(query.ents[k]), set(past.ents[k])
        score += len(qset & pset) * 3.0
    score += len(set(query.tags) & set(past.tags)) * 2.0
    return score

def _topk_links(index: List[Msg], k: int = 4) -> List[Msg]:
    if not index:
        return []
    q = index[-1]  # newest message
    scored = [(m, _score(q, m)) for m in index[:-1]] # function scores each past message for relevance
    scored.sort(key=lambda x: x[1], reverse=True)
    return [m for m, s in scored if s > 0][:k]

# ------------ Summarization  ------------
def _shorten(s: str, n: int = 160) -> str:
    s = s.strip().replace("\n"," ")
    return s if len(s) <= n else s[:n-1] + "…"

def _compose_running_summary(index: List[Msg]) -> str:
    if not index:
        return ""
    # Concise: most recent domain + entities
    last = index[-1]
    dom = ", ".join(last.tags) if last.tags else "general"
    ents = []
    if last.ents["orders"]:   ents.append(f"orders: {', '.join(last.ents['orders'][:2])}")
    if last.ents["payments"]: ents.append(f"payments: {', '.join(last.ents['payments'][:2])}")
    if not ents:
        # fall back to a clipped fragment of last user message
        frag = _shorten(last.content, 80)
        return f"{dom} — {frag}"
    return f"{dom} — " + "; ".join(ents)

# ------------ Public API ------------
def memory_agent(state: AgentState) -> AgentState:
    """
    Gives quick context to agent responses:
      - context_summary: 1 line
      - context_refs: list of short prior snippets
      - memory: {entities, links}
    Will load previous messages from DB
    """
    # 1) Fetch messages
    msgs = state.get("messages") or []
    if not msgs and db and state.get("conversation_id"):
        row = db.get_conversation(state["conversation_id"])  # fetch from DB
        try:
            raw = row["conversation_text"] if hasattr(row, "__getitem__") else row 
        except Exception:
            raw = None
        if raw:
            try:
                msgs = json.loads(raw)
            except Exception:
                msgs = [{"role":"assistant","content":line} for line in (raw.splitlines() if raw else []) if line.strip()]

    if not msgs:
        # no context — returns a minimal state
        state["context_summary"] = ""
        state["context_refs"] = []
        state["memory"] = {"entities":{}, "links":[]}
        return state

    # 2) Builds index and links newest message
    index = _build_index(msgs[-20:])  # last 20 msgs
    links = _topk_links(index, k=5)

    # 3) Collect entities and builds memory
    entities: Dict[str, set] = {"orders": set(), "payments": set(), "emails": set(), "dates": set(), "addresses": set()}
    for m in index:
        for k, vals in m.ents.items():
            entities[k].update(vals)

    # 4) Produce summary
    summary = _compose_running_summary(index)
    refs = [f"{m.role}: {_shorten(m.content, 220)}" for m in links]

    # 5) Saves into state
    state["context_summary"] = summary
    state["context_refs"] = refs
    state["memory"] = {
        "entities": {k: sorted(list(v)) for k, v in entities.items()},
        "links": [m.idx for m in links],
    }
    return state

# Lets other agents fetch memory
TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "memory:get_context": {
        "fn": lambda **kw: {
            "summary": kw.get("context_summary",""),
            "refs": kw.get("context_refs", []),
            "entities": kw.get("entities", {}),
        },
        "schema": {"context_summary":"str","context_refs":"list[str]","entities":"dict"},
        "desc": "Return current memory summary/refs/entities",
    }
}
