# Contratto proposto tra app e pannello promozioni

Questo documento definisce il confine di integrazione. Non modifica né assume
la struttura del progetto separato `F:\proggetto Meteo Friul App\INSERZIONI`.

## Responsabilità

### Pannello amministratore

- crea, modifica, sospende e archivia inserzionisti e campagne;
- sceglie i posizionamenti ammessi (`home`, `eventi`, `scopri`), priorità,
  periodo, area geografica e limite di impressioni;
- pubblica una revisione immutabile del catalogo a ogni variazione;
- mostra statistiche aggregate e salute della distribuzione, senza ricevere
  preferenze, alias Community o posizione GPS precisa.

### Backend Meteo Friûl

- valida il catalogo pubblicato, URL, date, immagini e posizionamenti;
- espone all'app soltanto l'ultima revisione attiva;
- riceve eventi idempotenti, applica limiti e li aggrega per giorno, campagna e
  posizionamento;
- conserva separati catalogo campagne, telemetria e dati editoriali Eventi;
- può disattivare immediatamente una campagna senza attendere la cache Eventi.

### App Meteo Friûl

- ricontrolla il catalogo all'avvio, al ritorno in primo piano e ogni 5 minuti;
- usa una cache autonoma per revisione, mai la cache Eventi di 48 ore;
- nasconde le promozioni se il catalogo è scaduto e non può essere verificato;
- conserva localmente i limiti di frequenza e una breve coda eventi;
- non elimina limiti o coda promozionale tramite «Svuota cache»;
- apre soltanto URL HTTPS validati dal backend.

## Catalogo minimo

Ogni risposta dovrebbe contenere `revision`, `generated_at`, `expires_at` e
`campaigns`. Ogni campagna dovrebbe almeno dichiarare:

- `campaign_id`, `advertiser_id`, `creative_revision`;
- `enabled`, `starts_at`, `ends_at`;
- `placements`, `priority`, `daily_cap`;
- testi IT/FUR, etichetta pubblicitaria, CTA e URL HTTPS;
- immagine con URL versionato e hash o revisione;
- eventuale insieme di Comuni/Province/Regioni, senza coordinate utente.

La revisione deve cambiare anche per sospensioni e riattivazioni. Una risposta
parziale o non valida non sostituisce mai un catalogo attivo verificato.

## Eventi utili al pannello

Gli eventi proposti sono:

- `impression`: card realmente visibile secondo soglia concordata;
- `click`: pressione dell'utente sulla CTA o sulla card;
- `destination_opened`: consegna riuscita al browser/app esterna;
- `destination_failed`: apertura non riuscita;
- `catalog_refresh_ok`, `catalog_refresh_failed`, `catalog_cache_used`: salute
  della distribuzione, da aggregare e non mostrare come conversioni.

Payload minimo: `event_id` casuale e idempotente, `campaign_id`,
`creative_revision`, `placement`, `event_type`, `occurred_at`, piattaforma,
versione app e lingua. Comune ISTAT solo se deriva dalla località scelta e solo
in forma aggregata; mai GPS, alias, token push, installation ID o identificatori
pubblicitari.

Il backend deve rispondere rapidamente e accettare batch. L'app elimina dalla
coda solo gli eventi confermati; ritenta con backoff e scarta gli eventi oltre
la finestra di conservazione concordata. Il pannello legge esclusivamente le
aggregazioni del backend, non scrive direttamente nelle cache dell'app.

## Decisioni ancora da condividere prima del collegamento

1. URL e autenticazione degli endpoint catalogo/eventi.
2. Durata esatta della cache promozioni e della coda offline.
3. Soglia temporale/percentuale per contare una impressione.
4. Retention delle aggregazioni e informativa privacy.
5. Modalità di attribuzione di `destination_opened` sulle diverse versioni
   Android e Web.
