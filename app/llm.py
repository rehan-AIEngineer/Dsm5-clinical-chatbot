"""
llm.py
------
Handles LLM answer generation with Gemini (primary).

Simplified version: only Gemini remains.
Expansion query function stays.
"""

import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ---- Gemini credentials ----
GEMINI_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", "").split(",") if k.strip()]
GEMINI_MODEL = "models/gemini-3.5-flash-lite"

_gemini_key_index = 0


# --------------------------------------------------------------------------
# Error classification
# --------------------------------------------------------------------------

def _is_switchable_error(e: Exception) -> bool:
    """True if this error means 'try the next key'."""
    msg = str(e).lower()
    triggers = [
        "quota",
        "rate limit",
        "429",
        "resourceexhausted",
        "timeout",
        "timed out",
        "connection",
        "503",
        "502",
        "500",
        "unavailable",
        "server error",
    ]
    return any(t in msg for t in triggers)


# --------------------------------------------------------------------------
# Prompt building
# --------------------------------------------------------------------------

def build_cot_prompt(query: str, context_chunks: list):
    """
    Production-grade clinical response prompt for a DSM-5-TR RAG chatbot.
    """

    context_text = "\n\n".join(
        f"[{c.get('disorder_name', 'DSM-5-TR')} — "
        f"{c.get('section_name', 'Reference')}]\n"
        f"{c.get('text', '')}"
        for c in context_chunks
    )

    prompt = f"""
You are a warm, empathetic, and clinically knowledgeable AI educational
assistant whose primary purpose is to help users understand mental-health
concerns through the DSM-5-TR.

You are NOT a psychiatrist, psychologist, or medical doctor.
You do not diagnose users or provide treatment plans.

========================
CORE RESPONSE RULES
========================

1. Never provide or imply a definitive diagnosis.

Use language such as:
- "These symptoms can occur in..."
- "A clinician may consider..."
- "This pattern can be seen in..."
- "More information would be needed to distinguish between..."

Never say:
- "You have schizophrenia."
- "This definitely means bipolar disorder."
- "This proves that..."

2. Ground DSM-5-TR clinical claims in the retrieved reference material.

3. Never invent:
- diagnostic criteria
- duration requirements
- prevalence/statistics
- risk factors
- treatment claims
- medication information
- medical facts presented as DSM criteria

4. Never mention internal systems or implementation details.

Do NOT mention:
- RAG
- vector search
- embeddings
- database
- retrieved chunks
- context
- prompts
- internal documents
- "the provided context does not contain..."

5. Do not expose your internal reasoning or step-by-step chain of thought.
Return only the natural final response.

6. Paraphrase DSM-5-TR content in your own words rather than quoting it
directly. Summarize the clinical meaning; do not reproduce long verbatim
passages from the reference material.

========================
EMPATHY & COMMUNICATION
========================

For personal mental-health situations:

- Start with brief, genuine emotional validation.
- Be calm, respectful, and non-judgmental.
- Use simple language that a caregiver or general user can understand.
- Avoid sounding like a textbook.
- Avoid unnecessarily long lists.
- Ask no more than 1-2 relevant clarifying questions when needed.

For purely informational questions:

- Answer directly.
- Do not force an empathy statement.
- Do not ask unnecessary follow-up questions.

- Respond in the same language/register the user writes in (English, Urdu,
  or Roman Urdu). Do not switch languages on the user unprompted.

========================
CLINICAL REASONING FRAMEWORK
========================

When symptoms are described, silently consider:

1. SYMPTOMS
Identify the clinically relevant symptoms described by the user.

2. DURATION
Pay close attention to how long symptoms have been present.

For psychotic-spectrum presentations, duration is important, but duration
alone must NEVER be treated as sufficient to establish a diagnosis.

3. FUNCTIONING
Consider whether symptoms are affecting:
- school
- work
- relationships
- self-care
- daily activities

Functional impairment is clinically relevant, but it does not by itself
establish a diagnosis.

4. AGE / DEVELOPMENT
Consider the person's age and developmental context when provided.

5. SUBSTANCE / MEDICATION / MEDICAL CAUSES
Before presenting a primary psychiatric disorder as a possibility, consider
whether the symptoms could be related to:
- substance use
- intoxication or withdrawal
- medication effects
- another medical or neurological condition

Do not claim that these causes have been ruled out unless the user explicitly
provides evidence that they were evaluated.

6. MOOD SYMPTOMS
When relevant, distinguish between:
- depressive symptoms
- manic symptoms
- hypomanic symptoms
- psychotic symptoms occurring during mood episodes
- psychotic symptoms occurring outside mood episodes

7. PSYCHOTIC SYMPTOMS
When hallucinations, delusions, paranoia, or disorganized behavior are
described, consider:
- duration
- functional impairment
- substance or medication effects
- medical causes
- mood-related psychosis
- other relevant psychotic-spectrum possibilities

8. NEGATIVE SYMPTOMS
When relevant, consider:
- reduced emotional expression
- flat or blunted affect
- avolition
- alogia
- social withdrawal
- reduced motivation

Do not automatically interpret these symptoms as schizophrenia because
similar features can occur in other clinical presentations.

9. DIFFERENTIAL POSSIBILITIES
When clinically appropriate, explain the main possibilities a professional
might consider.

Do not produce an unnecessarily long list of disorders.

========================
DIAGNOSTIC BOUNDARY
========================

The assistant should explain clinical concepts and help the user understand
what information clinicians typically consider.

The assistant must NOT make the final diagnostic decision.

When the available information is insufficient, clearly communicate the
uncertainty rather than guessing. For example: "That's a good question — I
don't have that level of detail on hand, but here's what is established
about..." Never fabricate an answer just to avoid acknowledging a gap.

========================
CONVERSATION CONTINUITY
========================

Treat the conversation as ongoing.

Use relevant information already provided by the user.

Do not repeatedly ask for information that has already been provided,
including: age, symptom duration and onset, sleep, appetite, energy, mood,
substance use, recent stressors, previous episodes, functional impairment,
and safety concerns.

When new information is provided, incorporate it into the current response
instead of restarting the assessment from the beginning.

========================
SAFETY
========================

If the user describes suicidal thoughts, self-harm, intent to harm others,
or an inability to stay safe:

- Prioritize immediate safety.
- Respond calmly and directly.
- Encourage seeking urgent professional/emergency help.
- Do not provide instructions that could facilitate self-harm or violence.

Do not allow the normal DSM explanation to take priority over an immediate
safety concern.

========================
RESPONSE STYLE
========================

- Warm
- Empathetic
- Concise
- Clinically careful
- Non-judgmental
- Easy to understand
- No unnecessary headings
- No unnecessary bullet lists
- No definitive diagnosis
- No treatment or medication instructions
- No internal reasoning

========================
DSM-5-TR REFERENCE
========================

{context_text}

========================
USER QUESTION
========================

{query}

Respond directly to the user with a natural, supportive, clinically careful
answer.
"""

    return prompt
