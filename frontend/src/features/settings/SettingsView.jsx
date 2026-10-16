import { useEffect, useRef, useState } from "react";
import { getDefinitiveBrandMark } from "../../services/brandMark";
import { isDefinitiveAppExperience } from "../../services/localWeatherPilot";
import { registerPilotBackHandler } from "../../services/pilotBackNavigation";

import {
  AlertTriangle,
  ArrowLeft,
  BellRing,
  ChevronRight,
  ChevronLeft,
  Eraser,
  ExternalLink,
  HeartHandshake,
  Info,
  Languages,
  Loader2,
  MapPin,
  Navigation,
  Palette,
  Pencil,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";

import { DEFAULT_NOTIFICATION_PREFERENCES } from "../../app/notificationPreferences";
import { sanitizeWebPushErrorCode } from "../../services/firebaseWebMessaging";
import { toPushRegistrationNationalManualMunicipality } from "../../services/pushDeviceRegistration";
import {
  fetchCommunityReputation,
  readExistingLiveReportClientId,
} from "../../services/liveApi";
import {
  getAutomaticLocationToggleAction,
  getNotificationToggleAction,
} from "./notificationToggleAction";
import {
  getConfiguredSupportUrl,
  normalizeSupportUrl,
} from "../../services/supportLink";
import {
  getLocationDisplayName,
  getMunicipalityDisplayName,
} from "../../domain/geo/locationDisplayName";
import { getLocationMunicipality } from "../../domain/geo/locationIdentity";
import { TabPage } from "../../ui/layout/TabPage";
import {
  readCommunityIdentity,
  regenerateCommunityIdentity,
} from "../community/communityIdentity";
import { normalizeCommunityReputation } from "../community/communityReputation";
import { CommunityAvatar } from "../community/CommunityAvatar";

const COPY = {
  it: {
    title: "Impostazioni",
    backHome: "Indietro",
    sections: {
      general: "Preferenze generali",
      location: "Località",
      notifications: "Notifiche",
      project: "Info e progetto",
      support: "Sostieni Meteo Friûl",
      information: "Informazioni",
    },
    actions: {
      changeLocation: "Cambia",
      manage: "Gestisci",
      resetCache: "Svuota",
      disable: "Disattiva",
      enable: "Attiva",
      disablePosition: "Disattiva",
      usePosition: "Usa posizione",
    },
    language: {
      title: "Lingua",
      it: "Italiano",
      fur: "Furlan",
    },
    theme: {
      title: "Tema",
      light: "Chiaro",
      dark: "Scuro",
      system: "Sistema",
    },
    profile: {
      totalReports: "Inviate: {count}",
      aliasChanged: "Nuovo alias: {alias}",
      changeAlias: "Cambia alias",
      label: "Profilo community anonimo",
      localAlias: "Sentinella Meteo",
      pendingReports: "Segnalazioni in attesa: {count}",
      pointsAbbreviation: "pt",
      rulesTitle: "Sentinelle, alias e punti",
      closeHelp: "Chiudi informazioni",
      sentinelsHelp: <>Le <strong>Sentinelle Meteo</strong> sono le persone che condividono ciò che osservano nella propria zona.</>,
      aliasHelp: <>Il tuo <strong>alias</strong> è un nome di fantasia in friulano, accompagnato da un’icona. Compare sulle tue segnalazioni e puoi cambiarlo senza perdere punti o storico.</>,
      observersHelp: "Nelle schede, le icone rappresentano chi ha inviato le osservazioni. Toccale per leggere tutti gli alias.",
      rulesSubtitle: "Inviate, Confermate e Punti",
      rulesBody: "Inviate: ogni osservazione accettata. Confermate: quelle convalidate da un’altra installazione, anche senza premio. Un punto per segnalazione convalidata; per lo stesso fenomeno e Comune, 3 ore dall’ultimo punto. Nessun tetto giornaliero ai punti. Tranquillo e il solo voto non danno punti. I ranghi sono estetici e cambiano a 5 e 15 punti.",
      privacy: "Senza registrazione • Nome ed email non richiesti",
      rankDetail: "Rango {rank}: {points} punti convalidati",
      rankUnavailable: "Rango non disponibile",
      ranks: {
        lookout: "Vuaite dal Timp",
        novice: "Osservadôr dal Cîl",
        sentinel: "Sentinele dal Teritori",
      },
      validatedReports: "Confermate: {count}",
    },
    rows: {
      activeCity: ["Località", "Udine"],
      defaultLocation: "Località predefinita",
      activeMunicipality: "Comune di {name}{province}",
      automaticLocation: "Posizione",
      backgroundLocation: {
        active: "Attiva anche ad app chiusa",
        checking: "Attiva",
        error: "Posizione in background temporaneamente non disponibile.",
        label: "Posizione sempre",
        permission: "Consenti sempre",
        requiresAutomaticLocation: "Attiva Posizione automatica",
      },
      deviceLocation: ["Posizione", "Non rilevata"],
      deviceLocationActive: "Attiva",
      deviceLocationDenied: "Permesso negato",
      deviceLocationError: "Non disponibile",
      deviceLocationLoading: "Ricerca posizione",
      deviceLocationLastKnown: "Ultima rilevazione: {city}",
      deviceLocationOutsideFvg: "Fuori FVG",
      deviceLocationSuccess: "Attiva",
      runtimeCache: ["Cache", ""],
      appVersion: {
        title: "Versione",
        preview: "Anteprima Web",
        unavailable: "Non disponibile",
      },
      runtimeCacheCleared: "Cache svuotata",
      runtimeCacheClearing: "Svuotamento in corso…",
      runtimeCacheFailed: "Pulizia incompleta. Riprova.",
      officialAlerts: "Allerte",
      officialAlertsUnavailable: "Disponibili solo in Friuli Venezia Giulia",
      nationalOfficialAlerts: "Allerte per {name}",
      nationalOfficialAlertsDetail: "Segui le allerte ufficiali del Comune scelto. Non segue la posizione GPS.",
      nationalOfficialAlertsManualRequired: "Fuori FVG scegli un Comune dalla ricerca aggiornata: deve avere un codice ISTAT verificato per seguirne le allerte.",
      localAlerts: "Avvisi",
      notificationRuntime: {
        androidUnavailable: "Le notifiche non sono disponibili in questa build Android.",
        authorize: "Autorizza notifiche",
        connecting: "Collegamento notifiche in corso.",
        connected: "Allerte e Avvisi meteo attivi su questo dispositivo.",
        connectedOfficial: "Allerte attive su questo dispositivo.",
        connectedWeather: "Avvisi meteo attivi su questo dispositivo.",
        connectedLocalPending: "Allerte attive. Per ricevere gli Avvisi scegli un Comune valido o aggiorna la posizione.",
        connectedLocalOnlyPending: "Per ricevere gli Avvisi scegli un Comune valido o aggiorna la posizione.",
        denied: "Notifiche bloccate nelle impostazioni Android.",
        deniedWeb: "Notifiche bloccate nelle impostazioni del browser per questo sito.",
        disabled: "Notifiche disattivate su questo dispositivo.",
        error: "Collegamento non riuscito. Riproveremo automaticamente.",
        errorCategories: {
          app_check: "La verifica di sicurezza App Check non è riuscita. Consenti gli script per questo sito e riprova.",
          backend: "Il servizio non ha accettato la registrazione. Riproveremo automaticamente.",
          browser: "Questo browser non può completare la registrazione delle notifiche.",
          client: "La configurazione delle notifiche è incompleta e deve essere corretta.",
          fcm: "Firebase non ha completato la registrazione delle notifiche. Riproveremo automaticamente.",
          network: "Il browser non raggiunge il servizio notifiche. Controlla rete, VPN o blocchi privacy e riprova.",
          policy: "Le notifiche Web non sono abilitate dal servizio in questa fase.",
          permission: "Il browser non ha concesso il permesso per le notifiche.",
          service_worker: "Il componente notifiche del browser non si è attivato. Aggiorna la pagina e riprova.",
          storage: "Il browser non può salvare la registrazione. Esci dalla navigazione privata o consenti i dati del sito.",
          vapid: "La chiave pubblica delle notifiche non è stata accettata e deve essere corretta.",
        },
        errorReference: "Riferimento tecnico",
        permissionRequired: "Autorizza le notifiche per ricevere Allerte e Avvisi su questo dispositivo.",
        webEnrollmentDisabled: "Le notifiche Web non sono attive in questa fase. Per ricevere allerte e avvisi usa l'app Android Meteo Friûl.",
        webBadge: "Solo nell’app Android",
        webNotConfigured: "Le notifiche Web non sono attive in questa fase. Per ricevere allerte e avvisi usa l'app Android Meteo Friûl.",
        webUnsupported: "Questo browser non supporta le notifiche web in modo sicuro.",
      },
      product: {
        name: "Meteo Friûl",
        site: "meteofriul.it",
        siteLabel: "Apri il sito Meteo Friûl",
      },
      privacy: {
        description: "Dati, permessi, contenuti e immagini",
        label: "Apri l’informativa privacy, fonti e crediti",
        title: "Informativa privacy, fonti e crediti",
      },
      support: {
        body: "Se Meteo Friûl ti è utile, puoi contribuire volontariamente ai costi dei servizi e al lavoro necessario per mantenerla attiva, affidabile e aggiornata.",
        promise: "Nessuna funzione riservata: l'app resta uguale per tutti.",
        action: "Sostieni su Ko-fi",
        status: "Contributi non ancora attivi",
        compactBody: "Aiuta Meteo Friûl a restare attiva, affidabile e aggiornata.",
      },
    },
  },
  fur: {
    title: "Impostazions",
    backHome: "Indaûr",
    sections: {
      general: "Preferencis gjenerâls",
      location: "Localitât",
      notifications: "Notifichis",
      project: "Informazions e progjet",
      support: "Sosten Meteo Friûl",
      information: "Informazions",
    },
    actions: {
      changeLocation: "Cambie",
      manage: "Gjestìs",
      resetCache: "Nete",
      disable: "Disative",
      enable: "Ative",
      disablePosition: "Disative",
      usePosition: "Dopre posizion",
    },
    language: {
      title: "Lenghe",
      it: "Italian",
      fur: "Furlan",
    },
    theme: {
      title: "Teme",
      light: "Clâr",
      dark: "Scûr",
      system: "Sisteme",
    },
    profile: {
      totalReports: "Mandadis: {count}",
      rulesTitle: "Sentinelis, alias e ponts",
      closeHelp: "Siere informazions",
      sentinelsHelp: <>Lis <strong>Sentinelis Meteo</strong> a son lis personis che a condividin ce che a osservin te lôr zone.</>,
      aliasHelp: <>Il to <strong>alias</strong> al è un non di fantasie in furlan, compagnât di une icone. Al comparìs su lis tôs segnalazions e tu puedis cambiâlu cence pierdi ponts o storic.</>,
      observersHelp: "Tes schedis, lis iconis a rapresentin cui che al à mandât lis osservazions. Selezione lis iconis par lei ducj i alias.",
      rulesSubtitle: "Mandadis, Confermadis e Ponts",
      rulesBody: "Mandadis: ogni osservazion acetade. Confermadis: chês convalidadis di une altre instalazion, ancje cence premi. Un pont par segnalazion convalidade; pal stes fenomen e Comun, 3 oris dal ultin pont. Nissun limit zornaliêr ai ponts. Trancuil e il sôl vôt no dan ponts. I rancs a son estetics e a cambiin a 5 e 15 ponts.",
      aliasChanged: "Gnûf alias: {alias}",
      changeAlias: "Cambie alias",
      label: "Profîl community anonim",
      localAlias: "Sentinele Meteo",
      pendingReports: "Segnalazions in spiete: {count}",
      pointsAbbreviation: "pt",
      privacy: "Cence regjistrazion • Non e e-mail no coventin",
      rankDetail: "Ranc {rank}: {points} ponts convalidâts",
      rankUnavailable: "Ranc no disponibil",
      ranks: {
        lookout: "Vuaite dal Timp",
        novice: "Osservadôr dal Cîl",
        sentinel: "Sentinele dal Teritori",
      },
      validatedReports: "Confermadis: {count}",
    },
    rows: {
      backgroundLocation: {
        active: "Ative ancje cu la app sierade",
        checking: "Ative",
        error: "Posizion in sotfont no disponibile pal moment.",
        label: "Posizion simpri",
        permission: "Permet simpri",
        requiresAutomaticLocation: "Ative Posizion automatiche",
      },
      deviceLocationActive: "Ative",
      deviceLocationDenied: "Permes negat",
      deviceLocationError: "No disponibile",
      deviceLocationLoading: "O cir la posizion",
      deviceLocationLastKnown: "Ultime rilevazion: {city}",
      deviceLocationOutsideFvg: "Fur dal FVG",
      deviceLocationSuccess: "Ative",
      runtimeCache: ["Cache", ""],
      runtimeCacheCleared: "Cache netade",
      runtimeCacheClearing: "O neti la cache…",
      runtimeCacheFailed: "Nete incompletade. Torne prove.",
      appVersion: {
        title: "Version",
        preview: "Anteprime Web",
        unavailable: "No disponibile",
      },
      activeCity: ["Localitât", "Udin"],
      defaultLocation: "Localitât predefinide",
      activeMunicipality: "Comun di {name}{province}",
      automaticLocation: "Posizion",
      deviceLocation: ["Posizion", "No ative"],
      officialAlerts: "Alertis",
      officialAlertsUnavailable: "Disponibilis dome in Friûl Vignesie Julie",
      nationalOfficialAlerts: "Alertis par {name}",
      nationalOfficialAlertsDetail: "Seguìs lis alertis uficiâls dal Comun sielzût. No seguìs la posizion GPS.",
      nationalOfficialAlertsManualRequired: "Fûr dal FVG sielç un Comun de ricercje inzornade: il codiç ISTAT al à di jessi verificât par seguî lis sôs alertis.",
      localAlerts: "Avîs",
      notificationRuntime: {
        androidUnavailable: "Lis notifichis no son disponibilis in cheste build Android.",
        authorize: "Autorize lis notifichis",
        connecting: "Daûr a colegâ lis notifichis.",
        connected: "Alertis e Avîs meteo atîfs su chest dispositîf.",
        connectedOfficial: "Alertis ativis su chest dispositîf.",
        connectedWeather: "Avîs meteo atîfs su chest dispositîf.",
        connectedLocalPending: "Alertis ativis. Par ricevi i Avîs sielç un Comun valit o inzorne la posizion.",
        connectedLocalOnlyPending: "Par ricevi i Avîs sielç un Comun valit o inzorne la posizion.",
        denied: "Notifichis blocadis tes impostazions Android.",
        deniedWeb: "Notifichis blocadis tes impostazions dal navigadôr par chest sît.",
        disabled: "Notifichis disativadis su chest dispositîf.",
        error: "No si è rivâts a colegâsi. O tornarìn a provâ in automatic.",
        errorCategories: {
          app_check: "La verifiche di sigurece App Check no je lade a bon fin. Permet i script par chest sît e torne prove.",
          backend: "Il servizi nol à acetât la regjistrazion. O tornarìn a provâ in automatic.",
          browser: "Chest navigadôr nol pues completâ la regjistrazion des notifichis.",
          client: "La configurazion des notifichis no je complete e e à di jessi corete.",
          fcm: "Firebase nol à completât la regjistrazion des notifichis. O tornarìn a provâ in automatic.",
          network: "Il navigadôr nol rive al servizi notifichis. Controle la rêt, la VPN o i blocs di privacy e torne prove.",
          policy: "Lis notifichis Web no son abilitadis dal servizi in cheste fase.",
          permission: "Il navigadôr nol à concedût il permès pes notifichis.",
          service_worker: "Il component notifichis dal navigadôr no si è ativât. Inzorne la pagjine e torne prove.",
          storage: "Il navigadôr nol pues salvâ la regjistrazion. Jes de navigazion privade o permet i dâts dal sît.",
          vapid: "La clâf publiche des notifichis no je stade acetade e e à di jessi corete.",
        },
        errorReference: "Riferiment tecnic",
        permissionRequired: "Autorize lis notifichis par ricevi Alertis e Avîs su chest dispositîf.",
        webEnrollmentDisabled: "Lis notifichis Web no son ativis in cheste fase. Par ricevi lis alertis e i avîs dopre la app Android Meteo Friûl.",
        webBadge: "Dome te app Android",
        webNotConfigured: "Lis notifichis Web no son ativis in cheste fase. Par ricevi lis alertis e i avîs dopre la app Android Meteo Friûl.",
        webUnsupported: "Chest navigadôr nol supuarte lis notifichis web in mût sigûr.",
      },
      product: {
        name: "Meteo Friûl",
        site: "meteofriul.it",
        siteLabel: "Vierç il sît Meteo Friûl",
      },
      privacy: {
        description: "Dâts, permès, contignûts e imagjins",
        label: "Vierç la informative su la privacy, fonts e credits",
        title: "Informative su la privacy, fonts e credits",
      },
      support: {
        body: "Se Meteo Friûl ti covente, tu puedis contribuî in mût volontari ai coscj dai servizis e al lavôr necessari par mantignîlu atîf, afidabil e inzornât.",
        promise: "Nissune funzion riservade: la app e reste compagne par ducj.",
        action: "Sosten su Ko-fi",
        status: "I contribûts no son ancjemò atîfs",
        compactBody: "Jude Meteo Friûl a restâ atîf, afidabil e inzornât.",
      },
    },
  },
};

const THEME_OPTIONS = ["light", "dark", "system"];

function getCopy(language) {
  return COPY[language === "fur" ? "fur" : "it"];
}

function OptionButton({ children, isActive, onClick }) {
  return (
    <button
      aria-pressed={isActive}
      className={`mf-settings-segment${isActive ? " is-active" : ""}`}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  );
}

function SettingsChoiceRow({ icon: Icon, label, onSelect, options, value, variant }) {
  return (
    <div className={`mf-settings-choice-row mf-settings-choice-row--${variant}`}>
      <span className="mf-settings-row__icon">
        <Icon aria-hidden="true" size={19} strokeWidth={2.25} />
      </span>
      <span className="mf-settings-row__label">{label}</span>
      <div
        aria-label={label}
        className={`mf-settings-segments mf-settings-segments--inline mf-settings-segments--${variant}`}
        role="group"
      >
        {options.map((option) => (
          <OptionButton
            isActive={value === option.value}
            key={option.value}
            onClick={() => onSelect?.(option.value)}
          >
            {option.label}
          </OptionButton>
        ))}
      </div>
    </div>
  );
}

function SettingsRow({
  actionBusy = false,
  actionDisabled = false,
  actionIcon: ActionIcon,
  actionLabel,
  description,
  detail,
  icon: Icon,
  onAction,
  title,
  variant,
}) {
  const hasAction = Boolean(actionLabel && onAction);
  const hasDescription = Boolean(description);
  const hasDetail = Boolean(detail);
  const EffectiveActionIcon = actionBusy ? Loader2 : ActionIcon;
  const rowClassName = [
    "mf-settings-row",
    hasAction && "mf-settings-row--with-action",
    !hasDetail && "mf-settings-row--without-value",
    hasDescription && "mf-settings-row--with-description",
    variant && `mf-settings-row--${variant}`,
  ].filter(Boolean).join(" ");

  return (
    <div className={rowClassName}>
      <span className="mf-settings-row__icon">
        <Icon aria-hidden="true" size={19} strokeWidth={2.25} />
      </span>
      <span className="mf-settings-row__label">{title}</span>
      {hasDescription ? <span className="mf-settings-row__description">{description}</span> : null}
      {hasDetail ? <span className="mf-settings-row__value">{detail}</span> : null}
      {hasAction ? (
        <button
          aria-label={actionLabel}
          aria-busy={actionBusy || undefined}
          className="mf-settings-row__action"
          data-tooltip={actionLabel}
          disabled={actionDisabled}
          onClick={onAction}
          title={actionLabel}
          type="button"
        >
          {EffectiveActionIcon ? (
            <span className="mf-settings-row__action-icon">
              <EffectiveActionIcon
                aria-hidden="true"
                className={actionBusy ? "mf-settings-row__action-spinner" : undefined}
                size={15}
                strokeWidth={2.35}
              />
            </span>
          ) : null}
        </button>
      ) : null}
    </div>
  );
}

function SettingsPanel({ children, icon: Icon, title, variant }) {
  const className = ["mf-settings-panel", variant ? `mf-settings-panel--${variant}` : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <section className={className}>
      {Icon && title ? (
        <div className="mf-settings-panel__heading">
          <Icon
            aria-hidden="true"
            className="mf-settings-panel__leading-icon"
            size={27}
            strokeWidth={2}
          />
          <h2>{title}</h2>
        </div>
      ) : (
        <>
          {Icon ? (
            <Icon
              aria-hidden="true"
              className="mf-settings-panel__leading-icon"
              size={30}
              strokeWidth={2}
            />
          ) : null}
          {title ? <h2>{title}</h2> : null}
        </>
      )}
      {children}
    </section>
  );
}

function PilotIdentityCard({
  alias,
  animating = false,
  copy,
  identity,
  notice,
  onRegenerate,
  reputation,
  totalReports,
}) {
  const helpDialog = useRef(null);
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => {
    if (!helpOpen) return undefined;
    return registerPilotBackHandler(() => {
      helpDialog.current?.close();
      setHelpOpen(false);
    });
  }, [helpOpen]);

  return (
    <section
      aria-labelledby="mf-settings-community-alias"
      className={`mf-settings-identity${animating ? " is-changing" : ""}`}
    >
      <span aria-hidden="true" className="mf-settings-identity__avatar">
        <CommunityAvatar decorative identity={identity} size={52} />
      </span>
      <span className="mf-settings-identity__body">
        <small>{copy.localAlias}</small>
        <span className="mf-settings-identity__headline">
          <strong id="mf-settings-community-alias">{alias}</strong>
          <button
            aria-label={copy.changeAlias}
            className="mf-settings-identity__refresh"
            onClick={onRegenerate}
            title={copy.changeAlias}
            type="button"
          >
            <RefreshCw aria-hidden="true" size={18} strokeWidth={2.35} />
          </button>
        </span>
      </span>
      <span className="mf-settings-identity__stats">
        <PilotReputationStat copy={copy} reputation={reputation} />
        <PilotIdentityStat count={totalReports} template={copy.totalReports} />
        {reputation?.validatedReports != null ? <PilotIdentityStat count={reputation.validatedReports} template={copy.validatedReports} /> : null}
        <button
          aria-label={copy.rulesTitle}
          aria-haspopup="dialog"
          className="mf-settings-identity__info"
          onClick={() => {
            helpDialog.current?.showModal();
            setHelpOpen(true);
          }}
          title={copy.rulesTitle}
          type="button"
        >
          <Info aria-hidden="true" size={20} />
        </button>
      </span>
      <dialog
        aria-labelledby="mf-settings-community-help-title"
        className="mf-settings-community-help"
        onClose={() => setHelpOpen(false)}
        ref={helpDialog}
      >
        <header>
          <h2 id="mf-settings-community-help-title">{copy.rulesTitle}</h2>
          <button
            aria-label={copy.closeHelp}
            className="mf-settings-community-help__close"
            onClick={() => helpDialog.current?.close()}
            type="button"
          >
            <X aria-hidden="true" size={22} />
          </button>
        </header>
        <div className="mf-settings-community-help__body">
          <p>{copy.sentinelsHelp}</p>
          <p>{copy.aliasHelp}</p>
          <p>{copy.observersHelp}</p>
          <p className="mf-settings-identity__privacy">
            <ShieldCheck aria-hidden="true" size={15} />
            {copy.privacy}
          </p>
          <h3>{copy.rulesSubtitle}</h3>
          <p>{copy.rulesBody}</p>
        </div>
      </dialog>
      {notice ? (
        <span
          aria-live="polite"
          className="mf-settings-identity__notice"
          role="status"
        >
          {notice}
        </span>
      ) : null}
    </section>
  );
}

