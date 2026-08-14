# Diario Autista PWA corretta

Carica nella ROOT della repository:
- index.html
- manifest.json
- service-worker.js
- icon-192.png
- icon-512.png

GitHub Pages:
Settings > Pages > Deploy from a branch > main > /(root) > Save

Se avevi già caricato la PWA difettosa:
1. sostituisci tutti i file con questi;
2. attendi GitHub Pages 1-2 minuti;
3. in Chrome ricarica la pagina;
4. se appare ancora la vecchia versione, elimina i dati del sito / disinstalla la vecchia PWA e riapri il sito.

Questa versione inserisce il codice PWA solo dopo la chiusura dello script principale,
senza alterare il JavaScript del Diario.
