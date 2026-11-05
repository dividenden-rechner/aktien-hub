#!/usr/bin/env python3
"""Schreibt SEO- und LLM-taugliche Texte (Kurzantwort, Rechenbeispiel, Annahmen, Fragen, Verweise) und strukturierte Daten
(WebApplication, FAQPage, BreadcrumbList) in die Rechnerseiten. Ersetzt jeweils den Bereich zwischen <!--seo-start--> und <!--seo-end-->.

Aufruf: python3 tools/build_seo.py
Die Rechenbeispiele nutzen die Voreinstellungen der Rechner (Stand 2. November 2026). Aendern sich Voreinstellungen oder Rechenwege,
muessen die Zahlen hier angepasst werden.
"""
import html, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://dividenden-rechner.github.io/aktien-hub/"
H = html.escape

R = {  # Verweise (Pfad ab Startseite, Text)
    "start": ("", "Dividenden-Rechner"),
    "vergleich": ("dividenden-vergleich/", "Dividenden-Vergleich: zwei Aktien oder Strategien gegenüberstellen"),
    "leben": ("von-dividenden-leben/", "Von Dividenden leben: nötiges Kapital berechnen"),
    "luecke": ("rentenluecke/", "Rentenlücke füllen: Sparrate und Kapital berechnen"),
    "strategie": ("rentenstrategie/", "Rentenstrategie: Dividenden, Entnahme oder Zeitrente"),
    "reinv": ("dividenden-reinvestieren/", "Dividenden reinvestieren: der Zinseszinseffekt"),
    "av": ("altersvorsorgedepot/", "Altersvorsorgedepot-Rechner und Anbieter im Vergleich"),
    "vap": ("vorabpauschale-rechner/", "Vorabpauschale berechnen"),
    "etf": ("etf-rechner/", "ETF-Sparplan-Rechner"),
    "steuer": ("grundlagen/dividendenbesteuerung/", "Dividendenbesteuerung in Deutschland"),
    "rendite": ("grundlagen/dividendenrendite/", "Dividendenrendite erklärt"),
    "quelle": ("fortgeschrittene/quellensteuer/", "Quellensteuer auf ausländische Dividenden"),
    "thes": ("grundlagen/ausschuettend-thesaurierend/", "Ausschüttend oder thesaurierend"),
    "dwachs": ("fortgeschrittene/dividendenwachstum/", "Dividendenwachstum bewerten"),
    "strat": ("fortgeschrittene/dividendenstrategien/", "Dividendenstrategien im Überblick"),
    "einkommen": ("einfuehrung/dividendeneinkommen-berechnen/", "Dividendeneinkommen berechnen"),
    "etfoder": ("einfuehrung/dividenden-etf-oder-einzelaktien/", "Dividenden-ETF oder Einzelaktien"),
    "quote": ("grundlagen/ausschuettungsquote/", "Ausschüttungsquote erklärt"),
    "falle": ("grundlagen/dividendenfalle/", "Dividendenfalle erkennen"),
    "reartikel": ("fortgeschrittene/dividenden-reinvestieren/", "Dividenden reinvestieren: Artikel"),
    "hub": ("aktien-hub/", "Aktien-Hub: Kennzahlen und Dividendenverlauf jeder Aktie"),
    "depot": ("depot/", "Depot-Tracker mit Dividendenkalender"),
}

C = {}

C[""] = dict(
    name="Dividenden-Rechner", crumb=None,
    title="Dividendenrechner: Dividenden, Zinseszins und Steuer berechnen | Dividenden-Rechner",
    desc="Kostenloser Dividendenrechner: Berechne Endkapital, Netto-Dividenden und Steuer für deine Sparrate, Dividendenrendite und Dividendenwachstum, mit Reinvestition.",
    intro=None,
    sections=[
        ("Wie funktioniert der Dividendenrechner?", """<p>Du gibst Startkapital, monatliche Sparrate, Dividendenrendite, Dividendenwachstum, Kurszuwachs und Anlagedauer ein und wählst, ob die Dividenden reinvestiert werden. Der Rechner simuliert dann Jahr für Jahr: Die Sparrate kommt dazu, das Kapital wächst mit dem Kurszuwachs, auf das Kapital wird die Dividende gezahlt, davon geht die Steuer ab, und bei Reinvestition fließt der Netto-Betrag zurück ins Depot. Danach steigt die Dividendenrendite um das Dividendenwachstum.</p>
<p>Als Ergebnis siehst du das Endkapital, die Summe der Netto-Dividenden und den Betrag, den du selbst eingezahlt hast. Alles läuft in deinem Browser, Eingaben werden nicht gespeichert.</p>"""),
        ("Rechenbeispiel mit den Voreinstellungen", """<p>Startkapital 10.000 Euro, Sparrate 200 Euro im Monat, Dividendenrendite 3 Prozent, Dividendenwachstum 5 Prozent pro Jahr, Kurszuwachs 4 Prozent pro Jahr, 20 Jahre, Steuersitz Deutschland (26,375 Prozent) und Reinvestition. Ergebnis: ein Endkapital von rund 166.656 Euro. Eingezahlt hast du 58.000 Euro (10.000 Euro Start plus 20 Jahre mal 2.400 Euro), die Netto-Dividenden summieren sich auf rund 57.373 Euro.</p>
<p>Ohne Reinvestition fließen die Dividenden auf dein Konto und werden nicht erneut angelegt, das Depot wächst dann langsamer. Wie groß der Unterschied ist, zeigt der <a href="dividenden-reinvestieren/">Rechner zum Reinvestieren</a>.</p>"""),
        ("Dividendenrendite, Dividendenwachstum und Kurszuwachs", """<ul>
<li><strong>Dividendenrendite:</strong> Dividende je Aktie geteilt durch den Kurs. Zahlt eine Aktie für 50 Euro 2 Euro Dividende im Jahr, liegt die Rendite bei 4 Prozent. Mehr dazu unter <a href="grundlagen/dividendenrendite/">Dividendenrendite erklärt</a>.</li>
<li><strong>Dividendenwachstum:</strong> Um wie viel Prozent die Dividende je Aktie pro Jahr steigt. Ein hohes Wachstum kann eine niedrige Startrendite mit den Jahren ausgleichen, siehe <a href="fortgeschrittene/dividendenwachstum/">Dividendenwachstum bewerten</a>.</li>
<li><strong>Kurszuwachs:</strong> Um wie viel Prozent der Aktienkurs pro Jahr steigt. Dividendenrendite und Kurszuwachs zusammen ergeben grob die Gesamtrendite.</li>
</ul>"""),
        ("Steuern auf Dividenden in Deutschland", """<p>Dividenden unterliegen der Abgeltungsteuer von 25 Prozent. Dazu kommt der Solidaritätszuschlag von 5,5 Prozent auf die Steuer, zusammen 26,375 Prozent, und auf Wunsch Kirchensteuer. Bis zum Sparer-Pauschbetrag von 1.000 Euro (2.000 Euro bei Paaren) sind Kapitalerträge im Jahr steuerfrei, wenn du deinem Broker einen Freistellungsauftrag erteilt hast. Bei ausländischen Aktien wird zusätzlich Quellensteuer im Herkunftsland einbehalten, die sich teilweise anrechnen lässt. Der Rechner verwendet einen Pauschalsatz auf die gesamte Dividende. Details stehen in den Artikeln <a href="grundlagen/dividendenbesteuerung/">Dividendenbesteuerung in Deutschland</a> und <a href="fortgeschrittene/quellensteuer/">Quellensteuer</a>.</p>"""),
    ],
    faq=[
        ("Was ist ein Dividendenrechner?", "Ein Dividendenrechner zeigt, wie sich Dividenden, Sparrate und Zinseszins auf dein Depot auswirken. Du gibst Annahmen zu Rendite, Wachstum und Steuer ein und siehst, wie hoch Endkapital und Netto-Dividenden nach der gewählten Laufzeit sein können."),
        ("Wie berechne ich die Dividendenrendite?", "Teile die Dividende je Aktie für ein Jahr durch den aktuellen Kurs und multipliziere mit 100. Beispiel: 2 Euro Dividende bei einem Kurs von 50 Euro ergeben 4 Prozent."),
        ("Wie viel bleibt von der Dividende netto übrig?", "In Deutschland bleiben von 1.000 Euro Dividende ohne Freibetrag und Kirchensteuer 736,25 Euro, weil 26,375 Prozent Steuer abgezogen werden. Mit freiem Sparer-Pauschbetrag kann die Steuer auf bis zu 1.000 Euro Kapitalerträge im Jahr entfallen."),
        ("Soll ich Dividenden reinvestieren oder auszahlen lassen?", "Wenn du das Geld nicht zum Leben brauchst, wächst das Depot durch Reinvestition schneller, weil auch die gekauften Aktien wieder Dividenden zahlen. Brauchst du das Einkommen, lässt du dir die Dividende auszahlen. Beide Wege kannst du im Rechner vergleichen."),
        ("Sind Dividenden sicher?", "Nein. Unternehmen können die Dividende kürzen oder streichen. Der Rechner zeigt ein Szenario auf Basis deiner Annahmen, keine Prognose. Wie du die Stabilität einer Dividende prüfst, steht unter Ausschüttungsquote und Free Cashflow."),
    ],
    related=["vergleich", "reinv", "leben", "etf", "steuer", "hub"],
)

