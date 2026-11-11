"""Explicit model-token pricing; no model-name or provider-fee inference."""

from __future__ import annotations

import json
import math
import re
from decimal import Decimal, InvalidOperation
from typing import Any

ModelPricing = dict[str, dict[str, float]]
RATE_FIELDS = {"input_usd_per_million", "output_usd_per_million"}
MODEL_NAME = re.compile(r"^[A-Za-z0-9_./:\-]{1,120}$")


def validate_model_pricing(value: Any) -> ModelPricing:
    if not isinstance(value, dict) or len(value) > 100:
        raise ValueError("Model pricing must map at most 100 model IDs to input/output rates.")
    normalized = {}
    for model, rates in value.items():
        if not isinstance(model, str) or MODEL_NAME.fullmatch(model) is None:
            raise ValueError("Model pricing contains an invalid model ID.")
        if not isinstance(rates, dict) or set(rates) != RATE_FIELDS:
            raise ValueError(
                "Each model price requires only input_usd_per_million and output_usd_per_million."
            )
        validated = {}
        for field, rate in rates.items():
            try:
                valid = type(rate) in {int, float} and math.isfinite(rate) and rate >= 0
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError("Model pricing rates must be finite, nonnegative numbers.")
            validated[field] = float(rate)
        normalized[model] = validated
    return normalized


def parse_model_pricing_json(raw: str) -> ModelPricing:
    if len(raw) > 32000:
        raise ValueError("RILO_MODEL_PRICING_JSON exceeds the 32 KB limit.")
    try:
        value = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise ValueError(
            "RILO_MODEL_PRICING_JSON must contain a valid model-price object."
        ) from exc
    return validate_model_pricing(value)


def price_basis(model: str, pricing: ModelPricing, *, fixture: bool = False) -> dict:
    if fixture:
        return {"version": "model-token-pricing-v1", "status": "not_applicable"}
    rates = pricing.get(model)
    return {
        "version": "model-token-pricing-v1",
        "status": "configured" if rates is not None else "unknown",
        "requested_model": model,
        "currency": "USD",
        "unit": "per million reported input/output tokens",
        "rates": dict(rates) if rates is not None else None,
        "source": "explicit RILO_MODEL_PRICING_JSON configuration" if rates is not None else None,
        "model_match_policy": "exact response model or matching provider plus unqualified model; contradictory routing metadata rejected",
        "coverage": "model-token fees only; excludes search credits, hardware, energy, discounts, and external billing adjustments",
    }


def response_matches_requested_model(result: dict, requested: str) -> bool:
    actual = result.get("model")
    if not isinstance(actual, str):
        return False
    provider, separator, unqualified = requested.partition("/")
    if not separator:
        return actual == requested
    extra = result.get("extra_fields", {})
    if not isinstance(extra, dict):
        return False
    routing = extra.get("routing_info", {})
    if not isinstance(routing, dict):
        return False
    providers = [
        value for value in (extra.get("provider"), routing.get("provider")) if value is not None
    ]
    if providers and any(value != provider for value in providers):
        return False
    expected_models = {requested, unqualified}
    if actual not in expected_models or (actual != requested and not providers):
        return False
    for metadata, field in (
        (extra, "resolved_model_used"),
        (extra, "original_model_requested"),
        (routing, "model"),
        (routing, "requested_model"),
    ):
        if field in metadata and (
            not isinstance(metadata[field], str) or metadata[field] not in expected_models
        ):
            return False
    return "requested_provider" not in routing or routing["requested_provider"] == provider


def estimated_model_fee(basis: dict, input_tokens: int, output_tokens: int) -> float | None:
    if basis.get("status") != "configured":
        return None
    rates = basis.get("rates")
    try:
        validated = validate_model_pricing({basis["requested_model"]: rates})[
            basis["requested_model"]
        ]
        fee = (
            Decimal(input_tokens) * Decimal(str(validated["input_usd_per_million"]))
            + Decimal(output_tokens) * Decimal(str(validated["output_usd_per_million"]))
        ) / Decimal(1_000_000)
        amount = float(fee)
        return amount if math.isfinite(amount) else None
    except (KeyError, ValueError, OverflowError, InvalidOperation):
        return None
