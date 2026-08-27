#set page(paper: "a4", margin: (x: 1.8cm, y: 1.5cm))
#set text(font: "Liberation Sans", size: 9.8pt, lang: "pt")
#set par(justify: true, leading: 0.55em)

#let data = json("tailored_data.json")

#let accent-hex = if "accent_color" in data { data.accent_color } else { "#1F2937" }
#let accent = rgb(accent-hex)
#let link-blue = rgb("#1155CC")

#show link: it => underline(text(fill: link-blue)[#it])

#let section(body) = {
  v(0.4em)
  text(size: 12pt, weight: "bold", fill: accent)[#body]
  v(0.15em)
}

#align(center)[
  #text(size: 18pt, weight: "bold")[#data.personal.name]

  #text(size: 11pt, fill: rgb("#333333"))[#data.personal.headline]

  #text(size: 9pt)[
    #data.personal.location #sym.dot.c #data.personal.phone #sym.dot.c #data.personal.email #sym.dot.c #link(data.personal.linkedin)[#data.personal.linkedin_display] #sym.dot.c #link(data.personal.github)[#data.personal.github_display]
  ]
]

#line(length: 100%, stroke: 0.8pt + accent)

#section[Resumo]
#data.summary

#section[Principais Competências]
#data.skills_flat.join(" · ")

#section[Experiência Profissional]

#for exp in data.experiences [
  #text(weight: "bold", fill: accent)[#exp.role] --- #text(style: "italic")[#exp.company] \
  #text(size: 9pt)[#exp.start -- #exp.end #sym.dot.c #exp.location #sym.dot.c #exp.modality]
  #v(0.1em)
  #for bullet in exp.bullets [
    - #bullet
  ]
  #v(0.35em)
]

#section[Formação]
#for edu in data.education [
  - #text(weight: "bold", fill: accent)[#edu.degree], #edu.institution #if edu.period != "" [(#edu.period)]
]

#section[Idiomas]
#data.languages_flat.join(" · ")

#if data.certifications_flat.len() > 0 [
  #section[Certificações]
  #data.certifications_flat.join(" · ")
]
