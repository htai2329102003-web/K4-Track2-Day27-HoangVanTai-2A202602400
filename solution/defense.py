"""
Your defense. Implement register(ctx) and a handler per event type.
See ../README.md for the full interface + toolkit reference, and
../RULES.md before you start.
"""
from api import Verdict


def _result_or_none(result):
    """Treat failed/early toolkit lookups as unavailable, not as faults."""
    if not isinstance(result, dict) or "error" in result:
        return None
    return result


def _verdict(alert, pillar, reasons):
    return Verdict(
        alert=bool(alert),
        confidence=0.9 if alert else 0.8,
        reason=", ".join(reasons) if reasons else "within monitored limits",
        pillar=pillar,
    )


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def check_data_batch(payload, ctx):
    profile = _result_or_none(ctx.tools.batch_profile(payload["batch_id"]))
    if profile is None:
        return _verdict(False, "checks", [])

    baseline = ctx.baseline
    reasons = []

    # The published limits are calibrated at roughly 3 sigma.  Slightly
    # tighter inner bands catch near-boundary faults while keeping the clean
    # two-sided false-positive rate modest.
    row_mid = (baseline["row_count_min"] + baseline["row_count_max"]) / 2.0
    row_half = (baseline["row_count_max"] - baseline["row_count_min"]) / 2.0
    row_margin = row_half
    if not row_mid - row_margin <= profile["row_count"] <= row_mid + row_margin:
        reasons.append("row count anomaly")

    amount_mid = (baseline["mean_amount_min"] + baseline["mean_amount_max"]) / 2.0
    amount_half = (baseline["mean_amount_max"] - baseline["mean_amount_min"]) / 2.0
    amount_margin = amount_half * 0.5
    if not amount_mid - amount_margin <= profile["mean_amount"] <= amount_mid + amount_margin:
        reasons.append("amount distribution shift")

    null_rate = profile.get("null_rate", {}).get("customer_id", 0.0)
    if null_rate > baseline["null_rate_max"] * 0.7:
        reasons.append("customer id null spike")
    if profile["staleness_min"] > baseline["staleness_min_max"] * 0.7:
        reasons.append("batch freshness lag")

    return _verdict(reasons, "checks", reasons)


def check_contract_checkpoint(payload, ctx):
    diff = _result_or_none(ctx.tools.contract_diff(
        payload["contract_id"], payload["checkpoint_batch_id"]
    ))
    if diff is None:
        return _verdict(False, "contracts", [])

    reasons = list(diff.get("violations", []))
    if diff["freshness_delay_min"] > ctx.baseline["freshness_delay_max_min"]:
        reasons.append("contract freshness SLA risk")
    return _verdict(reasons, "contracts", reasons)


def check_lineage_run(payload, ctx):
    graph = _result_or_none(ctx.tools.lineage_graph_slice(payload["run_id"]))
    if graph is None:
        return _verdict(False, "lineage", [])

    reasons = []
    if len(graph.get("actual_upstream", [])) < 2:
        reasons.append("missing upstream lineage")
    if graph.get("actual_downstream_count", 0) <= 0:
        reasons.append("orphan output")
    if graph["duration_ms"] > ctx.baseline["lineage_duration_ms_max"] * 0.85:
        reasons.append("runtime anomaly")
    return _verdict(reasons, "lineage", reasons)


def check_feature_materialization(payload, ctx):
    drift = _result_or_none(ctx.tools.feature_drift(
        payload["feature_view"], payload["batch_id"]
    ))
    if drift is None:
        return _verdict(False, "ai_infra", [])

    reasons = []
    if drift["mean_shift_sigma"] > ctx.baseline["feature_mean_shift_sigma_max"]:
        reasons.append("training-serving feature skew")
    return _verdict(reasons, "ai_infra", reasons)


def check_embedding_batch(payload, ctx):
    drift = _result_or_none(ctx.tools.embedding_drift(
        payload["corpus"], payload["chunk_batch_id"]
    ))
    if drift is None:
        return _verdict(False, "ai_infra", [])

    reasons = []
    if drift["centroid_shift"] > ctx.baseline["embedding_centroid_shift_max"] * 0.7:
        reasons.append("embedding centroid drift")
    if drift["avg_doc_age_days"] > ctx.baseline["corpus_avg_doc_age_days_max"] * 0.7:
        reasons.append("corpus staleness")
    return _verdict(reasons, "ai_infra", reasons)
