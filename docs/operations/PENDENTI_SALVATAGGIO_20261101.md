# Salvataggio delle modifiche pendenti — 1 novembre 2026

Il proprietario ha autorizzato il salvataggio delle modifiche rimaste locali,
con separazione tra codice e resoconti degli audit. Il lavoro prosegue sul
ramo esistente `codex/mercati-integration-20261028`; nessun cambio di ramo,
promozione a main o pubblicazione è stato eseguito.

## Commit e perimetro

- Commit funzionale [`a81161da`](https://github.com/meteofriul/meteofriul-app/commit/a81161dafdef193a6c6d17b126b7bd53b2c45013):
  18 file frontend e tre documenti/ricevute dell'integrazione. Raggio
  modificabile soltanto nelle Impostazioni, condiviso da Home, Eventi e
  Mercati, persistente e incluso nelle chiavi delle cache e nei contatori.
  Push riuscito; hash remoto riletto con `git ls-remote`.
- Il commit documentale che contiene questo verbale conserva separatamente
  [audit job](JOBS_READONLY_AUDIT_20261031.md),
  [recupero ICON](ICON_RECOVERY_20261031.md), rispettive ricevute e richiami
  in README, inventario job, stato release e parità Web/Android.
- Pannello esterno già pulito e sincronizzato nel commit `fe4768f`;
  nessun ulteriore intervento necessario sul suo repository.

Le frasi «non committato» o «nessun push» nei verbali precedenti descrivono
le rispettive finestre storiche. Questo checkpoint supera quelle indicazioni
per i file salvati, senza riscrivere i risultati dei controlli passati.

## Verifiche conservate

`build_verifica` ha confrontato tutti i **18 sourceHashes** della
[ricevuta del raggio](evidence/MERCATI_RAGGIO_SOLO_IMPOSTAZIONI_20261031.json)
con il working tree: **18/18 identici**, nessuna modifica frontend o di
configurazione aggiuntiva non coperta. Node 22.17.1, Vitest 4.1.12 e Vite 8.1.6
coincidono con l'ambiente registrato.

Si riutilizzano quindi le prove esistenti di **760 test in 67 file PASS**,
lint, build Web, build service worker e controllo standalone PASS.
Non sono nuove esecuzioni, non rappresentano l'intera suite frontend e non
qualificano un artefatto di release. Gli artefatti temporanei della precedente
build non sono stati riverificati.

La review corrente di cache, raggio, contatori e test non ha rilevato problemi
materiali. `git diff --check` e il controllo del workspace canonico passano.
Le ricevute JSON sono parseabili; i collegamenti documentali aggiunti sono
controllati localmente. La
[ricevuta del checkpoint](evidence/PENDENTI_SALVATAGGIO_20261101.json)
conserva hash e limiti della verifica.

Restano i precedenti warning non bloccanti sulla dimensione del chunk e
sull'import statico/dinamico di AlmanacView. Nessuna nuova prova su browser,
telefono, Android o Safari/iPhone è dichiarata. I rapporti dei job restano
evidenze del **31 ottobre**, non un controllo operativo del 1 novembre.

## Copia locale e privacy

Backup prima dei commit:
`.dev-logs/markets/backups/pending-20261101T162631Z/`.
Contiene i 29 file inizialmente pendenti e una copia dello schema UI
navigabile, con manifest e checksum verificati. È una copia sullo stesso PC.
Il database resta nella copia consistente già documentata nel
[precedente salvataggio Mercati](MERCATI_SALVATAGGIO_20261101.md);
non è stato modificato o copiato nuovamente durante questo passaggio.

Token, credenziali, database, log e helper locali restano ignorati da Git.
Il controllo dei candidati non ha rilevato la credenziale amministrativa
locale, chiavi private o token Bearer reali. Il pre-push privacy esterno
rimane attivo e il push del commit funzionale lo ha superato.

Lo schema UI è una proposta locale, conservata anche nel backup; non è
codice applicativo approvato né una nuova UI distribuita.

## Attività aperte

- Collegamento SMTP e attivazione del promemoria email ancora da completare.
- Definizione della struttura generale dell'app e successiva revisione UI.
- Eventuale promozione mediante PR, verifiche richieste e pubblicazioni
  restano passaggi distinti; nessun deploy, APK/AAB o merge a main eseguito.
- I due avvisi Dependabot già segnalati sul ramo predefinito non sono stati
  analizzati in questo salvataggio; nessuna dipendenza modificata.

Non sono stati eseguiti o riprovati job, modificati scheduler, inviati
promemoria o alterati dati delle schede. Il salvataggio non chiude i limiti
operativi riportati nei verbali datati.
