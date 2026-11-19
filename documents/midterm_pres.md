# Midterm presentation

## Introduction

- Motivation: Why do we want to extract predictions?
    - **Goal** is benchmark for AI with training data cutoff date in the past to test hindcasting accuracy → in turn used to improve forecasting abilities of models with recent cutoff
    - Benchmark in the shape of a dataset that contains **specific questions** about the relative future that are derived from predictive statements (e.g. “Will England beat Spain in the final game of the 1954 world cup?”)
    - Together with source & date of statement, it’s time horizon, and **actual outcome**
    - If we just want questions we can ask an LLM about the future from a perspective in the past, why don’t we formulate them on the basis of the facts we already know now? [insert timeline for clarification]
        
        → Because predictive statements (give us a chance to) capture exactly those questions that carry enough uncertainty to be interesting to ask, but are confined enough to be worth trying to predict. 
        In addition, these statements communicate an uncertainty about an event which is important enough for the people at that time to formulate in a newspaper. The questions we extract therefore were of a non-trivial nature. Examining (and training) today’s LLMs based on those questions allows us to create models that can answer similar questions about our own future.
        
- What is a prediction? And what is a good prediction?
    - Definition of a prediction: (use certainty continuum)
        - Any statement about the future can be seen as a prediction [give example of astronomical event like “On Monday, the 9th of August, we will have a full moon.”, then go one step towards uncertainty with “The 1962 FIFA World Cup will be held in Chile.”]
        - But many of these statements don’t carry any inherent **uncertainty**. They are expected to be true, no matter what.
        - So for our purpose, a prediction should ideally carry at least some uncertainty.
        - ALSO: mention conditional statements
    - Quality of a prediction: [expand with verifiability dimension, draw on two axes]
        - Some predictions are much more easy to verify than others
        - BUT often those that are not as easy to verify (more subjective) are the more interesting ones for us. (”The winter will be harsh.”)
- How could we actually build the dataset?
    - **Prediction-based**: extract actual predictive statements, try finding the outcomes for them
    - **Fact-based**: start with facts (that are reported on in newspapers) indicating an uncertainty in hindsight (e.g., “Contrary to popular belief, the Republicans did not win this election.”) → synthesize corresponding questions (”Who will win this election?”)

## Extraction methods we tried

- To extract the actual statements from articles on Impresso, we experimented with a variety of different approaches.
- The platform offers an API that (among other parameters) lets you search by key words (cues) and years → try different combinations of future cues and topic-specific key words to extract articles that contain predictions
    - When using **topic cues** combined with **strong future cues** ⇒ too little amount of extracted predictions with mediocre quality [show sample]
    - When searching only with **strong future cues** [give examples] ⇒ ended up with too much noise (many of the extracted statements were not what we consider a usable prediction) [show sample, highlight good results]
    - When searching only with **weaker futures cues** [give examples] ⇒ too many extractions overall, out of which most weren’t what we consider an interesting prediction neither
- For now, we found **two methods** that delivered more promising results than the others:
    - Using topic cues in combination with weaker future cues ⇒ ratio of predictions still relatively low [insert exact number], but quality closer to what we hoped to see
    [Show process and results in more details, Samuel’s work]
    - Diving the extraction in two separate steps: Article selection (search) & LLM based extraction [Lucas’ work] ⇒ most promising results with good quality
        - Download broad range of articles with topic cues and a few weaker future cues
        - Feed those articles entirely to an LLM with a carefully crafted prompt [present with most important features] to extract any predictions it contains → require strict JSON output schema [show header of table containing this schema]
        - Directly use that same prompt to enrich each extracted prediction with:
            - The originally extracted quote
            - The prediction **resolution**: a statement in English containing the context (by filling in references to it) and the time the resolution date
            - The category (one of the pre-defined list)
            - The resolution date (time the outcome should be known)
            - The predictor (who makes the prediction)
            - The confidence (certain/likely/possible/unlikely)
            - And a boolean stating whether the outcome is realistically **verifiable**
    - Show selection of results (numbers and actual data; 800 articles, 3400 predictions)

## Evaluation & Next Steps

- Example of false positive: 

LSE-1958-03-27-a-i0032,1958-03-27,"Le Peuple, La Sentinelle",fr,3169,science_technology,la semaine de cinq jours ne sera pas introduite dans les classes primaires,"As of March 1958, the five-day school week will not be introduced in the primary schools of Le Locle.",**education,**,bureau de la Commission scolaire du Locle,certain,True

→ Doesn’t actually claim anything about the future, but reports on a decision
- Biggest missing part (where most of the future work lies): source of truth for outcome of the statements
- Another To Do: Question generation from resolved prediction statements (to feed to language model as benchmark)
- Cost and compute
    - 1$ exploration 4$ extraction => quite good for extraction
    - Costs for statement outcome search expected to be a little higher, reduced input domain, still needs work
    - Cost mitigation possibilities
        - Back select articels (using cues) with high degree of outcome verifiability
        - Try an impresso search for newspapers reporting back on events (after resolution date)
        - But cost should remain proportional (linear) to final dataset quantity!

## One-slide summary & conclusion