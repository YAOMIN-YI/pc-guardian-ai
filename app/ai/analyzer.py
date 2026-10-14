from copy import deepcopy
from app.diagnosis import diagnose
from .mock_backend import MockBackend


def validate_output(output: object, findings: list[dict]) -> dict:
    """Reject schema drift, arbitrary commands, fabricated findings/actions."""
    if not isinstance(output, dict) or set(output) != {"summary", "diagnoses"}:
        raise ValueError("Backend must return only summary and diagnoses")
    if not isinstance(output["summary"], str) or len(output["summary"]) > 2000:
        raise ValueError("Invalid backend summary")
    rows = output["diagnoses"]
    if not isinstance(rows, list) or len(rows) > len(findings):
        raise ValueError("Invalid backend diagnoses")
    allowed = {f["id"]: f["action_id"] for f in findings}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"finding_id", "action_id"}:
            raise ValueError("Invalid diagnosis schema")
        fid, action = row["finding_id"], row["action_id"]
        if not isinstance(fid, str) or fid not in allowed or fid in seen:
            raise ValueError("Unknown or duplicate finding")
        if action is not None and (action != "start_print_spooler" or action != allowed[fid]):
            raise ValueError("Action is not supported by trusted evidence")
        seen.add(fid)
    return output


class Analyzer:
    def __init__(self, backend=None):
        self.backend = backend or MockBackend()

    def analyze(self, snapshot: dict) -> tuple[list[dict], dict]:
        findings = diagnose(snapshot)
        info = {"name": self.backend.name, "hardware_validated": False,
                "trained_model_inference": False, "status": "ok"}
        try:
            # Supply only minimal canonical evidence, not raw event text or host identifiers.
            output = self.backend.infer({"findings": deepcopy(findings)})
            info["output"] = validate_output(output, findings)
        except Exception as exc:
            info.update(status="rejected", error=f"{type(exc).__name__}: {exc}")
        # Backend text is advisory. Trusted rules retain exclusive action eligibility.
        return findings, info

