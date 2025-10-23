from __future__ import annotations
from typing import TypedDict, Optional, List, Dict, Any, Callable
from datetime import datetime, timedelta, timezone
import re, json

# ---------------- Defaults ----------------
DEFAULTS = {
    "return_window_days": 30,
    "rma_ship_back_days": 7,
    "warranty_years": 1,
    "non_returnable_categories": {"digital goods", "perishable", "personalized", "gift cards", "clearance", "final sale"},
    "max_restocking_fee_pct": 0.15,
    "prepaid_label_on": {"defective", "incorrect"},
    "international_customer_pays": True,
}

# ---------------- State ----------------
class AgentState(TypedDict, total=False):
    input: str
    intent: Optional[str]
    tool_calls: List[str]
    tool_results: List[str]
    output: Optional[str]
    confidence: float

    # policy injection
    policy_text: Optional[str]
    return_policy: Optional[str]
    policy_format: Optional[str]  # "plain" | "json"

    # order / item context
    order_id: Optional[str]
    delivery_date: Optional[str]    # YYYY-MM-DD or ISO
    purchase_date: Optional[str]
    category: Optional[str]
    condition: Optional[str]
    original_packaging: Optional[bool]
    proof_of_purchase: Optional[bool]
    is_defective: Optional[bool]
    is_incorrect_item: Optional[bool]
    customer_reason: Optional[str]
    country: Optional[str]
    payment_method: Optional[str]

# ---------------- Compile policy text ----------------

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def compile_policy(policy_text: Optional[str], policy_format: str = "plain") -> Dict[str, Any]:
    print("[DEBUG] " + policy_text)
    if not policy_text:
        return dict(DEFAULTS)
    if policy_format == "json":
        try:
            cfg = json.loads(policy_text)
            out = dict(DEFAULTS)
            out.update(cfg)
            return out
        except Exception:
            pass
    txt = _clean(policy_text)
    cfg = dict(DEFAULTS)
    m = re.search(r"within\s+(\d{1,3})\s*days\s+of\s+the\s+delivery\s+date", txt)
    if m: cfg["return_window_days"] = int(m.group(1))
    m = re.search(r"within\s+(\d{1,3})\s*days\s+of\s+rma\s+approval", txt)
    if m: cfg["rma_ship_back_days"] = int(m.group(1))
    m = re.search(r"(\d+)[-\s]*year\s+limited\s+warranty", txt)
    if m: cfg["warranty_years"] = int(m.group(1))
    m = re.search(r"non[-\s]*returnable.*?including\s+(.*?)\.", txt)
    if m:
        items = [i.strip(" .") for i in re.split(r",|and", m.group(1)) if i.strip()]
        if items: cfg["non_returnable_categories"] = set(items)
    m = re.search(r"restocking\s+charges?.*?\(up\s*to\s*(\d{1,2})%\)", txt)
    if m: cfg["max_restocking_fee_pct"] = int(m.group(1))/100.0
    if "defective or incorrect items: we cover all return shipping costs" in txt:
        cfg["prepaid_label_on"] = {"defective", "incorrect"}
    if "international customers are responsible for all return shipping" in txt:
        cfg["international_customer_pays"] = True
    return cfg

# ---------------- Date helpers ----------------

def _to_date(s: Optional[str]) -> Optional[datetime]:
    if not s: return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None

def _now() -> datetime:
    return datetime.now(timezone.utc)

# ---------------- Core checks ----------------

def return_eligibility(*, delivery_date: Optional[str], category: Optional[str], condition: Optional[str],
                       original_packaging: Optional[bool], proof_of_purchase: Optional[bool],
                       is_defective: Optional[bool], is_incorrect_item: Optional[bool],
                       customer_reason: Optional[str], country: Optional[str],
                       policy_cfg: Optional[dict] = None) -> Dict[str, Any]:
    cfg = policy_cfg or DEFAULTS
    window = int(cfg["return_window_days"])  # days
    ship_back_days = int(cfg["rma_ship_back_days"])  # days
    nonret = {_clean(x).replace(" ", "_") for x in cfg["non_returnable_categories"]}
    restock = float(cfg["max_restocking_fee_pct"])  # fraction
    prepaid_on = {_clean(x) for x in cfg.get("prepaid_label_on", set())}

    now = _now()
    delivered = _to_date(delivery_date)
    days_since = None if not delivered else abs((now - delivered).days)
    window_ok = (days_since is not None) and (days_since <= window)

    cat = _clean(category or "").replace(" ", "_")
    non_returnable = cat in nonret

    cond = _clean(condition or "")
    condition_ok = cond in {"new", "unused", "resalable"} and bool(original_packaging)

    has_proof = bool(proof_of_purchase)
    prepaid_label = (bool(is_defective) and "defective" in prepaid_on) or (bool(is_incorrect_item) and "incorrect" in prepaid_on)

    eligible = window_ok and (not non_returnable) and condition_ok and has_proof

    reasons: List[str] = []
    if delivered is None: reasons.append("Missing delivery date.")
    elif not window_ok: reasons.append(f"Outside {window}-day window ({days_since} days since delivery).")
    if non_returnable: reasons.append("Item is non-returnable per policy category.")
    if not condition_ok: reasons.append("Item must be new/unused/resalable with original packaging.")
    if not has_proof: reasons.append("Proof of purchase required.")

    intl = _clean(country or "") not in {"", "us", "usa", "united states"}
    notes = ["International: customer pays shipping + duties/taxes."] if (intl and cfg.get("international_customer_pays", True)) else []

    return {
        "eligible": bool(eligible),
        "prepaid_label": bool(prepaid_label),
        "restocking_fee_pct": restock if (eligible and not (is_defective or is_incorrect_item)) else 0.0,
        "rma_ship_by": (now + timedelta(days=ship_back_days)).date().isoformat() if eligible else None,
        "reasons": reasons,
        "notes": notes,
    }