C["dividenden-vergleich"] = dict(
    name="Dividenden-Vergleich", crumb="Dividenden-Vergleich",
    title="Dividenden-Vergleich: zwei Aktien oder Strategien berechnen | Dividenden-Rechner",
    desc="Vergleiche zwei Dividendenaktien oder Strategien mit gleichem Einsatz: Endkapital, Netto-Dividenden und der Zeitpunkt, ab dem die zweite Variante mehr ausschüttet.",
    intro="Vergleiche zwei Aktien oder Strategien mit gleichem Einsatz, zum Beispiel einen Dividendenzahler mit einem Wachstumswert. Der Rechner zeigt Endkapital, Netto-Dividenden und ab wann die eine Variante mehr ausschüttet als die andere.",
    sections=[
        ("Wann hilft der Dividenden-Vergleich?", """<p>Der Rechner beantwortet eine typische Frage von Dividendenanlegern: Nehme ich die Aktie mit der höheren Dividende heute oder die mit dem stärkeren Wachstum? Beide Varianten bekommen dasselbe Startkapital und dieselbe Sparrate und werden mit derselben Rechnung über die gleiche Zeit gerechnet. So siehst du, wann ein höheres Wachstum eine niedrigere Startrendite einholt.</p>"""),
        ("Rechenbeispiel mit den Voreinstellungen", """<p>Variante A ist ein Dividendenwert mit 3 Prozent Rendite, 5 Prozent Dividendenwachstum und 4 Prozent Kurszuwachs. Variante B ist ein Wachstumswert mit 1 Prozent Rendite, 10 Prozent Dividendenwachstum und 8 Prozent Kurszuwachs. Beide starten mit 10.000 Euro, sparen 200 Euro im Monat, laufen 20 Jahre und reinvestieren bei 26,375 Prozent Steuer.</p>
<ul>
<li>Endkapital A: rund 166.656 Euro, Endkapital B: rund 235.423 Euro.</li>
<li>Netto-Dividende im letzten Jahr: A rund 8.810 Euro, B rund 10.144 Euro. Der Wachstumswert zahlt ab Jahr 18 mehr Netto-Dividende pro Jahr als der Dividendenwert.</li>
<li>Summe der Netto-Dividenden über 20 Jahre: A rund 57.373 Euro, B rund 50.161 Euro. Der Dividendenwert zahlt insgesamt mehr aus, weil er von Anfang an mehr ausschüttet.</li>
</ul>
<p>Das Ergebnis hängt vollständig von den Annahmen ab. Setzt du für B nur 5 Prozent Dividendenwachstum an, sieht der Vergleich anders aus.</p>"""),
        ("Worauf du bei den Annahmen achten solltest", """<ul>
<li><strong>Wachstum ist die unsichere Größe.</strong> Die Dividendenrendite von heute kennst du, das Wachstum der nächsten 20 Jahre nicht. Prüfe die Annahme mit der Entwicklung der letzten fünf und zehn Jahre.</li>
<li><strong>Dividenden können gekürzt werden.</strong> Der Rechner lässt die Dividende jedes Jahr wachsen. In der Praxis sinken Dividenden in Krisen auch. Die <a href="grundlagen/ausschuettungsquote/">Ausschüttungsquote</a> hilft einzuschätzen, wie stabil eine Dividende ist.</li>
<li><strong>Eine hohe Rendite ist kein Qualitätsmerkmal.</strong> Sehr hohe Renditen zeigen oft einen gefallenen Kurs, siehe <a href="grundlagen/dividendenfalle/">Dividendenfalle</a>.</li>
<li><strong>Steuern:</strong> Der Rechner nimmt einen Pauschalsatz auf die gesamte Dividende ohne Freibetrag. Dein tatsächlicher Satz kann niedriger sein. Wählst du ein Land, kommt die Quellensteuer dazu: Der anrechenbare Teil wird auf die deutsche Steuer angerechnet, der Rest geht verloren, wenn du ihn nicht erstatten lässt. Die Sätze stammen aus den Länderseiten unter <a href="fortgeschrittene/quellensteuer/">Quellensteuer</a>.</li>
</ul>"""),
    ],
    faq=[
        ("Was ist wichtiger, Dividendenrendite oder Dividendenwachstum?", "Auf kurze Sicht zählt die Rendite, auf lange Sicht das Wachstum. Eine Aktie mit niedriger Startrendite und hohem Dividendenwachstum kann nach einigen Jahren mehr ausschütten als eine mit hoher Rendite und niedrigem Wachstum. Der Rechner zeigt, ab welchem Jahr das passiert."),
        ("Wie schätze ich das Dividendenwachstum einer Aktie?", "Schau dir die jährliche Wachstumsrate der Dividende der letzten fünf und zehn Jahre an, prüfe die Ausschüttungsquote und den Free Cashflow und setze lieber einen vorsichtigeren Wert an. Eine Anleitung steht unter Dividendenwachstum bewerten."),
        ("Kann ich auch einen ETF mit einer Einzelaktie vergleichen?", "Ja. Trage für den ETF seine Ausschüttungsrendite und die erwartete Kursentwicklung als eine Variante ein. Beachte, dass ausschüttende und thesaurierende ETFs steuerlich unterschiedlich behandelt werden."),
    ],
    related=["start", "reinv", "dwachs", "quote", "etfoder", "hub"],
)

