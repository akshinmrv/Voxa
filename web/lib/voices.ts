export type VoiceSample = { id: string; src: string };

/** OpenAI TTS voice samples shown on the landing (generated with tts-1-hd). */
export const VOICE_MODEL = "tts-1-hd";

export const VOICE_SAMPLES: VoiceSample[] = [
  { id: "alloy", src: "/tts-samples/alloy.mp3" },
  { id: "echo", src: "/tts-samples/echo.mp3" },
  { id: "fable", src: "/tts-samples/fable.mp3" },
  { id: "nova", src: "/tts-samples/nova.mp3" },
  { id: "onyx", src: "/tts-samples/onyx.mp3" },
  { id: "shimmer", src: "/tts-samples/shimmer.mp3" },
];