def warranty_eligibility(*, purchase_date: Optional[str], delivery_date: Optional[str],
                         proof_of_purchase: Optional[bool], is_defective: Optional[bool],
                         policy_cfg: Optional[dict] = None) -> Dict[str, Any]:
    cfg = policy_cfg or DEFAULTS
    years = int(cfg["warranty_years"])  # years

    now = _now()
    anchor = _to_date(delivery_date) or _to_date(purchase_date)
    within = False
    days_since = None
    if anchor:
        days_since = abs((now - anchor).days)
        within = anchor + timedelta(days=365 * years) >= now

    reasons: List[str] = []
    if not proof_of_purchase: reasons.append("Proof of purchase required for warranty.")
    if not is_defective: reasons.append("Warranty covers manufacturer defects only.")
    if anchor is None: reasons.append("Missing delivery/purchase date.")
    elif not within: reasons.append(f"Outside {years}-year limited warranty window.")

    eligible = bool(within and proof_of_purchase and is_defective)
    return {"eligible": eligible, "days_since_delivery_or_purchase": days_since, "reasons": reasons}

# ---------------- Minimal agent + tools ----------------
Tool = Callable[..., Any]
TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "policy:return_eligibility": {
        "fn": lambda **kw: return_eligibility(**kw),
        "schema": {},
        "desc": "Evaluate return eligibility against policy config",
    },
    "policy:warranty_eligibility": {
        "fn": lambda **kw: warranty_eligibility(**kw),
        "schema": {},
        "desc": "Evaluate warranty eligibility against policy config",
    },
}

class PolicyAgent:
    def run(self, state: AgentState) -> AgentState:
        state.setdefault("tool_calls", []); state.setdefault("tool_results", [])
        pol_text = state.get("policy_text") or state.get("return_policy")
        cfg = compile_policy(pol_text, state.get("policy_format", "plain"))

        # Decide which check to run
        text = _clean(state.get("input", ""))
        do_warranty = any(w in text for w in ["warranty", "defect", "manufacturer"]) and not any(w in text for w in ["return", "refund", "exchange", "rma"]) 

        if do_warranty:
            args = {
                "purchase_date": state.get("purchase_date"),
                "delivery_date": state.get("delivery_date"),
                "proof_of_purchase": state.get("proof_of_purchase", True),
                "is_defective": state.get("is_defective", False),
                "policy_cfg": cfg,
            }
            state["tool_calls"].append("policy:warranty_eligibility({...})")
            res = warranty_eligibility(**args)
            state["tool_results"].append(repr(res)[:400])
            state["output"] = _fmt_warranty(res)
            state["confidence"] = 0.85
            return state

        args = {
            "delivery_date": state.get("delivery_date"),
            "category": state.get("category"),
            "condition": state.get("condition"),
            "original_packaging": state.get("original_packaging"),
            "proof_of_purchase": state.get("proof_of_purchase", True),
            "is_defective": state.get("is_defective", False),
            "is_incorrect_item": state.get("is_incorrect_item", False),
            "customer_reason": state.get("customer_reason"),
            "country": state.get("country"),
            "policy_cfg": cfg,
        }
        state["tool_calls"].append("policy:return_eligibility({...})")
        res = return_eligibility(**args)
        state["tool_results"].append(repr(res)[:400])
        state["output"] = _fmt_return(res)
        state["confidence"] = 0.85
        return state

# ---------------- Formatting ----------------

def _fmt_return(res: Dict[str, Any]) -> str:
    if res.get("eligible"):
        fee = res.get("restocking_fee_pct", 0.0)
        fee_text = f" A restocking fee up to {int(round(fee*100))}% may apply." if fee else ""
        label = "Prepaid label provided." if res.get("prepaid_label") else "Customer pays return shipping."
        ship_by = res.get("rma_ship_by")
        return (
            f"✅ Return eligible. {label}{fee_text}\n"
            + (f"**RMA ship-by:** {ship_by}" if ship_by else "")
        )
    reasons = res.get("reasons") or ["Not eligible per policy."]
    notes = res.get("notes") or []
    return "❌ Return not eligible:\n- " + "\n- ".join(reasons + notes)

def _fmt_warranty(res: Dict[str, Any]) -> str:
    if res.get("eligible"):
        return "✅ Warranty claim eligible. Provide proof of purchase and start a claim."
    return "❌ Warranty not eligible:\n- " + "\n- ".join(res.get("reasons") or [])

# ---------------- Public entrypoint ----------------

def policy_agent(state: AgentState) -> AgentState:
    if not isinstance(state, dict):
        state = {"input": str(state)}
    try:
        return PolicyAgent().run(state)
    except Exception as e:
        state.setdefault("tool_calls", []); state.setdefault("tool_results", [])
        state["tool_results"].append(f"[FATAL] {e!r}")
        state["output"] = "Sorry—something went wrong while evaluating policy."
        state["confidence"] = 0.2
        return state