C["von-dividenden-leben"] = dict(
    name="Von Dividenden leben", crumb="Von Dividenden leben",
    title="Von Dividenden leben: Wie viel Kapital brauchst du? | Dividenden-Rechner",
    desc="Berechne, wie viel Kapital du brauchst, damit Dividenden dein Wunsch-Einkommen decken, und wann du dein Ziel mit deiner Sparrate erreichst. Mit Steuer und Inflation.",
    intro="Wie viel Kapital brauchst du, damit die Dividenden dein gewünschtes Netto-Einkommen decken, und wann erreichst du das mit deiner Sparrate? Der Rechner berücksichtigt Steuer, Sparer-Pauschbetrag und Inflation.",
    sections=[
        ("So berechnest du das nötige Kapital", """<p>Die Grundformel lautet: nötiges Kapital = nötige Brutto-Dividende pro Jahr geteilt durch die Dividendenrendite. Die Brutto-Dividende ergibt sich aus deinem Wunsch-Netto plus Steuer. Weil der Sparer-Pauschbetrag steuerfrei bleibt, rechnet der Rechner so: Bis zum Pauschbetrag gilt die Dividende voll, darüber wird der Steuersatz abgezogen.</p>"""),
        ("Rechenbeispiel mit den Voreinstellungen", """<p>Gewünscht sind 2.000 Euro netto im Monat in heutiger Kaufkraft, also 24.000 Euro im Jahr. Die Dividendenrendite beträgt 3,5 Prozent, der Steuersatz 26,375 Prozent, der Sparer-Pauschbetrag 1.000 Euro.</p>
<ul>
<li>1.000 Euro bleiben steuerfrei, die restlichen 23.000 Euro sind nach Steuer gemeint. Brutto sind dafür 23.000 geteilt durch 0,73625, also rund 31.239 Euro nötig, plus die 1.000 Euro Freibetrag: rund 32.239 Euro im Jahr, das sind etwa 2.687 Euro im Monat.</li>
<li>Bei 3,5 Prozent Rendite ergibt das ein nötiges Kapital von rund 921.000 Euro.</li>
<li>Mit 10.000 Euro Startkapital, 500 Euro Sparrate, 4 Prozent Kurszuwachs, 5 Prozent Dividendenwachstum und 2 Prozent Inflation erreichst du dieses Ziel nach 23 Jahren.</li>
</ul>"""),
        ("Nötiges Kapital für typische Wunsch-Einkommen", """<p>Mit denselben Annahmen (3,5 Prozent Dividendenrendite, 26,375 Prozent Steuer, 1.000 Euro Sparer-Pauschbetrag, heutige Kaufkraft) brauchst du grob:</p>
<ul>
<li>1.000 Euro netto im Monat: rund 455.000 Euro</li>
<li>2.000 Euro netto im Monat: rund 921.000 Euro</li>
<li>3.000 Euro netto im Monat: rund 1.387.000 Euro</li>
</ul>
<p>Eine höhere Dividendenrendite senkt das nötige Kapital, bedeutet aber oft ein höheres Risiko. Bei 5 Prozent Rendite wäre es für 2.000 Euro im Monat deutlich weniger, dafür steigt das Risiko einer Kürzung.</p>"""),
        ("Worauf du achten solltest", """<ul>
<li><strong>Inflation:</strong> Das Ziel wächst im Rechner mit der Inflation mit, damit dein Einkommen real gleich bleibt.</li>
<li><strong>Schwankende Dividenden:</strong> Dividenden können sinken. Streue auf mehrere Unternehmen und Branchen und prüfe die <a href="grundlagen/ausschuettungsquote/">Ausschüttungsquote</a>.</li>
<li><strong>Nicht berücksichtigt:</strong> Kirchensteuer, Quellensteuer und mögliche Beiträge zur Krankenversicherung auf Kapitalerträge, etwa bei freiwillig Versicherten in der gesetzlichen Krankenversicherung.</li>
<li><strong>Kapital bleibt erhalten:</strong> Wer nur von Dividenden lebt, verkauft keine Aktien. Das kostet mehr Startkapital als ein Entnahmeplan, siehe <a href="rentenstrategie/">Rentenstrategie</a>.</li>
</ul>"""),
    ],
    faq=[
        ("Wie viele Dividenden brauche ich, um von Dividenden zu leben?", "Teile deinen Jahresbedarf vor Steuern durch die Dividendenrendite. Für 24.000 Euro netto im Jahr braucht es bei 3,5 Prozent Rendite und deutschen Steuern rund 921.000 Euro Kapital. Die genaue Zahl hängt von Rendite, Steuer und Sparer-Pauschbetrag ab."),
        ("Ab wie viel Euro Depot kann man von Dividenden leben?", "Das hängt vom Bedarf. Für 1.000 Euro netto im Monat sind es bei 3,5 Prozent Rendite rund 455.000 Euro, für 2.000 Euro netto rund 921.000 Euro. Ein ausreichendes Einkommen aus Dividenden braucht in der Regel ein sechsstelliges bis siebenstelliges Depot."),
        ("Warum steigt das Ziel im Rechner mit der Inflation?", "Das gewünschte Einkommen verliert mit der Zeit an Kaufkraft. Damit es real gleich bleibt, muss die Netto-Dividende mit der Inflation mitwachsen, das nötige Kapital steigt entsprechend."),
        ("Ist von Dividenden leben ohne Verkauf von Aktien möglich?", "Ja, wenn das Kapital groß genug ist und die Dividenden stabil bleiben. Dafür braucht es mehr Kapital als bei einem Entnahmeplan, der das Depot nach und nach aufbraucht."),
    ],
    related=["start", "luecke", "strategie", "steuer", "einkommen", "quote"],
)

