# Webcam preview control plane

## Scopo

Il controllo amministrativo consente di sospendere e riattivare l'anteprima di
ogni webcam senza modificare l'app Web o distribuire un nuovo APK/AAB. Una
webcam sospesa resta nel catalogo con identità, posizione, fallback e
collegamento alla fonte; la risposta pubblica omette esclusivamente
`imageUrl`, `mediaType` e `playerUrl`.

Il contratto pubblico di `GET /api/live/webcams` non cambia. Gli APK già
distribuiti interpretano quindi la voce come fallback, usando il comportamento
già esistente.

## Webcam con snapshot e video

Quando una fonte verificata offre sia un'immagine aggiornata sia un vero video,
Meteo Friûl conserva entrambe le modalità come risorse della stessa webcam. Il
record pubblico espone una sola modalità principale per volta: `imageUrl` con
`mediaType: snapshot`, oppure `playerUrl` con `mediaType: iframe`. Le due coppie
non possono coesistere nello stesso record.

Il controllo corrente gestisce soltanto ON/OFF della modalità selezionata nel
catalogo. Una futura estensione del pannello Webcam dovrà offrire anche la
selezione **Snapshot / Video**, limitata alle varianti già censite e approvate,
senza accettare URL liberi inseriti dall'operatore. La sostituzione dovrà essere
atomica e mantenere identità, fallback, attribuzione e pagina sorgente. Gemona
è il primo record con snapshot predefinito e player video alternativo già
verificato.

## Separazione dal pannello Inserzioni

Questo ramo implementa soltanto il dominio webcam nel backend Meteo Friûl. Non
modifica il progetto separato `INSERZIONI`, campagne, sponsor o contratti
promozionali.

Una futura integrazione nel medesimo pannello potrà riusare accesso e
navigazione, ma dovrà mantenere una sezione Webcam indipendente:

- claim Firebase `webcamAdmin`, distinto da `adsAdmin`;
- collezione Firestore `webcam_admin_state`, distinta da
  `promotion_admin_state`;
- endpoint `/api/admin/webcams/*`, distinti dagli endpoint promozioni;
- revisione, motivazione e tracciamento operatore autonomi.

Il possesso del solo claim `adsAdmin` non autorizza operazioni sulle webcam.

## API amministrativa

### Lettura

`GET /api/admin/webcams/state` richiede un Firebase ID token con
`webcamAdmin: true`. Restituisce la revisione corrente e una riga per ogni
webcam attiva con:

- identità, località, provider e pagina sorgente;
- disponibilità di anteprima e fallback;
- stato effettivo `previewEnabled`;
- motivazione, data e operatore dell'ultima variazione.

### Aggiornamento

`PUT /api/admin/webcams/state` applica una o più variazioni atomiche:

```json
{
  "expectedRevision": 4,
  "changes": [
    {
      "webcamId": "udine-panorama-castello",
      "previewEnabled": false,
      "reason": "Verifica della fonte in corso"
    }
  ]
}
```

`expectedRevision` impedisce che due sessioni amministrative si sovrascrivano:
una revisione superata restituisce HTTP `409`. ID sconosciuti, duplicati o
tentativi di sospendere una voce che non possiede anteprima restituiscono HTTP
`422`.

La riattivazione usa lo stesso comando con `previewEnabled: true`. L'URL
originario non viene eliminato dal catalogo e non deve essere reinserito.

## Persistenza e comportamento di sicurezza

Lo stato è conservato nel documento Firestore
`webcam_admin_state/current`. In sviluppo locale, senza `K_SERVICE`, è
disponibile una memoria di processo per i test e il pilot.

In un servizio distribuito la persistenza Firestore è obbligatoria. Se il
backend non può confermare lo stato amministrativo, la risposta pubblica
fallisce in sicurezza rimuovendo tutte le anteprime ma conservando i fallback.
Non viene riattivata una foto sulla base di uno stato amministrativo
indisponibile.

Il backend conserva il controllo letto per un massimo di 60 secondi. Il client
ricontrolla il manifest webcam ogni 10 minuti; dopo una risposta aggiornata la
cache persistente contiene già la versione senza anteprima e non ripristina il
vecchio URL durante un successivo periodo offline.

## Autenticazione e strumento claim

La modalità ordinaria verifica Firebase Authentication con revoca del token.
La modalità locale usa esclusivamente:

- `WEBCAM_ADMIN_AUTH_MODE=local`;
- `WEBCAM_ADMIN_LOCAL_TOKEN=<token di sviluppo>`.

La modalità locale viene rifiutata quando è presente `K_SERVICE`.

Lo strumento `backend/tools/set_webcam_admin_claim.py` opera in dry-run finché
non viene passato `--apply`:

```powershell
Set-Location backend
py tools/set_webcam_admin_claim.py --email operator@example.test --enable
py tools/set_webcam_admin_claim.py --email operator@example.test --enable --apply
```

Nessun claim è stato assegnato e nessuno stato Cloud è stato modificato durante
questa implementazione.

## Verifica locale del contratto

Il 29 settembre 2026 il pilot canonico è stato avviato su `127.0.0.1:5174`
con API locale su `127.0.0.1:8002`. Il ciclo sulla webcam
`udine-panorama-castello` ha prodotto:

1. revisione `0` iniziale, anteprima attiva;
2. revisione `1` con anteprima OFF: `imageUrl` e `mediaType` assenti, fallback
   `/municipalities/photos/030129-photo.webp` presente;
3. revisione `2` con anteprima nuovamente ON: URL Panomax originale ripristinato
   dal catalogo senza reinserimento manuale.

Lo stato era soltanto nella memoria del processo locale. Nessun documento
Firestore è stato creato o modificato.

## Confine della consegna corrente

La consegna locale comprende backend, autenticazione, persistenza, conflitto di
revisione, fail-closed e test. Non comprende:

- interfaccia nel progetto `INSERZIONI`;
- deploy backend o pannello;
- creazione o modifica di documenti Firestore reali;
- assegnazione di claim;
- build o distribuzione Android.
