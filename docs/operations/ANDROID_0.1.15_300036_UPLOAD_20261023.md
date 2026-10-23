# AAB 0.1.15 / 300036 — test interno del 23 ottobre 2026

## Esito

**Disponibile per i tester interni dalle 13:37 Europe/Rome.** Usata la AAB
archiviata `meteofriul-300036-0.1.15.aab`, senza ricostruirla: 73.017.302 byte,
SHA256 `024212752b3af72f163d75849aa53c2b191ba0352e42423b11efccd2d7f8b51f`.
Sorgente `9d5ff2f415ab8b10be510eff2a0b058a8c2408ac`; package `com.meteofriul.app`.
[Identità e controlli di build](ANDROID_0.1.15_300036_BUILD_20261023.md).
CI dei record `39945799912` verde su `ea4c7327` prima dell'upload.

La lista selezionata contiene due account. Il proprietario ne ha confermato
la configurazione con «lascia ho messo io»: lista e membri sono rimasti
invariati; gli indirizzi non sono stati letti. Le altre liste restano escluse.
Produzione riletta dopo il caricamento: **0.1.14 / 300031**, invariata.
La 300035 è sostituita nel canale interno; resta l'ultimo pacchetto osservato
sul Galaxy, con il difetto Tempo reale documentato.

Sponsor ricontrollati prima e dopo: `enabled=false`, zero campagne, revisione
117; ultima lettura `2026-10-23T11:45:04.299104+00:00`. Pannello e sincronizzazione sponsor
non attivati. Nessuna installazione, emulatore, nuovo deploy, invio manuale
o pubblicazione in produzione.

## Convalida Play e limiti

Revisione: **zero errori bloccanti e un avviso**, relativo ai simboli nativi
di debug mancanti già documentati per le librerie transitive. Mapping ReTrace
allegato automaticamente; nessun cambiamento alla toolchain.

| Area | Riscontro per la 300036 e limite |
| --- | --- |
| Edge-to-edge / inset | Nessun errore bloccante in revisione; Android 15/16, gesti, cutout e tastiera NON VERIFICATI sul nuovo pacchetto |
| API system bar deprecate | Avvisi delle dipendenze conservati nel verbale di build; nessun report pre-lancio utilizzabile, nessun PASS implicito |
| Orientamento / schermi grandi | 19.333 dispositivi supportati, nessun dispositivo perso; small/normal/large/xlarge dichiarati. Tablet e multi-window NON VERIFICATI |
| R8 / risorse | Console: ottimizzazione DEX 89%, offuscamento e riduzione 91%, modalità completa e riduzione risorse ottimizzata. Raccomandazione repackaging/AGP 9.0 non bloccante; avvio minificato della 300036 NON VERIFICATO |

Play dichiara supporto statico pagine 16 kB, minimo API 24 e target 36. La pagina
del report pre-lancio non contiene risultati utilizzabili: nessuna esecuzione
cloud manuale né modifica alle sue impostazioni. Questi controlli non sono una
prova sul telefono. **REALTIME-LAYOUT-01 resta aperto** fino alla prova della
nuova versione aggiornata da Play, con mappa, dock, lista e webcam.
Verificare anche tutte le sezioni, Posizione prima/dopo e aria/pollini IT/FUR.

## Note pubblicate

Testo italiano completo, 480 caratteri:

• Tempo reale: mappa corretta, estesa fino alla barra inferiore.
• Previsioni: temi chiaro/scuro, giorni uniformi e pioggia più leggibile.
• Bollettino: mappa e aggiornamento FVG corretti; menu fissi anche in Eventi.
• Community: conferma No/Sì, nuova ricevuta e «Inviata da».
• Rivisti italiano e friulano; allerte «in FVG».
• Corretti Indietro, ricerca, Posizione e caricamento aria/pollini.
• Migliorati catalogo Eventi, compatibilità meteo, configurazione Android e sicurezza.

## Registro e conservazione

- [Release nella Console](https://play.google.com/console/u/0/developers/7317561924451916933/app/4972150571875270846/tracks/4700755128382710882/releases/19/details).
- [Accettazione append-only](../../release-history/android-play/20261023T113755179Z-play-accepted-e9ed3d84a42b4973bd01b15fa21c96eb.evidence.json). I 56 record precedenti sono invariati; nuovo totale 57.
- [Ricevuta strutturata](evidence/release-0.1.15-300036-upload-20261023/verification.json), con hash delle prove private.
- Screenshot e letture nell'archivio canonico ignorato `release-artifacts/android-play/evidence-300036/play-upload-20261023/`. Nessun indirizzo dei tester versionato.

PR 11 in bozza, main non modificato. Il record e il verbale di accettazione
sono salvati sul ramo release secondo il runbook; non cambiano i sorgenti
dell'AAB. La Web dalla stessa sorgente resta preparata e non pubblicata.
Safari/iPhone, PWA e aggiornamento cache restano non verificati.
