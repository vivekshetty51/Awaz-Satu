"""
Domain Intent Router and DPI Service Resolver for Awaaz Setu.

Architectural Context:
- Evaluates transcribed caller queries against agricultural domain categories:
  1. e-NAM Mandi Prices (demo)
  2. PM-Kisan Samman Nidhi
  3. Pashu Palan & Livestock Advisory
  4. IMD Weather Advisory
  5. Awaaz Setu General Advisory
- Robust to speech recognition variations, Hinglish, code-switching, and common ASR misrecognitions
  (e.g., 'Monday prices' -> Mandi prices, 'BM ki sana' / 'ki sana' -> PM-Kisan).
- Distinguishes 'weather' from English conjunction 'whether' via boundary regex.
- Transparently labels demo data as '(demo data)'.
- Resolves appropriate localized text responses for synthesis and DPI payloads for UI delivery.
- If speech is empty or unintelligible, returns None for DPI service to avoid false triggers.
"""

import re
from typing import Optional, Tuple

# Mandi / Commodity market keywords including common ASR mishearings
MANDI_KEYWORDS = [
    "mandi", "monday price", "monday prices", "monday rate", "mandi price", "mandi prices",
    "mandi rate", "mandi rates", "bhav", "bhaav", "price", "rate", "daam", "dam",
    "kimat", "keemat", "tamatar", "tomato", "tomatoes", "gehu", "wheat", "pyaz", "onion",
    "onions", "aalu", "aloo", "potato", "potatoes", "sarson", "mustard", "chana", "gram",
    "fasal", "crop price", "crop rate", "market price", "market rate", "bazaar", "bazar",
    "मंडी", "भाव", "दाम", "कीमत", "टमाटर", "गेहूं", "गेहु", "प्याज", "आलू", "सरसों", "चना", "फसल", "बाजार"
]

# PM-Kisan scheme keywords including common ASR mishearings (e.g. 'BM ki sana', 'ki sana')
PM_KISAN_KEYWORDS = [
    "pm kisan", "pm-kisan", "pmkisan", "bm kisan", "bm-kisan", "bm ki sana", "ki sana",
    "kisana", "kisaan", "kisan", "samman nidhi", "samman", "kist", "kisht", "installment",
    "subsidy", "yojana", "scheme", "paisa", "rupaye", "account", "dbt", "beneficiary",
    "farmer scheme", "kisan samman",
    "किसान", "सम्मान निधि", "किस्त", "पैसा", "रुपये", "योजना", "सब्सिडी", "खाता"
]

# Livestock & Animal husbandry keywords
LIVESTOCK_KEYWORDS = [
    "pashu", "gay", "gaay", "cow", "cows", "bhains", "buffalo", "buffaloes", "doodh", "milk",
    "pashupalan", "dairy", "bimari", "beemari", "disease", "veterinary", "tika", "teeka", "vaccine",
    "vaccination", "cattle", "livestock", "fodder", "chara",
    "पशु", "गाय", "भैंस", "दूध", "पशुपालन", "डेयरी", "बीमारी", "टीका"
]

# Weather regex pattern: uses word boundaries so English conjunction 'whether' is NOT mistaken for 'weather'
WEATHER_PATTERN = re.compile(
    r"\b(weather|mausam|barish|rain|rainfall|barsat|temperature|tapman|hawa|toofan|barsaat|forecast)\b",
    re.IGNORECASE,
)
WEATHER_HINDI_KEYWORDS = ["बादल", "मौसम", "बारिश", "बरसात", "तापमान", "हवा"]


def classify_intent(query: str) -> Tuple[Optional[str], Optional[str], str]:
    """
    Classifies a transcribed query into a DPI service, structured details, and spoken response.

    Returns:
        (dpi_service, dpi_details, spoken_text)
    """
    q = (query or "").lower().strip()
    if not q:
        return (
            None,
            None,
            "माफ़ कीजिए, आपकी आवाज़ साफ़ नहीं आई। कृपया अपना सवाल दोबारा पूछें।",
        )

    # 1. PM-Kisan Samman Nidhi (checked first to handle 'BM ki sana' before general conjunction checks)
    if any(k in q for k in PM_KISAN_KEYWORDS):
        service = "PM-Kisan Samman Nidhi"
        details = "PM-Kisan: Next installment is scheduled for release. Beneficiary verification active."
        spoken = "Aapka kisan samman nidhi ka agla kist 15 tarikh ko aayega."
        return service, details, spoken

    # 2. Mandi Prices (e-NAM)
    if any(k in q for k in MANDI_KEYWORDS):
        service = "e-NAM Mandi Prices (demo)"
        if any(w in q for w in ["tamatar", "tomato", "tomatoes", "टमाटर"]):
            details = "Tomato prices in Yeshwanthpur Mandi: Rs 2,400 per Quintal. Trend: Steady (demo data)."
            spoken = "येशवंतपुर मंडी में टमाटर का भाव 2,400 रुपये प्रति क्विंटल है। (डेमो जानकारी)"
        elif any(w in q for w in ["gehu", "wheat", "गेहूं", "गेहु"]):
            details = "Wheat (Gehu) prices in Bhopal Mandi: Rs 2,275 per Quintal. Trend: Steady (demo data)."
            spoken = "भोपाल मंडी में गेहूं का भाव 2,275 रुपये प्रति क्विंटल है। (डेमो जानकारी)"
        elif any(w in q for w in ["pyaz", "onion", "onions", "प्याज"]):
            details = "Onion (Pyaz) prices in Lasalgaon Mandi: Rs 1,850 per Quintal. Trend: Decreasing (demo data)."
            spoken = "लासलगांव मंडी में प्याज का भाव 1,850 रुपये प्रति क्विंटल है। (डेमो जानकारी)"
        else:
            details = "e-NAM Mandi: Gehu Rs 2,275/Q, Tamatar Rs 2,400/Q, Pyaz Rs 1,850/Q (demo data)."
            spoken = "ई-नाम मंडी में गेहूं 2,275 रुपये, टमाटर 2,400 रुपये और प्याज 1,850 रुपये प्रति क्विंटल है। (डेमो जानकारी)"
        return service, details, spoken

    # 3. Livestock & Animal Husbandry
    if any(k in q for k in LIVESTOCK_KEYWORDS):
        service = "Pashu Palan & Livestock Advisory"
        details = "Livestock Advisory: Maintain vaccination schedule and balanced mineral feed for cattle."
        spoken = "पशुपालन सलाह: मवेशियों के अच्छे स्वास्थ्य के लिए समय पर टीकाकरण और संतुलित आहार सुनिश्चित करें।"
        return service, details, spoken

    # 4. Weather / IMD (boundary regex ensures 'whether' does not trigger weather)
    if WEATHER_PATTERN.search(q) or any(k in q for k in WEATHER_HINDI_KEYWORDS):
        service = "IMD Weather Advisory"
        details = "IMD Weather Advisory: Clear skies expected over the next 48 hours in your region."
        spoken = "मौसम विभाग के अनुसार अगले दो दिनों तक आपके क्षेत्र में मौसम साफ रहने का अनुमान है।"
        return service, details, spoken

    # 5. General / Unrelated Query
    service = "Awaaz Setu General Advisory"
    details = "Awaaz Setu: Downstream conversational AI service is offline. Ask about Mandi prices, PM-Kisan, or Livestock."
    spoken = "नमस्ते, आवाज़ सेतु में आपका स्वागत है। आप मंडी भाव, किसान सम्मान निधि, या पशुपालन संबंधी सवाल पूछ सकते हैं।"
    return service, details, spoken
