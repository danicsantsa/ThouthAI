VALID_SESSION_MODES = ("standard", "focus", "hyperfocus")


def normalize_session_mode(mode):
    """Normalize and validate a session mode value for the app and worker."""
    if mode is None:
        return "standard"
    normalized = str(mode).strip().lower().replace("-", "").replace(" ", "")
    aliases = {
        "standard": "standard",
        "default": "standard",
        "focus": "focus",
        "fokus": "focus",
        "fokusmodus": "focus",
        "hyperfocus": "hyperfocus",
        "hyperfokus": "hyperfocus",
        "hyperfocusmodus": "hyperfocus",
    }
    if normalized in aliases:
        return aliases[normalized]
    if normalized in VALID_SESSION_MODES:
        return normalized
    if normalized == "":
        return "standard"
    return "standard"


def evaluate_session_mode(mode, app_category=None, idle_seconds=None, app_name=None, allowed_app=None, phone_detected=False):
    """Return a structured focus-state decision for a session mode."""
    mode = normalize_session_mode(mode)
    base = {
        "mode": mode,
        "alert": False,
        "score": 100,
        "reason": None,
        "recommendation": "Laufend",
        "status": "normal",
        "soft_pause": False,
        "allowed_app": allowed_app,
        "phone_detected": phone_detected,
    }

    if mode == "standard":
        return base

    app_name_key = (app_name or "").lower()
    category = (app_category or "").lower()
    allowed_app_key = (allowed_app or "").strip().lower()

    if category in {"nicht-arbeit", "unbekannt", "unknown", "non-work", "nonwork"}:
        base["score"] -= 35
        base["reason"] = "Ablenkende App erkannt"
    if idle_seconds is not None and idle_seconds >= 30:
        base["score"] -= 20
        if base["reason"] is None:
            base["reason"] = "Längerer Leerlauf erkannt"
    for token in ("youtube", "netflix", "spotify", "discord", "steam", "instagram", "tiktok"):
        if token in app_name_key:
            base["score"] -= 25
            base["reason"] = "Ablenkungsquelle erkannt"
            break

    if mode == "focus":
        base["recommendation"] = "Bitte kurz zurück zur Arbeit kommen."
    elif mode == "hyperfocus":
        if allowed_app_key:
            app_matches = allowed_app_key in app_name_key or any(token in app_name_key for token in allowed_app_key.split())
            if not app_matches:
                base["score"] -= 70
                base["reason"] = f"Hyperfocus: Nur '{allowed_app_key}' ist erlaubt."
                base["alert"] = True
                base["soft_pause"] = True
                base["recommendation"] = "Hyperfocus aktiv: Kehre sofort zur erlaubten App zurück."
        base["score"] -= 10
        base["recommendation"] = "Hyperfocus aktiv: Nur die ausgewählte App bleibt zugelassen."

    if phone_detected:
        base["score"] -= 30
        base["alert"] = True
        base["soft_pause"] = True
        base["reason"] = "Handy-/Mobilnutzung erkannt"
        base["recommendation"] = "Hyperfocus aktiv: Handy-Nutzung erkannt. Bitte wieder zur Arbeit kommen."

    if base["score"] < 60:
        base["alert"] = True

    if base["alert"] and mode == "focus":
        base["status"] = "warning"
    elif base["alert"] and mode == "hyperfocus":
        base["status"] = "critical"
        base["soft_pause"] = True
    elif mode == "focus":
        base["status"] = "normal"
    elif mode == "hyperfocus":
        base["status"] = "warning"

    return base
