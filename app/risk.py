OFFSHORE_JURISDICTIONS = {
    "bvi",
    "british virgin islands",
    "cayman",
    "cayman islands",
    "panama",
    "seychelles",
    "mauritius",
    "isle of man",
    "jersey",
    "guernsey",
}

KEYWORDS = {
    "pep": ("PEP exposure", 2),
    "politically exposed": ("PEP exposure", 2),
    "sanction": ("Sanctions mention", 2),
    "crypto": ("Crypto payment", 2),
    "cash": ("Cash-heavy activity", 1),
    "shell": ("Shell company indicator", 2),
    "offshore": ("Offshore mention", 2),
}


def calculate_risk(entity_type: str, jurisdiction: str | None, original_text: str):
    score = 0
    flags = []

    text = original_text.lower()

    # 1. Unknown entity penalty
    if entity_type == "unknown":
        score += 1
        flags.append("Unknown entity type")

    # 2. Offshore jurisdiction
    if jurisdiction:
        j = jurisdiction.lower()
        if any(o in j for o in OFFSHORE_JURISDICTIONS):
            score += 3
            flags.append("Offshore jurisdiction")

    # 3. Keyword scanning
    for keyword, (flag, pts) in KEYWORDS.items():
        if keyword in text:
            score += pts
            if flag not in flags:
                flags.append(flag)

    if score > 10:
        score = 10

    return score, flags