function PilotReputationStat({ copy, reputation }) {
  if (!reputation) {
    return (
      <span className="mf-settings-identity__reputation is-unavailable">
        {copy.rankUnavailable}
      </span>
    );
  }

  const rank = copy.ranks[reputation.rank.id] || copy.rankUnavailable;
  const detail = [
    formatTemplate(copy.rankDetail, {
      points: reputation.points,
      rank,
    }),
    reputation.validatedReports === null
      ? ""
      : formatTemplate(copy.validatedReports, { count: reputation.validatedReports }),
    reputation.pendingReports === null
      ? ""
      : formatTemplate(copy.pendingReports, { count: reputation.pendingReports }),
  ].filter(Boolean).join(". ");

  return (
    <span
      aria-label={detail}
      className={`mf-settings-identity__reputation mf-settings-identity__reputation--${reputation.rank.id}`}
      title={detail}
    >
      <span aria-hidden="true">🏆</span>
      <strong className="mf-settings-identity__rank">{rank}</strong>
      <span aria-hidden="true">·</span>
      <strong className="mf-settings-identity__stat-value">{reputation.points}</strong>
      <span>{copy.pointsAbbreviation}</span>
    </span>
  );
}

function PilotIdentityStat({ count, template }) {
  const marker = "{count}";
  const markerIndex = template.indexOf(marker);

  if (markerIndex < 0) {
    return <span>{formatTemplate(template, { count })}</span>;
  }

  const prefix = template.slice(0, markerIndex);
  const suffix = template.slice(markerIndex + marker.length);

  return (
    <span>
      {prefix}
      <strong className="mf-settings-identity__stat-value">{count}</strong>
      {suffix}
    </span>
  );
}

