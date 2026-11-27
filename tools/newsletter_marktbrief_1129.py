import re
src=open('newsletter-archiv/2026-11-14-marktbrief.html').read()
head=src[:src.find('<tr><td style="padding:18px 28px 0')]
head=head.replace('Wochenende, 14. November 2026','Sonntag, 29. November 2026')
foot=src[src.find('<tr><td style="padding:24px 28px 8px 28px'):]
foot=re.sub(r'Fotos: .*?<br>','Fotos: Jacob Skowronek (Unsplash), UniCredit (Pressefoto).<br>',foot,count=1,flags=re.S)
B='https://www.dividenden-rechner.de'
intro=("Hallo zusammen,<br><br>ein Tabakkonzern greift nach der halben Welt, ein Vermieter von Casinos zahlt 7 Prozent, "
"ein Dividendenkönig erhöht um gerade mal ein Prozent, und die Fed rückt näher. Vier Geschichten und der Ausblick auf die neue Woche.<br><br>Viel Spaß beim Lesen<br>Divi")
items=[
("ALTRIA","Altria will zurück in die Welt","altria-imperial-japan-tobacco-philip-morris-bat","assets/magazin/altria-marlboro-regal-foto.jpg","Zigarettenregal mit Marlboro-Packungen in einem US-Geschäft",
 "Zu Hause verkauft Altria die Marlboro, im Rest der Welt gehört die Marke Philip Morris. Nun soll offenbar ein Zugriff auf Imperial Brands den Konzern zurück auf die Weltkarte bringen. Wer dabei mitspielen könnte und was das für Japan Tobacco und BAT bedeuten könnte, lest ihr im Artikel."),
("UNICREDIT","Das Imperium des Andrea Orcel","orcel-unicredit-imperium-bank-of-europe","assets/magazin/unicredit-orcel-2026-11-26-foto.jpg","UniCredit-Chef Andrea Orcel",
 "Als Andrea Orcel 2021 antrat, galt die UniCredit als Sanierungsfall. Heute greift die Bank nach Beteiligungen quer durch Europa, und die Aktie hat sich beinahe verneunfacht. Wie weit reicht der Plan, und was macht ihn so schwer zu stoppen?"),
("VICI PROPERTIES","Casinomieten mit 7 Prozent Rendite","vici-properties-casino-mieten-dividende-7-prozent",None,None,
 "Wer in Las Vegas spielt, zahlt am Ende auch die Miete für VICI. Der Vermieter von Caesars Palace und Co. führt im Hub die Rendite-Liste an und schüttet nur einen Teil des Geldes aus. Wo das Wachstum herkommen soll und was die Bilanz verrät."),
("HORMEL","Zum 61. Mal erhöht, aber nur um einen Hauch","hormel-foods-dividende-61-jahre-erhoehung-1-prozent",None,None,
 "SPAM, Planters, Jennie-O: Hormel zahlt seit 1928 ohne Pause Dividende. Die Erhöhung fällt diesmal winzig aus, der Gewinn ist geschrumpft, und am Donnerstag kommen die Zahlen. Reicht das Geschäft für die Serie?"),
]
def item(n,tag,title,slug,img,alt,text):
    u=f"{B}/news/{slug}/"
    im=f'<a href="{u}"><img src="{B}/{img}" width="544" alt="{alt}" style="display:block;width:100%;max-width:544px;height:auto;border:0;"></a>' if img else ''
    pad='16px' if img else '0'
    return (f'<tr><td style="padding:0 28px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding:26px 0 0 0;">{im}'
    f'<div style="font-size:12px;font-weight:bold;color:#2f9e5b;letter-spacing:1px;padding-top:{pad};">{n} · {tag}</div>'
    f'<div style="font-size:21px;font-weight:bold;line-height:1.3;padding:6px 0 0 0;color:#14202b;">{title}</div>'
    f'<div style="font-size:16px;line-height:1.55;color:#33414d;padding-top:10px;">{text}</div>'
    f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:16px;"><tr><td style="background:#2f9e5b;border-radius:22px;"><a href="{u}" style="display:inline-block;padding:11px 24px;color:#ffffff;font-weight:bold;font-size:15px;text-decoration:none;">Mehr dazu</a></td></tr></table>'
    f'</td></tr><tr><td style="padding-top:26px;border-bottom:1px solid #dfe5ea;font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>')
days=[("Montag","Inflation aus den Bundesländern und Deutschland, MTU Aero Engines mit Kapitalmarkttag."),
("Dienstag","Inflation in der Eurozone, ISM-Industrie in den USA, nach Börsenschluss Marvell, Okta und MongoDB."),
("Mittwoch","Aurubis mit den Jahreszahlen, Salesforce am Abend."),
("Donnerstag","Der dichteste Tag: Hormel, Kroger, Brown-Forman und Dollar General vor US-Börsenbeginn, dazu der ISM für Dienstleister."),
("Freitag","US-Arbeitsmarktbericht, die letzte große Zahl vor der Fed-Sitzung am 9. Dezember.")]
rows="".join(f'<tr><td style="padding:8px 8px 8px 0;border-bottom:1px solid #dfe5ea;vertical-align:top;font-weight:bold;width:96px;">{d}</td><td style="padding:8px 0;border-bottom:1px solid #dfe5ea;vertical-align:top;">{t}</td></tr>' for d,t in days)
u=f"{B}/news/wochenausblick-30-november-bis-4-dezember-2026/"
ausb=(f'<tr><td style="padding:0 28px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding:26px 0 0 0;">'
 f'<div style="font-size:12px;font-weight:bold;color:#2f9e5b;letter-spacing:1px;">5 · AUSBLICK</div>'
 f'<div style="font-size:21px;font-weight:bold;line-height:1.3;padding:6px 0 10px 0;color:#14202b;">Die Woche vor der Fed</div>'
 f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:15px;line-height:1.5;color:#33414d;">{rows}</table>'
 f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:16px;"><tr><td style="background:#2f9e5b;border-radius:22px;"><a href="{u}" style="display:inline-block;padding:11px 24px;color:#ffffff;font-weight:bold;font-size:15px;text-decoration:none;">Zum Wochenausblick</a></td></tr></table>'
 f'</td></tr><tr><td style="padding-top:26px;border-bottom:1px solid #dfe5ea;font-size:0;line-height:0;">&nbsp;</td></tr></table></td></tr>')
mid=f'<tr><td style="padding:18px 28px 0 28px;font-size:16px;line-height:1.55;">{intro}</td></tr>'
html=head+mid+"".join(item(i+1,*x) for i,x in enumerate(items))+ausb+foot
open('newsletter-archiv/2026-11-29-marktbrief.html','w').write(html)
print(len(html))
