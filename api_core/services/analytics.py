from __future__ import annotations


FINANCIAL_KEYWORDS = {
    "positive": ["tavan", "yükseliş", "alım", "rekor", "kar", "büyüme", "temettü", "pozitif", "destek", "hedef", "bullish", "buy", "profit", "growth", "dividend"],
    "negative": ["taban", "düşüş", "satış", "zarar", "negatif", "direnç", "risk", "ayı", "bearish", "sell", "loss", "warning", "crash"],
}


def analyze_sentiment(text_list: list[str]) -> dict[str, object]:
    if not text_list:
        return {"score": 0, "label": "NEUTRAL", "confidence": 0}

    total_score = 0
    mentions = 0
    for text in text_list:
        normalized = text.lower()
        pos = sum(1 for word in FINANCIAL_KEYWORDS["positive"] if word in normalized)
        neg = sum(1 for word in FINANCIAL_KEYWORDS["negative"] if word in normalized)
        total_score += pos - neg
        mentions += pos + neg

    score = round(total_score / len(text_list), 2)
    label = "BULLISH" if score > 0.1 else ("BEARISH" if score < -0.1 else "NEUTRAL")
    return {
        "score": score,
        "label": label,
        "mentions_detected": mentions,
        "sample_count": len(text_list),
    }
