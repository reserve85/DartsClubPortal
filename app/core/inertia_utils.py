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


# --- Django forms -> React form fields --------------------------------------
#
# Every classic Django form (matchday, penalty, catalog, team, season, user,
# invite ...) is described as a list of plain field dicts; the React component
# ``FormFields`` renders them with Mantine. Validation stays 100 % in Django.


def _field_kind(field, widget) -> str:
    from django import forms

    if isinstance(widget, forms.HiddenInput):
        return "hidden"
    if isinstance(field, forms.BooleanField) or isinstance(widget, forms.CheckboxInput):
        return "switch"
    if isinstance(field, forms.MultipleChoiceField | forms.ModelMultipleChoiceField):
        return "multiselect"
    if isinstance(field, forms.ChoiceField | forms.ModelChoiceField):
        return "radio" if isinstance(widget, forms.RadioSelect) else "select"
    if isinstance(field, forms.DateTimeField):
        return "datetime"
    if isinstance(field, forms.DateField):
        return "date"
    if isinstance(field, forms.TimeField):
        return "time"
    if isinstance(field, forms.IntegerField | forms.DecimalField | forms.FloatField):
        return "number"
    if isinstance(field, forms.FileField):
        return "file"
    if isinstance(field, forms.EmailField):
        return "email"
    if isinstance(widget, forms.PasswordInput):
        return "password"
    if isinstance(widget, forms.Textarea):
        return "textarea"
    return "text"


def _field_value(bound, kind):
    import datetime
    from decimal import Decimal

    value = bound.value()
    if kind == "switch":
        return bool(value) and value not in ("false", "False", "0", "off")
    if kind == "multiselect":
        return [str(v.pk if hasattr(v, "pk") else v) for v in (value or [])]
    if kind in ("select", "radio"):
        if value is None:
            return ""
        return str(value.pk if hasattr(value, "pk") else value)
    if kind == "number":
        if value in (None, ""):
            return None
        try:
            number = Decimal(str(value).replace(",", "."))
        except ArithmeticError:
            return None
        return int(number) if number == number.to_integral_value() else float(number)
    if kind in ("date", "datetime", "time"):
        if isinstance(value, datetime.datetime | datetime.date):
            return value.isoformat()
        if isinstance(value, datetime.time):
            return value.strftime("%H:%M")
        return str(value or "")
    if kind == "file":
        return None
    return "" if value is None else str(value)


def _number_limits(field, widget) -> dict:
    from django.core import validators

    out = {}
    attrs = widget.attrs or {}
    for key in ("min", "max", "step"):
        if attrs.get(key) not in (None, ""):
            out[key] = float(attrs[key])
    for v in field.validators:
        if isinstance(v, validators.MinValueValidator) and "min" not in out:
            out["min"] = float(v.limit_value)
        if isinstance(v, validators.MaxValueValidator) and "max" not in out:
            out["max"] = float(v.limit_value)
    places = getattr(field, "decimal_places", None)
    if places is not None:
        out["decimals"] = places
    elif _is_integer(field):
        out["decimals"] = 0
    return out


def _is_integer(field) -> bool:
    from django import forms

    return isinstance(field, forms.IntegerField)


def _plain_help(text) -> str:
    """Help text as plain text: lists become "a · b", links (e.g. allauth's
    "forgot password" hint next to the field) are dropped - the pages show
    those actions as real buttons/links."""
    import re

    from django.utils.html import strip_tags

    text = str(text or "")
    if "<a " in text:
        return ""
    items = re.findall(r"<li>(.*?)</li>", text, flags=re.DOTALL)
    if items:
        return " · ".join(strip_tags(i).strip() for i in items)
    return " ".join(strip_tags(text).split())


def form_schema(form, exclude=()) -> list[dict]:
    """Describe every field of a Django form for the React ``FormFields``."""
    fields = []
    for bound in form:
        if bound.name in exclude:
            continue
        field, widget = bound.field, bound.field.widget
        kind = _field_kind(field, widget)
        item = {
            "name": bound.name,
            "type": kind,
            "label": str(bound.label or ""),
            "help": _plain_help(field.help_text),
            "required": bool(field.required) and kind != "switch",
            "disabled": bool(field.disabled),
            "value": _field_value(bound, kind),
            "error": " ".join(str(e) for e in bound.errors),
        }
        attrs = widget.attrs or {}
        if attrs.get("placeholder"):
            item["placeholder"] = str(attrs["placeholder"])
        if attrs.get("autocomplete"):
            item["autocomplete"] = str(attrs["autocomplete"])
        if kind == "text" and getattr(widget, "input_type", "") == "email":
            item["type"] = "email"
        if getattr(field, "max_length", None):
            item["maxLength"] = field.max_length
        if kind in ("select", "multiselect", "radio"):
            item["choices"] = [
                {"value": str(value), "label": str(label)}
                for value, label in field.choices
                if value not in ("", None)
            ]
        if kind == "number":
            item.update(_number_limits(field, widget))
        if kind in ("date", "datetime") and attrs.get("max"):
            item["max"] = str(attrs["max"])
        if kind in ("date", "datetime") and attrs.get("min"):
            item["min"] = str(attrs["min"])
        fields.append(item)
    return fields


class InertiaFormMixin:
    """For Create/Update/FormViews: render the form as the React ``Common/Form`` page.

    Subclasses add page texts via ``form_page_props(form)`` (title, subtitle,
    submitLabel, cancelUrl, deleteUrl, rows ...). Invalid posts render the
    same page again with the field errors filled in.
    """

    inertia_component = "Common/Form"

    def form_page_props(self, form) -> dict:
        return {}

    def render_to_response(self, context, **response_kwargs):
        from inertia import render as inertia_render

        form = context["form"]
        props = {
            "fields": form_schema(form),
            "errors": form_errors(form) if form.is_bound else {},
            "action": self.request.get_full_path(),
            **self.form_page_props(form),
        }
        return inertia_render(
            self.request, self.inertia_component, props=props, template_data=context
        )
