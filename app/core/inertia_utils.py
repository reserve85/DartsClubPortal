"""Helpers shared by all Inertia views."""

import json


def form_errors(form) -> dict:
    """Django form errors -> {field: "message", "form": "non-field message"}."""
    out = {}
    for field, errs in form.errors.items():
        out["form" if field == "__all__" else field] = " ".join(str(e) for e in errs)
    return out


def request_data(request):
    """Form data of a POST (JSON posts are converted by InertiaJsonFormMiddleware)."""
    return request.POST


class InertiaJsonFormMiddleware:
    """Inertia sends forms as JSON; Django views read ``request.POST``.

    For JSON POSTs of the React pages this fills ``request.POST`` with the
    same QueryDict a classic form would produce (lists -> repeated keys,
    booleans -> "true"/"false", null -> left out), so every existing view,
    form and permission check works unchanged.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.method == "POST"
            and request.content_type == "application/json"
            and request.headers.get("X-Inertia")
        ):
            from django.http import QueryDict
            from django.utils.datastructures import MultiValueDict

            try:
                data = json.loads(request.body or b"{}")
            except ValueError:
                data = {}
            qd = QueryDict(mutable=True)
            for key, value in (data or {}).items():
                if value is None:
                    continue
                if isinstance(value, list):
                    qd.setlist(key, [_scalar(v) for v in value if v is not None])
                elif isinstance(value, dict):
                    qd[key] = json.dumps(value)
                else:
                    qd[key] = _scalar(value)
            qd._mutable = False
            request._post = qd
            request._files = MultiValueDict()
        return self.get_response(request)


def _scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
