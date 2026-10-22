# Aria e pollini: caricamento distinto da indisponibilità

## Stato del lavoro

22 ottobre 2026. Ramo `codex/cams-loading-state`, creato da main
`d62683b9666ad38de42033fd2fe6db022ead8943`.
Correzione e verbale salvati nel commit locale di questo ramo. La promozione
su main resta in attesa della prova su dispositivo prevista da AGENTS.md,
oppure di una deroga esplicita del proprietario per questa sola modifica.
Il controllo ADB del 22 ottobre non rileva dispositivi collegati.
Main e il ramo release 0.1.15 restano invariati. Nessuna variazione a
versionName/versionCode.

## Comportamento

| Stato | Italiano | Friulano |
| --- | --- | --- |
| Richiesta in corso, senza valori utilizzabili | Caricamento… | In cjariament… |
| Dati assenti/non utilizzabili dopo un esito esplicito | Dati non disponibili | Dâts no disponibii |
| Dati disponibili | Valori e provenienza | Valori e provenienza |

Le stesse diciture compaiono nelle schede Previsioni e nei dettagli.
Il caricamento iniziale viene seguito dalla route e quello differito dallo
stato CAMS. Un esito CAMS esplicito, compresa la revoca, prevale sul generico
caricamento meteo. Aria e pollini conservano disponibilità indipendente;
i valori validi, inclusi gli zeri, restano visibili durante l'aggiornamento.
Non cambiano acquisizione, cache, tolleranze, servizi, layout o soglie.

## Verifiche

- 250 test superati in 25 file: area weather, caricamento differito,
  avvio con revoche, continuità CAMS, candidato attivo e controller Home.
- Regressioni nuove: attesa iniziale/differita, errore terminale, recupero,
  aria/pollini indipendenti, zero reale e due lingue.
- Due regressioni di revoca hanno inizialmente evidenziato una precedenza
  errata del caricamento generico; corretta nel modello senza indebolire
  i controlli di revoca. La ripetizione completa sopra è verde.
- Lint frontend e `git diff --check`: superati.
- Browser integrato, launcher `scripts/start-local-weather-pilot.ps1`
  con `-NationalCloud`, esclusivamente porta 5174.
- Scenari locali simulati con i componenti reali: caricamento,
  indisponibilità, recupero e dettagli, in italiano e friulano.
  La pagina temporanea è ignorata da Git e non entra nell'app pubblicata.
- Pagina reale: osservato `Caricamento…` per entrambe le schede, seguito
  dai dati CAMS senza interventi sulla cache. PM2.5 9,4 µg/m³, PM10
  11,4 µg/m³, graminacee 0,11 grani/m³. Controllata anche la vista friulana.
- Italiano e tema chiaro ripristinati; posizione e notifiche non modificate.

Evidenze locali nella radice canonica:
`.tmp/cams-loading-state-20261022/` (screenshot IT/FUR, stati simulati
e albero accessibile del passaggio reale caricamento → dati).

## Limiti e perimetro

La verifica browser non sostituisce una prova su telefono o una prova della
release minificata Android. Nessuna installazione, AAB, push, deploy, invio,
esecuzione manuale di job o emulatore. Gli sponsor restano disattivati.
Il lavoro non attribuisce a un job il precedente episodio transitorio
dell'anteprima: quella causa non era dimostrata.
