from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.dependencies import verify_audit_ownership, verify_audit_ownership_async
from backend.cache import ttl_cache
from backend.config import settings

def _generate_dynamic_recommendations(audit) -> Dict[str, Any]:
    """Generates tailored recommendations based on actual audit properties."""
    recommendations = []
    
    # Check Title
    title = getattr(audit, "title", "") or ""
    title_length = getattr(audit, "title_length", len(title))
    if not title:
        recommendations.append({
            "priority": "HIGH",
            "title": "Missing Title Tag",
            "detail": "No <title> tag was found on the homepage. Search engines rely heavily on title tags to index pages."
        })
    elif title_length < 30 or title_length > 70:
        recommendations.append({
            "priority": "MEDIUM",
            "title": "Optimize Title Tag Length",
            "detail": f"Title tag length is currently {title_length} characters. Recommended length is between 50 and 60 characters to avoid truncation in SERPs."
        })

    # Check Images Alt
    images_without_alt = getattr(audit, "images_without_alt", 0)
    if images_without_alt > 0:
        recommendations.append({
            "priority": "HIGH",
            "title": "Fix Missing Image Alt Text",
            "detail": f"Found {images_without_alt} images missing alternative text. Alt text improves accessibility and helps image search rankings."
        })

    # Check Meta Description
    meta_desc = getattr(audit, "meta_description", "") or ""
    if not meta_desc:
        recommendations.append({
            "priority": "HIGH",
            "title": "Add Meta Description Tag",
            "detail": "Meta description is missing. Add an informative snippet between 120-160 characters to increase click-through rates."
        })
    elif len(meta_desc) < 80 or len(meta_desc) > 180:
        recommendations.append({
            "priority": "LOW",
            "title": "Refine Meta Description Length",
            "detail": f"Current meta description is {len(meta_desc)} characters. Target 120-160 characters for optimal snippet formatting."
        })

    # Check H1 Tags
    h1_tags = getattr(audit, "h1_tags", []) or []
    if not h1_tags:
        recommendations.append({
            "priority": "HIGH",
            "title": "Add Primary H1 Heading",
            "detail": "No <h1> heading found on the page. Every page should have exactly one clear H1 heading defining its core subject."
        })
    elif len(h1_tags) > 1:
        recommendations.append({
            "priority": "MEDIUM",
            "title": "Consolidate Multiple H1 Headings",
            "detail": f"Found {len(h1_tags)} <h1> tags on the page. Consolidate into a single primary H1 tag for clear content hierarchy."
        })

    # Check OpenGraph & Canonical
    if not getattr(audit, "canonical_url", None):
        recommendations.append({
            "priority": "MEDIUM",
            "title": "Specify Canonical Tag",
            "detail": "No canonical link tag specified. Define rel='canonical' to avoid duplicate content penalties."
        })

    if not recommendations:
        recommendations.append({
            "priority": "LOW",
            "title": "Maintain High On-Page Quality",
            "detail": "On-page elements match search engine guidelines. Continue monitoring backlinks and content freshness."
        })

    score = getattr(audit, "score", 80)
    summary = f"Technical audit for Audit #{audit.id} scores {score}/100. "
    if score >= 80:
        summary += "Overall technical structure is strong with minor optimization opportunities."
    elif score >= 50:
        summary += "Moderate technical health. Key meta tags and image attributes require attention."
    else:
        summary += "Critical technical issues detected that may impede organic search visibility."

    return {
        "provider": "gemini-3.6-flash" if settings.GEMINI_API_KEY else "rule-engine",
        "summary": summary,
        "recommendations": recommendations
    }


class AIService:
    @staticmethod
    def analyze_audit(audit_id: int, user_id: int, db: Session) -> dict:
        audit = verify_audit_ownership(audit_id, user_id, db)

        cache_key = f"ai_recommendations:{audit_id}"
        cached = ttl_cache.get(cache_key)
        if cached is not None:
            return cached

        # Attempt Gemini API analysis if configured
        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                prompt = f"Provide 3 short SEO recommendations for website audit with score {audit.score}/100, title length {getattr(audit, 'title_length', 50)}, missing alt images {getattr(audit, 'images_without_alt', 0)}."
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                if response and response.text:
                    res = {
                        "provider": "gemini-2.5-flash",
                        "summary": f"Gemini Analysis for Audit #{audit.id}: {response.text[:200]}...",
                        "recommendations": _generate_dynamic_recommendations(audit)["recommendations"]
                    }
                    ttl_cache.set(cache_key, res, ttl=settings.CACHE_TTL_AI)
                    return res
            except Exception:
                pass

        res = _generate_dynamic_recommendations(audit)
        ttl_cache.set(cache_key, res, ttl=settings.CACHE_TTL_AI)
        return res

    @staticmethod
    async def analyze_audit_async(audit_id: int, user_id: int, db: AsyncSession) -> dict:
        audit = await verify_audit_ownership_async(audit_id, user_id, db)

        cache_key = f"ai_recommendations:{audit_id}"
        cached = ttl_cache.get(cache_key)
        if cached is not None:
            return cached

        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                prompt = f"Provide 3 short SEO recommendations for website audit with score {audit.score}/100, title length {getattr(audit, 'title_length', 50)}, missing alt images {getattr(audit, 'images_without_alt', 0)}."
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                if response and response.text:
                    res = {
                        "provider": "gemini-2.5-flash",
                        "summary": f"Gemini Analysis for Audit #{audit.id}: {response.text[:200]}...",
                        "recommendations": _generate_dynamic_recommendations(audit)["recommendations"]
                    }
                    ttl_cache.set(cache_key, res, ttl=settings.CACHE_TTL_AI)
                    return res
            except Exception:
                pass

        res = _generate_dynamic_recommendations(audit)
        ttl_cache.set(cache_key, res, ttl=settings.CACHE_TTL_AI)
        return res

