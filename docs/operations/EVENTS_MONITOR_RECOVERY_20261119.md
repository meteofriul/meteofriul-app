# Monitor Eventi: verifica del 19 novembre 2026

Ramo `codex/events-monitor-recovery-20261119`, separato dal recupero delle
fonti attive nella PR 48. Questo intervento riguarda soltanto i monitor in
sola lettura di Palazzo Attems e GiroFVG. Non modifica il catalogo pubblico,
non approva schede e non cambia la pianificazione del job.

## Palazzo Attems

L'API ufficiale espone ora anche percorsi annidati, per esempio
`/italia-settanta-165450/design-176458/musica-176459`. Il lettore degli ID
accettava solo un segmento e faceva fallire l'intero monitor. Ora estrae
l'ultimo ID soltanto da percorsi locali con segmenti `slug-id` validi; rifiuta
URL esterni, query e percorsi non conformi. La prova in sola lettura del 19
novembre ha completato il confronto: due schede verificate, tre casi con
informazioni insufficienti e modifiche all'inventario da valutare. Non li
considera pubblicabili.

## GiroFVG

Il sitemap ufficiale contiene 50 voci recenti cambiate rispetto alla base
revisionata. Il limite di 30 letture di dettaglio resta invariato. Il
monitor completa il confronto delle sette categorie, segnala il numero
delle voci non approfondite e mostra un campione dei loro URL ufficiali.
La copertura rimane esplicitamente incompleta; gli articoli non letti non
diventano eventi. La segnalazione principale appare tra i primi dieci
rilievi del job. La prova del 19 novembre ha contato 12.316 URL nel
sitemap, 90 pagine di categoria attese e 89 lette; la pagina storica
`/fiere-e-mostre?start=168` continua a rispondere con un errore noto.

## Verifica e seguito

I test coprono i percorsi annidati e il limite GiroFVG con modifiche
contemporanee alle schede attive. Restano da revisionare editorialmente i
50 URL cambiati e i tre casi Attems, senza aggiornare automaticamente la
base di confronto. La prima esecuzione del job ordinario dopo l'eventuale
promozione delle PR resta una verifica distinta. I nuovi comandi Eventi
nel pannello online restano non attivati.
