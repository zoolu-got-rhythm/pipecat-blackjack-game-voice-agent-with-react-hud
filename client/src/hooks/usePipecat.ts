import { useCallback, useEffect, useRef, useState } from "react";
import { PipecatClient, RTVIEvent } from "@pipecat-ai/client-js";
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport";

export interface GameState {
  action: string;
  player_hand?: number[];
  player_value?: number;
  dealer_upcard?: number;
  dealer_hand?: number[];
  dealer_value?: number;
  bust?: boolean;
  result?: "player_wins" | "dealer_wins" | "push";
}

export function usePipecat(botUrl = "http://localhost:7860/api/offer") {
  const clientRef = useRef<PipecatClient | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isBotSpeaking, setIsBotSpeaking] = useState(true);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const audio = new Audio();
    audio.autoplay = true;
    audioRef.current = audio;

    const transport = new SmallWebRTCTransport();
    const client = new PipecatClient({
      transport,
      enableMic: true,
    });

    client.on(RTVIEvent.Connected, () => setIsConnected(true));
    client.on(RTVIEvent.Disconnected, () => setIsConnected(false));
    client.on(RTVIEvent.BotStartedSpeaking, () => setIsBotSpeaking(true));
    client.on(RTVIEvent.BotStoppedSpeaking, () => setIsBotSpeaking(false));
    client.on(RTVIEvent.TrackStarted, (track: MediaStreamTrack, participant?: { local?: boolean }) => {
      if (!participant?.local && track.kind === "audio") {
        audio.srcObject = new MediaStream([track]);
        audio.play().catch(() => {});
      }
    });
    client.on(RTVIEvent.ServerMessage, (data: unknown) => {
      const msg = data as { type?: string } & GameState;
      if (msg.type === "game_state") {
        setGameState(msg as GameState);
      }
    });
    client.on(RTVIEvent.Error, (err: unknown) => {
      setError(String(err));
    });

    clientRef.current = client;

    return () => {
      client.disconnect().catch(() => {});
      audio.srcObject = null;
    };
  }, [botUrl]);

  const connect = useCallback(async () => {
    setError(null);
    try {
      await clientRef.current?.connect({ connectionUrl: botUrl });
    } catch (err) {
      setError(String(err));
    }
  }, [botUrl]);

  const disconnect = useCallback(async () => {
    await clientRef.current?.disconnect();
  }, []);

  return { isConnected, isBotSpeaking, gameState, error, connect, disconnect };
}
