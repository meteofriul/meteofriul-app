# Meteo Friul UI 3.0.0 - UI Components Contract

Data: 2026-06-21
Stato: contratto iniziale

## Scopo

Questo documento definisce le regole dei componenti UI base della nuova Meteo Friul UI 3.0.0.

Obiettivo: evitare che ogni tab inventi card, bottoni, badge, testi e stati visivi diversi.

## Principi comuni

Ogni componente UI deve essere:

- leggibile;
- mobile-first;
- riusabile;
- accessibile;
- coerente con blu Friul e oro Friul;
- indipendente dalla logica dati;
- testabile;
- privo di side effect.

Un componente UI non deve fare fetch, scrivere cache, interpretare OSMER o decidere notifiche.

## Token obbligatori

I componenti devono usare token, non colori sparsi.

Token minimi:

```css
--mf-blue: #0073CF;
--mf-gold: #D4AF37;
--mf-ink: #0F172A;
--mf-muted: #475569;
--mf-paper: #F4F8FC;
--mf-surface: #F8FBFF;
--mf-surface-strong: #EAF3FB;
--mf-border: rgba(15, 76, 129, 0.14);
--mf-danger: #DC2626;
--mf-warning: #EA580C;
--mf-success: #15803D;
--mf-radius-card: 14px;
--mf-radius-control: 12px;
--mf-shadow-card: 0 14px 32px rgba(15, 23, 42, 0.10);
```

I valori possono cambiare, i nomi devono restare stabili.

## AppShell

Responsabilita:

- frame mobile;
- header;
- tab content area;
- bottom navigation;
- overlay/sheet globali;
- lingua corrente;
- safe area.

Non deve:

- fare fetch diretto;
- interpretare meteo;
- contenere markup specifico di una tab;
- avere logica cache.

## Mobile runtime e orientamento

La app finale deve essere portrait-only.

Regole:

- l'interfaccia e' progettata e verificata solo in verticale;
- la rotazione landscape non deve essere una modalita supportata della app;
- il blocco reale dell'orientamento va configurato nel runtime nativo Android, non nel CSS;
- quando verra importato/creato il wrapper Android o Capacitor, dovra essere impostato il blocco verticale, ad esempio tramite configurazione nativa equivalente a `android:screenOrientation="portrait"`;
- se verra usata una PWA installabile, il manifest potra dichiarare `orientation: "portrait"`, ma questo non sostituisce il blocco nativo Android.

Non usare workaround visivi tipo layout landscape simulato o messaggi "ruota il telefono" come soluzione primaria.

## AppHeader

Deve contenere:

- logo/brand;
- titolo bi-color;
- azione impostazioni;
- eventuale lingua se previsto dalla vista.

Regole:

- `Meteo Friul` sempre riconoscibile;
- blu/oro coerenti;
- cambio lingua percepibile ma non invasivo;
- nessuna compressione del titolo su mobile.

## BottomNavigation

Tab principali:

- Home;
- Bollettino;
- Territorio;
- Eventi;
- Scopri.

Regole:

- target touch comodi;
- stato attivo chiaro;
- icona + testo;
- non usare bottom nav per opzioni secondarie;
- non cambiare ordine tab senza decisione scritta.

## AppCard

Uso:

- contenitori informativi;
- teaser;
- pannelli ripetuti;
- sezioni editoriali.

Regole:

- niente card dentro card salvo modali o item ripetuti realmente necessari;
- bordo leggero;
- fondo morbido;
- ombra sobria;
- testo leggibile;
- padding coerente.

Varianti:

- `default`;
- `interactive`;
- `official`;
- `editorial`;
- `warning`;
- `glass` solo se necessario e leggibile.

## AppButton

Varianti:

- `primary` blu Friul;
- `secondary` superficie chiara;
- `ghost` solo per azioni leggere;
- `danger` per rimozioni;
- `external` con icona link esterno.

Regole:

- label chiara;
- icona quando aiuta;
- target touch comodo;
- loading e disabled visibili;
- niente pulsanti solo colore senza testo/aria-label.

## AppIconButton

Uso:

- chiudi;
- impostazioni;
- espandi;
- link esterno;
- refresh.

Regole:

- icone lucide-react se disponibili;
- aria-label obbligatoria;
- dimensioni stabili;
- tooltip o title dove utile;
- non sostituire comandi importanti con icone misteriose.

## AppBadge

Uso:

- stato fonte;
- lingua;
- consigliato;
- ufficiale;
- cache/stato;
- gravita.

Regole:

- testo breve;
- contrasto sufficiente;
- non usare oro su bianco per testo piccolo;
- badge informativo diverso da bottone.

## AppToast

Uso:

- avvisi meteo locali in app;
- esiti azioni;
- messaggi brevi.

Regole:

- colore coerente con gravita;
- chiusura con X;
- durata sufficiente;
- non coprire brand/localita;
- non sostituire push reali;
- testo breve.

Gravita:

