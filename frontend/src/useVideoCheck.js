import { useCallback, useEffect, useRef, useState } from "react";

export function useVideoCheck() {
  const [status, setStatus] = useState("idle"); // idle | checking | ready | error
  const [error, setError] = useState("");
  const [stream, setStream] = useState(null);
  const videoRef = useRef(null);

  const stop = useCallback(() => {
    stream?.getTracks().forEach((t) => t.stop());
    setStream(null);
    if (videoRef.current) videoRef.current.srcObject = null;
  }, [stream]);

  const check = useCallback(async () => {
    setStatus("checking");
    setError("");
    stop();

    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("error");
      setError("Camera not supported in this browser.");
      return false;
    }

    try {
      const media = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
        audio: true,
      });

      const videoTrack = media.getVideoTracks()[0];
      if (!videoTrack || videoTrack.readyState !== "live" || !videoTrack.enabled) {
        media.getTracks().forEach((t) => t.stop());
        setStatus("error");
        setError("Camera is not active. Please enable your webcam.");
        return false;
      }

      setStream(media);
      setStatus("ready");
      return true;
    } catch (e) {
      setStatus("error");
      if (e.name === "NotAllowedError") {
        setError("Camera permission denied. Please allow camera access to continue.");
      } else if (e.name === "NotFoundError") {
        setError("No camera found. Connect a webcam to continue.");
      } else {
        setError(e.message || "Could not access camera.");
      }
      return false;
    }
  }, [stop]);

  useEffect(() => {
    if (stream && videoRef.current) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  useEffect(() => () => stop(), [stop]);

  return { status, error, stream, videoRef, check, stop };
}
