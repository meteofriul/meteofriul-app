# Anteprima generale della Web app — 21 ottobre 2026

## Ambito e stato

- Ramo locale: `codex/web-social-preview`, dalla baseline main `246279ab`.
- Preparazione dei soli metadati social e dell'immagine generale di
  `https://meteofriul.app/`. Nessuna pubblicazione, push o promozione a main.
- Nessuna modifica a logica dell'app, API, notifiche, manifest, icone launcher,
  configurazione Android, versione o AAB. Le anteprime delle singole
  segnalazioni restano fuori da questo intervento.

## Contenuto

`frontend/index.html` espone Open Graph e Twitter Card direttamente nell'HTML,
senza richiedere JavaScript al crawler. Titolo e descrizione presentano la Web
app. L'immagine PNG locale misura 1200 × 630 pixel, ha sfondo opaco fino ai
bordi e riusa il marchio ufficiale già presente nel repository.

L'URL dell'immagine contiene `?v=20261021`. L'anteprima è generale e in italiano,
indipendentemente dalla lingua selezionata nell'app. Non è una card dinamica
per una segnalazione, né una modifica all'anteprima del link Google Play.

Sorgente modificabile: `frontend/public/social-preview.svg`. Il dominio
stampato nell'immagine è `meteofriul.app`; la landing ha un asset distinto.
Per rigenerare il PNG con ImageMagick 7, dalla cartella `frontend/public`:

```powershell
magick -background '#102a54' social-preview.svg -alpha remove -alpha off -strip PNG24:social-preview.png
```

Controllare visivamente il risultato dopo ogni rigenerazione: font e renderer
SVG possono variare tra ambienti.

## Verifiche locali

- `node --test scripts/social-preview.node-tests.mjs`: 3/3, da `frontend`.
- ESLint sul nuovo test: superato.
- Build Vite in modalità production ordinaria, con `--configLoader native`
  e output temporaneo esterno: superata. Anche build e controllo standalone
  del service worker superati; nessuna iscrizione o notifica inviata.
- Metadati presenti nell'HTML compilato; PNG copiato senza variazioni.
- PNG ispezionato visivamente e ai quattro angoli: nessun angolo bianco o
  trasparente. SHA-256:
  `3e87b9a6a78d1eab37a1ff11fdafa23645e3a8fdd70524ad1ba5e5aa2a58f361`.
- Controllo di pulizia workspace canonico superato. Restano i warning di
  build su dimensione chunk e import dinamico/statica di AlmanacView.

La build è una verifica tecnica locale, non un candidato Cloudflare attestato.
Prima della pubblicazione occorre integrare il ramo nella baseline approvata e
seguire il runbook Web/Android. Non sono state verificate nuove condivisioni
pubbliche, cache dei social o Safari/iPhone. Una volta autorizzato il deploy,
verificare HTML e immagine effettivamente serviti e poi le anteprime social.
