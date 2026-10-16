import { ExternalLink, X } from "lucide-react";
import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { usePilotBackHandler } from "../../app/usePilotBackHandler";

import { AppIconButton } from "../../ui/components/AppIconButton";
import {
  isolateCommunityModalBackground,
  trapCommunityModerationFocus,
} from "./communityModerationFocus";
import { subscribeToWebcamPlayerBackgroundClose } from "./webcamPlayerLifecycle";

const WEBCAM_PLAYER_OPEN_CLASS = "mf-webcam-player-open";

export function WebcamPlayerDialog({ camera, copy, onClose }) {
  usePilotBackHandler(onClose);
  const dialogRef = useRef(null);
  const onCloseRef = useRef(onClose);
  const generatedId = useId();
  const titleId = `webcam-player-${generatedId}-title`;

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const documentLike = globalThis.document;
    if (!documentLike?.documentElement) return undefined;

    const previousFocus = documentLike.activeElement;
    const root = documentLike.documentElement;
    const wasAlreadyLocked = root.classList.contains(WEBCAM_PLAYER_OPEN_CLASS);
    const releaseBackground = isolateCommunityModalBackground(documentLike);
    const releaseBackgroundClose = subscribeToWebcamPlayerBackgroundClose({
      documentRef: documentLike,
      onClose: () => onCloseRef.current(),
      windowRef: globalThis.window,
    });
    root.classList.add(WEBCAM_PLAYER_OPEN_CLASS);

    const focusFrame = globalThis.requestAnimationFrame?.(
      () => dialogRef.current?.focus?.({ preventScroll: true }),
    );
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }

      trapCommunityModerationFocus(
        event,
        dialogRef.current,
        documentLike.activeElement,
      );
    };

    documentLike.addEventListener("keydown", handleKeyDown);

    return () => {
      if (focusFrame !== undefined) globalThis.cancelAnimationFrame?.(focusFrame);
      documentLike.removeEventListener("keydown", handleKeyDown);
      releaseBackgroundClose();
      if (!wasAlreadyLocked) root.classList.remove(WEBCAM_PLAYER_OPEN_CLASS);
      releaseBackground();
      globalThis.requestAnimationFrame?.(() => {
        if (previousFocus?.isConnected) previousFocus.focus?.({ preventScroll: true });
      });
    };
  }, []);

  const dialog = (
    <div className="mf-live-webcam-player-layer">
      <button
        aria-hidden="true"
        className="mf-live-webcam-player-layer__backdrop"
        onClick={() => onCloseRef.current()}
        tabIndex={-1}
        type="button"
      />
      <section
        aria-labelledby={titleId}
        aria-modal="true"
        className="mf-live-webcam-player"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <header className="mf-live-webcam-player__header">
          <div>
            <small>{copy.webcamLiveDialogTitle}</small>
            <strong id={titleId}>{camera.name}</strong>
          </div>
          <AppIconButton
            ariaLabel={copy.webcamLiveClose}
            icon={X}
            onClick={() => onCloseRef.current()}
          />
        </header>
        <div className="mf-live-webcam-player__frame">
          <iframe
            allow="fullscreen"
            allowFullScreen
            loading="eager"
            referrerPolicy="no-referrer"
            sandbox="allow-same-origin allow-scripts"
            src={camera.playerUrl}
            title={`${copy.webcamLiveDialogTitle}: ${camera.name}`}
          />
        </div>
        {camera.sourceUrl ? (
          <footer className="mf-live-webcam-player__footer">
            <a
              href={camera.sourceUrl}
              rel="noopener noreferrer"
              target="_blank"
            >
              <span>{copy.webcamLiveExternal}</span>
              <ExternalLink aria-hidden="true" size={17} strokeWidth={2.3} />
            </a>
          </footer>
        ) : null}
      </section>
    </div>
  );

  return globalThis.document?.body
    ? createPortal(dialog, globalThis.document.body)
    : dialog;
}