function ProductLink({ copy }) {
  return (
    <a
      aria-label={copy.siteLabel}
      className="mf-settings-product-link mf-settings-product-link--brand"
      href="https://meteofriul.it"
      rel="noreferrer"
      target="_blank"
    >
      <img
        alt=""
        className="mf-settings-product-link__icon"
        height="48"
        src={isDefinitiveAppExperience() ? getDefinitiveBrandMark() : "/branding/icon_launcher_any_mf-r5-20260927-192.png"}
        width="48"
      />
      <span className="mf-settings-product-link__body">
        <strong>{copy.name}</strong>
        <span>{copy.site}</span>
      </span>
      <ExternalLink aria-hidden="true" size={18} strokeWidth={2.2} />
    </a>
  );
}

function AppVersionRow({ copy, info }) {
  const version = String(info?.version || "").trim();
  const hasVersion = version && version.toLowerCase() !== "unknown";
  const isAndroid = info?.platform === "android";
  if (isAndroid && hasVersion) {
    return (
      <footer className="mf-settings-version">
        {version.replace(/\+\d+$/, "")}
      </footer>
    );
  }

  const detail = hasVersion ? version : copy.unavailable;
  const platform = isAndroid ? "Android" : info?.development ? copy.preview : "Web";

  return (
    <footer className="mf-settings-version">
      <span>{copy.title}</span>{" "}<span>{detail}</span>{" · "}<span>{platform}</span>
    </footer>
  );
}

