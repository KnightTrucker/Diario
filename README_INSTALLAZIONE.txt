# TruckNavigator - aggiornamento automatico divieti

Carica questi file nel repository GitHub `KnightTrucker/TruckNavigator` mantenendo esattamente i percorsi:

- `index.html` nella cartella principale
- `road_safety.json` nella cartella principale
- `.github/workflows/update-road-safety.yml` nel percorso indicato

## Cosa succede

GitHub Actions esegue l'aggiornamento automaticamente ogni giorno alle 03:17 UTC.
Puoi anche avviarlo manualmente da:

GitHub -> repository TruckNavigator -> Actions -> Update road safety database -> Run workflow

Il workflow legge OpenStreetMap tramite Overpass API, ricostruisce `road_safety.json` e, se cambia, esegue automaticamente un commit nel repository.

Nell'app, il pulsante **AGGIORNA DIVIETI** scarica l'ultima versione di `road_safety.json` da GitHub Pages e aggiorna la copia locale, senza aprire il selettore file.

## Importante

Nel repository GitHub deve essere consentito al workflow di scrivere nel repository.
Con il file fornito è già impostato `permissions: contents: write`.
Se l'organizzazione/account blocca comunque la scrittura dei workflow, abilita:
Settings -> Actions -> General -> Workflow permissions -> Read and write permissions.

Non inserire token GitHub dentro `index.html`.