- info: blu;
- heat/warning: arancio;
- storm/danger: rosso/violaceo sobrio;
- success: verde;
- neutral: grigio/blu.

## AppTabs / SegmentedControl

Uso:

- filtri giorno;
- filtri eventi;
- categorie webcam;
- opzioni compatte.

Regole:

- non troppo piccoli;
- stato attivo chiaro;
- scroll orizzontale solo se necessario;
- non interferire con swipe principale.

## AppSheet / Modal

Uso:

- impostazioni;
- selezione localita;
- dettaglio webcam;
- disclaimer mappa.

Regole:

- chiusura chiara;
- focus gestito;
- contenuto scrollabile;
- niente modali profonde annidate;
- testo leggibile.

## EmptyState

Uso:

- nessun evento;
- dati meteo non disponibili;
- nessuna segnalazione;
- webcam non attiva.

Regole:

- dire cosa succede;
- dire cosa puo fare l'utente, se utile;
- non sembrare errore se non e' errore;
- non promettere refresh che non esiste.

## WeatherHero

Responsabilita:

- localita;
- temperatura;
- condizione;
- percepita;
- scenetta.

Regole:

- scenetta autonoma;
- temperatura leggibile su ogni sfondo;
- condizione chiara;
- no interpretazioni del bollettino;
- vento come effetto secondario.

## WeatherStatsGrid

Responsabilita:

- dettagli meteo essenziali.

Regole:

- icona, valore, label;
- niente sparkline decorative in Home;
- se servono andamenti, portarli nel Bollettino con legenda;
- griglia stabile senza shift.

## BulletinMapShell

Responsabilita:

- mappa FVG;
- marker A1-A9;
- overlay vento/fulmini;
- province se previste.

Regole:

- A1-A9 ufficiali comandano;
- overlay non invasivi;
- fonte chiara;
- nessuna interpretazione libera;
- se manca dato, stato non disponibile.

## BulletinDataReadiness

Responsabilita:

- bootstrap meteo/OSMER condiviso con Home;
- cache dispositivo `weatherBootstrapCache:v2`;
- refresh silenzioso dopo render iniziale.

Regole:

- il Bollettino legge subito l'ultimo payload OSMER ufficiale valido se presente;
- la fetch live non deve produrre una schermata transitoria di caricamento;
- se la fetch fallisce ma esiste cache ufficiale, la UI resta sul dato cache/stale;
- se non esiste alcun payload ufficiale valido, solo allora la vista puo' mostrare stato non disponibile;
- il componente visuale non decide fetch/cache.

## EventCard

Responsabilita:

- titolo;
- data;
- luogo;
- distanza se disponibile;
- fonte;
- immagine/fallback.

Regole:

- non bloccare lista per immagini lente;
- fonte leggibile;
- categoria prudente;
- card compatta ma non schiacciata.

## WebcamCard

Responsabilita:

- preview;
- stato fonte;
- titolo area;
- apertura dettaglio.

Regole:

- se video non disponibile, mostra immagine senza promettere video;
- stato fonte discreto;
- nota fonti esterne leggibile;
- no badge ridondanti.

## EditorialCard

Uso:

- Scopri;
- Almanacco;
- Ostermann;
- proverbi;
- contenuti storici.

Regole:

- tono editoriale;
- testo respirato;
- fonte/credito se necessario;
- stato FUR in revisione visibile solo dove serve;
- evitare blocchi lunghi senza gerarchia.

## EventsView

Responsabilita:

- presentare lista Eventi;
- filtrare per tempo e categoria usando un modello gia preparato;
- mostrare immagine o fallback visuale;
- aprire link evento esterno quando presente;
- aprire il cambio localita tramite callback della shell.

Non deve:

- fare fetch;
- leggere o scrivere localStorage;
- chiamare `/local/events`;
- decidere cache, retry o fonte;
- cambiare ranking geografico.

Contratto dati:

- riceve `model` da `buildEventsViewModel()`;
- riceve `onChangeLocation`;
- il controller dati vive fuori dalla view;
- stati `loading`, `empty`, `refreshing` e `partial` devono arrivare dal model/controller.

## Checklist per ogni componente

Prima di approvare un componente:

- usa token;
- non contiene fetch;
- non contiene copy hardcoded se localizzabile;
- ha aria-label dove serve;
- regge IT/FUR;
- regge testo lungo;
- regge stato vuoto/loading;
- non dipende da App.css legacy;
- non usa `!important` salvo ponte temporaneo documentato.

## SettingsView

Responsabilita:

- preferenze lingua e tema;
- stato sintetico dei servizi principali;
- punto di accesso futuro per localita, refresh, cache, notifiche e permessi.

Regole:

- non entra nella bottom nav;
- si apre dall'ingranaggio della testata;
- non avvia GPS, notifiche, fetch o reset cache da sola;
- lingua e tema sono controlli reali;
- stati non ancora collegati vanno mostrati con copy utente, non con note interne tipo migrazione/audit;
- i collegamenti runtime restano da importare in tranche dedicate.