function PrivacyPolicyLink({ copy, language }) {
  const url = language === "fur"
    ? "https://meteofriul.it/fur/privacy/"
    : "https://meteofriul.it/privacy/";

  return (
    <a
      aria-label={copy.label}
      className="mf-settings-product-link mf-settings-privacy-link mf-settings-product-link--privacy"
      href={url}
      rel="noopener noreferrer"
      target="_blank"
    >
      <span aria-hidden="true" className="mf-settings-privacy-link__icon">
        <ShieldCheck size={22} strokeWidth={2.1} />
      </span>
      <span className="mf-settings-product-link__body">
        <strong>{copy.title}</strong>
        <span>{copy.description}</span>
      </span>
      <ExternalLink aria-hidden="true" size={18} strokeWidth={2.2} />
    </a>
  );
}

function SupportPreview({ copy, onSupportOpen, supportUrl }) {
  const normalizedSupportUrl = normalizeSupportUrl(supportUrl);

  return (
    <div
      className="mf-settings-support"
      data-support-state={normalizedSupportUrl ? "ready" : "preview"}
    >
      <p className="mf-settings-support__body">{copy.body}</p>
      <p className="mf-settings-support__promise">{copy.promise}</p>
      {!normalizedSupportUrl ? <p className="mf-settings-support__status">{copy.status}</p> : null}
      {normalizedSupportUrl ? (
        <a
          aria-label={copy.action}
          className="mf-settings-support__action"
          href={normalizedSupportUrl}
          onClick={onSupportOpen ? (event) => {
            event.preventDefault();
            onSupportOpen(normalizedSupportUrl);
          } : undefined}
          rel="noopener noreferrer"
          target="_blank"
        >
          <span>{copy.action}</span>
          <ExternalLink aria-hidden="true" size={14} strokeWidth={2.25} />
        </a>
      ) : (
        <button
          aria-label={`${copy.action}: ${copy.status}`}
          className="mf-settings-support__action"
          disabled
          type="button"
        >
          {copy.action}
        </button>
      )}
    </div>
  );
}

