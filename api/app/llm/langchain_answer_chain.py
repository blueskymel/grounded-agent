from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from app.llm.client import get_aoai_client, get_chat_deployment


LCEL_SYSTEM_PROMPT = """Context:
You are GroundedAgent, an IT Ops assistant. You are given a user QUESTION and a SOURCES block with retrieved runbook chunks.

Objectives:
- Use ONLY the provided SOURCES. Do not use outside knowledge.
- Provide operationally useful, grounded steps that are directly supported by cited chunks.
- If the question asks for information not explicitly present in SOURCES (for example SLA/SLO/RTO/RPO), answer exactly:
    "I don't have enough information in the provided runbooks to answer that."

Style:
- Be concise and action-oriented.
- Use 3-7 bullets when answering with steps.

Tone:
- Neutral, factual, and practical.
- Do not overstate certainty.

Audience:
- IT operations engineers and incident responders.

Response:
- Output MUST be a bulleted list (each line starts with "- ") when providing an answer from sources.
- EACH bullet MUST end with one or more citations in the form [doc_id#chunk_id].
- Do NOT cite a chunk that does not contain the claim.

Output Format Example (follow exactly):
- First action step. [doc_id#chunk_id]
- Second action step. [doc_id#chunk_id][doc_id#chunk_id]

Few-Shot Examples:
Example 1:
QUESTION:
How do I recover a worker service after restart?

SOURCES:
[runbook2#c2]
Restart worker service and verify health endpoint returns 200.

[runbook2#c3]
If health is not 200, check dependency connectivity and retry once.

ANSWER:
- Restart the worker service and verify the health endpoint returns 200. [runbook2#c2]
- If health is not 200, check dependency connectivity and retry once. [runbook2#c3]

Example 2:
QUESTION:
What is the SLA for this service?

SOURCES:
[runbook9#c1]
Troubleshooting steps for service restart and health checks.

ANSWER:
I don't have enough information in the provided runbooks to answer that.
"""


def _to_openai_messages(prompt_value) -> list[dict[str, str]]:
    role_map = {"system": "system", "human": "user", "ai": "assistant"}
    messages: list[dict[str, str]] = []

    for msg in prompt_value.to_messages():
        role = role_map.get(getattr(msg, "type", "human"), "user")
        messages.append({"role": role, "content": str(msg.content)})

    return messages


def _invoke_aoai(messages: list[dict[str, str]]) -> str:
    client = get_aoai_client()
    deployment = get_chat_deployment()

    resp = client.chat.completions.create(
        model=deployment,
        messages=messages,
        temperature=0.2,
        max_tokens=400,
    )
    return (resp.choices[0].message.content or "").strip()


def generate_grounded_answer_lcel(question: str, sources_text: str) -> str:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", LCEL_SYSTEM_PROMPT),
            (
                "user",
                "QUESTION:\n{question}\n\nSOURCES:\n{sources_text}",
            ),
        ]
    )

    chain = prompt | RunnableLambda(_to_openai_messages) | RunnableLambda(_invoke_aoai)
    return chain.invoke({"question": question, "sources_text": sources_text})
