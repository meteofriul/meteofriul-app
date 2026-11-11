import { getHomeStaticViewModel } from "./homeFixture";
import { HomeBulletinSummary } from "./HomeBulletinSummary";
import { HomeLocalMetrics } from "./HomeLocalMetrics";
import { HomeOfficialAlertCard } from "./HomeOfficialAlertCard";
import { HomeQuickGrid } from "./HomeQuickGrid";
import { HomeWeatherHero } from "./HomeWeatherHero";
import { useHomeWeatherVisual } from "./useHomeWeatherVisual";
import { useEditorialAdvice } from "./useEditorialAdvice";
import { isDefinitiveAppExperience } from "../../services/localWeatherPilot";

export function HomeView({
  cardStyle = "texture",
  language = "it",
  model,
  onChangeLocation,
  onNavigate,
  weatherNow,
}) {
  const homeModel = model || getHomeStaticViewModel(language);
  const editorialAdvice = useEditorialAdvice();
  const weatherVisual = useHomeWeatherVisual(homeModel.weather, { now: weatherNow });
  const officialAlert = homeModel.officialAlert || homeModel.weather?.alertSummary || null;
  const hasActiveAlert = Boolean(officialAlert?.label);
  const hasAlertDestination = officialAlert?.action?.type === "tab-anchor"
    && Boolean(officialAlert.action.tab);
  const bulletin = editorialAdvice && homeModel.bulletin
    ? { ...homeModel.bulletin, advice: { source: "editorial", group: editorialAdvice.type,
      type: editorialAdvice.type, title: editorialAdvice.title, label: editorialAdvice.message } }
    : homeModel.bulletin;
  const handleAlertAction = (action) => {
    if (action?.type === "tab-anchor" && action.tab) {
      onNavigate?.(action.tab, { anchor: action.anchor });
    }
  };

  return (
    <div className="mf-home-view mf-home-card-style" data-card-style={cardStyle}>
      <div className="mf-home-now">
        <HomeWeatherHero
          changeLocationLabel={homeModel.changeLocationLabel}
          locationTitle={homeModel.locationTitle}
          onChangeLocation={onChangeLocation}
          sceneMode={homeModel.sceneMode}
          showUpdateStatus={!isDefinitiveAppExperience()}
          visualState={weatherVisual}
          weather={homeModel.weather}
        />
        {!isDefinitiveAppExperience() ? <HomeLocalMetrics model={homeModel.localMetrics} /> : null}
        {hasActiveAlert ? (
          <HomeOfficialAlertCard
            alert={officialAlert}
            language={language}
            onOpen={onNavigate && hasAlertDestination
              ? () => handleAlertAction(officialAlert.action)
              : undefined}
          />
        ) : (
          <HomeBulletinSummary
            bulletin={bulletin}
            onOpen={onNavigate ? () => onNavigate("bulletin") : undefined}
          />
        )}
      </div>
      <HomeQuickGrid
        almanac={homeModel.almanac}
        events={homeModel.events}
        hourly={homeModel.hourly}
        language={language}
        now={weatherNow}
        onNavigate={onNavigate}
        territory={homeModel.territory}
      />
    </div>
  );
}
