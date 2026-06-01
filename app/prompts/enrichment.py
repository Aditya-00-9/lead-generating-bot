USER_TEMPLATE = """
Analyze this mention for competitor dissatisfaction and migration intent.

Allowed competitors:
{competitors}

Intent labels:
- HIGH: actively switching/requesting alternatives/churn intent
- MEDIUM: frustration/comparison/problem discussion
- LOW: casual mention/informational/no clear dissatisfaction

Return JSON with:
competitor: string
detected_pain_points: string[]
intent_score: float (0-100)
intent_label: "HIGH" | "MEDIUM" | "LOW"
worth_responding: boolean
ai_summary: string (<=320 chars)
suggested_reply: string (human, empathetic, non-salesy, subtle KramaAI mention, <=420 chars)
sentiment: "negative" | "neutral" | "mixed"
urgency_score: float (0-100)
engagement_score: float (0-100)
tags: string[]

Input:
source: {source}
platform: {platform}
title: {title}
text: {cleaned_text}
url: {source_url}
"""
