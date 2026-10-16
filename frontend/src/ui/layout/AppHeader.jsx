import { Languages, Settings, UserRound } from "lucide-react";
import { getDefinitiveBrandMark } from "../../services/brandMark";

import { AppIconButton } from "../components/AppIconButton";
import { isDefinitiveAppExperience } from "../../services/localWeatherPilot";
import { CommunityAvatar } from "../../features/community/CommunityAvatar";

export function AppHeader({
  communityIdentity = null,
  copy,
  hidePilotProfileAction = false,
  language,
  navigationLocked = false,
  onLanguageChange,
  onSettingsOpen,
  profileStatus = "",
}) {
  const friulora = isDefinitiveAppExperience();
  const normalizedProfileStatus = ["alert", "location"].includes(profileStatus)
    ? profileStatus
    : "";
  const profileStatusLabel = normalizedProfileStatus
    ? language === "fur"
      ? normalizedProfileStatus === "alert"
        ? "alerte meteo ative"
        : "posizion automatiche ative"
      : normalizedProfileStatus === "alert"
        ? "allerta meteo attiva"
        : "posizione automatica attiva"
    : "";
  const profileButtonLabel = profileStatusLabel
    ? `${copy.settingsLabel}, ${profileStatusLabel}`
    : copy.settingsLabel;
  return (
    <header className="mf-app-header">
      <div
        className={`mf-brand${friulora ? " mf-brand--friulora" : ""}`}
        aria-label={friulora ? undefined : `${copy.brand.first} ${copy.brand.second}`}
      >
        <span className="mf-brand-mark" aria-hidden="true">
          <img alt="" src={friulora ? getDefinitiveBrandMark() : "/brand/logo-eagle-mark.webp"} />
        </span>
        <span className="mf-brand-copy">
          {friulora ? (
            <span className="mf-brand-title mf-brand-title--friulora">
              <span className="mf-brand-title__accessible">METEO FRIÛL</span>
              <span aria-hidden="true" className="mf-brand-title__visual">
                <span className="mf-brand-title__meteo">METEO</span>
                <span className="mf-brand-title__friul">
                  <span className="mf-brand-title__friul-word">
                    FRI
                    <span className="mf-brand-title__accented-u">
                      U
                      <svg
                        className="mf-brand-title__circumflex"
                        focusable="false"
                        viewBox="0 0 12 6"
                      >
                        <path d="M1 5 6 0.8 11 5" />
                      </svg>
                    </span>
                    L
                  </span>
                  <svg
                    className="mf-brand-title__underline"
                    focusable="false"
                    preserveAspectRatio="none"
                    viewBox="0 0 64 7"
                  >
                    <path d="M0.6 6.5C17 1.1 46 0.45 63.4 4.1C46 4.7 17 5.45 0.6 6.5Z" />
                  </svg>
                </span>
              </span>
            </span>
          ) : (
            <span className="mf-brand-title">
              <span>{copy.brand.first}</span>
              <span>{copy.brand.second}</span>
            </span>
          )}
          <span className="mf-brand-tagline">{friulora ? (language === "fur" ? "Meteo e events pal timp libar" : "Meteo ed eventi per il tempo libero") : copy.brandTagline}</span>
        </span>
      </div>
      <div className="mf-header-actions">
        {!friulora ? (
          <AppIconButton
            ariaLabel={copy.languageLabel}
            disabled={navigationLocked}
            icon={Languages}
            onClick={onLanguageChange}
            title={`${copy.languageLabel}: ${language.toUpperCase()}`}
          />
        ) : null}
        {friulora ? (
          hidePilotProfileAction ? null : (
            <button
              aria-label={profileButtonLabel}
              className="mf-icon-button mf-icon-button--ghost mf-header-profile-button"
              disabled={navigationLocked}
              onClick={onSettingsOpen}
              title={copy.settingsLabel}
              type="button"
            >
              {communityIdentity ? (
                <CommunityAvatar
                  className="mf-header-profile-button__avatar"
                  decorative
                  glyphScale={1.4}
                  identity={communityIdentity}
                  size={40}
                />
              ) : (
                <UserRound aria-hidden="true" size={21} strokeWidth={2.25} />
              )}
            </button>
          )
        ) : (
          <AppIconButton
            ariaLabel={copy.settingsLabel}
            disabled={navigationLocked}
            icon={Settings}
            onClick={onSettingsOpen}
            title={copy.settingsLabel}
          />
        )}
      </div>
    </header>
  );
}