# --------------------------------------------------------------------------
# Provider: Gemini (with multiple keys rotation)
# --------------------------------------------------------------------------

def _call_gemini(prompt: str) -> str:
    global _gemini_key_index
    if not GEMINI_KEYS:
        raise RuntimeError("Gemini quota exhausted: no API keys configured")
    
    last_error = None
    for _ in range(len(GEMINI_KEYS)):
        try:
            genai.configure(api_key=GEMINI_KEYS[_gemini_key_index])
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            last_error = e
            if _is_switchable_error(e):
                print(f"Gemini key {_gemini_key_index} failed, rotating...")
                _gemini_key_index = (_gemini_key_index + 1) % len(GEMINI_KEYS)
                continue
            raise

    raise RuntimeError(f"All Gemini keys failed. Last error: {last_error}")

# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------

def _strip_reasoning(text: str) -> str:
    """Removes any leaked reasoning/step markers, keeping only the final answer."""
    markers = ["Final Answer:", "Answer:", "**Final Answer:**", "**Answer:**"]
    for marker in markers:
        if marker in text:
            return text.split(marker, 1)[1].strip()
    return text.strip()


def generate_answer(query: str, context_chunks: list) -> str:
    if not GEMINI_KEYS:
        return "Error: Gemini API key not configured. Please set GEMINI_API_KEYS in .env"
    
    if not context_chunks:
        return "I couldn't find relevant information in the DSM-5-TR reference for this question."

    prompt = build_cot_prompt(query, context_chunks)
    
    try:
        raw = _call_gemini(prompt)
        answer = _strip_reasoning(raw)
        return answer
        
    except Exception as e:
        # ✅ Check if it's a quota/rate limit error
        error_msg = str(e).lower()
        if "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg:
            return "I'm sorry, but the assistant is temporarily unavailable because the daily response limit has been reached. Please try again later."
        return f"Error generating response: {str(e)}"


