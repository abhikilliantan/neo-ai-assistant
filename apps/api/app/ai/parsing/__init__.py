"""Subprocess parse-isolation package (ADR 0003).

Intentionally EMPTY of imports so `python -m app.ai.parsing.child` pulls in only
stdlib + the child modules, never the app/DB/event loop. The parent-side harness
is imported explicitly from `app.ai.parsing.harness`.
"""
