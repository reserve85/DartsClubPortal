"""Helpers shared by all Inertia views."""

import json


def form_errors(form) -> dict:
    """Django form errors -> {field: "message", "form": "non-field message"}."""
    out = {}
    for field, errs in form.errors.items():
        out["form" if field == "__all__" else field] = " ".join(str(e) for e in errs)
    return out


def request_data(request) -> dict:
    """Form data of a POST: classic form fields or Inertia's JSON body.

    JSON is flattened to strings the way Django forms expect them
    (lists -> "a, b", booleans -> "True" / "", null -> "").
    """
    if request.POST:
        return request.POST
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return {}
    out = {}
    for key, value in data.items():
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value)
        elif isinstance(value, bool):
            value = "True" if value else ""
        out[key] = "" if value is None else str(value)
    return out
