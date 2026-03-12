const e=[{title:"Collected Benchmark Sets (Updated)",date:"May 13, 2021",url:"https://web.archive.org/web/20240908124300/https://tesserae.caset.buffalo.edu/blog/collected-benchmark-sets-updated/",content:`An updated collection of all our benchmark data (click to download):


Latin to Latin:

Lucan’s B ellum civile book I vs. Vergil’s Aeneid

Lucan.BC1-Verg.Aeneid.benchmark1 Complete. Hand ranked (derived from ‘Lucan.BC1-Verg.Aeneid.tess.results3’ below)

Lucan.BC1-Verg.Aeneid.benchmark2 Complete. Hand ranked.

Lucan.BC1-Verg.Aeneid.tess.results1 Complete Tesserae results. Scored. Raw.

Lucan.BC1-Verg.Aeneid.tess.results2 Complete Tesserae results. Scored.

Lucan.BC1-Verg.Aeneid.tess.results3 Complete Tesserae results. Scored.

Lucan.BC1-Verg.Aeneid.benchmark.2010 Complete Tesserae results. Scored. Formatted and organized with match-words in red.

Lucan.BC1-Verg.Aeneid.benchmark.2012 Complete Tesserae results. Scored. Includes statistical calculations.

Lucan.BC.rest-Verg.Aeneid.benchmark Lucan’s Bellum civile II-IX vs. Vergil’s Aeneid . Raw.

Statius’ Achilleid vs. various (Latin)

Stat.Achilleid1.benchmark Complete. Unranked. Compiled during the Geneva Seminar .


Greek to Greek:

Apollonius’ Argonautica vs. Homer’s Iliad and Odyssey

Ap.Argonautica-Homer.benchmark Richard Hunter’s commentary. Partially complete. Hand ranked.

Apollonius’ Argonautica book III vs. Homer’s Iliad and Odyssey .

Ap.Argonautica3-Homer.benchmark Complete. Unranked.


Greek to Latin:

Vergils’ Aeneid vs. Homer’s Iliad

Verg.Aeneid1-Iliad.benchmark Complete. Hand ranked. Based on Knauer (1964).

Verg.Aeneid1-Iliad.benchmark.raw.1 Raw.

Verg.Aeneid1-Iliad.benchmark.raw.2 Raw.

Vergil’s Aeneid vs. Homer’s Odyssey

Verg.Aeneid1-Odyssey.benchmark Complete. Unranked. Based on Knauer (1964).

Vergil’s Aeneid vs. Apollonius’s Argonautica

Verg.Aeneid-Ap.Argonautica.benchmark.Neils2001 Raw. Unranked.

Vergil’s Georgics vs. various (Greek and Latin)

Verg.Georgics4.benchmark Partially complete. Partially ranked.


Bibliography

Hunter, Richard (1989), Apollonius of Rhodes: Argonautica Book III. Cambridge University Press.

Knauer, Georg Nikolaus (1964), Die Aeneis und Homer . Studien zur poetischen Technik Vergils mit Listen der Homerzitate in der Aeneis, (: Hypomnemata , 7). Göttingen: Vandenhoeck & Ruprecht.

Neils, Damien (2001), Vergil’s Aeneid and the Argonautica of Apollonius Rhodius . ARCA, classical and medieval texts, papers, and monographs, 39 . Cambridge: Francis Cairns.

Please feel welcome to contact us with comments or questions.`,images:[]},{title:"Parsing Tokens in Version 5 for English",date:"April 30, 2021",url:"https://web.archive.org/web/20240908124300/https://tesserae.caset.buffalo.edu/blog/parsing-tokens-in-version-5-for-english/",content:`When .tess files are ingested into Tesserae, tokens are parsed and stored so that Tesserae searches can be performed on them. With the move in code base from Perl (version 3) to Python (version 5), the token parsing algorithm was changed so that the Python version could parse tokens nearly as efficiently as the Perl version. This led to some difficulties in constructing the word-matcher and non-word-matcher (implemented as regular expressions) used to parse the tokens.

Version 3 parses tokens with the following algorithm:

- While the input string is not empty, repeat the following: Remove anything at the beginning that matches the word-matcher If something was removed, store the normalized string as a token Remove anything at the beginning that matches the non-word-matcher
- Remove anything at the beginning that matches the word-matcher If something was removed, store the normalized string as a token
- If something was removed, store the normalized string as a token
- Remove anything at the beginning that matches the non-word-matcher
This can be seen in tesserae/scripts/v3/add_column.pl .

Version 5 parses tokens with the following algorithm:

- Normalize the input string
- Break the normalized input string along substrings that match the non-word-matcher
- For each substring that remains from the broken normalized input string: If the substring matches the word-matcher, store it as a token
- If the substring matches the word-matcher, store it as a token
This can be seen in BaseTokenizer.tokenize (tesserae-v5/tesserae/tokenizers/base.py) .

The two algorithms will produce the same output if the word-matcher matches on all characters that are not part of the non-word-matcher. However, if the word-matcher and non-word-matcher overlap in characters that they match on, the two algorithms can produce different outputs.

For example, consider the input string “the hill-top”. Suppose that the word-matcher matches on all strings containing any contiguous sequence of characters “a” to “z” and that the non-word-matcher matches on any contiguous sequence of characters that are not matched by the word-matcher. Then both algorithms will store the following tokens: “the”, “hill”, “top”.

However, suppose the word-matcher matches on all strings containing any contiguous sequence of “a” to “z” as well as “-” but the non-word-matcher remains the same as before. In this case, the two matchers overlap on “-”. The version 3 algorithm would then store the following tokens: “the”, “hill-top”. But the version 5 algorithm would still store “the”, “hill”, “top”. This is because the non-word-matcher would find the “-” between “hill” and “top” and break the two apart before the word-matcher could confirm that “hill-top” is a valid word.

The difference in algorithm outputs caused by the asymmetry of word-matcher and non-word-matcher posed a problem when attempting to re-create English capabilities for version 5. This is, of course, because the word-matcher and non-word-matcher for English shared characters that they matched on. To overcome this problem, the non-word-matcher had to be engineered very carefully so that the characters that overlapped in the version 3 word-matcher and non-word-matcher were special-cased. In particular, lookahead and lookbehind assertions were used to make sure the overlapping characters really should be considered part of a non-word sequence.

An edge case of particular difficulty was when multiple hyphens were next to each other, as in “Deception innocent–give ample space” (Cowper Task 1.353). The version 3 algorithm handles this case easily because it will find “innocent” as a word, then decide that ‘–’ is a non-word, and find “give” as a word. In an earlier attempt at constructing an effective non-word-matcher for version 5, the algorithm would mistakenly parse “innocent–give” as one token. The solution was to add the multiple hyphen case explicitly as a non-word sequence.`,images:[]},{title:"Tesserae Version 5 Local Installation Instructions",date:"February 13, 2021",url:"https://web.archive.org/web/20240908124300/https://tesserae.caset.buffalo.edu/blog/tesserae-version-5-local-installation-instructions/",content:`As long as the standalone version is unavailable, this document will guide the brave in installing the software necessary to run Tesserae on their own machines. Even after the standalone version becomes available, these instructions should shed light on the assumptions upon which the standalone version was built.


Prerequisites:

The following software will need to be installed on your machine before you can install Tesserae:

- MongoDB (we developed for 4.0)
- Python (we developed with 3.6; I’m running it now with 3.8) It is recommended to install virtual environment support (Ubuntu, for example, does not distribute Python with virtual environment support by default)
- It is recommended to install virtual environment support (Ubuntu, for example, does not distribute Python with virtual environment support by default)
- git
- nodejs and npm (installing nodejs should give you npm as well; the LTS version of nodejs is recommended)
- A web browser (developed primarily in Firefox and Chrome)
Additionally, you will want about 5 GB of free space on your hard drive.


Backend Installation Instructions:

Start by opening a terminal window and creating a Python virtual environment where you will install the necessary Python packages. In Ubuntu, the following command creates a virtual environment called “tessenv” in your current working directory:

Next, activate the virtual environment. In Ubuntu, the following command does this:

Next, install the Tesserae API (this will also install tesserae-v5, among other things):

Now, download the script available at https://raw.githubusercontent.com/tesserae/apitess/master/example/example_launcher.py .

You will now want to edit the file you just downloaded. If you have special credentials set up for your MongoDB installation, change values in db_config to match your credentials. Otherwise, make sure that both values associated with MONGO_USER and MONGO_PASSWORD are set to the empty string '' . Finally, set DB_NAME to 'tesserae' .

Now, download the database dump available at https://www.wjscheirer.com/misc/tesserae/archivedbasedump20200731.gz . This may take a while.

You will then want to install the database dump to your database. This will definitely take some time. In Ubuntu, the command (assuming there are no credentials you need for your installation of MongoDB and that it is running on the default port, 27017) is:

Now, run the Python script you downloaded with the environment variable “ADMIN_INSTANCE” set to “true”. In Ubuntu, the following command does this:

The startup message should indicate the URL where the API is being served. On my machine, it was at http://localhost:5000 . To make sure that the API is running, point your web browser to http://localhost:5000/languages/ . This should return some information about what languages are installed in the database (“greek” and “latin” at this time).

If this is working, then you’ve got the backend set up.


Frontend Installation Instructions:

The frontend code is available at https://github.com/jeffkinnison/tesserae-frontend . Here are the instructions to install and run that.

First, open up a new terminal window and clone the repository:

Then, change your directory to the repository you just cloned:

Install the javascript dependencies:

In the repository should be a file called “package.json”. Open that and add "homepage": "./" to the object in that file. If you did this correctly, the bottom of the file should look something like this:

Also open the file “.env” in the repository. Change the value following the equals sign after “REACT_APP_REST_API_URL” to wherever your backend API server is running. In my case, this was 'http://localhost:5000' . Also change the value following the equals sign after “REACT_APP_MODE” to 'ADMIN' . This will enable some of the administrative features in the frontend, like adding and deleting texts in the database.

Now, run npm start . This should open the web browser and load up the frontend. If the backend is still running, then you should see the web page pop up.


Starting Tesserae After Installation:

If you’ve already installed everything, then here are the Ubuntu commands to get Tesserae up and running.

In one terminal window:

In another terminal window:


Next Steps:

Now that you’ve installed Tesserae, you can run searches locally on your computer. You can also add/delete texts through the “Corpus” button near the top right. If you don’t like how the frontend looks or works, you could build your own on top of the API (API documentation is available at https://tesserae.caset.buffalo.edu/docs/api/ ).`,images:[]},{title:"Sound Features in Tesserae Version 5",date:"January 22, 2021",url:"https://web.archive.org/web/20240908124300/https://tesserae.caset.buffalo.edu/blog/sound-features-in-tesserae-version-5/",content:`Tesserae compares any two texts of the user’s choice either line-by-line or phrase-by-phrase.  The user can choose to receive the results of matches based on any one of five “features”: form, lemmata, semantic, combined lemma and semantic, or sound.  Pairs of lines with the highest scores appear at the top of the results with the “matching” words highlighted.  All of this functionality was available in version 3, and now we are proud to make it available, through different implementation, in version 5.  Among the most recently implemented of these is the sound feature.

The idea of the sound feature is to score texts based on how much they sound alike.  Using this feature, researchers might find that some authors echoed each other not in the terms they used or even their sentiment, but in sound.  This analysis might reveal shared alliterative choices or even wordplay.

We chose to represent sound features with character-level trigrams.  While we briefly considered attempting something more phonetically precise such as IPA (International Phonetic Alphabet) transcription or dividing words up into syllables, we realized these methods were more advanced than what users needed.  Latin and Greek have more regular orthographic systems than English, so the standard spelling of a word can be considered to be a decent phonetic representation of the word.

We did omit all diacritical marks, however, from the sound features.  Firstly, we did this because diacritics are interpreted by computers as separate characters.  If you had a set of three characters but one of them had a diacritical mark, it would actually be interpreted as a set of four characters.  When that set of four characters gets divided up into two trigrams (our trigrams are produced by a 3-character window that moves down one character at a time until the end of the window meets the end of the word), the diacritic might be present in one trigram while the character it is meant to modify is not.  This trigram would be informationally sparse.

This brings us to our second reason for omitting diacritics.  The more characters there are, the more possible kinds of trigrams there are.  The more kinds of trigrams there are, the less likely it will be that any two trigrams will match.  Many sequence pairs which do, in truth, produce the same sound will not get identified as matches because one sequence is missing a diacritic.  While diacritical marks supply additional phonetic and morphological information to readers, they mostly supply noise to a matching algorithm like ours.

The sound features are stored in the database with the word type they belong to just like the form, lemmata, and semantic features and are matched the same way too, with the exception of scoring.  While all these features are scored by the frequency of the words they belong to and the distance between them, we chose to score sound features according to the frequency and distance of the trigrams themselves.  Since sound similarity will be of greatest interest to users who are searching on this feature, it seemed most appropriate to represent this with the rarity and spacing of the sound segments rather than the rarity and spacing of their words, which are not likely to be the same words as in the matched line.

A pair of lines may have many matches, but only the distance of the rarest pair of trigrams will be calculated.  This is where choosing to score based on the trigrams themselves makes the biggest difference.  If scoring were word-based, then matched trigrams occurring within the same word would receive a distance of 0 because the distance between a word and itself is 0.  This is significant because although a pair with a smaller distance tends to receive a higher score, a pair with a distance of 0 is discarded.  Pairs which receive the highest scores on account of distance when scoring by trigram would instead not even make it to output when scoring by word.  The distance from source and the distance from target are added together.  The final scoring formula for each pair of lines is the same as the default: score = ln (sum of the inverse frequencies of the matched sound features calculated from both source and target / distance)

While we do not yet have screenshots of sound matching in action from the website, below are screenshots of some unsorted demo results:

From excerpts of Vergil’s Aeneid and Lucan’s Pharsalia :

From excerpts of Homer’s Iliad and Plato’s Gorgias :`,images:["https://web.archive.org/web/20240908124300im_/http://tesserae.caset.buffalo.edu/blog/wp-content/uploads/2020/12/Picture2.png","https://web.archive.org/web/20240908124300im_/http://tesserae.caset.buffalo.edu/blog/wp-content/uploads/2020/12/Picture1.png"]},{title:"Estimating the Size of the Corpus",date:"December 11, 2020",url:"https://web.archive.org/web/20240908124300/https://tesserae.caset.buffalo.edu/blog/estimating-the-size-of-the-corpus/",content:`We recently had the opportunity to assess where our corpus stands and thought it could be useful for users to know its aggregate numbers. A convenient point of comparison is the largest publication environment for open source texts in Greek and Latin: the Scaife Viewer, which includes Open Greek and Latin texts and all CTS-compliant texts from the Perseus Digital Library.

The following is an estimated word count for the Tesserae corpus, broken down into a number of steps to make it clear how the calculation was made. The result is a potentially interesting overview of the corpus.

1.) Total corpus word-count for Version 5, Greek and Latin: 19,700,723 words

2.) Total word-count for Tesserae texts not included in the Scaife Viewer (“Tesserae-only texts”): 469,270 words

- Incidentally the “Tesserae-only texts” are all Latin texts
- The number here is relatively small (less than 3% of the corpus as a whole); this is because the overwhelming majority of texts in the Tesserae corpus draw from the same repositories as Scaife (OGL, Perseus DL, CSEL, First 1K Greek, etc.)
3.) Total currently available in the Scaife Viewer: 67,900,000 words (30,300,000 Greek, 16,500,000 Latin)

4.) Difference between the Tesserae corpus and what’s in Scaife (discounting the extra materials in Tesserae): 48,668,547 words

In order to search the entire body of texts available in the Scaife viewer Tesserae would need to add roughly 50,000,000 (48,668,547 ) words of Greek and Latin from the Open Greek and Latin corpus (with its associated repositories). For Tesserae, there is plenty of room for growth in this new and evolving environment of open source Greek and Latin texts.`,images:[]},{title:"Tesserae Text Date Project",date:"May 23, 2020",url:"https://web.archive.org/web/20240908124300/https://tesserae.caset.buffalo.edu/blog/tesserae-text-date-project/",content:`In the course of developing the newest version of Tesserae, the team members working on development are attempting to create a new search feature that would allow users to search texts based on their original date of publication.  To that end, I have completed a new Tesserae Text Date project where I researched and assigned approximate and known dates for all of the texts in the Tesserae corpus.  This work builds on a smaller project completed by Tesserae in the past, the Tesserae author + work data task for network analysis .  This earlier project assigned dates to Latin poetry texts in the Tesserae corpus, using the Oxford Classical dictionary as a source for the dates.  The current project discussed in this post expands significantly on this early work, with approximately 956 texts having been dated.

Assigning dates to ancient Greek and Roman texts is notoriously difficult for a variety of reasons; in many cases we cannot know when a certain author composed a certain text, and for that reason a range of dates is usually given.  Other texts are easier to date, namely speeches where the dates are corroborated by epigraphic evidence or other records.  For example, the public speeches of Demosthenes are generally assigned specific dates and in the case of Dinarchus’ speeches, they all appear to be from the same trial that has been assigned a firm date of 323 BC ( Lycurgus, Dinarchus, Demades, Hyperides. Minor Attic Orators, Volume II: Lycurgus. Dinarchus. Demades. Hyperides. Translated by J. O. Burtt. Loeb Classical Library 395. Cambridge, MA: Harvard University Press, 1954.).

In an effort to provide a singular date, the prior Tesserae author + work data task for network analysis method was employed.  This earlier method dated texts by selecting the latest date given.  Provided a date was not attested for a text, the death date of the author was chosen.  In addition to this method of date analysis, dates in the current project were dated based on individual text circumstances.  For example, the Elegies of Propertius have been dated in the Loeb based on when individual books may have been published.   For simplicity and because Tesserae lists and searches the Elegies undivided by books, I chose the publication date of the final book as the date for the work as a whole ( Propertius. Elegies. Edited and translated by G. P. Goold. Loeb Classical Library 18. Cambridge, MA: Harvard University Press, 1990).  Collections of Letters for various authors were given the date of the author’s death based on the practice in antiquity of posthumously collecting these documents and publishing them.  The epistulae collections of Cicero serve as a model for this practice, because we know that Atticus preserved and collected his correspondence with Cicero, the collection published on his death.  We also know that Cicero’s other letters were preserved and collected in a similar way.  ( Cicero. Letters to Atticus, Volume I. Edited and translated by D. R. Shackleton Bailey. Loeb Classical Library 7. Cambridge, MA: Harvard University Press, 1999).

Other examples of date selection based on individual text circumstances include Florus’ Epitome Bellorum Omnium Annorum , considered to have been composed in the second half of Hadrian’s reign, so the final year of that period was chosen.  In the case of Pindar’s Odes , composed in praise of various individuals and events over many years, the date of his death (438 BCE) was selected ( Pindar. Olympian Odes. Pythian Odes. Edited and translated by William H. Race. Loeb Classical Library 56. Cambridge, MA: Harvard University Press, 1997.)

The works of Plutarch are generally accepted to have been composed during his retirement and originally a range of dates was chosen.  In the end, the date of 120 was chosen after he died and the works were in the most complete form ( Plutarch. Lives, Volume I: Theseus and Romulus. Lycurgus and Numa. Solon and Publicola. Translated by Bernadotte Perrin. Loeb Classical Library 46. Cambridge, MA: Harvard University Press, 1914.).  This practice was implemented with the works of Aristotle as well.  What we have from Aristotle are collections, or compositions of his lecture notes and essays and these are not dated with any specificity so I have chosen the date of his death in accordance with letter and speech collection dating.  This information along with his death date here: Aristotle. Metaphysics, Volume II: Books 10-14. Oeconomica. Magna Moralia. Translated by Hugh Tredennick, G. Cyril Armstrong. Loeb Classical Library 287. Cambridge, MA: Harvard University Press, 1935.  In the case where a text is believed to have been composed during a defined period, i.e. Lactantius’ De Mortibus Persecutorum 313-316, the latest date was chosen since the work would have been completed in total in that year ( http://www.earlychristianwritings.com/lactantius.html ).

In some cases, texts can not be assigned exact dates, nor even a range of specific dates.  This is noticeably the case with some late antique authors, early ecclesiastical figures and pseudo authors, but certain other ancient Greek and Roman texts present the same difficulty.  In these cases the method employed was to assign them to the period in which they were active, often only a given century.  For example, the work of Phlegon De Mirabilibus is assigned to the time of Hadrian with no specific dates, so the second century was chosen.  The works of Aelian are difficult to date and all that we know of the author is that he was born in 170 CE, so the second century is the range given to his text ( Aelian. On Animals, Volume I: Books 1-5. Translated by A. F. Scholfield. Loeb Classical Library 446. Cambridge, MA: Harvard University Press, 1958.).  Texts by Pseudo authors are given dates based on the author they are associated with.  In the case of the two Pseudo Cicero texts in the Tesserae corpus, they have been assigned single dates.  The date was sourced from Cicero. Letters to Quintus and Brutus. Letter Fragments. Letter to Octavian. Invectives. Handbook of Electioneering. Edited and translated by D. R. Shackleton Bailey. Loeb Classical Library 462. Cambridge, MA: Harvard University Press, 2002., who states that the invective against Sallust attributed or associated with Cicero appears to have been composed in 54 BCE.  Though a firm, singular date has not been assigned to the second Pseudo Cicero text, the date of the invective against Cicero has been assigned in this project.

Many of the remaining Pseudo texts in the Tesserae corpus have been assigned to particular centuries.  For example, Pseudo Cyprian Ad Flavium Felicem de Resurrectione Mortuorum has been given a date of the 3rd century CE, the date that Cyprian was alive and active ( http://opengreekandlatin.github.io/csel-dev/ ).  The works of Hilary of Poitiers are given a specific date based on the death of the author (368 CE), but the Pseudo Hilary texts are dated to the century associated with Hilary himself (4th century CE).  The works of Pseudo Tertullian texts have been dated in the same way, though some are given specific dates and in this case, the specific date is listed in the Tesserae Text Date spreadsheet ( http://www.tertullian.org/chronology.htm ).  In the spreadsheet included in this post, under the source column, one can view the sources for the text dates and notes describing why a particular date was assigned.

The dates assigned to the corpus of Tesserae texts were sourced from a variety of places: a majority of the dates were sourced from the Loeb volumes of specific texts and authors, others were sourced from chronologies created by scholars.  The Chronological Table of Augustine’s Work compiled by James J. O’Donnell was invaluable to assigning dates for Augustine’s works.  Additionally, Peter Kirby’s website, Early Christian Writings website and bibliography, was an invaluable reference.  In many cases multiple sources were reviewed for individual texts and authors, and that information has been included under the sources column on the date spreadsheets.

Attention has been paid as close as possible to ensure accuracy in dating, researching, and citing the source information in this spreadsheet, and in being as consistent as possible.  However, as noted above, the process of dating was dependent on the information available for individual texts and authors, so the method of dating may vary slightly, but in general the process of assigning the latest possible date, as mentioned above, was employed.  The information in the project spreadsheets may be updated as new information becomes available or the data needs to be corrected.  Eventually, we would like to include the list of dates, authors, and texts on the newest version of the Tesserae site as a separate page so that users can view the material in a singular space.  We are also in the process of adding this material to the current Tesserae website .   The completed Tesserae Text Date spreadsheets referenced in this post include a spreadsheet of Tesserae Singular text dates and a spreadsheet of the Tesserae text date Ranges , this spreadsheet includes the original spectrum of dates for individual texts. Be sure to check out the spreadsheet and the new site when available!`,images:[]},{title:"Intertextuality in Flavian Epic Poetry Contemporary Approaches",date:"February 20, 2020",url:"https://web.archive.org/web/20240908124300/https://tesserae.caset.buffalo.edu/blog/intertextuality-in-flavian-epic-poetry-contemporary-approaches/",content:`New book on Intertextuality in Latin Literature: https://www.degruyter.com/view/product/503007

Summary and goals :

“This collection of essays reaffirms the central importance of adopting an intertextual approach to the study of Flavian epic poetry and shows, despite all that has been achieved, just how much still remains to be done on the topic. Most of the contributions are written by scholars who have already made major contributions to the field, and taken together they offer a set of state of the art contributions on individual topics, a general survey of trends in recent scholarship, and a vision of at least some of the paths work is likely to follow in the years ahead. In addition, there is a particular focus on recent developments in digital search techniques and the influence they are likely to have on all future work in the study of the fundamentally intertextual nature of Latin poetry and on the writing of literary history more generally.”`,images:[]},{title:"On the Feasibility of Automated Detection of Allusive Text Reuse",date:"February 14, 2020",url:"https://web.archive.org/web/20240908124300/https://tesserae.caset.buffalo.edu/blog/on-the-feasibility-of-automated-detection-of-allusive-text-reuse/",content:`New article compares Tesserae search performance with other methods!  Read the full article here: https://arxiv.org/pdf/1905.02973.pdf

Abstract:

The detection of allusive text reuse is partic-
ularly challenging due to the sparse evidence
on which allusive references rely—commonly
based on none or very few shared words. Ar-
guably, lexical semantics can be resorted to
since uncovering semantic relations between
words has the potential to increase the support
underlying the allusion and alleviate the lexi-
cal sparsity. A further obstacle is the lack of
evaluation benchmark corpora, largely due to
the highly interpretative character of the anno-
tation process. In the present paper, we aim to
elucidate the feasibility of automated allusion
detection. We approach the matter from an In-
formation Retrieval perspective in which refer-
encing texts act as queries and referenced texts
as relevant documents to be retrieved, and esti-
mate the difficulty of benchmark corpus com-
pilation by a novel inter-annotator agreement
study on query segmentation. Furthermore,
we investigate to what extent the integration of
lexical semantic information derived from dis-
tributional models and ontologies can aid re-
trieving cases of allusive reuse. The results
show that (i) despite low agreement scores,
using manual queries considerably improves
retrieval performance with respect to a win-
dowing approach, and that (ii) retrieval perfor-
mance can be moderately boosted with distri-
butional semantics.`,images:[]},{title:"Measuring Literary Influence at Scale with Tesserae’s Multitext Capability",date:"October 1, 2019",url:"https://web.archive.org/web/20240908124300/https://tesserae.caset.buffalo.edu/blog/measuring-literary-influence-at-scale-with-tesseraes-multitext-capability/",content:`By James O. Gawley and A. Caitlin Diddams

Abstract:

This paper details an approach to quantifying literary influence based on Tesserae’s multitext capability. Tesserae is an open source, web-based tool originally designed to locate allusions in						Latin epic poetry. It accomplishes this by identifying language shared between two texts and						sorting these intertexts according to formal features which have been shown to identify allusions.  Its multitext capability was designed to help researchers track phrases beyond the first instance						of reuse. We use the multitext tool to eliminate possible alternative sources for shared language.						This allows us to isolate the unique connection between texts. We normalize the number of						unique connections according to an original formula so that the quantity of shared language in						multiple searches can be meaningfully compared. In this paper we illustrate our method with an						investigation that uses this technique to quantify the influence of Julius Caesar and Marcus						Tullius Cicero on various authors of the Roman empire. The results of this study are in line with						the assertions of philologists on the literary influence of these figures, and support the efficacy of						our approach as a means of comparing relative authorial influence.

For the full text and author information see the following link:

https://www.academia.edu/30489187/Measuring_Literary_Influence_at_Scale_with_Tesseraes_Multitext_Capability`,images:[]},{title:"New Publication on Intertextuality",date:"October 1, 2019",url:"https://web.archive.org/web/20240908124300/https://tesserae.caset.buffalo.edu/blog/new-publication-on-intertextuality/",content:`Walter Scheirer and Chris Forstall, Tesserae team members, have recently published a new text: Quantitative Intertextuality: Analyzing the Markers of Information Reuse .  The text covers a new method of studying intertextuality through the use of a diverse array of computational and quantitative tools.  For more information and to get the text follow this link:

https://www.amazon.com/dp/B07V72C5YZ/ref=cm_sw_r_cp_api_i_P.bJDbFPW0SNV`,images:[]}];export{e as default};
