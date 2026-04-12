import os


def create_stt():
    match os.getenv("STT_PROVIDER", "deepgram"):
        case "deepgram":
            from pipecat.services.deepgram.stt import DeepgramSTTService
            return DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))
        case _:
            raise ValueError(f"Unknown STT_PROVIDER: {os.getenv('STT_PROVIDER')}")


def create_tts():
    match os.getenv("TTS_PROVIDER", "cartesia"):
        case "cartesia":
            from pipecat.services.cartesia.tts import CartesiaTTSService
            return CartesiaTTSService(
                api_key=os.getenv("CARTESIA_API_KEY"),
                settings=CartesiaTTSService.Settings(
                    voice="71a7ad14-091c-4e8e-a314-022ece01c121",  # British Reading Lady
                ),
            )
        case "openai":
            from pipecat.services.openai.tts import OpenAITTSService
            return OpenAITTSService(
                api_key=os.getenv("OPENAI_API_KEY"),
                settings=OpenAITTSService.Settings(voice="alloy"),
            )
        case "deepgram":
            from pipecat.services.deepgram.tts import DeepgramTTSService
            return DeepgramTTSService(
                api_key=os.getenv("DEEPGRAM_API_KEY"),
                settings=DeepgramTTSService.Settings(voice="aura-2-helena-en"),
            )
        case _:
            raise ValueError(f"Unknown TTS_PROVIDER: {os.getenv('TTS_PROVIDER')}")


def create_llm(system_instruction: str, tools=None):
    kwargs = {}
    if tools:
        kwargs["tools"] = tools

    match os.getenv("LLM_PROVIDER", "grok"):
        case "grok":
            from pipecat.services.grok.llm import GrokLLMService
            return GrokLLMService(
                api_key=os.getenv("GROK_API_KEY"),
                model="grok-3-beta",
                settings=GrokLLMService.Settings(system_instruction=system_instruction),
            )
        case "openai":
            from pipecat.services.openai.llm import OpenAILLMService
            return OpenAILLMService(
                api_key=os.getenv("OPENAI_API_KEY"),
                model="gpt-4o",
                settings=OpenAILLMService.Settings(system_instruction=system_instruction),
            )
        case "anthropic":
            from pipecat.services.anthropic.llm import AnthropicLLMService
            return AnthropicLLMService(
                api_key=os.getenv("CLAUDE_API_KEY"),
                model="claude-sonnet-4-6",
                settings=AnthropicLLMService.Settings(system_instruction=system_instruction),
            )
        case "gemini":
            from pipecat.services.google.llm import GoogleLLMService
            return GoogleLLMService(
                api_key=os.getenv("GOOGLE_GEMINI_API_KEY"),
                model="gemini-2.0-flash",
                settings=GoogleLLMService.Settings(system_instruction=system_instruction),
            )
        case _:
            raise ValueError(f"Unknown LLM_PROVIDER: {os.getenv('LLM_PROVIDER')}")
