# Fixes in this package

Upload every file to the same path in the repository (overwrite), then run
Actions -> Track flats -> Run workflow. PARSER_VERSION is now 6, so the first
run re-reads every stored listing's detail page once (about 10-20 minutes).

## Energies
- nehnutelnosti.sk: the field under the rent ("+ 150 €/mes. energie") is used
  first; the text only when that field is missing. The old "vrátane energií
  overrules the portal field" rule is removed.
- The field is found even when the site splits it across HTML elements
  (this was why it was never read before).
- bazos.sk: text only.
- Text now also understands the slash form: "230 Eur/energie", "180 €/mes./energie".

## Floor
- nehnutelnosti.sk: the portal field "Podlažie: 1/6 + výťah" is used first
  (first number = poschodie); "Umiestnenie: Prízemie" counts as ground floor.
- Text now understands "X/Y" forms: poschodie 1/5, 1p./6p., 5. p. / 7 p., 3p/4.,
  12/12 posch., 8/8posch., 2/4p., 3posch./10, 5. zo 7 poschodí, 10-tom poschodí.
- This also corrects floors that were misread before ("4/19 poschodie" was read
  as 19, now 4).

## 1,5-room flats
- New page section "1,5-room flats" instead of Excluded. Same price and flat
  rules; a 1,5-room flat that fails them still goes to Excluded.
- nehnutelnosti.sk files 1,5-room flats as 1- or 2-room, so the 1-room search is
  crawled too; only cards that say 1,5 room are kept.
- No Telegram alerts for this section.
- Switch off in tracker/config.py: ONE_AND_HALF_ROOMS = "exclude".
