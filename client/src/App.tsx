import { useState, useEffect, useRef } from "react";

const flashStyle = `
  @keyframes flash {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.25; }
  }
`;

import Confetti from "react-confetti";
import { usePipecat, GameState } from "./hooks/usePipecat";

function Hand({ cards, value }: { cards: number[]; value: number }) {
  return (
    <span>
      [{cards.join(", ")}] = <strong>{value}</strong>
    </span>
  );
}

function ResultBadge({ result }: { result: GameState["result"] }) {
  const config: Record<string, { label: string; color: string }> = {
    player_wins: { label: "You win!", color: "green" },
    dealer_wins: { label: "Dealer wins", color: "red" },
    push: { label: "Push", color: "orange" },
  };
  if (!result) return null;
  const { label, color } = config[result];
  return <strong style={{ color }}>{label}</strong>;
}

const CHIP_GOAL = 250;

export default function App() {
  const {
    isConnected,
    isBotSpeaking,
    isThinking,
    gameState,
    error,
    connect,
    disconnect,
    setMicEnabled,
  } = usePipecat();

  const [showingResult, setShowingResult] = useState(false);
  const [showConfetti, setShowConfetti] = useState(false);
  const [gameWon, setGameWon] = useState(false);
  const [gameOverConfirmed, setGameOverConfirmed] = useState(false);
  const brokeSpeakingRef = useRef(false);
  const lastRoundRef = useRef<Pick<GameState, "player_hand" | "player_value" | "dealer_hand" | "dealer_value" | "dealer_upcard" | "bust" | "result"> | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const brokeAndAwaiting = !gameWon &&
    gameState?.action === "awaiting_bet" &&
    (gameState?.chips ?? 1) <= 0;

  useEffect(() => {
    if (gameState?.chips !== undefined && gameState.chips >= CHIP_GOAL && !gameWon) {
      setGameWon(true);
      setShowConfetti(true);
      setMicEnabled(false);
    }
  }, [gameState?.chips]);

  useEffect(() => {
    if (brokeAndAwaiting) setMicEnabled(false);
  }, [brokeAndAwaiting]);

  useEffect(() => {
    if (!brokeAndAwaiting) {
      brokeSpeakingRef.current = false;
      setGameOverConfirmed(false);
      return;
    }
    if (isBotSpeaking) {
      brokeSpeakingRef.current = true;
    } else if (brokeSpeakingRef.current) {
      setGameOverConfirmed(true);
      disconnect();
    }
  }, [brokeAndAwaiting, isBotSpeaking]);

  useEffect(() => {
    if (!gameState?.result && !gameState?.bust) return;
    lastRoundRef.current = {
      player_hand: gameState.player_hand,
      player_value: gameState.player_value,
      dealer_hand: gameState.dealer_hand,
      dealer_value: gameState.dealer_value,
      dealer_upcard: gameState.dealer_upcard,
      bust: gameState.bust,
      result: gameState.result,
    };
    setShowingResult(true);
    if (gameState.result === "player_wins") setShowConfetti(true);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setShowingResult(false);
      lastRoundRef.current = null;
    }, 8000);
  }, [gameState?.result, gameState?.bust]);

  const displayHands = showingResult
    ? lastRoundRef.current
    : gameState?.action !== "awaiting_bet"
    ? gameState
    : null;

  return (
    <>
      <style>{flashStyle}</style>
      {showConfetti && (
        <Confetti
          recycle={false}
          numberOfPieces={gameWon ? 800 : 400}
          gravity={0.6}
          onConfettiComplete={() => setShowConfetti(false)}
        />
      )}
      {gameWon && (
        <div style={{
          position: "fixed", inset: 0, display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
          background: "rgba(0,0,0,0.75)", zIndex: 10, color: "white", textAlign: "center",
        }}>
          <div style={{ fontSize: "3em", marginBottom: 12 }}>🏆</div>
          <div style={{ fontSize: "2em", fontWeight: "bold", marginBottom: 8 }}>You reached {CHIP_GOAL} chips!</div>
          <div style={{ color: "#aaa", marginBottom: 24 }}>Congratulations, you beat the house!</div>
          <button onClick={() => window.location.reload()} style={{ padding: "10px 24px", fontSize: "1em" }}>
            Play Again
          </button>
        </div>
      )}
    <div
      style={{
        fontFamily: "monospace",
        maxWidth: 390,
        margin: "40px auto",
        padding: "0 16px",
      }}
    >
      <h1>Blackjack Voice Agent 🂡</h1>

      <div style={{ marginBottom: 16 }}>
        {!isConnected ? (
          <button onClick={connect}>Connect &amp; Play</button>
        ) : (
          <button onClick={disconnect}>Disconnect</button>
        )}
        <span style={{ marginLeft: 12, color: isConnected ? "green" : "gray" }}>
          {isConnected ? "Connected" : "Disconnected"}
        </span>
      </div>

      {error && (
        <div style={{ color: "red", marginBottom: 12 }}>Error: {error}</div>
      )}

      {gameState && (
        <div style={{ lineHeight: 2 }}>
          {gameState.chips !== undefined && (
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>
                <strong style={{ color: "#B8860B" }}>Chips:</strong> <span style={{ color: "#B8860B" }}>{gameState.current_bet && (gameState.action === "new_game" || gameState.action === "hit") ? gameState.chips! - gameState.current_bet : gameState.chips}</span>
                {gameState.current_bet !== undefined &&
                  gameState.current_bet > 0 &&
                  gameState.action !== "awaiting_bet" && (
                    <span style={{ marginLeft: 16 }}>
                      <strong style={{ color: "#B8860B" }}>Bet:</strong> <span style={{ color: "#B8860B" }}>{gameState.current_bet}</span>
                    </span>
                  )}
              </span>
              <span style={{ color: "#888", fontSize: "0.85em", marginRight: "30px" }}>To win reach: {CHIP_GOAL}</span>
            </div>
          )}

          {displayHands && (
            <>
              {displayHands.player_hand && displayHands.player_value !== undefined && (
                <div>
                  <strong>Your hand:</strong>{" "}
                  <Hand
                    cards={displayHands.player_hand}
                    value={displayHands.player_value}
                  />
                  {displayHands.bust && <span style={{ color: "red" }}> BUST</span>}
                </div>
              )}

              {displayHands.dealer_upcard !== undefined && !displayHands.dealer_hand && (
                <div>
                  <strong>Dealer upcard:</strong> {displayHands.dealer_upcard}
                </div>
              )}

              {displayHands.dealer_hand && displayHands.dealer_value !== undefined && (
                <div>
                  <strong>Dealer hand:</strong>{" "}
                  <Hand
                    cards={displayHands.dealer_hand}
                    value={displayHands.dealer_value}
                  />
                </div>
              )}

              {displayHands.result && (
                <div style={{ marginTop: 8, fontSize: "1.2em" }}>
                  <ResultBadge result={displayHands.result} />
                </div>
              )}
            </>
          )}

          {gameState.action === "awaiting_bet" && !isBotSpeaking && (gameState.chips ?? 0) > 0 && !gameWon && (
            <div style={{ marginTop: 12, color: "#555", animation: "flash 1.2s ease-in-out infinite" }}>
              🎙️ Place your bet to start the round.
            </div>
          )}

          {gameOverConfirmed && (
            <div style={{ marginTop: 12, color: "red" }}>
              Out of chips, game over!
            </div>
          )}

          {(gameState.action === "new_game" || gameState.action === "hit") &&
            !gameState.bust &&
            !isBotSpeaking &&
            !gameWon && (
              <div style={{ marginTop: 12, color: "#555", animation: "flash 1.2s ease-in-out infinite" }}>
                🎙️ hit or stick?
              </div>
            )}
        </div>
      )}

{isThinking && (
        <p style={{ color: "gray", fontStyle: "italic" }}>
          🧠 Dealer is thinking...
        </p>
      )}

      {isConnected && !gameState && !isThinking && (
        <p style={{ color: "gray" }}>Waiting for game state...</p>
      )}
    </div>
    </>
  );
}
