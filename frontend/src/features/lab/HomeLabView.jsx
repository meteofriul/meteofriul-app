import { useEffect, useMemo, useState } from "react";

import { HomeView } from "../home/HomeView";
import { TabPage } from "../../ui/layout/TabPage";
import {
  buildHomeWeatherVariantPreviewModel,
  getHomeWeatherVariantPreviewCopy,
  getHomeWeatherVariantPreviewOptions,
} from "./homeVariantPreview";

const SCENE_PHASE_OPTIONS = [
  { id: "night", label: { fur: "Gnot", it: "Notte" } },
  { id: "dawn", label: { fur: "Albe", it: "Alba" } },
  { id: "morning", label: { fur: "Doman", it: "Mattino" } },
  { id: "midday", label: { fur: "Misdì", it: "Mezzogiorno" } },
  { id: "afternoon", label: { fur: "Dopomisdì", it: "Pomeriggio" } },
  { id: "sunset", label: { fur: "Tramont", it: "Tramonto" } },
];

const CARD_STYLE_OPTIONS = [
  { id: "current", label: { fur: "Origjinâl", it: "Originale" } },
  { id: "underline", label: { fur: "Linie", it: "Linea" } },
  { id: "texture", label: { fur: "Trame", it: "Texture" } },
];

const HOME_LAB_SELECTIONS = {
  cardStyle: {
    defaultValue: "current",
    storageKey: "mf-home-lab-card-style",
    values: CARD_STYLE_OPTIONS.map((option) => option.id),
  },
  phase: {
    defaultValue: "midday",
    storageKey: "mf-home-lab-day-phase",
    values: SCENE_PHASE_OPTIONS.map((option) => option.id),
  },
  variant: {
    defaultValue: "clear",
    storageKey: "mf-home-lab-weather-variant",
    values: ["clear", "partly", "cloud", "rain", "storm", "snow", "fog"],
  },
};

function readSessionSelection({ defaultValue, storageKey, values }) {
  if (typeof window === "undefined") return defaultValue;

  try {
    const savedValue = window.sessionStorage.getItem(storageKey);
    return values.includes(savedValue) ? savedValue : defaultValue;
  } catch {
    return defaultValue;
  }
}

function useSessionSelection(config) {
  const [value, setValue] = useState(() => readSessionSelection(config));

  useEffect(() => {
    try {
      window.sessionStorage.setItem(config.storageKey, value);
    } catch {
      // The Lab remains usable when storage is unavailable or disabled.
    }
  }, [config.storageKey, value]);

  return [value, setValue];
}

function PreviewOptionRail({ ariaLabel, onSelect, options, selected, title }) {
  return (
    <div className="mf-weather-variant-preview__group">
      <span className="mf-weather-variant-preview__title">{title}</span>
      <div className="mf-weather-variant-preview__rail" role="group" aria-label={ariaLabel}>
        {options.map((option) => (
          <button
            aria-pressed={option.id === selected}
            className="mf-weather-variant-preview__button"
            data-active={option.id === selected}
            key={option.id}
            onClick={() => onSelect(option.id)}
            type="button"
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function WeatherVariantPreviewControl({
  cardStyleOptions,
  copy,
  onSelectCardStyle,
  onSelectPhase,
  onSelectVariant,
  phaseOptions,
  selectedCardStyle,
  selectedPhase,
  selectedVariant,
  variantOptions,
}) {
  return (
    <section className="mf-weather-variant-preview" aria-label={copy.ariaLabel}>
      <PreviewOptionRail
        ariaLabel={copy.variantAriaLabel}
        onSelect={onSelectVariant}
        options={variantOptions}
        selected={selectedVariant}
        title={copy.title}
      />
      <PreviewOptionRail
        ariaLabel={copy.phaseAriaLabel}
        onSelect={onSelectPhase}
        options={phaseOptions}
        selected={selectedPhase}
        title={copy.phaseTitle}
      />
      <PreviewOptionRail
        ariaLabel={copy.cardStyleAriaLabel}
        onSelect={onSelectCardStyle}
        options={cardStyleOptions}
        selected={selectedCardStyle}
        title={copy.cardStyleTitle}
      />
    </section>
  );
}

export function HomeLabView({ copy, language, onNavigate }) {
  const [selectedVariant, setSelectedVariant] = useSessionSelection(HOME_LAB_SELECTIONS.variant);
  const [selectedPhase, setSelectedPhase] = useSessionSelection(HOME_LAB_SELECTIONS.phase);
  const [selectedCardStyle, setSelectedCardStyle] = useSessionSelection(HOME_LAB_SELECTIONS.cardStyle);
  const languageKey = language === "fur" ? "fur" : "it";
  const previewCopy = {
    ...getHomeWeatherVariantPreviewCopy(language),
    cardStyleAriaLabel: languageKey === "fur" ? "Stîl des schedis informativis" : "Stile delle card informative",
    cardStyleTitle: languageKey === "fur" ? "Stîl schedis" : "Stile card",
    phaseAriaLabel: languageKey === "fur" ? "Fase de zornade" : "Fase della giornata",
    phaseTitle: languageKey === "fur" ? "Fase zornade" : "Fase giornata",
    variantAriaLabel: languageKey === "fur" ? "Variant meteo" : "Variante meteo",
  };
  const cardStyleOptions = useMemo(
    () => CARD_STYLE_OPTIONS.map((option) => ({ ...option, label: option.label[languageKey] })),
    [languageKey],
  );
  const phaseOptions = useMemo(
    () => SCENE_PHASE_OPTIONS.map((option) => ({ ...option, label: option.label[languageKey] })),
    [languageKey],
  );
  const variantOptions = useMemo(
    () => getHomeWeatherVariantPreviewOptions(language).filter((option) => !option.id.includes("night")),
    [language],
  );
  const previewModel = useMemo(() => {
    const model = buildHomeWeatherVariantPreviewModel(language, selectedVariant);

    return {
      ...model,
      weather: {
        ...model.weather,
        scenePhaseOverride: selectedPhase,
      },
    };
  }, [language, selectedPhase, selectedVariant]);

  return (
    <TabPage className="mf-tab-page--home" language={language} title={copy.placeholders.homeTitle} titleMode="hidden">
      <WeatherVariantPreviewControl
        cardStyleOptions={cardStyleOptions}
        copy={previewCopy}
        onSelectCardStyle={setSelectedCardStyle}
        onSelectPhase={setSelectedPhase}
        onSelectVariant={setSelectedVariant}
        phaseOptions={phaseOptions}
        selectedCardStyle={selectedCardStyle}
        selectedPhase={selectedPhase}
        selectedVariant={selectedVariant}
        variantOptions={variantOptions}
      />
      <div className="mf-home-card-style-preview">
        <HomeView
          cardStyle={selectedCardStyle}
          language={language}
          model={previewModel}
          onNavigate={onNavigate}
        />
      </div>
    </TabPage>
  );
}