function PilotSupportLink({ copy, onSupportOpen, supportUrl, title }) {
  const normalizedSupportUrl = normalizeSupportUrl(supportUrl);
  const content = (
    <>
      <span aria-hidden="true" className="mf-settings-privacy-link__icon">
        <HeartHandshake size={21} strokeWidth={2.15} />
      </span>
      <span className="mf-settings-product-link__body">
        <strong>{title}</strong>
        <span>{normalizedSupportUrl ? copy.compactBody : copy.status}</span>
      </span>
      <ExternalLink aria-hidden="true" size={18} strokeWidth={2.2} />
    </>
  );

  if (!normalizedSupportUrl) {
    return (
      <button
        aria-label={`${title}: ${copy.status}`}
        className="mf-settings-product-link mf-settings-project-row mf-settings-product-link--support"
        disabled
        type="button"
      >
        {content}
      </button>
    );
  }

  return (
    <a
      aria-label={copy.action}
      className="mf-settings-product-link mf-settings-project-row mf-settings-product-link--support"
      href={normalizedSupportUrl}
      onClick={onSupportOpen ? (event) => {
        event.preventDefault();
        onSupportOpen(normalizedSupportUrl);
      } : undefined}
      rel="noopener noreferrer"
      target="_blank"
    >
      {content}
    </a>
  );
}

function NotificationRuntimeStatus({ copy, preferences, runtime }) {
  const connected = runtime?.connected === true;
  const platform = runtime?.platform === "android" ? "android" : "web";
  const runtimeStatus = String(runtime?.status || "").trim().toLowerCase();
  let state = connected ? "connected" : `${platform}_not_connected`;
  const officialAlertsEnabled = preferences?.officialAlerts !== false;
  const weatherNoticesEnabled = preferences?.weatherNotices !== false;
  const notificationsEnabled = officialAlertsEnabled || weatherNoticesEnabled;
  const errorCategory = String(runtime?.errorCategory || "").trim().toLowerCase();
  const errorCode = sanitizeWebPushErrorCode(runtime?.errorCode);
  const errorMessage = copy.errorCategories?.[errorCategory] || copy.error;
  const diagnosticMessage = errorCode
    ? `${errorMessage} ${copy.errorReference}: ${errorCode}.`
    : errorMessage;
  let message = connected
    ? officialAlertsEnabled && weatherNoticesEnabled
      ? copy.connected
      : officialAlertsEnabled
        ? copy.connectedOfficial
        : copy.connectedWeather
    : copy.androidUnavailable;

  if (
    connected
    && weatherNoticesEnabled
    && runtime?.localTargetEligible === false
  ) {
    message = officialAlertsEnabled
      ? copy.connectedLocalPending || copy.connectedWeather
      : copy.connectedLocalOnlyPending || copy.connectedWeather;
  }

  if (!connected && runtime?.readOnly === true) {
    if (platform === "web" && runtime?.reason === "web_enrollment_disabled") {
      state = "web_enrollment_disabled";
      message = copy.webEnrollmentDisabled || copy.webNotConfigured;
    } else if (runtimeStatus === "not_configured" || runtime?.reason === "not_configured") {
      state = `${platform}_not_configured`;
      message = platform === "web" ? copy.webNotConfigured : copy.androidUnavailable;
    } else if (runtimeStatus === "error") {
      state = `${platform}_error`;
      message = diagnosticMessage;
    } else {
      state = `${platform}_unsupported`;
      message = platform === "web" ? copy.webUnsupported : copy.androidUnavailable;
    }
  } else if (!connected && runtime?.permission === "denied") {
    state = `${platform}_permission_denied`;
    message = platform === "web" ? copy.deniedWeb : copy.denied;
  } else if (!connected && runtime?.permission === "prompt") {
    state = `${platform}_permission_prompt`;
    message = copy.permissionRequired;
  } else if (!connected && ["connecting", "registering"].includes(runtimeStatus)) {
    state = `${platform}_connecting`;
    message = copy.connecting;
  } else if (!connected && runtimeStatus === "error") {
    state = `${platform}_error`;
    message = diagnosticMessage;
  } else if (!connected && runtimeStatus === "disabled") {
    state = `${platform}_disabled`;
    message = copy.disabled;
  }

  const hasActionableConnectedIssue = connected
    && weatherNoticesEnabled
    && runtime?.localTargetEligible === false;
  const isTransientConnection = !connected
    && !runtime?.reason
    && !["denied", "prompt"].includes(runtime?.permission)
    && ["", "checking", "connecting", "registering"].includes(runtimeStatus);

  if (
    !notificationsEnabled
    || (connected && !hasActionableConnectedIssue)
    || isTransientConnection
  ) {
    return null;
  }

  return (
    <p
      className="mf-settings-notification-runtime"
      data-notification-error-category={errorCategory || undefined}
      data-notification-error-code={errorCode || undefined}
      data-notification-runtime={state}
      role="status"
    >
      {message}
    </p>
  );
}

function SettingsToggleRow({
  backgroundLocationState,
  checked,
  detail,
  disabled = false,
  icon: Icon,
  label,
  onChange,
  pilotWebReadOnly = false,
  toggleLabel,
  variant,
}) {
  const rowClassName = [
    "mf-settings-row",
    "mf-settings-row--toggle",
    detail && "mf-settings-row--with-description",
    variant && `mf-settings-row--${variant}`,
  ].filter(Boolean).join(" ");

  return (
    <div
      className={rowClassName}
      data-background-location-status={backgroundLocationState || undefined}
      data-pilot-web-read-only={pilotWebReadOnly || undefined}
    >
      <span className="mf-settings-row__icon">
        <Icon aria-hidden="true" size={19} strokeWidth={2.25} />
      </span>
      <span className="mf-settings-row__label">{label}</span>
      {detail ? <span className="mf-settings-row__description">{detail}</span> : null}
      <button
        aria-checked={checked}
        aria-label={toggleLabel}
        className="mf-settings-toggle"
        data-tooltip={toggleLabel}
        disabled={disabled}
        onClick={() => onChange?.(!checked)}
        role="switch"
        title={toggleLabel}
        type="button"
      >
        <span aria-hidden="true" className="mf-settings-toggle__thumb" />
      </button>
    </div>
  );
}

function formatTemplate(value, replacements = {}) {
  return Object.entries(replacements).reduce(
    (text, [key, replacement]) => text.replace(`{${key}}`, replacement ?? ""),
    value || "",
  );
}

function getDeviceLocationDetail(copy, { activeCity, autoLocationEnabled, status }) {
  if (status?.status === "loading") return copy.rows.deviceLocationLoading || "Ricerca posizione";
  if (status?.status === "denied") return copy.rows.deviceLocationDenied || "Permesso negato";
  if (status?.status === "outside_fvg") return copy.rows.deviceLocationOutsideFvg || "Fuori FVG";
  if (status?.status === "error") return copy.rows.deviceLocationError || "Non disponibile";
  if (status?.status === "last_known") {
    return formatTemplate(copy.rows.deviceLocationLastKnown || "Ultima rilevazione: {city}", {
      city: status.displayName || status.city || activeCity,
    });
  }
  if (status?.status === "success") {
    return formatTemplate(copy.rows.deviceLocationSuccess || "Aggiornata su {city}", {
      city: status.displayName || status.city || activeCity,
    });
  }
  if (autoLocationEnabled) {
    return formatTemplate(copy.rows.deviceLocationActive || "Attiva su {city}", { city: activeCity });
  }

  return copy.rows.deviceLocation[1];
}

