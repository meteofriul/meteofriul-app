# Reindirizzamento degli host Firebase legacy

La web app canonica e' pubblicata su `https://meteofriul.app/` tramite
Cloudflare Pages. Gli host Firebase Hosting restano disponibili esclusivamente
come ingressi legacy:

- `https://meteo-friul.web.app/`;
- `https://meteo-friul.firebaseapp.com/`.

Sono origini browser distinte: permessi di posizione e notifiche concessi o
negati su una di esse non si trasferiscono alla web app canonica. Per evitare
che vecchi preferiti o link mostrino una build superata, `firebase.json`
pubblica soltanto il contenuto minimo di `firebase-legacy-redirect` e applica
un redirect temporaneo `302` di root e percorsi verso `https://meteofriul.app/`.
Le risorse Firebase riservate sotto `/__/` restano
gestite dalla piattaforma e il progetto Firebase non viene eliminato: continua
a servire FCM, Firestore e App Check.

## Procedura di pubblicazione

1. verificare il progetto CLI `meteo-friul`;
2. pubblicare prima su un canale Hosting temporaneo;
3. verificare root, percorso, query string e assenza di loop;
4. promuovere esattamente la versione verificata sul canale live;
5. verificare entrambi gli host Firebase e la destinazione Cloudflare;
6. mantenere il `302` per 24-48 ore, poi valutare un `301` definitivo.

La versione Hosting precedente al passaggio e'
`6ca0b3d4f1436a6f`. Rollback, solo se necessario:

```powershell
npx firebase-tools hosting:clone `
  meteo-friul:@6ca0b3d4f1436a6f `
  meteo-friul:live `
  --project meteo-friul
```

Il redirect non corregge un permesso gia' negato su `meteofriul.app`, la
localizzazione disattivata a livello di sistema o i limiti dei browser interni
di applicazioni come WhatsApp e Facebook.
