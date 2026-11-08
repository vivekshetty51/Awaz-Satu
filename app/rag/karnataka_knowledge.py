"""
Karnataka Government Official Portals, Schemes, and Citizen Services Knowledge Base.

This module houses verified, authoritative facts directly sourced from official
Government of Karnataka websites (sevasindhu.karnataka.gov.in, bhoomi.karnataka.gov.in,
bescom.karnataka.gov.in, ksrtc.in, ahara.kar.nic.in, raitamitra.karnataka.gov.in,
ssp.karnataka.gov.in, dssp.karnataka.gov.in, nadakacheri.karnataka.gov.in, etc.).

Used by the Karnataka RAG pipeline to ground responses in authentic state data.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class KarnatakaSchemeDocument:
    id: str
    scheme_name: str
    category: str
    department: str
    official_portal: str
    official_url: str
    helpline: str
    summary: str
    benefits: str
    eligibility: str
    documents_required: str
    how_to_apply: str
    keywords: List[str] = field(default_factory=list)

    def to_chunk_text(self) -> str:
        """Serializes document into a rich text chunk for vector and keyword retrieval."""
        return (
            f"Scheme / Service: {self.scheme_name}\n"
            f"Category: {self.category}\n"
            f"Department: {self.department}\n"
            f"Official Website: {self.official_url} (Portal: {self.official_portal})\n"
            f"Helpline: {self.helpline}\n"
            f"Summary: {self.summary}\n"
            f"Benefits: {self.benefits}\n"
            f"Eligibility Criteria: {self.eligibility}\n"
            f"Documents Required: {self.documents_required}\n"
            f"Application Procedure: {self.how_to_apply}\n"
            f"Search Keywords: {', '.join(self.keywords)}"
        )


KARNATAKA_GOVERNMENT_DOCUMENTS: List[KarnatakaSchemeDocument] = [
    # -------------------------------------------------------------------------
    # 1. Gruha Lakshmi Scheme
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="gruha_lakshmi",
        scheme_name="Gruha Lakshmi Scheme",
        category="Welfare & Women Empowerment",
        department="Department of Women and Child Development, Government of Karnataka",
        official_portal="Seva Sindhu Karnataka",
        official_url="https://sevasindhu.karnataka.gov.in",
        helpline="1902 or 080-22279954",
        summary="Flagship Karnataka guarantee scheme providing ₹2,000 monthly financial assistance via DBT directly to woman head of each eligible household.",
        benefits="₹2,000 per month credited directly to the woman head's Aadhaar-linked bank account (DBT).",
        eligibility=(
            "Woman head of household (Yajamani) listed on BPL, Antyodaya (AAY), or APL ration cards in Karnataka. "
            "Neither the woman head nor her husband can be income tax payers or GST payers. Only one woman per household is eligible."
        ),
        documents_required="Woman head's Aadhaar card, husband's Aadhaar card, Ration card (AAY/BPL/APL), and Aadhaar-seeded active bank account.",
        how_to_apply=(
            "Apply online for free on sevasindhu.karnataka.gov.in or in person at Grama One (rural), Bangalore One (Bengaluru), "
            "or Karnataka One (urban) centers. Beneficiary receives an SMS confirmation with application acknowledgement."
        ),
        keywords=[
            "gruha lakshmi", "gruhalakshmi", "graha lakshmi", "2000 rupees", "2000 rs", "woman head",
            "women financial assistance", "dbt 2000", "yajamani", "guarantee scheme", "karnataka women scheme",
            "housewife money", "mother pension 2000"
        ],
    ),

    # -------------------------------------------------------------------------
    # 2. Gruha Jyothi Scheme
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="gruha_jyothi",
        scheme_name="Gruha Jyothi Scheme",
        category="Energy & Public Utilities",
        department="Energy Department, Government of Karnataka (BESCOM, MESCOM, HESCOM, GESCOM, CESC)",
        official_portal="Seva Sindhu & BESCOM",
        official_url="https://sevasindhu.karnataka.gov.in",
        helpline="1912 (24x7 Karnataka Electricity Consumer Helpline)",
        summary="Karnataka guarantee scheme providing free domestic electricity up to 200 units per month to all residential households in Karnataka.",
        benefits="Free electricity up to 200 units per month. Net zero electricity bill if monthly consumption stays within entitlement limit.",
        eligibility=(
            "All domestic/residential electricity consumers in Karnataka, including homeowners and registered tenants. "
            "Average monthly consumption of the previous 12 months plus 10% buffer is calculated (up to max 200 units). "
            "Commercial establishments and agricultural pump sets are excluded."
        ),
        documents_required="Electricity bill Consumer ID / Account ID, Consumer Aadhaar number, and linked mobile number.",
        how_to_apply=(
            "Register on sevasindhu.karnataka.gov.in under Gruha Jyothi registration. "
            "Link electricity meter Account ID with Aadhaar card. Can also register at Grama One, Bangalore One, or BESCOM/ESCOM sub-division offices."
        ),
        keywords=[
            "gruha jyothi", "gruhajyothi", "graha jyothi", "free electricity", "200 units free power",
            "electricity bill subsidy", "bescom free electricity", "mescom", "hescom", "gescom", "cesc",
            "power bill zero", "light bill karnataka", "1912"
        ],
    ),

    # -------------------------------------------------------------------------
    # 3. Yuva Nidhi Scheme
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="yuva_nidhi",
        scheme_name="Yuva Nidhi Scheme",
        category="Skill Development & Youth Employment",
        department="Department of Skill Development, Entrepreneurship and Livelihood, Karnataka",
        official_portal="Seva Sindhu Karnataka",
        official_url="https://sevasindhu.karnataka.gov.in",
        helpline="1902",
        summary="Unemployment monthly financial assistance of ₹3,000 for unemployed graduates and ₹1,500 for diploma holders in Karnataka.",
        benefits="₹3,000 per month for degree holders/graduates and ₹1,500 per month for diploma holders for up to 2 years or until employed.",
        eligibility=(
            "Domiciled residents of Karnataka who graduated or passed diploma in the academic year 2022-23 or later. "
            "Must have remained unemployed for at least 180 days (6 months) post results. "
            "Not pursuing higher education, not self-employed, not paying income tax, and not employed in private or government sectors."
        ),
        documents_required="Degree/Diploma marks card, Convocation/Provisional certificate, Aadhaar card, Karnataka domicile certificate (or 7 years Karnataka study certificate), and Aadhaar-linked bank account.",
        how_to_apply="Apply online via sevasindhu.karnataka.gov.in or through Grama One, Bangalore One, or Karnataka One centers with Aadhaar verification.",
        keywords=[
            "yuva nidhi", "yuvanidhi", "unemployment allowance", "unemployed graduate 3000", "diploma 1500",
            "graduate stipend", "karnataka youth scheme", "jobless allowance", "unemployment money", "degree stipend"
        ],
    ),

    # -------------------------------------------------------------------------
    # 4. Anna Bhagya Scheme
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="anna_bhagya",
        scheme_name="Anna Bhagya Scheme",
        category="Food & Civil Supplies",
        department="Department of Food, Civil Supplies and Consumer Affairs, Karnataka",
        official_portal="Ahara Karnataka Portal",
        official_url="https://ahara.kar.nic.in",
        helpline="1967 (Toll-Free PDS Helpline)",
        summary="Provides 10 kg of food grains per month per person for BPL and Antyodaya (AAY) ration cardholders in Karnataka, including cash DBT transfer.",
        benefits="5 kg food grain supplied by Central Govt plus ₹34 per kg cash transfer by Karnataka Govt for the remaining 5 kg (₹170 per person/month) credited via DBT.",
        eligibility="BPL (Priority Household) and Antyodaya Anna Yojana (AAY) ration cardholders residing in Karnataka with active Aadhaar-seeded bank accounts.",
        documents_required="Karnataka BPL/AAY Ration card, Aadhaar card of family members, and Aadhaar-seeded bank passbook.",
        how_to_apply=(
            "Automatic entitlement for eligible BPL/AAY cardholders. Cardholders can track DBT status and rice allotment on "
            "ahara.kar.nic.in under E-Services -> Status of DBT."
        ),
        keywords=[
            "anna bhagya", "annabhagya", "free rice", "10 kg rice", "170 rupees dbt", "ration card bpl",
            "antyodaya", "aay", "ahara portal", "rice money", "food subsidy karnataka", "pds karnataka"
        ],
    ),

    # -------------------------------------------------------------------------
    # 5. Shakti Scheme
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="shakti_scheme",
        scheme_name="Shakti Scheme",
        category="Transport & Mobility",
        department="Transport Department, Government of Karnataka (KSRTC, BMTC, NWKRTC, KKRTC)",
        official_portal="KSRTC Portal",
        official_url="https://ksrtc.in",
        helpline="080-22221321 or 080-49596666",
        summary="Free bus travel across Karnataka for all women residents in state-run RTC ordinary and express buses.",
        benefits="100% free bus travel within Karnataka borders on KSRTC, BMTC, NWKRTC, and KKRTC city and express buses.",
        eligibility=(
            "All women, girls, and transgender persons domiciled in Karnataka. "
            "Valid on ordinary, express, and city buses within the state. Not applicable to luxury, sleeper, AC (Airavat, Club Class), or interstate routes."
        ),
        documents_required="Any government photo identity card showing Karnataka residential address (Aadhaar Card, Voter ID, Driving Licence, or Shakti Smart Card).",
        how_to_apply="No prior booking needed. Simply present your government photo ID with Karnataka address to the conductor to receive a zero-fare ticket.",
        keywords=[
            "shakti scheme", "shakthi scheme", "free bus travel", "women bus pass", "free ksrtc",
            "free bmtc", "karnataka bus pass", "nwkrtc", "kkrtc", "zero fare ticket", "women travel free"
        ],
    ),

    # -------------------------------------------------------------------------
    # 6. Bhoomi Portal (Land Records & RTC / Pahani)
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="bhoomi_portal",
        scheme_name="Bhoomi Land Records Portal",
        category="Revenue & Land Administration",
        department="Revenue Department, Government of Karnataka",
        official_portal="Bhoomi Karnataka",
        official_url="https://bhoomi.karnataka.gov.in",
        helpline="080-22113255 (Email: bhoomi@karnataka.gov.in)",
        summary="Karnataka's centralized digital land record management system providing online RTC (Pahani), mutation register, and land maps.",
        benefits="Instant online viewing and downloading of digitally signed RTC (Pahani), mutation status tracking, Tippan, and Akarband records.",
        eligibility="Open to all landowners, farmers, legal heirs, and citizens owning or verifying agricultural and revenue land in Karnataka.",
        documents_required="District, Taluk, Hobli, Village name, Survey Number, Surnoc, and Hissa Number.",
        how_to_apply=(
            "Visit bhoomi.karnataka.gov.in -> Click 'View RTC & MR' -> Select District, Taluk, Hobli, Village, and Survey Number -> "
            "Fetch details. For a legally valid digitally signed copy, pay ₹15 online or visit a Nada Kacheri or Bangalore One center."
        ),
        keywords=[
            "bhoomi", "bhoomi portal", "rtc", "pahani", "mutation", "land records karnataka",
            "survey number", "akarband", "tippan", "karnataka land", "khata", "mr status", "bhoomi online"
        ],
    ),

    # -------------------------------------------------------------------------
    # 7. e-Swathu Portal (Rural Property Records)
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="eswathu_portal",
        scheme_name="e-Swathu Portal",
        category="Rural Development & Property Records",
        department="Rural Development and Panchayat Raj Department (RDPR), Karnataka",
        official_portal="e-Swathu Karnataka",
        official_url="https://eswathu.karnataka.gov.in",
        helpline="080-22253564",
        summary="Digital ownership and property tax record system for rural properties located in Gram Panchayat jurisdictions.",
        benefits="Issues authentic Form 9 (village property document) and Form 11 (property tax assessment register) necessary for rural property registration.",
        eligibility="Owners of residential and non-agricultural properties within Karnataka Gram Panchayat limits.",
        documents_required="Property details, title deed / conversion order, village panchayat tax receipts, and owner Aadhaar card.",
        how_to_apply="Submit property papers to the Panchayat Development Officer (PDO) of the local Gram Panchayat or verify property records on eswathu.karnataka.gov.in.",
        keywords=[
            "eswathu", "e-swathu", "form 9", "form 11", "gram panchayat property", "rural khata",
            "panchayat property tax", "pdo property", "eswathu search", "rural property registration"
        ],
    ),

    # -------------------------------------------------------------------------
    # 8. Ganga Kalyana Scheme (Irrigation Borewells)
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="ganga_kalyana",
        scheme_name="Ganga Kalyana Scheme",
        category="Agriculture & Irrigation Welfare",
        department="Dr. B.R. Ambedkar Development Corporation & Backward Classes Welfare, Karnataka",
        official_portal="Dr. B.R. Ambedkar Development Corporation",
        official_url="https://drbrambedkar.karnataka.gov.in",
        helpline="080-22261789 or 080-22261788",
        summary="Drills free individual or community borewells with electric pumpsets and pipeline energization for small and marginal SC/ST and minority farmers.",
        benefits="Full subsidy between ₹3.50 lakh and ₹4.50 lakh for drilling borewell, installing submersible motor pumpset, and electricity connection.",
        eligibility=(
            "Small and marginal farmers owning between 1.0 and 5.0 acres of dry agricultural land in Karnataka. "
            "Must belong to SC, ST, or notified religious/backward minority communities. Annual family income must be under ₹1.5 lakh (rural) or ₹2.0 lakh (urban)."
        ),
        documents_required="Caste Certificate (RD number), Income Certificate (RD number), Land RTC/Pahani, Small/Marginal Farmer certificate, and Aadhaar card.",
        how_to_apply="Apply online via sevasindhu.karnataka.gov.in or directly at Dr. B.R. Ambedkar Development Corporation district offices.",
        keywords=[
            "ganga kalyana", "gangakalyana", "borewell subsidy", "free borewell", "farmer borewell",
            "sc st irrigation", "pumpset subsidy", "ambedkar corporation borewell", "irrigation borewell karnataka"
        ],
    ),

    # -------------------------------------------------------------------------
    # 9. K-Kisan & Raitha Siri (Agriculture Welfare)
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="raitha_siri",
        scheme_name="Raitha Siri & K-Kisan Schemes",
        category="Agriculture & Farmer Advisory",
        department="Department of Agriculture, Government of Karnataka",
        official_portal="Raita Mitra Karnataka",
        official_url="https://raitamitra.karnataka.gov.in",
        helpline="1800-425-3553 (Kisan Call Centre) or 1551",
        summary="Incentives for millet cultivation (₹10,000/ha Raitha Siri), farm pond subsidies (Krishi Bhagya), and farm machinery hiring via RSK centers.",
        benefits="₹10,000 per hectare incentive directly to bank accounts of millet farmers, up to 90% subsidy for farm ponds and drip irrigation under Krishi Bhagya.",
        eligibility="Agricultural landholders in Karnataka registered on the FRUITS (Farmer Registration and Unified Beneficiary Information System) portal.",
        documents_required="FRUITS FID number, land RTC (Pahani), Aadhaar card, and bank passbook.",
        how_to_apply="Register land on FRUITS portal (fruits.karnataka.gov.in) and visit nearest Raitha Samparka Kendra (RSK) in your taluk.",
        keywords=[
            "raitha siri", "raitamitra", "k-kisan", "krishi bhagya", "fruits portal", "millet incentive 10000",
            "farm pond subsidy", "raitha samparka kendra", "rsk", "karnataka agriculture", "seed subsidy"
        ],
    ),

    # -------------------------------------------------------------------------
    # 10. Pashu Bhagya Scheme (Dairy & Livestock)
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="pashu_bhagya",
        scheme_name="Pashu Bhagya Scheme",
        category="Animal Husbandry & Dairy",
        department="Department of Animal Husbandry and Veterinary Services (AHVS), Karnataka",
        official_portal="AHVS Karnataka",
        official_url="https://ahvs.karnataka.gov.in",
        helpline="1800-425-0012 (Pashu Sahayavani)",
        summary="Subsidized loans through commercial banks for establishing dairy cattle units, sheep and goat rearing units, piggery, and poultry.",
        benefits="33% subsidy for general category farmers and 50% subsidy for SC/ST farmers for dairy and livestock units with subsidized interest rates.",
        eligibility="Farmers, landless agricultural labourers, and rural youth residing in Karnataka.",
        documents_required="Aadhaar card, Caste certificate, land RTC or residence certificate, bank account details, and animal health verification.",
        how_to_apply="Submit application form to the local Veterinary Officer / Assistant Director of Animal Husbandry in your taluk or on ahvs.karnataka.gov.in.",
        keywords=[
            "pashu bhagya", "pashubhagya", "cow loan subsidy", "dairy subsidy karnataka", "buffalo loan",
            "sheep rearing subsidy", "goat farming karnataka", "livestock loan", "ahvs karnataka"
        ],
    ),

    # -------------------------------------------------------------------------
    # 11. Seva Sindhu Portal (Unified Citizen Services)
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="seva_sindhu",
        scheme_name="Seva Sindhu Citizen Services Portal",
        category="Citizen Services & E-Governance",
        department="Department of Personnel and Administrative Reforms (e-Governance), Karnataka",
        official_portal="Seva Sindhu Karnataka",
        official_url="https://sevasindhu.karnataka.gov.in",
        helpline="1902 or 080-22279954 (8:00 AM - 8:00 PM)",
        summary="Unified single-window e-governance portal integrating 800+ citizen services from all departments of the Karnataka Government.",
        benefits="Single digital window to apply for all Karnataka guarantee schemes, caste/income certificates, driver licenses, revenue services, and track application status.",
        eligibility="All residents and citizens of Karnataka.",
        documents_required="Aadhaar card, active mobile phone number for OTP verification, and service-specific documents.",
        how_to_apply="Register with Aadhaar and mobile number at sevasindhu.karnataka.gov.in, or visit Grama One, Bangalore One, or Karnataka One kiosks.",
        keywords=[
            "seva sindhu", "sevasindhu", "seva sindhu portal", "grama one", "bangalore one",
            "karnataka one", "citizen services karnataka", "1902", "apply online karnataka", "track application sevasindhu"
        ],
    ),

    # -------------------------------------------------------------------------
    # 12. Nada Kacheri (Caste, Income & Domicile Certificates)
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="nadakacheri",
        scheme_name="Nada Kacheri Portal (Atalji Janasnehi Kendra)",
        category="Revenue & Statutory Certificates",
        department="Directorate of Atalji Janasnehi Kendra, Revenue Department, Karnataka",
        official_portal="Nada Kacheri Karnataka",
        official_url="https://nadakacheri.karnataka.gov.in",
        helpline="080-22214556",
        summary="Official portal for issuing statutory certificates including Caste, Income, Residence, Living, and HK Region 371(J) certificates.",
        benefits="Digital issuance of legally valid certificates carrying a 15-digit GSC number verifiable by any government department or college.",
        eligibility="Any citizen residing in Karnataka requiring statutory revenue certificates.",
        documents_required="Aadhaar card, Ration card, previous caste/income records, and school leaving certificate.",
        how_to_apply="Visit nadakacheri.karnataka.gov.in -> Click 'Online Applications' -> Select certificate type -> Fill details -> Pay ₹25 fee.",
        keywords=[
            "nadakacheri", "nada kacheri", "caste certificate karnataka", "income certificate karnataka",
            "residence certificate", "domicile karnataka", "371j certificate", "ajsk", "tahsildar certificate"
        ],
    ),

    # -------------------------------------------------------------------------
    # 13. State Scholarship Portal (SSP Karnataka)
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="ssp_scholarship",
        scheme_name="State Scholarship Portal (SSP Karnataka)",
        category="Education & Student Welfare",
        department="Center for e-Governance & Social Welfare Department, Karnataka",
        official_portal="SSP Post-Matric & Pre-Matric",
        official_url="https://ssp.postmatric.karnataka.gov.in",
        helpline="1902 or 080-35254999",
        summary="Unified digital scholarship platform for pre-matric and post-matric students belonging to SC, ST, OBC, Minority, and EWS categories.",
        benefits="Direct fee reimbursement to colleges and monthly maintenance allowance credited directly to students' Aadhaar-linked bank accounts via DBT.",
        eligibility="Karnataka domicile students enrolled in recognized schools, PUC, diploma, undergraduate, or postgraduate institutions in Karnataka.",
        documents_required="Student SATS ID / College Registration number, Aadhaar number, Income and Caste certificate RD numbers from Nada Kacheri, and e-Attested documents.",
        how_to_apply="Create student account on ssp.postmatric.karnataka.gov.in, link Aadhaar, provide SATS/University ID, and submit before annual deadlines.",
        keywords=[
            "ssp", "ssp scholarship", "post matric scholarship", "vidyasiri", "fee reimbursement karnataka",
            "student scholarship", "e-attestation", "sats id", "social welfare scholarship karnataka"
        ],
    ),

    # -------------------------------------------------------------------------
    # 14. Sandhya Suraksha Yojana (Social Security Pensions)
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="sandhya_suraksha",
        scheme_name="Sandhya Suraksha Yojana & Social Security Pensions",
        category="Social Welfare & Old Age Pensions",
        department="Directorate of Social Security Pensions (DSSP), Revenue Department, Karnataka",
        official_portal="DSSP Karnataka Portal",
        official_url="https://dssp.karnataka.gov.in",
        helpline="080-22340089",
        summary="Monthly pension of ₹1,000 for destitute senior citizens aged 65 years and above in Karnataka, alongside widow and disability pensions.",
        benefits="Monthly pension of ₹1,000 transferred via DBT directly into beneficiary's bank or postal account.",
        eligibility="Resident of Karnataka aged 65 years or older. Combined annual income of applicant and spouse must not exceed ₹20,000 per annum.",
        documents_required="Aadhaar card, Age proof (Voter ID or school record), Income certificate from Nada Kacheri, and bank passbook.",
        how_to_apply="Submit application form at nearest Nada Kacheri, Atalji Janasnehi Kendra, or via sevasindhu.karnataka.gov.in.",
        keywords=[
            "sandhya suraksha", "old age pension karnataka", "senior citizen pension", "widow pension karnataka",
            "manasvini", "disability pension karnataka", "dssp", "1000 rupees pension", "destitute pension"
        ],
    ),

    # -------------------------------------------------------------------------
    # 15. Kutumba Portal (Family Entitlement Database)
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="kutumba_portal",
        scheme_name="Kutumba Portal (Family Social Registry)",
        category="E-Governance & DBT Administration",
        department="Department of e-Governance, Government of Karnataka",
        official_portal="Kutumba Karnataka",
        official_url="https://kutumba.karnataka.gov.in",
        helpline="080-22371054",
        summary="Karnataka's unified resident family entitlement database mapping Aadhaar, ration cards, land holdings, and caste for automatic scheme eligibility.",
        benefits="Paperless benefit delivery: citizens do not need to repeatedly submit caste, income, or land proofs for government schemes.",
        eligibility="All families residing in Karnataka.",
        documents_required="Aadhaar cards of all family members and Ration card.",
        how_to_apply="Families are automatically enrolled via ration cards and Aadhaar. Check your family ID and entitlement status on kutumba.karnataka.gov.in.",
        keywords=[
            "kutumba", "kutumba portal", "family id karnataka", "social registry", "dbt entitlement",
            "karnataka family database", "kutumba search", "kutumba.karnataka.gov.in"
        ],
    ),

    # -------------------------------------------------------------------------
    # 16. Arogya Karnataka (Ayushman Bharat - Arogya Karnataka / ARK)
    # -------------------------------------------------------------------------
    KarnatakaSchemeDocument(
        id="arogya_karnataka",
        scheme_name="Arogya Karnataka (Ayushman Bharat - ARK)",
        category="Public Health & Medical Insurance",
        department="Department of Health & Family Welfare / Suvarna Arogya Suraksha Trust (SAST)",
        official_portal="Arogya Karnataka Portal",
        official_url="https://arogya.karnataka.gov.in",
        helpline="104 (Karnataka Health Helpline) or 1800-425-8330",
        summary="Comprehensive universal healthcare scheme providing cashless medical coverage up to ₹5 lakh per family per year for BPL families.",
        benefits="Up to ₹5 lakh annual cashless hospitalization per family for complex secondary and tertiary treatments in empanelled hospitals for BPL families.",
        eligibility="All Karnataka residents. BPL (Eligible) category gets 100% cashless treatment. APL (General) category receives 30% financial assistance up to ₹1.5 lakh.",
        documents_required="Ration card (BPL or APL), Aadhaar card, and referral letter from a Government public health center or district hospital.",
        how_to_apply="Visit any Government Hospital or Taluk Hospital with your Ration card and Aadhaar card to obtain your ARK patient health ID and referral.",
        keywords=[
            "arogya karnataka", "ayushman bharat karnataka", "ark card", "free hospital treatment",
            "5 lakh health insurance", "sast karnataka", "medical treatment subsidy", "health card karnataka", "104"
        ],
    ),
]


def get_all_karnataka_documents() -> List[KarnatakaSchemeDocument]:
    """Returns all verified Government of Karnataka scheme documents."""
    return list(KARNATAKA_GOVERNMENT_DOCUMENTS)


def get_document_by_id(doc_id: str) -> Optional[KarnatakaSchemeDocument]:
    """Look up a specific Karnataka document by id."""
    for doc in KARNATAKA_GOVERNMENT_DOCUMENTS:
        if doc.id == doc_id:
            return doc
    return None
