# AAB 0.1.15 / 300035 — test interno del 23 ottobre 2026

## Esito

**Disponibile per il solo account del proprietario nel test interno.**
La Console conferma pubblicazione interna alle **09:59 Europe/Rome**,
release `300035 (0.1.15)`. Una sola mailing list selezionata, con un solo
account verificato; le altre liste restano escluse. Nessuna modifica ai tester.
Produzione riletta dopo l'operazione: **0.1.14 / 300031**, invariata.

Usato esclusivamente il bundle archiviato, senza rigenerazione:
`meteofriul-300035-0.1.15.aab`, 73.017.265 byte, SHA256
`1bcf6a32348eee0f098f475c179523a309d962a86c3faf8736a0bd29a1622762`.
Package `com.meteofriul.app`; sorgente `5e9bc7dcdc6183a2fc43ada2dea3dfb22f2a3dc1`.
Firma e identità già verificate nel [verbale di build](ANDROID_0.1.15_300035_BUILD_20261023.md).
CI dei record `39918859098` verde su `367a0103`; ramo release pulito prima dell'upload.

Sponsor riconfermati alle 08:01:20 UTC: `enabled=false`, zero campagne,
revisione 117. Pannello e sincronizzazione sponsor non attivati.
Nessuna installazione, nuovo deploy, invio manuale o pubblicazione in produzione.

## Convalida Play e limiti

La revisione mostra **zero errori bloccanti e un avviso**: simboli di debug
nativi non caricati. È il limite già noto delle quattro librerie transitive,
non il mapping Java/Kotlin: il **mapping ReTrace è allegato** automaticamente.
Non sono stati inventati simboli né cambiata la toolchain per eliminare l'avviso.

| Area | Riscontro della nuova 300035 e limite |
| --- | --- |
| Edge-to-edge / inset | Nessun nuovo errore bloccante nella revisione; Android 15/16, gesti, cutout e tastiera restano NON VERIFICATI sul nuovo pacchetto |
| API system bar deprecate | Gli avvisi della dashboard Produzione sono etichettati 300031; non dimostrano né escludono rilievi della 300035. Restano gli avvisi delle dipendenze documentati in build |
| Orientamento / schermi grandi | Nessun dispositivo perso rispetto alla release interna precedente; layout small/normal/large/xlarge dichiarati. Tablet e multi-window NON VERIFICATI |
| R8 / risorse | Console: ottimizzazione DEX alta, 89%; offuscamento 91%; riduzione 91%; modalità completa, riduzione risorse ottimizzata. Suggerimento AGP 9.0 per repackaging, non requisito bloccante; nessun upgrade eseguito |

Play riporta supporto pagine da 16 kB, target SDK 36 e minimo 24. La classificazione
statica non sostituisce l'avvio reale. Report pre-lancio: nessun risultato
disponibile nella pagina Panoramica al momento della verifica; nessun test
cloud manuale avviato e nessuna configurazione cambiata. Non è un PASS runtime.

## Registro e prossima verifica

- [Release nella Console](https://play.google.com/console/u/0/developers/7317561924451916933/app/4972150571875270846/tracks/4700755128382710882/releases/18/details).
- [Accettazione append-only](../../release-history/android-play/20261023T080003228Z-play-accepted-05f3f1ff4aaa450cb3219d1ac87f6458.evidence.json); riserva e manifesto di build preesistenti invariati.
- [Ricevuta strutturata](evidence/release-0.1.15-300035-upload-20261023/verification.json).
- Evidenze private e screenshot nell'archivio canonico ignorato `release-artifacts/android-play/evidence-300035/play-upload-20261023/`; solo hash e riscontri non personali versionati.

L'aggiornamento deve essere provato dal proprietario attraverso Play. Rilevare
la preferenza Posizione **prima e subito dopo** l'aggiornamento, poi verificare
avvio/ripresa minificati e stati aria/pollini IT/FUR. La 300033 rimane l'ultimo
pacchetto osservato sul telefono; non attribuire le sue prove alla 300035.
PR 11 in bozza e promozione a main sospesa fino ai controlli pertinenti.
La candidata Web della stessa sorgente resta preparata e non pubblicata.
