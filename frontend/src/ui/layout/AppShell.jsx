import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";

import {
  canStartPullRefresh,
  getPullRefreshEndState,
  getPullRefreshMoveState,
  getPullRefreshResultState,
  PULL_REFRESH_CONFIG,
  PULL_REFRESH_STATE,
} from "../../domain/runtime/pullRefreshPolicy";
import { AppHeader } from "./AppHeader";
import { BottomNavigation } from "./BottomNavigation";
import { isPullRefreshDisabled } from "./navigationLockPolicy";
import { getPullRefreshFeedbackLabel } from "./pullRefreshFeedback";

export function AppShell({
  activeTab,
  activeRoute,
  autoLocationEnabled = false,
  children,
  communityIdentity = null,
  communityReportsTotal = null,
  communityReportsUnread = false,
  copy,
  definitiveExperience = false,
  eventsPeriod = null,
  eventsTotal = null,
  fitMainViewport = false,
  language,
  labEnabled,
  nativeAndroid = false,
  navigationLocked = false,
  officialAlert = null,
  onLanguageChange,
  onLocationSearchOpen,
  onOfficialAlertOpen,
  onRuntimeRefresh,
  onSettingsOpen,
  onTabChange,
  tabs,
  theme = "light",
}) {
  const mainRef = useRef(null);
  const gestureRef = useRef({ active: false, distance: 0, startX: 0, startY: 0 });
  const navigationLockedRef = useRef(navigationLocked);
  const onRuntimeRefreshRef = useRef(onRuntimeRefresh);
  const resultTimerRef = useRef(null);
  const resetTimerRef = useRef(null);
  const stateRef = useRef(PULL_REFRESH_STATE.idle);
  const [pullRefresh, setPullRefresh] = useState({
    distance: 0,
    state: PULL_REFRESH_STATE.idle,
  });

  const setPullRefreshState = useCallback((nextState) => {
    stateRef.current = nextState.state;
    setPullRefresh(nextState);
  }, []);

  useEffect(() => {
    if (mainRef.current) {
      mainRef.current.scrollTop = 0;
    }
  }, [activeRoute]);

  useEffect(() => {
    onRuntimeRefreshRef.current = onRuntimeRefresh;
  }, [onRuntimeRefresh]);

  useEffect(() => {
    navigationLockedRef.current = navigationLocked;
  }, [navigationLocked]);

  useEffect(() => {
    const main = mainRef.current;
    if (!main) return undefined;

    const resetPullRefresh = (delayMs = 0) => {
      window.clearTimeout(resetTimerRef.current);
      resetTimerRef.current = window.setTimeout(() => {
        window.clearTimeout(resultTimerRef.current);
        gestureRef.current = { active: false, distance: 0, startX: 0, startY: 0 };
        setPullRefreshState({ distance: 0, state: PULL_REFRESH_STATE.idle });
      }, delayMs);
    };

    const showRefreshResult = (feedbackStartedAt, result) => {
      if (result?.status === "superseded" || result?.status === "skipped") {
        resetPullRefresh();
        return;
      }
      const elapsed = Date.now() - feedbackStartedAt;
      const loadingRemainder = Math.max(PULL_REFRESH_CONFIG.minFeedbackMs - elapsed, 0);

      window.clearTimeout(resultTimerRef.current);
      resultTimerRef.current = window.setTimeout(() => {
        setPullRefreshState(getPullRefreshResultState({
          offline: globalThis.navigator?.onLine === false,
          result,
        }));
        resetPullRefresh(PULL_REFRESH_CONFIG.resultFeedbackMs);
      }, loadingRemainder);
    };

    const handleTouchStart = (event) => {
      if (event.touches.length !== 1) return;
      if (stateRef.current !== PULL_REFRESH_STATE.idle) return;
      if (!canStartPullRefresh({
        disabled: isPullRefreshDisabled({
          navigationLocked: navigationLockedRef.current,
          onRuntimeRefresh: onRuntimeRefreshRef.current,
        }),
        scrollTop: main.scrollTop,
        target: event.target,
      })) {
        return;
      }

      const touch = event.touches[0];
      gestureRef.current = {
        active: true,
        distance: 0,
        startX: touch.clientX,
        startY: touch.clientY,
      };
    };

    const handleTouchMove = (event) => {
      const gesture = gestureRef.current;
      if (!gesture.active || event.touches.length !== 1) return;
      if (navigationLockedRef.current) {
        gestureRef.current = { active: false, distance: 0, startX: 0, startY: 0 };
        setPullRefreshState({ distance: 0, state: PULL_REFRESH_STATE.idle });
        return;
      }

      const touch = event.touches[0];
      const nextState = getPullRefreshMoveState({
        currentX: touch.clientX,
        currentY: touch.clientY,
        startX: gesture.startX,
        startY: gesture.startY,
      });

      if (nextState.state === PULL_REFRESH_STATE.cancelled) {
        gestureRef.current = { active: false, distance: 0, startX: 0, startY: 0 };
        setPullRefreshState({ distance: 0, state: PULL_REFRESH_STATE.idle });
        return;
      }

      if (nextState.state === PULL_REFRESH_STATE.idle) return;

      gestureRef.current = {
        ...gesture,
        distance: nextState.distance,
      };

      if (nextState.shouldPreventDefault && event.cancelable) {
        event.preventDefault();
      }

      setPullRefreshState({
        distance: nextState.distance,
        state: nextState.state,
      });
    };

    const handleTouchEnd = () => {
      const gesture = gestureRef.current;
      if (!gesture.active) return;

      if (navigationLockedRef.current) {
        gestureRef.current = { active: false, distance: 0, startX: 0, startY: 0 };
        setPullRefreshState({ distance: 0, state: PULL_REFRESH_STATE.idle });
        return;
      }

      const nextState = getPullRefreshEndState({ distance: gesture.distance });
      gestureRef.current = { active: false, distance: 0, startX: 0, startY: 0 };

      if (nextState.shouldRefresh) {
        setPullRefreshState({
          distance: nextState.distance,
          state: nextState.state,
        });
        const feedbackStartedAt = Date.now();
        const refreshResult = onRuntimeRefreshRef.current?.({ force: true, source: "pull" });

        if (refreshResult?.then) {
          refreshResult.then(
            (result) => showRefreshResult(feedbackStartedAt, result),
            () => showRefreshResult(feedbackStartedAt, { status: "failed" }),
          );
        } else {
          showRefreshResult(feedbackStartedAt, { status: "failed" });
        }
        return;
      }

      resetPullRefresh();
    };

    main.addEventListener("touchstart", handleTouchStart, { passive: true });
    main.addEventListener("touchmove", handleTouchMove, { passive: false });
    main.addEventListener("touchend", handleTouchEnd, { passive: true });
    main.addEventListener("touchcancel", handleTouchEnd, { passive: true });

    return () => {
      window.clearTimeout(resultTimerRef.current);
      window.clearTimeout(resetTimerRef.current);
      main.removeEventListener("touchstart", handleTouchStart);
      main.removeEventListener("touchmove", handleTouchMove);
      main.removeEventListener("touchend", handleTouchEnd);
      main.removeEventListener("touchcancel", handleTouchEnd);
    };
  }, [setPullRefreshState]);

  const pullRefreshCopy = copy.pullRefresh || {
    pull: "Trascina per aggiornare",
    loading: "Caricamento",
    success: "Aggiornato",
    failed: "Controlla la rete",
    release: "Rilascia per aggiornare",
  };
  const pullRefreshLabel = getPullRefreshFeedbackLabel(pullRefresh, pullRefreshCopy);
  const isPullRefreshStatus = [
    PULL_REFRESH_STATE.refreshing,
    PULL_REFRESH_STATE.success,
    PULL_REFRESH_STATE.partial,
    PULL_REFRESH_STATE.failed,
  ].includes(pullRefresh.state);

  return (
    <div
      className={`mf-app-shell lang-${language} theme-${theme}${definitiveExperience ? " is-definitive-app" : ""}${nativeAndroid ? " is-native-android" : ""}${labEnabled ? " is-lab" : ""}`}
      data-theme={theme}
    >
      <AppHeader
        communityIdentity={communityIdentity}
        copy={copy}
        hidePilotProfileAction={activeRoute === "settings"}
        language={language}
        navigationLocked={navigationLocked}
        onLanguageChange={onLanguageChange}
        onLocationSearchOpen={onLocationSearchOpen}
        onSettingsOpen={onSettingsOpen}
        profileStatus={officialAlert ? "alert" : autoLocationEnabled ? "location" : ""}
      />
      <main
        className={`mf-app-main${fitMainViewport ? " mf-app-main--territory-fit" : ""}`}
        ref={mainRef}
      >
        <div
          aria-hidden={pullRefresh.state === PULL_REFRESH_STATE.idle ? "true" : undefined}
          aria-live={isPullRefreshStatus ? "polite" : undefined}
          className={`mf-pull-refresh is-${pullRefresh.state}`}
          role={isPullRefreshStatus ? "status" : undefined}
          style={{ "--mf-pull-distance": `${pullRefresh.distance}px` }}
        >
          <span className="mf-pull-refresh__inner">
            <RefreshCw className="mf-pull-refresh__icon" aria-hidden="true" size={15} strokeWidth={2.4} />
            <span className="mf-pull-refresh__label">{pullRefreshLabel}</span>
          </span>
        </div>
        {children}
      </main>
      <BottomNavigation
        activeTab={activeTab}
        communityReportsTotal={communityReportsTotal}
        communityReportsUnread={communityReportsUnread}
        copy={copy}
        eventsPeriod={eventsPeriod}
        eventsTotal={eventsTotal}
        navigationLocked={navigationLocked}
        officialAlert={officialAlert}
        onOfficialAlertOpen={onOfficialAlertOpen}
        onTabChange={onTabChange}
        tabs={tabs}
      />
    </div>
  );
}
