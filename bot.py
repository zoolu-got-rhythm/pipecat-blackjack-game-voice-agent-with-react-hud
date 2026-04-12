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
from services_factory import create_llm, create_stt, create_tts
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
        self.chips = 100
        self.current_bet = 0
        self.awaiting_bet = True

    def _build_deck(self):
        values = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11]
        return values * 4

    def hand_value(self, hand):
        total = sum(hand)
        aces = hand.count(11)
        while total > 21 and aces:
            total -= 10
            aces -= 1
        return total

    def place_bet(self, amount: int):
        amount = int(amount)
        if amount <= 0:
            return {"error": "Bet must be positive"}
        if amount > self.chips:
            return {"error": f"Not enough chips. You have {self.chips}"}
        self.current_bet = amount
        self.awaiting_bet = False
        self.deck = self._build_deck()
        random.shuffle(self.deck)
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]
        self.over = False
        return {
            "player_hand": self.player_hand,
            "player_value": self.hand_value(self.player_hand),
            "dealer_upcard": self.dealer_hand[0],
            "chips": self.chips,
            "current_bet": self.current_bet,
        }

    def hit(self):
        self.player_hand.append(self.deck.pop())
        value = self.hand_value(self.player_hand)
        bust = value > 21
        if bust:
            self.chips -= self.current_bet
            self.over = True
            self.awaiting_bet = True
        return {
            "player_hand": self.player_hand,
            "player_value": value,
            "bust": bust,
            "chips": self.chips,
            "current_bet": self.current_bet,
        }

    def stick(self):
        while self.hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
        player_val = self.hand_value(self.player_hand)
        dealer_val = self.hand_value(self.dealer_hand)
        if dealer_val > 21 or player_val > dealer_val:
            result = "player_wins"
            self.chips += self.current_bet
        elif player_val == dealer_val:
            result = "push"
        else:
            result = "dealer_wins"
            self.chips -= self.current_bet
        self.over = True
        self.awaiting_bet = True
        return {
            "player_hand": self.player_hand,
            "player_value": player_val,
            "dealer_hand": self.dealer_hand,
            "dealer_value": dealer_val,
            "result": result,
            "chips": self.chips,
            "current_bet": self.current_bet,
        }


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    logger.info(f"Starting bot")

    game = BlackjackGame()

    stt = create_stt()
    tts = create_tts()

    tools = ToolsSchema(
        standard_tools=[
            FunctionSchema(
                name="place_bet",
                description="Place a bet to start the next round. Must be called before cards are dealt.",
                properties={
                    "amount": {
                        "type": "integer",
                        "description": "The number of chips to bet.",
                    }
                },
                required=["amount"],
            ),
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
        ]
    )

    llm = create_llm(
        system_instruction=(
            "You are a friendly blackjack dealer, quick to the point and succinct. "
            "The player starts with 100 chips. Their goal is to reach 250 chips to win the game. "
            "Before each round, ask for a bet. "
            "When the player says a bet amount (e.g. 'I bet 10', 'bet 20 chips', 'ten'), call place_bet with that amount. "
            "If place_bet returns an error, tell the player and ask again. "
            "When the player says 'hit' or 'hit me', call the hit function. "
            "When the player says 'stick', 'stand', or 'I'll stay', call the stick function. "
            "After each round ends (bust or stick result), always announce the outcome first (win, loss, or push) before mentioning the dealer's cards or any other details, then state the chip total and ask for their next bet. "
            "If the player's chip total reaches 250 or more, enthusiastically congratulate them — they have beaten the house and won the game. "
            "Always narrate the result of each action in a short, conversational sentence."
        ),
    )

    async def handle_place_bet(params: FunctionCallParams):
        amount = params.arguments.get("amount", 0)
        result = game.place_bet(amount)
        logger.info(f"Place bet: {result}")
        if "error" in result:
            await params.result_callback(str(result))
            return
        await send_game_state("new_game", {
            "player_hand": result["player_hand"],
            "player_value": result["player_value"],
            "dealer_upcard": result["dealer_upcard"],
            "chips": result["chips"],
            "current_bet": result["current_bet"],
        })
        await params.result_callback(str(result))

    async def handle_hit(params: FunctionCallParams):
        result = game.hit()
        logger.info(f"Hit: {result}")
        await send_game_state("hit", {
            "player_hand": result["player_hand"],
            "player_value": result["player_value"],
            "bust": result["bust"],
            "chips": result["chips"],
            "current_bet": result["current_bet"],
        })
        if game.over:
            await send_game_state("awaiting_bet", {"chips": result["chips"]})
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
            "chips": result["chips"],
            "current_bet": result["current_bet"],
        })
        await send_game_state("awaiting_bet", {"chips": result["chips"]})
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

    llm.register_function("place_bet", handle_place_bet)
    llm.register_function("hit", handle_hit)
    llm.register_function("stick", handle_stick)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"Client connected")
        await send_game_state("awaiting_bet", {"chips": game.chips})
        context.add_message(
            {
                "role": "user",
                "content": f"I just joined. I have {game.chips} chips. Welcome me and ask me to place my first bet.",
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
