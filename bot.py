#
# Copyright (c) 2024-2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Pipecat Quickstart Example.

The example runs a simple voice AI bot that you can connect to using your
browser and speak with it. You can also deploy this bot to Pipecat Cloud.

Required AI services:
- Deepgram (Speech-to-Text)
- Grok / xAI (LLM)
- Cartesia (Text-to-Speech)

Run the bot using::

    uv run bot.py
"""

import os
import random

from dotenv import load_dotenv
from loguru import logger

print("🚀 Starting Pipecat bot...")
print("⏳ Loading models and imports (20 seconds, first run only)\n")

logger.info("Loading Silero VAD model...")
from pipecat.audio.vad.silero import SileroVADAnalyzer

logger.info("✅ Silero VAD model loaded")

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import LLMRunFrame, OutputTransportMessageFrame
from pipecat.services.llm_service import FunctionCallParams

logger.info("Loading pipeline components...")
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.grok.llm import GrokLLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.daily.transport import DailyParams

logger.info("✅ All components loaded successfully!")

load_dotenv(override=True)


class BlackjackGame:
    def __init__(self):
        self.deck = self._build_deck()
        self.player_hand = []
        self.dealer_hand = []
        self.over = False
        self._deal_initial()

    def _build_deck(self):
        values = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11]
        return values * 4

    def _deal_initial(self):
        random.shuffle(self.deck)
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]

    def hand_value(self, hand):
        total = sum(hand)
        aces = hand.count(11)
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    def hit(self):
        self.player_hand.append(self.deck.pop())
        value = self.hand_value(self.player_hand)
        bust = value > 21
        if bust:
            self.over = True
        return {"player_hand": self.player_hand, "player_value": value, "bust": bust}

    def stick(self):
        while self.hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
        player_val = self.hand_value(self.player_hand)
        dealer_val = self.hand_value(self.dealer_hand)
        if dealer_val > 21 or player_val > dealer_val:
            result = "player_wins"
        elif player_val == dealer_val:
            result = "push"
        else:
            result = "dealer_wins"
        self.over = True
        return {
            "player_hand": self.player_hand,
            "player_value": player_val,
            "dealer_hand": self.dealer_hand,
            "dealer_value": dealer_val,
            "result": result,
        }

    def new_game(self):
        self.__init__()
        return {
            "player_hand": self.player_hand,
            "player_value": self.hand_value(self.player_hand),
            "dealer_upcard": self.dealer_hand[0],
        }


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    logger.info(f"Starting bot")

    game = BlackjackGame()

    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))

    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        settings=CartesiaTTSService.Settings(
            voice="71a7ad14-091c-4e8e-a314-022ece01c121",  # British Reading Lady
        ),
    )

    tools = ToolsSchema(
        standard_tools=[
            FunctionSchema(
                name="hit",
                description="Player takes another card from the deck.",
                properties={},
                required=[],
            ),
            FunctionSchema(
                name="stick",
                description="Player stands; dealer plays out their hand and the winner is determined.",
                properties={},
                required=[],
            ),
            FunctionSchema(
                name="new_game",
                description="Start a brand new game of blackjack.",
                properties={},
                required=[],
            ),
        ]
    )

    llm = GrokLLMService(
        api_key=os.getenv("GROK_API_KEY"),
        model="grok-3-beta",
        settings=GrokLLMService.Settings(
            system_instruction=(
                "You are a friendly blackjack dealer. "
                "When the player says 'hit' or 'hit me', call the hit function. "
                "When the player says 'stick', 'stand', or 'I'll stay', call the stick function. "
                "When the player wants to play again or start a new game, call the new_game function. "
                "Always narrate the result of each action in a short, conversational sentence. "
                "If the result includes a 'new_game' field, announce the new hand immediately after."
            ),
        ),
    )

    async def handle_hit(params: FunctionCallParams):
        result = game.hit()
        logger.info(f"Hit: {result}")
        await send_game_state("hit", {
            "player_hand": result["player_hand"],
            "player_value": result["player_value"],
            "bust": result["bust"],
        })
        if game.over:
            new = game.new_game()
            result["new_game"] = new
            await send_game_state("new_game", {
                "player_hand": new["player_hand"],
                "player_value": new["player_value"],
                "dealer_upcard": new["dealer_upcard"],
            })
        await params.result_callback(str(result))

    async def handle_stick(params: FunctionCallParams):
        result = game.stick()
        logger.info(f"Stick: {result}")
        await send_game_state("stick", {
            "player_hand": result["player_hand"],
            "player_value": result["player_value"],
            "dealer_hand": result["dealer_hand"],
            "dealer_value": result["dealer_value"],
            "result": result["result"],
        })
        new = game.new_game()
        result["new_game"] = new
        await send_game_state("new_game", {
            "player_hand": new["player_hand"],
            "player_value": new["player_value"],
            "dealer_upcard": new["dealer_upcard"],
        })
        await params.result_callback(str(result))

    async def handle_new_game(params: FunctionCallParams):
        result = game.new_game()
        logger.info(f"New game: {result}")
        await send_game_state("new_game", {
            "player_hand": result["player_hand"],
            "player_value": result["player_value"],
            "dealer_upcard": result["dealer_upcard"],
        })
        await params.result_callback(str(result))

    context = LLMContext(tools=tools)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    pipeline = Pipeline(
        [
            transport.input(),  # Transport user input
            stt,
            user_aggregator,  # User responses
            llm,  # LLM
            tts,  # TTS
            transport.output(),  # Transport bot output
            assistant_aggregator,  # Assistant spoken responses
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    async def send_game_state(action: str, data: dict):
        message = {
            "label": "rtvi-ai",
            "type": "server-message",
            "data": {"type": "game_state", "action": action, **data},
        }
        await task.queue_frames([OutputTransportMessageFrame(message=message)])

    llm.register_function("hit", handle_hit)
    llm.register_function("stick", handle_stick)
    llm.register_function("new_game", handle_new_game)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"Client connected")
        initial = {
            "player_hand": game.player_hand,
            "player_value": game.hand_value(game.player_hand),
            "dealer_upcard": game.dealer_hand[0],
        }
        await send_game_state("new_game", initial)
        context.add_message(
            {
                "role": "user",
                "content": f"Deal me in. My starting hand is: {initial}. Welcome me and tell me my hand.",
            }
        )
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"Client disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)

    await runner.run(task)


async def bot(runner_args: RunnerArguments):
    """Main bot entry point for the bot starter."""

    transport_params = {
        "daily": lambda: DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
        "webrtc": lambda: TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    }

    transport = await create_transport(runner_args, transport_params)

    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
