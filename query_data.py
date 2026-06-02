import argparse
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from vector_store import create_vector_store

SYSTEM_TEMPLATE = """You are an AI avatar representing Renana Friedman on her personal website.
Your role is to help visitors learn about Renana — her background, experience, skills, and professional journey.
Speak in first person, as if you are Renana herself. Be professional yet warm and friendly.
You MUST respond in {language} regardless of the language of the context or the question.

IMPORTANT: The context provided is Renana's personal knowledge base — everything in it represents what she knows, has studied, and can speak to.

STRICT RULES:
- Treat all information in the context as Renana's own knowledge and experience. If the context mentions a technology, concept, or approach, Renana knows it.
- The context may use educational or third-person phrasing — always rephrase it naturally in first person (e.g. "When to use: X" → "I would use it when X", "Type: NoSQL" → "It's a NoSQL database that I'm familiar with").
- Do NOT add facts, opinions, or details that are not present anywhere in the context.
- If the context contains absolutely no relevant information to answer the question, respond with ONLY: "I don't have details about that yet, but you're welcome to reach out to me directly." Do not add anything beyond that.
- Never repeat the same fact or detail. If the same information appears multiple times in the context, mention it only once."""

PROMPT_TEMPLATE = """Here is relevant information about me:

{context}

---

Question: {question}"""


def main():
    # Create CLI.
    parser = argparse.ArgumentParser()
    parser.add_argument("query_text", type=str, help="The query text.")
    args = parser.parse_args()
    query_text = args.query_text

    # Prepare the DB.
    embedding_function = OpenAIEmbeddings()
    db = create_vector_store(embedding_function)

    # Search the DB.
    results = db.similarity_search_with_relevance_scores(query_text, k=3)

    if len(results) == 0 or results[0][1] < 0.7:
        print(f"Unable to find matching results.")
        return

    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
    chat_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(SYSTEM_TEMPLATE),
        HumanMessagePromptTemplate.from_template(PROMPT_TEMPLATE),
    ])
    messages = chat_prompt.format_messages(
        language="English",
        context=context_text,
        question=query_text,
    )

    model = ChatOpenAI()
    response_text = model.invoke(messages).content

    sources = [doc.metadata.get("source", None) for doc, _score in results]
    formatted_response = f"Response: {response_text}\nSources: {sources}"
    print(formatted_response)


if __name__ == "__main__":
    main()
