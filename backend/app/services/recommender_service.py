"""services/recommender_service.py
Analyses the user's query/task and recommends the best free/paid LLMs.

Uses the user's own Groq API key to call the LLM for analysis,
then returns structured recommendations with reasoning.
"""
from __future__ import annotations
import json
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.models import LLMRecommendation, RecommendResponse
from app.utils.logger import log

SYSTEM_PROMPT = """You are an expert AI model consultant. A user will describe a task or query.
Analyse it and recommend the best LLMs (free and paid) for that task.

Respond ONLY with valid JSON matching this exact schema:
{
  "query_analysis": "brief analysis of the task type and requirements",
  "task_type": "one of: coding | reasoning | creative | research | qa | summarization | math | general",
  "recommendations": [
    {
      "name": "Model display name",
      "provider": "Company name",
      "tier": "free or paid",
      "best_for": "one-line description of what it excels at",
      "context_window": "e.g. 128K tokens",
      "speed": "fast | medium | slow",
      "cost": "Free / $X per 1M tokens / etc",
      "why_recommended": "2-3 sentences why this fits the user's task",
      "groq_model_id": "groq model id if available on Groq free tier, else null"
    }
  ],
  "top_pick": "Name of the single best model for this task",
  "reasoning": "2-3 sentences explaining why the top pick wins for this specific task"
}

Include 4-6 recommendations mixing free and paid options.
Always include at least 2 free options.
Base recommendations on real current models (GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro,
Llama 3.3 70B, Mixtral 8x7B, Gemma 2 9B, Mistral Large, DeepSeek V3, etc.)
"""


async def get_recommendations(query: str, api_key: str) -> RecommendResponse:
    log.info("Generating LLM recommendations for task: %s", query[:80])
    llm = ChatGroq(
        groq_api_key=api_key,
        model_name="llama-3.3-70b-versatile",
        temperature=0.2,
    )
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"My task/query: {query}"),
    ]
    response = await llm.ainvoke(messages)
    raw = response.content.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    data = json.loads(raw)
    recommendations = [LLMRecommendation(**r) for r in data["recommendations"]]

    return RecommendResponse(
        query_analysis=data["query_analysis"],
        task_type=data["task_type"],
        recommendations=recommendations,
        top_pick=data["top_pick"],
        reasoning=data["reasoning"],
    )