C["rentenluecke"] = dict(
    name="Rentenlücke füllen", crumb="Rentenlücke füllen",
    title="Rentenlücke berechnen und füllen: Sparrate und Kapital | Dividenden-Rechner",
    desc="Berechne deine Rentenlücke und wie viel Kapital und Sparrate du brauchst, um sie mit ETFs oder Dividenden zu füllen. Mit Inflation, Steuer und zwei Varianten.",
    intro="Wie groß ist die Lücke zwischen deinem Wunsch-Einkommen und der gesetzlichen Rente, und wie viel Kapital und Sparrate brauchst du, um sie zu füllen? Der Rechner zeigt zwei Wege: Kapitalverzehr und nur von Dividenden leben.",
    sections=[
        ("Was ist die Rentenlücke?", """<p>Die Rentenlücke ist die Differenz zwischen dem Netto-Einkommen, das du im Ruhestand haben möchtest, und der Netto-Rente, die du voraussichtlich bekommst. Deine voraussichtliche gesetzliche Rente steht in der jährlichen Renteninformation der Deutschen Rentenversicherung. Dort wird meist der Brutto-Betrag genannt. Davon gehen noch Beiträge zur Kranken- und Pflegeversicherung und gegebenenfalls Steuer ab. Trage im Rechner deshalb den Netto-Wert ein.</p>"""),
        ("Rechenbeispiel mit den Voreinstellungen", """<p>Du bist 35, gehst mit 67 in Rente und planst bis 90. Du wünschst dir 3.000 Euro netto im Monat, erwartest 1.800 Euro Netto-Rente, die Inflation liegt bei 2 Prozent, das Kapital erwirtschaftet bis zur Rente 6 Prozent und im Ruhestand 3 Prozent.</p>
<ul>
<li>Die Lücke beträgt 1.200 Euro im Monat in heutiger Kaufkraft. Bis zum Rentenbeginn, 32 Jahre später, steigt sie mit der Inflation auf rund 2.261 Euro.</li>
<li><strong>Kapitalverzehr:</strong> Du entnimmst jedes Jahr einen mit der Inflation steigenden Betrag bis 90, das Kapital ist dann aufgebraucht. Nötig sind rund 624.000 Euro bei Rentenbeginn, die Sparrate beträgt rund 557 Euro im Monat.</li>
<li><strong>Nur Dividenden:</strong> Das Kapital bleibt erhalten, du lebst von den Ausschüttungen (3,5 Prozent Rendite). Nötig sind rund 1.053.000 Euro, die Sparrate beträgt rund 940 Euro im Monat.</li>
</ul>"""),
        ("Worauf du achten solltest", """<ul>
<li><strong>Die Sparrate bleibt fest.</strong> Gehaltserhöhungen sind nicht eingerechnet. Wer die Sparrate später erhöht, braucht am Anfang weniger.</li>
<li><strong>Die Rendite ist eine Annahme.</strong> 6 Prozent sind kein Versprechen. Rechne zusätzlich mit 4 und 5 Prozent, um zu sehen, wie stark das Ergebnis schwankt.</li>
<li><strong>Staatliche Förderung:</strong> Ab 2027 gibt es das <a href="altersvorsorgedepot/">Altersvorsorgedepot</a> mit Zulagen von bis zu 540 Euro im Jahr. Das kann die nötige eigene Sparrate senken.</li>
<li><strong>Steuer auf Entnahmen:</strong> Beim Verkauf von Anteilen ist nur der Gewinnanteil steuerpflichtig. Der Rechner nimmt dafür eine Pauschale von 10 Prozent an, die du anpassen kannst.</li>
</ul>"""),
    ],
    faq=[
        ("Wie berechne ich meine Rentenlücke?", "Ziehe von dem Netto-Einkommen, das du im Ruhestand brauchst, die erwartete Netto-Rente ab. Für die Zukunft rechnest du die Lücke mit der Inflation hoch. Der Rechner übernimmt beides."),
        ("Wie viel muss ich sparen, um die Rentenlücke zu schließen?", "Das hängt von Lücke, Zeit bis zur Rente und Rendite ab. Im Beispiel mit 1.200 Euro Lücke, 32 Jahren Zeit und 6 Prozent Rendite sind es rund 557 Euro im Monat, wenn das Kapital im Ruhestand aufgebraucht werden darf."),
        ("Wo finde ich meine voraussichtliche Rente?", "In der jährlichen Renteninformation der Deutschen Rentenversicherung oder in deinem Online-Konto bei der Rentenversicherung. Beachte, dass dort meist ein Brutto-Betrag steht."),
        ("Reicht ein ETF-Sparplan, um die Rentenlücke zu schließen?", "Ein regelmäßig besparter Welt-ETF kann das Kapital liefern. Ob es reicht, hängt von Sparrate, Laufzeit und Rendite ab. Rechne die Variante mit dem ETF-Sparplan-Rechner nach."),
    ],
    related=["start", "leben", "strategie", "av", "etf", "strat"],
)

