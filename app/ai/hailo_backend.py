class HailoBackend:
    """Integration contract only. Implement after driver/model/hardware validation.

    Future implementation: host-side HailoRT inference with a compatible compiled
    model. Return the same structured schema as MockBackend.infer. Never receive
    an executor, shell, or repair capability. Do not silently fall back to CPU.
    """
    name = "hailo-unavailable"

    def __init__(self):
        raise NotImplementedError(
            "UGen300/HailoRT adapter is not implemented or hardware-validated. Use --backend mock."
        )

