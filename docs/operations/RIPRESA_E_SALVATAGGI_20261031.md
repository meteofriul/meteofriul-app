# Ripresa e salvataggi locali — 31 ottobre 2026

Controllo richiesto dal proprietario dopo la riaccensione del PC. Questo
passaggio conserva il lavoro e ne verifica lo stato; non promuove funzionalità
e non pubblica app, pannello o servizi.

## Main e rami dell'app

`git fetch origin` completato. `main` locale e `origin/main` coincidono in
`e3527f73`, con la correzione della tipografia Home e il relativo verbale
integrati tramite PR 36 e 37. Non serve riallineare main o importarlo nel ramo
Mercati: main è già un antenato del ramo corrente.

| Lavoro | Stato alla lettura iniziale | Passaggio ancora necessario |
| --- | --- | --- |
| Mercati | Ramo `codex/mercati-integration-20261028`, pulito, commit `e2af4388`; 18 commit oltre main e un commit oltre il ramo remoto | Revisione UI e dati; nessuna promozione ora |
| Blocco pubblicazione | `e2af4388`, salvato localmente; verifica precedente di 40 test backend | Conservare il blocco fino all'autorizzazione esplicita |
| Raggio nelle Impostazioni | `f8c9ff5b`, ramo `codex/events-markets-radius-settings-20261030`, pulito e senza upstream | Integrare nel ramo Mercati preservando l'archivio condiviso, ripetere le prove incrociate e la revisione visiva |
| Orto | `c27df16b` nel ramo dedicato | Lavoro conservato, non ripreso o promosso in questo controllo |
| CSS e Barcolana | Commit già salvati, presenti anche nella cronologia del ramo Mercati | Riesaminare il perimetro di un'eventuale PR; evitare un merge generale non revisionato |

I 159 test del raggio, la build e il lint citati nel suo verbale sono risultati
del 30 ottobre, non prove di integrazione con il backend Mercati attuale.
Anche i 40 test del blocco cloud sono evidenza del 30 ottobre; non sono stati
rieseguiti durante questo inventario senza modifiche al codice dell'app.

## Pannello esterno: lavoro salvato

Il pannello `PANNELLO INSERZIONI` era nel ramo
`codex/markets-management-20261030`, con 23 file modificati o nuovi non
committati. Comprendevano l'editor Mercati e le precedenti modifiche al Centro
di gestione e alle bozze editoriali locali. Nessun file è stato ripristinato
o scartato per isolare artificialmente i lavori.

1. Salvata una copia dei 23 file con manifest SHA-256 e verifica dello ZIP.
2. Confrontati byte per byte i 96 file di sorgenti, asset e configurazione
   del pannello con la copia locale usata per le verifiche.
3. Eseguiti tutti i 165 test in 29 file con Node 22.17.1 e configurazione nativa;
   esito PASS con `--maxWorkers 2`. Lint completo PASS.
4. Salvato il checkpoint locale `7e2b2fc1bdb8f5288f2a82e4c46ea3c2de0bfbbd`,
   comprensivo del documento `SALVATAGGIO_LOCALE_20261031.md`. Working tree
   pulito dopo il commit; i 23 file originali conservano gli stessi hash.

La prima esecuzione dei test senza limitare i worker ha superato 164 test e
raggiunto il timeout di 5 secondi nella prova PDF delle ricevute. La ripetizione
completa con due worker passa senza modificare test o timeout. Non è stata
eseguita una nuova build né una prova visuale; il checkpoint è un salvataggio
del lavoro in corso, non una dichiarazione di prontezza alla distribuzione.

Nessun push del pannello. I lavori editoriali preesistenti sono conservati
esplicitamente nel checkpoint; eventuali sviluppi successivi indipendenti
mantengono i rispettivi perimetri di lavoro e revisione.

## Archivio locale: revisione 2 conservata

La lettura del database in modalità read-only ha rilevato un salvataggio
successivo alla preparazione iniziale del lotto: revisione amministrativa **2**,
con modifica di una pratica dal pannello. Non va sostituita con la revisione 1
descritta nel verbale storico del 30 ottobre.

- 100 identità e 213 date amministrative.
- Tutte le 59 pratiche preparate, 13 più complete e 46 con verifiche residue.
- Revisione pubblica ancora 0: 53 schede e 161 date nella proiezione precedente.
- Copia SQLite effettuata con API di backup, `PRAGMA quick_check` PASS e
  checksum del payload verificato; copia e originale coincidono.

Backup e ricevute sono in `.tmp/resume-checkpoint-20261031/`, esclusi da Git.
La credenziale amministrativa non è stata inclusa. Questa è una copia locale,
non un backup esterno o una sincronizzazione cloud.

Gli script di migrazione preparati il 30 ottobre assumono la revisione locale 1:
non devono essere eseguiti senza una nuova revisione del contenuto e del
perimetro, oltre all'autorizzazione. Il blocco operativo rimane attivo.

## Confini della ripresa

Nessuna modifica remota, push, PR, merge a main, esecuzione di job, build
Android, installazione o pubblicazione eseguita in questo passaggio.
L'inventario delle risorse cloud predisposte resta quello del
[verbale di attivazione sospesa](MERCATI_ATTIVAZIONE_ONLINE_20261030.md);
non è stato ripetuto un controllo cloud in questa ripresa.

Le porte locali 5174, 5182 e 8002 non risultavano in ascolto dopo la riaccensione;
i servizi non sono stati riavviati da questo inventario. Per la prossima prova
usare il launcher pilota canonico e mantenere distinti app locale e pannello.

Priorità successiva: anteprima integrata, rifinitura dell'interfaccia e verifica
dei dati che si intende pubblicare. Nessuna pubblicazione automatica, nemmeno
del solo pannello: prima revisione del risultato e autorizzazione esplicita.
