class MockBackend:
    """Deterministic CPU mock. This is not trained model inference."""
    name = "mock"

    def infer(self, evidence: dict) -> dict:
        return {
            "summary": "CPU deterministic rules / mock AI. No trained model or UGen300 inference.",
            "diagnoses": [{"finding_id": f["id"], "action_id": f["action_id"]}
                          for f in evidence["findings"]],
        }