C["rentenstrategie"] = dict(
    name="Rentenstrategie", crumb="Rentenstrategie",
    title="Rentenstrategie-Vergleich: Dividenden, 4-Prozent-Entnahme oder Zeitrente | Dividenden-Rechner",
    desc="Vergleiche drei Wege, ein Depot im Ruhestand zu nutzen: nur Dividenden, inflationsangepasste Entnahme wie die 4-Prozent-Regel und feste Zeitrente. Mit Steuer und Inflation.",
    intro="Drei Wege, ein Depot im Ruhestand zu nutzen: nur von den Dividenden leben, jedes Jahr einen inflationsangepassten Betrag entnehmen oder eine feste Zeitrente beziehen. Der Rechner stellt sie nebeneinander.",
    sections=[
        ("Die drei Strategien im Überblick", """<ul>
<li><strong>A: Nur Dividenden.</strong> Du behältst die Aktien und gibst nur die Netto-Dividenden aus. Das Kapital bleibt erhalten und wächst mit.</li>
<li><strong>B: Inflationsangepasste Entnahme.</strong> Im ersten Jahr entnimmst du eine gewählte Quote vom Startkapital, zum Beispiel 4 Prozent, danach jedes Jahr den Betrag plus Inflation. Die bekannte 4-Prozent-Regel stammt aus US-Untersuchungen und ist keine Garantie.</li>
<li><strong>C: Feste Zeitrente.</strong> Ein gleichbleibender Betrag, der das Kapital genau bis zum Endalter aufbraucht. Er steigt nicht mit der Inflation.</li>
</ul>"""),
        ("Rechenbeispiel mit den Voreinstellungen", """<p>Kapital bei Rentenbeginn 500.000 Euro, Alter 67, Planung bis 95, Gesamtrendite 6 Prozent, Dividendenrendite 3,5 Prozent, Dividendenwachstum 4 Prozent, Inflation 2 Prozent, Steuer auf Dividenden 26,375 Prozent, Steuer auf Entnahmen pauschal 10 Prozent, Entnahmequote 4 Prozent.</p>
<ul>
<li><strong>A (Dividenden):</strong> rund 1.074 Euro netto im Monat zu Beginn, nach 19 Jahren rund 2.262 Euro. Am Ende sind noch rund 998.000 Euro Kapital da.</li>
<li><strong>B (Entnahme):</strong> rund 1.500 Euro im Monat zu Beginn, nach 19 Jahren rund 2.185 Euro. Am Ende sind noch rund 769.000 Euro da.</li>
<li><strong>C (Zeitrente):</strong> rund 2.639 Euro im Monat, gleichbleibend. Das Kapital ist mit 95 aufgebraucht.</li>
</ul>
<p>Strategie C zahlt zu Beginn am meisten, verliert aber durch die Inflation an Kaufkraft. Strategie A zahlt zu Beginn am wenigsten, hinterlässt aber das größte Kapital.</p>"""),
        ("Worauf du achten solltest", """<ul>
<li><strong>Die Rendite ist konstant gerechnet.</strong> In der Wirklichkeit schwanken Märkte. Fällt der Markt gleich zu Beginn des Ruhestands stark, trifft das Entnahmepläne härter, weil du auch in schlechten Phasen verkaufst.</li>
<li><strong>Dividenden können gekürzt werden.</strong> Auch Strategie A ist nicht sicher, wenn Dividenden sinken.</li>
<li><strong>Steuer:</strong> Dividenden werden voll besteuert, bei Entnahmen nur der Gewinnanteil. Die Pauschale von 10 Prozent ist eine grobe Annahme.</li>
<li><strong>Mischformen sind möglich.</strong> Viele nutzen die Dividenden als Basis und entnehmen bei Bedarf zusätzlich.</li>
</ul>"""),
    ],
    faq=[
        ("Was ist die 4-Prozent-Regel?", "Eine Faustregel aus US-Untersuchungen: Im ersten Ruhestandsjahr entnimmst du 4 Prozent des Depots und passt den Betrag danach jedes Jahr an die Inflation an. Ob das für deinen Zeitraum und deine Märkte reicht, ist nicht garantiert."),
        ("Welche Rentenstrategie ist die beste?", "Das hängt von deinen Zielen ab. Wer das Kapital vererben oder erhalten will, nimmt eher Dividenden. Wer zu Beginn mehr Einkommen braucht, nimmt Entnahme oder Zeitrente. Eine beste Lösung für alle gibt es nicht."),
        ("Wie lange hält mein Depot bei einer Entnahme von 4 Prozent?", "Im Beispiel mit 6 Prozent Rendite und 2 Prozent Inflation ist das Kapital bis 95 nicht aufgebraucht. Bei schlechterer Rendite oder höherer Inflation kann es früher leer sein. Der Rechner nennt das Alter, in dem das Kapital ausgeht."),
    ],
    related=["start", "leben", "luecke", "strat", "steuer", "quote"],
)

C["dividenden-reinvestieren"] = dict(
    name="Dividenden reinvestieren", crumb="Dividenden reinvestieren",
    title="Dividenden reinvestieren: So viel bringt der Zinseszinseffekt | Dividenden-Rechner",
    desc="Berechne, was es bringt, Dividenden wieder anzulegen statt auszugeben: Depotwert mit und ohne Reinvestition, Netto-Dividenden und der Vorteil in Euro.",
    intro="Was bringt es, Dividenden wieder anzulegen, statt sie auszugeben? Der Rechner stellt beide Wege nebeneinander und zeigt den Vorteil in Euro.",
    sections=[
        ("So funktioniert der Zinseszinseffekt bei Dividenden", """<p>Mit Reinvestition kaufst du für die Netto-Dividende weitere Aktien. Diese zahlen im nächsten Jahr selbst Dividenden, und so wächst das Depot schneller. Ohne Reinvestition fließt die Dividende auf dein Konto und arbeitet nicht weiter. Der Vorteil ist die Differenz der beiden Depotwerte am Ende.</p>"""),
        ("Rechenbeispiel mit den Voreinstellungen", """<p>Startkapital 10.000 Euro, Sparrate 200 Euro im Monat, Dividendenrendite 3 Prozent, Dividendenwachstum 5 Prozent, Kurswachstum 4 Prozent, 20 Jahre, Steuer 26,375 Prozent.</p>
<ul>
<li>Depotwert mit Reinvestition: rund 133.738 Euro.</li>
<li>Depotwert ohne Reinvestition: rund 96.237 Euro. Der Vorteil beträgt rund 37.500 Euro.</li>
<li>Ohne Reinvestition hast du über die 20 Jahre zusätzlich rund 23.805 Euro Netto-Dividenden ausgezahlt bekommen. Fair verglichen sind es also 133.738 Euro im Depot gegen 96.237 Euro im Depot plus 23.805 Euro auf dem Konto, zusammen rund 120.042 Euro.</li>
<li>Die Netto-Dividende pro Monat im letzten Jahr liegt mit Reinvestition bei rund 277 Euro, ohne bei rund 204 Euro.</li>
</ul>"""),
        ("Worauf du achten solltest", """<ul>
<li><strong>Die Dividende wird zuerst versteuert.</strong> Nur der Netto-Betrag kann reinvestiert werden. Der Rechner zieht die Steuer deshalb vor der Wiederanlage ab.</li>
<li><strong>Der Effekt wächst mit der Laufzeit.</strong> Nach 10 Jahren ist der Unterschied klein, nach 30 Jahren deutlich.</li>
<li><strong>Reinvestieren ist nicht immer richtig.</strong> Wenn du das Einkommen brauchst, ist Auszahlen sinnvoll. Wenn eine einzelne Aktie schon einen großen Teil des Depots ausmacht, kann es besser sein, die Dividende breiter zu streuen.</li>
<li><strong>Thesaurierende ETFs</strong> reinvestieren automatisch, unterliegen aber der Vorabpauschale, siehe <a href="grundlagen/ausschuettend-thesaurierend/">Ausschüttend oder thesaurierend</a>.</li>
</ul>"""),
    ],
    faq=[
        ("Lohnt es sich, Dividenden zu reinvestieren?", "Wenn du die Dividenden nicht zum Leben brauchst, ja. Du kaufst mehr Aktien, die wiederum Dividenden zahlen. Im Beispiel mit 20 Jahren ergibt das rund 37.500 Euro mehr Depotwert."),
        ("Werden Dividenden beim Reinvestieren besteuert?", "Ja. Die Dividende wird zuerst versteuert und nur der Netto-Betrag kann reinvestiert werden. Ein Freistellungsauftrag kann die Steuer bis zum Sparer-Pauschbetrag senken."),
        ("Was ist der Unterschied zwischen reinvestieren und thesaurieren?", "Beim Reinvestieren kaufst du selbst von der ausgezahlten Dividende neue Aktien oder ETF-Anteile. Beim Thesaurieren behält der Fonds die Erträge ein und legt sie automatisch wieder an. Steuerlich greift bei thesaurierenden Fonds die Vorabpauschale."),
    ],
    related=["start", "vergleich", "reartikel", "thes", "vap", "steuer"],
)

