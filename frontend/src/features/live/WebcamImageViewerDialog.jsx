import { RotateCcw, X, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { usePilotBackHandler } from "../../app/usePilotBackHandler";
import { AppIconButton } from "../../ui/components/AppIconButton";
import {
  isolateCommunityModalBackground,
  trapCommunityModerationFocus,
} from "./communityModerationFocus";

const MIN_SCALE = 1;
const MAX_SCALE = 4;
const ZOOM_STEP = 0.5;
const WEBCAM_VIEWER_OPEN_CLASS = "mf-webcam-player-open";

function clamp(value, minimum, maximum) {
  return Math.min(maximum, Math.max(minimum, value));
}

function getContainedImageSize(viewport, image) {
  const viewportWidth = viewport?.clientWidth;
  const viewportHeight = viewport?.clientHeight;
  const naturalWidth = image?.naturalWidth;
  const naturalHeight = image?.naturalHeight;
  if (
    !Number.isFinite(viewportWidth)
    || viewportWidth <= 0
    || !Number.isFinite(viewportHeight)
    || viewportHeight <= 0
  ) {
    return { height: viewportHeight, width: viewportWidth };
  }
  if (
    !Number.isFinite(naturalWidth)
    || naturalWidth <= 0
    || !Number.isFinite(naturalHeight)
    || naturalHeight <= 0
  ) {
    return { height: viewportHeight, width: viewportWidth };
  }

  const containScale = Math.min(
    viewportWidth / naturalWidth,
    viewportHeight / naturalHeight,
  );
  return {
    height: naturalHeight * containScale,
    width: naturalWidth * containScale,
  };
}

function clampPanAxis(value, viewportSize, imageSize, scale) {
  if (scale <= MIN_SCALE) return 0;
  if (!Number.isFinite(viewportSize) || viewportSize <= 0) return value;

  const renderedImageSize = Number.isFinite(imageSize) && imageSize > 0
    ? imageSize
    : viewportSize;
  const limit = Math.max(0, (renderedImageSize * scale - viewportSize) / 2);
  return clamp(value, -limit, limit);
}

function constrainTransform(transform, viewport, image) {
  const scale = clamp(transform.scale, MIN_SCALE, MAX_SCALE);
  const imageSize = getContainedImageSize(viewport, image);
  return {
    scale,
    x: clampPanAxis(transform.x, viewport?.clientWidth, imageSize.width, scale),
    y: clampPanAxis(transform.y, viewport?.clientHeight, imageSize.height, scale),
  };
}

function readGesture(pointers) {
  const [first, second] = [...pointers.values()];
  if (!first) return null;
  if (!second) {
    return { center: first, distance: 0 };
  }

  return {
    center: {
      x: (first.x + second.x) / 2,
      y: (first.y + second.y) / 2,
    },
    distance: Math.hypot(second.x - first.x, second.y - first.y),
  };
}

function imageAlt(copy, camera) {
  const label = copy.webcamSnapshotImage || copy.webcamImageViewerTitle;
  return `${label}: ${camera.name}`;
}

export function WebcamImageViewerDialog({ camera, copy, imageUrl, onClose }) {
  usePilotBackHandler(onClose);
  const dialogRef = useRef(null);
  const imageRef = useRef(null);
  const viewportRef = useRef(null);
  const onCloseRef = useRef(onClose);
  const pointersRef = useRef(new Map());
  const gestureRef = useRef(null);
  const generatedId = useId();
  const titleId = `webcam-image-viewer-${generatedId}-title`;
  const [transform, setTransform] = useState({ scale: MIN_SCALE, x: 0, y: 0 });

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const documentLike = globalThis.document;
    if (!documentLike?.documentElement) return undefined;

    const previousFocus = documentLike.activeElement;
    const root = documentLike.documentElement;
    const wasAlreadyLocked = root.classList.contains(WEBCAM_VIEWER_OPEN_CLASS);
    const releaseBackground = isolateCommunityModalBackground(documentLike);
    root.classList.add(WEBCAM_VIEWER_OPEN_CLASS);

    const focusFrame = globalThis.requestAnimationFrame?.(
      () => dialogRef.current?.focus?.({ preventScroll: true }),
    );
    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current?.();
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
      if (!wasAlreadyLocked) root.classList.remove(WEBCAM_VIEWER_OPEN_CLASS);
      releaseBackground();
      globalThis.requestAnimationFrame?.(() => {
        if (previousFocus?.isConnected) previousFocus.focus?.({ preventScroll: true });
      });
    };
  }, []);

  useEffect(() => {
    const handleResize = () => {
      setTransform((current) => constrainTransform(
        current,
        viewportRef.current,
        imageRef.current,
      ));
    };
    globalThis.addEventListener?.("resize", handleResize);
    return () => globalThis.removeEventListener?.("resize", handleResize);
  }, []);

  const updateTransform = (updater) => {
    setTransform((current) => constrainTransform(
      updater(current),
      viewportRef.current,
      imageRef.current,
    ));
  };

  const resetTransform = () => {
    setTransform({ scale: MIN_SCALE, x: 0, y: 0 });
  };

  const zoomBy = (delta) => {
    updateTransform((current) => ({
      ...current,
      scale: current.scale + delta,
    }));
  };

  const handlePointerDown = (event) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;

    event.preventDefault();
    event.currentTarget.setPointerCapture?.(event.pointerId);
    pointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    gestureRef.current = readGesture(pointersRef.current);
  };

  const handlePointerMove = (event) => {
    if (!pointersRef.current.has(event.pointerId)) return;

    event.preventDefault();
    const previousGesture = gestureRef.current;
    pointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const nextGesture = readGesture(pointersRef.current);
    gestureRef.current = nextGesture;
    if (!previousGesture || !nextGesture) return;

    updateTransform((current) => {
      if (previousGesture.distance > 0 && nextGesture.distance > 0) {
        const viewportRect = viewportRef.current?.getBoundingClientRect?.();
        const scale = clamp(
          current.scale * (nextGesture.distance / previousGesture.distance),
          MIN_SCALE,
          MAX_SCALE,
        );
        const ratio = scale / current.scale;
        const viewportCenterX = (viewportRect?.left || 0) + (viewportRect?.width || 0) / 2;
        const viewportCenterY = (viewportRect?.top || 0) + (viewportRect?.height || 0) / 2;
        const previousOriginX = previousGesture.center.x - viewportCenterX;
        const previousOriginY = previousGesture.center.y - viewportCenterY;
        const nextOriginX = nextGesture.center.x - viewportCenterX;
        const nextOriginY = nextGesture.center.y - viewportCenterY;

        return {
          scale,
          x: nextOriginX - ratio * (previousOriginX - current.x),
          y: nextOriginY - ratio * (previousOriginY - current.y),
        };
      }

      return {
        ...current,
        x: current.x + nextGesture.center.x - previousGesture.center.x,
        y: current.y + nextGesture.center.y - previousGesture.center.y,
      };
    });
  };

  const handlePointerEnd = (event) => {
    if (!pointersRef.current.has(event.pointerId)) return;

    pointersRef.current.delete(event.pointerId);
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture?.(event.pointerId);
    }
    gestureRef.current = readGesture(pointersRef.current);
  };

  const handleWheel = (event) => {
    if (!event.deltaY) return;

    event.preventDefault();
    const viewportRect = viewportRef.current?.getBoundingClientRect?.();
    const originX = event.clientX - ((viewportRect?.left || 0) + (viewportRect?.width || 0) / 2);
    const originY = event.clientY - ((viewportRect?.top || 0) + (viewportRect?.height || 0) / 2);

    updateTransform((current) => {
      const scale = clamp(
        current.scale + (event.deltaY < 0 ? ZOOM_STEP / 2 : -ZOOM_STEP / 2),
        MIN_SCALE,
        MAX_SCALE,
      );
      const ratio = scale / current.scale;
      return {
        scale,
        x: originX - ratio * (originX - current.x),
        y: originY - ratio * (originY - current.y),
      };
    });
  };

  const zoomPercent = Math.round(transform.scale * 100);
  const isReset = transform.scale === MIN_SCALE && transform.x === 0 && transform.y === 0;
  const dialog = (
    <div className="mf-live-webcam-image-viewer-layer">
      <button
        aria-hidden="true"
        className="mf-live-webcam-image-viewer-layer__backdrop"
        onClick={() => onCloseRef.current?.()}
        tabIndex={-1}
        type="button"
      />
      <section
        aria-labelledby={titleId}
        aria-modal="true"
        className="mf-live-webcam-image-viewer"
        ref={dialogRef}
        role="dialog"
        tabIndex={-1}
      >
        <header className="mf-live-webcam-image-viewer__header">
          <div>
            <small>{copy.webcamImageViewerTitle}</small>
            <strong id={titleId}>{camera.name}</strong>
          </div>
          <AppIconButton
            ariaLabel={copy.webcamImageViewerClose}
            icon={X}
            onClick={() => onCloseRef.current?.()}
          />
        </header>
        <div
          className="mf-live-webcam-image-viewer__viewport"
          data-zoomed={transform.scale > MIN_SCALE ? "true" : "false"}
          onDoubleClick={resetTransform}
          onLostPointerCapture={handlePointerEnd}
          onPointerCancel={handlePointerEnd}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerEnd}
          onWheel={handleWheel}
          ref={viewportRef}
          style={{ touchAction: "none" }}
        >
          <img
            alt={imageAlt(copy, camera)}
            className="mf-live-webcam-image-viewer__image"
            draggable="false"
            onLoad={() => setTransform((current) => constrainTransform(
              current,
              viewportRef.current,
              imageRef.current,
            ))}
            ref={imageRef}
            referrerPolicy={camera.mediaType === "snapshot" ? "no-referrer" : undefined}
            src={imageUrl}
            style={{
              transform: `translate3d(${transform.x}px, ${transform.y}px, 0) scale(${transform.scale})`,
            }}
          />
        </div>
        <footer
          aria-label={copy.webcamImageViewerTitle}
          className="mf-live-webcam-image-viewer__controls"
          role="group"
        >
          <AppIconButton
            ariaLabel={copy.webcamImageZoomOut}
            disabled={transform.scale <= MIN_SCALE}
            icon={ZoomOut}
            onClick={() => zoomBy(-ZOOM_STEP)}
          />
          <output
            aria-atomic="true"
            aria-live="polite"
            className="mf-live-webcam-image-viewer__zoom-value"
          >
            {zoomPercent}%
          </output>
          <AppIconButton
            ariaLabel={copy.webcamImageZoomReset}
            disabled={isReset}
            icon={RotateCcw}
            onClick={resetTransform}
          />
          <AppIconButton
            ariaLabel={copy.webcamImageZoomIn}
            disabled={transform.scale >= MAX_SCALE}
            icon={ZoomIn}
            onClick={() => zoomBy(ZOOM_STEP)}
          />
        </footer>
      </section>
    </div>
  );

  return globalThis.document?.body
    ? createPortal(dialog, globalThis.document.body)
    : dialog;
}
