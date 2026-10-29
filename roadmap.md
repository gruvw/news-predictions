# First Statement Extraction Process

## 1. Determine clear prediction type candidates
- Doubling down Topic type of pediction (elections / sports events...)
  - Candidates
    - Election results
    - Sport event outcomes
  - Justification
    - Can carry multiple predictions in one sentence
    - Outcome easily findable in publicly available sources (news/wikipedia)

 - Nature of prediction is more important than where the prediction comes from
  

## 2. Define Impresso search parameters
#### Cues / Search terms
- Find the types of clues that lead to the highest density predictions in results 
- Is it a statement about the futur? → Refine the search terms to match grammar/expressions about future

#### Impresso topic selection
- Figure out how the topics work in Impresso and which ones to select for each of the prediction candidates  


## 3. Extracting the data
- Given the context, how much certainty can be attributed to the statement → Find way to separate clear statements (high certainty) about planned events from predictions (mabye employ LLM)
- Statement needs to have enough potential for "objective" evaluation (by numbers, news reporting, etc.)
  - Example: "If the Prime Minister loses this election, he will not be able to look at himself in the mirror anymore."

## 4. Outcome Determination
- Manual Validation of prediction first
- Finding a way to automatically determine the outcome of a prediction by checking later sources for cues that are specific to each prediction