C["altersvorsorgedepot"] = dict(
    name="Altersvorsorge-Depot", crumb="Altersvorsorge-Depot",
    title="Altersvorsorgedepot-Rechner und Anbieter im Vergleich 2027 | Dividenden-Rechner",
    desc="Altersvorsorgedepot berechnen: Zulagen, Depotwert und Auszahlung im Vergleich zum ETF-Sparplan, dazu die Anbieter 2027 mit Kosten (Trade Republic, Scalable, ING, Deka, comdirect).",
    intro="Das Altersvorsorgedepot löst ab 2027 die Riester-Rente ab. Der Rechner zeigt Depotwert, Zulagen und Auszahlung und stellt einen ETF-Sparplan ohne Förderung daneben. Unten findest du die Anbieter mit Kosten und Quellen.",
    sections=[
        ("Rechenbeispiel mit den Voreinstellungen", """<p>Du bist 30, zahlst 150 Euro im Monat ein, die Auszahlung beginnt mit 67 und läuft bis 85. Das Depot erzielt 6 Prozent vor Kosten, die Kosten liegen bei 1,0 Prozent im Jahr (gesetzliche Obergrenze für das Standarddepot), in der Auszahlphase sind es 3 Prozent, dein Steuersatz im Alter beträgt 20 Prozent.</p>
<ul>
<li>Depotwert bei Auszahlungsbeginn: rund 241.965 Euro. Davon sind 66.600 Euro eigene Beiträge, 19.980 Euro Zulagen und 155.385 Euro Erträge.</li>
<li>Die Zulage beträgt 540 Euro im Jahr: 150 Euro im Monat sind 1.800 Euro im Jahr, die Förderung liegt damit bei 30 Prozent der Beiträge.</li>
<li>Die Auszahlung liegt bei rund 1.157 Euro im Monat nach Steuer. Der ETF-Sparplan mit 0,2 Prozent Kosten ohne Förderung liefert rund 1.170 Euro im Monat.</li>
</ul>
<p>Der Vergleich zeigt: Bei der Kostenobergrenze von 1,0 Prozent frisst die Kostenlast die Förderung im Beispiel fast auf. Sinken die Kosten im Altersvorsorgedepot auf 0,5 Prozent, steigt die Auszahlung auf rund 1.296 Euro im Monat, bei 0,2 Prozent auf rund 1.388 Euro. Die Kosten des Anbieters entscheiden deshalb mit, ob sich das Altersvorsorgedepot gegenüber einem normalen ETF-Sparplan lohnt.</p>"""),
        ("Mit Kind und Berufseinsteiger-Bonus", """<p>Ein Beispiel mit anderen Eingaben: Du bist 24, bekommst ein Kind (Alter 0, 18 Jahre Kinderzulage) und erhältst den einmaligen Bonus von 200 Euro. Bei 150 Euro im Monat steigt die Zulage dann auf 840 Euro im Jahr, zusammen rund 28.820 Euro Zulagen und Bonus, und der Depotwert bei Auszahlungsbeginn auf rund 370.600 Euro. Das Alter der Kinder trägst du im Rechner ein, er rechnet dann genau aus, wie viele Jahre die Kinderzulage läuft (bis 18, bei Ausbildung oder Studium bis 25). Der Anteil der Förderung am Ergebnis wächst, je früher du beginnst und je mehr Kinder zulageberechtigt sind.</p>"""),
        ("Für wen lohnt sich das Altersvorsorgedepot?", """<ul>
<li><strong>Eltern:</strong> Die Kinderzulage von 100 Prozent je eingezahltem Euro bis 300 Euro im Jahr und Kind ist die stärkste Förderung. Sie läuft, solange Kindergeld gezahlt wird.</li>
<li><strong>Berufseinsteiger:</strong> Bonus von 200 Euro bei Abschluss vor dem 25. Geburtstag und viel Zeit für den Zinseszins.</li>
<li><strong>Bestehende Riester-Sparer:</strong> Bestehende Verträge laufen weiter, neue Riester-Verträge gibt es ab 2027 nicht mehr. Ein Wechsel ist möglich, kann aber Kosten verursachen.</li>
<li><strong>Weniger sinnvoll</strong> kann es sein, wenn du früh an das Geld willst. Die Auszahlung beginnt frühestens mit 65.</li>
</ul>"""),
    ],
    faq=[
        ("Wann startet das Altersvorsorgedepot?", "Neue Verträge sind ab dem 1. Januar 2027 möglich. Das Gesetz hat der Bundestag am 27. März 2026 beschlossen, der Bundesrat hat am 8. Mai 2026 zugestimmt. Anbieter brauchen vorher eine Zertifizierung durch das Bundeszentralamt für Steuern."),
        ("Welcher Anbieter hat das günstigste Altersvorsorgedepot?", "Das lässt sich noch nicht verbindlich sagen. Anbieter wie flatex, Deka, Scalable Capital und ING nennen niedrige laufende Kosten, Trade Republic und weitere erstatten ETF-Kosten. Alle Angaben sind Ankündigungen. Der Vergleich unten zeigt den Stand mit Quellen."),
        ("Wie hoch sind die Kosten beim Altersvorsorgedepot?", "Das Standarddepot ist auf höchstens 1,0 Prozent Effektivkosten pro Jahr gedeckelt. Beim frei gestalteten Depot gibt es keinen gesetzlichen Deckel. Der Anbieterwechsel ist nach fünf Jahren kostenfrei, der neue Anbieter darf höchstens 150 Euro berechnen."),
        ("Kann ich im Rechner Anbieter vergleichen?", "Ja. Wähle oben einen Anbieter aus, dann übernimmt der Rechner dessen Kosten und die Dauer einer möglichen Erstattung. Unter dem Rechner siehst du alle Anbieter mit deinen Eingaben nebeneinander, sortiert nach der Auszahlung pro Monat. Die Angaben werden regelmäßig automatisch auf Änderungen geprüft."),
        ("Wird das Altersvorsorgedepot in der Ansparphase besteuert?", "Nein. In der Ansparphase fallen keine Steuern an, auch keine Vorabpauschale, und Umschichten löst keine Abgeltungsteuer aus. Die Auszahlung wird nachgelagert mit deinem persönlichen Steuersatz versteuert."),
    ],
    related=["luecke", "etf", "vap", "start", "etfoder", "depot"],
)

