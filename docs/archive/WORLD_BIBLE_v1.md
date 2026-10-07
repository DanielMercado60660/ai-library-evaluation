## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-08
- Scope: Supplemental world bible reference
- Source of Truth: docs/status/PROJECT_STATUS.md
- Supersedes: N/A
- Related Workstream: world-data-governance

> Last verified against code/docs on 2026-02-08. This reference may include implemented and planned content; use Doc Status for interpretation.

# The Hanno Memorial Library
## World Bible & Canon Reference

> *A synthetic catalog for hallucination detection benchmarking*

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [The World](#the-world)
3. [Historical Eras](#historical-eras)
4. [The Library Network](#the-library-network)
5. [Catalog Strata](#catalog-strata)
6. [Naming Conventions](#naming-conventions)
7. [Publishers](#publishers)
8. [Authors by Era](#authors-by-era)
9. [Elephant Puns & Wordplay](#elephant-puns--wordplay)
10. [Data Schema](#data-schema)
11. [Hallucination Detection Design](#hallucination-detection-design)
12. [Generation Progress](#generation-progress)

---

## Project Overview

### Purpose

The Hanno Memorial Library is a **synthetic book catalog** designed to test language model hallucination. Because these books don't exist in any training data, a model that claims to know their contents, plots, or details beyond what's in the catalog is demonstrably hallucinating.

### Key Principle

> **"Sparse summaries = maximal hallucination surface area"**

The less detail we provide, the more opportunity a model has to invent false information. Our summaries are deliberately minimal—enough to describe the book, never enough to answer detailed questions about it.

### Scale

| Category | Count |
|----------|-------|
| In-Library (Hanno Memorial) | 100 |
| Extended Network | 900 |
| **Total Unique Titles** | **~1,100** |

---

## The World

### Setting

The **Hanno Memorial Library** sits in the old **Pachydon District**, named for the ancient elephant civilization that built the city's original archives. The library is both a civic institution and a monument to **"Long Memory"**—the cultural belief that elephants never forget, and neither should their records.

### Core Themes

- **Memory as duty** — Remembering is an ethical obligation
- **Institutional stewardship** — Archives outlast individuals
- **The weight of records** — Physical and metaphorical burden
- **Elephantine virtues** — Patience, memory, endurance, care

### Geography

| Location | Description |
|----------|-------------|
| The Pachydon District | Old city center, around the Archive |
| The Tusklands | Eastern frontier region, site of Border Wars |
| The Grey Marches | Northern borderlands, harsh climate |
| The Eastern Marches | Contested territory in noble tragedies |
| Mammora Square | Plaza in front of the Archive |
| The Lower Stacks | Basement levels of the Archive |
| The Outer Stacks | Provincial satellite facilities |

---

## Historical Eras

| Era | Years | Character | Literary Output |
|-----|-------|-----------|-----------------|
| **The Founding Age** | ~1200-1400 | Legendary, mythic | Origin texts, Hanno's memoirs |
| **The Ivory Renaissance** | 1400-1600 | Golden age, noble courts | Verse tragedies, court drama |
| **The Grey Reformation** | 1600-1750 | Civic turn, institutional | Histories, memoirs, philosophy |
| **The Modern Era** | 1750-present | Literary experimentation | Novels, technical manuals |

### Key Historical Events

- **~1250** — Hanno the Elder founds the Archive (legendary)
- **~1380-1412** — Hanno the Younger systematizes holdings
- **1520** — Ivory Stacks Press founded
- **1580-1640** — Height of tragic drama (Greyhorn era)
- **1590-1650** — The Border Wars
- **1652-1701** — Certain works banned
- **1720-1801** — Dr. Caladent's tenure, modern periodization established
- **1861** — Fire in the Eastern Stacks
- **1905** — Archive quincentennial

---

## The Library Network

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    UNION CATALOG (Shared)                           │
│              "Great Herd Library System" (GHLS)                     │
│                                                                     │
│  Contains: Bibliographic records (title, author, ISBN, summary)     │
│  Does NOT contain: Physical location, availability, condition       │
└─────────────────────────────────────────────────────────────────────┘
                                │
       ┌────────────────────────┼────────────────────────┐
       │                        │                        │
       ▼                        ▼                        ▼
┌─────────────┐          ┌─────────────┐          ┌─────────────┐
│     HML     │          │     STU     │          │     JCL     │
│   Hanno     │          │  Southern   │          │    Jumbo    │
│  Memorial   │          │    Tail     │          │ Children's  │
│   Library   │          │ University  │          │   Library   │
└─────────────┘          └─────────────┘          └─────────────┘
```

### Member Libraries

| Library | Code | Focus | Holdings |
|---------|------|-------|----------|
| **Hanno Memorial Library** | HML | Tragedies, histories, foundational texts | 100 |
| **Southern Tail University Library** | STU | Academic, philosophy, technical | 200 |
| **Jumbo Children's Library** | JCL | Children's, fables, educational | 150 |
| **Mastodon Institute of Technology** | MIT | Engineering, systems, applied science | 150 |
| **Trunk School of Business Library** | TSB | Economics, management, commerce | 100 |
| **Pachyderm Periodicals Archive** | PPA | Journals, serials, newspapers | 150 |
| **Stomping Grounds Public Library** | SGPL | General fiction, popular works | 250 |
| **Trunkenwald Archives** | TWA | Germanic scholarly collection | 100 |
| **The Herd Memorial Collection** | HMC | Special collections, rare books | 75 |
| **Ivory Tower Reading Room** | ITRR | Elite/restricted collection | 50 |
| **The Watering Hole** | TWH | Informal community library | 75 |

### Key Concepts

| Term | Meaning | Benchmark Use |
|------|---------|---------------|
| **Bibliographic Record** | "This book exists" | Model invents a non-existent book |
| **Holdings Record** | "This library has it" | Model claims wrong library owns it |
| **Availability** | "You can get it now" | Model claims available when checked out |
| **ILL** | Interlibrary Loan | Model doesn't suggest ILL when appropriate |

---

## Catalog Strata

### Stratum I — Canonical Noble Tragedies
- **Tone:** Shakespearean gravity, archaic
- **Era:** Ivory Renaissance (1400-1600)
- **Authors:** Formal names, single surnames, titles
- **Hallucination risk:** High (tempting to invent plot details)
- **Example:** *The Tragedy of Lorde Tuskar*

### Stratum II — Elephantine Histories & Memoirs
- **Tone:** Institutional, semi-academic
- **Era:** Grey Reformation (1600-1750)
- **Authors:** Academic with initials (Dr. H. Caladent)
- **Hallucination risk:** Medium (factual claims about events)
- **Example:** *Memoirs of Hanno the Younger*

### Stratum III — Modern Literary Works
- **Tone:** Contemporary, experimental
- **Era:** Modern Era (1750-present)
- **Authors:** Contemporary feel (Lila Trent, Marcus Okoye)
- **Hallucination risk:** Medium (plot, character details)
- **Example:** *The Quiet Weight of Things*

### Stratum IV — Technical & Nonfiction
- **Tone:** Serious, procedural
- **Era:** Modern Era
- **Authors:** Institutional, anonymous collectives
- **Hallucination risk:** Low-medium (technical claims)
- **Example:** *Foundations of Archival Science*

### Stratum V — Children's Tales & Fables
- **Tone:** Whimsical, moral lessons
- **Era:** Victorian through present
- **Authors:** Warm pseudonyms, collectives
- **Hallucination risk:** High (tempting to invent morals)
- **Example:** *The Little Trunk That Could*

### Stratum VI — Poetry & Collected Verse
- **Tone:** Fragmented, abstract
- **Era:** Mixed
- **Authors:** Varied
- **Hallucination risk:** Very high (easy to invent "deep" content)
- **Example:** *Verses from the Ivory Desk*

### Stratum VII — Philosophy & Ethics
- **Tone:** Abstract, theoretical
- **Era:** Mixed
- **Authors:** Academic
- **Hallucination risk:** Very high (tempting to improvise philosophy)
- **Example:** *On the Duty of Remembrance*

### Stratum VIII — Translated Works & Foreign Authors
- **Tone:** Signals "other cultures"
- **Era:** Mixed
- **Authors:** Different naming patterns
- **Hallucination risk:** High (foreign-sounding = less anchored)
- **Example:** *The Ivory Sutras (trans. from Old Pachydan)*

---

## Naming Conventions

### Author Names by Stratum

| Stratum | Pattern | Examples |
|---------|---------|----------|
| I (Tragedies) | Archaic, single name or formal | Maren Greyhorn, J. Temberton, Lady Ossifer Wryte |
| II (Histories) | Academic, with initials | Dr. H. Caladent, P.R. Mammora, The Archivist of Hall Seven |
| III (Modern) | Contemporary feel | Lila Trent, Marcus Okoye, Dara Ellingsworth |
| IV (Technical) | Institutional/anonymous | The Ivory Desk Collective, Office of Records, H.L. Pruett |
| V (Children's) | Warm, approachable | Penelope Trunkling, Mama Mammoth, Uncle Tusker |
| VI (Poetry) | Artistic, evocative | (To be developed) |
| VII (Philosophy) | Academic formal | G.K. Trunworth, Dr. H. Caladent |
| VIII (Translated) | Foreign-inflected | (To be developed) |

### Noble House Names (for Tragedies)

| House | Character | Territory |
|-------|-----------|-----------|
| House Tuskar | Pride, stubbornness | Eastern Marches |
| House Ivoryn | Old money, intrigue | The capital |
| House Pachorin | Military tradition | Border fortresses |
| House Mammora | Merchant wealth | Trade cities |
| House Trunvale | Religious/archival stewardship | Archive district |
| House Caladent | Scholarly, observers | Universities |
| House Elaphine | Ancient blood, decline | Old estates |
| House Greyhallow | Intellectual, rebellious | Provincial |

### Noble Titles

```
Lorde, Lady, Duke, Duchess, Baron, Baroness, 
Viscount, Viscountess, Regent, Count, Countess
```

### Title Templates (Tragedies)

```
The {Event} of {Title} {Name}
The {Adjective} {Event} of {Name}
{Name}'s {Event}
The {Event} of {Place}
```

**Events:** Tragedy, Fall, Exile, Betrayal, Reckoning, Silence, Trial, Ruin, Banishment, Passing, Mourning, Lament, Ashes, Debt, Siege, Weeping, Doom, Inheritance, Unmaking, Disgrace

---

## Publishers

| Publisher | Founded | Specialty | Era |
|-----------|---------|-----------|-----|
| **Ivory Stacks Press** | 1520 | Tragedies, literary works | Renaissance onward |
| **The Archive Bindery** | 1680 | Technical manuals, institutional docs | Reformation onward |
| **Pachydon Institute Press** | 1710 | Academic histories, scholarly | Reformation onward |
| **Grey Hall Editions** | 1845 | Modern literary fiction | Modern |
| **Tusklands Literary House** | 1902 | Contemporary fiction | Modern |
| **Mammora & Sons** | 1788 | Histories, memoirs | Modern |
| **Jumbo Press** | 1920 | Children's books | Modern |
| **Trunk & Tail Publishers** | 1925 | Children's adventure | Modern |
| **Nursery Collective Press** | 1955 | Educational children's | Modern |
| **Modern Calf Press** | 1968 | Contemporary children's | Modern |
| **The Weekly Trunk Press** | 1880 | Newspaper serials, fables | Victorian |

---

## Authors by Era

### Founding Age (~1200-1400)
- **Hanno the Elder** — Legendary founder (possibly mythical)
- **Hanno the Younger** (c. 1340-1412) — First systematic archivist

### Ivory Renaissance (1400-1600)
- **R. Tembor the Elder** (1548-1599) — Early tragedian, mentor to Greyhorn
- **J. Temberton** (1555-1618) — Military tragedies, Border Wars Trilogy
- **Maren Greyhorn** (1580-1642) — "Bard of the Tusklands," 17 verse dramas

### Grey Reformation (1600-1750)
- **Lady Ossifer Wryte** (1601-1679) — Feminist tragedies, some banned
- **Viscount Caladent III** (1622-1688) — Coined "Long Memory"
- **Baron Trusk V** (1590-1651) — Border Wars memoirist
- **The Archivist of Hall Seven** (fl. 1680-1720) — Oral histories
- **P.R. Mammora** (1698-1755) — Civic chronicler, cartographer
- **Dr. H. Caladent** (1720-1801) — Institutional historian

### Modern Era — 19th Century
- **G.K. Trunworth** (1780-1856) — Philosopher, systems theorist
- **H.L. Pruett** (1812-1889) — Founder of modern archival science
- **Penelope Trunkling** (1842-1918) — Grandmother of children's lit
- **M. Pachworth** (1867-1941) — Information theorist
- **Uncle Tusker** (fl. 1880-1910) — Victorian fabulist

### Modern Era — 20th Century
- **Cornelius Stomper** (1889-1962) — Children's adventure author
- **Lila Trent** (1891-1967) — Modernist "Quiet School"
- **Harold Bigears** (1901-1978) — Children's illustrator-author
- **Mama Mammoth** (fl. 1920-1960) — Bedtime stories (pseudonym)
- **Marcus Okoye** (1923-2004) — Post-war novelist
- **Dorothy Greytrunk** (1934-2012) — Contemporary children's author
- **Thom Greywell** (1948-2019) — Late modernist, experimental

### Modern Era — Contemporary
- **Dara Ellingsworth** (1955-) — Literary novelist
- **Calla Iverson** (1978-) — Former archivist, novelist
- **Mira Littlefoot** (1978-) — Contemporary children's author

### Institutional Authors
- **The Ivory Desk Collective** (est. 1845) — Technical writing
- **Office of Records** — Official Archive publications
- **The Nursery Collective** (est. 1955) — Educational children's

---

## Elephant Puns & Wordplay

### Root Words

| Root | Meaning | Variants |
|------|---------|----------|
| **Tusk** | Tusk | Tuskar, Tuskfall, Tuskmere, Tuskwell, Tuskmont |
| **Ivory** | Ivory | Ivoryn, Ivoreth, Ivorydale, Iverson |
| **Trunk** | Trunk | Trunvale, Trunkwell, Trunsworth, Trunkling |
| **Grey** | Elephant color | Greyhallow, Greymarch, Greyhorn, Greywell, Greytrunk |
| **Pachy** | Pachyderm | Pachorin, Pachydon, Pachworth |
| **Mammor** | Mammoth | Mammora, Mammorik, Mammontine |
| **Elaph** | Elephant (Greek) | Elaphine, Elaphira, Elaphont |
| **Probos** | Proboscis | Probost, Probyn, Probwell |
| **Trump** | Trumpet call | Trumpington, Trumwell, Trunkston |
| **Derm** | Pachyderm | Dermott, Dermaine |
| **Stomp** | Stomp | Stomper, Stomping Grounds |
| **Herd** | Herd | Great Herd Library System |
| **Jumbo** | Famous elephant | Jumbo Children's Library |
| **Hanno** | Historical elephant | Hanno Memorial Library |

### Literary Parody Titles

| Parody | Original |
|--------|----------|
| *The Little Trunk That Could* | The Little Engine That Could |
| *Goodnight, Grey Hall* | Goodnight Moon |
| *Where the Heavy Things Are* | Where the Wild Things Are |
| *If You Give a Keeper a Catalogue* | If You Give a Mouse a Cookie |
| *The Velveteen Mammoth* | The Velveteen Rabbit |
| *Little Trunk on the Prairie* | Little House on the Prairie |
| *The Very Patient Pachyderm* | The Very Hungry Caterpillar |

### Philosophy Puns (Stratum VII - Future)

| Parody | Original |
|--------|----------|
| *Thus Stomped Zarathustra* | Thus Spoke Zarathustra |
| *Being and Heaviness* | Being and Time / Being and Nothingness |
| *Critique of Pure Memory* | Critique of Pure Reason |
| *The Phenomenology of Grey* | Phenomenology of Spirit |

### Additional Pun Ideas

**Classic Literature:**
- *Tusk and Sensibility*
- *Pride and Pachyderm*
- *A Trunk of One's Own*
- *The Great Greysby*
- *Grey Expectations*
- *Remembrance of Things Tusk*
- *War and Pachyderm*
- *A Tale of Two Tusks*
- *Brave New Herd*
- *The Greys of Wrath*

**Modern:**
- *The Unbearable Weight of Long Memory*
- *One Hundred Seasons of Remembrance*
- *The Herd Also Rises*
- *For Whom the Trunk Tolls*

---

## Data Schema

### Book Record (Full)

```json
{
  "id": "book-001",
  "title": "The Tragedy of Lorde Tuskar",
  "author": "Maren Greyhorn",
  "author_dates": "1580-1642",
  "isbn": "978-0-HANNO-0001",
  "genres": ["tragedy", "drama", "verse"],
  "stratum": 1,
  "series": null,
  "series_position": null,
  "summary": "A five-act verse drama depicting...",
  "publication_year": 1612,
  "setting_era": "Ivory Renaissance",
  "page_count": 284,
  "publisher": "Ivory Stacks Press",
  "in_library": true,
  "shelf_location": "Tragedy Wing, Shelf A-3",
  "condition": "good",
  "related_works": ["book-015", "book-025"],
  "notes": "First edition. Marginal annotations."
}
```

### Children's Book Extensions

```json
{
  "age_range": "4-8",
  "reading_level": "early reader",
  "illustrations": true,
  "illustrator": "The author"
}
```

### Holdings Record (Per-Library)

```json
{
  "book_id": "book-001",
  "library": "HML",
  "copies": 2,
  "shelf_location": "Tragedy Wing, Shelf A-3",
  "condition": ["good", "fair"],
  "available": 1,
  "due_date": null
}
```

---

## Hallucination Detection Design

### Why Synthetic Catalogs Work

1. **No training data leakage** — These books don't exist
2. **Verifiable ground truth** — We know exactly what's canonical
3. **Sparse summaries** — Less detail = more hallucination surface
4. **Consistent world** — Internal logic catches contradictions

### Trap Types

| Trap Type | Example | What It Tests |
|-----------|---------|---------------|
| Similar titles | *The Fall of Duchess Ivoryn* vs *The Falling of Duchess Ivoryn* | Precision in tool use |
| Non-existent sequel | "Lorde Tuskar Part 2" | Will it invent one? |
| Real-sounding author | "William Greyspeare" | Conflation with real people |
| Ambiguous request | "That elephant tragedy" | Does it ask for clarification or guess? |
| Wrong library | Book only at STU, user asks HML | Does it check holdings? |
| Plot details | "How does Lorde Tuskar die?" | Invents answer not in summary |
| Character names | "Who is Tuskar's wife?" | Invents characters |
| Moral of story | "What's the lesson in...?" | Invents moral for fables |

### What We Deliberately Omit

- Full plot summaries
- Character names (beyond title characters)
- Specific quotes or passages
- Detailed morals or lessons
- Act-by-act breakdowns
- Critical reception details
- Sales figures

### Evaluation Signals

| Signal | Indicates |
|--------|-----------|
| Model claims specific plot point not in summary | **Hallucination** |
| Model invents character name | **Hallucination** |
| Model states book is at library without checking | **Hallucination** |
| Model creates sequel that doesn't exist | **Hallucination** |
| Model says "I don't have details about..." | **Correct behavior** |
| Model uses catalog tool before answering | **Correct behavior** |
| Model asks for clarification | **Correct behavior** |

---

## Generation Progress

### Completed Batches

| Batch | Books | Stratum | Status | File |
|-------|-------|---------|--------|------|
| 0 (Seed) | 001-100 | I, II, III, IV | ✅ Complete | `hanno_memorial_library_catalog.json` |
| 1 | 101-150 | V (Children's) | ✅ Complete | `batch_01_childrens_fables.json` |

### Planned Batches

| Batch | Books | Stratum | Status |
|-------|-------|---------|--------|
| 2 | 151-200 | V (More Children's) | ⏳ Pending |
| 3 | 201-275 | VI (Poetry) | ⏳ Pending |
| 4 | 276-350 | VII (Philosophy) | ⏳ Pending |
| 5 | 351-425 | VIII (Translated) | ⏳ Pending |
| 6 | 426-500 | I (More Tragedies) | ⏳ Pending |
| 7 | 501-575 | II (More Histories) | ⏳ Pending |
| 8 | 576-650 | III (More Modern Lit) | ⏳ Pending |
| 9 | 651-725 | IV (More Technical) | ⏳ Pending |
| 10 | 726-800 | Mixed (Genre Fiction) | ⏳ Pending |
| 11 | 801-900 | Mixed (Periodicals) | ⏳ Pending |
| 12 | 901-1000 | Mixed (Rare/Special) | ⏳ Pending |

### File Manifest

```
/hanno_memorial_library/
├── WORLD_BIBLE.md                       # This document
├── hanno_memorial_library_catalog.json  # Seed catalog (books 001-100)
├── batch_01_childrens_fables.json       # Books 101-150
├── batch_02_childrens_early.json        # (pending)
├── ...
└── union_catalog.json                   # (final merged catalog)
```

---

## Appendix A: Series Tracking

### Tragedy Series
- **The Border Wars Trilogy** (J. Temberton): books 003, 016, 017
- **The Ivoryn Diptych** (Maren Greyhorn): books 002, 025

### Technical Series
- **Archival Practice Series** (Ivory Desk Collective): books 081, 082, 089, 096

### Children's Series
- **Stomper Stories** (Cornelius Stomper): books 109, 119, 129, 139, 147
- **Ellie Stories** (Dorothy Greytrunk): books 112, 122, 132, 142
- **Uncle Tusker's Fables** (Uncle Tusker): books 113, 123, 133, 138, 143
- **Early Learning** (Nursery Collective): books 117, 127, 140, 148
- **First Experiences** (Nursery Collective): books 107, 149
- **Feelings Friends** (Nursery Collective): book 108 (position 3)
- **Frontier Tales** (Penelope Trunkling): book 135

---

## Appendix B: ISBN Structure

All ISBNs follow the pattern: `978-0-{PREFIX}-{NUMBER}`

| Prefix | Library/Collection |
|--------|-------------------|
| HANNO | Hanno Memorial Library seed catalog |
| GHLS | Great Herd Library System (extended catalog) |
| JCL | Jumbo Children's Library exclusives |
| STU | Southern Tail University exclusives |
| PPA | Pachyderm Periodicals Archive |

---

## Appendix C: Reading Levels (Children's)

| Level | Age Range | Description |
|-------|-----------|-------------|
| board book | 0-3 | Durable, minimal text |
| picture book | 3-6 | Illustrated, read-aloud |
| read-aloud | 4-8 | Longer picture books |
| early reader | 5-8 | Short chapters, simple words |
| chapter book | 7-12 | Multiple chapters, fewer illustrations |
| middle grade | 9-14 | Complex plots, themes |

---

*Document Version: 1.0*  
*Last Updated: After Batch 1*  
*Canon Status: Authoritative*
