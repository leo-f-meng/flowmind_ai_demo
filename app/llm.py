import os
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI
from app.schemas import ExtractionResult


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPEN_AI_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-5-nano")

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4), reraise=True
    )
    def extract_json(self, text: str) -> dict:
        try:
            response = self.client.responses.parse(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": "Extract structured fields from the user's text.",
                    },
                    {
                        "role": "user",
                        "content": text,
                    },
                ],
                text_format=ExtractionResult,
            )

            parsed = response.output_parsed
            if parsed is None:
                raise LLMError(
                    "No parsed output (model may have refused or output was empty)."
                )

            return parsed.model_dump()

        except Exception as e:
            raise LLMError(str(e)) from e