C["vorabpauschale-rechner"] = dict(
    name="Vorabpauschale berechnen", crumb="Vorabpauschale",
    title="Vorabpauschale berechnen: Rechner für ETF und Fonds 2026 | Dividenden-Rechner",
    desc="Berechne die Vorabpauschale und die fällige Steuer für deinen ETF oder Fonds: mit Basiszins 2026 (3,20 %), Teilfreistellung, Sparer-Pauschbetrag und Kaufmonat.",
    intro="Berechne die Vorabpauschale und die darauf fällige Steuer für einen Fonds oder ETF, mit Basiszins, Teilfreistellung, Sparer-Pauschbetrag und Kaufmonat.",
    sections=[
        ("So wird die Vorabpauschale berechnet", """<p>Die Vorabpauschale ist eine Mindestbesteuerung für Fonds, die kaum oder keine Erträge ausschütten. Du rechnest in vier Schritten:</p>
<ol>
<li><strong>Basisertrag:</strong> Fondswert am 1. Januar mal Basiszins mal 70 Prozent.</li>
<li><strong>Vorabpauschale:</strong> Basisertrag minus Ausschüttungen im Jahr. Sie ist nie höher als der tatsächliche Wertzuwachs plus Ausschüttungen und nie negativ.</li>
<li><strong>Teilfreistellung:</strong> Bei Aktienfonds sind 30 Prozent der Vorabpauschale steuerfrei, bei Mischfonds 15 Prozent.</li>
<li><strong>Steuer:</strong> Vom Rest bleibt der Sparer-Pauschbetrag steuerfrei. Darüber gelten 26,375 Prozent (25 Prozent Abgeltungsteuer plus Solidaritätszuschlag, ohne Kirchensteuer).</li>
</ol>
<p>Wer im laufenden Jahr kauft, bekommt die Vorabpauschale für jeden vollen Monat vor dem Kauf um ein Zwölftel gekürzt.</p>"""),
        ("Rechenbeispiel mit den Voreinstellungen", """<p>Ein Aktien-ETF ist am 1. Januar 10.000 Euro wert, am 31. Dezember 10.800 Euro, ohne Ausschüttung. Der Basiszins für 2026 beträgt 3,20 Prozent.</p>
<ul>
<li>Basisertrag: 10.000 mal 3,20 Prozent mal 70 Prozent = 224,00 Euro.</li>
<li>Die Vorabpauschale beträgt 224,00 Euro, weil der Wertzuwachs von 800 Euro höher ist.</li>
<li>Nach 30 Prozent Teilfreistellung sind 156,80 Euro steuerpflichtig.</li>
<li>Mit freiem Sparer-Pauschbetrag fällt keine Steuer an. Ohne Freibetrag wären es 156,80 Euro mal 26,375 Prozent, also rund 41,36 Euro.</li>
</ul>"""),
        ("Wann und wie wird die Vorabpauschale gezahlt?", """<ul>
<li>Die Vorabpauschale gilt als am ersten Werktag des Folgejahres zugeflossen. Dein Broker zieht die Steuer dann in der Regel vom Verrechnungskonto ein. Achte darauf, dass dort genug Geld liegt.</li>
<li>Ein Freistellungsauftrag senkt die Steuer, bis der Sparer-Pauschbetrag aufgebraucht ist.</li>
<li>Gezahlte Vorabpauschalen werden beim späteren Verkauf des Fonds angerechnet. Sie sind also eine Vorauszahlung und kein dauerhafter Verlust.</li>
<li>Ausschüttende Fonds zahlen weniger Vorabpauschale, weil die Ausschüttung abgezogen wird. Mehr dazu unter <a href="grundlagen/ausschuettend-thesaurierend/">Ausschüttend oder thesaurierend</a>.</li>
</ul>"""),
    ],
    faq=[
        ("Wie hoch ist der Basiszins für die Vorabpauschale 2026?", "Das Bundesfinanzministerium hat für 2026 einen Basiszins von 3,20 Prozent festgesetzt. Für andere Jahre trägst du den jeweils gültigen Wert ein."),
        ("Wann wird die Vorabpauschale abgebucht?", "Sie gilt als am ersten Werktag des Folgejahres zugeflossen. Dein Broker bucht die Steuer in der Regel Anfang Januar vom Verrechnungskonto ab."),
        ("Fällt die Vorabpauschale an, wenn der ETF im Minus ist?", "Nein. Die Vorabpauschale ist auf den tatsächlichen Wertzuwachs plus Ausschüttungen begrenzt und nie negativ. Hat der Fonds im Jahr verloren, fällt keine an."),
        ("Zahlen auch Aktien die Vorabpauschale?", "Nein. Die Vorabpauschale betrifft nur Investmentfonds und ETFs, nicht Einzelaktien."),
    ],
    related=["etf", "thes", "av", "steuer", "start", "etfoder"],
)

