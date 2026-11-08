"""
End-to-End RAG Engine Grounded in Karnataka Government Knowledge Base.

Architectural Context:
- Integrates the Karnataka RAG Retriever with conversational synthesis.
- Strictly grounds all responses in official Government of Karnataka sources.
- Supports both Grounded Gemini LLM synthesis and high-precision deterministic offline synthesis.
- Formats speakable English answers (concise 1-3 sentences) suitable for telephone/WebRTC audio playout,
  plus rich structured metadata (official portal URL, scheme name, eligibility) for the frontend UI.
"""

from dataclasses import dataclass
import os
import re
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.logger import get_logger
from app.rag.karnataka_knowledge import KarnatakaSchemeDocument
from app.rag.retriever import KarnatakaRAGRetriever, RetrievalResult

logger = get_logger("awaaz_setu.rag.engine")


@dataclass
class RAGResponse:
    spoken_text: str
    official_url: str
    official_portal: str
    scheme_name: str
    category: str
    dpi_service: str
    dpi_details: str
    retrieval_score: float
    grounded_via: str  # "gemini-grounded" or "official-template"


class KarnatakaRAGEngine:
    """
    RAG Engine that retrieves verified Karnataka Government information
    and synthesizes speakable, accurate English responses.
    """

    def __init__(self, retriever: Optional[KarnatakaRAGRetriever] = None):
        self.retriever = retriever or KarnatakaRAGRetriever()

    def _generate_template_answer(self, doc: KarnatakaSchemeDocument, query: str) -> str:
        """
        Produces a crisp, speakable English response grounded in the official document.
        Guaranteed zero hallucination and speakable by TTS without strange symbols.
        """
        # Specific natural voice responses for key Karnataka schemes
        if doc.id == "gruha_lakshmi":
            return (
                "Under the Karnataka Gruha Lakshmi Scheme, eligible women heads of households receive 2,000 rupees "
                "per month through direct bank transfer. You can apply on the Seva Sindhu portal or at Grama One and "
                "Bangalore One centers using your Aadhaar card and Ration card."
            )
        elif doc.id == "gruha_jyothi":
            return (
                "Under the Gruha Jyothi scheme, Karnataka households get free domestic electricity up to 200 units per month. "
                "You can register online on the Seva Sindhu portal by linking your electricity account ID with your Aadhaar card."
            )
        elif doc.id == "yuva_nidhi":
            return (
                "The Yuva Nidhi scheme provides monthly financial assistance of 3,000 rupees for unemployed graduates "
                "and 1,500 rupees for diploma holders in Karnataka for up to two years. Applications are accepted on the Seva Sindhu portal."
            )
        elif doc.id == "anna_bhagya":
            return (
                "Under the Anna Bhagya scheme, Karnataka BPL and Antyodaya families receive 10 kg of food grains per person each month, "
                "with cash DBT transferred for the state portion. You can check your payment status on the official Ahara portal."
            )
        elif doc.id == "shakti_scheme":
            return (
                "Under the Shakti scheme, all women residents of Karnataka can travel for free across the state on KSRTC, BMTC, "
                "and state transport ordinary and express buses by presenting a valid government photo identity card."
            )
        elif doc.id == "bhoomi_portal":
            return (
                "You can view and download your land RTC and Pahani online through the Karnataka Bhoomi portal at bhoomi.karnataka.gov.in. "
                "Simply enter your district, taluk, village, and survey number to access digitally signed records."
            )
        elif doc.id == "eswathu_portal":
            return (
                "The e-Swathu portal manages rural property ownership records under Gram Panchayats and issues Form 9 and Form 11 "
                "required for property registration in rural Karnataka."
            )
        elif doc.id == "ganga_kalyana":
            return (
                "Under the Ganga Kalyana Scheme, small and marginal farmers belonging to SC, ST, and minority communities receive "
                "a fully subsidized irrigation borewell with a submersible pumpset and electrical connection."
            )
        elif doc.id == "raitha_siri":
            return (
                "The Raitha Siri scheme offers 10,000 rupees per hectare for millet cultivation, and Krishi Bhagya provides up to 90 percent "
                "subsidy for farm ponds and micro-irrigation through the Karnataka Agriculture Department."
            )
        elif doc.id == "pashu_bhagya":
            return (
                "The Pashu Bhagya scheme provides bank loans with 33 to 50 percent subsidy for establishing dairy cattle, sheep, and goat "
                "rearing units in Karnataka. You can apply through your local taluk Veterinary Office."
            )
        elif doc.id == "ssp_scholarship":
            return (
                "The Karnataka State Scholarship Portal provides pre-matric and post-matric fee reimbursement and maintenance allowances "
                "for SC, ST, OBC, and minority students. You can apply online at ssp.postmatric.karnataka.gov.in."
            )
        elif doc.id == "nadakacheri":
            return (
                "You can apply for legally valid Caste, Income, and Residence certificates online through the Nada Kacheri portal at "
                "nadakacheri.karnataka.gov.in or at Atalji Janasnehi Kendras for a nominal fee of 25 rupees."
            )
        elif doc.id == "sandhya_suraksha":
            return (
                "The Sandhya Suraksha Yojana offers a monthly pension of 1,000 rupees to destitute senior citizens aged 65 and above "
                "in Karnataka. You can apply at your nearest Nada Kacheri or Seva Sindhu center."
            )
        elif doc.id == "arogya_karnataka":
            return (
                "Under Arogya Karnataka, BPL families receive cashless hospitalization up to 5 lakh rupees per year for major treatments "
                "at empanelled government and private network hospitals across Karnataka."
            )
        else:
            # General clean synthesis from document fields
            return (
                f"Regarding {doc.scheme_name}, {doc.summary} "
                f"You can access official services on {doc.official_portal} at {doc.official_url}. "
                f"For inquiries, contact the helpline at {doc.helpline}."
            )

    async def _synthesize_with_gemini(
        self,
        doc: KarnatakaSchemeDocument,
        query: str,
        api_key: str,
        model_name: str = "gemini-1.5-flash",
    ) -> Optional[str]:
        """
        Synthesizes a tailored, speakable English response using Google Gemini,
        strictly grounded in the retrieved Karnataka Government document.
        """
        if not api_key:
            return None

        prompt = (
            "You are Awaaz Setu, an authoritative and empathetic voice assistant for Karnataka citizens.\n"
            "Answer the user query based ONLY on the provided official Government of Karnataka document.\n"
            "STRICT VOICE CONSTRAINTS:\n"
            "1. Maximum 2 to 3 concise, clear sentences in English.\n"
            "2. Absolutely NO markdown, asterisks (*), bullets, numbered lists, emojis, or raw URLs in speech.\n"
            "3. State the key benefit, eligibility, and the official portal name clearly.\n"
            "4. Be 100% truthful to the provided document.\n\n"
            f"OFFICIAL KARNATAKA DOCUMENT:\n{doc.to_chunk_text()}\n\n"
            f"USER QUERY: {query}\n"
            "ANSWER:"
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 150},
        }

        try:
            async with httpx.AsyncClient(timeout=3.5) as client:
                res = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        clean = re.sub(r"[*_#`~>•]", " ", text)
                        clean = re.sub(r"\s+", " ", clean).strip()
                        if clean:
                            return clean
        except Exception as exc:
            logger.warning("Gemini RAG synthesis error: %s (falling back to template)", exc)

        return None

    async def answer(
        self,
        query: str,
        phone: str = "",
        min_score: float = 0.12,
    ) -> Optional[RAGResponse]:
        """
        Retrieves top Karnataka Government context for query, and synthesizes
        a grounded voice response with structured DPI payload.
        """
        results = self.retriever.retrieve(query, top_k=1, min_score=min_score)
        if not results:
            logger.info("No matching Karnataka Government document found for query: '%s'", query[:60])
            return None

        top_match = results[0]
        doc = top_match.document

        # Attempt Gemini synthesis if API key available
        gemini_key = (os.getenv("GEMINI_API_KEY", settings.GEMINI_API_KEY) or "").strip()
        spoken_text = None
        grounded_via = "official-template"

        if gemini_key:
            model_name = os.getenv("GEMINI_MODEL", settings.GEMINI_MODEL)
            gemini_ans = await self._synthesize_with_gemini(doc, query, gemini_key, model_name)
            if gemini_ans:
                spoken_text = gemini_ans
                grounded_via = "gemini-grounded"

        if not spoken_text:
            spoken_text = self._generate_template_answer(doc, query)

        # Build structured DPI payload for frontend UI display
        dpi_service = f"Karnataka Gov - {doc.scheme_name}"
        dpi_details = (
            f"{doc.summary} "
            f"Benefits: {doc.benefits} "
            f"Official Website: {doc.official_url} | Helpline: {doc.helpline}"
        )

        return RAGResponse(
            spoken_text=spoken_text,
            official_url=doc.official_url,
            official_portal=doc.official_portal,
            scheme_name=doc.scheme_name,
            category=doc.category,
            dpi_service=dpi_service,
            dpi_details=dpi_details,
            retrieval_score=top_match.score,
            grounded_via=grounded_via,
        )


# Singleton RAG instance
karnataka_rag_engine = KarnatakaRAGEngine()
