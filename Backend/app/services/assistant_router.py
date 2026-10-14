"""Deterministic, testable intent routing for Kenneth.

Routing does not query the database or call the LLM. It only identifies the
requested operation and resolves explicit conversational references.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import get_close_matches
from dataclasses import dataclass

MONTH_NAMES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5,
    "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9,
    "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
MONTH_LABELS = {number: name for name, number in MONTH_NAMES.items()}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    words = text.split()
    spelling = {
        "meyor": "mejor", "mejro": "mejor", "vendio": "vendio",
        "clietne": "cliente", "produtco": "producto", "ventaz": "ventas",
    }
    vocabulary = {"venta", "ventas", "producto", "productos", "cliente", "clientes",
                  "compras", "comprar", "mejor", "junio", "febrero"}
    normalized_words = []
    for word in words:
        if word in spelling:
            normalized_words.append(spelling[word])
        elif len(word) >= 5 and word not in vocabulary:
            candidates = get_close_matches(word, vocabulary, n=1, cutoff=0.86)
            normalized_words.append(candidates[0] if candidates and candidates[0][0] == word[0] else word)
        else:
            normalized_words.append(word)
    return " ".join(normalized_words)


def months_in(text: str) -> list[int]:
    tokens = normalize(text).split()
    return list(dict.fromkeys(MONTH_NAMES[token] for token in tokens if token in MONTH_NAMES))


def _user_messages(history: list[dict] | None) -> list[str]:
    messages = []
    for entry in (history or [])[-16:]:
        if (entry.get("role") or entry.get("from")) not in ("user", "usuario"):
            continue
        content = str(entry.get("content") or entry.get("text") or "").strip()
        if content:
            messages.append(content)
    return messages


def _is_greeting(normalized: str) -> bool:
    if normalized in {"hola", "holi", "buenas", "hey", "hello",
                      "buenos dias", "buenas tardes", "buenas noches",
                      "gracias", "muchas gracias", "perfecto gracias"}:
        return True
    parts = normalized.split()
    return (len(parts) == 2 and parts[0] in {"hola", "holi", "buenas", "hey"}
            and parts[1] in {"kenneth", "keneth", "kenteh", "kent", "kennet"})


def _context_months(history: list[dict] | None, *, wanted: int) -> list[int]:
    """Use recent *user* analytical turns, not old assistant summaries."""
    result = []
    for previous in reversed(_user_messages(history)[-6:]):
        norm = normalize(previous)
        if _is_greeting(norm) or any(term in norm for term in ("predic", "pronostic", "anomalia")):
            break
        # Do not borrow periods from a different business topic.
        if not any(term in norm for term in ("venta", "mes", "diferencia", "producto",
                                              "junio", "febrero", "enero", "marzo",
                                              "abril", "mayo", "julio", "agosto",
                                              "septiembre", "octubre", "noviembre", "diciembre")):
            break
        for month in reversed(months_in(previous)):
            if month not in result:
                result.insert(0, month)
        if len(result) >= wanted:
            break
    return result


def _last_year(question: str, history: list[dict] | None) -> int | None:
    current = re.search(r"\b(20\d{2})\b", normalize(question))
    if current:
        return int(current.group(1))
    for previous in reversed(_user_messages(history)[-6:]):
        if _is_greeting(normalize(previous)):
            break
        if months_in(previous):
            match = re.search(r"\b(20\d{2})\b", normalize(previous))
            if match:
                return int(match.group(1))
    return None


def _metric(text: str) -> str:
    words = set(text.split())
    if ("unidades" in words or "unidad" in words or "cantidad de productos" in text
            or "cuantos productos" in text):
        return "units"
    if ("cuantas ventas" in text or "cuantos pedidos" in text or
            "numero de ventas" in text or "cantidad de ventas" in text or
            "transacciones" in words):
        return "count"
    return "amount"


@dataclass(frozen=True)
class Intent:
    kind: str
    metric: str = "amount"
    months: tuple[int, ...] = ()
    year: int | None = None
    resolved_question: str = ""
    limit: int = 1


def _rank_limit(text: str, plural: bool) -> int:
    match = re.search(r"\b(?:top|primeros?|primeras?|mejores?|los|las)\s+(\d{1,2})\b", text)
    if match:
        return max(1, min(20, int(match.group(1))))
    return 5 if plural else 1


def route_request(question: str, history: list[dict] | None = None) -> Intent:
    """Classify the actual request before applying conversational context."""
    text = normalize(question)
    if _is_greeting(text):
        return Intent("conversation", resolved_question=question)

    direct_months = months_in(question)
    explicitly_mentions_year = bool(re.search(r"\b20\d{2}\b", text))
    elliptical = text.startswith(("y ", "ese ", "esa ", "esos ", "esas ", "del mismo "))
    year = (_last_year(question, history) if explicitly_mentions_year or elliptical or not direct_months else None)
    metric = _metric(text)
    product = any(term in text.split() for term in ("producto", "productos", "articulo",
                                                     "articulos", "item", "items"))
    customer = any(term in text.split() for term in ("cliente", "clientes", "comprador",
                                                      "compradores"))
    compare = any(term in text for term in ("diferencia", "compar", "variacion",
                                             "entre los dos", "entre ambos", "frente a",
                                             " vs ", "versus", "contra", "respecto a"))
    ranking = any(term in text for term in ("mas vendido", "mejor", "mayor", "top",
                                             "ranking", "mas compra", "mas gasto",
                                             "mas ventas", "mas unidades", "mas dinero",
                                             "mas compro", "mas ha comprado", "estrella"))
    attribution = product and any(term in text for term in (
        "diferencia", "marco", "contribuy", "explica", "incremento", "aumento", "cambio",
    ))
    if attribution:
        previous_months = _context_months(history, wanted=2)
        months = direct_months[:]
        for month in previous_months:
            if month not in months:
                months.append(month)
        if len(months) == 2:
            m1, m2 = months
            resolved = f"{question}\nCompara las ventas por producto entre {MONTH_LABELS[m1]} y {MONTH_LABELS[m2]}."
        else:
            resolved = question
        return Intent("product_attribution", "amount", tuple(months), year, resolved)

    if product and ranking:
        months = direct_months or (_context_months(history, wanted=1) if "ese mes" in text else [])
        return Intent("product_top", "amount" if "ingreso" in text or "dinero" in text or "importe" in text else "units",
                      tuple(months), year, question, _rank_limit(text, "productos" in text.split()))

    if customer and ranking:
        return Intent("customer_top", "count" if "frecuent" in text or "veces" in text or "mas compras" in text else "amount",
                      tuple(direct_months), year, question, _rank_limit(text, "clientes" in text.split()))

    if any(term in text for term in ("predic", "pronostic", "proyeccion", "forecast")):
        return Intent("forecast", resolved_question=question)
    if any(term in text for term in ("anomalia", "anomalo", "atipico", "inusual", "outlier")):
        return Intent("anomaly", resolved_question=question)

    # A short "¿y en febrero?" inherits the previous *type of analysis*,
    # never the preceding result. This preserves units, money and entity type.
    if direct_months and elliptical and not product and not customer:
        for previous in reversed(_user_messages(history)[-6:]):
            previous_text = normalize(previous)
            if _is_greeting(previous_text):
                break
            previous_intent = route_request(previous, [])
            if previous_intent.kind in {"monthly_total", "product_top", "customer_top"}:
                return Intent(previous_intent.kind, previous_intent.metric,
                              tuple(direct_months), year, question,
                              previous_intent.limit)
            if previous_intent.kind in {"forecast", "anomaly"}:
                break

    sales = any(term in text for term in ("venta", "vendido", "facturacion", "ingreso"))
    if compare and not product and not customer:
        months = direct_months[:]
        if len(months) < 2:
            for month in _context_months(history, wanted=2):
                if month not in months:
                    months.append(month)
        if len(months) == 2:
            return Intent("monthly_compare", metric, tuple(months), year, question)

    if sales and len(direct_months) == 1 and not product and not customer:
        return Intent("monthly_total", metric, tuple(direct_months), year, question)

    return Intent("sql", metric, tuple(direct_months), year, question)
