import { useState, useRef, useEffect } from "react";

export function useScreenShare() {
  const [status, setStatus] = useState("idle"); // idle | checking | ready | error
  const [error, setError] = useState(null);
  const [stream, setStream] = useState(null);
  const [warnings, setWarnings] = useState(0);
  const [showWarning, setShowWarning] = useState(false);
  const [warningCountdown, setWarningCountdown] = useState(0);
  const streamRef = useRef(null);
  const warningIntervalRef = useRef(null);
  const onAutoSubmitRef = useRef(null);

  const MAX_WARNINGS = 3;
  const WARNING_DURATION = 3;

  const checkScreenShare = async () => {
    try {
      setStatus("checking");
      setError(null);
      // Request entire screen (displaySurface: 'monitor')
      const screenStream = await navigator.mediaDevices.getDisplayMedia({
        video: {
          displaySurface: "monitor",
          cursor: "always",
        },
        audio: false,
      });

      streamRef.current = screenStream;
      setStream(screenStream);
      setStatus("ready");

      // Stop stream if user stops sharing
      screenStream.getVideoTracks().forEach((track) => {
        track.onended = () => {
          setStream(null);
          setStatus("error");
          setError("Screen sharing stopped.");
        };
      });

      return true;
    } catch (err) {
      setStatus("error");
      setError(err.message || "Failed to start screen sharing.");
      return false;
    }
  };

  const stopScreenShare = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setStream(null);
      setStatus("idle");
    }
  };

  const handleVisibilityChange = (onAutoSubmit) => {
    onAutoSubmitRef.current = onAutoSubmit;
    if (document.hidden && warnings < MAX_WARNINGS) {
      // Tab changed - increment warning
      setWarnings((prev) => {
        const newCount = prev + 1;
        setShowWarning(true);
        setWarningCountdown(WARNING_DURATION);

        if (warningIntervalRef.current) {
          clearInterval(warningIntervalRef.current);
        }

        let countdown = WARNING_DURATION;
        warningIntervalRef.current = setInterval(() => {
          countdown -= 1;
          setWarningCountdown(countdown);
          if (countdown <= 0) {
            clearInterval(warningIntervalRef.current);
            setShowWarning(false);
          }
        }, 1000);

        return newCount;
      });
    } else if (document.hidden && warnings >= MAX_WARNINGS) {
      // Max warnings reached - auto submit
      if (onAutoSubmitRef.current) {
        onAutoSubmitRef.current(true); // true = banned
      }
    }
  };

  const resetWarnings = () => {
    setWarnings(0);
    setShowWarning(false);
    setWarningCountdown(0);
    if (warningIntervalRef.current) {
      clearInterval(warningIntervalRef.current);
    }
  };

  useEffect(() => {
    return () => {
      stopScreenShare();
      if (warningIntervalRef.current) {
        clearInterval(warningIntervalRef.current);
      }
    };
  }, []);

  return {
    status,
    error,
    stream,
    warnings,
    showWarning,
    warningCountdown,
    MAX_WARNINGS,
    checkScreenShare,
    stopScreenShare,
    handleVisibilityChange,
    resetWarnings,
  };
}
