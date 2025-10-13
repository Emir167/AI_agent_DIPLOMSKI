# services/planner.py
import os
import textwrap
from ai_providers.groq_provider import GroqProvider
from ai_providers.local_stub import LocalStub

# ------------------------
# Provider
# ------------------------
def _get_provider():
    if os.getenv("GROQ_API_KEY"):
        try:
            return GroqProvider(model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
        except Exception:
            pass
    return LocalStub()

def _chat(system: str, user: str) -> str:
    prov = _get_provider()
    try:
        return prov._chat(system, user)
    except Exception:
        # Minimalan fallback (da UI ne pukne ako padne mreža/limit)
        return (
            "Tehnika učenja: Fokus blokovi (45/10) — duži fokus + kratke pauze.\n\n"
            "Dnevni plan (primer):\n"
            "- 13:00–13:45 Učenje\n- 13:45–13:55 Pauza\n- 13:55–14:40 Učenje\n"
            "- ... (nastavi po istom obrascu do ciljnih minuta)\n\n"
            "Preporuke: utišaj notifikacije, jednominutni reset daha, voda pri ruci, kratke šetnje.\n"
            "Motivacija: „Napredak, ne perfekcija.“"
        )

# ------------------------
# SYSTEM PROMPT (LLM vodi sve)
# ------------------------
SYSTEM_PLANNER = """\
You are a specialized study coach. ALWAYS reply in the SAME LANGUAGE as the user input.

HARD CONSTRAINTS (all must be satisfied):
- Exactly {days} days.
- All time ranges strictly within {start_time}–{end_time}.
- Total EFFECTIVE study time per day (learning + review, excluding breaks) must be {daily_min}±15 minutes.
- No overlapping or repeated time ranges; times strictly increase within a day.
- Breaks: 5–10 min; one longer 15–20 min break after ~4 focus blocks.
- If pages are mentioned, do NOT assign unrealistic chunks (keep realistic pace).
- If constraints are too tight, adapt content/coverage BUT NEVER violate the window, day count, or daily minutes.

OUTPUT (exact sections in this order, no extra chatter):
1) Tehnika učenja: <naziv> — <kratko zašto baš ta tehnika s obzirom na ciljeve i napomene>
2) Dnevni plan (za {days} dana):
   - Dan X ({start_time}–{end_time}):
     - <HH:MM–HH:MM> · Učenje/Obnavljanje/Vežbanje (+ ako ima strana, navedite realan raspon)
     - ... (pauze 5–10 min; posle ~4 blokova 15–20 min)
     - Ukupno efektivno: ~{daily_min} min
3) Preporuke za fokus/koncentraciju (3–5 kratkih, praktičnih saveta prilagođenih napomenama)
4) Motivacioni citat (jedna rečenica)

VALIDATION (do it silently before you answer):
- [✔] Exactly {days} days
- [✔] All times within {start_time}–{end_time}
- [✔] No overlaps; strictly increasing times
- [✔] Daily effective minutes = {daily_min}±15
- [✔] Realistic pages per block if pages are mentioned
"""

# ------------------------
# USER PROMPT (kompaktan)
# ------------------------
def _build_user_prompt(profile: dict, ask: str) -> str:
    level        = (profile.get("level") or "Undergraduate").strip()
    style        = (profile.get("learning_style") or "mixed").strip()
    goals        = (profile.get("goals") or "").strip()
    notes        = (profile.get("notes") or "").strip()
    start_time   = (profile.get("start_time") or "13:00").strip()
    end_time     = (profile.get("end_time") or "03:00").strip()
    daily_min    = int(profile.get("daily_minutes") or 360)
    days         = int(profile.get("days") or 10)

    return textwrap.dedent(f"""\
        PROFIL:
        - Nivo: {level}
        - Stil učenja: {style}
        - Ciljevi: {goals}
        - Napomene: {notes}

        ZAHTEV:
        {ask}

        PARAMETRI:
        - Broj dana: {days}
        - Dnevno efektivno učenje: {daily_min} min (±15)
        - Prozor učenja: {start_time}–{end_time}

        Upute:
        - Ne izmišljaj parametre koje nisam dao.
        - Drži se prozora i minuta; ako je potrebno, prilagodi sadržaj (ne minute).
        - Jasne stavke po vremenskim intervalima, bez tabela, bez suvišnog teksta.
    """)

# ------------------------
# Glavna funkcija (LLM radi sve)
# ------------------------
def generate_personal_plan(profile: dict, ask: str) -> str:
    start_time = (profile.get("start_time") or "13:00").strip()
    end_time   = (profile.get("end_time") or "03:00").strip()
    daily_min  = int(profile.get("daily_minutes") or 360)
    days       = int(profile.get("days") or 10)

    system = SYSTEM_PLANNER.format(
        days=days,
        start_time=start_time,
        end_time=end_time,
        daily_min=daily_min,
    )
    user = _build_user_prompt(profile, ask)
    return _chat(system, user)
