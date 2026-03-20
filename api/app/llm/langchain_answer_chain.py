from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from app.llm.client import get_aoai_client, get_chat_deployment


LCEL_SYSTEM_PROMPT = """You are GroundedAgent, an IT Ops assistant.

NON-NEGOTIABLE RULES:
- Use ONLY the provided SOURCES. Do not use outside knowledge.
- Output MUST be a bulleted list (each line starts with "- ").
- EACH bullet MUST end with one or more citations in the form [doc_id#chunk_id].
- Do NOT cite a chunk that does not contain the claim.
- If the question asks for info not explicitly stated in the sources (e.g., SLA/SLO/RTO/RPO), answer exactly:
  "I don't have enough information in the provided runbooks to answer that."

STYLE:
- Be concise and action-oriented.
- 3-7 bullets max.

OUTPUT FORMAT EXAMPLE (follow exactly):
- First action step. [doc_id#chunk_id]
- Second action step. [doc_id#chunk_id][doc_id#chunk_id]
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
