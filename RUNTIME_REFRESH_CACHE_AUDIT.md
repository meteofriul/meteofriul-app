# Meteo Friul UI 3.0.0 - Audit runtime cache e refresh

Data: 2026-08-10

## Scopo

Auditare la vecchia app per recuperare il comportamento runtime che rende l'app pronta e reattiva:

```text
cache subito -> render immediato -> refresh dietro -> mai svuotare dati validi -> avviso solo se serve
```

Questa tranche non collega nuovi runtime, non aggiunge pull-to-refresh e non cambia la UI.

## Avvio per audit locale

Per auditare cache, refresh e sorgenti dati in modo ripetibile, usare:

```powershell
scripts\start-dev.ps1 -CheckOnly
scripts\start-dev.ps1 -Restart
```

Lo script mantiene il backend validato sulla porta `8001` e la UI 3.0.0 sulla porta `5173`, con proxy `/api` verso il backend. In questo modo le verifiche runtime leggono lo stesso backend della app validata, ma senza avviare il vecchio frontend.

## Fonti audit vecchia app

| Area | File sorgente vecchia app | Cosa recuperare |
| --- | --- | --- |
| Cache meteo | `frontend/src/App.jsx` | `weatherBootstrapCache:v2`, TTL, fallback stale |
| Cache Eventi | `frontend/src/App.jsx` | `eventsCache:v10`, schema `single-source-v1`, full limit 100 |
| Refresh manuale | `frontend/src/App.jsx` | `handleRefreshNow()` |
| Pull-to-refresh | `frontend/src/App.jsx`, `App.css` | gesture, soglie, feedback minimo |
| Foreground/online | `frontend/src/App.jsx` | `visibilitychange`, `focus`, `online`, intervallo minimo |
| Anti localita sbagliata | `frontend/src/App.jsx` | `activeLocationKeyRef`, ignore risposte stale |
| Reset/cache Opzioni | `LocationSelector.jsx` vecchia app | pulsante aggiorna e ultimo aggiornamento |

## Comportamento vecchia app da conservare

### Avvio e idratazione

All'avvio la vecchia app legge subito da cache:

- meteo corrente;
- previsioni;
- allerte ufficiali;
- bollettino regionale;
- eventi;
- ultimo aggiornamento.

Se esiste un dato cache leggibile, la schermata parte piena e il refresh lavora dopo.
L'utente non deve vedere una schermata vuota o `Caricamento...` quando esiste un ultimo dato valido.

### Cache meteo

Contratto:

- chiave: `weatherBootstrapCache:v2:<locationKey>`;
- TTL fresco: 5 minuti;
- cache stale leggibile come fallback se la rete fallisce;
- `force=true` usa cache buster `_=` e fetch `no-store`;
- se il refresh fallisce ma esiste cache, il dato resta visibile;
- se non esiste cache, allora e solo allora si mostra stato non raggiungibile/errore.
- Home UI3: il fallback post-failure non deve usare cache meteo senza limite; oltre la finestra controllata non si resuscita il dato corrente.

### Cache Bollettino

Il bollettino non deve usare qualunque cache meteo: serve testo ufficiale OSMER.

La vecchia app usa `hasOfficialOsmerForecasts()` per accettare solo cache con previsioni ufficiali testuali.

Regola UI3:

- cache valida con OSMER ufficiale: render immediato;
- cache vecchia ma ancora entro finestra controllata: render prudente o stato stale;
- refresh fallito con cache ufficiale ancora entro finestra controllata: mantenere il bollettino visibile;
- fonte non raggiungibile senza cache ufficiale: `Dati non raggiungibili`;
- cache ufficiale troppo vecchia oltre finestra controllata: non resuscitare il testo, mostrare `Dati non raggiungibili`;
- mai mostrare fixture o testo statico come se fosse bollettino ufficiale corrente.

### Cache Eventi

Contratto:

- chiave: `eventsCache:v10:<locationKey>:<limit>`;
- schema: `single-source-v1`;
- TTL: 48 ore;
- limite Home vecchio: 8;
- limite canonico completo: 100;
- preferire sempre cache full 100 quando esiste;
- la cache Home 8 e' solo fallback legacy;
- payload backend `refreshing` o `partial` non va scritto in cache;
- se backend e' in refresh e c'e' cache, si mostra cache + stato aggiornamento, non lista vuota.
- Home UI3: se il refresh Eventi fallisce ma c'e' cache, lo stato e' `stale`, non `error` vuoto.

### Refresh manuale

`handleRefreshNow()` nella vecchia app:

1. se posizione automatica attiva, prova prima controllo GPS;
2. se GPS cambia localita, evita refresh doppio della vecchia localita;
3. se manca localita, aggiorna bollettino regionale;
4. se localita esiste, aggiorna meteo + Eventi in parallelo;
5. ritorna esito `{ ok, changed }` per feedback utente.

Regola UI3:

