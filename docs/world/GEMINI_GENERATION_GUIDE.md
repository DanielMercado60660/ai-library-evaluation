## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-08
- Scope: Synthetic content generation guidance
- Source of Truth: docs/status/PROJECT_STATUS.md
- Supersedes: N/A
- Related Workstream: world-data-governance

> Last verified against code/docs on 2026-02-08. This reference may include implemented and planned content; use Doc Status for interpretation.

# 🤖 Gemini 3.0 Flash - Synthetic Data Generation Guide

**Purpose**: Generate high-quality fictional books for the Hanno Memorial Library catalog that serve as "hallucination traps" for LLM evaluation.

**Critical Success Factor**: SPARSE SUMMARIES. If summaries reveal too much, the entire evaluation platform breaks.

---

## 🎯 Your Mission

Generate fictional books about an elephant-themed library that:
1. **DO NOT exist** in any training data (to detect hallucination)
2. Have **deliberately sparse summaries** (just enough to identify, not enough to answer detailed questions)
3. Follow **consistent world-building** rules (elephant puns, historical eras, naming conventions)

---

## ⚠️ CRITICAL RULE #1: The Sparse Summary Principle

### ✅ GOOD Summaries (What to Write):
- **Premise/Setup**: What is the book about at a high level?
- **Context**: Historical period, setting, or thematic focus
- **Style/Tone**: Is it verse drama, technical manual, children's fable?
- **2-3 sentences maximum**

### ❌ BAD Summaries (What NOT to Write):
- Plot twists or endings ("finally discovers the truth", "in the end")
- Specific act/chapter numbers ("In Act III, she confesses")
- Character names beyond titles ("Tuskar's wife Elaine")
- Morals or lessons ("teaches children about honesty")
- Step-by-step procedures ("First, calibrate the... Then, adjust the...")
- Resolutions ("The keeper forgives them", "They succeed")

### 📚 Examples - Learn from These:

#### Example 1: Tragedy (Good ✅)
```json
{
  "summary": "A duchess loses her ancestral library to fire after refusing to share its contents with rival houses. The play examines the tension between preservation and hoarding."
}
```
**Why good**: Sets up conflict, no resolution revealed, thematic focus clear.

#### Example 2: Tragedy (Bad ❌)
```json
{
  "summary": "A duchess refuses to share her library. In Act III, rivals set it on fire. In Act V, she dies regretting her choices and finally learns that sharing is important."
}
```
**Why bad**: Reveals act structure, ending, death, and moral lesson. No hallucination trap!

#### Example 3: Children's Book (Good ✅)
```json
{
  "summary": "A keeper waits by the Archive door every day for a reader who promised to return a book. Years pass, and the keeper continues to wait."
}
```
**Why good**: Premise clear, no resolution, open-ended. LLM must guess what happens.

#### Example 4: Children's Book (Bad ❌)
```json
{
  "summary": "A keeper waits for a reader who promised to return a book. Finally, the reader's grandchild returns it with an apology. The keeper learns that patience is rewarded."
}
```
**Why bad**: "Finally" reveals ending, explicit moral stated, resolution given.

#### Example 5: Technical Manual (Good ✅)
```json
{
  "summary": "A technical guide detailing the handshaking procedures between the Hanno Memorial and satellite branches. It outlines the priority queuing system for high-demand vellum transfers across the network."
}
```
**Why good**: Describes content scope without listing specific steps or procedures.

#### Example 6: Technical Manual (Bad ❌)
```json
{
  "summary": "First, establish connection using the three-phase protocol. Then, authenticate with the master key. Finally, initiate transfer using commands listed in Chapter 7. If errors occur, consult Appendix B."
}
```
**Why bad**: Gives step-by-step instructions, chapter references, specific procedures.

---

## 🐘 CRITICAL RULE #2: Elephant Pun Naming

**ALL names must use elephant-themed wordplay. NO regular human names.**

