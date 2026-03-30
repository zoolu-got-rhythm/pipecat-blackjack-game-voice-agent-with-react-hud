import { usePipecat, GameState } from "./hooks/usePipecat";

function Hand({ cards, value }: { cards: number[]; value: number }) {
  return (
    <span>
      [{cards.join(", ")}] = <strong>{value}</strong>
    </span>
  );
}

function ResultBadge({ result }: { result: GameState["result"] }) {
  const labels: Record<string, string> = {
    player_wins: "You win!",
    dealer_wins: "Dealer wins",
    push: "Push",
  };
  return result ? <strong>{labels[result]}</strong> : null;
}

export default function App() {
  const { isConnected, isBotSpeaking, gameState, error, connect, disconnect } = usePipecat();

  return (
    <div style={{ fontFamily: "monospace", maxWidth: 480, margin: "40px auto", padding: "0 16px" }}>
      <h1>Blackjack</h1>

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
          {gameState.player_hand && gameState.player_value !== undefined && (
            <div>
              <strong>Your hand:</strong>{" "}
              <Hand cards={gameState.player_hand} value={gameState.player_value} />
              {gameState.bust && <span style={{ color: "red" }}> BUST</span>}
            </div>
          )}

          {gameState.dealer_upcard !== undefined && !gameState.dealer_hand && (
            <div>
              <strong>Dealer upcard:</strong> {gameState.dealer_upcard}
            </div>
          )}

          {gameState.dealer_hand && gameState.dealer_value !== undefined && (
            <div>
              <strong>Dealer hand:</strong>{" "}
              <Hand cards={gameState.dealer_hand} value={gameState.dealer_value} />
            </div>
          )}

          {gameState.result && (
            <div style={{ marginTop: 8, fontSize: "1.2em" }}>
              <ResultBadge result={gameState.result} />
            </div>
          )}

          {(gameState.action === "new_game" || gameState.action === "hit") && !gameState.bust && !isBotSpeaking && (
            <div style={{ marginTop: 12, color: "#555" }}>
              🎙️ Stick or hit?
            </div>
          )}
        </div>
      )}

      {isConnected && !gameState && (
        <p style={{ color: "gray" }}>Waiting for game state...</p>
      )}
    </div>
  );
}
