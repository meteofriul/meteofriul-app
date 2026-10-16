# Contratto live v1

Queste fixture congelano il solo contratto runtime consumato dalla pagina
Territorio (`tab=live`). Non contengono HTML, stato visuale o dettagli interni di persistenza.

Endpoint:

- `GET /api/live/webcams`;
- `GET /api/community/reports`;
- `POST /api/community/reports`;
- `POST /api/community/reputation`;
- `DELETE /api/community/reports/{reportId}`;
- `POST /api/community/reports/{groupId}/confirmation`;
- `POST /api/community/reports/{groupId}/flags`.

Regole invarianti:

- una segnalazione dura 60 minuti;
- lo stesso client attende 45 minuti prima di inviarne un'altra;
- l'autore puo' annullarla per 60 secondi;
- creazione e conferme/smentite richiedono `accepted_terms: true` e la versione
  corrente `community-guidelines-v2`;
- tutte le mutazioni, compresi conferme e flag, richiedono App Check;
- una correzione manuale della localita e' ammessa entro 5 km dal GPS;
- il pre-filtro client usa la busta piu' ampia della mappa, mentre il backend
  applica la busta FVG e il vincolo autoritativo dei 5 km; tutti i 215 centri
  supportati e il relativo raggio ammesso restano compresi nella busta backend;
- l'API pubblica il centro del Comune, non le coordinate precise del telefono;
- ogni fonte mantiene una chiave pubblica opaca giornaliera; una nuova
  segnalazione puo' anche includere `identity` v1 con il solo snapshot
  allowlisted di alias e ricetta avatar (`subject_id`, `palette_id`,
  `pattern_id`, `variant`, `angle`);
- lo snapshot e' immutabile per il report: rigenerare l'alias influenza solo
  le segnalazioni future; nei gruppi ogni elemento di `identities` associa
  `sourceKey` a `identity` ed e' deduplicato per fonte;
- i report legacy senza `identity` restano leggibili tramite `sourceKey`;
- ogni flag nasconde subito il contenuto al segnalante e lo inserisce nella
  coda privata di moderazione;
- nessun numero di flag produce automaticamente un hide globale: la decisione
  globale e' esclusivamente del moderatore;
- i motivi ammessi sono soltanto `inaccurate`, `duplicate` e `misuse`;
- flag, snapshot di moderazione e blocchi amministrativi scadono dopo 24 ore;
- le segnalazioni sono informative e non verificate e non sostituiscono mai
  comunicazioni ufficiali;
- un errore remoto delle webcam usa il manifest locale pronto all'avvio.

La reputazione Community e' un contratto privato distinto dal feed effimero:

- la richiesta contiene soltanto il `client_id` dell'installazione ed e'
  protetta da App Check; la risposta non restituisce mai identificatori;
- non esiste recupero account: cancellare i dati locali o cambiare
  installazione crea una nuova identita' e il vecchio rango non e' collegabile;
- una nuova segnalazione parte da zero punti; l'autore riceve al massimo un
  punto per episodio solo dopo una conferma indipendente o una seconda
  segnalazione dello stesso fenomeno da un'altra installazione;
- `quiet` (`Tutto tranquillo`) e i voti dei confermatori non assegnano punti;
- il limite e' tre punti al giorno, calcolato sul giorno civile
  `Europe/Rome`;
- una smentita `non piove piu` chiude temporalmente l'episodio ma non invalida
  una segnalazione gia' verificata; solo il rifiuto amministrativo per dato
  inesatto o abuso revoca l'eventuale punto;
- il riepilogo pseudonimo scade 365 giorni dopo l'ultima convalida o revoca;
  ogni assegnazione scade 365 giorni dopo la convalida o revoca del relativo
  episodio.
  Entrambe le collection richiedono `expires_at_timestamp` e policy TTL
  Firestore `ACTIVE` prima di una build ufficiale;
- `community-ephemeral-safety-v1` continua a descrivere esclusivamente il feed
  pubblico dei report da 60 minuti, non il ledger reputazione separato.

Le chiavi pubbliche e gli snapshot identità non sono account o identificatori
interni. `identity` rifiuta campi aggiuntivi e non può contenere `client_id` o
`owner_key`. Gli hash privati necessari a cooldown e moderazione non compaiono
mai nelle risposte runtime. Anche i riferimenti del ledger reputazione sono
hash privati e non compaiono nel feed pubblico. La gestione amministrativa avviene soltanto tramite
lo strumento privato documentato nel backend; non esiste una route
amministrativa pubblica.

Le fixture community usano due localita rappresentative per restare leggibili.
Il catalogo runtime reale contiene tutti i 215 Comuni FVG e viene verificato dai
test del servizio.