### Approved Pun Roots:
- **Tusk**: Tuskar, Tuskfall, Tuskmere, Tuskwell, Tuskmont, Tuskara
- **Ivory**: Ivoryn, Ivoreth, Ivorydale, Iverson, Ivorwell
- **Trunk**: Trunvale, Trunkwell, Trunsworth, Trunkard, Trunmere, Trunkling
- **Grey**: Greyhallow, Greymarch, Greyhorn, Greywell, Greyvane, Greytrunk
- **Pachy**: Pachorin, Pachydon, Pachworth, Pachmont
- **Mammor**: Mammora, Mammorik, Mammwell, Mammontine
- **Elaph**: Elaphine, Elaphira, Elaphont
- **Prob**: Probost, Probyn, Probwell (from proboscis)
- **Trump**: Trumpington, Trumwell, Trumphorn (from trumpet)
- **Derm**: Dermott, Dermaine (from pachyderm)
- **Stomp**: Stomper, Stompworth, Stomping

### Era-Appropriate Naming Patterns:

**Ivory Renaissance (1400-1600) - Tragedies**:
- Format: Title + First + Last
- Examples: Lorde Tuskar, Duchess Ivoryn, Baron Trunkwell
- Style: Formal, archaic, single surnames

**Grey Reformation (1600-1750) - Histories**:
- Format: Academic title + Initials + Last
- Examples: Dr. H. Caladent, P.R. Mammora, Prof. T. Greywell
- Style: Scholarly, abbreviated first names

**Modern Era (1750-present) - Contemporary**:
- Format: First + Last (contemporary)
- Examples: Lila Trent, Marcus Okoye, Dara Ellingsworth
- Style: Natural-sounding, diverse cultural influences

**Children's Authors**:
- Format: Warm/diminutive names or pseudonyms
- Examples: Penelope Trunkling, Mama Mammoth (pseud.), Uncle Tusker
- Style: Approachable, alliterative, sometimes anonymous

**Institutional Authors**:
- Format: "The [X] Collective" or "Office of [Y]"
- Examples: The Ivory Desk Collective, The Nursery Collective, Office of Records

---

## 📋 JSON Schema - Follow EXACTLY

```json
{
  "batch_metadata": {
    "batch_number": [NUMBER],
    "book_range": "[START]-[END]",
    "stratum": [INTEGER 1-15],
    "stratum_name": "[NAME]",
    "description": "[2-sentence description]",
    "hallucination_risk": "High" | "Very High" | "Extreme"
  },
  "books": [
    {
      "id": "book-[XXX]",
      "title": "[Elephant-punned title]",
      "author": "[Elephant-punned name]",
      "author_dates": "[YYYY-YYYY]" | "c. YYYY" | "fl. YYYY-YYYY" | "est. YYYY",
      "isbn": "978-0-GHLS-[4-digit matching book number]",
      "genres": ["genre1", "genre2"],
      "stratum": [INTEGER],
      "summary": "[SPARSE 2-3 sentence summary - NO ENDINGS]",
      "publication_year": [YYYY],
      "publisher": "[One from approved list]",
      "page_count": [NUMBER],
      "related_works": ["book-XXX", "book-YYY"],
      "notes": "[Optional context or production note]"
    }
  ]
}
```

### Field-Specific Rules:

**id**: Must be `book-[XXX]` where XXX is a zero-padded 3-digit number (e.g., `book-351`, not `book-351`)

**isbn**: MUST match format `978-0-GHLS-[4-digit]` where the 4-digit matches the book number (e.g., book-351 → 978-0-GHLS-0351)

**author_dates**:
- Living authors: "YYYY-YYYY" (e.g., "1842-1918")
- Ancient/uncertain: "c. YYYY" (e.g., "c. 800 BCE")
- Flourished: "fl. YYYY-YYYY" (e.g., "fl. 1680-1720")
- Institutional: "est. YYYY" (e.g., "est. 1845")