def generate_answer_stream(query: str, context_chunks: list):
    """Yield the Gemini answer in chunks so the frontend can render it live."""
    if not GEMINI_KEYS:
        yield "Error: Gemini API key not configured. Please set GEMINI_API_KEYS in .env"
        return

    if not context_chunks:
        yield "I couldn't find relevant information in the DSM-5-TR reference for this question."
        return

    prompt = build_cot_prompt(query, context_chunks)

    try:
        genai.configure(api_key=GEMINI_KEYS[_gemini_key_index])
        model = genai.GenerativeModel(GEMINI_MODEL)

        # Added streaming path: Gemini yields partial chunks instead of waiting
        # for the whole answer, and the frontend appends them live.
        for chunk in model.generate_content(prompt, stream=True):
            chunk_text = getattr(chunk, "text", "") or ""
            if chunk_text:
                yield chunk_text

    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg:
            yield "I'm sorry, but the assistant is temporarily unavailable because the daily response limit has been reached. Please try again later."
            return
        yield f"Error generating response: {str(e)}"

        
def generate_general_response(query: str) -> str:
    """Generate a concise response for general/non-clinical queries."""

    prompt = f"""
You are a helpful and friendly AI assistant.

The user's question is outside the primary mental-health and
DSM-5-TR focus of this chatbot.

Answer the user's question briefly, naturally, and accurately.

Guidelines:
- Keep the response concise, preferably 2-4 sentences.
- Answer only what the user asked.
- Do not use DSM-5-TR information or clinical reasoning.
- Do not provide a long or detailed explanation.
- Do not mention RAG, databases, prompts, retrieval, or internal systems.
- Do not make the response sound like a refusal.
- After answering, briefly remind the user about the chatbot's main purpose.

End with this message:

"I'm primarily designed to help with mental-health and DSM-5-TR
related questions, such as symptoms, mental disorders, diagnostic
criteria, and clinical concerns."

User question:
{query}

Answer:
"""

    try:
        response = _call_gemini(prompt)
        return _strip_reasoning(response)

    except Exception as e:
        print(f"DEBUG - General response failed: {e}")

        return (
            "I'm having trouble answering that right now. "
            "I'm primarily designed to help with mental-health "
            "and DSM-5-TR related questions."
        )






def expand_to_clinical_terms(query: str) -> dict:
    """
    Uses Gemini to classify the user's query as either:
    - clinical: expand into DSM-style clinical terminology
    - general: return a short general-answer instruction

    Clinical queries continue to the DSM-5 RAG pipeline.
    Non-clinical queries skip clinical expansion and DSM retrieval.
    """

    prompt = f"""
You are a query router for a DSM-5-TR mental-health chatbot.

Analyze the user's question and decide whether it is primarily
related to mental health, psychiatry, psychology, DSM-5-TR,
mental-health symptoms, mental disorders, diagnosis, or clinical
assessment.

Return ONLY valid JSON in this exact format:

{{
    "type": "clinical" or "general",
    "clinical_terms": "short comma-separated clinical terms"
}}

Rules:

1. If the question is about mental health, psychiatric symptoms,
   mental disorders, diagnosis, DSM-5-TR concepts, or someone
   experiencing possible psychological symptoms:
   - type = "clinical"
   - Convert the user's casual description into short,
     relevant clinical/psychiatric terminology.
   - Do NOT diagnose the person.

2. If the question is unrelated to mental health or clinical topics:
   - type = "general"
   - clinical_terms must be an empty string.

3. Do not answer the user's question.
4. Do not provide explanations.
5. Return ONLY the JSON object.

User question:
"{query}"
"""

    try:
        if not GEMINI_KEYS:
            print("DEBUG - No Gemini keys configured")
            return {
                "type": "clinical",
                "query": query
            }

        genai.configure(api_key=GEMINI_KEYS[_gemini_key_index])

        model = genai.GenerativeModel(GEMINI_MODEL)

        response = model.generate_content(prompt)

        result = response.text.strip()

        print(f"DEBUG - Query classification: {result}")

        # Remove markdown code fences if Gemini returns them
        result = result.replace("```json", "").replace("```", "").strip()

        import json

        data = json.loads(result)

        query_type = data.get("type", "clinical")
        clinical_terms = data.get("clinical_terms", "").strip()

        # =====================================================
        # CLINICAL QUERY
        # =====================================================
        if query_type == "clinical":

            if clinical_terms:
                expanded_query = f"{query} ({clinical_terms})"
            else:
                expanded_query = query

            print(
                f"DEBUG - Clinical query detected: {expanded_query}"
            )

            return {
                "type": "clinical",
                "query": expanded_query
            }

        # =====================================================
        # GENERAL QUERY
        # =====================================================
        else:

            print("DEBUG - General/non-clinical query detected")

            return {
                "type": "general",
                "query": query
            }

    except Exception as e:

        print(f"DEBUG - Query classification failed: {e}")

        # Safe fallback:
        # If classification fails, keep the existing clinical RAG
        # behavior instead of losing the user's question.
        return {
            "type": "clinical",
            "query": query
        }