# Workflow für Artikel und Stories (Quartalszahlen)

Gilt für alle Artikel, die Claude schreibt. Stand 05.11.2026, nach Rückmeldung von Divi: Texte wirkten immer gleich.

1. **Zuerst recherchieren, dann schreiben.** Neben der Unternehmensunterlage (Präsentation, Mitteilung) immer nach den allerneuesten Berichten zum selben Ereignis suchen (Agenturen, Fachportale, Analystenschätzungen, Konsens). Fragen: Worauf konzentrieren sich die Berichte? Was wurde erwartet? Was überrascht? Was ist das eigentliche Thema des Quartals?
2. **Fokus setzen.** Der Artikel erzählt eine Geschichte, nicht eine Kennzahlenliste: Was ist passiert, warum, wie ist es einzuordnen (Erwartung, Vorjahr, Risiken, Ausblick). Gegenargumente und andere Auslöser immer aufnehmen, ausgewogen bleiben.
3. **Story-Text (`story_text`) = drei kurze Absätze mit unterschiedlichen Themen**, getrennt durch `\n` in der Kopfzeile, z. B.: (1) Ergebnis gegen Erwartung und der Hauptgrund, (2) was das Kerngeschäft zeigt, gute und schlechte Seiten, (3) Ausblick, Dividende, Risiko, Einordnung. Kein Kurs. Keine Wiederholung der Kopfzeile mit Umsatz und Gewinn.
4. **Zahlen aus Fremdquellen kennzeichnen** (z. B. Konsens, Ausblick aus der Telefonkonferenz) und unter dem Artikel als Quelle verlinken. Was nur eine Quelle sagt, als solches formulieren.
5. **Story-Aufbau:** oben links kleines Logo, rechts Umsatz und Gewinn mit Entwicklung, dann Chart (Folienbild oder eigenes Diagramm der Veränderung zum Vorjahr), dann Text, unten CEO (und Kursbild, wenn vorhanden).
6. Aufmacherfoto: Fotoanfrage in `tools/asset.request` gleich mit anlegen.