C["etf-rechner"] = dict(
    name="ETF-Rechner", crumb="ETF-Sparplan-Rechner",
    title="ETF-Sparplan-Rechner: Endwert nach Kosten und Steuern | Dividenden-Rechner",
    desc="Berechne, wie sich dein ETF-Sparplan entwickelt: Endwert vor und nach Steuern, mit Sparrate, Rendite, Kosten (TER), Teilfreistellung und Sparer-Pauschbetrag.",
    intro="Berechne, wie sich ein ETF-Sparplan entwickeln kann und was nach Kosten und Steuern übrig bleibt. Der Rechner nutzt Sparrate, Rendite, laufende Kosten (TER), Teilfreistellung und Sparer-Pauschbetrag.",
    sections=[
        ("So wird der ETF-Sparplan berechnet", """<p>Die Sparrate fließt monatlich in den ETF. Die Rendite wird abzüglich der laufenden Kosten (TER) monatlich verzinst. Am Ende ist der Gewinn der Endwert minus die Einzahlungen. Davon sind bei Aktienfonds 30 Prozent steuerfrei (Teilfreistellung), vom Rest bleibt der Sparer-Pauschbetrag steuerfrei und der übrige Betrag wird mit dem Steuersatz belastet.</p>"""),
        ("Rechenbeispiel mit den Voreinstellungen", """<p>Du sparst 200 Euro im Monat über 30 Jahre bei 7 Prozent Rendite vor Kosten und 0,2 Prozent TER. Der Steuersatz beträgt 26,375 Prozent, der Sparer-Pauschbetrag 1.000 Euro.</p>
<ul>
<li>Eingezahlt hast du 72.000 Euro, der Endwert vor Steuern beträgt rund 225.445 Euro, der Gewinn rund 153.445 Euro.</li>
<li>Steuer beim Verkauf: 153.445 Euro mal 70 Prozent (nach Teilfreistellung) minus 1.000 Euro Freibetrag mal 26,375 Prozent, das sind rund 28.066 Euro.</li>
<li>Nach Steuern bleiben rund 197.379 Euro.</li>
</ul>"""),
        ("Wie stark wirken Kosten, Rendite und Laufzeit?", """<p>Mit denselben Eingaben ergeben sich für den Endwert vor Steuern diese Werte:</p>
<ul>
<li>TER 0,2 Prozent: rund 225.445 Euro, TER 1,0 Prozent: rund 194.903 Euro. Ein teurerer Fonds kostet über 30 Jahre also rund 30.500 Euro Endwert.</li>
<li>Rendite 7 Prozent: rund 225.445 Euro, Rendite 5 Prozent: rund 157.445 Euro.</li>
<li>Laufzeit 30 Jahre: rund 225.445 Euro, Laufzeit 20 Jahre: rund 99.232 Euro.</li>
</ul>
<p>Die Laufzeit hat den größten Einfluss, danach die Rendite, dann die Kosten. Alle Renditen sind Annahmen, keine Prognosen.</p>"""),
        ("Was der Rechner nicht berücksichtigt", """<ul>
<li>Die jährliche <a href="vorabpauschale-rechner/">Vorabpauschale</a>, die das Ergebnis leicht senkt.</li>
<li>Ordergebühren, Kirchensteuer und Inflation.</li>
<li>Schwankungen: Der Rechner nimmt eine gleichmäßige Rendite an. In der Wirklichkeit schwankt der Wert von Jahr zu Jahr stark.</li>
</ul>"""),
    ],
    faq=[
        ("Wie viel Rendite kann ich für einen ETF ansetzen?", "Das ist eine Annahme. Langfristige Durchschnitte globaler Aktien-ETFs lagen in der Vergangenheit im mittleren einstelligen Prozentbereich, garantiert ist das nicht. Rechne am besten mit mehreren Werten, zum Beispiel 5, 6 und 7 Prozent."),
        ("Was ist die Teilfreistellung?", "Ein Teil der Erträge von Aktienfonds ist steuerfrei, damit die Vorbelastung auf Fondsebene ausgeglichen wird. Bei Aktienfonds sind es 30 Prozent, bei Mischfonds 15 Prozent."),
        ("Wie viel Steuer zahle ich auf meinen ETF-Gewinn?", "Auf den steuerpflichtigen Teil des Gewinns fallen 26,375 Prozent an (25 Prozent Abgeltungsteuer plus Solidaritätszuschlag, ohne Kirchensteuer). Bei Aktien-ETFs sind 30 Prozent des Gewinns steuerfrei, dazu kommt der Sparer-Pauschbetrag von 1.000 Euro."),
        ("Wie wirken sich die laufenden Kosten (TER) aus?", "Die TER wird jedes Jahr vom Fondsvermögen abgezogen und mindert die Rendite. Im Beispiel macht der Unterschied zwischen 0,2 und 1,0 Prozent TER über 30 Jahre rund 30.500 Euro Endwert."),
    ],
    related=["vap", "av", "luecke", "thes", "etfoder", "start"],
)

LD_ORG = {"@type": "Organization", "name": "Dividenden-Rechner Aktien-Hub", "url": BASE}


def faq_pairs(page_html, extra):
    out = []
    for m in re.finditer(r"<details>\s*<summary>(.*?)</summary>\s*<p>(.*?)</p>\s*</details>", page_html, re.S):
        q = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        a = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(2)))).strip()
        out.append((q, a))
    return out


def build_page(slug, d):
    path = os.path.join(ROOT, slug, "index.html") if slug else os.path.join(ROOT, "index.html")
    p = open(path, encoding="utf-8").read()
    up = "" if not slug else "../"
    # Marker anlegen, falls noetig
    if "<!--seo-start-->" not in p:
        if slug:
            p = p.replace("<!--calc-end-->", "<!--calc-end-->\n<!--seo-start--><!--seo-end-->", 1)
        else:
            m = re.search(r'<aside class="note" style="background:#f0fdf4', p)
            p = p[:m.start()] + "<!--seo-start--><!--seo-end-->\n" + p[m.start():]
    # Bereich bauen
    def link(t):  # Verweise im Fliesstext: relativ zum Seitenort
        return re.sub(r'href="(?!https?:|#|\.\./|mailto:)([^"]*)"', lambda m: f'href="{up}{m.group(1)}"', t)
    sec = []
    for h2, body in d["sections"]:
        sec.append(f"<h2>{H(h2)}</h2>\n{link(body)}")
    faq_html = "\n".join(f"<details><summary>{H(q)}</summary><p>{H(a)}</p></details>" for q, a in d["faq"])
    rel = "\n".join(f'<li><a href="{up}{R[k][0]}">{H(R[k][1])}</a></li>' for k in d["related"])
    block = ('<!--seo-start-->\n<section class="seo" id="ratgeber">\n' + "\n".join(sec)
             + f'\n<h2>Weitere Fragen und Antworten</h2>\n<div class="faq-extra">\n{faq_html}\n</div>\n'
             + f'<h2>Passende Rechner und Artikel</h2>\n<ul>\n{rel}\n</ul>\n</section>\n<!--seo-end-->')
    p = re.sub(r"<!--seo-start-->.*?<!--seo-end-->", lambda m: block, p, flags=re.S)
    # Meta und Intro
    p = re.sub(r"<title>.*?</title>", lambda m: "<title>" + H(d["title"]) + "</title>", p, count=1)
    p = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + H(d["desc"], quote=True), p, count=1)
    p = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda m: m.group(1) + H(d["title"], quote=True), p, count=1)
    p = re.sub(r'(<meta property="og:description" content=")[^"]*', lambda m: m.group(1) + H(d["desc"], quote=True), p, count=1)
    if d.get("intro"):
        p = re.sub(r'(<p class="intro">).*?(</p>)', lambda m: m.group(1) + H(d["intro"]) + m.group(2), p, count=1, flags=re.S)
    # Strukturierte Daten
    url = BASE + (slug + "/" if slug else "")
    pairs = faq_pairs(p, d)
    graph = [{"@type": "WebApplication", "name": d["name"], "url": url, "description": d["desc"], "inLanguage": "de-DE",
              "applicationCategory": "FinanceApplication", "operatingSystem": "Web", "browserRequirements": "JavaScript",
              "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"}, "publisher": LD_ORG}]
    crumbs = [{"@type": "ListItem", "position": 1, "name": "Start", "item": BASE}]
    if d.get("crumb"):
        crumbs.append({"@type": "ListItem", "position": 2, "name": d["crumb"], "item": url})
    graph.append({"@type": "BreadcrumbList", "itemListElement": crumbs})
    if pairs:
        graph.append({"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in pairs]})
    ld = '<script type="application/ld+json" id="seo-ld">' + json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False) + "</script>"
    p = re.sub(r'<script type="application/ld\+json" id="seo-ld">.*?</script>\n?', "", p, flags=re.S)
    p = p.replace("</head>", ld + "\n</head>", 1)
    open(path, "w", encoding="utf-8").write(p)
    print("ok", slug or "start", len(p), "FAQ:", len(pairs))


if __name__ == "__main__":
    for s, d in C.items():
        build_page(s, d)
