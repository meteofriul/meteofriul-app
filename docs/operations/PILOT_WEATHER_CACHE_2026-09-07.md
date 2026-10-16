# Cache e verifica meteo pilota

- Verifica automatica ogni 10 minuti, solo a pagina visibile; refresh manuale
  resta esplicito. Il timer legacy mantiene i suoi parametri.
- Il comune selezionato viene aggiornato anche se la rubrica aperta non è Meteo.
- Verifica del bundle persistita: riapertura entro 10 minuti riusa il bundle
  solo se comune, ora prevista, corsa e controlli CAMS restano validi.
- Risposte recuperate per errore di rete non spostano la data di verifica.
- I metadati immutabili sono riusati solo se coincidono con l'hash del padre;
  indici latest e revoche continuano a essere controllati. Refresh forzato
  mantiene la possibilità di richiedere nuovamente tutti gli oggetti.
- Home e Previsioni rieseguono la selezione meteo al cambio d'ora nella pilota.
  Il controllo di validità del campione impedisce il riuso del bundle dell'ora
  precedente; i dati grezzi e i metadati già scaricati restano riutilizzabili.

Verifiche: 128 test passati (runtime, client integrità/cache, cambio comune,
policy refresh e benchmark reale), più 2 test rendering route mirati.
La suite completa AppRoutes ha un disallineamento estraneo: il test attende
"Live" ma la navigazione esistente mostra "Territorio"; non modificato qui.
Browser ricontrollato: Home Pordenone mostra meteo, pollini e 68 eventi.

Benchmark dopo modifica: altri comuni nella stessa sessione 5 richieste invece
di 9; meteo 359–422 ms e completamento CAMS 646–853 ms nel campione.
Ritorno immediato: 0 richieste. Non è una misura touch-to-paint né una prova
su rete mobile rallentata. Nessun deploy beta, nuovo job o modifica cloud.
