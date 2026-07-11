import json
from typing import Any

from ..config import get_settings


class LLMError(RuntimeError):
    pass


def complete_json(
    system_prompt: str, user_content: str, stage: str | None = None
) -> dict[str, Any]:
    settings = get_settings()
    if settings.use_mock:
        from .mock import mock_response

        return mock_response(stage or "", user_content)

    if settings.llm_provider == "mistral":
        return _complete_json_mistral(system_prompt, user_content, settings)
    else:
        return _complete_json_gemini(system_prompt, user_content, settings)


def complete_chat_json(
    system_prompt: str,
    messages: list[dict[str, str]],
    stage: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if settings.use_mock:
        from .mock import mock_chat_response

        return mock_chat_response(stage or "", messages)

    if settings.llm_provider == "mistral":
        return _complete_chat_json_mistral(system_prompt, messages, settings)
    else:
        return _complete_chat_json_gemini(system_prompt, messages, settings)


def _complete_json_gemini(
    system_prompt: str, user_content: str, settings
) -> dict[str, Any]:
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise LLMError(
            "google-generativeai not installed; install it or set USE_MOCK_LLM=true"
        ) from exc

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=system_prompt,
        generation_config={
            "temperature": 0,
            "response_mime_type": "application/json",
        },
    )
    try:
        resp = model.generate_content(
            user_content,
            request_options={"timeout": settings.request_timeout},
        )
    except Exception as exc:
        raise LLMError(f"Gemini request failed: {exc}") from exc

    content = (getattr(resp, "text", None) or "{}").strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Model did not return valid JSON: {content[:500]}") from exc


def _complete_json_mistral(
    system_prompt: str, user_content: str, settings
) -> dict[str, Any]:
    try:
        from mistralai.client import Mistral
    except ImportError as exc:
        raise LLMError(
            "mistralai not installed; install it with 'pip install mistralai' or set USE_MOCK_LLM=true"
        ) from exc

    client = Mistral(api_key=settings.mistral_api_key)
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        resp = client.chat.complete(
            model=settings.mistral_model,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise LLMError(f"Mistral request failed: {exc}") from exc

    content = resp.choices[0].message.content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Model did not return valid JSON: {content[:500]}") from exc


def _complete_chat_json_gemini(
    system_prompt: str, messages: list[dict[str, str]], settings
) -> dict[str, Any]:
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise LLMError(
            "google-generativeai not installed; install it or set USE_MOCK_LLM=true"
        ) from exc

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=system_prompt,
        generation_config={
            "temperature": 0.3,
            "response_mime_type": "application/json",
        },
    )

    history = []
    for msg in messages[:-1]:
        role = "user" if msg["role"] == "user" else "model"
        history.append({"role": role, "parts": [msg["content"]]})

    last = messages[-1]["content"] if messages else ""
    try:
        if history:
            chat = model.start_chat(history=history)
            resp = chat.send_message(
                last,
                request_options={"timeout": settings.request_timeout},
            )
        else:
            resp = model.generate_content(
                last,
                request_options={"timeout": settings.request_timeout},
            )
    except Exception as exc:
        raise LLMError(f"Gemini chat request failed: {exc}") from exc

    content = (getattr(resp, "text", None) or "{}").strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Model did not return valid JSON: {content[:500]}") from exc


def _complete_chat_json_mistral(
    system_prompt: str, messages: list[dict[str, str]], settings
) -> dict[str, Any]:
    try:
        from mistralai.client import Mistral
    except ImportError as exc:
        raise LLMError(
            "mistralai not installed; install it with 'pip install mistralai' or set USE_MOCK_LLM=true"
        ) from exc

    client = Mistral(api_key=settings.mistral_api_key)
    
    mistral_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        role = "user" if msg["role"] == "user" else "assistant"
        mistral_messages.append({"role": role, "content": msg["content"]})

    try:
        resp = client.chat.complete(
            model=settings.mistral_model,
            messages=mistral_messages,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise LLMError(f"Mistral chat request failed: {exc}") from exc

    content = resp.choices[0].message.content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Model did not return valid JSON: {content[:500]}") from exc
