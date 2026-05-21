# PROMPT LOG - MLPG Project
Registro delle modifiche e dei test effettuati sui prompt.

## [15 Maggio 2026] - Setup Iniziale
- **Azione:** Creato `system_mlpg.md` basato sulla Specifica v3.0.
- **Obiettivo:** Definire il comportamento del tutor e il formato JSON di output.
- **Risultato atteso:** L'LLM deve restituire esattamente 3 moduli validabili via Pydantic.

## [15 Maggio 2026] - Prompt aggiornati
- **Azione:** Aggiornato prompt del tutor per richiedere risposta JSON-only e `spiegazione_semplificata` in caso di confusione.
- **Obiettivo:** Assicurare che il modello non generi testo libero oltre al JSON e che fornisca spiegazioni semplificate quando l'utente dice di non capire.
- **Risultato atteso:** Risposta valida JSON con campo `spiegazione_semplificata` e nessun modulo rigenerato inutilmente.

- **Azione:** Aggiunta logica di parsing in `src/generator.py` per estrarre JSON da risposte contenenti blocchi markdown.
- **Obiettivo:** Rendere robusto il processo di validazione anche quando Gemini ritorna codice o testo extra.
- **Risultato atteso:** Valutazioni e spiegazioni alternative processate correttamente senza errori di parsing.

- **Azione:** Aggiunta prompt di chiusura empatica personalizzata in `genera_saluto_finale()`.
- **Obiettivo:** Generare un saluto finale motivante e rassicurante, diverso se l'utente ha interrotto per dubbi.
- **Risultato atteso:** Saluto umano in italiano, con tono incoraggiante e rassicurante.

## [19 Maggio 2026] - Prompt per spiegazioni mirate ai livelli intermedi/avanzati
- **Azione:** Aggiornato `genera_spiegazione_alternativa()` perché risponda in modo differenziato secondo il livello `base/intermedio/avanzato`.
- **Obiettivo:** Fornire spiegazioni più utili per utenti intermedi/avanzati usando esempio pratico e passaggi chiari.
- **Risultato atteso:** L'AI fornisce una spiegazione mirata al livello e un output JSON strutturato con contenuti di supporto.

- **Azione:** Modificato `main.py` per chiedere un dubbio specifico e passare quel contesto al prompt.
- **Obiettivo:** Ridurre l'ambiguità del feedback dell'utente e indirizzare meglio la spiegazione alternativa.
- **Risultato atteso:** Il tutor risponde a un punto preciso di confusione e non ripete un modulo inutile.

## [19 Maggio 2026] - Web interface e Streamlit
- **Azione:** Creato `app.py` (Flask) e `streamlit_app.py` con interfaccia Streamlit.
- **Obiettivo:** Rendere il tutor fruibile tramite browser con UI grafica e percorsi interattivi.
- **Risultato atteso:** L’utente può usare il tutor via web, generare moduli e richiedere chiarimenti mirati senza terminale.

- **Azione:** Aggiornato `requirements.txt` includendo `flask` e `streamlit`.
- **Obiettivo:** Assicurare che l’ambiente supporti le nuove interfacce web.
- **Risultato atteso:** Installazione completa delle dipendenze per eseguire sia Flask che Streamlit.

---
*Aggiungi qui le prossime modifiche quando testerai i prompt su VS Code.*