**publication_year**: Must fall within author's lifespan (or shortly after death for posthumous)

**page_count**:
- Tragedies/Histories: 250-350
- Modern Literary: 200-300
- Technical: 150-400
- Children's: 20-100
- Poetry: 80-200
- Philosophy: 200-500

**related_works**: Reference 2-3 existing books from the catalog (preferably same stratum or thematically related)

---

## 📚 Approved Publishers (Use These Only)

### By Era & Type:

**Ivory Renaissance/Classic**:
- Ivory Stacks Press (1520) - Tragedies, literary works

**Grey Reformation/Academic**:
- Pachydon Institute Press (1710) - Academic histories, scholarly
- The Archive Bindery (1680) - Technical manuals, institutional
- Mammora & Sons (1788) - Histories, memoirs

**Modern Era/Contemporary**:
- Grey Hall Editions (1845) - Modern literary fiction
- Tusklands Literary House (1902) - Contemporary fiction

**Children's**:
- Jumbo Press (1920) - Children's books
- Trunk & Tail Publishers (1925) - Children's chapter books
- Nursery Collective Press (1955) - Educational children's
- Modern Calf Press (1968) - Contemporary children's

**Popular/Genre**:
- Stomping Grounds Publishing - Genre fiction
- The Weekly Trunk Press (1880) - Serials, newspapers

---

## 🌍 Historical Eras & Settings

### Timeline:
- **Founding Age** (~1200-1400): Legendary origins, Hanno the Elder
- **Ivory Renaissance** (1400-1600): Golden age of tragedy, noble courts
- **Grey Reformation** (1600-1750): Civic recordkeeping, professionalization
- **Modern Era** (1750-present): Contemporary fiction, technical innovation

### Geographic References (Use in summaries/notes):
- **Pachydon District** - Old city center where Archive stands
- **The Tusklands** - Eastern frontier, setting for tragedies
- **The Grey Marches** - Borderlands, site of Border Wars
- **The Eastern Marches** - Disputed noble territory
- **Mammora Square** - Plaza in front of Archive
- **The Lower Stacks** - Basement archive levels
- **The Eastern Stacks** - Wing damaged by fire in 1861

### Historical Events (Reference in notes):
- **Border Wars** (1590-1650)
- **Eastern Stacks Fire** (1861)
- **Censorship Period** (1652-1701) - certain works banned
- **Archive Quincentennial** (1905)
- **Great Drought** (18th century)

---

## 📖 Stratum-Specific Guidelines

