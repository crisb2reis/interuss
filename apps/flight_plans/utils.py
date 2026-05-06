# utils.py (novo arquivo)
def extract_subscription_id(ref: dict, result: dict) -> str:
    sub_id = ref.get("subscription_id")
    if not sub_id:
        subscribers = result.get("subscribers", [])
        sub_id = subscribers[0].get("subscription_id", "") if subscribers else ""
    return sub_id


def build_dss_oir_payload(oir_id, extents, uss_base_url, state, ovns) -> dict:
    return dict(
        oir_id=oir_id,
        extents=extents,
        uss_base_url=uss_base_url,
        state=state,
        key=ovns or None,
        new_subscription={
            "uss_base_url": uss_base_url,
            "notify_for_operational_intents": True,
            "notify_for_constraints": True,
        },
    )