function getBackgroundLocationStatus(copy, {
  autoLocationEnabled,
  runtime,
  weatherNoticesEnabled,
}) {
  if (!weatherNoticesEnabled) return null;

  const runtimeCopy = copy.rows.backgroundLocation;
  if (!autoLocationEnabled) {
    return {
      message: runtimeCopy.requiresAutomaticLocation,
      state: "automatic_location_required",
    };
  }
  if (["configure_failed", "settings_unavailable", "status_failed"].includes(runtime?.lastStatus)) {
    return {
      message: runtimeCopy.error,
      state: "error",
    };
  }
  if (!runtime?.backgroundPermission) {
    return {
      message: runtimeCopy.permission,
      state: "permission_required",
    };
  }
  if (runtime?.trackingActive) {
    return {
      message: runtimeCopy.active,
      state: "active",
    };
  }

  return {
    message: runtimeCopy.checking,
    state: "checking",
  };
}

function getBackgroundLocationQaRuntime(runtime) {
  if (!import.meta.env.DEV) return runtime;

  const qaState = new URLSearchParams(globalThis.window?.location?.search || "")
    .get("backgroundLocationQa");
  if (!qaState) return runtime;

  if (qaState === "active") {
    return {
      ...runtime,
      available: true,
      backgroundPermission: true,
      lastStatus: "configured",
      trackingActive: true,
    };
  }
  if (qaState === "missing") {
    return {
      ...runtime,
      available: true,
      backgroundPermission: false,
      lastStatus: "configured",
      trackingActive: false,
    };
  }

  return runtime;
}