- refresh manuale non deve svuotare Home/Bollettino/Eventi;
- se non cambia niente, feedback discreto tipo `Dati gia aggiornati`;
- se fallisce e c'e' cache, dato resta visibile;
- se fallisce e non c'e' cache, stato chiaro `Dati non raggiungibili`.

### Pull-to-refresh

Soglie vecchia app:

- direzione minima verticale: 28 px;
- trigger refresh: 172 px;
- massimo visuale: 224 px;
- rapporto tracking: 0.58;
- feedback minimo: 900 ms.

Guardrail vecchi da mantenere:

- non parte dentro bottoni/input/select;
- non parte dentro mappe, bollettino scrollabile, pannelli, menu o bottom sheet;
- non parte se una modale/localita e' aperta;
- non interferisce con swipe orizzontale tab;
- se gesture non supera soglia, non aggiorna.

### Foreground e online

Vecchia app:

- verifica meteo ogni 5 minuti;
- refresh su `visibilitychange`, `focus`, `online`;
- min intervallo foreground: 2 minuti;
- Eventi refresh periodico ogni 30 minuti;
- se auto-location attiva, foreground puo prima verificare GPS.

Regola UI3:

- refresh foreground deve essere leggero e non visibile come blocco;
- non deve partire a raffica;
- deve rispettare localita corrente;
- foreground GPS resta separato dal gate Android e va collegato solo dopo test APK.

### Anti-risposte vecchie

La vecchia app usa `activeLocationKeyRef`:

- se una risposta arriva per una localita non piu attiva, non aggiorna la UI;
- puo salvare cache per quella localita, ma non deve mescolare dati nella schermata corrente.

Questa regola e' fondamentale quando l'utente cambia comune mentre una fetch e' in corso.

## Stato UI3 attuale

Gia coperto:

- `jsonCache`, `weatherCache`, `eventsCache` estratti e testati;
- `homeDataController` usa cache fresca e fallback meteo fino a 6 ore;
- `bulletinDataController` idrata da cache ufficiale OSMER ancora valida per
  calendario e non usa cache senza dato ufficiale;
- dati meteo locali e radar usano fallback fino a 3 ore;
- `eventsDataController` mantiene cache durante refresh/failure e non scrive payload `refreshing`/`partial`;
- Eventi accetta cache fino a 48 ore; Territorio conserva webcam fino a 7 giorni
  e segnalazioni community fino a 65 minuti;
- `AppRoutes` rimonta le route su chiave localita;
- pull-to-refresh UI3 collegato alla shell con feedback `Aggiornamento...` / `Aggiornato` / `Fallito`;
- reset cache locale da Opzioni collegato a meteo Home, Eventi e Territorio;
- test espliciti verificano che nessun dominio riutilizzi cache oltre la propria
  finestra quando la nuova API non risponde;
- collaudo browser completato con `8001` e `8002` spenti: le cache valide
  mantengono Home, Bollettino, Territorio ed Eventi leggibili senza caricamenti
  bloccati; Scopri e Almanacco restano disponibili dai dati locali.

Parziale:

- `App.jsx` ha timer 5 minuti, focus, online e `runtimeRefreshToken`;
- non esiste ancora un orchestratore unico con esito `{ ok, changed, source }`;
- foreground GPS non collegato in modo Android-safe;
- feedback refresh ancora minimo, da validare poi in wrapper Android reale.

## Contratto runtime UI3

Stati minimi:

| Stato | Significato |
| --- | --- |
| `hydrated` | dati letti subito da cache valida |
| `refreshing` | refresh in corso, dati attuali restano visibili |
| `fresh` | refresh riuscito con dati nuovi |
| `unchanged` | refresh riuscito, nessuna modifica sostanziale |
| `stale_visible` | rete fallita, cache ancora mostrabile |
| `unreachable_empty` | rete fallita e nessuna cache utile |
| `ignored_stale_location` | risposta arrivata per localita non piu attiva |

Azioni minime:

| Azione | Regola |
| --- | --- |
| `hydrate_from_cache` | prima del primo fetch |
| `refresh_current_location` | meteo, bollettino, eventi coerenti con localita corrente |
| `refresh_regional_bulletin` | se localita non risolta |
| `retry_events_if_pending` | solo per `refreshing`/`partial` backend |
| `show_passive_feedback` | mai bloccare UI gia leggibile |
| `show_unreachable_state` | solo se manca dato valido |

## Cosa non fare ora

- Non copiare il vecchio `App.jsx`.
- Non svuotare dati durante refresh.
- Non mostrare `Caricamento...` se cache utile esiste.
- Non usare fixture per mascherare fonte non raggiungibile.
- Non collegare GPS foreground o notifiche in questa tranche.

## Prossimo passo consigliato

Collaudare la nuova API su una revisione Cloud Run senza traffico, abilitando
Firestore per le segnalazioni community. Ripetere sul relativo URL i percorsi
con fonte disponibile, fonte assente e cache gia presente. Il wrapper Android
nativo resta successivo alla chiusura del prodotto web.
