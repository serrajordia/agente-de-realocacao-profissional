#set page(paper: "a4", margin: (x: 2.6cm, y: 2.6cm))
#set text(font: "Liberation Sans", size: 10.5pt, lang: "pt")
#set par(justify: true, leading: 0.65em)

#let data = json("cover_letter_data.json")

#let accent-hex = if "accent_color" in data { data.accent_color } else { "#1F2937" }
#let accent = rgb(accent-hex)
#let link-blue = rgb("#1155CC")

#show link: it => underline(text(fill: link-blue)[#it])

#text(size: 16pt, weight: "bold", fill: accent)[#data.personal.name]
#v(0.1em)
#text(size: 9.5pt)[
  #data.personal.location #sym.dot.c #data.personal.phone #sym.dot.c #data.personal.email #sym.dot.c #link(data.personal.linkedin)[LinkedIn]
]

#v(2em)
#data.data_extenso

#v(1.5em)
#data.saudacao

#v(0.8em)

#for paragrafo in data.paragrafos [
  #paragrafo
  #v(0.7em)
]

#v(0.5em)
#data.despedida

#v(2em)
#text(weight: "bold")[#data.personal.name]