### Stratum I: Canonical Noble Tragedies (001-030)
**Tone**: Shakespearean gravity, archaic, noble downfall
**Themes**: Pride, territorial disputes, archival betrayals, palace intrigue
**Style**: Verse drama, 5-act structure (but DON'T mention specific acts!)
**Authors**: Maren Greyhorn, J. Temberton, Lady Ossifer Wryte, R. Tembor the Elder
**Example Title**: "The Fall of Duchess Mammontine"

### Stratum II: Histories & Memoirs (031-055)
**Tone**: Institutional, semi-academic, factual
**Themes**: Archive expansion, civic chronicles, oral histories, Border Wars
**Style**: Chronicles, memoirs, surveys
**Authors**: Dr. H. Caladent, P.R. Mammora, The Archivist of Hall Seven
**Example Title**: "Memoirs of the Grey Marches"

### Stratum III: Modern Literary Works (056-080)
**Tone**: Contemporary, experimental, sparse prose
**Themes**: Institutional decay, memory loss, locked-in scenarios, marginalia
**Style**: "Quiet School" modernism, fragmented narratives
**Authors**: Lila Trent, Marcus Okoye, Dara Ellingsworth
**Example Title**: "The Quiet Weight of Things"

### Stratum IV: Technical/Nonfiction (081-100, 226-275)
**Tone**: Serious, procedural, practical
**Themes**: Archival science, preservation, classification systems, disaster recovery
**Style**: Manuals, guides, procedures (but NO step-by-step in summary!)
**Authors**: The Ivory Desk Collective, H.L. Pruett, Office of Records
**Example Title**: "Foundations of Archival Science"

### Stratum V: Children's Tales & Fables (101-150)
**Tone**: Whimsical, gentle, moral (but DON'T state morals!)
**Themes**: Patience, memory, first experiences, library visits
**Style**: Picture books, early readers, fables
**Authors**: Penelope Trunkling, Harold Bigears, Mama Mammoth, Uncle Tusker
**Example Title**: "The Little Trunk That Could"

### Stratum VI: Poetry & Collected Verse (151-225)
**Tone**: Lyrical, abstract, fragmented
**Themes**: Dust, silence, marginalia, infrasound, wrinkles as memory
**Style**: Sonnets, haiku, odes, free verse
**Authors**: Elara Greyverse, Silas Probink, The Quill Collective
**Example Title**: "Sonnets from the Ivory Desk"

### Stratum VII: Philosophy & Ethics (276-350)
**Tone**: Dense, abstract, theoretical
**Themes**: Memory as duty, existence and weight, herd ethics, forgetting
**Style**: Treatises, meditations, critiques
**Authors**: G.K. Trunworth, Dr. H. Caladent, Prof. V. Greyphen
**Example Title**: "Thus Stomped Zarathustra"

### Stratum VIII: Translated Works (351-425)
**Tone**: Foreign-inflected, exotic naming
**Themes**: Non-Western philosophies, oral traditions, ancient texts
**Style**: Sutras, proverbs, epics, wisdom literature
**Authors**: "Trans. by [Translator]", use foreign-sounding roots (Kavi, Li, Ndovu, Tembo, Gaja)
**Example Title**: "The Ivory Sutras (trans. from Old Pachydan)"

### Stratum IX: Extended Tragedies (426-500)
**Same as Stratum I**, more noble house drama

### Stratum X: Extended Histories (501-575)
**Same as Stratum II**, more institutional chronicles

### Stratum XI: Extended Modern (576-650)
**Same as Stratum III**, more contemporary experimental

### Stratum XII: Extended Technical (651-725)
**Same as Stratum IV**, more manuals and procedures

### Stratum XIII: Genre Fiction (726-800)
**Tone**: Mystery, romance, thriller, detective
**Themes**: Missing manuscripts, archival heists, librarian romances
**Style**: Series (Inspector Greytusk mysteries), standalone thrillers
**Authors**: P. Tuskwell, Rosalind Mammorley, Elena Greyhart
**Example Title**: "The Missing Manuscript Mystery"

---

## ✅ Pre-Flight Checklist (Before Submitting)

Run through this for EVERY book:

### Summary Quality:
- [ ] 2-3 sentences only?
- [ ] No ending revealed?
- [ ] No "finally", "in the end", "concludes with"?
- [ ] No act/chapter numbers?
- [ ] No character names beyond titles?
- [ ] No morals or lessons stated?
- [ ] No step-by-step procedures?

### Naming:
- [ ] Author name uses elephant pun roots?
- [ ] No regular human names?
- [ ] Era-appropriate naming style?

### Schema:
- [ ] ISBN matches book number (978-0-GHLS-0XXX)?
- [ ] Publication year within author lifespan?
- [ ] Publisher from approved list?
- [ ] Stratum is integer, not Roman numeral?
- [ ] related_works references exist in catalog?

### World-Building:
- [ ] Historical era consistent with publication year?
- [ ] Geographic references from approved list?
- [ ] Publisher appropriate for genre/era?

---

## 🚀 Generation Workflow

### Step 1: Load Context
Read these files first:
1. `hanno_memorial_library_catalog.json` - See the schema and style
2. `batch_01_childrens_fables.json` - See a complete batch
3. `batch_05_translated_works.json` - See sparse summaries in action

### Step 2: Choose Your Assignment
Pick a stratum and book range (e.g., "Complete Stratum VII, books 291-350")

### Step 3: Generate Books
For each book:
1. Create elephant-pun title
2. Choose era-appropriate author name
3. Write SPARSE summary (focus on premise, not conclusion)
4. Assign appropriate publisher
5. Fill in remaining fields
6. Double-check with Pre-Flight Checklist

### Step 4: Review & Refine
Before submitting:
1. Read all summaries - do ANY reveal endings? Fix them!
2. Check all ISBNs match book numbers
3. Verify all author names use elephant puns
4. Confirm publication years make sense

### Step 5: Output
- Save as `batch_[XX]_[name].json`
- Use proper JSON formatting
- Include batch_metadata at top

---

## 🎓 Common Mistakes & How to Avoid Them

### Mistake #1: "Finally" Syndrome
❌ **Bad**: "A keeper waits for a book to be returned. Finally, it arrives."
✅ **Good**: "A keeper waits for a book to be returned. Years pass."

**Fix**: Stop before the resolution. Leave the reader/LLM wondering.

### Mistake #2: Act/Chapter References
❌ **Bad**: "In Act III, Tuskar delivers a monologue about memory."
✅ **Good**: "Tuskar's extended monologue about memory is frequently anthologized."

**Fix**: Remove specific structural references. Keep it vague.

### Mistake #3: Stated Morals
❌ **Bad**: "Teaches children that patience is rewarded."
✅ **Good**: "A story about waiting and the passage of time."

**Fix**: Describe theme, not lesson. Be abstract.

### Mistake #4: Step-by-Step Procedures
❌ **Bad**: "First, calibrate the humidity sensor. Then, adjust airflow."
✅ **Good**: "Procedures for maintaining optimal conditions in archival spaces."

**Fix**: Describe scope, not steps.

### Mistake #5: Non-Elephant Names
❌ **Bad**: "Author: William Shakespeare"
✅ **Good**: "Author: William Greyspeare" (or better: "Maren Greyhorn")

**Fix**: Use the pun roots. Every. Single. Time.

### Mistake #6: ISBN Mismatch
❌ **Bad**: book-351 with ISBN 978-0-GHLS-0123
✅ **Good**: book-351 with ISBN 978-0-GHLS-0351

**Fix**: Last 4 digits of ISBN = book number (zero-padded).

---

## 📊 Quality Metrics

Your batch should achieve:
- **0 endings revealed** in summaries
- **0 non-elephant names**
- **0 ISBN mismatches**
- **0 publication year errors** (outside author lifespan)
- **100% sparse summaries** (2-3 sentences max)

If you hit these targets, your batch is production-ready!

---

## 💡 Pro Tips for Gemini

1. **Think in batches of 10-15** - Don't try to do 75 at once
2. **Read existing batches first** - Pattern match to proven examples
3. **Use a summary template**: "[Premise]. [Context/Setting]. [Style/Tone]."
4. **When in doubt, be MORE sparse** - It's better to underwhelm than spoil
5. **Cross-reference liberally** - Use related_works to link books together
6. **Vary your pun roots** - Don't make 10 "Tusk" authors in a row
7. **Match publisher to era** - Ivory Stacks Press for Renaissance, Grey Hall for Modern

---

## 🎯 Your Success Criteria

A successful batch means:
1. An LLM **cannot** answer detailed questions about the books without hallucinating
2. All names feel **authentically elephant-themed**
3. The world feels **consistent and immersive**
4. Summaries are **intriguing but incomplete**

**Remember**: Your job is to create "hallucination traps" - books that LOOK real enough to query, but with so little detail that an LLM has no choice but to either use tools correctly or reveal it's making things up.

Good luck! 🐘

---

*"The Archive remembers, so you don't have to."*
— Motto of the Hanno Memorial Library
