import csv
import os
import re
from typing import Any, Dict, Optional, List
from backend.utils.logger import get_logger
from backend.utils.helpers import generate_id, now_iso

logger = get_logger("scraping_tool")

INDUSTRY_PERSONAS = {
    "saas": ["VP of Engineering", "CTO", "Head of Product"],
    "healthcare": ["Chief Medical Officer", "VP Operations", "Director of IT"],
    "finance": ["CFO", "VP Finance", "Director of Technology"],
    "logistics": ["VP Supply Chain", "COO", "Director of Operations"],
    "retail": ["CMO", "VP eCommerce", "Director of Digital"],
    "manufacturing": ["VP Operations", "CTO", "Director of IT"],
    "default": ["CEO", "VP Sales", "Head of Operations"],
}

COMPANY_SIGNALS = {
    "hiring": "Company is actively hiring in key departments",
    "funding": "Recently secured funding round",
    "expansion": "Expanding into new markets",
    "product_launch": "Recently launched new product/service",
    "competitor_switch": "Evaluating alternatives to current vendor",
    "pain_point": "Public discussion of operational challenges",
}


def enrich_company(company: str, industry: str = "default") -> Dict[str, Any]:
    logger.info("Enriching company data", company=company, industry=industry)
    # First, attempt to load leads from a CSV dataset if provided.
    csv_paths: List[str] = []
    env_path = os.environ.get("LINKEDIN_CSV_PATH")
    if env_path:
        csv_paths.append(env_path)

    # Common locations to check
    csv_paths.extend([
        os.path.join(os.path.dirname(__file__), "..", "data", "linkedin.csv"),
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "linkedin.csv"),
        os.path.join(os.getcwd(), "data", "linkedin.csv"),
    ])

    found_rows = []
    for p in csv_paths:
        try:
            p = os.path.abspath(p)
            if not os.path.exists(p):
                continue
            with open(p, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    # Gather possible company fields from the CSV row to support different export formats
                    candidate_keys = [
                        "company",
                        "company_name",
                        "row_company",
                        "full_name",
                        "occupation",
                        "experiences0company",
                        "experiences1company",
                        "experiences0company_linkedin_profile_url",
                    ]
                    row_company = ""
                    for k in candidate_keys:
                        v = (row.get(k) or "").strip()
                        if v:
                            # prefer short tokens that look like a company name
                            row_company = v
                            break

                    # If still empty, try to infer from headline/occupation fields
                    if not row_company:
                        row_company = (row.get("headline") or row.get("summary") or "").strip()

                    if not row_company:
                        continue

                    # Case-insensitive substring match to allow loose matches like 'Vodafone' vs 'vodafone'
                    try:
                        if company.lower() in row_company.lower() or row_company.lower() in company.lower():
                            found_rows.append(row)
                    except Exception:
                        continue
            if found_rows:
                logger.info("Loaded leads from CSV", path=p, matches=len(found_rows))
                break
        except Exception:
            continue

    industry_key = industry.lower().split()[0] if industry else "default"
    personas = INDUSTRY_PERSONAS.get(industry_key, INDUSTRY_PERSONAS["default"])

    slug = re.sub(r'[^a-z0-9]', '-', company.lower())
    domain = f"{slug}.com"

    leads = []
    if found_rows:
        for i, row in enumerate(found_rows[:5]):
            name = (row.get("name") or row.get("full_name") or "").strip()
            title = (row.get("title") or row.get("job_title") or personas[i % len(personas)]).strip()
            email = (row.get("email") or row.get("work_email") or "").strip()
            linkedin = (row.get("linkedin") or row.get("linkedin_url") or "").strip()
            try:
                score = float(row.get("score") or row.get("ranking") or 0.7)
            except Exception:
                score = 0.7

            leads.append({
                "lead_id": generate_id("lead"),
                "name": name or f"Lead {i+1}",
                "title": title,
                "company": company,
                "email": email,
                "linkedin": linkedin,
                "score": round(score, 2),
                "signals": list(COMPANY_SIGNALS.values())[:2],
                "enriched_at": now_iso(),
            })
    else:
        # Fallback: synthesize leads as before when no CSV data is available.
        for i, title in enumerate(personas[:2]):
            first_names = ["Alex", "Jordan", "Morgan", "Taylor", "Casey"]
            last_names = ["Smith", "Johnson", "Williams", "Brown", "Davis"]
            first = first_names[i % len(first_names)]
            last = last_names[i % len(last_names)]
            email_format = f"{first.lower()}.{last.lower()}@{domain}"

            leads.append({
                "lead_id": generate_id("lead"),
                "name": f"{first} {last}",
                "title": title,
                "company": company,
                "email": email_format,
                "linkedin": f"https://linkedin.com/in/{first.lower()}-{last.lower()}",
                "score": round(0.65 + (i * 0.1), 2),
                "signals": list(COMPANY_SIGNALS.values())[:2],
                "enriched_at": now_iso(),
            })

    signals = [
        "Active on LinkedIn with posts about scaling challenges",
        "Job postings suggest technology investment",
        "Recent press releases indicate growth phase",
    ]

    return {
        "company": company,
        "domain": domain,
        "industry": industry,
        "estimated_employees": "100-500",
        "tech_stack_signals": ["Salesforce", "Slack", "AWS"],
        "leads": leads,
        "intent_signals": signals,
        "enriched_at": now_iso(),
    }


def search_company_news(company: str) -> Dict[str, Any]:
    logger.info("Searching company news", company=company)

    mock_news = [
        {
            "title": f"{company} announces Q4 growth strategy",
            "source": "TechCrunch",
            "date": now_iso()[:10],
            "summary": f"{company} is expanding operations and investing in new technology",
            "sentiment": "positive",
        },
        {
            "title": f"{company} faces competitive pressure in market",
            "source": "Bloomberg",
            "date": now_iso()[:10],
            "summary": "Market analysis shows increased competition in the segment",
            "sentiment": "neutral",
        },
    ]

    competitor_signals = []
    competitor_keywords = ["evaluating alternatives", "competitive", "switch", "migration"]
    for news in mock_news:
        for kw in competitor_keywords:
            if kw in news["summary"].lower():
                competitor_signals.append({
                    "signal": f"Competitor signal: {news['title']}",
                    "source": news["source"],
                    "severity": "medium",
                })

    return {
        "company": company,
        "news": mock_news,
        "competitor_signals": competitor_signals,
        "searched_at": now_iso(),
    }


def detect_intent_signals(company: str, account_data: Optional[Dict] = None) -> Dict[str, Any]:
    signals = []
    risk_factors = []

    if account_data:
        days_inactive = account_data.get("days_inactive", 0)
        health_score = account_data.get("health_score", 100)
        open_tickets = account_data.get("open_tickets", 0)
        logins = account_data.get("logins_last_30_days", 10)

        if days_inactive >= 10:
            risk_factors.append(f"No contact for {days_inactive} days")
        if health_score < 40:
            risk_factors.append(f"Low health score: {health_score}")
        if open_tickets > 5:
            risk_factors.append(f"High support load: {open_tickets} open tickets")
        if logins < 5:
            risk_factors.append(f"Low engagement: {logins} logins in 30 days")

        if health_score > 30 and days_inactive < 30:
            signals.append("Account shows signs of recovery potential")
        if logins > 0:
            signals.append("Buyer still logging in - relationship not lost")

    news_data = search_company_news(company)
    signals.extend([n["title"] for n in news_data["news"][:1]])
    risk_factors.extend([s["signal"] for s in news_data["competitor_signals"]])

    return {
        "company": company,
        "positive_signals": signals,
        "risk_factors": risk_factors,
        "competitor_activity": len(news_data["competitor_signals"]) > 0,
        "overall_sentiment": "at_risk" if len(risk_factors) > 2 else "neutral",
        "analyzed_at": now_iso(),
    }
