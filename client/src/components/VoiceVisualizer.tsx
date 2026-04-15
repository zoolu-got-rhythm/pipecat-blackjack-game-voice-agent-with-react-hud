import { useEffect, useRef } from "react";

interface VoiceVisualizerProps {
  barCount?: number;
  active?: boolean;
  width?: number;
  height?: number;
  color?: string;
  gap?: number;
}

export default function VoiceVisualizer({
  barCount = 20,
  active = true,
  width = 60,
  height = 60,
  color = "#4a9eff",
  gap = 3,
}: VoiceVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameRef = useRef<number>(0);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Set canvas pixel buffer to match CSS size × DPR once upfront
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    const ctx2d = canvas.getContext("2d")!;
    ctx2d.scale(dpr, dpr);

    if (!active) {
      // Draw idle bars at minimum height
      ctx2d.clearRect(0, 0, width, height);
      const totalGap = gap * (barCount + 1);
      const barW = (width - totalGap) / barCount;
      const barH = height * 0.15;
      ctx2d.fillStyle = color;
      for (let i = 0; i < barCount; i++) {
        const x = gap + i * (barW + gap);
        ctx2d.fillRect(x, height - barH, barW, barH);
      }
      return;
    }

    let stopped = false;

    async function setup() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        if (stopped) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;

        const audioCtx = new AudioContext();
        audioCtxRef.current = audioCtx;

        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 1024;
        analyser.smoothingTimeConstant = 0.8;
        analyser.minDecibels = -85;
        analyser.maxDecibels = -25;
        analyserRef.current = analyser;

        audioCtx.createMediaStreamSource(stream).connect(analyser);

        draw();
      } catch {
        // mic unavailable — visualizer stays silent
      }
    }

    function draw() {
      const analyser = analyserRef.current;
      if (!analyser) return;

      const bufferLength = analyser.frequencyBinCount; // fftSize / 2 = 512
      const dataArray = new Uint8Array(bufferLength);
      analyser.getByteFrequencyData(dataArray);

      // Clear using CSS pixel dimensions (transform already applied)
      ctx2d.clearRect(0, 0, width, height);

      const totalGap = gap * (barCount + 1);
      const barW = (width - totalGap) / barCount;

      // Noise gate: if average energy is below threshold, treat as silent
      const avg = dataArray.reduce((sum, v) => sum + v, 0) / bufferLength;
      const gated = avg < 8;

      // Logarithmic bin mapping: bar 0 → lowest bin, bar N-1 → highest bin
      const maxBin = bufferLength - 1;
      const logMax = Math.log2(maxBin + 1);

      for (let i = 0; i < barCount; i++) {
        const t = barCount > 1 ? i / (barCount - 1) : 0;
        const binIndex = Math.min(Math.round(Math.pow(2, t * logMax) - 1), maxBin);
        const amplitude = gated ? 0 : dataArray[binIndex] / 255;

        const minH = height * 0.15;
        const barH = minH + amplitude * (height - minH);
        const x = gap + i * (barW + gap);
        const y = height - barH;

        ctx2d.fillStyle = color;
        ctx2d.fillRect(x, y, barW, barH);
      }

      animFrameRef.current = requestAnimationFrame(draw);
    }

    setup();

    return () => {
      stopped = true;
      cancelAnimationFrame(animFrameRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      audioCtxRef.current?.close();
      analyserRef.current = null;
      streamRef.current = null;
      audioCtxRef.current = null;
    };
  }, [active, barCount, color, gap, width, height]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width, height, display: "block" }}
    />
  );
}
