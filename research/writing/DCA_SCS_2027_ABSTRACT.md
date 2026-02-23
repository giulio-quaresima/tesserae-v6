# DCA SCS 2027 Abstract: Experimental Contexts for Digital Classics

**Panel:** Experimental Contexts for Digital Classics (Digital Classics Association)
**Deadline:** Friday, February 20, 2026
**Submit to:** digitalclassicsassociation@gmail.com
**Format:** Anonymous, ≤400 words; identifying info in email. SCS member confirmation required.

---

## Title

Multi-Channel Fusion for Improving Intertextual Search Recall

---

## Abstract (≤400 words)

Intertextual search systems for classical Latin have relied on lexical overlap to identify parallels. Coffee et al. (2012) reported ~27% recall on Lucan–Vergil parallels using Tesserae V3. Manjavacas et al. (2019) showed hybrid models outperform purely lexical approaches, and Burns (forthcoming) argues word embeddings are key to improving recall. Yet many allusions rely on phonetic echoes, structural imitation, synonym substitution, or single pivotal words. This study tests whether multi-channel fusion can substantially improve recall.

**Method.** We evaluated Tesserae V6 on five benchmarks: Lucan *BC* 1 vs. Vergil *Aeneid* (Coffee et al. 2012; 213 gold pairs), Valerius Flaccus *Argonautica* 1 vs. Vergil (Dexter et al. 2024; 521 pairs), and Statius *Achilleid* 1 vs. Vergil, Ovid *Metamorphoses*, and *Thebaid* (Geneva 2015; gold = 2+ commentators). Nine channels run independently over the same source–target line pairs, each using a different algorithm: two lemma-based (requiring 2 and 1 shared lemmas), exact token matching, SPhilBERTa sentence embeddings for neural semantic similarity (Riemenschneider and Frank 2023), curated synonym dictionary for lexicographic matching, sound similarity via character trigrams, Levenshtein fuzzy matching, UD syntax patterns, and rare-word detection. The best configuration merges all nine via weighted score fusion: each match is scored by a channel-specific weight (highest for phonetic and edit-distance, lowest for single-lemma), with a bonus for pairs found by multiple channels. Additional tuning: unbounded IDF scoring (preserving discrimination above 1.0) and embedding threshold cosine ≥ 0.85 with no lexical overlap requirement.

**Results.** This achieves 76.5% recall on Lucan–Vergil (163/213) and 84.5% on VF–Vergil (440/521) — nearly tripling the V3 baseline. Relaxing shared lemmas from 2 to 1 was the single largest contributor (+21 percentage points), recovering allusions built around single charged words such as *cano* (Lucan 1.2 echoing Vergil's opening). Weighted fusion achieves precision at 10 (P@10) of 90% on VF–Vergil, meaning 9 of the first 10 results are commentary-attested parallels. Results generalize across all five benchmarks, with recall from 76.5% to 87.0%.

**Discussion.** The multi-channel approach reveals distinct allusive strategies — single-word echoes, phonetic play, synonym substitution, structural imitation — each captured by a different channel. An estimated 40% of remaining misses share no vocabulary at all, representing thematic parallels at the limit of feature-based detection. The system runs on a single server in three hours without GPU.