export function SettingsView({
  activeLocation,
  appVersion,
  autoLocationEnabled = false,
  backgroundLocationRuntime,
  communityIdentity = null,
  communityReputationLoader = fetchCommunityReputation,
  deviceLocationStatus,
  language = "it",
  notificationPreferences = DEFAULT_NOTIFICATION_PREFERENCES,
  notificationRuntime = { connected: false, platform: "web", readOnly: true },
  productScope,
  onAutomaticLocationChange,
  onBackgroundLocationSettingsOpen,
  onCommunityIdentityChange,
  onLanguageSelect,
  onLocationSearchOpen,
  onSettingsBack,
  onNavigate,
  onNotificationPermissionRequest,
  onNotificationPreferenceChange,
  onNotificationSettingsOpen,
  onRuntimeCacheReset,
  onSupportOpen,
  onThemePreferenceChange,
  supportUrl = getConfiguredSupportUrl(),
  themePreference = "system",
}) {
  const pilotEnabled = isDefinitiveAppExperience();
  const [cacheResetState, setCacheResetState] = useState("idle");
  const [localCommunityIdentity, setLocalCommunityIdentity] = useState(() => (
    pilotEnabled
      ? readCommunityIdentity()
      : null
  ));
  const [profileAliasNotice, setProfileAliasNotice] = useState("");
  const [profileIdentityAnimating, setProfileIdentityAnimating] = useState(false);
  const [profileClientId] = useState(() => (
    pilotEnabled ? readExistingLiveReportClientId() : ""
  ));
  const [profileReputation, setProfileReputation] = useState(null);

  useEffect(() => {
    if (!profileAliasNotice) return undefined;

    const timer = globalThis.setTimeout?.(() => setProfileAliasNotice(""), 2400);
    return () => globalThis.clearTimeout?.(timer);
  }, [profileAliasNotice]);

  useEffect(() => {
    if (!profileIdentityAnimating) return undefined;

    const timer = globalThis.setTimeout?.(() => setProfileIdentityAnimating(false), 280);
    return () => globalThis.clearTimeout?.(timer);
  }, [profileIdentityAnimating]);

  useEffect(() => {
    if (!pilotEnabled) return undefined;

    if (!profileClientId) return undefined;
    let cancelled = false;

    communityReputationLoader({ clientId: profileClientId })
      .then(normalizeCommunityReputation)
      .then((reputation) => {
        if (!cancelled && reputation) setProfileReputation(reputation);
      })
      .catch(() => {
        // Reputation is optional UI: never substitute local activity for server points.
      });

    return () => {
      cancelled = true;
    };
  }, [communityReputationLoader, pilotEnabled, profileClientId]);

  const copy = getCopy(language);
  const effectiveBackgroundLocationRuntime = getBackgroundLocationQaRuntime(
    backgroundLocationRuntime,
  );
  const backgroundLocationQaActive = effectiveBackgroundLocationRuntime !== backgroundLocationRuntime;
  const effectiveAutoLocationEnabled = backgroundLocationQaActive ? true : autoLocationEnabled;
  const effectiveNotificationRuntime = backgroundLocationQaActive
    ? {
        ...notificationRuntime,
        connected: true,
        localTargetEligible: true,
        permission: "granted",
        platform: "android",
        readOnly: false,
        status: "connected",
      }
    : notificationRuntime;
  const currentTheme = THEME_OPTIONS.includes(themePreference) ? themePreference : "system";
  const activeCity = getLocationDisplayName(activeLocation, language) || copy.rows.activeCity[1];
  const municipality = getLocationMunicipality(activeLocation);
  const municipalityName = getMunicipalityDisplayName(activeLocation, language);
  const municipalityProvince = String(municipality?.province || activeLocation?.province || "").trim();
  const pilotLocationDetail = municipalityProvince
    ? `${activeCity} (${municipalityProvince})`
    : activeCity;
  const profileIdentity = communityIdentity || localCommunityIdentity;
  const profileAlias = profileIdentity?.alias || "";
  const profileTotalReports = profileReputation
    && profileReputation.totalReports !== null
    ? profileReputation.totalReports
    : profileClientId
      ? "—"
      : 0;
  const activeMunicipality = municipalityName
    ? formatTemplate(copy.rows.activeMunicipality || "Comune di {name}{province}", {
        name: municipalityName,
        province: municipalityProvince ? ` (${municipalityProvince})` : "",
      })
    : "";
  const isDeviceLocationLoading = deviceLocationStatus?.status === "loading";
  const deviceLocationDetail = getDeviceLocationDetail(copy, {
    activeCity,
    autoLocationEnabled: effectiveAutoLocationEnabled,
    status: deviceLocationStatus,
  });
  const cacheResetDetail = cacheResetState === "cleared"
    ? copy.rows.runtimeCacheCleared
    : cacheResetState === "clearing"
      ? copy.rows.runtimeCacheClearing
      : cacheResetState === "failed"
        ? copy.rows.runtimeCacheFailed
        : copy.rows.runtimeCache[1];
  const notificationsReadOnly = effectiveNotificationRuntime?.readOnly === true;
  const regionalAlertsAvailable = productScope?.sources?.osmer?.status == null
    || productScope.sources.osmer.status === "enabled";
  const nationalManualMunicipality = !regionalAlertsAvailable
    && effectiveNotificationRuntime?.platform === "android"
    && productScope?.sources?.nationalAlerts?.status === "enabled"
    ? toPushRegistrationNationalManualMunicipality(activeLocation)
    : null;
  const nationalAlertsAvailable = Boolean(nationalManualMunicipality);
  const officialAlertsAvailable = regionalAlertsAvailable || nationalAlertsAvailable;
  const officialAlertsPreference = nationalAlertsAvailable
    ? "nationalOfficialAlerts"
    : "officialAlerts";
  const officialAlertsLabel = nationalAlertsAvailable
    ? copy.rows.nationalOfficialAlerts.replace("{name}", nationalManualMunicipality.name)
    : copy.rows.officialAlerts;
  const officialAlertsUnavailableDetail = !regionalAlertsAvailable
    && effectiveNotificationRuntime?.platform === "android"
    && productScope?.sources?.nationalAlerts?.status === "enabled"
    ? copy.rows.nationalOfficialAlertsManualRequired
    : copy.rows.officialAlertsUnavailable;
  const effectiveNotificationPreferences = {
    ...notificationPreferences,
    officialAlerts: officialAlertsAvailable
      && (nationalAlertsAvailable
        ? notificationPreferences.nationalOfficialAlerts === true
        : notificationPreferences.officialAlerts !== false),
  };
  const notificationsSelected = effectiveNotificationPreferences.officialAlerts !== false
    || effectiveNotificationPreferences.weatherNotices !== false;
  const canRequestNotificationPermission = notificationsSelected
    && !notificationsReadOnly
    && effectiveNotificationRuntime?.platform !== "android"
    && effectiveNotificationRuntime?.permission === "prompt";
  const showBackgroundLocation = backgroundLocationQaActive || (
    effectiveNotificationRuntime?.platform === "android"
      && effectiveBackgroundLocationRuntime?.available === true
  );
  const backgroundLocationStatus = showBackgroundLocation
    ? getBackgroundLocationStatus(copy, {
        autoLocationEnabled: effectiveAutoLocationEnabled,
        runtime: effectiveBackgroundLocationRuntime,
        weatherNoticesEnabled: notificationPreferences.weatherNotices !== false,
      })
    : null;
  const weatherNoticesSelected = notificationPreferences.weatherNotices !== false;
  const androidNotificationPermissionMissing = effectiveNotificationRuntime?.platform === "android"
    && ["denied", "prompt"].includes(effectiveNotificationRuntime?.permission);
  const officialAlertsChecked = effectiveNotificationPreferences.officialAlerts !== false
    && !androidNotificationPermissionMissing;
  const weatherNoticesChecked = weatherNoticesSelected
    && !androidNotificationPermissionMissing;
  // The foreground GPS preference and the optional Android background grant
  // are independent. Missing "always allow" must never make the persisted
  // Position preference look disabled when Weather notices are selected.
  const automaticLocationChecked = effectiveAutoLocationEnabled;
  const automaticLocationDetail = effectiveAutoLocationEnabled
    ? backgroundLocationStatus?.message || deviceLocationDetail
    : deviceLocationDetail;
  const handleAutomaticLocationToggle = async (enabled) => {
    if (backgroundLocationQaActive) return;

    const action = getAutomaticLocationToggleAction({
      autoLocationEnabled,
      backgroundLocationState: backgroundLocationStatus?.state,
      enabled,
    });

    if (action === "disable_location") {
      await onAutomaticLocationChange?.(false);
      return;
    }

    if (action === "open_background_settings") {
      await onBackgroundLocationSettingsOpen?.();
      return;
    }

    if (action === "none") return;

    const result = await onAutomaticLocationChange?.(true);
    if (result?.ok === false || result?.enabled === false) return;

    if (
      weatherNoticesSelected
      && showBackgroundLocation
      && effectiveBackgroundLocationRuntime?.backgroundPermission !== true
    ) {
      await onBackgroundLocationSettingsOpen?.();
    }
  };
  const handleNotificationToggle = async (preference, enabled) => {
    const action = getNotificationToggleAction({
      enabled,
      permission: effectiveNotificationRuntime?.permission,
      platform: effectiveNotificationRuntime?.platform,
    });

    if (action === "update_preference") {
      await onNotificationPreferenceChange?.(preference, enabled);
      return;
    }

    await onNotificationPreferenceChange?.(preference, true);
    if (action === "request_permission") {
      await onNotificationPermissionRequest?.();
      return;
    }

    await onNotificationSettingsOpen?.();
  };
  const handleRuntimeCacheReset = async () => {
    if (cacheResetState === "clearing") return;
    setCacheResetState("clearing");
    try {
      const result = await onRuntimeCacheReset?.();
      setCacheResetState(result?.ok === true ? "cleared" : "failed");
    } catch {
      setCacheResetState("failed");
    }
  };
  const handleProfileAliasRegenerate = () => {
    const nextIdentity = regenerateCommunityIdentity(profileIdentity);

    if (!communityIdentity) setLocalCommunityIdentity(nextIdentity);
    onCommunityIdentityChange?.(nextIdentity);
    setProfileIdentityAnimating(true);
    setProfileAliasNotice(formatTemplate(copy.profile.aliasChanged, {
      alias: nextIdentity.alias,
    }));
  };
  const handleSettingsBack = () => {
    if (onSettingsBack) {
      onSettingsBack();
      return;
    }

    onNavigate?.("home");
  };
  const pilotWebNotificationsReadOnly = pilotEnabled
    && notificationsReadOnly
    && effectiveNotificationRuntime?.platform !== "android";
  const presentedOfficialAlertsChecked = pilotWebNotificationsReadOnly
    ? false
    : officialAlertsChecked;
  const presentedWeatherNoticesChecked = pilotWebNotificationsReadOnly
    ? false
    : weatherNoticesChecked;
  const notificationControls = (
    <>
      <SettingsToggleRow
        checked={presentedOfficialAlertsChecked}
        detail={!officialAlertsAvailable
          ? officialAlertsUnavailableDetail
          : nationalAlertsAvailable
            ? copy.rows.nationalOfficialAlertsDetail
          : pilotWebNotificationsReadOnly
            ? copy.rows.notificationRuntime.webBadge
            : undefined}
        disabled={notificationsReadOnly || !officialAlertsAvailable}
        icon={AlertTriangle}
        label={officialAlertsLabel}
        onChange={(enabled) => handleNotificationToggle(officialAlertsPreference, enabled)}
        pilotWebReadOnly={pilotWebNotificationsReadOnly}
        toggleLabel={!officialAlertsAvailable
          ? `${officialAlertsLabel}: ${officialAlertsUnavailableDetail}`
          : pilotWebNotificationsReadOnly
            ? `${officialAlertsLabel}: ${copy.rows.notificationRuntime.webBadge}`
            : `${presentedOfficialAlertsChecked ? copy.actions.disable : copy.actions.enable} ${officialAlertsLabel}`}
        variant="alert"
      />
      <SettingsToggleRow
        checked={presentedWeatherNoticesChecked}
        detail={pilotWebNotificationsReadOnly
          ? copy.rows.notificationRuntime.webBadge
          : undefined}
        disabled={notificationsReadOnly}
        icon={BellRing}
        label={copy.rows.localAlerts}
        onChange={(enabled) => handleNotificationToggle("weatherNotices", enabled)}
        pilotWebReadOnly={pilotWebNotificationsReadOnly}
        toggleLabel={pilotWebNotificationsReadOnly
          ? `${copy.rows.localAlerts}: ${copy.rows.notificationRuntime.webBadge}`
          : `${presentedWeatherNoticesChecked ? copy.actions.disable : copy.actions.enable} ${copy.rows.localAlerts}`}
        variant="notice"
      />
      {!pilotWebNotificationsReadOnly ? (
        <NotificationRuntimeStatus
          copy={copy.rows.notificationRuntime}
          preferences={effectiveNotificationPreferences}
          runtime={effectiveNotificationRuntime}
        />
      ) : null}
      {canRequestNotificationPermission ? (
        <button
          className="mf-settings-notification-action"
          onClick={() => onNotificationPermissionRequest?.()}
          type="button"
        >
          {copy.rows.notificationRuntime.authorize}
        </button>
      ) : null}
    </>
  );
  const renderBackButton = ({ iconOnly = false } = {}) => (
    <button
      aria-label={iconOnly ? copy.backHome : undefined}
      className={`mf-settings-back${iconOnly ? " mf-settings-back--icon" : ""}`}
      onClick={handleSettingsBack}
      type="button"
    >
      {iconOnly ? (
        <ArrowLeft aria-hidden="true" size={23} strokeWidth={2.6} />
      ) : (
        <ChevronLeft aria-hidden="true" size={18} strokeWidth={2.35} />
      )}
      {iconOnly ? null : <span>{copy.backHome}</span>}
    </button>
  );

  return (
    <TabPage
      className={`mf-tab-page--settings${pilotEnabled ? " mf-tab-page--settings-pilot" : ""}`}
      language={language}
      title={copy.title}
      titleMode={pilotEnabled ? "hidden" : "visible"}
    >
      <div className={`mf-settings-view${pilotEnabled ? " mf-settings-view--pilot" : ""}`}>
        {pilotEnabled ? (
          <>
            <div className="mf-settings-topbar">
              {renderBackButton({ iconOnly: true })}
              <strong aria-hidden="true">{copy.title}</strong>
            </div>

            <PilotIdentityCard
              alias={profileAlias}
              animating={profileIdentityAnimating}
              copy={copy.profile}
              identity={profileIdentity}
              notice={profileAliasNotice}
              onRegenerate={handleProfileAliasRegenerate}
              reputation={profileReputation}
              totalReports={profileTotalReports}
            />

            <SettingsPanel title={copy.sections.general} variant="pilot-group">
              <SettingsChoiceRow
                icon={Languages}
                label={copy.language.title}
                onSelect={onLanguageSelect}
                options={[
                  { label: copy.language.it, value: "it" },
                  { label: copy.language.fur, value: "fur" },
                ]}
                value={language === "fur" ? "fur" : "it"}
                variant="language"
              />
              <SettingsChoiceRow
                icon={Palette}
                label={copy.theme.title}
                onSelect={onThemePreferenceChange}
                options={THEME_OPTIONS.map((option) => ({
                  label: copy.theme[option],
                  value: option,
                }))}
                value={currentTheme}
                variant="theme"
              />
              <SettingsRow
                actionIcon={ChevronRight}
                actionLabel={copy.actions.changeLocation}
                detail={pilotLocationDetail}
                icon={MapPin}
                onAction={() => onLocationSearchOpen?.()}
                title={copy.rows.defaultLocation}
                variant="default-location"
              />
              <SettingsToggleRow
                backgroundLocationState={backgroundLocationStatus?.state}
                checked={automaticLocationChecked}
                detail={automaticLocationDetail}
                disabled={isDeviceLocationLoading}
                icon={Navigation}
                label={copy.rows.automaticLocation}
                onChange={handleAutomaticLocationToggle}
                toggleLabel={`${automaticLocationChecked ? copy.actions.disable : copy.actions.enable} ${copy.rows.automaticLocation}`}
              />
            </SettingsPanel>

            <SettingsPanel title={copy.sections.notifications} variant="pilot-group">
              {notificationControls}
            </SettingsPanel>

            <SettingsPanel title={copy.sections.project} variant="pilot-group">
              <ProductLink copy={copy.rows.product} />
              <PrivacyPolicyLink copy={copy.rows.privacy} language={language} />
              <SettingsRow
                actionBusy={cacheResetState === "clearing"}
                actionDisabled={cacheResetState === "clearing"}
                actionIcon={Eraser}
                actionLabel={copy.actions.resetCache}
                detail={cacheResetDetail || copy.actions.resetCache}
                icon={Eraser}
                onAction={handleRuntimeCacheReset}
                title={copy.rows.runtimeCache[0]}
                variant="cache"
              />
              <PilotSupportLink
                copy={copy.rows.support}
                onSupportOpen={onSupportOpen}
                supportUrl={supportUrl}
                title={copy.sections.support}
              />
            </SettingsPanel>
          </>
        ) : (
          <>
            {renderBackButton()}

            <SettingsPanel>
              <SettingsToggleRow
                checked={language === "fur"}
                detail={copy.language[language]}
                icon={Languages}
                label={copy.language.title}
                onChange={(enabled) => onLanguageSelect?.(enabled ? "fur" : "it")}
                toggleLabel={`${copy.language.title}: ${copy.language[language === "it" ? "fur" : "it"]}`}
              />

              <div className="mf-settings-control mf-settings-control--theme">
                <div>
                  <span>{copy.theme.title}</span>
                </div>
                <div className="mf-settings-segments" role="group" aria-label={copy.theme.title}>
                  {THEME_OPTIONS.map((option) => (
                    <OptionButton
                      isActive={currentTheme === option}
                      key={option}
                      onClick={() => onThemePreferenceChange?.(option)}
                    >
                      {copy.theme[option]}
                    </OptionButton>
                  ))}
                </div>
              </div>
            </SettingsPanel>

            <SettingsPanel title={copy.sections.location}>
              <SettingsRow
                actionIcon={Pencil}
                actionLabel={copy.actions.changeLocation}
                description={activeMunicipality}
                icon={MapPin}
                onAction={onLocationSearchOpen}
                title={activeCity}
              />
              <SettingsToggleRow
                backgroundLocationState={backgroundLocationStatus?.state}
                checked={automaticLocationChecked}
                detail={automaticLocationDetail}
                disabled={isDeviceLocationLoading}
                icon={Navigation}
                label={copy.rows.automaticLocation}
                onChange={handleAutomaticLocationToggle}
                toggleLabel={`${automaticLocationChecked ? copy.actions.disable : copy.actions.enable} ${copy.rows.automaticLocation}`}
              />
            </SettingsPanel>

            <SettingsPanel title={copy.sections.notifications}>
              {notificationControls}
            </SettingsPanel>

            <SettingsPanel title={copy.sections.information}>
              <ProductLink copy={copy.rows.product} />
              <PrivacyPolicyLink copy={copy.rows.privacy} language={language} />
              <SettingsRow
                actionBusy={cacheResetState === "clearing"}
                actionDisabled={cacheResetState === "clearing"}
                actionIcon={Eraser}
                actionLabel={copy.actions.resetCache}
                detail={cacheResetDetail}
                icon={Eraser}
                onAction={handleRuntimeCacheReset}
                title={copy.rows.runtimeCache[0]}
                variant="prominent"
              />
            </SettingsPanel>

            <SettingsPanel
              icon={HeartHandshake}
              title={copy.sections.support}
              variant="support"
            >
              <SupportPreview
                copy={copy.rows.support}
                onSupportOpen={onSupportOpen}
                supportUrl={supportUrl}
              />
            </SettingsPanel>
          </>
        )}
        <AppVersionRow copy={copy.rows.appVersion} info={appVersion} />
      </div>
    </TabPage>
  );
}
