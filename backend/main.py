from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from anthropic import Anthropic
from dotenv import load_dotenv
import os
import json
import asyncio

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Anthropic()

class EmailRequest(BaseModel):
    emails: list[str]

class TransformRequest(BaseModel):
    text: str
    mode: str

SYSTEM_PROMPT = """You are a client relationship intelligence assistant for a boutique Registered Investment Advisor (RIA) firm.

Your job is to help the financial advisor manage their client inbox. You understand:
- The language and concerns of high-net-worth individuals
- Common financial life events (retirement, inheritance, divorce, college funding, market anxiety)
- How RIA advisors communicate professionally with clients
- The difference between a client who is at risk of leaving vs one who just needs reassurance
- Compliance-conscious language appropriate for a fiduciary advisor

When analyzing emails, think like a seasoned financial advisor who has been managing client relationships for 20 years.

Always respond with valid JSON only. No extra text, no markdown, no code blocks. Just raw JSON."""

async def analyze_single_email(email: str) -> dict:
    loop = asyncio.get_event_loop()

    def call_api():
        return client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"""Analyze this client email sent to their RIA financial advisor. Return a JSON object with these fields:

1. category: one of:
   - "portfolio_review" (questions about investments, performance, allocation, market concerns)
   - "tax_planning" (tax questions, RMDs, Roth conversions, capital gains, RSUs)
   - "financial_life_event" (divorce, inheritance, college, retirement, job change, death in family, marriage)
   - "client_at_risk" (complaints, frustration, threats to leave, long silence then contact, unusual withdrawal requests)
   - "new_money_referral" (new funds to invest, referral from existing client, new account inquiry)
   - "relationship_checkin" (general check-ins, thank you notes, scheduling, small talk)

2. urgency: one of "high", "medium", "low"
   - high: client is upset, at risk, has time-sensitive financial decision, or major life event
   - medium: needs response within 24-48 hours, has a specific question or request
   - low: FYI, thank you, general check-in, no action needed urgently

3. sender_name: extract the sender's first and last name if mentioned, otherwise "Client"

4. subject: a short 5-8 word subject line summarizing the email as a financial advisor would label it

5. planning_areas: array of 2-3 specific financial planning topic tags relevant to this email (e.g. ["Asset Allocation", "Market Volatility"], ["529 Plan", "College Funding"], ["RMD", "Tax Planning"])

6. summary: one sentence summary of what the client needs, written from the advisor's perspective

7. client_sentiment: one of "anxious", "frustrated", "satisfied", "neutral", "urgent", "grateful"

8. suggested_action: one specific, actionable sentence telling the advisor exactly what to do next with timeframes and specifics

9. draft_reply: a professional, warm, fiduciary-appropriate reply (max 150 words) written as the advisor. Use the client's name if known. Sound human, not templated.

Return ONLY this JSON structure:
{{
  "category": "...",
  "urgency": "...",
  "sender_name": "...",
  "subject": "...",
  "planning_areas": ["...", "..."],
  "summary": "...",
  "client_sentiment": "...",
  "suggested_action": "...",
  "draft_reply": "..."
}}

Client email:
{email}"""
                }
            ]
        )

    response = await loop.run_in_executor(None, call_api)
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw.strip())
    result["original_email"] = email
    return result


@app.post("/triage")
async def triage_emails(request: EmailRequest):
    # Process in batches of 3 to avoid rate limits
    batch_size = 3
    results = []
    for i in range(0, len(request.emails), batch_size):
        batch = request.emails[i:i + batch_size]
        batch_tasks = [analyze_single_email(email) for email in batch]
        batch_results = await asyncio.gather(*batch_tasks)
        results.extend(batch_results)
    return {"results": results}

from fastapi.responses import StreamingResponse

@app.post("/triage-stream")
async def triage_emails_stream(request: EmailRequest):
    async def generate():
        batch_size = 3
        total = len(request.emails)
        completed = 0

        for i in range(0, total, batch_size):
            batch = request.emails[i:i + batch_size]
            batch_tasks = [analyze_single_email(email) for email in batch]
            batch_results = await asyncio.gather(*batch_tasks)

            for result in batch_results:
                completed += 1
                payload = json.dumps({
                    "result": result,
                    "completed": completed,
                    "total": total
                })
                yield f"data: {payload}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


TRANSFORM_PROMPTS = {
    "shorten": "Shorten this RIA financial advisor email reply to about half the length. Keep it professional, warm, and fiduciary-appropriate. Preserve all key information and the client's name if present. Return only the reply text, no preamble or explanation.",
    "expand": "Expand this RIA financial advisor email reply to be more thorough. Add more warmth, context, and specific next steps. Keep it professional and compliance-conscious. Return only the reply text, no preamble.",
    "rewrite": "Rewrite this RIA financial advisor email reply with completely fresh wording. Keep the same meaning, tone, and key points but use different phrasing. Return only the reply text, no preamble.",
    "formal": "Rewrite this RIA financial advisor email reply in a more formal, polished tone suitable for a high-net-worth client. Remove any casual language while keeping it warm and human. Return only the reply text, no preamble."
}

@app.post("/transform")
async def transform_draft(request: TransformRequest):
    if request.mode not in TRANSFORM_PROMPTS:
        return {"error": "Invalid mode"}

    loop = asyncio.get_event_loop()
    def call_api():
        return client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system="You are a writing assistant for a fiduciary financial advisor. You help refine client email replies to sound professional, warm, and appropriate for high-net-worth client relationships. Return only the revised email text with no extra commentary.",
            messages=[
                {
                    "role": "user",
                    "content": f"{TRANSFORM_PROMPTS[request.mode]}\n\nEmail reply to transform:\n{request.text}"
                }
            ]
        )

    response = await loop.run_in_executor(None, call_api)
    return {"result": response.content[0].text.strip()}


@app.get("/")
def root():
    return {"status": "RIA Inbox Assistant is running", "model": "claude-haiku-4-5-20251001", "mode": "parallel"}