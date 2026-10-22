# Navigazione fissa nelle sezioni Bollettino ed Eventi

Stato: modifica locale sul ramo `codex/section-sticky-navigation`, basato su
`main` `3da1db2d4d2f1de4bd14745ef7fd078ec8d399dd`. Non promossa su main.

## Perimetro approvato

- Bollettino: località e menù meteo esistenti restano visibili durante lo
  scorrimento. Le pill dei giorni e il contenuto continuano a scorrere.
- Eventi: località e filtri esistenti restano visibili nella lista.
  Il dettaglio evento resta sovrapposto alla schermata, barra compresa.
- Nessun nuovo controllo, testo o cambio di grafica. Previsioni e Tempo reale
  mantengono lo scorrimento precedente.
- L'apertura di un'ancora nel Bollettino tiene conto dell'altezza effettiva della
  barra, così il contenuto richiesto può apparire sotto i controlli.

## Verifiche del 22 ottobre 2026

- Vitest con `--configLoader native`: 82 test superati in 8 file, relativi a
  composizione/navigazione meteo, route, Eventi e dettaglio, CSS del layout.
  Il test di composizione esistente è stato adeguato al contenitore della barra,
  conservando i controlli sui pulsanti e sull'isolamento dei gesti.
- ESLint sui componenti e sul test modificati: superato.
- `git diff --check`: superato.
- Browser integrato, anteprima del ramo avviata esclusivamente con
  `scripts/start-local-weather-pilot.ps1 -WeatherCloud` su porta 5174;
  provata anche la modalità prevista `-StableFrontend`.
- Controllo visivo a 390 × 844: Bollettino ed Eventi mantengono località e menù
  visibili durante lo scorrimento in italiano/tema chiaro e friulano/tema scuro.
  Coperto il margine superiore per non lasciar comparire frammenti del contenuto
  dietro la barra. Screenshot osservati nella chat.
- Eventi: aperta una scheda dalla lista scorsa; il dettaglio copre anche la barra.
  Alla chiusura tornano lista e filtri. Nessuna modifica al comportamento del
  dettaglio o alle sue azioni.

## Limiti e lavoro ancora da verificare

Il launcher ha infine fermato i propri processi perché il controllo del reader
meteo corrente non è passato, sia in modalità Vite sia stabile. Il successivo
`-WeatherCloud -CheckOnly` ha confermato il controllo non superato. Questa nota
non attribuisce una causa al servizio: non è stata eseguita una diagnosi cloud.
La build Web locale della modalità stabile è riuscita (restano gli avvisi
preesistenti sulla dimensione dei chunk e sull'import Almanac).

Il percorso Home/Sintesi → allerta nel Bollettino non è stato completato nel
browser con un'allerta corrente: nella sessione non era presente il relativo
blocco. L'offset è implementato ma la prova visiva di quel percorso resta aperta.
La verifica su telefono, inizialmente pendente, è completata per il browser
Brave nel seguito riportato sotto. Restano non provati Safari/iPhone, il runtime
Android nativo e il percorso dell'allerta corrente. Nessuna promozione su main
è stata effettuata in questa sessione.

Nessuna AAB, installazione, emulatore, push, deploy, esecuzione di job o invio
manuale. Sponsor e altri lavori (posizione Android, configurazione nativa,
sovrapposizioni della mappa) non modificati.


## Verifica su Galaxy in Brave, 22 ottobre 2026

Candidato: `aa505cd66494d7fa9833d12d7d740947562cdcc7`, ramo
`codex/section-sticky-navigation`, codice invariato durante questa verifica.
Telefono Galaxy A52 (SM-A525F), Android 14, Brave 1.97.59, schermo fisico
1080 × 2400. Accesso alla sola anteprima locale tramite USB reverse della porta
5174; nessuna installazione. Il telefono è stato lasciato sul Bollettino in
italiano/tema chiaro, con il contenuto scorso e i controlli visibili.

L'anteprima del ramo è stata avviata con il launcher prescritto:
`scripts/start-local-weather-pilot.ps1 -WeatherTestNow '2026-09-04T13:00:00Z'`.
I controlli di avvio sono passati usando lo snapshot meteo locale. Questo esito
non risolve né sostituisce il precedente controllo del reader cloud: la prova
riguarda la navigazione, non la freschezza delle previsioni. Nessun job cloud
o acquisizione meteo manuale è stato avviato.

| Controllo reale | Esito |
| --- | --- |
| Bollettino italiano/chiaro | Località e tre pulsanti meteo restano alla stessa posizione mentre il contenuto scorre. |
| Bollettino friulano/scuro | Stesso comportamento per località, Previsions, Boletin e Timp reâl. |
| Eventi italiano/chiaro e friulano/scuro | Località e filtri restano fissi mentre le schede scorrono. |
| Dettaglio Evento | Si sovrappone anche alla barra; nessun nuovo controllo introdotto. |
| Indietro Android nel browser | Chiude il dettaglio e ripristina la posizione precedente della lista. |
| Home/Sintesi → Bollettino ordinario OSMER | Apertura con località e menù visibili. |
| Home/Sintesi → ancora dell'allerta ufficiale | Non esercitato: nessuna scheda di allerta ufficiale presente nell'anteprima. |

Confrontate immagini e gerarchie Android: nel Bollettino la località mantiene
la coordinata superiore y=476 e il menù y=584; negli Eventi i filtri mantengono
y=702. Una scheda evento passa da y=1497 a y=998 durante lo scorrimento e torna
a y=998 dopo Indietro. Le coordinate sono pixel fisici della sessione, non
dimensioni CSS da fissare nel prodotto. I dettagli sono in
[checks.json](evidence/section-sticky-navigation-2026-10-22/checks.json).

Il proprietario ha confermato dopo la prova: **solo Bollettino ed Eventi**.
Previsioni resta volutamente a scorrimento normale, come Tempo reale.
Nessuna estensione del perimetro applicata.

### Evidenze e limiti

- [Ambiente](evidence/section-sticky-navigation-2026-10-22/environment.json) e
  [hash SHA-256](evidence/section-sticky-navigation-2026-10-22/manifest.json).
- [Bollettino scorso, italiano/chiaro](evidence/section-sticky-navigation-2026-10-22/bulletin-final-visible.png).
- [Eventi scorsi, italiano/chiaro](evidence/section-sticky-navigation-2026-10-22/events-scrolled.png).
- [Dettaglio sovrapposto](evidence/section-sticky-navigation-2026-10-22/event-detail.png).
- [Boletin, friulano/scuro](evidence/section-sticky-navigation-2026-10-22/boletin-fur-dark-scrolled.png).
- [Eventi, friulano/scuro](evidence/section-sticky-navigation-2026-10-22/events-fur-dark-scrolled.png).

Le gerarchie grezze e gli screenshot intermedi restano nella cartella locale
ignorata `.tmp/section-sticky-phone-20261022` della radice canonica. Sono
escluse dalle evidenze versionabili le schermate delle impostazioni personali.
Le preferenze dell'anteprima sono state riportate a italiano/tema chiaro.

La verifica Brave non attesta WebView Android, AAB o Safari/iPhone. Il ramo non
include ancora la distinta correzione della mappa già promossa su main; questa
sessione non la ricopia e non modifica altri rami. Nessuna AAB, installazione,
emulatore, push, deploy, invio o modifica degli sponsor. I test automatici già
registrati sopra restano quelli del candidato, senza ripetizioni inutili perché
il codice non è cambiato.
