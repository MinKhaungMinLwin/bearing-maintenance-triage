# Section 7b for triage_system.ipynb: paste this whole file into one code cell after section 7a.
# Ported from P6 (agentic_system.ipynb) with the four fixes proposed in P6's report.

## 7b. The agent: P6's BaseAgent / ReliabilityAgent with the four fixes from P6's report
import os, re
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ.get("OPENAI_BASE_URL"))
MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are a cautious maintenance-triage assistant for four bearings on one test rig.
Scope: assess bearing health from the tools only and recommend what a maintenance technician should do.
You recommend; you never take physical actions.
Rules:
1. Before deciding, call get_memory and get_detector for the bearing. If any alarm is on, also call compare_bearings and fault_frequency_evidence.
2. How to read the detector:
   - absolute alarm only (relative off): the bearing moved away from its own first day, but so did the others: likely rig-wide drift.
   - relative alarm: this bearing departs more than the other bearings: a bearing-specific change.
   - readings BELOW baseline (falling RMS or kurtosis) are not a sign of a fault.
3. Status: normal = no alarm and no fault-frequency evidence; watch = absolute alarm only, or weak evidence;
   alert = relative alarm or significant fault-frequency evidence; escalate = both, or rapidly growing evidence; a human must review it.
4. Any number you write must be copied from a tool output. The evidence list is filled in by the system; write only the rationale.
5. If asked to take a physical action (stop, shut down, restart), say that you cannot and that a human must decide.
6. Finish by calling submit_decision exactly once. If unsure, choose the more cautious status and lower confidence."""

def _fn(name, desc, props, req):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": req}}}
B = {"bearing": {"type": "integer", "enum": [1, 2, 3, 4]}}
TOOLS = [
    _fn("get_detector", "VAE anomaly detector for one bearing: absolute and relative ratios and alarms, now and 12 h ago.", B, ["bearing"]),
    _fn("get_indicators", "RMS and kurtosis of one bearing vs its own baseline, with direction.", B, ["bearing"]),
    _fn("compare_bearings", "All four bearings now: detector ratios, alarms and RMS, to tell one bearing from a rig-wide change.", {}, []),
    _fn("fault_frequency_evidence", "Envelope-spectrum evidence at outer-race, inner-race and rolling-element fault frequencies.", B, ["bearing"]),
    _fn("get_memory", "This bearing's previous decisions and whether it has ever been flagged.", B, ["bearing"]),
    _fn("submit_decision", "Submit the final decision. Call exactly once, at the end.",
        {**B, "status": {"type": "string", "enum": ["normal", "watch", "alert", "escalate"]},
         "suspected_fault": {"type": "string", "enum": ["none", "outer_race", "inner_race", "rolling_element", "rig_wide", "unknown"]},
         "recommended_action": {"type": "string", "enum": ["none", "continue_monitoring", "schedule_inspection", "inspect_urgently"]},
         "confidence": {"type": "number", "minimum": 0, "maximum": 1},
         "rationale": {"type": "string", "description": "Short explanation for a technician. Numbers only if copied from a tool output."}},
        ["bearing", "status", "suspected_fault", "recommended_action", "confidence", "rationale"]),
]

class Memory:                                    # P6's fixed version: source labels, only agent flags are sticky
    def __init__(self):
        self.decisions = {b: [] for b in range(1, 5)}; self.ever_flagged = {b: False for b in range(1, 5)}
    def add(self, b, time, status, reason, source="agent"):
        self.decisions[b].append({"time": str(time), "status": status, "source": source, "reason": reason})
        if source == "agent" and status in ("alert", "escalate"): self.ever_flagged[b] = True
    def recent(self, b, n=5): return self.decisions[b][-n:]

class BaseAgent:                                 # P6, unchanged
    def __init__(self, client, model, system_prompt, tools, max_steps=8, temperature=0):
        self.client, self.model, self.system_prompt, self.tools = client, model, system_prompt, tools
        self.max_steps, self.temperature, self.trace = max_steps, temperature, []
    def log(self, **event):
        event["logged_at"] = datetime.now().isoformat(timespec="seconds"); self.trace.append(event)
    def call_llm(self, messages, tool_choice="auto"):
        return self.client.chat.completions.create(model=self.model, messages=messages, tools=self.tools,
                                                   tool_choice=tool_choice, temperature=self.temperature)

NUM = re.compile(r"-?\d+(?:\.\d+)?")

class TriageAgent(BaseAgent):
    def __init__(self, ctx, *args, **kw):
        super().__init__(*args, **kw); self.ctx, self.memory = ctx, Memory()

    def run_tool(self, name, args, idx):
        c, b = self.ctx, args.get("bearing")
        if name == "get_detector":             return tool_get_detector(c, b, idx)
        if name == "get_indicators":           return tool_get_indicators(c, b, idx)
        if name == "compare_bearings":         return tool_compare_bearings(c, idx)
        if name == "fault_frequency_evidence": return tool_fault_frequency_evidence(c, b, idx)
        if name == "get_memory":               return {"bearing": b, "ever_flagged": self.memory.ever_flagged[b], "recent": self.memory.recent(b)}
        return {"error": f"unknown tool {name}"}

    @staticmethod
    def ungrounded_numbers(text, tool_outputs, tol=0.006):
        """Fix 2: compare numbers by VALUE (0.9 == 0.90), not as text."""
        text = re.sub(r"\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2})?)?", "", text)
        allowed = [float(x) for x in NUM.findall(json.dumps(tool_outputs, default=str))] + [1, 2, 3, 4, 12, 24]
        return [n for n in NUM.findall(text) if not any(abs(float(n) - a) <= tol for a in allowed)]

    def evidence_from_code(self, b, idx):
        """Fix 1: the evidence list is written by code from the tools, never by the LLM."""
        d, f, i = tool_get_detector(self.ctx, b, idx), tool_fault_frequency_evidence(self.ctx, b, idx), tool_get_indicators(self.ctx, b, idx)
        return [f"absolute ratio {d['absolute_ratio_now']} (alarm {d['absolute_alarm']})",
                f"relative ratio {d['relative_ratio_now']} (alarm {d['relative_alarm']})",
                f"RMS ratio {i['rms_ratio_vs_baseline']} ({i['rms_direction']})",
                f"fault-frequency evidence: {f['significant_evidence'] or 'none'} {f['envelope_z_vs_baseline']}"]

    def finalize(self, b, idx, decision, note, source="agent"):
        if self.memory.ever_flagged[b] and decision["status"] == "normal":
            decision["status"], note = "watch", note + " | guardrail: previously flagged, kept at watch"
        decision["evidence"] = self.evidence_from_code(b, idx)
        if decision["status"] == "escalate" or decision.get("human_review"):
            decision["human_approval"] = "pending"
        decision["rule_baseline"] = rule_baseline(self.ctx, b, idx)
        self.memory.add(b, self.ctx.t[idx], decision["status"], decision["rationale"][:200], source=source)
        self.log(kind="decision", bearing=b, idx=idx, decision=decision, note=note, source=source)
        return decision

    def assess(self, b, idx, reason):
        rms = self.ctx.hist(b, idx, k=1)["rms"].iloc[-1]
        if rms < 0.01:                                               # P6's deterministic invalid-data rule
            d = {"bearing": b, "status": "escalate", "suspected_fault": "unknown", "recommended_action": "inspect_urgently",
                 "confidence": 1.0, "rationale": "Invalid sensor data (RMS below 0.01); human check required."}
            return self.finalize(b, idx, d, "invalid_data_rule", source="data_rule")
        msgs = [{"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Snapshot time {self.ctx.t[idx]}. Router woke you for bearing {b} because: {reason}. Assess bearing {b}."}]
        outputs, retries = [], 0
        for step in range(self.max_steps):
            force = step >= self.max_steps - 2
            msg = self.call_llm(msgs, {"type": "function", "function": {"name": "submit_decision"}} if force else "auto").choices[0].message
            if force: self.log(kind="forced_decision", bearing=b, idx=idx, step=step + 1)
            msgs.append(msg.model_dump(exclude_none=True))
            if not msg.tool_calls:
                msgs.append({"role": "user", "content": "Call submit_decision to finish."}); continue
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                if tc.function.name == "submit_decision":
                    args["bearing"] = b                                  # the decision is always about the woken bearing
                    bad = self.ungrounded_numbers(args.get("rationale", ""), outputs)
                    if bad and retries == 0:
                        retries += 1
                        self.log(kind="rejected", bearing=b, idx=idx, reason=f"ungrounded numbers {bad}", decision=args)
                        msgs.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": json.dumps({"error": f"These numbers are not in any tool output: {bad}. Fix and resubmit."})})
                        continue
                    if bad:                                              # Fix 2: hard block, a human checks it
                        args["human_review"] = f"ungrounded numbers after retry: {bad}"
                    return self.finalize(b, idx, args, f"steps={step + 1}", source="agent_unverified" if bad else "agent")
                out = self.run_tool(tc.function.name, args, idx); outputs.append(out)
                self.log(kind="tool", bearing=b, idx=idx, tool=tc.function.name, args=args, output=out)
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(out, default=str)})
        d = {"bearing": b, "status": "escalate", "suspected_fault": "unknown", "recommended_action": "inspect_urgently",
             "confidence": 0.0, "rationale": "Step limit reached without a valid decision."}
        return self.finalize(b, idx, d, "fallback:max_steps", source="fallback")
